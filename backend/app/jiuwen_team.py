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

MOTIF_CATALOG = """可用高质量科学视觉母题：spectrum_prism 棱镜与光谱分解；particle_scatter 粒子碰撞与分流；atmospheric_globe 星球、大气层与观察者；horizon_path 地平线与长短路径；split_synthesis 双场景结论对照；orbital_system 环绕系统；cell_network 细胞或节点网络；layered_scale 多层尺度；flow_machine 机制流动装置；field_comparison 连续场对比；timeline_curve 演化曲线；data_landscape 数据地形。选择母题时依据当前科学概念，允许使用不同 actor、方向、色彩和层级，相邻场景不得重复母题。"""

ART_DIRECTOR_PROMPT = f"""你是科普动态图形总导演。综合专家报告，为整片制定艺术圣经。只输出 JSON：
{{"art_bible":{{"concept":"","mood":"","background":"#hex","primary":"#hex","secondary":"#hex","accent":"#hex","warm":"#hex","type_style":"","motion_language":"","continuity_device":""}},"scene_assignments":[{{"scene_number":1,"motif":"","directing_note":"","transition_in":"","transition_out":""}}]}}
{MOTIF_CATALOG}
要求：每幕科学现象对应一个可视化隐喻；全片至少三种明显不同的空间结构；避免玻璃卡片墙和PPT版式；色彩、字体、章节导航形成连续性；观众可见文字全为简体中文；不得虚构数字。"""

SCENE_DESIGN_PROMPT = f"""你是只负责一幕的资深科学动态图形设计师。你会收到当前幕逐字稿、总导演艺术圣经和专家意见。只输出 JSON：
{{"scene_number":1,"motif":"","headline":"","subline":"","focus":"","labels":[""],"actors":[{{"kind":"sun|prism|ray|particle|molecule|globe|atmosphere|observer|path|orbit|cell|node|wave|bar|label","label":"","role":""}}],"composition":{{"flow":"left-to-right|right-to-left|radial|vertical|split|diagonal","focus_x":50,"focus_y":55,"visual_scale":90,"depth":"foreground|midground|deep"}},"animation_beats":[{{"at":0.1,"action":"draw|scatter|split|orbit|grow|pulse|travel|reveal|fade","target":"","meaning":""}}],"transition_in":"","transition_out":""}}
{MOTIF_CATALOG}
要求：只处理当前幕；画面先表达科学关系，再承载文字；至少三个 actor；至少三个有先后顺序的动画节拍；动画在入场完成后继续运动；标题不超过16字、说明不超过30字、标签不超过10字；不输出制作术语给观众。"""

