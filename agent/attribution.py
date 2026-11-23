# -*- coding: utf-8 -*-
"""8 类归因分类：规则打分 + 置信度。可选 LLM 增强（默认关闭）。

对应 docs/04 的 8 类短名。分类结果给出置信度：
- high（≥2 分差或强关键词）：可直接入库
- medium（1 分差）：建议人工确认
- low（并列或全 0）：归"其他"，不硬套

LLM 是可选增强：只有在规则置信度 low 且用户显式配置时才调用，
避免在稳定判断上引入不确定性。
"""
from dataclasses import dataclass

# docs/04 定义的 8 类短名（顺序固定，统计时用）
ATTRIBUTIONS = [
    "技术栈不符", "经验不足", "专业口径", "到岗时间",
    "薪资", "沟通表达", "岗位关闭", "无反馈",
]

# 每类归因的强/弱关键词。强词 2 分，弱词 1 分。
_RULES: dict[str, tuple[list[str], list[str]]] = {
    "技术栈不符": (
        ["技术栈不符", "技术栈不匹配", "缺 c++", "缺 java", "需要 java", "需要 c++",
         "不用 python", "非 python", "skill mismatch", "tech stack"],
        ["技术", "框架", "语言", "工具", "stack", "framework"],
    ),
    "经验不足": (
        ["经验不足", "项目经验", "需要经验", "缺乏经验", "实习经验",
         "lack of experience", "more experience"],
        ["经验", "经历过", "做过", "independent project"],
    ),
    "专业口径": (
        ["专业不符", "专业不对口", "非计算机", "专业要求", "学历不符",
         "年级不符", "届别", "major requirement", "degree"],
        ["专业", "学历", "本科", "硕士", "年级", "major"],
    ),
    "到岗时间": (
        ["到岗时间", "到岗", "实习时长", "每周", "几天", "全职",
         "时间不匹配", "availability", "on-site"],
        ["时间", "长期", "短期", "六个月", "三个月"],
    ),
    "薪资": (
        ["薪资", "预算", "薪酬", "待遇", "salary", "budget", "compensation"],
        ["日薪", "月薪", "钱", "pay"],
    ),
    "沟通表达": (
        ["沟通", "表达", "表述", "面试表现", "communication", "articulate"],
        ["回答", "讲", "说", "present"],
    ),
    "岗位关闭": (
        ["岗位关闭", "岗位招满", "暂停招聘", "不再招", "名额已满",
         "position closed", "hiring freeze"],
        ["关闭", "招满", "暂停", "取消"],
    ),
    "无反馈": (
        ["无反馈", "超过七天", "没有回复", "暂无", "未回复"],
        ["无回音", "没回复", "沉默", "no response"],
    ),
}


@dataclass
class Attribution:
    label: str            # 8 类之一，或"其他"
    confidence: str       # high / medium / low
    scores: dict[str, int]
    evidence: list[str]   # 命中的关键词

    @property
    def usable(self) -> bool:
        """是否可直接写入数据箱。low 置信度不硬套。"""
        return self.confidence in ("high", "medium") and self.label != "其他"


def classify_attribution(text: str | None) -> Attribution:
    """规则打分分类。纯函数、离线、可复现。

    不使用 LLM：归因是统计口径，必须稳定；概率模型会让同一条反馈
    今天归"经验不足"明天归"技术栈不符"，统计就废了。
    """
    low = (text or "").lower()
    scores: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}

    for label, (strong, weak) in _RULES.items():
        s = 0
        hits = []
        for kw in strong:
            if kw.lower() in low:
                s += 2
                hits.append(kw)
        for kw in weak:
            if kw.lower() in low:
                s += 1
                hits.append(kw)
        if s > 0:
            scores[label] = s
            evidence[label] = hits

    if not scores:
        return Attribution("其他", "low", {}, [])

    ranked = sorted(scores.items(), key=lambda x: (-x[1], ATTRIBUTIONS.index(x[0])))
    top_label, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score >= 4 and top_score - second_score >= 2:
        conf = "high"
    elif top_score - second_score >= 1:
        conf = "medium"
    else:
        conf = "low"

    return Attribution(top_label, conf, scores, evidence.get(top_label, []))


def classify_with_llm_fallback(text: str, client=None, model: str = "") -> Attribution:
    """可选 LLM 增强：仅当规则判为 low 且传入 client 时调用。

    client 需兼容 OpenAI ChatCompletion 接口（chat.completions.create）。
    这里不 import 任何 SDK——用户自己注入，保持零重依赖。
    """
    rule_result = classify_attribution(text)
    if rule_result.confidence != "low" or client is None:
        return rule_result

    prompt = (
        "把下面这条招聘反馈归入且仅归入一类，只输出类名本身：\n"
        + "、".join(ATTRIBUTIONS) + "\n\n反馈：" + text
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
        )
        answer = resp.choices[0].message.content.strip()
        if answer in ATTRIBUTIONS:
            return Attribution(answer, "medium", rule_result.scores,
                               ["llm:" + answer])
    except Exception:
        pass
    return rule_result
