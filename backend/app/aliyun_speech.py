from __future__ import annotations

import base64
import json
import mimetypes
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from . import store


DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def speech_settings() -> dict[str, str]:
    settings = store.snapshot().get("settings", {})
    return {
        "api_key": os.getenv("DASHSCOPE_API_KEY", "").strip()
        or str(settings.get("dashscope_api_key") or "").strip(),
        "base_url": str(
            os.getenv("DASHSCOPE_BASE_URL")
            or settings.get("dashscope_base_url")
            or DEFAULT_DASHSCOPE_BASE_URL
        ).rstrip("/"),
        "compatible_base_url": str(
            os.getenv("DASHSCOPE_COMPATIBLE_BASE_URL")
            or settings.get("dashscope_compatible_base_url")
            or DEFAULT_COMPATIBLE_BASE_URL
        ).rstrip("/"),
        "tts_model": str(settings.get("tts_model") or "qwen3-tts-flash"),
        "tts_voice": str(settings.get("tts_voice") or "Cherry"),
        "asr_model": str(settings.get("asr_model") or "qwen3-asr-flash"),
    }


def probe_duration_s(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"读取音频时长失败：{(proc.stderr or '').strip()[-600:]}")
    return max(0.1, float((proc.stdout or "0").strip()))


def synthesize_speech(text: str, out_path: Path) -> dict[str, Any]:
    cfg = speech_settings()
    if not cfg["api_key"]:
        raise RuntimeError("阿里云百炼 API Key 未配置，无法生成科普旁白。")
    clean_text = (text or "").strip()
    if not clean_text:
        raise RuntimeError("旁白文本为空，无法调用阿里云 TTS。")
    if len(clean_text) > 600:
        raise RuntimeError("单段旁白超过阿里云 TTS 的 600 字符限制，请先分段。")
    response = _request_with_retry(
        "post",
        f"{cfg['base_url']}/services/aigc/multimodal-generation/generation",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={
            "model": cfg["tts_model"],
            "input": {"text": clean_text, "voice": cfg["tts_voice"], "language_type": "Chinese"},
        },
        timeout=90,
    )
    if not response.ok:
        raise RuntimeError(f"阿里云 TTS 请求失败（{response.status_code}）：{_safe_error(response)}")
    payload = response.json()
    audio = ((payload.get("output") or {}).get("audio") or {})
    audio_url = str(audio.get("url") or "").strip()
    audio_data = str(audio.get("data") or "").strip()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if audio_url:
        download = _request_with_retry("get", audio_url, timeout=90)
        download.raise_for_status()
        out_path.write_bytes(download.content)
    elif audio_data:
        out_path.write_bytes(base64.b64decode(audio_data))
    else:
        raise RuntimeError("阿里云 TTS 没有返回可下载音频。")
    duration = probe_duration_s(out_path)
    return {
        "provider": "aliyun-bailian",
        "model": cfg["tts_model"],
        "voice": cfg["tts_voice"],
        "audio_path": str(out_path),
        "duration_s": round(duration, 3),
        "request_id": payload.get("request_id"),
    }


def transcribe_audio_cloud(audio_path: Path, out_dir: Path, language: str = "zh") -> dict[str, Any]:
    cfg = speech_settings()
    if not cfg["api_key"]:
        raise RuntimeError("阿里云百炼 API Key 未配置，无法识别上传媒体。")
    out_dir.mkdir(parents=True, exist_ok=True)
    asr_input = out_dir / "aliyun_asr_input.mp3"
    converted = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_path),
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "48k", str(asr_input),
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if converted.returncode != 0:
        raise RuntimeError(f"阿里云 ASR 音频预处理失败：{(converted.stderr or '').strip()[-600:]}")
    if asr_input.stat().st_size > 10 * 1024 * 1024:
        raise RuntimeError("上传媒体超过同步 ASR 的 10MB 限制，请将时长控制在 5 分钟内。")
    mime = mimetypes.guess_type(asr_input.name)[0] or "audio/mpeg"
    encoded = base64.b64encode(asr_input.read_bytes()).decode("ascii")
    response = _request_with_retry(
        "post",
        f"{cfg['compatible_base_url']}/chat/completions",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={
            "model": cfg["asr_model"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"data": f"data:{mime};base64,{encoded}"}}
                    ],
                }
            ],
            "stream": False,
            "asr_options": {"language": language, "enable_itn": True},
        },
        timeout=240,
    )
    if not response.ok:
        raise RuntimeError(f"阿里云 ASR 请求失败（{response.status_code}）：{_safe_error(response)}")
    payload = response.json()
    try:
        text = str(payload["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("阿里云 ASR 返回结构中没有逐字稿。") from exc
    if not text:
        raise RuntimeError("阿里云 ASR 返回的逐字稿为空。")
    return {
        "text": text,
        "words": [],
        "model": cfg["asr_model"],
        "provider": "aliyun-bailian",
        "request_id": payload.get("id"),
    }


def _safe_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        return str(payload.get("message") or payload.get("error") or payload.get("code") or "请求未成功")[:500]
    except (ValueError, AttributeError):
        return response.text[:500]


def _request_with_retry(method: str, url: str, *, attempts: int = 3, **kwargs: Any) -> requests.Response:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == attempts:
                return response
            response.close()
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt == attempts:
                raise
        time.sleep(1.5 * attempt)
    if last_error:
        raise last_error
    raise RuntimeError("阿里云语音请求重试结束但没有返回结果。")
