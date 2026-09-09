#!/usr/bin/env python3
"""Run a real browser upload -> analyze -> generate -> download acceptance test."""
from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def probe(video: Path) -> str:
    return subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-of", "json", str(video)],
        text=True,
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--studio", default="http://127.0.0.1:5174")
    parser.add_argument("--token-file", type=Path, default=ROOT / "backend/storage/access_token.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "benchmark-results/ui-downloaded-preview.mp4")
    args = parser.parse_args()
    if not args.audio.is_file():
        raise FileNotFoundError(args.audio)
    token = args.token_file.read_text(encoding="utf-8").strip()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(accept_downloads=True)
        page.goto(f"{args.studio.rstrip('/')}/projects/new?access_token={token}", wait_until="networkidle")
        page.locator('input[placeholder*="AI 产业观点"]').fill("openJiuwen 网页端真实60秒验收")
        page.locator("select").nth(0).select_option("16:9")
        page.get_by_role("button", name="创建并进入工作台").click()
        page.wait_for_url("**/studio?project=**", timeout=30_000)
        page.wait_for_load_state("networkidle")

        with page.expect_response(
            lambda response: "/assets/upload" in response.url and response.request.method == "POST",
            timeout=120_000,
        ) as upload_info:
            page.locator('input[type="file"]').set_input_files(str(args.audio.resolve()))
        if not upload_info.value.ok:
            raise RuntimeError(f"upload failed: {upload_info.value.status} {upload_info.value.text()}")
        page.get_by_text("已上传", exact=True).wait_for(timeout=30_000)
        upload_seconds = time.perf_counter() - started
        print(f"upload_ready_seconds={upload_seconds:.2f}", flush=True)

        page.get_by_role("button", name="开始 AI 分析").click()
        page.get_by_role("button", name="确认生成").wait_for(timeout=300_000)
        analyze_seconds = time.perf_counter() - started - upload_seconds
        print(f"analysis_seconds={analyze_seconds:.2f}", flush=True)

        page.get_by_role("button", name="确认生成").click()
        page.get_by_text("完整视频", exact=True).wait_for(timeout=300_000)
        generate_seconds = time.perf_counter() - started - upload_seconds - analyze_seconds
        print(f"generation_seconds={generate_seconds:.2f}", flush=True)

        with page.expect_download(timeout=60_000) as download_info:
            page.locator('a[download]').first.click()
        download_info.value.save_as(args.output)
        browser.close()

    total_seconds = time.perf_counter() - started
    if total_seconds >= 300:
        raise RuntimeError(f"browser flow exceeded five minutes: {total_seconds:.2f}s")
    print(f"total_seconds={total_seconds:.2f}")
    print(f"download={args.output}")
    print(probe(args.output))


if __name__ == "__main__":
    main()
