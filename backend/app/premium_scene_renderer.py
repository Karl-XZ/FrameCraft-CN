from __future__ import annotations

import html
from typing import Any


PREMIUM_MOTIFS = {
    "spectrum_prism",
    "particle_scatter",
    "atmospheric_globe",
    "horizon_path",
    "split_synthesis",
    "orbital_system",
    "cell_network",
    "layered_scale",
    "flow_machine",
    "field_comparison",
    "timeline_curve",
    "data_landscape",
}


def premium_scene_css(width: int, height: int, theme: dict[str, Any]) -> str:
    primary = str(theme.get("primary") or "#59c8ff")
    secondary = str(theme.get("secondary") or "#62e2bd")
    accent = str(theme.get("accent") or "#ffd36a")
    warm = str(theme.get("warm") or "#ff765a")
    portrait = height > width
    stage_top = 410 if portrait else 250
    stage_height = 1090 if portrait else 650
    return f"""
      .premium-scene .headline {{ font-weight: 900; text-shadow: 0 12px 48px rgba(0,0,0,.35); }}
      .premium-stage {{ position:absolute; left:-4%; right:-4%; top:{stage_top}px; height:{stage_height}px; overflow:visible; }}
      .premium-stage .pm-label {{ position:absolute; padding:12px 18px; border-radius:999px; background:rgba(2,10,25,.72); border:1px solid rgba(255,255,255,.15); color:#f8fcff; font-size:{30 if portrait else 22}px; font-weight:750; box-shadow:0 16px 40px rgba(0,0,0,.25); z-index:8; }}
      .pm-sun {{ position:absolute; width:{170 if portrait else 145}px; height:{170 if portrait else 145}px; border-radius:50%; background:radial-gradient(circle at 35% 30%,#fff9d2 0 9%,{accent} 38%,{warm} 73%,rgba(255,118,90,.1) 74%); box-shadow:0 0 55px {accent},0 0 150px rgba(255,118,90,.4); animation:pmSun 3s ease-in-out infinite; }}
      .pm-prism {{ position:absolute; width:0; height:0; border-left:150px solid transparent; border-right:150px solid transparent; border-bottom:280px solid rgba(178,235,255,.18); filter:drop-shadow(0 0 35px rgba(110,210,255,.38)); }}
      .pm-prism::after {{ content:""; position:absolute; left:-150px; top:0; width:296px; height:276px; clip-path:polygon(50% 0,100% 100%,0 100%); border:3px solid rgba(220,248,255,.72); background:linear-gradient(145deg,rgba(255,255,255,.2),rgba(80,184,255,.03)); }}
      .pm-beam {{ position:absolute; height:10px; border-radius:12px; transform-origin:left; box-shadow:0 0 24px currentColor; animation:pmBeam 2.4s ease-in-out infinite; }}
      .pm-spectrum .pm-beam:nth-child(1){{color:#ff5362;background:#ff5362;transform:rotate(-18deg)}} .pm-spectrum .pm-beam:nth-child(2){{color:#ff9852;background:#ff9852;transform:rotate(-12deg)}} .pm-spectrum .pm-beam:nth-child(3){{color:#ffe06b;background:#ffe06b;transform:rotate(-6deg)}} .pm-spectrum .pm-beam:nth-child(4){{color:#69e98c;background:#69e98c}} .pm-spectrum .pm-beam:nth-child(5){{color:#52c4ff;background:#52c4ff;transform:rotate(6deg)}} .pm-spectrum .pm-beam:nth-child(6){{color:#8586ff;background:#8586ff;transform:rotate(12deg)}} .pm-spectrum .pm-beam:nth-child(7){{color:#d276ff;background:#d276ff;transform:rotate(18deg)}}
      .pm-molecule {{ position:absolute; width:40px; height:40px; border-radius:50%; background:radial-gradient(circle at 35% 30%,#e4fbff,{primary} 44%,#173d70 74%); box-shadow:0 0 32px rgba(89,200,255,.48); animation:pmFloat 4s ease-in-out infinite; }}
      .pm-molecule::after {{ content:""; position:absolute; width:22px; height:22px; right:-14px; bottom:-8px; border-radius:50%; background:#467ec2; }}
      .pm-path {{ fill:none; stroke-linecap:round; stroke-dasharray:24 17; animation:pmDash 2.1s linear infinite; }}
      .pm-blue {{ stroke:{primary}; filter:drop-shadow(0 0 12px {primary}); }} .pm-red {{ stroke:{warm}; filter:drop-shadow(0 0 10px {warm}); }}
      .pm-globe {{ position:absolute; left:50%; bottom:-430px; width:{1350 if not portrait else 1150}px; height:{730 if not portrait else 1150}px; transform:translateX(-50%); border-radius:50%; background:radial-gradient(circle at 50% 4%,#2794af 0 18%,#0a5870 40%,#042b3a 70%); box-shadow:0 -18px 44px rgba(74,196,255,.35),0 -55px 150px rgba(45,143,255,.3); }}
      .pm-atmosphere {{ position:absolute; left:50%; bottom:-385px; width:{1460 if not portrait else 1240}px; height:{790 if not portrait else 1240}px; transform:translateX(-50%); border-radius:50%; border:18px solid rgba(82,188,255,.2); box-shadow:0 -16px 72px rgba(67,181,255,.4); animation:pmAtmosphere 4s ease-in-out infinite; }}
      .pm-photon {{ position:absolute; width:21px; height:21px; border-radius:50%; background:{primary}; box-shadow:0 0 30px {primary}; animation:pmPhoton 3.1s ease-in-out infinite; }}
      .pm-observer {{ position:absolute; width:46px; height:110px; z-index:7; }} .pm-observer::before{{content:"";position:absolute;left:7px;width:32px;height:32px;border-radius:50%;background:#fff}} .pm-observer::after{{content:"";position:absolute;left:20px;top:30px;width:8px;height:73px;background:#fff;box-shadow:-19px 30px 0 -2px #fff,19px 30px 0 -2px #fff}}
      .pm-horizon {{ position:absolute; left:-8%; right:-8%; bottom:-30px; height:210px; background:linear-gradient(#09283c,#020914); border-radius:50% 50% 0 0; }}
      .pm-orbit {{ position:absolute; left:50%; top:50%; border:2px dashed rgba(255,255,255,.25); border-radius:50%; transform:translate(-50%,-50%); animation:pmSpin 20s linear infinite; }}
      .pm-node {{ position:absolute; width:76px; height:76px; border-radius:50%; display:grid; place-items:center; background:{primary}; box-shadow:0 0 0 18px rgba(89,200,255,.1),0 0 60px rgba(89,200,255,.55); animation:pmNode 2.4s ease-in-out infinite; }}
      .pm-cell {{ position:absolute; width:150px; height:125px; border-radius:52% 48% 55% 45%; background:radial-gradient(circle at 43% 45%,{accent} 0 10%,rgba(98,226,189,.4) 12% 38%,rgba(28,96,103,.55) 40%); border:2px solid rgba(149,255,229,.38); box-shadow:0 0 45px rgba(98,226,189,.22); animation:pmCell 5s ease-in-out infinite; }}
      .pm-layer {{ position:absolute; left:50%; border-radius:50%; border:3px solid rgba(89,200,255,.34); transform:translateX(-50%); box-shadow:0 0 45px rgba(89,200,255,.12); animation:pmLayer 4s ease-in-out infinite; }}
      .pm-split {{ position:absolute; inset:0; display:grid; grid-template-columns:1fr 150px 1fr; gap:28px; align-items:center; }}
      .pm-side {{ position:relative; height:88%; border-radius:42px; overflow:hidden; border:1px solid rgba(255,255,255,.16); box-shadow:0 28px 75px rgba(0,0,0,.28); }}
      .pm-side.cool {{ background:radial-gradient(circle at 25% 20%,#b9e9ff,{primary} 42%,#063363); }} .pm-side.warm {{ background:radial-gradient(circle at 74% 62%,#ffd27e,{warm} 27%,#542642 65%,#111429); }}
      .pm-side h3 {{ position:absolute; left:28px; top:26px; padding:10px 16px; border-radius:15px; background:#eefaff; color:#061326; font-size:{32 if not portrait else 27}px; }} .pm-side.warm h3{{background:#160e25;color:#fff}}
      .pm-side p {{ position:absolute; left:32px; bottom:28px; padding:10px 14px; border-radius:14px; background:rgba(2,8,22,.9); color:#fff; font-size:{24 if not portrait else 22}px; line-height:1.45; font-weight:750; text-shadow:0 3px 16px #000; }}
      .pm-equals {{ width:132px; height:132px; border-radius:50%; display:grid; place-items:center; text-align:center; font-size:21px; font-weight:900; background:rgba(2,8,22,.78); border:2px solid rgba(255,255,255,.22); box-shadow:0 0 0 15px rgba(255,255,255,.05),0 0 65px rgba(89,200,255,.25); animation:pmNode 3s ease-in-out infinite; z-index:6; }}
      .pm-flow-line {{ position:absolute; height:8px; border-radius:9px; background:linear-gradient(90deg,{primary},{secondary},{accent}); box-shadow:0 0 24px rgba(89,200,255,.5); transform-origin:left; animation:pmBeam 2.2s ease-in-out infinite; }}
      .pm-data-bar {{ position:absolute; bottom:30px; width:110px; border-radius:30px 30px 10px 10px; background:linear-gradient(180deg,{primary},{secondary}); box-shadow:0 0 45px rgba(89,200,255,.25); animation:pmData 3s ease-in-out infinite; }}
      .pm-cool-particle {{ position:absolute; width:18px; height:18px; border-radius:50%; background:{primary}; box-shadow:0 0 24px {primary}; }}
      .pm-warm-core {{ position:absolute; left:50%; top:52%; width:110px; height:110px; transform:translate(-50%,-50%); border-radius:50%; background:radial-gradient(circle,#fff7c7 0 12%,{accent} 34%,{warm} 66%,transparent 68%); box-shadow:0 0 70px {warm}; }}
      @keyframes pmSun{{50%{{transform:scale(1.06);filter:brightness(1.1)}}}} @keyframes pmBeam{{50%{{opacity:.58;filter:brightness(1.35)}}}} @keyframes pmFloat{{50%{{transform:translate(10px,-18px)}}}} @keyframes pmDash{{to{{stroke-dashoffset:-82}}}} @keyframes pmAtmosphere{{50%{{transform:translateX(-50%) scale(1.025);opacity:.78}}}} @keyframes pmPhoton{{50%{{transform:translate(38px,-32px);opacity:.55}}}} @keyframes pmSpin{{to{{transform:translate(-50%,-50%) rotate(360deg)}}}} @keyframes pmNode{{50%{{transform:scale(1.08);filter:brightness(1.18)}}}} @keyframes pmCell{{50%{{transform:translate(8px,-14px) rotate(3deg)}}}} @keyframes pmLayer{{50%{{transform:translateX(-50%) scale(1.035);opacity:.68}}}} @keyframes pmData{{50%{{transform:scaleY(.92);filter:brightness(1.2)}}}}
    """


