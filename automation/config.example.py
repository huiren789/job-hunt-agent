# -*- coding: utf-8 -*-
"""配置样例：复制本文件为 config.py 后，按你自己的平台和页面修改。

所有平台专属信息（URL / 选择器 / 关键词 / 路径）都在这里，脚本本身通用。
"""
from pathlib import Path

# 工作目录：本地数据都写这里，不要提交到 git
BASE = Path(__file__).resolve().parent.parent

# ===== 平台配置 =====
# 每个平台一个独立登录态目录（互不干扰），一个消息页 URL，一组消息卡片选择器。
# 选择器请打开你的消息页、用浏览器开发者工具确认后填写；可填多个候选，脚本依次尝试。
PLATFORMS = {
    "platform_a": {
        "url": "https://example.com/messages",          # 你的平台消息页
        "profile": BASE / "profile_platform_a",          # 独立登录态目录
        "message_selectors": [                            # 消息卡片选择器（按优先级）
            "[class*='chat-item']",
            "[class*='message-item']",
            ".message-list li",
        ],
        "mode": "messages",                               # messages=读消息卡片
    },
    "platform_b": {
        "url": "https://example.org/my/deliveries",
        "profile": BASE / "profile_platform_b",
        "message_selectors": [".delivery-item", "[class*='application-card']"],
        "mode": "messages",
        # 若你的平台是按状态 tab 分类的投递页，可开启下面两项：
        "status_tabs_selector": ".tab",                   # 状态 tab 的选择器
        "feedback_tabs": ["面试", "不合适", "录用"],       # 只处理这些有实质反馈的 tab
    },
}

# ===== 判定关键词 =====
# 判定顺序固定：想聊 → 过了 → 拒了（见 docs/02）。关键词按你的实际语境补充。
WANT_CHAT_WORDS = ["想聊聊", "想进一步聊", "再聊聊", "方便电话吗", "let's chat"]
PASS_WORDS = ["面试邀约", "邀请您参加面试", "进入下一轮", "interview invitation", "offer"]
REJECT_WORDS = ["不合适", "未通过", "感谢参与", "本次招聘", "not selected", "rejected"]

# 遇到这些词视为验证码/风控，脚本跳过该平台、不硬闯（保护账号）
BLOCK_WORDS = ["安全验证", "滑块", "拖动验证", "captcha", "点击按钮进行验证", "当前 ip"]

# ===== 浏览器 / 运行参数 =====
BROWSER_CHANNEL = "msedge"     # 用你本机已装的浏览器；改成 chrome 亦可
HEADLESS = False                # 首次登录必须 False；日常检测可 True（部分站点会反无头）
LOGIN_WAIT_SECONDS = 90         # 首次登录窗口保持多久后自动保存退出
DELAY_MIN, DELAY_MAX = 1, 3     # 读取每条消息后的随机延时（秒），放慢更像人
MAX_MESSAGES_PER_RUN = 50       # 单次最多读多少条

# ===== 输出文件（本地，勿提交） =====
OUTBOX = BASE / "outbox.json"
LOG = BASE / "run.log"
