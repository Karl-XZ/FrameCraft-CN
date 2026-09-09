from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def ffmpeg_trim(src: Path, dst: Path, start_s: float, end_s: float) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{start_s:.3f}",
        "-to",
        f"{end_s:.3f}",
        "-i",
        str(src),
        "-ar",
        "44100",
        "-ac",
        "1",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-1200:]
        raise RuntimeError(f"ffmpeg trim failed for {dst.name}: {tail}")


def build_audio_meta(project_dir: Path, scene_seed_path: Path, source_audio_path: Path) -> dict:
    seed = json.loads(scene_seed_path.read_text(encoding="utf-8"))
    scenes = seed.get("scenes") or []
    voice_dir = project_dir / "assets" / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    scene_map: dict[str, dict] = {}
    for scene in scenes:
        sid = str(scene["sceneId"])
        start_s = float(scene["start_s"])
        end_s = float(scene["end_s"])
        words = scene.get("words") or []
        wav_rel = f"assets/voice/{sid}.wav"
        words_rel = f"assets/voice/{sid}_words.json"
        wav_abs = project_dir / wav_rel
        words_abs = project_dir / words_rel
        ffmpeg_trim(source_audio_path, wav_abs, start_s, end_s)
        localized = []
        for idx, word in enumerate(words):
            localized.append(
                {
                    "id": str(word.get("id") or f"w{idx}"),
                    "text": str(word.get("text") or "").strip(),
                    "start": round(float(word["start"]) - start_s, 3),
                    "end": round(float(word["end"]) - start_s, 3),
                }
            )
        words_abs.write_text(json.dumps(localized, ensure_ascii=False, indent=2), encoding="utf-8")
        scene_map[sid] = {
            "voicePath": wav_rel,
            "voiceDuration": round(end_s - start_s, 3),
            "wordsPath": words_rel,
        }
    return {
        "tts_provider": "uploaded-audio",
        "voice_id": None,
        "bgm_provider": None,
        "bgm_enabled": False,
        "bgm_path": None,
        "bgm_pending": False,
        "bgm_log": None,
        "bgm_pid": None,
        "bgm_mode": None,
        "bgm_target_duration_s": None,
        "bgm_seed_duration_s": None,
        "bgm_loop_count": None,
        "total_duration_s": round(float(seed.get("total_duration_s") or 0), 3),
        "scenes": scene_map,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--scene-seed", required=True)
    parser.add_argument("--source-audio", required=True)
    parser.add_argument("--out", default="audio_meta.json")
    args = parser.parse_args()
    project_dir = Path(args.project_dir).resolve()
    scene_seed_path = Path(args.scene_seed).resolve()
    source_audio_path = Path(args.source_audio).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = project_dir / out_path
    audio_meta = build_audio_meta(project_dir, scene_seed_path, source_audio_path)
    out_path.write_text(json.dumps(audio_meta, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
