from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from openjiuwen.core.multi_agent.config import TeamConfig
from openjiuwen.core.multi_agent.team import BaseTeam
from openjiuwen.core.multi_agent.team_runtime import CommunicableAgent
from openjiuwen.core.session.session import Session
from openjiuwen.core.single_agent.base import BaseAgent
from openjiuwen.core.single_agent.schema.agent_card import AgentCard
from openjiuwen.core.multi_agent.schema.team_card import TeamCard

from .deepseek_api import create_async_client, deepseek_settings, parse_json_object


AGENT_PROMPTS = {
    "narrative": """你是解说视频内容导演。依据逐字稿与场景时间，仅输出 JSON：
{"strategy":"一句话叙事策略","scenes":[{"scene_number":1,"headline":"观众可见短标题","subline":"补充说明","chips":["关键词"],"steps":["信息点"]}]}
要求：逐场覆盖，不写制作术语，不虚构数据，标题不超过16个汉字，所有文字为简体中文。""",
    "visual": """你是高级动态图形视觉导演。依据逐字稿与场景时间，仅输出 JSON：
{"theme":{"mood":"","palette":["#hex"],"motion":""},"scenes":[{"scene_number":1,"variant":"process|data|knowledge|story","layout":"wide|split-left|split-right|center","visual_metaphor":"","emphasis":""}]}
要求：场景形式随内容变化；流程逐节点出现；数据只呈现原稿明确提供的数据；相邻场景不得使用相同 layout；避免整齐划一和PPT感。""",
    "timing": """你是动态图形时序与可读性专家。依据逐字稿与场景时间，仅输出 JSON：
{"rhythm":"","scenes":[{"scene_number":1,"density":"low|medium|high","entry_order":["标题","图形"],"hold_seconds":2.0}],"risks":[]}
要求：信息至少可读1.5秒；字幕固定底部居中；场景覆盖完整音频；同屏重点不超过两组。""",
}


class DeepSeekJsonAgent(CommunicableAgent, BaseAgent):
    def __init__(self, card: AgentCard, system_prompt: str, model: str):
        super().__init__(card=card)
        self.system_prompt = system_prompt
        self.model = model

    def configure(self, config: Any) -> "DeepSeekJsonAgent":
        return self

    async def invoke(self, inputs: Any, session: Optional[Session] = None) -> Any:
        payload = json.dumps(inputs, ensure_ascii=False, separators=(",", ":"))
        started = time.perf_counter()
        response = await create_async_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": payload},
            ],
            temperature=0.25,
            max_tokens=1800 if self.model.endswith("-pro") else 1200,
            extra_body={"thinking": {"type": "disabled"}},
        )
        message = response.choices[0].message
        result = parse_json_object(message.content or getattr(message, "reasoning_content", ""))
        return {
            "agent": self.card.id,
            "model": self.model,
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "result": result,
        }

    async def stream(self, inputs: Any, session: Optional[Session] = None) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, session)


class FrameCraftJiuwenTeam(BaseTeam):
    def __init__(self, team_id: str):
        super().__init__(
            card=TeamCard(id=team_id, name=team_id, description="FrameCraft openJiuwen 多智能体视频设计团队"),
            config=TeamConfig(max_agents=6, max_concurrent_messages=8, message_timeout=90),
        )
        cfg = deepseek_settings()
        fast_model = cfg["text_model"]
        cards = {
            name: AgentCard(id=name, name=name, description=f"FrameCraft {name} agent")
            for name in (*AGENT_PROMPTS.keys(), "code_director")
        }
        for name, prompt in AGENT_PROMPTS.items():
            self.add_agent(cards[name], lambda n=name, p=prompt: DeepSeekJsonAgent(cards[n], p, fast_model))
        self.add_agent(
            cards["code_director"],
            lambda: DeepSeekJsonAgent(cards["code_director"], _code_director_prompt(), cfg["pro_model"]),
        )

    async def design(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self.runtime.start()
        try:
            started = time.perf_counter()
            parallel = await asyncio.gather(
                *[
                    self.runtime.send(payload, recipient=name, sender="leader")
                    for name in AGENT_PROMPTS
                ]
            )
            synthesis = await self.runtime.send(
                {"source": payload, "expert_reports": parallel},
                recipient="code_director",
                sender="leader",
            )
            return {
                "framework": "openjiuwen",
                "topology": "leader_parallel_experts_then_code_director",
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "experts": parallel,
                "creative_plan": synthesis["result"],
                "code_director": {k: v for k, v in synthesis.items() if k != "result"},
            }
        finally:
            await self.runtime.stop()

    async def invoke(self, inputs: Any, session: Optional[Session] = None) -> Any:
        return await self.design(dict(inputs or {}))

    async def stream(self, inputs: Any, session: Optional[Session] = None) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, session)


def _code_director_prompt() -> str:
    return """你是 HyperFrames 代码总监。综合三位专家结果，为通用组件渲染器生成唯一创意规格。只输出 JSON：
{
  "theme":{"background":"#07111f","surface":"rgba(9,20,44,.58)","primary":"#7cb4ff","secondary":"#41e5b5","accent":"#ffb35c"},
  "scenes":[{"scene_number":1,"variant":"process|data|knowledge|story","layout":"wide|split-left|split-right|center","headline":"","subline":"","chips":[""],"steps":[""],"values":[{"label":"原稿中的指标","value":"原稿中的值","height":70}]}]
}
硬约束：场景数量和编号必须与 source.scenes 完全一致；每场文字基于对应 transcript；观众可见文字全为简体中文；不得出现“场景、步骤、制作、动画、工作流、FrameCraft”等幕后文案；不得编造百分比或事实；流程图逐节点；相邻场景尽量使用不同 variant 且不得使用相同 layout；每个标题最多16字，每个说明最多32字，每个节点最多12字。"""


def run_creative_team(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(FrameCraftJiuwenTeam(f"framecraft_{project_id}").design(payload))


async def review_contact_sheet(image_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    cfg = deepseek_settings()
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt = """你是成片视觉验收 Agent。这是一张按时间顺序覆盖全片的抽帧联系表。检查：文字是否可读、构图是否高级、信息是否过少或拥挤、是否出现幕后制作文案、字幕是否底部居中、各场景是否有明显变化。画面最底部的黑色圆角胶囊是字幕；左下方较大的半透明矩形是观众内容卡，不要把两者混淆。第一人称表达若能在 source_transcript 中找到，属于原始演讲内容，不是幕后文案。只输出 JSON：{"pass":true,"score":0-100,"issues":[],"summary":""}。存在明显问题时 pass 必须为 false。"""
    started = time.perf_counter()
    response = await create_async_client().chat.completions.create(
        model=cfg["vision_model"],
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": json.dumps(context, ensure_ascii=False)},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                ],
            },
        ],
        temperature=0,
        max_tokens=1000,
        extra_body={"thinking": {"type": "disabled"}},
    )
    message = response.choices[0].message
    result = parse_json_object(message.content or getattr(message, "reasoning_content", ""))
    result.update(
        {
            "reviewer": "openjiuwen_visual_qa",
            "model": cfg["vision_model"],
            "contact_sheet": str(image_path),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }
    )
    return result


def run_visual_review(image_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(review_contact_sheet(image_path, context))