QUALITY_CRITIC_PROMPT = """你是高级科普视频方案审片人。检查整合后的创意规格是否达到专业动态图形标准，只输出 JSON：
{"pass":true,"score":0,"issues":[{"scene_number":1,"problem":"","fix":""}],"global_fix":""}
检查重点：每幕视觉是否真正解释对应逐字稿；相邻母题与空间结构是否明显不同；每幕是否至少三个视觉角色、三个有顺序的动画节拍；是否存在PPT卡片感、无意义装饰、过小主视觉、幕后文案、虚构数据；全片色彩和转场是否连续。低于85分必须 pass=false，并给出可以直接执行的逐幕修正。"""


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
            config=TeamConfig(max_agents=18, max_concurrent_messages=18, message_timeout=90),
        )
        cfg = deepseek_settings()
        fast_model = cfg["text_model"]
        cards = {
            name: AgentCard(id=name, name=name, description=f"FrameCraft {name} agent")
            for name in (*AGENT_PROMPTS.keys(), "art_director", "quality_critic", "code_director")
        }
        for name, prompt in AGENT_PROMPTS.items():
            self.add_agent(cards[name], lambda n=name, p=prompt: DeepSeekJsonAgent(cards[n], p, fast_model))
        self.add_agent(
            cards["art_director"],
            lambda: DeepSeekJsonAgent(cards["art_director"], ART_DIRECTOR_PROMPT, cfg["pro_model"]),
        )
        self.add_agent(
            cards["quality_critic"],
            lambda: DeepSeekJsonAgent(cards["quality_critic"], QUALITY_CRITIC_PROMPT, fast_model),
        )
        self.add_agent(
            cards["code_director"],
            lambda: DeepSeekJsonAgent(cards["code_director"], _code_director_prompt(), cfg["pro_model"]),
        )

    async def design(self, payload: dict[str, Any]) -> dict[str, Any]:
        cfg = deepseek_settings()
        for index, raw_scene in enumerate(payload.get("scenes") or []):
            scene_number = int(raw_scene.get("scene_number") or index + 1)
            name = f"scene_designer_{scene_number}"
            card = AgentCard(id=name, name=name, description=f"第 {scene_number} 幕独立科学动画设计师")
            self.add_agent(card, lambda c=card: DeepSeekJsonAgent(c, SCENE_DESIGN_PROMPT, cfg["text_model"]))
        await self.runtime.start()
        try:
            started = time.perf_counter()
            parallel = await asyncio.gather(
                *[
                    self.runtime.send(payload, recipient=name, sender="leader")
                    for name in AGENT_PROMPTS
                ]
            )
            art_direction = await self.runtime.send(
                {"source": payload, "expert_reports": parallel},
                recipient="art_director",
                sender="leader",
            )
            scene_reports = await asyncio.gather(
                *[
                    self.runtime.send(
                        {
                            "project": payload.get("project"),
                            "scene": raw_scene,
                            "art_direction": art_direction["result"],
                            "expert_reports": parallel,
                        },
                        recipient=f"scene_designer_{int(raw_scene.get('scene_number') or index + 1)}",
                        sender="art_director",
                    )
                    for index, raw_scene in enumerate(payload.get("scenes") or [])
                ]
            )
            synthesis = await self.runtime.send(
                {
                    "source": payload,
                    "expert_reports": parallel,
                    "art_direction": art_direction,
                    "scene_reports": scene_reports,
                },
                recipient="code_director",
                sender="art_director",
            )
            plan_review = await self.runtime.send(
                {"source": payload, "art_direction": art_direction, "creative_plan": synthesis.get("result") or {}},
                recipient="quality_critic",
                sender="art_director",
            )
            if not plan_review["result"].get("pass") or float(plan_review["result"].get("score") or 0) < 85:
                synthesis = await self.runtime.send(
                    {
                        "source": payload,
                        "expert_reports": parallel,
                        "art_direction": art_direction,
                        "scene_reports": scene_reports,
                        "previous_plan": synthesis.get("result") or {},
                        "quality_review": plan_review["result"],
                        "instruction": "逐项落实审片意见，返回完整修订版，不能只返回差异。",
                    },
                    recipient="code_director",
                    sender="quality_critic",
                )
            creative_plan = normalize_creative_plan(
                payload,
                art_direction.get("result") or {},
                [report.get("result") or {} for report in scene_reports],
                synthesis.get("result") or {},
            )
            return {
                "framework": "openjiuwen",
                "topology": "parallel_experts_then_art_director_then_parallel_scene_agents_then_integrator",
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "experts": parallel,
                "art_direction": art_direction,
                "scene_agents": scene_reports,
                "plan_review": plan_review,
                "creative_plan": creative_plan,
                "code_director": {k: v for k, v in synthesis.items() if k != "result"},
            }
        finally:
            await self.runtime.stop()

    async def invoke(self, inputs: Any, session: Optional[Session] = None) -> Any:
        return await self.design(dict(inputs or {}))

    async def stream(self, inputs: Any, session: Optional[Session] = None) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, session)


def _code_director_prompt() -> str:
    return """你是 HyperFrames 集成导演。综合专家、总导演与每幕独立设计师结果，生成唯一全片创意规格。只输出 JSON：
{
  "theme":{"background":"#07111f","primary":"#7cb4ff","secondary":"#41e5b5","accent":"#ffb35c","warm":"#ff765a","mood":"","motion_language":"","continuity_device":""},
  "scenes":[{"scene_number":1,"variant":"process|data|knowledge|story","layout":"wide|split-left|split-right|center","semantic_motion":"mechanism|scale|comparison|timeline|system","motif":"","headline":"","subline":"","chips":[""],"steps":[""],"actors":[{"kind":"","label":"","role":""}],"composition":{"flow":"","focus_x":50,"focus_y":55,"visual_scale":90,"depth":"midground"},"animation_beats":[{"at":0.1,"action":"","target":"","meaning":""}]}]
}
""" + MOTIF_CATALOG + """
硬约束：场景数量和编号必须与 source.scenes 完全一致；优先保留每幕设计师的科学隐喻并统一艺术风格；相邻场景不能重复 motif；每场文字基于对应 transcript 和 visual_claim；观众可见文字全为简体中文；不得出现“场景、步骤、制作、动画、工作流、FrameCraft”等幕后文案；不得编造数字或事实；每幕至少三个 actors 和三个 animation_beats；每个标题最多16字，每个说明最多30字，每个节点最多10字。"""


