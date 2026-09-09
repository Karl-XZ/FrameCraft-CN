from __future__ import annotations

import json
import math
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import store
from .local_speech import probe_duration_s, synthesize_speech, transcribe_audio_local


@dataclass
class PreparedSource:
    mode: str
    source_dir: Path
    source_text: str
    source_audio_path: Path | None
    transcript_path: Path | None
    scene_seed_path: Path | None
    metadata_path: Path


def script_file_path(project_id: str) -> Path:
    return store.project_dir(project_id) / "input" / "script.txt"


def write_script_text(project_id: str, text: str) -> Path:
    path = script_file_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((text or "").strip() + "\n", encoding="utf-8")
    return path


def read_script_text(project: dict[str, Any]) -> str:
    pid = str(project.get("id") or "")
    if not pid:
        return ""
    direct = str(project.get("script_text") or "").strip()
    if direct:
        return direct
    path = script_file_path(pid)
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def transcript_json_path(project_id: str) -> Path:
    return store.project_dir(project_id) / "input" / "transcribe" / "transcript.json"


def ensure_version_subtitles(project_id: str, version_dir: Path) -> Path | None:
    subtitle_path = version_dir / "subtitles.srt"
    if subtitle_path.is_file() and subtitle_path.stat().st_size > 0:
        return subtitle_path
    transcript_path = transcript_json_path(project_id)
    if not transcript_path.is_file():
        return None
    try:
        words = json.loads(transcript_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    cues = build_subtitle_cues(words)
    if not cues:
        return None
    subtitle_path.write_text(render_srt(cues), encoding="utf-8")
    return subtitle_path


def prepare_source_bundle(project_id: str) -> PreparedSource:
    data = store.snapshot()
    project = data["projects"].get(project_id) or {}
    assets = [a for a in data["assets"].values() if a["project_id"] == project_id]
    source_dir = store.project_dir(project_id) / "input"
    source_dir.mkdir(parents=True, exist_ok=True)

    script_text = read_script_text(project)
    if script_text:
        return prepare_script_source(project_id, project, source_dir, script_text)

    audio_asset = choose_audio_asset(assets)
    if not audio_asset:
        raise RuntimeError("请上传一条解说音频，或者先填写讲稿文字。")
    return prepare_audio_source(project_id, project, source_dir, Path(str(audio_asset["path"])).resolve())


def prepare_script_source(
    project_id: str,
    project: dict[str, Any],
    source_dir: Path,
    script_text: str,
) -> PreparedSource:
    script_path = write_script_text(project_id, script_text)
    source_audio = source_dir / "source_audio.mp3"
    tts_meta = synthesize_speech(script_text, source_audio)
    transcript_dir = source_dir / "transcribe"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_txt = normalize_script_text(script_text)
    words = make_pseudo_timed_words(transcript_txt, probe_duration_s(source_audio))
    transcript_path = transcript_dir / "transcript.json"
    transcript_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    (transcript_dir / "transcript.txt").write_text(transcript_txt + "\n", encoding="utf-8")
    words = json.loads(transcript_path.read_text(encoding="utf-8"))
    scene_seed = build_audio_scene_seed(words)
    seed_path = source_dir / "scene_seed.json"
    seed_path.write_text(json.dumps(scene_seed, ensure_ascii=False, indent=2), encoding="utf-8")
    (source_dir / "transcript.txt").write_text(transcript_txt + "\n", encoding="utf-8")
    meta = {
        "mode": "script",
        "script_path": str(script_path),
        "source_audio_path": str(source_audio),
        "transcript_path": str(transcript_path),
        "scene_seed_path": str(seed_path),
        "target_duration": float(scene_seed.get("total_duration_s") or 0),
        "tts": tts_meta,
    }
    meta_path = source_dir / "source_bundle.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return PreparedSource(
        mode="script",
        source_dir=source_dir,
        source_text=transcript_txt or script_text,
        source_audio_path=source_audio,
        transcript_path=transcript_path,
        scene_seed_path=seed_path,
        metadata_path=meta_path,
    )


