# -*- coding: utf-8 -*-
"""内容层：把 GB2312 子集版产物的文案换成中文。由 _build_zh.py 调用。

用途是**展示中文排版效果**，不是完整本地化：只替换四页里最能体现字体表现的那部分
——导航、大标题、正文段落、按钮、侧栏、下拉菜单项。刻意保留英文的有：色值
(#e4544b)、设计令牌名 (brand-soft)、文件名 (colors.md)、人名与品牌名，
它们正好把中英混排的效果一并展示出来。

三条约束，都写成了断言：

  1. **只动 `.pv` 面板内部**。底部悬浮切换器（Marketing / Application / …）留英文：
     它是 typeui.sh 的站点 chrome，不是被预览的设计系统，两者本就该分家。
  2. **每条替换的命中数必须精确**。表里的数字是照着产物数出来的，源产物一变就报错，
     不会静默漏译或错译。
  3. **译文用字必须落在 GB2312 内**。这一版内嵌的是 GB2312 子集字体，用了子集外的字
     会当场掉回系统字体——所以逐字校验，不合格就拒绝出文件。

只做文本节点替换（`>文案<`，容忍并保留首尾空白），不碰标签、class、属性与 JS。
已核实运行时 JS 不按文案匹配（无任何待译串以字符串字面量出现在 <script> 里），
因此交互不受影响。

本文件是**内容层**，由 _build_zh.py 编排调用，不单独运行：
    python3 _build_zh.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def need(cond, msg):
    if not cond:
        sys.exit(f"[本地化失败] {msg}")


def gb2312_charset() -> set:
    out = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                out.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return out


# (英文原文, 中文译文, 期望命中数) —— 命中数照着产物数出来，不是估的
TABLE = [
    ('Home', '首页', 7),
    ('Products', '产品', 4),
    ('Blog', '博客', 3),
    ('Contact', '联系我们', 5),
    ('Talk to sales', '联系销售', 1),
    ('Login', '登录', 3),
    ('Get started free', '免费开始使用', 1),
    ('Watch the tour', '观看产品演示', 1),
    ('Childcare software families genuinely love.', '让家长真心喜欢的托育管理系统。', 1),
    ('Enrollment, billing, attendance, and family updates in one friendly app.', '招生、账单、考勤与家园沟通，全在一个顺手的应用里。', 1),
    ('Family messaging just landed in Charm', '家园消息功能已在 Charm 上线', 1),
    ('Search families, invoices, staff', '搜索家庭、账单、员工', 1),
    ('Overview', '总览', 4),
    ('Families', '家庭', 3),
    ('Messages', '消息', 2),
    ('Billing', '账务', 7),
    ('Calendar', '日历', 2),
    ('Reports', '报表', 1),
    ('Director', '园长', 3),
    ('Good afternoon, Grace', '下午好，Grace', 2),
    ('Here is what happened across your centers this week.', '以下是本周各园区的情况汇总。', 2),
    ('Enrolled children', '在园幼儿', 1),
    ('Monthly revenue', '月度营收', 1),
    ('Attendance today', '今日出勤', 1),
    ('Weekly check-ins', '每周签到', 1),
    ('Children', '幼儿', 1),
    ('Staff', '教职工', 2),
    ('Recent activity', '近期动态', 1),
    ('View all', '查看全部', 1),
    ('Plan mix', '套餐构成', 1),
    ('Enroll', '招生', 1),
    ('Profile', '个人资料', 2),
    ('Settings', '设置', 4),
    ('Sign out', '退出登录', 2),
    ('Logout', '退出', 1),
    ('Enrolled', '已入园', 1),
    ('Waitlist', '候补名单', 1),
    ('Alumni', '已毕业', 1),
    ('Invoices', '发票', 1),
    ('Payouts', '结算', 1),
    ('Docs', '文档', 1),
    ('New in Charm', 'Charm 新功能', 1),
    ('Get the update', '立即更新', 1),
    ('Invite teammates', '邀请同事', 1),
    ('This week', '本周', 2),
    ('Revenue overview', '营收总览', 1),
    ('Across all centers, this year vs last', '全部园区，今年与去年对比', 1),
    ('Last 12 months', '近 12 个月', 1),
    ('Last 7 days', '近 7 天', 9),
    ('Last 30 days', '近 30 天', 7),
    ('Last 90 days', '近 90 天', 6),
    ('Custom period', '自定义区间', 6),
    ('Details', '详情', 1),
    ('Revenue details', '营收明细', 1),
    ('Monthly revenue across all centers, most recent first.', '全部园区的月度营收，按时间倒序排列。', 1),
    ('Month', '月份', 2),
    ('Marketplace', '商城', 2),
    ('Features', '特色', 4),
    ('Team', '团队', 3),
    ('Top categories', '热门分类', 1),
    ('View more categories', '查看更多分类', 1),
    ('Pre-order now', '立即预订', 2),
    ('Save $500 today on your new dream setup.', '今日下单，梦想装备立省 $500。', 1),
    ('Computers', '电脑', 2),
    ('Fashion', '服饰', 2),
    ('Electronics', '数码', 2),
    ('Gaming', '游戏', 2),
    ('Toys', '玩具', 2),
    ('Sport', '运动', 2),
    ('Grocery', '食品', 2),
    ('Health', '健康', 2),
    ('Auto', '汽车', 2),
    ('Computer &amp; Office', '电脑与办公', 1),
    ('Fashion &amp; Clothes', '服饰与鞋包', 1),
    ('Gaming &amp; Consoles', '游戏与主机', 1),
    ('TV &amp; Projectors', '电视与投影', 1),
    ('Collectibles &amp; Toys', '收藏与玩具', 1),
    ('Sports &amp; Outdoors', '运动与户外', 1),
    ('Food &amp; Grocery', '食品与生鲜', 1),
    ('Books', '图书', 3),
    ('Home Air Quality', '家用空气', 1),
    ('Photo &amp; Video', '影像与摄影', 1),
    ('The component library', '组件库', 1),
    ('The source of truth for every component shipped with Charm.', 'Charm 所交付的每一个组件，皆以此为准。', 1),
    ('Foundations', '基础', 2),
    ('Actions', '操作', 4),
    ('Forms', '表单', 2),
    ('Selection', '选择', 2),
    ('Feedback', '反馈', 2),
    ('Navigation', '导航', 2),
    ('Surfaces', '表面', 2),
    ('Overlays', '浮层', 2),
    ('Brand ramp', '品牌色阶', 1),
    ('Surfaces and lines', '表面与描边', 1),
    ('Help center', '帮助中心', 2),
    ('Help &amp; Terms', '帮助与条款', 1),
    ('Resources', '资源', 1),
    ('Company', '公司', 2),
    ('Pricing', '定价', 1),
    ('Careers', '招聘', 2),
    ('Security', '安全', 1),
    ('Status', '状态', 3),
    ('Revenue', '营收', 2),
    ('Enrollments', '招生数', 1),
    ('Avg. tuition', '平均学费', 1),
    ('Retention', '留存率', 1),
    ('This year', '今年', 2),
    ('Last year', '去年', 2),
    ('Today', '今日', 5),
    ('Components', '组件', 1),
    ('Help', '帮助', 1),
    ('+ New enrollment', '+ 新增入园', 1),
    ('Desktop', '桌面端', 1),
    ('Mobile', '移动端', 1),
    ('Family messaging just landed. Update to send photos and notes straight from the classroom.',
     '家园消息功能已上线，更新后即可直接从教室发送照片与文字。', 1),
    ("The tokens every component reads from: the brand ramp, the surfaces it sits on, "
     "the status hues, one type scale and the system's radii.",
     '每个组件都从这里取值：品牌色阶、所处的表面、状态色、一套字号梯度，以及系统圆角。', 1),
    ("Trade in any eligible device and get this week's member pricing on the whole desktop "
     "lineup, with free delivery and 30-day returns.",
     '任意符合条件的设备均可折抵，整条台式产品线本周会员价，包邮并支持 30 天退货。', 1),

    # 字号梯度：Heading scale（h1–h6）与 Body scale（body-lg/body/sm/xs）共 10 行同一句样例。
    # 换成中英混排——把拉丁词与数字夹在汉字中间，正是中西混排最吃功夫、
    # 也最能看出字体表现的情形（基线是否对齐、字重是否匹配、间距是否匀）。
    # 十行同串是刻意的：字号梯度的样例本就该逐级同文，只变尺寸。
    ('The system keeps its promises', '用 Charm 2.0 构建的设计系统言出必行', 10),
    ('Heading scale', '标题字号梯度', 1),
    ('Body scale', '正文字号梯度', 1),
    ('Status color means state, never decoration.', '状态色表示状态，绝不用于装饰。', 1),
    ('Status hues', '状态色', 1),
    ('Spacing', '间距', 1),
]

# 输入框的 placeholder 不是文本节点，单独走一张表。
# Northwind（人名）与 Small / Default / Large（尺寸演示）刻意留英文。
ATTRS = [
    ('Search families, invoices, staff', '搜索家庭、账单、员工', 1),
    ('Search for staff', '搜索员工', 1),
    ('Search', '搜索', 1),
    ('How did it go?', '体验如何？', 1),
]

NOTE_ANCHOR = "  需要 Chrome/Edge 119+"
NOTE = """  ⚠ 本文件是**中文文案示例**：在 charm-preview-cjk-gb.html 的基础上，把四页里
     {entries} 条文案换成了中文（共 {hits} 处替换），用来展示中文排版效果。
     色值、设计令牌名、文件名、人名刻意保留英文，一并展示中英混排。
     底部切换器保持英文——它是站点 chrome，不属于被预览的设计系统。
     译文用字全部落在 GB2312 子集内（构建时逐字校验过）。
     生成：_build_zh.py（复刻层 → 设计层 → 内容层），英文原版见 charm-preview-cjk-gb.html。

