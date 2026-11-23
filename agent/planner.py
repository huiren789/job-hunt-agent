# -*- coding: utf-8 -*-
"""改进计划生成：读真样本 → 归因聚合 → 三维度建议 → 优先级。

对应 docs/05：
- 没有真样本 → 拒绝生成，不编造
- 按归因次数排 P1/P2/P3
- 每条建议能指回具体样本，不凭空发明
- 不承诺"补了就能过"
"""
from dataclasses import dataclass
from collections import defaultdict

from .databox import DataBox, Sample

# 每个归因对应的「该补什么」——只写行动方向，不承诺结果
_ADVICE: dict[str, dict[str, str]] = {
    "技术栈不符": {
        "skill": "针对高频点名的技术栈做一个可展示的小项目，写清用了什么、解决了什么。",
        "resume": "把项目里用到的技术栈明确写出来，别只写「熟悉」。",
    },
    "经验不足": {
        "skill": "补一个从需求到上线的完整小项目，能讲清每一步的决策。",
        "resume": "项目经历写结果和数字，不只写「参与了」。",
    },
    "专业口径": {
        "skill": "用作品证明能力，弥补专业表述上的口径差。",
        "resume": "简历开头直接写技术证据，把专业放在教育背景里。",
    },
    "到岗时间": {
        "skill": "——",
        "resume": "投递前先确认时间口径，不匹配就别投；话术里主动说明可到岗时间。",
    },
    "薪资": {
        "skill": "——",
        "resume": "先问清预算范围再谈，别在前期把薪资当主旋律。",
    },
    "沟通表达": {
        "skill": "练把项目讲清楚：做了什么、为什么这么做、结果如何。",
        "resume": "——",
    },
    "岗位关闭": {
        "skill": "——",
        "resume": "岗位状态类反馈不反映能力，不用据此调整简历或技能。",
    },
    "无反馈": {
        "skill": "——",
        "resume": "超过 7 天无回音可发一次简短跟进，别反复追问。",
    },
    "其他": {
        "skill": "样本理由不明确，先补问原因再定动作。",
        "resume": "——",
    },
}

_PRIORITY_LABEL = {1: "P1（高频，优先做）", 2: "P2（次高频）", 3: "P3（单次，观察）"}


@dataclass
class Suggestion:
    priority: str
    attribution: str
    count: int
    skill_action: str
    resume_action: str
    evidence: list[str]   # 支撑该建议的原话摘录


@dataclass
class Plan:
    generated_at: str
    sample_count: int
    suggestions: list[Suggestion]
    direction_note: str

    @property
    def empty(self) -> bool:
        return self.sample_count == 0


def generate_plan(box: DataBox) -> Plan | None:
    """生成改进计划。没有真样本返回 None（调用方据此拒绝生成）。"""
    if not box.has_samples():
        return None

    grouped: dict[str, list[Sample]] = defaultdict(list)
    for s in box.samples:
        grouped[s.attribution].append(s)

    # 按次数排序；次数相同按 ATTRIBUTIONS 固定顺序，保证可复现
    from .attribution import ATTRIBUTIONS
    order = {name: i for i, name in enumerate(ATTRIBUTIONS)}
    ranked = sorted(grouped.items(), key=lambda kv: (-len(kv[1]), order.get(kv[0], 99)))

    suggestions = []
    for i, (attr, samples) in enumerate(ranked):
        pr = 1 if len(samples) >= 3 else (2 if len(samples) == 2 else 3)
        advice = _ADVICE.get(attr, _ADVICE["其他"])
        evidence = [s.raw_text[:70] for s in samples[:3]]
        suggestions.append(Suggestion(
            priority=_PRIORITY_LABEL[pr],
            attribution=attr,
            count=len(samples),
            skill_action=advice["skill"],
            resume_action=advice["resume"],
            evidence=evidence,
        ))

    # 维度三：岗位方向校准——基于被拒最多的归因给方向性提示
    top = suggestions[0]
    direction_note = (
        f"本期被点名最多的是「{top.attribution}」（{top.count} 次）。"
        "先看维度一和维度二是否针对这一类；若多次集中在同一类，"
        "再考虑这类岗位是不是当前阶段的主投方向。"
    )

    from datetime import datetime
    return Plan(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        sample_count=len(box.samples),
        suggestions=suggestions,
        direction_note=direction_note,
    )