def prepare_audio_source(
    project_id: str,
    project: dict[str, Any],
    source_dir: Path,
    source_audio: Path,
) -> PreparedSource:
    audio_copy = source_dir / f"source_audio{source_audio.suffix.lower() or '.mp3'}"
    if not audio_copy.exists() or audio_copy.stat().st_mtime < source_audio.stat().st_mtime:
        shutil.copy2(source_audio, audio_copy)
    transcript_path, transcript_txt = transcribe_audio(
        audio_copy,
        source_dir / "transcribe",
        str(project.get("output_language") or "zh"),
    )
    words = json.loads(transcript_path.read_text(encoding="utf-8"))
    scene_seed = build_audio_scene_seed(words)
    seed_path = source_dir / "scene_seed.json"
    seed_path.write_text(json.dumps(scene_seed, ensure_ascii=False, indent=2), encoding="utf-8")
    (source_dir / "transcript.txt").write_text(transcript_txt + "\n", encoding="utf-8")
    meta = {
        "mode": "audio",
        "source_audio_path": str(audio_copy),
        "transcript_path": str(transcript_path),
        "scene_seed_path": str(seed_path),
        "target_duration": float(scene_seed.get("total_duration_s") or 0),
    }
    meta_path = source_dir / "source_bundle.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return PreparedSource(
        mode="audio",
        source_dir=source_dir,
        source_text=transcript_txt,
        source_audio_path=audio_copy,
        transcript_path=transcript_path,
        scene_seed_path=seed_path,
        metadata_path=meta_path,
    )


def choose_audio_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    audio_assets = [a for a in assets if a.get("file_type") == "audio"]
    if audio_assets:
        audio_assets.sort(key=lambda a: a.get("created_at") or "", reverse=True)
        return audio_assets[0]
    return None


