from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import AsyncOpenAI, OpenAI

from . import store

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_FAST_MODEL = "deepseek-v4-flash"
DEFAULT_PRO_MODEL = "deepseek-v4-pro"
DEFAULT_VISION_MODEL = "deepseek-v4-flash-vision-exp"


def deepseek_settings() -> dict[str, str]:
    settings = store.snapshot()["settings"]
    text_model = str(settings.get("text_model") or DEFAULT_FAST_MODEL).strip()
    vision_model = str(settings.get("vision_model") or DEFAULT_VISION_MODEL).strip()
    return {
        "api_key": os.getenv("DEEPSEEK_API_KEY", "").strip() or str(settings.get("api_key") or "").strip(),
        "base_url": str(os.getenv("DEEPSEEK_BASE_URL") or settings.get("base_url") or DEFAULT_BASE_URL).strip(),
        "text_model": text_model if text_model.startswith("deepseek-") else DEFAULT_FAST_MODEL,
        "pro_model": str(settings.get("pro_model") or DEFAULT_PRO_MODEL).strip(),
        "vision_model": vision_model if vision_model.startswith("deepseek-") else DEFAULT_VISION_MODEL,
    }


def deepseek_available() -> bool:
    return bool(deepseek_settings()["api_key"])


def create_client() -> OpenAI:
    cfg = deepseek_settings()
    if not cfg["api_key"]:
        raise RuntimeError("DeepSeek API Key 未配置。请在模型设置中填写，或设置 DEEPSEEK_API_KEY。")
    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=90)


def create_async_client() -> AsyncOpenAI:
    cfg = deepseek_settings()
    if not cfg["api_key"]:
        raise RuntimeError("DeepSeek API Key 未配置。请在模型设置中填写，或设置 DEEPSEEK_API_KEY。")
    return AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=90)


def parse_json_object(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if not text:
        raise RuntimeError("Agent 返回了空结果。")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", text):
            try:
                candidate, _ = decoder.raw_decode(text[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                parsed = candidate
                break
        if parsed is None:
            raise RuntimeError("Agent 没有返回可解析的 JSON。")
    if not isinstance(parsed, dict):
        raise RuntimeError("Agent 返回结果必须是 JSON 对象。")
    return parsed
