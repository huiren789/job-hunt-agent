# -*- coding: utf-8 -*-
"""求职反馈分析模块。规则优先、可选 LLM 增强、离线可用。"""
from .feedback import is_genuine_feedback, FeedbackKind
from .attribution import classify_attribution, Attribution, ATTRIBUTIONS
from .databox import DataBox, Sample
from .planner import generate_plan, Plan, Suggestion
from .dashboard import render_html, write_dashboard

__all__ = [
    "is_genuine_feedback", "FeedbackKind",
    "classify_attribution", "Attribution", "ATTRIBUTIONS",
    "DataBox", "Sample",
    "generate_plan", "Plan", "Suggestion",
    "render_html", "write_dashboard",
]