def normalize_creative_plan(
    source: dict[str, Any],
    art_direction: dict[str, Any],
    scene_reports: list[dict[str, Any]],
    synthesis: dict[str, Any],
) -> dict[str, Any]:
    """Merge all agent layers without allowing the final summarizer to drop scene work."""
    art_bible = art_direction.get("art_bible") if isinstance(art_direction.get("art_bible"), dict) else {}
    theme = synthesis.get("theme") if isinstance(synthesis.get("theme"), dict) else {}
    merged_theme = {**art_bible, **theme}
    assignments = {
        int(item.get("scene_number") or 0): item
        for item in art_direction.get("scene_assignments") or []
        if isinstance(item, dict)
    }
    reports = {
        int(item.get("scene_number") or 0): item
        for item in scene_reports
        if isinstance(item, dict)
    }
    integrated = {
        int(item.get("scene_number") or 0): item
        for item in synthesis.get("scenes") or []
        if isinstance(item, dict)
    }
    scenes: list[dict[str, Any]] = []
    for index, source_scene in enumerate(source.get("scenes") or []):
        number = int(source_scene.get("scene_number") or index + 1)
        assignment = assignments.get(number, {})
        report = reports.get(number, {})
        final = integrated.get(number, {})
        scene = {**report, **final, "scene_number": number}
        scene["motif"] = str(
            final.get("motif") or report.get("motif") or assignment.get("motif") or ""
        ).strip()
        scene["headline"] = str(
            final.get("headline") or report.get("headline") or source_scene.get("headline") or ""
        ).strip()
        scene["subline"] = str(
            final.get("subline") or report.get("subline") or source_scene.get("visual_claim") or ""
        ).strip()
        for key in ("actors", "animation_beats", "labels"):
            candidate = final.get(key) or report.get(key) or []
            scene[key] = candidate if isinstance(candidate, list) else []
        composition = final.get("composition") or report.get("composition") or {}
        scene["composition"] = composition if isinstance(composition, dict) else {}
        scene["transition_in"] = str(
            final.get("transition_in") or report.get("transition_in") or assignment.get("transition_in") or ""
        )
        scene["transition_out"] = str(
            final.get("transition_out") or report.get("transition_out") or assignment.get("transition_out") or ""
        )
        scenes.append(scene)
    return {"theme": merged_theme, "scenes": scenes}


def run_creative_team(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(FrameCraftJiuwenTeam(f"framecraft_{project_id}").design(payload))


async def review_contact_sheet(image_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    cfg = deepseek_settings()
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    prompt = """你是科普成片视觉验收 Agent。这是一张按真实分镜抽取、从左到右再从上到下排列的全片联系表，采样秒数见 media_validation.contact_sample_times_s，采样策略通常为每幕依次抽取入场、中段、退场三帧。context.scenes 是真实分镜清单。联系表中的每格会等比缩到 384 或 480 像素宽，原片通常为 1920 像素宽；必须按元素占单格的相对比例判断最终字号和可读性，不能把缩略图的表观字号直接当作原片字号。字幕容器在原片底部水平居中，只有视觉中心相对单格中心明显偏离时才判定未居中。
检查：每场能否在一秒内看出科学焦点；三张连续采样是否体现明确入场、持续运动或状态演化、退场衔接，不能只是整块卡片淡入淡出；静帧是否能辨认机制、尺度、对比、时间线或系统关系；相邻场景是否采用不同空间结构与运动方向；主视觉是否充分利用画面且没有大片无意义空白；文字是否可读且不拥挤；是否出现幕后制作文案；字幕是否固定在底部居中。字幕是逐字稿的短时分段，片段以逗号结束属于正常断句；只有字形触碰容器边缘、被遮住或残缺时才能判定 CSS 截断。仅当 context.requires_source_labels 为 true 时检查相关场景左下来源；用户原文和上传媒体模式没有外部来源台账，不得因缺少来源标注扣分。不要要求定性尺度图伪造数值刻度，只有原稿含精确数字时才检查数字一致性。只输出 JSON：{"pass":true,"score":0-100,"issues":[],"summary":""}。存在真实可见问题时 pass 必须为 false。"""
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
