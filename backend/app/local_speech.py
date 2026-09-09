from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    voice = os.getenv("FRAMECRAFT_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
    try:
        import edge_tts

        asyncio.run(edge_tts.Communicate(text=text, voice=voice, rate="+4%").save(str(out_path)))
        return {"provider": "edge-tts", "voice": voice, "audio_path": str(out_path)}
    except Exception as edge_error:
        if shutil.which("say"):
            wav_path = out_path.with_suffix(".aiff")
            proc = subprocess.run(["say", "-v", "Tingting", "-r", "190", "-o", str(wav_path), text], capture_output=True, text=True)
            if proc.returncode == 0:
                convert = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), str(out_path)], capture_output=True, text=True)
                wav_path.unlink(missing_ok=True)
                if convert.returncode == 0:
                    return {"provider": "macos-say", "voice": "Tingting", "audio_path": str(out_path)}
        raise RuntimeError(f"讲稿配音失败：{edge_error}") from edge_error


def transcribe_audio_local(audio_path: Path, out_dir: Path, language: str = "zh") -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    whisper = shutil.which("whisper-cli")
    if not whisper:
        raise RuntimeError("服务器缺少 whisper-cli，无法转写上传音频。")
    model = _find_whisper_model()
    if not model:
        raise RuntimeError("服务器缺少 Whisper small 模型。请配置 FRAMECRAFT_WHISPER_MODEL。")
    wav = out_dir / "whisper_input.wav"
    converted = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_path), "-vn", "-ar", "16000", "-ac", "1", str(wav)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if converted.returncode != 0:
        raise RuntimeError(f"音频预处理失败：{(converted.stderr or '').strip()[-600:]}")
    prefix = out_dir / "whisper"
    proc = subprocess.run(
        [whisper, "--model", str(model), "--language", language, "--output-json-full", "--output-file", str(prefix), str(wav)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    if proc.returncode != 0 or not prefix.with_suffix(".json").is_file():
        raise RuntimeError(f"Whisper 转写失败：{(proc.stderr or proc.stdout or '').strip()[-1000:]}")
    raw = json.loads(prefix.with_suffix(".json").read_text(encoding="utf-8"))
    words: list[dict[str, Any]] = []
    full_text: list[str] = []
    for segment in raw.get("transcription") or []:
        segment_text = str(segment.get("text") or "").strip()
        if segment_text:
            full_text.append(segment_text)
        for token in segment.get("tokens") or []:
            token_text = str(token.get("text") or "").strip()
            offsets = token.get("offsets") or {}
            if not token_text or token_text.startswith("[_") or offsets.get("to", 0) <= offsets.get("from", 0):
                continue
            words.append({"text": token_text, "start": round(float(offsets["from"]) / 1000, 3), "end": round(float(offsets["to"]) / 1000, 3)})
    if not words:
        raise RuntimeError("Whisper 没有生成可用逐字时间码。")
    return {"text": "".join(full_text), "words": words, "model": str(model), "provider": "whisper.cpp"}


def _find_whisper_model() -> Path | None:
    configured = os.getenv("FRAMECRAFT_WHISPER_MODEL", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path.home() / ".cache/hyperframes/whisper/models/ggml-small.bin",
        Path("/opt/framecraft/models/ggml-small.bin"),
        Path("/FrameCraft/models/ggml-small.bin"),
    ]
    return next((path for path in candidates if path and path.is_file()), None)
