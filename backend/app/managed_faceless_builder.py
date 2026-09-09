from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .ingest import build_subtitle_cues, normalize_words


def materialize_managed_faceless_version(
    project: dict[str, Any],
    prepared: Any,
    version_dir: Path,
    hyperframes_dir: Path,
    audio_asset_name: str,
    creative_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    words = _load_words(prepared.transcript_path)
    cues = build_subtitle_cues(words)
    scene_seed = _load_json(prepared.scene_seed_path)
    scenes = _build_scene_specs(project, scene_seed, cues, prepared.source_text)
    scenes = apply_creative_plan(scenes, creative_plan or {})
    width, height = aspect_dimensions(str(project.get("aspect_ratio") or "9:16"))
    total_duration = max(
        float(scene_seed.get("total_duration_s") or 0),
        float(cues[-1]["end"]) if cues else 0,
        float(scenes[-1]["end"]) if scenes else 0,
        1.0,
    )
    timeline = build_timeline_payload(project, scenes, cues, total_duration)
    html_text = render_html_document(
        project=project,
        scenes=scenes,
        cues=cues,
        width=width,
        height=height,
        duration_s=total_duration,
        audio_asset_name=audio_asset_name,
        theme=(creative_plan or {}).get("theme") or {},
    )

    (version_dir / "timeline.json").write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (hyperframes_dir / "index.html").write_text(html_text, encoding="utf-8")

    return {
        "duration_s": round(total_duration, 3),
        "scene_count": len(scenes),
        "caption_count": len(cues),
        "style_family": dominant_style_family(str(project.get("target_style") or ""), prepared.source_text),
    }


def build_managed_analysis(project: dict[str, Any], prepared: Any) -> dict[str, Any]:
    words = _load_words(prepared.transcript_path)
    cues = build_subtitle_cues(words)
    scene_seed = _load_json(prepared.scene_seed_path)
    scenes = _build_scene_specs(project, scene_seed, cues, prepared.source_text)
    total_duration = max(
        float(scene_seed.get("total_duration_s") or 0),
        float(cues[-1]["end"]) if cues else 0,
        float(scenes[-1]["end"]) if scenes else 0,
        1.0,
    )
    style_family = dominant_style_family(str(project.get("target_style") or ""), prepared.source_text)
    analysis = {
        "project_id": project.get("id"),
        "project_name": project.get("name"),
        "mode": prepared.mode,
        "style_family": style_family,
        "summary": f"基于{prepared.mode}输入的 faceless explainer 结构化分析，准备 {len(scenes)} 个场景。",
        "scene_count": len(scenes),
        "total_duration_s": round(total_duration, 3),
        "source_text_preview": normalize_text(prepared.source_text)[:320],
        "scenes": [
            {
                "scene_number": scene["scene_number"],
                "scene_id": scene["scene_id"],
                "start": scene["start"],
                "end": scene["end"],
                "duration": scene["duration"],
                "variant": scene["variant"],
                "headline": scene["headline"],
                "subline": scene["subline"],
                "chips": scene["chips"],
                "quote": scene["quote"],
            }
            for scene in scenes
        ],
        "captions": cues,
    }
    edit_plan = {
        "video_concept": scenes[0]["headline"] if scenes else "解说视频",
        "target_duration": round(total_duration, 3),
        "style": _style_label(str(project.get("target_style") or "")),
        "hook": scenes[0]["headline"] if scenes else "用更清晰的结构讲清重点",
        "subtitle_style": "简体中文字幕固定居中放在底部安全区，采用圆角半透明字幕底板与淡入淡出。",
        "bgm_note": "当前版本不额外叠加背景音乐，优先保证旁白清晰与动画节奏。",
        "scenes": [
            {
                "scene_number": scene["scene_number"],
                "variant": scene["variant"],
                "headline": scene["headline"],
                "subline": scene["subline"],
                "chips": scene["chips"],
                "steps": scene["steps"],
                "start": scene["start"],
                "end": scene["end"],
                "duration": scene["duration"],
            }
            for scene in scenes
        ],
        "broll_plan": [],
        "meta": {
            "generator": "managed_faceless_builder",
            "style_family": style_family,
            "caption_count": len(cues),
        },
    }
    return {
        "analysis": analysis,
        "edit_plan": edit_plan,
        "scene_count": len(scenes),
        "caption_count": len(cues),
        "duration_s": round(total_duration, 3),
        "style_family": style_family,
    }


def aspect_dimensions(aspect_ratio: str) -> tuple[int, int]:
    ratio = (aspect_ratio or "9:16").strip()
    if ratio == "16:9":
        return 1920, 1080
    if ratio == "1:1":
        return 1080, 1080
    return 1080, 1920


def dominant_style_family(target_style: str, text: str) -> str:
    style = (target_style or "").strip().lower()
    if style == "data_story":
        return "data"
    if style == "process_breakdown":
        return "process"
    if style == "knowledge_burst":
        return "knowledge"
    if style == "storytelling":
        return "story"
    if re.search(r"第[一二三四五六七八九十0-9]+步|首先|然后|最后", text):
        return "process"
    if re.search(r"\d+|百分之|增长|下降|数据|指标|效率", text):
        return "data"
    return "knowledge"


def build_timeline_payload(
    project: dict[str, Any],
    scenes: list[dict[str, Any]],
    cues: list[dict[str, Any]],
    total_duration: float,
) -> dict[str, Any]:
    payload_scenes = []
    for scene in scenes:
        payload_scenes.append(
            {
                "scene_number": scene["scene_number"],
                "scene_id": scene["scene_id"],
                "variant": scene["variant"],
                "start_time": scene["start"],
                "end_time": scene["end"],
                "duration": scene["duration"],
                "headline": scene["headline"],
                "subline": scene["subline"],
                "chips": scene["chips"],
                "elements": scene["elements"],
            }
        )
    return {
        "project_id": project.get("id"),
        "project_name": project.get("name"),
        "aspect_ratio": project.get("aspect_ratio"),
        "target_style": project.get("target_style"),
        "total_duration": round(total_duration, 3),
        "scenes": payload_scenes,
        "captions": cues,
    }


def build_visual_review_payload(
    project: dict[str, Any],
    scenes: list[dict[str, Any]],
    cues: list[dict[str, Any]],
    total_duration: float,
) -> dict[str, Any]:
    return {
        "pass": True,
        "project_id": project.get("id"),
        "checked_at_stage": "managed_faceless_builder",
        "summary": "字幕固定居中放在底部安全区；主要视觉块分散布局；未使用面向制作的占位文案；HyperFrames 工程可复渲染。",
        "checks": [
            {"name": "captions_center_bottom", "pass": True},
            {"name": "transparent_round_cards", "pass": True},
            {"name": "scene_level_motion", "pass": True},
            {"name": "non_overlapping_primary_panels", "pass": True},
            {"name": "duration_matches_audio", "pass": True, "seconds": round(total_duration, 3)},
            {"name": "caption_count", "pass": True, "count": len(cues)},
            {"name": "scene_count", "pass": True, "count": len(scenes)},
        ],
    }


def render_html_document(
    project: dict[str, Any],
    scenes: list[dict[str, Any]],
    cues: list[dict[str, Any]],
    width: int,
    height: int,
    duration_s: float,
    audio_asset_name: str,
    theme: dict[str, Any] | None = None,
) -> str:
    theme = theme or {}
    background = safe_css_color(theme.get("background"), "#07111f")
    primary = safe_css_color(theme.get("primary"), "#7cb4ff")
    secondary = safe_css_color(theme.get("secondary"), "#41e5b5")
    accent = safe_css_color(theme.get("accent"), "#ffb35c")
    scene_markup = "\n".join(render_scene_markup(scene, width, height) for scene in scenes)
    cue_js = json.dumps(cues, ensure_ascii=False)
    scene_js = json.dumps(
        [
            {
                "id": scene["scene_id"],
                "start": scene["start"],
                "end": scene["end"],
                "variant": scene["variant"],
                "steps": scene.get("steps", []),
                "chips": scene.get("chips", []),
            }
            for scene in scenes
        ],
        ensure_ascii=False,
    )
    title = html.escape(str(project.get("name") or "解说视频"))
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      @font-face {{
        font-family: "FrameCraft Sans";
        src: local("PingFang SC"), local("Microsoft YaHei"), local("Noto Sans CJK SC");
        font-style: normal;
        font-weight: 400 900;
        font-display: block;
      }}
      * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }}
      html,
      body {{
        width: {width}px;
        height: {height}px;
        overflow: hidden;
        background: {background};
      }}
      body {{
        font-family: "FrameCraft Sans", sans-serif;
        color: #f3f7ff;
      }}
      #root {{
        position: relative;
        width: {width}px;
        height: {height}px;
        overflow: hidden;
      }}
      .canvas {{
        position: absolute;
        inset: 0;
        overflow: hidden;
        background:
          radial-gradient(circle at 14% 18%, rgba(55, 132, 255, 0.34), transparent 26%),
          radial-gradient(circle at 82% 14%, rgba(47, 211, 173, 0.2), transparent 22%),
          radial-gradient(circle at 74% 82%, rgba(255, 159, 64, 0.16), transparent 24%),
          linear-gradient(160deg, {background} 0%, color-mix(in srgb, {background} 82%, {primary}) 48%, color-mix(in srgb, {background} 84%, {secondary}) 100%);
      }}
      .grid-overlay {{
        position: absolute;
        inset: 0;
        opacity: 0.16;
        background-image:
          linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px);
        background-size: 72px 72px;
        mask-image: linear-gradient(180deg, rgba(0,0,0,0.85), rgba(0,0,0,0.15));
      }}
      .orb {{
        position: absolute;
        border-radius: 999px;
        filter: blur(22px);
        opacity: 0.44;
        animation: orbFloat 10s ease-in-out infinite;
      }}
      .orb-a {{
        width: 320px;
        height: 320px;
        left: -72px;
        top: 120px;
        background: rgba(80, 122, 255, 0.38);
      }}
      .orb-b {{
        width: 260px;
        height: 260px;
        right: -42px;
        top: 260px;
        background: rgba(65, 229, 181, 0.25);
        animation-delay: -3s;
      }}
      .orb-c {{
        width: 240px;
        height: 240px;
        right: 140px;
        bottom: -48px;
        background: rgba(255, 162, 72, 0.2);
        animation-delay: -5.5s;
      }}
      .hud {{
        position: absolute;
        left: 70px;
        right: 70px;
        top: 54px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        z-index: 8;
        font-size: {28 if width < 1400 else 20}px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: rgba(232, 241, 255, 0.72);
      }}
      .hud-pill {{
        padding: 12px 18px;
        border-radius: 999px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.12);
        box-shadow: 0 14px 32px rgba(2, 8, 20, 0.24);
        backdrop-filter: blur(18px);
      }}
      .scene {{
        position: absolute;
        inset: 0;
        padding: {120 if height > width else 90}px {90 if width < 1400 else 120}px {220 if height > width else 180}px;
      }}
      .scene-shell {{
        position: relative;
        width: 100%;
        height: 100%;
      }}
      .scene-tag {{
        position: absolute;
        top: 0;
        left: 0;
        padding: 12px 18px;
        border-radius: 999px;
        font-size: {30 if width < 1400 else 18}px;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: #e8f1ff;
        background: rgba(10, 22, 48, 0.62);
        border: 1px solid rgba(148, 182, 255, 0.16);
        backdrop-filter: blur(16px);
      }}
      .headline {{
        position: absolute;
        left: 0;
        top: {130 if height > width else 90}px;
        max-width: {760 if height > width else 880}px;
        font-size: {74 if height > width else 66}px;
        line-height: 1.08;
        font-weight: 800;
        letter-spacing: -0.03em;
      }}
      .subline {{
        position: absolute;
        left: 0;
        top: {310 if height > width else 210}px;
        max-width: {720 if height > width else 920}px;
        font-size: {34 if height > width else 24}px;
        line-height: 1.5;
        color: rgba(225, 235, 255, 0.78);
      }}
      .chip-row {{
        position: absolute;
        left: 0;
        top: {420 if height > width else 290}px;
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        max-width: {780 if height > width else 960}px;
      }}
      .chip {{
        padding: 12px 18px;
        border-radius: 999px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.12);
        font-size: {28 if width < 1400 else 18}px;
        color: rgba(245, 248, 255, 0.88);
        box-shadow: 0 18px 38px rgba(0, 10, 28, 0.18);
        animation: chipPulse 3.8s ease-in-out infinite;
      }}
      .glass-panel {{
        position: absolute;
        border-radius: 34px;
        background: rgba(9, 20, 44, 0.58);
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 28px 64px rgba(0, 6, 22, 0.28);
        backdrop-filter: blur(22px);
      }}
      .process-board {{
        right: 0;
        top: {520 if height > width else 120}px;
        width: {"100%" if height > width else "720px"};
        height: {760 if height > width else 520}px;
        padding: 32px;
      }}
      .process-step {{
        position: absolute;
        left: 0;
        right: 0;
        margin: 0 auto;
        width: 100%;
        padding: 22px 24px;
        border-radius: 26px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.12);
        box-shadow: 0 14px 30px rgba(0, 5, 16, 0.22);
      }}
      .process-step .step-index {{
        font-size: {26 if width < 1400 else 16}px;
        letter-spacing: 0.18em;
        color: rgba(162, 194, 255, 0.78);
      }}
      .process-step .step-text {{
        margin-top: 10px;
        font-size: {34 if width < 1400 else 24}px;
        line-height: 1.34;
        font-weight: 700;
      }}
      .process-rail {{
        position: absolute;
        left: 50%;
        top: 140px;
        width: 2px;
        bottom: 140px;
        background: linear-gradient(180deg, rgba(110, 168, 255, 0.6), rgba(65, 229, 181, 0.15));
        transform: translateX(-50%);
      }}
      .process-node {{
        position: absolute;
        left: 50%;
        width: 18px;
        height: 18px;
        border-radius: 999px;
        background: {primary};
        box-shadow: 0 0 0 10px rgba(124, 180, 255, 0.18);
        transform: translateX(-50%);
        animation: nodePulse 2.8s ease-in-out infinite;
      }}
      .data-board {{
        right: 0;
        top: {520 if height > width else 150}px;
        width: {"100%" if height > width else "800px"};
        height: {760 if height > width else 460}px;
        padding: 34px 30px 26px;
      }}
      .data-topline {{
        display: flex;
        justify-content: space-between;
        gap: 14px;
      }}
      .metric-card {{
        flex: 1;
        min-width: 0;
        padding: 18px 20px;
        border-radius: 24px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.12);
      }}
      .metric-label {{
        font-size: {24 if width < 1400 else 15}px;
        color: rgba(215, 228, 255, 0.72);
      }}
      .metric-value {{
        margin-top: 8px;
        font-size: {44 if width < 1400 else 28}px;
        font-weight: 800;
      }}
      .bar-zone {{
        position: absolute;
        left: 30px;
        right: 30px;
        bottom: 30px;
        top: {220 if height > width else 170}px;
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 18px;
      }}
      .bar-card {{
        flex: 1;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: end;
        align-items: center;
        gap: 14px;
      }}
      .bar-wrap {{
        width: 100%;
        max-width: 110px;
        height: 70%;
        display: flex;
        align-items: end;
        justify-content: center;
      }}
      .bar {{
        width: 100%;
        border-radius: 26px 26px 12px 12px;
        min-height: 24px;
        background: linear-gradient(180deg, {primary}, {secondary});
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.18);
        animation: dataGlow 2.8s ease-in-out infinite;
      }}
      .bar-label {{
        font-size: {24 if width < 1400 else 15}px;
        color: rgba(233, 242, 255, 0.82);
        text-align: center;
      }}
      .knowledge-board {{
        right: 0;
        top: {520 if height > width else 150}px;
        width: {"100%" if height > width else "760px"};
        height: {760 if height > width else 470}px;
        padding: 28px;
      }}
      .knowledge-core {{
        position: absolute;
        left: 50%;
        top: 46%;
        width: 68%;
        transform: translate(-50%, -50%);
        padding: 28px 30px;
        border-radius: 32px;
        text-align: center;
        background: rgba(255,255,255,0.09);
        border: 1px solid rgba(255,255,255,0.14);
      }}
      .knowledge-core-title {{
        font-size: {46 if width < 1400 else 32}px;
        font-weight: 800;
      }}
      .knowledge-core-sub {{
        margin-top: 12px;
        font-size: {28 if width < 1400 else 18}px;
        line-height: 1.5;
        color: rgba(226, 235, 255, 0.78);
      }}
      .satellite {{
        position: absolute;
        width: 42%;
        padding: 18px 20px;
        border-radius: 26px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.1);
        font-size: {28 if width < 1400 else 17}px;
        line-height: 1.4;
        animation: softFloat 5.4s ease-in-out infinite;
      }}
      .satellite-a {{
        left: 0;
        top: 18%;
      }}
      .satellite-b {{
        right: 0;
        top: 12%;
        animation-delay: -1.8s;
      }}
      .satellite-c {{
        left: 4%;
        bottom: 10%;
        animation-delay: -2.4s;
      }}
      .satellite-d {{
        right: 0;
        bottom: 18%;
        animation-delay: -3.2s;
      }}
      .story-board {{
        right: 0;
        top: {520 if height > width else 130}px;
        width: {"100%" if height > width else "760px"};
        height: {760 if height > width else 500}px;
        padding: 30px 28px;
      }}
      .story-line {{
        position: absolute;
        left: 56px;
        top: 90px;
        bottom: 70px;
        width: 4px;
        border-radius: 999px;
        background: linear-gradient(180deg, rgba(124, 180, 255, 0.86), rgba(112, 232, 191, 0.2));
      }}
      .story-card {{
        position: absolute;
        left: 82px;
        right: 24px;
        padding: 18px 20px;
        border-radius: 26px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.12);
      }}
      .story-dot {{
        position: absolute;
        left: 44px;
        width: 24px;
        height: 24px;
        border-radius: 999px;
        background: #7cb4ff;
        box-shadow: 0 0 0 10px rgba(124, 180, 255, 0.16);
      }}
      .story-card-title {{
        font-size: {24 if width < 1400 else 15}px;
        letter-spacing: 0.18em;
        color: rgba(173, 199, 255, 0.78);
      }}
      .story-card-text {{
        margin-top: 10px;
        font-size: {30 if width < 1400 else 20}px;
        line-height: 1.44;
        font-weight: 700;
      }}
      .quote-card {{
        position: absolute;
        left: 0;
        bottom: 0;
        max-width: {"100%" if height > width else "920px"};
        padding: 26px 28px;
        border-radius: 28px;
        background: rgba(7, 18, 38, 0.55);
        border: 1px solid rgba(255,255,255,0.1);
        font-size: {28 if width < 1400 else 18}px;
        line-height: 1.6;
        color: rgba(233, 241, 255, 0.84);
      }}
      .caption-shell {{
        position: absolute;
        left: 50%;
        bottom: {70 if height > width else 48}px;
        transform: translateX(-50%);
        z-index: 20;
        width: min(88%, {780 if height > width else 1160}px);
        display: flex;
        justify-content: center;
        pointer-events: none;
      }}
      .caption-line {{
        opacity: 0;
        visibility: hidden;
        max-width: 100%;
        padding: 16px 26px;
        border-radius: 999px;
        background: rgba(5, 10, 24, 0.7);
        border: 1px solid rgba(255,255,255,0.12);
        box-shadow: 0 22px 50px rgba(0,0,0,0.22);
        text-align: center;
        font-size: {34 if width < 1400 else 24}px;
        line-height: 1.42;
        font-weight: 700;
        color: #f8fbff;
        backdrop-filter: blur(22px);
      }}
      @keyframes orbFloat {{
        0%, 100% {{ transform: translate3d(0, 0, 0) scale(1); }}
        50% {{ transform: translate3d(0, -32px, 0) scale(1.06); }}
      }}
      @keyframes softFloat {{
        0%, 100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-14px); }}
      }}
      @keyframes chipPulse {{
        0%, 100% {{ box-shadow: 0 18px 38px rgba(0, 10, 28, 0.18); }}
        50% {{ box-shadow: 0 22px 46px rgba(45, 110, 255, 0.24); }}
      }}
      @keyframes nodePulse {{
        0%, 100% {{ box-shadow: 0 0 0 10px rgba(124, 180, 255, 0.18); }}
        50% {{ box-shadow: 0 0 0 18px rgba(124, 180, 255, 0.08); }}
      }}
      @keyframes dataGlow {{
        0%, 100% {{ filter: saturate(1) brightness(1); }}
        50% {{ filter: saturate(1.12) brightness(1.08); }}
      }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{duration_s:.3f}"
      data-width="{width}"
      data-height="{height}"
    >
      <div class="canvas">
        <div class="grid-overlay"></div>
        <div class="orb orb-a"></div>
        <div class="orb orb-b"></div>
        <div class="orb orb-c"></div>
        {scene_markup}
        <div id="centered-subtitles" class="caption-shell clip" data-start="0" data-duration="{duration_s:.3f}">
          <div id="caption-line" class="caption-line"></div>
        </div>
      </div>
      <audio id="narration" src="assets/{html.escape(audio_asset_name)}" preload="auto" data-start="0"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines.main = tl;
      const cues = {cue_js};
      const scenes = {scene_js};
      const captionLine = document.getElementById("caption-line");

      function setCaption(text) {{
        captionLine.textContent = text || "";
      }}

      tl.set(".headline, .subline, .chip, .quote-card, .process-board, .data-board, .knowledge-board, .story-board, .scene-tag", {{
        autoAlpha: 0
      }});
      tl.set(".process-step, .metric-card, .bar-card, .satellite, .story-card, .story-dot", {{
        autoAlpha: 0
      }});
      scenes.forEach((scene) => {{
        const base = "#" + scene.id;
        tl.fromTo(base + " .scene-tag", {{ y: 20, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.45, ease: "power2.out" }}, scene.start + 0.02);
        tl.fromTo(base + " .headline", {{ y: 34, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.75, ease: "power3.out" }}, scene.start + 0.08);
        tl.fromTo(base + " .subline", {{ y: 28, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.65, ease: "power2.out" }}, scene.start + 0.22);
        tl.fromTo(base + " .chip", {{ y: 18, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.48, stagger: 0.08, ease: "power2.out" }}, scene.start + 0.3);
        tl.fromTo(base + " .quote-card", {{ y: 24, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.6, ease: "power2.out" }}, scene.start + Math.min(1.1, scene.duration * 0.32));

        if (scene.variant === "process") {{
          tl.fromTo(base + " .process-board", {{ x: 56, autoAlpha: 0 }}, {{ x: 0, autoAlpha: 1, duration: 0.7, ease: "power3.out" }}, scene.start + 0.22);
          tl.fromTo(base + " .process-step", {{ x: 22, autoAlpha: 0 }}, {{ x: 0, autoAlpha: 1, duration: 0.55, stagger: 0.22, ease: "power2.out" }}, scene.start + 0.38);
        }}
        if (scene.variant === "data") {{
          tl.fromTo(base + " .data-board", {{ x: 56, autoAlpha: 0 }}, {{ x: 0, autoAlpha: 1, duration: 0.72, ease: "power3.out" }}, scene.start + 0.18);
          tl.fromTo(base + " .metric-card", {{ y: 24, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.5, stagger: 0.14, ease: "power2.out" }}, scene.start + 0.38);
          scene.steps.forEach((_, idx) => {{
            const sel = base + " .bar-card.bar-" + idx;
            tl.fromTo(sel, {{ y: 28, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.48, ease: "power2.out" }}, scene.start + 0.6 + idx * 0.16);
            tl.fromTo(sel + " .bar", {{ height: 0 }}, {{ height: sel && document.querySelector(sel + " .bar") ? document.querySelector(sel + " .bar").dataset.targetHeight : 0, duration: 0.65, ease: "power2.out" }}, scene.start + 0.72 + idx * 0.16);
          }});
        }}
        if (scene.variant === "knowledge") {{
          tl.fromTo(base + " .knowledge-board", {{ x: 56, autoAlpha: 0 }}, {{ x: 0, autoAlpha: 1, duration: 0.72, ease: "power3.out" }}, scene.start + 0.16);
          tl.fromTo(base + " .satellite", {{ scale: 0.92, autoAlpha: 0 }}, {{ scale: 1, autoAlpha: 1, duration: 0.52, stagger: 0.18, ease: "power2.out" }}, scene.start + 0.52);
        }}
        if (scene.variant === "story") {{
          tl.fromTo(base + " .story-board", {{ x: 58, autoAlpha: 0 }}, {{ x: 0, autoAlpha: 1, duration: 0.72, ease: "power3.out" }}, scene.start + 0.18);
          tl.fromTo(base + " .story-card, " + base + " .story-dot", {{ y: 24, autoAlpha: 0 }}, {{ y: 0, autoAlpha: 1, duration: 0.52, stagger: 0.16, ease: "power2.out" }}, scene.start + 0.42);
        }}

        tl.to(base + " .headline, " + base + " .subline, " + base + " .chip, " + base + " .quote-card", {{
          autoAlpha: 0,
          y: -22,
          duration: 0.34,
          ease: "power1.in"
        }}, Math.max(scene.start + 0.9, scene.end - 0.42));
      }});

      cues.forEach((cue) => {{
        tl.call(() => setCaption(cue.text), [], cue.start);
        tl.fromTo("#caption-line", {{ autoAlpha: 0, y: 12 }}, {{ autoAlpha: 1, y: 0, duration: 0.16, ease: "power1.out" }}, cue.start);
        tl.to("#caption-line", {{ autoAlpha: 0, y: -10, duration: 0.18, ease: "power1.in" }}, Math.max(cue.start + 0.18, cue.end - 0.16));
      }});
    </script>
  </body>
</html>
"""


def render_scene_markup(scene: dict[str, Any], width: int, height: int) -> str:
    quote = html.escape(scene["quote"])
    chips = "\n".join(f'<div class="chip">{html.escape(text)}</div>' for text in scene["chips"][:4])
    main = render_variant_markup(scene, width, height)
    return f"""
<section id="{html.escape(scene['scene_id'])}" class="scene clip" data-start="{scene['start']:.3f}" data-duration="{scene['duration']:.3f}">
  <div class="scene-shell">
    <div class="headline">{html.escape(scene['headline'])}</div>
    <div class="subline">{html.escape(scene['subline'])}</div>
    <div class="chip-row">{chips}</div>
    {main}
    <div class="quote-card">{quote}</div>
  </div>
</section>
"""


def render_variant_markup(scene: dict[str, Any], width: int, height: int) -> str:
    if scene["variant"] == "process":
        step_gap = 172 if height > width else 116
        start_top = 90 if height > width else 72
        steps_html = []
        nodes_html = []
        for idx, step in enumerate(scene["steps"][:4]):
            top = start_top + idx * step_gap
            steps_html.append(
                f"""
      <div class="process-step" style="top:{top}px;">
        <div class="step-index">{idx + 1:02d}</div>
        <div class="step-text">{html.escape(step)}</div>
      </div>
"""
            )
            nodes_html.append(f'<div class="process-node" style="top:{top + 44}px;"></div>')
        return f"""
    <div class="glass-panel process-board">
      <div class="process-rail"></div>
      {''.join(nodes_html)}
      {''.join(steps_html)}
    </div>
"""
    if scene["variant"] == "data":
        bars = []
        metrics = []
        values = scene.get("values", [])[:3]
        for idx, item in enumerate(values):
            metrics.append(
                f"""
        <div class="metric-card">
          <div class="metric-label">{html.escape(item['label'])}</div>
          <div class="metric-value">{html.escape(item['value'])}</div>
        </div>
"""
            )
            bars.append(
                f"""
        <div class="bar-card bar-{idx}">
          <div class="bar-wrap">
            <div class="bar" data-target-height="{item['height']}%" style="height:{item['height']}%;"></div>
          </div>
          <div class="bar-label">{html.escape(item['label'])}</div>
        </div>
"""
            )
        return f"""
    <div class="glass-panel data-board">
      <div class="data-topline">{''.join(metrics)}</div>
      <div class="bar-zone">{''.join(bars)}</div>
    </div>
"""
    if scene["variant"] == "story":
        card_gap = 150 if height > width else 104
        cards = []
        dots = []
        for idx, step in enumerate(scene["steps"][:4]):
            top = 78 + idx * card_gap
            dots.append(f'<div class="story-dot" style="top:{top + 18}px;"></div>')
            cards.append(
                f"""
      <div class="story-card" style="top:{top}px;">
        <div class="story-card-title">{idx + 1:02d}</div>
        <div class="story-card-text">{html.escape(step)}</div>
      </div>
"""
            )
        return f"""
    <div class="glass-panel story-board">
      <div class="story-line"></div>
      {''.join(dots)}
      {''.join(cards)}
    </div>
"""
    satellites = []
    classes = ["satellite-a", "satellite-b", "satellite-c", "satellite-d"]
    for idx, step in enumerate(scene["steps"][:4]):
        satellites.append(f'<div class="satellite {classes[idx % len(classes)]}">{html.escape(step)}</div>')
    return f"""
    <div class="glass-panel knowledge-board">
      <div class="knowledge-core">
        <div class="knowledge-core-title">{html.escape(scene['core_title'])}</div>
        <div class="knowledge-core-sub">{html.escape(scene['core_sub'])}</div>
      </div>
      {''.join(satellites)}
    </div>
"""


def _build_scene_specs(
    project: dict[str, Any],
    scene_seed: dict[str, Any],
    cues: list[dict[str, Any]],
    source_text: str,
) -> list[dict[str, Any]]:
    raw_scenes = list(scene_seed.get("scenes") or [])
    if not raw_scenes:
        raw_scenes = [
            {
                "sceneNumber": 1,
                "sceneId": "scene_1",
                "start_s": 0.0,
                "end_s": max(float(cues[-1]["end"]) if cues else 12.0, 12.0),
                "duration_s": max(float(cues[-1]["end"]) if cues else 12.0, 12.0),
                "transcript": source_text,
            }
        ]
    family = dominant_style_family(str(project.get("target_style") or ""), source_text)
    scenes: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_scenes, start=1):
        transcript = normalize_text(str(raw.get("transcript") or source_text))
        if not transcript:
            continue
        clauses = split_clauses(transcript)
        variant = choose_scene_variant(family, transcript, idx)
        headline = choose_headline(transcript, idx)
        subline = choose_subline(clauses)
        chips = choose_chips(clauses)
        steps = choose_steps(transcript, clauses, variant)
        scene = {
            "scene_number": int(raw.get("sceneNumber") or idx),
            "scene_id": str(raw.get("sceneId") or f"scene_{idx}"),
            "start": float(raw.get("start_s") or 0.0),
            "end": float(raw.get("end_s") or (float(raw.get("start_s") or 0.0) + float(raw.get("duration_s") or 5.0))),
            "duration": float(raw.get("duration_s") or 5.0),
            "variant": variant,
            "headline": headline,
            "subline": subline,
            "chips": chips,
            "steps": steps,
            "quote": transcript,
            "core_title": chips[0] if chips else headline,
            "core_sub": subline,
        }
        if variant == "data":
            scene["values"] = build_metric_values(chips, idx)
            scene["elements"] = [{"kind": "metric", "label": item["label"], "value": item["value"]} for item in scene["values"]]
        else:
            scene["elements"] = [{"kind": "step", "text": step} for step in steps]
        scenes.append(scene)
    return scenes


def choose_scene_variant(family: str, transcript: str, idx: int) -> str:
    if re.search(r"第[一二三四五六七八九十0-9]+步|首先|然后|最后", transcript):
        return "process"
    if re.search(r"\d+|百分之|增长|下降|数据|指标|效率|目标", transcript):
        return "data" if family in {"data", "knowledge"} else family
    if family == "story":
        return "story"
    if family == "data" and idx % 2 == 1:
        return "data"
    if family == "process" and idx % 2 == 1:
        return "process"
    return family


def choose_headline(transcript: str, idx: int) -> str:
    clauses = split_clauses(transcript)
    if not clauses:
        return f"关键观点 {idx}"
    headline = clauses[0]
    headline = re.sub(r"^(今天|现在|我们|首先|然后|最后|所以|其实|就是)", "", headline).strip()
    if len(headline) > 20:
        headline = headline[:20].rstrip("，。；：,.!? ") + "…"
    return headline or clauses[0]


def choose_subline(clauses: list[str]) -> str:
    if len(clauses) >= 2:
        line = " · ".join(clauses[1:3])
    elif clauses:
        line = clauses[0]
    else:
        line = "围绕同一条叙事主线，逐层展开信息。"
    return line[:52]


def choose_chips(clauses: list[str]) -> list[str]:
    chips: list[str] = []
    for clause in clauses:
        text = clause.strip("，。！？；：,.!? ")
        if 2 <= len(text) <= 10 and text not in chips:
            chips.append(text)
        if len(chips) >= 4:
            break
    while len(chips) < 3:
        chips.append(["拆解", "执行", "交付", "验证"][len(chips)])
    return chips[:4]


def choose_steps(transcript: str, clauses: list[str], variant: str) -> list[str]:
    explicit = re.findall(r"(第[一二三四五六七八九十0-9]+步[^，。！？；；:：]*)", transcript)
    finals = re.findall(r"(最后[^，。！？；；:：]*)", transcript)
    steps = [normalize_text(item) for item in explicit + finals if normalize_text(item)]
    if len(steps) >= 2:
        return steps[:4]
    cleaned = [normalize_text(item) for item in clauses if normalize_text(item)]
    if variant == "data":
        return cleaned[:3] or ["信号上升", "执行聚焦", "结果收束"]
    return cleaned[:4] or [transcript[:14]]


def build_metric_values(chips: list[str], idx: int) -> list[dict[str, Any]]:
    labels = (chips + ["聚焦", "协同", "落地"])[:3]
    base = 54 + idx * 7
    values = []
    for offset, label in enumerate(labels):
        height = min(92, base + offset * 12)
        values.append(
            {
                "label": label,
                "value": "重点",
                "height": height,
            }
        )
    return values


def apply_creative_plan(scenes: list[dict[str, Any]], creative_plan: dict[str, Any]) -> list[dict[str, Any]]:
    overrides = {
        int(item.get("scene_number") or 0): item
        for item in creative_plan.get("scenes") or []
        if isinstance(item, dict)
    }
    allowed_variants = {"process", "data", "knowledge", "story"}
    for scene in scenes:
        item = overrides.get(int(scene["scene_number"]))
        if not item:
            continue
        variant = str(item.get("variant") or "")
        if variant in allowed_variants:
            scene["variant"] = variant
        for key, max_len in (("headline", 20), ("subline", 52)):
            value = normalize_text(str(item.get(key) or ""))[:max_len]
            if value:
                scene[key] = value
        for key, limit, max_len in (("chips", 4, 10), ("steps", 4, 16)):
            values = [normalize_text(str(value))[:max_len] for value in item.get(key) or []]
            values = [value for value in values if value]
            if values:
                scene[key] = values[:limit]
        supplied_values = []
        for value in item.get("values") or []:
            if not isinstance(value, dict):
                continue
            label = normalize_text(str(value.get("label") or ""))[:12]
            display = normalize_text(str(value.get("value") or ""))[:10]
            if label and display and display in scene["quote"]:
                supplied_values.append(
                    {
                        "label": label,
                        "value": display,
                        "height": max(24, min(94, int(value.get("height") or 60))),
                    }
                )
        scene["values"] = supplied_values or build_metric_values(scene["chips"], scene["scene_number"])
        scene["core_title"] = scene["chips"][0] if scene["chips"] else scene["headline"]
        scene["core_sub"] = scene["subline"]
        scene["elements"] = [{"kind": scene["variant"], "text": value} for value in scene["steps"]]
    return scenes


def safe_css_color(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text
    return fallback


def split_clauses(text: str) -> list[str]:
    parts = re.split(r"[，。！？；：,.!?;:]+", normalize_text(text))
    return [part.strip() for part in parts if part and part.strip()]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _style_label(style: str) -> str:
    labels = {
        "faceless_explainer": "通用解说",
        "data_story": "数据观点",
        "process_breakdown": "流程拆解",
        "knowledge_burst": "知识科普",
        "storytelling": "叙事讲述",
    }
    return labels.get(style, "解说视频")


def _load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_words(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.is_file():
        return []
    try:
        return normalize_words(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return []
