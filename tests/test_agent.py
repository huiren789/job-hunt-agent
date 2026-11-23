# -*- coding: utf-8 -*-
"""核心模块单元测试。用 unittest 标准库，零额外依赖。

跑法：python -m unittest discover -s tests -v
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from agent.feedback import is_genuine_feedback, FeedbackKind
from agent.attribution import classify_attribution, ATTRIBUTIONS
from agent.databox import DataBox, Sample
from agent.planner import generate_plan
from agent.dashboard import render_html


class TestFeedbackFilter(unittest.TestCase):
    def test_courtesy_not_genuine(self):
        for text in ["感谢投递，祝顺利", "岗位已招满，本次招聘结束",
                     "此邮件为系统自动发送，请勿回复", "已收到，请耐心等待"]:
            with self.subTest(text=text):
                self.assertEqual(is_genuine_feedback(text).kind,
                                 FeedbackKind.NON_GENUINE, text)

    def test_specific_is_genuine(self):
        for text in ["因为岗位需要C++经验，您技术栈不符，很遗憾",
                     "您缺少独立项目经验，如果做过完整项目会更好",
                     "专业不符，我们需要计算机相关专业"]:
            with self.subTest(text=text):
                self.assertEqual(is_genuine_feedback(text).kind,
                                 FeedbackKind.GENUINE, text)

    def test_courtesy_plus_specific_is_genuine(self):
        # 客套开头但带具体理由 → 真反馈（docs/04）
        r = is_genuine_feedback("感谢投递，因为缺 Java 经验，很遗憾")
        self.assertEqual(r.kind, FeedbackKind.GENUINE)

    def test_too_short_unknown(self):
        self.assertEqual(is_genuine_feedback("hi").kind, FeedbackKind.UNKNOWN)


class TestAttribution(unittest.TestCase):
    def test_labels_are_eight_short_names(self):
        self.assertEqual(len(ATTRIBUTIONS), 8)
        self.assertIn("技术栈不符", ATTRIBUTIONS)
        self.assertIn("无反馈", ATTRIBUTIONS)

    def test_classify_tech_stack(self):
        r = classify_attribution("因为岗位需要C++经验，您技术栈不符，很遗憾")
        self.assertEqual(r.label, "技术栈不符")
        self.assertIn(r.confidence, ("high", "medium"))
        self.assertTrue(r.usable)

    def test_classify_experience(self):
        r = classify_attribution("您缺少独立项目经验，建议补一个完整项目")
        self.assertEqual(r.label, "经验不足")
        # 命中词多少决定 high/medium；两者都可入库，不硬卡某一档
        self.assertIn(r.confidence, ("high", "medium"))
        self.assertTrue(r.usable)

    def test_no_signal_is_other(self):
        r = classify_attribution("随便一句话没有理由")
        self.assertEqual(r.label, "其他")
        self.assertFalse(r.usable)

    def test_deterministic(self):
        # 同一条反馈多次分类结果一致（统计口径必须稳定）
        text = "专业不符，我们需要计算机相关专业"
        rs = [classify_attribution(text) for _ in range(5)]
        self.assertEqual(len({(r.label, r.confidence) for r in rs}), 1)


class TestDataBox(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.path)  # 让 DataBox 从空开始
        self.box = DataBox(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_rejects_courtesy(self):
        self.assertFalse(self.box.add_text("感谢投递，祝顺利"))
        self.assertEqual(len(self.box.samples), 0)

    def test_accepts_genuine(self):
        self.assertTrue(self.box.add_text("因为技术栈不符，需要Java经验", company="X"))
        self.assertEqual(len(self.box.samples), 1)
        self.assertEqual(self.box.samples[0].company, "X")

    def test_dedup_by_text(self):
        t = "因为技术栈不符，需要Java经验"
        self.assertTrue(self.box.add_text(t))
        self.assertFalse(self.box.add_text(t))
        self.assertEqual(len(self.box.samples), 1)

    def test_dedup_by_source_id(self):
        self.assertTrue(self.box.add_text("因为技术栈不符", source_id="msg_1"))
        self.assertFalse(self.box.add_text("因为经验不足", source_id="msg_1"))

    def test_persistence(self):
        self.box.add_text("因为技术栈不符，需要Java经验")
        self.box.save()
        box2 = DataBox(self.path)
        self.assertEqual(len(box2.samples), 1)

    def test_stats(self):
        self.box.add_text("因为技术栈不符，需要Java经验")
        self.box.add_text("专业不符，需要计算机专业")
        s = self.box.stats()
        self.assertIn("技术栈不符", s)
        self.assertEqual(sum(s.values()), 2)


class TestPlanner(unittest.TestCase):
    def test_no_samples_refuses(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(path)
        box = DataBox(path)
        self.assertIsNone(generate_plan(box))
        self.assertIn("没有真样本", render_html(generate_plan(box) or type(
            "P", (), {"empty": True, "generated_at": "", "sample_count": 0,
                      "suggestions": [], "direction_note": ""})()))

    def test_plan_priority_and_evidence(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(path)
        box = DataBox(path)
        for t in ["因为需要C++经验，技术栈不符", "技术栈不匹配，主要用Java",
                  "岗位要用Go，技术栈不符", "您缺少项目经验"]:
            box.add_text(t)
        plan = generate_plan(box)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.sample_count, 4)
        self.assertEqual(plan.suggestions[0].attribution, "技术栈不符")
        self.assertIn("P1", plan.suggestions[0].priority)
        self.assertTrue(all(s.evidence for s in plan.suggestions))

    def test_html_has_sections(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(path)
        box = DataBox(path)
        box.add_text("因为需要C++经验，技术栈不符")
        h = render_html(generate_plan(box))
        for section in ["归因分布", "分档建议", "岗位方向校准", "不构成"]:
            self.assertIn(section, h)


if __name__ == "__main__":
    unittest.main()
