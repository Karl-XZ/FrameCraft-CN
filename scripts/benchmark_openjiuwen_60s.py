#!/usr/bin/env python3
"""Run repeatable 60-second, real-media API benchmarks and verify each MP4."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"completed", "failed", "needs_input", "cancelled"}


def wait_job(session: requests.Session, api: str, job_id: str, timeout: float) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    last_step = ""
    while time.perf_counter() - started < timeout:
        response = session.get(f"{api}/api/jobs/{job_id}", timeout=30)
        response.raise_for_status()
        job = response.json()
        step = f"{job['status']} {job['progress']:.0f}% {job.get('current_step') or ''}"
        if step != last_step:
            print(f"  {time.perf_counter() - started:6.1f}s  {step}", flush=True)
            last_step = step
        if job["status"] in TERMINAL:
            elapsed = time.perf_counter() - started
            if job["status"] != "completed":
                raise RuntimeError(job.get("error_message") or f"job {job_id} ended as {job['status']}")
            return job, elapsed
        time.sleep(2)
    raise TimeoutError(f"job {job_id} exceeded {timeout:.0f}s")


def probe(path: Path) -> dict[str, Any]:
    raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of", "json", str(path),
        ],
        text=True,
    )
    result = json.loads(raw)
    stream_types = {item.get("codec_type") for item in result.get("streams", [])}
    duration = float(result.get("format", {}).get("duration") or 0)
    if "video" not in stream_types or "audio" not in stream_types or not 58 <= duration <= 63:
        raise RuntimeError(f"invalid rendered media: duration={duration}, streams={stream_types}")
    return result


def run_once(session: requests.Session, api: str, audio: Path, index: int, aspect: str) -> dict[str, Any]:
    overall_started = time.perf_counter()
    project = session.post(
        f"{api}/api/projects",
        json={
            "name": f"openJiuwen 真实60秒稳定性测试 {index}",
            "aspect_ratio": aspect,
            "target_duration": 60,
            "target_style": "faceless_explainer",
            "output_language": "zh",
            "generate_draft": False,
            "keep_hyperframes": True,
        },
        timeout=30,
    )
    project.raise_for_status()
    project_id = project.json()["id"]
    with audio.open("rb") as handle:
        upload = session.post(
            f"{api}/api/projects/{project_id}/assets/upload",
            files={"file": (audio.name, handle, "audio/wav")},
            timeout=120,
        )
    upload.raise_for_status()

    analyze = session.post(
        f"{api}/api/projects/{project_id}/assets/analyze",
        json={"strategy": "complete", "platform": "douyin"},
        timeout=30,
    )
    analyze.raise_for_status()
    _, analyze_seconds = wait_job(session, api, analyze.json()["id"], 180)

    generate = session.post(
        f"{api}/api/projects/{project_id}/generate",
        json={"resolution": "1080p", "fps": 30, "strategy": "complete"},
        timeout=30,
    )
    generate.raise_for_status()
    _, generate_seconds = wait_job(session, api, generate.json()["id"], 300)

    versions = session.get(f"{api}/api/projects/{project_id}/versions", timeout=30)
    versions.raise_for_status()
    version = versions.json()[0]
    video_path = ROOT / "outputs" / project_id / version["id"] / "preview.mp4"
    media = probe(video_path)
    review = json.loads(video_path.with_name("agent_visual_review.json").read_text(encoding="utf-8"))
    if not review.get("pass") or float(review.get("score") or 0) < 75:
        raise RuntimeError(f"visual review failed: {review}")
    total_seconds = time.perf_counter() - overall_started
    if total_seconds >= 300:
        raise RuntimeError(f"end-to-end target missed: {total_seconds:.1f}s")
    return {
        "index": index,
        "project_id": project_id,
        "aspect_ratio": aspect,
        "analysis_seconds": round(analyze_seconds, 2),
        "generation_seconds": round(generate_seconds, 2),
        "total_seconds": round(total_seconds, 2),
        "video_path": str(video_path.relative_to(ROOT)),
        "duration_seconds": round(float(media["format"]["duration"]), 3),
        "visual_score": review["score"],
        "visual_model": review["model"],
        "passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8023")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--token-file", type=Path, default=ROOT / "backend/storage/access_token.txt")
    args = parser.parse_args()
    if not args.audio.is_file():
        raise FileNotFoundError(args.audio)
    token = args.token_file.read_text(encoding="utf-8").strip()
    session = requests.Session()
    session.headers["X-FrameCraft-Token"] = token
    health = session.get(f"{args.api}/api/health", timeout=30)
    health.raise_for_status()
    if health.json().get("mode") != "openjiuwen-multi-agent":
        raise RuntimeError(f"unexpected backend mode: {health.text}")

    results: list[dict[str, Any]] = []
    for index in range(1, args.runs + 1):
        aspect = "16:9" if index % 2 else "9:16"
        print(f"run {index}/{args.runs}: {aspect}", flush=True)
        result = run_once(session, args.api.rstrip("/"), args.audio, index, aspect)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_audio": args.audio.name,
        "target_seconds": 300,
        "runs": results,
        "max_total_seconds": max(item["total_seconds"] for item in results),
        "mean_total_seconds": round(sum(item["total_seconds"] for item in results) / len(results), 2),
        "stable_under_five_minutes": all(item["total_seconds"] < 300 for item in results),
    }
    out_dir = ROOT / "benchmark-results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"openjiuwen-60s-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={out_path}")


if __name__ == "__main__":
    main()
