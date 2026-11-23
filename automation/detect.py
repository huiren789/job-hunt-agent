# -*- coding: utf-8 -*-
"""招聘站反馈只读检测器（通用版）
==================================
用你自己的浏览器登录态，只读地抓取各平台消息/投递状态，
按关键词判定「想聊 / 过了 / 拒了」，结果写进本地 outbox.json。

硬边界：
  - 只读：不投递、不发消息、不点任何提交类按钮。
  - 不硬闯风控：检测到验证/滑块立即跳过该平台。
  - 平台专属信息全部来自 config.py，本文件不含任何站点 URL 或选择器。

用法：
  python detect.py --login <platform>   # 首次登录某平台（独立窗口，扫码后自动保存）
  python detect.py                       # 日常检测所有已登录平台
"""
import json
import random
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright

import config


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(config.LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def judge(text):
    """按固定顺序判定：想聊 → 过了 → 拒了。"""
    t = (text or "").lower()
    if any(k.lower() in t for k in config.WANT_CHAT_WORDS):
        return "想聊"
    if any(k.lower() in t for k in config.PASS_WORDS):
        return "过了"
    if any(k.lower() in t for k in config.REJECT_WORDS):
        return "拒了"
    return None


def is_blocked(page):
    """检测风控/验证页：命中就跳过，不硬闯。"""
    try:
        body = page.locator("body").inner_text(timeout=4000)
    except Exception:
        return False
    hit = [w for w in config.BLOCK_WORDS if w.lower() in body.lower()]
    if hit:
        log(f"  🛑 检测到风控/验证（{hit[0]}）——跳过本平台，不硬闯")
        return True
    return False


def read_cards(page, selectors):
    """只读抓取消息卡片文本；返回去重后的文本列表。"""
    out = []
    for sel in selectors:
        try:
            loc = page.locator(sel)
            n = min(loc.count(), config.MAX_MESSAGES_PER_RUN)
            for i in range(n):
                try:
                    t = loc.nth(i).inner_text(timeout=1500).strip()
                except Exception:
                    continue
                if t and t[:60] not in [x[:60] for x in out]:
                    out.append(t.replace("\n", " "))
            if out:
                break  # 命中一组选择器即可
        except Exception:
            continue
    return out


def login_mode(name):
    cfg = config.PLATFORMS.get(name)
    if not cfg:
        log(f"未知平台：{name}；可选 {list(config.PLATFORMS)}")
        return
    log(f"=== 登录 {name}：{cfg['url']}（独立窗口，{config.LOGIN_WAIT_SECONDS}秒后自动保存）===")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(cfg["profile"]),
            channel=config.BROWSER_CHANNEL,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg["url"], timeout=30000, wait_until="domcontentloaded")
        log("  请在窗口里手动登录，登录后无需操作，脚本自动保存退出。")
        try:
            page.wait_for_timeout(config.LOGIN_WAIT_SECONDS * 1000)
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
    log(f"=== {name} 登录态已保存 ===")


def detect_one(name, cfg, seen):
    if not cfg["profile"].exists():
        log(f"--- {name}：未登录（无登录态目录），跳过。请先 --login {name}")
        return []
    log(f"--- {name}：{cfg['url']}")
    results = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(cfg["profile"]),
            channel=config.BROWSER_CHANNEL,
            headless=config.HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(cfg["url"], timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(random.randint(2000, 4000))
            if is_blocked(page):
                return results
            # 若配置了状态 tab，逐个切到有实质反馈的 tab 再读
            tabs_sel = cfg.get("status_tabs_selector")
            feedback_tabs = cfg.get("feedback_tabs")
            groups = []
            if tabs_sel and feedback_tabs:
                tabs = page.locator(tabs_sel)
                for i in range(tabs.count()):
                    label = tabs.nth(i).inner_text().strip()
                    if label in feedback_tabs:
                        try:
                            tabs.nth(i).click(timeout=5000)
                            page.wait_for_timeout(1500)
                            groups.append((label, read_cards(page, cfg["message_selectors"])))
                        except Exception as e:
                            log(f"  ⚠️ 切 tab[{label}] 失败：{e}")
            else:
                groups.append(("", read_cards(page, cfg["message_selectors"])))
            for label, cards in groups:
                for raw in cards:
                    if raw[:60] in seen:
                        continue
                    j = judge(raw)
                    if j:
                        results.append({
                            "platform": name,
                            "tab": label,
                            "judge": j,
                            "text": raw[:300],
                            "detected_at": datetime.now().isoformat(timespec="seconds"),
                        })
                        seen.add(raw[:60])
                    # 只读，不做投递类动作
        except Exception as e:
            log(f"⚠️ {name} 读取失败：{e}（可能未登录或页面结构变了）")
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    return results


def main():
    if "--login" in sys.argv:
        i = sys.argv.index("--login")
        name = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        if name:
            login_mode(name)
        else:
            for n in config.PLATFORMS:
                login_mode(n)
        return
    log("=== 本地反馈检测启动（只读，不投递不发消息）===")
    outbox = {"items": [], "last_run": ""}
    if config.OUTBOX.exists():
        try:
            outbox = json.loads(config.OUTBOX.read_text(encoding="utf-8"))
        except Exception:
            pass
    seen = {x.get("text", "")[:60] for x in outbox.get("items", [])}
    results = []
    for name, cfg in config.PLATFORMS.items():
        results += detect_one(name, cfg, seen)
    outbox["items"] = (outbox.get("items", []) + results)[-500:]
    outbox["last_run"] = datetime.now().isoformat(timespec="seconds")
    config.OUTBOX.write_text(json.dumps(outbox, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"=== 完成：新判定 {len(results)} 条 → {config.OUTBOX} ===")
    for r in results:
        log(f"  - {r['platform']} / {r['judge']} / {r['text'][:50]}")


if __name__ == "__main__":
    main()
