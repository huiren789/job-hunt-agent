# -*- coding: utf-8 -*-
"""生成 HTML 改进计划看板。单文件、无外部依赖、可离线打开。

对应 templates/改进计划模板.md 的五个章节。
所有数据来自真样本，不编造、不承诺结果。
"""
import html
from pathlib import Path

from .planner import Plan


def _esc(s: str) -> str:
    return html.escape(s or "")


def render_html(plan: Plan) -> str:
    """把 Plan 渲染成完整 HTML 字符串。"""
    if plan.empty:
        return """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>改进计划</title></head><body><h1>改进计划</h1>
<p>数据箱还没有真样本，生成不了有意义的改进计划。先攒带具体理由的反馈。</p>
</body></html>"""

    # 归因分布条形图（纯 CSS，宽度按次数比例）
    max_count = max(s.count for s in plan.suggestions)
    bars = "\n".join(
        f'<div class="bar-row"><span class="bar-label">{_esc(s.attribution)}</span>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{s.count / max_count * 100:.0f}%"></div></div>'
        f'<span class="bar-count">{s.count}</span></div>'
        for s in plan.suggestions
    )

    rows = []
    for s in plan.suggestions:
        ev = "".join(f'<li>{_esc(e)}</li>' for e in s.evidence)
        rows.append(f"""
        <section class="card">
          <div class="card-head">
            <span class="prio">{_esc(s.priority)}</span>
            <h3>{_esc(s.attribution)} <small>× {s.count}</small></h3>
          </div>
          <div class="two-col">
            <div><h4>技能补强</h4><p>{_esc(s.skill_action)}</p></div>
            <div><h4>简历 / 话术</h4><p>{_esc(s.resume_action)}</p></div>
          </div>
          <details><summary>依据原话（{len(s.evidence)} 条）</summary><ul>{ev}</ul></details>
        </section>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>改进计划 {_esc(plan.generated_at)}</title>
<style>
  :root {{ --fg:#1a1a1a; --bg:#fafafa; --muted:#666; --line:#e5e5e5; --accent:#2c6fd6; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Microsoft YaHei",sans-serif; color:var(--fg);
         background:var(--bg); margin:0; padding:32px 20px; line-height:1.6; }}
  main {{ max-width:860px; margin:0 auto; }}
  h1 {{ font-size:26px; margin:0 0 6px; }}
  h3 {{ margin:0; font-size:18px; }}
  h4 {{ margin:0 0 4px; font-size:14px; color:var(--muted); }}
  .meta {{ color:var(--muted); font-size:14px; margin-bottom:24px; }}
  .panel {{ background:#fff; border:1px solid var(--line); border-radius:10px;
           padding:20px 24px; margin-bottom:20px; }}
  .bar-row {{ display:flex; align-items:center; gap:10px; margin:8px 0; }}
  .bar-label {{ width:100px; font-size:14px; flex-shrink:0; }}
  .bar-track {{ flex:1; background:#f0f0f0; border-radius:4px; height:14px; overflow:hidden; }}
  .bar-fill {{ height:100%; background:var(--accent); }}
  .bar-count {{ width:24px; text-align:right; font-size:14px; }}
  .card {{ background:#fff; border:1px solid var(--line); border-radius:10px;
          padding:18px 24px; margin-bottom:14px; }}
  .card-head {{ display:flex; align-items:center; gap:12px; margin-bottom:12px; }}
  small {{ color:var(--muted); font-weight:normal; }}
  .prio {{ background:#eef4ff; color:var(--accent); font-size:12px;
          padding:3px 10px; border-radius:12px; white-space:nowrap; }}
  .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
  .two-col p {{ margin:0; font-size:14px; }}
  details {{ margin-top:12px; font-size:13px; color:var(--muted); }}
  summary {{ cursor:pointer; }}
  ul {{ margin:8px 0 0; padding-left:20px; }}
  .note {{ font-size:14px; color:var(--muted); }}
  @media(max-width:600px) {{ .two-col {{ grid-template-columns:1fr; }} }}
</style></head><body><main>
  <h1>改进计划</h1>
  <div class="meta">生成于 {_esc(plan.generated_at)} · 基于 {plan.sample_count} 条真反馈
    · 只统计带具体理由的回复</div>

  <section class="panel">
    <h3>归因分布</h3>
    {bars}
  </section>

  <h3 style="margin:24px 0 12px">分档建议</h3>
  {''.join(rows)}

  <section class="panel">
    <h3>岗位方向校准</h3>
    <p class="note">{_esc(plan.direction_note)}</p>
  </section>

  <p class="note">说明：本看板只反映已收到的真反馈，不构成"补了就能过"的承诺。
  建议是否采纳由你自己决定。</p>
</main></body></html>"""


def write_dashboard(plan: Plan, path: str | Path) -> Path:
    """生成看板文件并返回路径。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_html(plan), encoding="utf-8")
    return p
