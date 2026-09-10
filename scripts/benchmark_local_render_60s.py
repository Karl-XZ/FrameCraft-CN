#!/usr/bin/env python3
"""Benchmark cloud Agent preparation plus a real user-local HyperFrames render."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


TERMINAL = {"completed", "failed", "cancelled", "needs_input"}


def wait_cloud_job(session: requests.Session, api: str, job_id: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    last = ""
    while time.perf_counter() - started < timeout:
        job = session.get(f"{api}/api/jobs/{job_id}", timeout=30).json()
        state = f"{job['status']} {job['progress']:.0f}% {job.get('current_step') or ''}"
        if state != last:
            print(f"  cloud {time.perf_counter() - started:6.1f}s {state}", flush=True)
            last = state
        if job["status"] in TERMINAL:
            if job["status"] != "completed":
                raise RuntimeError(job.get("error_message") or state)
            return job
        time.sleep(1)
    raise TimeoutError("云端 Agent 工程生成超时。")


def wait_local_job(renderer: str, job_id: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    last = ""
    while time.perf_counter() - started < timeout:
        response = requests.get(f"{renderer}/jobs/{job_id}", timeout=30)
        response.raise_for_status()
        job = response.json()
        state = f"{job['status']} {job['progress']:.0f}% {job.get('step') or ''}"
        if state != last:
            print(f"  local {time.perf_counter() - started:6.1f}s {state}", flush=True)
            last = state
        if job["status"] == "failed":
            raise RuntimeError(job.get("error") or state)
        if job["status"] == "completed":
            return job
        time.sleep(1)
    raise TimeoutError("用户电脑 HyperFrames 渲染超时。")


def probe(video: Path) -> dict[str, Any]:
    output = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of", "json", str(video),
        ],
        text=True,
    )
    media = json.loads(output)
    types = {item.get("codec_type") for item in media.get("streams", [])}
    duration = float(media.get("format", {}).get("duration") or 0)
    if types != {"video", "audio"} or not 58 <= duration <= 63:
        raise RuntimeError(f"成片验证失败：duration={duration}, streams={types}")
    return media


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8024")
    parser.add_argument("--renderer", default="http://127.0.0.1:19186")
    parser.add_argument("--token-file", type=Path, default=Path("backend/storage/access_token.txt"))
    parser.add_argument("--aspect", default="16:9")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.audio.is_file():
        raise FileNotFoundError(args.audio)
    token = args.token_file.read_text(encoding="utf-8").strip()
    session = requests.Session()
    session.headers["X-FrameCraft-Token"] = token
    api = args.api.rstrip("/")
    renderer = args.renderer.rstrip("/")
    overall = time.perf_counter()

    requests.get(f"{renderer}/health", timeout=5).raise_for_status()
    project = session.post(
        f"{api}/api/projects",
        json={
            "name": "本地渲染真实60秒测试",
            "aspect_ratio": args.aspect,
            "target_duration": 60,
            "target_style": "faceless_explainer",
            "output_language": "zh",
        },
        timeout=30,
    )
    project.raise_for_status()
    project_id = project.json()["id"]
    with args.audio.open("rb") as handle:
        upload = session.post(
            f"{api}/api/projects/{project_id}/assets/upload",
            files={"file": (args.audio.name, handle, "audio/wav")},
            timeout=120,
        )
    upload.raise_for_status()

    analysis_started = time.perf_counter()
    analysis = session.post(f"{api}/api/projects/{project_id}/assets/analyze", json={}, timeout=30)
    analysis.raise_for_status()
    wait_cloud_job(session, api, analysis.json()["id"], 180)
    analysis_seconds = time.perf_counter() - analysis_started

    preparation_started = time.perf_counter()
    generation = session.post(
        f"{api}/api/projects/{project_id}/generate",
        json={"resolution": "1080p", "fps": 24, "render_target": "local"},
        timeout=30,
    )
    generation.raise_for_status()
    cloud_job = wait_cloud_job(session, api, generation.json()["id"], 180)
    preparation_seconds = time.perf_counter() - preparation_started
    result = cloud_job.get("result") or {}
    if result.get("render_target") != "local":
        raise RuntimeError(f"服务器没有返回本地渲染任务：{result}")

    bundle_response = session.get(f"{api}{result['bundle_url']}", timeout=120)
    bundle_response.raise_for_status()
    local_started = time.perf_counter()
    local = requests.post(
        f"{renderer}/render?fps={result.get('fps') or 24}",
        headers={"Content-Type": "application/zip"},
        data=bundle_response.content,
        timeout=120,
    )
    local.raise_for_status()
    local_job = wait_local_job(renderer, local.json()["id"], 600)
    video_response = requests.get(f"{renderer}{local_job['download_url']}", timeout=120)
    video_response.raise_for_status()
    review_response = requests.get(f"{renderer}{local_job['review_url']}", timeout=30)
    review_response.raise_for_status()
    local_seconds = time.perf_counter() - local_started

    validation_started = time.perf_counter()
    complete = session.post(
        f"{api}/api/projects/{project_id}/versions/{result['version_id']}/local-render-review",
        files={"file": ("contact-sheet.jpg", review_response.content, "image/jpeg")},
        data={"media_json": json.dumps(local_job.get("media_validation") or {})},
        timeout=180,
    )
    if not complete.ok:
        raise RuntimeError(f"云端联系表验收失败（{complete.status_code}）：{complete.text}")
    validation_seconds = time.perf_counter() - validation_started
    version = complete.json()
    if version.get("preview_url") or version.get("preview_path"):
        raise RuntimeError("服务器错误地注册了本地 MP4 路径。")
    with tempfile.NamedTemporaryFile(suffix=".mp4") as handle:
        handle.write(video_response.content)
        handle.flush()
        media = probe(Path(handle.name))

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "aspect_ratio": args.aspect,
        "analysis_seconds": round(analysis_seconds, 2),
        "cloud_preparation_seconds": round(preparation_seconds, 2),
        "local_render_seconds": round(local_seconds, 2),
        "cloud_validation_seconds": round(validation_seconds, 2),
        "total_seconds": round(time.perf_counter() - overall, 2),
        "duration_seconds": round(float(media["format"]["duration"]), 3),
        "render_target": "local",
        "server_stores_video": False,
        "version_status": version.get("status"),
        "passed": True,
    }
    if report["total_seconds"] >= 300:
        raise RuntimeError(f"五分钟目标未达成：{report['total_seconds']} 秒")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
