# -*- coding: utf-8 -*-
"""命令行入口：把数据箱 → 改进计划 → HTML 看板串起来。

用法：
  python -m agent.cli add "反馈原话" --company 公司 --role 岗位
  python -m agent.cli add-texts examples/sample_feedback.json
  python -m agent.cli report --out 改进计划.html
  python -m agent.cli stats
  python -m agent.cli check "一条反馈"     # 只看判定，不入库

所有路径参数都是相对/绝对均可；默认数据箱写在当前目录 data/databox.json。
"""
import argparse
import json
import sys
from pathlib import Path

from .databox import DataBox
from .feedback import is_genuine_feedback
from .attribution import classify_attribution
from .planner import generate_plan
from .dashboard import write_dashboard

DEFAULT_BOX = Path("data/databox.json")


def _open_box(path: Path) -> DataBox:
    return DataBox(path)


def cmd_check(args):
    fb = is_genuine_feedback(args.text)
    attr = classify_attribution(args.text)
    print(f"判定: {fb.kind.value}")
    print(f"理由: {fb.reason}")
    print(f"归因: {attr.label} ({attr.confidence})")
    if fb.matched_specific:
        print(f"命中具体词: {', '.join(fb.matched_specific[:5])}")
    if fb.matched_improvement:
        print(f"命中改进词: {', '.join(fb.matched_improvement[:5])}")


def cmd_add(args):
    box = _open_box(args.box)
    ok = box.add_text(
        args.text,
        company=args.company or "",
        role=args.role or "",
        platform=args.platform or "",
    )
    if ok:
        box.save()
        print(f"已入库 → {args.box}")
    else:
        print("未入库：客套/含糊/重复（按 docs/04 规则）")


def cmd_add_texts(args):
    """批量导入 JSON 文件。格式见 examples/sample_feedback.json。"""
    src = Path(args.file)
    if not src.exists():
        print(f"文件不存在: {src}")
        return
    try:
        items = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        return
    box = _open_box(args.box)
    added = 0
    for item in items:
        if box.add_text(
            item.get("text", ""),
            company=item.get("company", ""),
            role=item.get("role", ""),
            platform=item.get("platform", ""),
        ):
            added += 1
    box.save()
    print(f"导入完成：新增 {added} 条，当前共 {len(box.samples)} 条 → {args.box}")


def cmd_report(args):
    box = _open_box(args.box)
    plan = generate_plan(box)
    if plan is None:
        print("数据箱还没有真样本，生成不了有意义的改进计划。先攒带具体理由的反馈。")
        return
    out = write_dashboard(plan, args.out)
    print(f"改进计划已生成: {out}（基于 {plan.sample_count} 条真样本）")


def cmd_stats(args):
    box = _open_box(args.box)
    print(f"样本总数: {len(box.samples)}")
    for k, v in box.stats().items():
        print(f"  {k}: {v}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="job-hunt-agent",
        description="反馈归因 → 数据箱 → 改进计划（只写真样本）",
    )
    parser.add_argument("--box", type=Path, default=DEFAULT_BOX,
                        help=f"数据箱路径（默认 {DEFAULT_BOX}）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="只判定一条反馈，不入库")
    p.add_argument("text")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("add", help="判断并加入一条反馈")
    p.add_argument("text")
    p.add_argument("--company", default="")
    p.add_argument("--role", default="")
    p.add_argument("--platform", default="")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("add-texts", help="从 JSON 批量导入")
    p.add_argument("file")
    p.set_defaults(func=cmd_add_texts)

    p = sub.add_parser("stats", help="查看归因分布")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("report", help="生成 HTML 改进计划")
    p.add_argument("--out", type=Path, default=Path("改进计划.html"))
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
