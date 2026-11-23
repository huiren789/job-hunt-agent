# -*- coding: utf-8 -*-
"""拒因数据箱：只存真样本，逐字原话，可统计。

对应 docs/04：
- 只存 GENUINE 反馈；客套/通知/含糊一律不进
- 归因值统一用 8 类短名
- 没有样本时，改进计划必须明确拒绝生成
"""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .feedback import FeedbackKind, is_genuine_feedback
from .attribution import Attribution, classify_attribution


@dataclass
class Sample:
    """一条真样本。字段对应 docs/04 的 scheme（简化版，去掉本地追踪列）。"""
    date: str
    company: str
    role: str
    platform: str
    raw_text: str                 # 对方原话，逐字保留
    attribution: str              # 8 类短名之一
    confidence: str               # high / medium
    improvement_hint: str = ""    # 对方的改进建议原话
    source_id: str = ""           # message_id 等，用于去重

    @classmethod
    def from_text(cls, text: str, *, company: str = "", role: str = "",
                  platform: str = "", source_id: str = "") -> "Sample | None":
        """从一段回复构造样本。非真反馈返回 None（不建空记录）。"""
        fb = is_genuine_feedback(text)
        if fb.kind != FeedbackKind.GENUINE:
            return None
        attr = classify_attribution(text)
        if not attr.usable:
            # 有理由词但归因置信度低 → 归"其他"也不硬套具体类；
            # docs/02 说拿不准归"其他"，这里保留样本但不给确定归因。
            label, conf = "其他", "low"
        else:
            label, conf = attr.label, attr.confidence
        return cls(
            date=datetime.now().strftime("%Y-%m-%d"),
            company=company,
            role=role,
            platform=platform,
            raw_text=text.strip(),
            attribution=label,
            confidence=conf,
            improvement_hint="；".join(fb.matched_improvement),
            source_id=source_id,
        )


class DataBox:
    """本地 JSON 样本库。线程不安全，单进程使用。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.samples: list[Sample] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for item in data.get("samples", []):
            try:
                self.samples.append(Sample(**item))
            except TypeError:
                continue  # 字段不匹配的老数据跳过，不污染

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"samples": [asdict(s) for s in self.samples]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, sample: Sample | None) -> bool:
        """加入样本。返回是否真的加入。重复 source_id 或原话去重。"""
        if sample is None:
            return False
        for s in self.samples:
            if sample.source_id and s.source_id == sample.source_id:
                return False
            if s.raw_text[:60] == sample.raw_text[:60]:
                return False
        self.samples.append(sample)
        return True

    def add_text(self, text: str, **kwargs) -> bool:
        """便捷方法：一段文本→判真→入库。客套直接返回 False。"""
        return self.add(Sample.from_text(text, **kwargs))

    def stats(self) -> dict[str, int]:
        """归因分布统计（只统计 usable 的样本，'其他'单列）。"""
        out: dict[str, int] = {}
        for s in self.samples:
            out[s.attribution] = out.get(s.attribution, 0) + 1
        return dict(sorted(out.items(), key=lambda x: -x[1]))

    def has_samples(self) -> bool:
        return len(self.samples) > 0