"""


def apply(html: str) -> tuple:
    """把文案换成中文。返回 (新 html, 替换处数)。

    只做文本节点与 placeholder 的替换，不碰标签、class、其它属性与 JS。
    已核实运行时 JS 不按文案匹配（无任何待译串以字符串字面量出现在 <script> 里）。
    """
    # 逐字校验译文都在 GB2312 内 —— 子集外的字会掉回系统字体
    gb = gb2312_charset()
    bad = {c for _, zh, _ in TABLE + ATTRS for c in zh if ord(c) > 0x7F and c not in gb}
    need(not bad, f"这些字不在 GB2312 子集内，会掉回系统字体：{''.join(sorted(bad))}")

    # 只动 .pv 面板内部：切换器在面板之前，保持英文（它是站点 chrome）
    i = html.index('<div class="pv" id="pv-')
    j = html.rindex("<script>")
    head, panels, tail = html[:i], html[i:j], html[j:]

    total = 0
    for en, zh, expect in TABLE:
        pat = r'(?<=>)(\s*)' + re.escape(en) + r'(\s*)(?=<)'
        panels, n = re.subn(pat, lambda m: m.group(1) + zh + m.group(2), panels)
        need(n == expect, f"[{en}] 命中 {n} 次，期望 {expect}")
        total += n

    for en, zh, expect in ATTRS:
        pat = r'placeholder="' + re.escape(en) + r'"'
        panels, n = re.subn(pat, f'placeholder="{zh}"', panels)
        need(n == expect, f"[placeholder {en}] 命中 {n} 次，期望 {expect}")
        total += n

    out = head + panels + tail
    out, n = re.subn(r'<title>([^<]*)</title>', r'<title>\1（中文文案示例）</title>', out, count=1)
    need(n == 1, "没找到 <title>")
    note = NOTE.format(entries=len(TABLE) + len(ATTRS), hits=total)
    out, n = re.subn(re.escape(NOTE_ANCHOR), note + NOTE_ANCHOR, out, count=1)
    need(n == 1, "没找到说明块的插入锚点")
    return out, total


def summary(hits: int) -> str:
    return (f"内容层：{len(TABLE)} 条文本 + {len(ATTRS)} 条 placeholder，"
            f"{hits} 处替换，译文用字全部在 GB2312 内")


if __name__ == "__main__":
    sys.exit("本文件是内容层，不单独运行。请跑：python3 _build_zh.py")
