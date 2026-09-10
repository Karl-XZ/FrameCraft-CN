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
    "narrative": """你是科学可视化内容导演。依据逐字稿、章节视觉主张与场景时间，仅输出 JSON：
{"strategy":"一句话科学解释路径","scenes":[{"scene_number":1,"headline":"观众可见短标题","subline":"当前概念的解释","chips":["科学关键词"],"steps":["因果或结构节点"]}]}
要求：不改写旁白事实；每场聚焦一个概念；不写制作术语；不虚构数据；避免“不是……而是……”句式；所有文字为简体中文。""",
    "visual": """你是高级科学动态图形导演。依据逐字稿与 visual_claim，仅输出 JSON：
{"theme":{"mood":"","palette":["#hex"],"motion":""},"scenes":[{"scene_number":1,"variant":"process|data|knowledge|story","layout":"wide|split-left|split-right|center","semantic_motion":"mechanism|scale|comparison|timeline|system","visual_metaphor":"","emphasis":""}]}
要求：动画必须解释机制、尺度、对比、时间或系统关系；对象在入场后仍有传播、旋转、增长、连接或状态变化；数据只呈现原稿明确提供的数据；相邻场景不得使用相同布局；禁止卡片轮播和PPT感。""",
    "timing": """你是动态图形时序与可读性专家。依据逐字稿与场景时间，仅输出 JSON：
{"rhythm":"","scenes":[{"scene_number":1,"density":"low|medium|high","entry_order":["标题","图形"],"hold_seconds":2.0}],"risks":[]}
要求：信息至少可读1.5秒；字幕固定底部居中；来源行位于左下且不与字幕碰撞；场景覆盖完整音频；同屏重点不超过两组。""",
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
  "scenes":[{"scene_number":1,"variant":"process|data|knowledge|story","layout":"wide|split-left|split-right|center","semantic_motion":"mechanism|scale|comparison|timeline|system","headline":"","subline":"","chips":[""],"steps":[""],"values":[{"label":"原稿中的指标","value":"原稿中的值","height":70}]}]
}
硬约束：场景数量和编号必须与 source.scenes 完全一致；variant 与 semantic_motion 必须一致：process 只配 mechanism，data 只配 scale/comparison，story 只配 timeline，knowledge 只配 system；每场文字基于对应 transcript 和 visual_claim；观众可见文字全为简体中文；不得出现“场景、步骤、制作、动画、工作流、FrameCraft”等幕后文案；不得编造百分比或事实；语义图逐节点演化；相邻场景使用不同视觉结构和 layout；每个标题最多16字，每个说明最多32字，每个节点最多12字。"""


def run_creative_team(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(FrameCraftJiuwenTeam(f"framecraft_{project_id}").design(payload))


async def review_contact_sheet(image_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    cfg = deepseek_settings()
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt = """你是科普成片视觉验收 Agent。这是一张按真实分镜中点抽取、从左到右再从上到下排列的全片联系表，采样秒数见 media_validation.contact_sample_times_s。context.scenes 是真实分镜清单。联系表中的每格被等比缩到 480 像素宽，原片通常为 1920 像素宽；必须按元素占单格的相对比例判断最终字号和可读性，不能把四分之一缩略图的表观字号直接当作原片字号。字幕容器在原片底部水平居中，只有视觉中心相对单格中心明显偏离时才判定未居中。
检查：每场能否在一秒内看出科学焦点；静帧是否能辨认机制、尺度、对比、时间线或系统关系；不同语义是否采用不同空间结构；主视觉是否充分利用画面且没有大片无意义空白；文字是否可读且不拥挤；是否出现幕后制作文案；字幕是否固定在底部居中。字幕是逐字稿的短时分段，片段以逗号结束属于正常断句；只有字形触碰容器边缘、被遮住或残缺时才能判定 CSS 截断。仅当 context.requires_source_labels 为 true 时检查相关场景左下来源；用户原文和上传媒体模式没有外部来源台账，不得因缺少来源标注扣分。不要要求定性尺度图伪造数值刻度，只有原稿含精确数字时才检查数字一致性。只输出 JSON：{"pass":true,"score":0-100,"issues":[],"summary":""}。存在真实可见问题时 pass 必须为 false。"""
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