def transcribe_audio(audio_path: Path, out_dir: Path, output_language: str) -> tuple[Path, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / "transcript.json"
    transcript_text_path = out_dir / "transcript.txt"
    if (
        transcript_path.is_file()
        and transcript_text_path.is_file()
        and transcript_path.stat().st_mtime >= audio_path.stat().st_mtime
    ):
        return transcript_path, transcript_text_path.read_text(encoding="utf-8").strip()

    asr = transcribe_audio_local(audio_path, out_dir, output_language if output_language in {"zh", "en", "ja", "ko"} else "zh")
    transcript_txt = normalize_script_text(str(asr.get("text") or ""))
    if not transcript_txt:
        raise RuntimeError("本地 ASR 逐字稿为空，无法生成解说视频。")
    total_duration = probe_duration_s(audio_path)
    words = asr.get("words") or make_pseudo_timed_words(transcript_txt, total_duration)
    if not words:
        raise RuntimeError("本地 ASR 没有生成可用时间轴。")
    transcript_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    transcript_text_path.write_text(transcript_txt + "\n", encoding="utf-8")
    raw_path = out_dir / "transcript_source.json"
    raw_path.write_text(
        json.dumps(
            {
                "provider": asr.get("provider") or "whisper.cpp",
                "text": transcript_txt,
                "duration_s": round(total_duration, 3),
                "word_count": len(words),
                "model": asr.get("model"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return transcript_path, transcript_txt


def build_audio_scene_seed(words: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = normalize_words(words)
    if not normalized:
        raise RuntimeError("音频转写结果为空，无法生成解说分镜。")
    scenes: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    min_duration = 4.0
    max_duration = 9.5
    hard_cap = 12.0
    for word in normalized:
        if not current:
            current.append(word)
            continue
        current.append(word)
        duration = current[-1]["end"] - current[0]["start"]
        gap = word["start"] - current[-2]["end"]
        boundary = (
            duration >= max_duration and ends_sentence(current[-1]["text"])
        ) or duration >= hard_cap or (gap >= 0.55 and duration >= min_duration)
        if boundary:
            scenes.append(make_audio_scene(len(scenes) + 1, current))
            current = []
    if current:
        if scenes and len(current) < 3:
            scenes[-1] = merge_audio_scene(scenes[-1], current)
        else:
            scenes.append(make_audio_scene(len(scenes) + 1, current))
    total_duration = scenes[-1]["end_s"] if scenes else normalized[-1]["end"]
    return {
        "mode": "audio",
        "total_duration_s": round(total_duration, 3),
        "scene_count": len(scenes),
        "scenes": scenes,
    }


def make_audio_scene(scene_number: int, words: list[dict[str, Any]]) -> dict[str, Any]:
    start = words[0]["start"]
    end = words[-1]["end"]
    return {
        "sceneNumber": scene_number,
        "sceneId": f"scene_{scene_number}",
        "start_s": round(start, 3),
        "end_s": round(end, 3),
        "duration_s": round(end - start, 3),
        "transcript": join_words(words),
        "word_count": len(words),
        "words": words,
    }


def merge_audio_scene(scene: dict[str, Any], words: list[dict[str, Any]]) -> dict[str, Any]:
    merged_words = list(scene.get("words") or []) + words
    scene["end_s"] = round(merged_words[-1]["end"], 3)
    scene["duration_s"] = round(scene["end_s"] - scene["start_s"], 3)
    scene["word_count"] = len(merged_words)
    scene["transcript"] = join_words(merged_words)
    scene["words"] = merged_words
    return scene


def build_subtitle_cues(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = normalize_words(words)
    if not normalized:
        return []
    cues: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    max_chars = 18
    max_duration = 2.8
    max_gap = 0.45
    for word in normalized:
        if not current:
            current.append(word)
            continue
        current_text = join_words(current)
        duration = current[-1]["end"] - current[0]["start"]
        gap = word["start"] - current[-1]["end"]
        next_text = join_words(current + [word])
        should_break = (
            ends_sentence(current[-1]["text"])
            or len(next_text) > max_chars
            or duration >= max_duration
            or gap >= max_gap
        )
        if should_break:
            cues.append(_make_subtitle_cue(len(cues) + 1, current))
            current = [word]
        else:
            current.append(word)
    if current:
        cues.append(_make_subtitle_cue(len(cues) + 1, current))
    return cues


def _make_subtitle_cue(index: int, words: list[dict[str, Any]]) -> dict[str, Any]:
    start = float(words[0]["start"])
    end = float(words[-1]["end"])
    if end <= start:
        end = start + 0.25
    return {
        "index": index,
        "start": start,
        "end": end,
        "text": join_words(words),
    }


def render_srt(cues: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for cue in cues:
        lines.extend(
            [
                str(cue["index"]),
                f"{format_srt_timestamp(float(cue['start']))} --> {format_srt_timestamp(float(cue['end']))}",
                str(cue["text"]).strip(),
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(int(round(seconds * 1000)), 0)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def normalize_words(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for idx, item in enumerate(words):
        text = str(item.get("text") or item.get("word") or "").strip()
        start = float(item.get("start") or 0)
        end = float(item.get("end") or 0)
        if not text or end <= start:
            continue
        normalized.append(
            {
                "id": str(item.get("id") or f"w{idx}"),
                "text": text,
                "start": round(start, 3),
                "end": round(end, 3),
            }
        )
    return normalized


def make_pseudo_timed_words(text: str, total_duration_s: float) -> list[dict[str, Any]]:
    sentences = split_sentences(normalize_script_text(text))
    if not sentences:
        return []
    sentence_units = [max(1.0, speech_units(sentence)) for sentence in sentences]
    total_units = sum(sentence_units) or 1.0
    cursor = 0.0
    words: list[dict[str, Any]] = []
    for sentence_index, sentence in enumerate(sentences):
        sentence_duration = max(0.4, total_duration_s * sentence_units[sentence_index] / total_units)
        pause = min(0.28, max(0.06, sentence_duration * 0.06)) if sentence_index < len(sentences) - 1 else 0.0
        spoken_duration = max(0.25, sentence_duration - pause)
        tokens = sentence_tokens(sentence)
        if not tokens:
            continue
        token_units = [max(1.0, speech_units(token)) for token in tokens]
        token_total = sum(token_units) or 1.0
        for token_index, token in enumerate(tokens):
            remaining_tokens = len(tokens) - token_index - 1
            duration = max(0.08, spoken_duration * token_units[token_index] / token_total)
            end = min(total_duration_s, cursor + duration)
            if remaining_tokens == 0 and sentence_index == len(sentences) - 1:
                end = total_duration_s
            words.append(
                {
                    "id": f"w{len(words)}",
                    "text": token,
                    "start": round(cursor, 3),
                    "end": round(max(cursor + 0.04, end), 3),
                }
            )
            cursor = round(words[-1]["end"], 3)
        cursor = round(min(total_duration_s, cursor + pause), 3)
    if words:
        words[-1]["end"] = round(max(words[-1]["end"], total_duration_s), 3)
    return normalize_words(words)


def sentence_tokens(sentence: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9%]+(?:[./:_-][A-Za-z0-9%]+)*|[\u4e00-\u9fff]{1,4}|[，。！？；：,.!?;:、…]+", sentence)
    tokens: list[str] = []
    for item in raw:
        if re.fullmatch(r"[，。！？；：,.!?;:、…]+", item):
            if tokens:
                tokens[-1] += item
            else:
                tokens.append(item)
            continue
        tokens.append(item)
    return tokens


def speech_units(text: str) -> float:
    stripped = re.sub(r"[，。！？；：,.!?;:、…\s]+", "", text)
    if not stripped:
        return 1.0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", stripped))
    latin = re.findall(r"[A-Za-z0-9%]+", stripped)
    if cjk:
        return float(cjk)
    if latin:
        return float(sum(max(1, len(token) / 3) for token in latin))
    return float(len(stripped))


def normalize_script_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def split_sentences(text: str) -> list[str]:
    items = re.split(r"(?<=[。！？!?；;])\s+|(?<=[。！？!?；;])", text)
    return [item.strip() for item in items if item and item.strip()]


def ends_sentence(text: str) -> bool:
    return bool(re.search(r"[。！？!?；;，,：:]$", text))


def join_words(words: list[dict[str, Any]]) -> str:
    out = ""
    for item in words:
        token = str(item.get("text") or "").strip()
        if not token:
            continue
        if not out:
            out = token
            continue
        if should_insert_space(out[-1], token[:1]):
            out += " " + token
        else:
            out += token
    return re.sub(r"\s+([，。！？；：,.!?;:、…])", r"\1", out).strip()


def should_insert_space(prev_char: str, next_char: str) -> bool:
    prev_is_ascii = bool(re.match(r"[A-Za-z0-9%]", prev_char))
    next_is_ascii = bool(re.match(r"[A-Za-z0-9%]", next_char))
    return prev_is_ascii and next_is_ascii


def build_script_scene_seed(script_text: str, target_duration: int) -> dict[str, Any]:
    cleaned = normalize_script_text(script_text)
    sentences = split_sentences(cleaned)
    if not sentences:
        sentences = [cleaned]
    scene_count = max(4, min(10, math.ceil(max(target_duration, 30) / 9)))
    groups = chunk_sentences(sentences, scene_count)
    scenes = []
    for idx, group in enumerate(groups, start=1):
        transcript = " ".join(group).strip()
        est = estimate_speech_seconds(transcript)
        scenes.append(
            {
                "sceneNumber": idx,
                "sceneId": f"scene_{idx}",
                "duration_s": round(est, 3),
                "transcript": transcript,
                "word_count": len(transcript),
            }
        )
    total = sum(scene["duration_s"] for scene in scenes)
    return {
        "mode": "script",
        "total_duration_s": round(total, 3),
        "scene_count": len(scenes),
        "scenes": scenes,
    }


def chunk_sentences(sentences: list[str], groups: int) -> list[list[str]]:
    if len(sentences) <= groups:
        return [[sentence] for sentence in sentences]
    result: list[list[str]] = []
    remaining = list(sentences)
    remaining_groups = groups
    while remaining:
        take = max(1, math.ceil(len(remaining) / remaining_groups))
        result.append(remaining[:take])
        remaining = remaining[take:]
        remaining_groups -= 1
        if remaining_groups <= 0 and remaining:
            result[-1].extend(remaining)
            break
    return result


def estimate_speech_seconds(text: str) -> float:
    chars = len(re.sub(r"\s+", "", text))
    return max(3.0, chars / 4.8)