def render_premium_scene(scene: dict[str, Any]) -> str:
    motif = str(scene.get("motif") or "").strip()
    labels = _labels(scene)
    if motif == "spectrum_prism":
        rays = "".join('<span class="pm-beam pm-spectrum-ray pm-beat" style="left:0;top:50%;width:92%"></span>' for _ in range(7))
        return f'<div class="premium-stage pm-spectrum-stage"><div class="pm-sun pm-beat" style="left:2%;top:34%"></div><div class="pm-beam pm-input-beam pm-beat" style="left:11%;top:51%;width:37%;background:#fff;color:#fff"></div><div class="pm-prism pm-beat" style="left:43%;top:13%"></div><div class="pm-spectrum" style="position:absolute;left:58%;top:28%;width:39%;height:250px">{rays}</div>{_label(labels[0], 43, 84)}</div>'
    if motif == "particle_scatter":
        molecules = "".join(f'<span class="pm-molecule pm-beat" style="left:{14+i*14}%;top:{18+(i%3)*27}%;animation-delay:-{i*.55:.2f}s"></span>' for i in range(6))
        return f'<div class="premium-stage">{molecules}<div class="pm-beam pm-beat" style="left:2%;top:52%;width:43%;background:#fff;color:#fff"></div><div class="pm-node pm-beat" style="left:46%;top:45%;width:82px;height:82px"></div><svg class="pm-beat" style="position:absolute;left:46%;top:8%;width:52%;height:82%" viewBox="0 0 900 450"><path class="pm-path pm-blue" stroke-width="8" d="M20 220 C220 180 300 55 510 28"/><path class="pm-path pm-blue" stroke-width="8" d="M20 220 C230 250 350 395 540 425"/><path class="pm-path pm-blue" stroke-width="7" d="M20 220 C240 210 430 115 760 105"/><path class="pm-path pm-red" stroke-width="6" d="M20 220 C300 220 590 220 880 220"/></svg>{_label(labels[0], 67, 5)}{_label(labels[1], 73, 82)}</div>'
    if motif == "atmospheric_globe":
        photons = "".join(f'<span class="pm-photon pm-beat" style="left:{46+i*8}%;top:{38+(i%3)*16}%;animation-delay:-{i*.45:.2f}s"></span>' for i in range(6))
        return f'<div class="premium-stage"><div class="pm-sun pm-beat" style="left:5%;top:12%"></div><div class="pm-beam pm-beat" style="left:12%;top:31%;width:48%;background:#fff2b0;color:#fff2b0;transform:rotate(18deg)"></div>{photons}<svg class="pm-beat" style="position:absolute;left:38%;top:12%;width:54%;height:70%" viewBox="0 0 900 430"><path class="pm-path pm-blue pm-atmo-ray" stroke-width="7" d="M30 245 C260 210 470 80 835 36"/><path class="pm-path pm-blue pm-atmo-ray" stroke-width="7" d="M30 245 C280 250 530 220 870 170"/><path class="pm-path pm-blue pm-atmo-ray" stroke-width="7" d="M30 245 C250 300 460 385 820 402"/></svg><div class="pm-atmosphere pm-beat"></div><div class="pm-globe pm-beat"></div><div class="pm-observer pm-beat" style="right:8%;bottom:4%"></div>{_label(labels[0], 78, 8)}</div>'
    if motif == "horizon_path":
        return f'<div class="premium-stage" style="background:linear-gradient(180deg,rgba(25,18,45,.1),rgba(255,108,64,.34));border-radius:50% 50% 0 0"><div class="pm-sun pm-beat" style="left:2%;bottom:4%;width:190px;height:190px"></div><div class="pm-horizon"></div><svg class="pm-beat" style="position:absolute;left:10%;top:12%;width:82%;height:78%" viewBox="0 0 1200 420"><path class="pm-path pm-red" stroke-width="12" d="M0 315 C300 80 780 55 1190 335"/></svg><div class="pm-observer pm-beat" style="right:5%;bottom:4%"></div>{_label(labels[0], 38, 35)}{_label(labels[1], 72, 12)}</div>'
    if motif in {"split_synthesis", "field_comparison"}:
        particles = "".join(f'<span class="pm-cool-particle" style="left:{18+i*11}%;top:{36+(i%3)*13}%"></span>' for i in range(6))
        return f'<div class="premium-stage"><div class="pm-split"><div class="pm-side cool pm-beat"><h3>{html.escape(labels[0])}</h3>{particles}<div class="pm-flow-line" style="left:12%;top:50%;width:72%"></div><p>{html.escape(labels[2])}</p></div><div class="pm-equals pm-beat">同一条<br/>科学规律</div><div class="pm-side warm pm-beat"><h3>{html.escape(labels[1])}</h3><div class="pm-warm-core"></div><div class="pm-flow-line" style="left:12%;top:50%;width:72%;background:linear-gradient(90deg,#ffd36a,#ff765a)"></div><p>{html.escape(labels[3])}</p></div></div></div>'
    if motif == "cell_network":
        cells = "".join(f'<span class="pm-cell pm-beat" style="left:{7+(i%4)*24}%;top:{8+(i//4)*48}%;animation-delay:-{i*.6:.2f}s"></span>' for i in range(8))
        return f'<div class="premium-stage">{cells}<svg class="pm-beat" style="position:absolute;inset:0;width:100%;height:100%" viewBox="0 0 1000 500"><path class="pm-path pm-blue" stroke-width="5" d="M110 100 C280 40 360 185 505 130 S740 40 890 115 M110 375 C275 430 360 285 505 350 S740 440 890 360"/></svg>{_label(labels[0], 42, 40)}</div>'
    if motif in {"orbital_system", "layered_scale"}:
        layers = "".join(f'<div class="pm-layer pm-beat" style="top:{8+i*7}%;width:{72-i*13}%;height:{88-i*14}%;animation-delay:-{i*.65:.2f}s"></div>' for i in range(4))
        nodes = "".join(f'<div class="pm-node pm-beat" style="left:{12+i*24}%;top:{24+(i%2)*38}%"></div>' for i in range(4))
        return f'<div class="premium-stage">{layers}{nodes}{_label(labels[0], 42, 42)}{_label(labels[1], 72, 18)}{_label(labels[2], 15, 72)}</div>'
    if motif in {"timeline_curve", "flow_machine"}:
        nodes = "".join(f'<div class="pm-node pm-beat" style="left:{8+i*27}%;top:{68-i*14}%"></div>{_label(labels[i], 5+i*27, 82-i*14)}' for i in range(4))
        return f'<div class="premium-stage"><svg class="pm-beat" style="position:absolute;inset:0;width:100%;height:100%" viewBox="0 0 1000 500"><path class="pm-path pm-blue" stroke-width="9" d="M35 380 C250 350 310 275 470 260 S730 140 960 90"/></svg>{nodes}</div>'
    if motif == "data_landscape":
        bars = "".join(f'<div class="pm-data-bar pm-beat" style="left:{12+i*18}%;height:{160+i*55}px;animation-delay:-{i*.4:.2f}s"></div>{_label(labels[i], 9+i*18, 8)}' for i in range(4))
        return f'<div class="premium-stage">{bars}</div>'
    return ""


def _labels(scene: dict[str, Any]) -> list[str]:
    values = list(scene.get("labels") or []) + list(scene.get("steps") or []) + list(scene.get("chips") or [])
    clean: list[str] = []
    for value in values:
        text = str(value).strip()[:10]
        if text and text not in clean:
            clean.append(text)
    while len(clean) < 4:
        clean.append(str(scene.get("headline") or "科学关系")[:10])
    return clean[:4]


def _label(text: str, left: int, top: int) -> str:
    return f'<div class="pm-label pm-beat" style="left:{left}%;top:{top}%">{html.escape(text)}</div>'
