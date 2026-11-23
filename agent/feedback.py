# -*- coding: utf-8 -*-
"""真反馈 vs 客套判定。

原则（docs/04）：宁可漏存，不可脑补。
客套婉拒、系统通知、含糊回复一律判为 NON_GENUINE；
只有指出具体不足或给改进方向，才判为 GENUINE。

判定是规则驱动的，不调用 LLM——这类判断需要稳定可复现，不适合交给概率模型。
"""
from dataclasses import dataclass
from enum import Enum


class FeedbackKind(str, Enum):
    GENUINE = "genuine"        # 具体理由/改进方向 → 入数据箱
    NON_GENUINE = "non_genuine"  # 客套/系统/含糊 → 只记日志
    UNKNOWN = "unknown"        # 太短或拿不准 → 归其他，不入库


# 客套话：命中这些且没有具体理由词，直接判非真反馈
COURTESY_MARKERS = [
    "感谢投递", "感谢您的投递", "感谢参与", "感谢关注",
    "已收到", "我们会尽快", "请耐心等待", "祝顺利", "祝好",
    "岗位已招满", "岗位招满", "本次招聘已结束", "名额已满",
    "此邮件为系统自动发送", "请勿回复", "no-reply", "自动回复",
    "we appreciate", "thank you for your interest", "best regards",
    "we have reviewed", "will be in touch", "position has been filled",
]

# 具体理由词：命中这些才可能是真反馈
SPECIFIC_MARKERS = [
    "因为", "原因", "主要", "不足", "欠缺", "缺少", "缺乏", "需要", "建议",
    "如果会", "如果能", "希望有", "要求", "匹配", "不符", "不符合",
    "经验", "项目", "技术栈", "专业", "年级", "学历", "到岗", "时间",
    "薪资", "沟通", "表达",
    "lack", "missing", "require", "need", "suggest", "because", "reason",
    "experience", "skill", "background", "availability", "salary",
]
# 注意：招满/关闭/暂停不在此表——它们是状态通知（docs/04 明确不入库），
# 只在 COURTESY_MARKERS 里出现。避免"岗位招满"被当成能力反馈误存。

# 改进方向词：出现这些是强真反馈信号
IMPROVEMENT_MARKERS = [
    "建议补", "建议学", "如果会", "如果能", "下次", "未来", "可以补充",
    "would be better", "suggest", "recommend", "consider",
]


@dataclass
class FeedbackResult:
    kind: FeedbackKind
    reason: str
    matched_specific: list[str]
    matched_improvement: list[str]


def is_genuine_feedback(text: str | None) -> FeedbackResult:
    """判断一段对方回复是否是真反馈。

    规则：
    1. 空或过短（<6 字）→ UNKNOWN
    2. 命中改进方向词 → GENUINE（最强信号）
    3. 命中具体理由词 ≥1 且（无客套词 或 客套词只是礼貌开头）→ GENUINE
    4. 只命中客套词、无任何具体词 → NON_GENUINE
    5. 都没有 → UNKNOWN

    注意：客套 + 具体理由同时出现时判 GENUINE。
    例如「感谢投递，因为岗位要求 C++ 经验，很遗憾」是真反馈。
    """
    t = (text or "").strip()
    if len(t) < 6:
        return FeedbackResult(FeedbackKind.UNKNOWN, "文本过短", [], [])

    low = t.lower()
    specific = [m for m in SPECIFIC_MARKERS if m.lower() in low]
    improvement = [m for m in IMPROVEMENT_MARKERS if m.lower() in low]
    courtesy = [m for m in COURTESY_MARKERS if m.lower() in low]

    if improvement:
        return FeedbackResult(
            FeedbackKind.GENUINE,
            "包含改进方向",
            specific, improvement,
        )
    if specific:
        # 有具体理由词——即便带客套也算真反馈（如"感谢投递，因缺X…"）
        return FeedbackResult(
            FeedbackKind.GENUINE,
            "包含具体理由词",
            specific, improvement,
        )
    if courtesy:
        return FeedbackResult(
            FeedbackKind.NON_GENUINE,
            "仅客套/通知，无具体理由",
            specific, improvement,
        )
    return FeedbackResult(
        FeedbackKind.UNKNOWN,
        "无明确信号，归其他",
        specific, improvement,
    )
