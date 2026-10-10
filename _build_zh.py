# -*- coding: utf-8 -*-
"""编排 zh 试验台产物：复刻产物 → （深色层 →（皮肤层））或（品牌层）→ 设计层 → （各层后段）→ 内容层。

分层与各自的职责
----------------
    _build_charm.py   复刻层   四页 → 五个产物，忠实复刻，**不含任何设计改动**
    _theme_dark.py    深色层   只作用于 --dark / --console 产物；主段在设计层之前，后段在之后
    _theme_console.py 皮肤层   只作用于 --console 产物；夹在深色层与设计层之间
    _theme_brand.py   品牌层   只作用于 --sim 产物；主段在设计层之前，后段在之后
    _ds_zh.py         设计层   令牌 / 色板 / 组件（只作用于 zh 产物）
    _localize_zh.py   内容层   文案（只作用于 zh 产物）
    _build_zh.py      编排     本文件

为什么设计改动不进复刻层：那五个产物的价值在于「与原站一致」这一可验证的性质
——像素回归、逐字节比对都以此为前提。设计上的试验一旦混进去，这些性质就全废了。
所以 zh 产物承担试验台的角色，改动都落在深色层、设计层与内容层。

深色层为什么拆两段：设计层的 token_value() 与 text_color_census() 都是
「首次声明胜」，主段先把 :root 改成深色，设计层读到的天然是深色值，状态色板
与文字色板自动自证；而设计层注入的 info 族来自其模块内硬编码的明亮常量，
只能在它之后由后段（apply_post）收拾。顺序是「设计层先、内容层后」不变：
设计层加进来的色块标签是设计令牌名，本就该保持英文，不该被内容层翻译。

皮肤层为什么夹在中间：同一条「首次声明胜」的理由——它把中性令牌再锚定成冷黑，
必须赶在设计层读值之前，色板才自证冷值。深色层主段的断言在皮肤层之前已全部
执行完毕，后段的 info 计数由设计层在皮肤层之后注入，两头都不受影响。
`--console` 因此蕴含 `--dark`（皮肤层换的是深色壳的中性族），两者不能同给。

品牌层与深色层同构：主段赶在设计层读值之前换掉品牌令牌，文字色板自证蓝值；
设计层注入的 info 族与新品牌蓝只差 7°，由后段（apply_post）并入品牌色阶。
`--sim --dark` 出蓝色品牌的深色版：深色层照旧按珊瑚红跑完（它的定稿值与断言都钉着
珊瑚原值，一个字节不动），品牌层深色段（apply_dark）随后把品牌族换成「深色层同一套
规则作用于明亮蓝」的结果——与皮肤层同一槽位，同一条「首次声明胜」的理由。
`--sim` 不与 `--console` 叠加：皮肤层的品牌恒等断言按珊瑚红写，蓝色控制台版要另做。

一次运行只出一个产物：_ds_zh 把 census 挂在函数属性上（apply.census），
同进程连出两个会让 summary() 只报最后一次。

运行（需要先有 charm-preview-cjk-gb.html）：
    python3 _build_charm.py --fonts=cjk-gb
    python3 _build_zh.py            # 明亮版 → charm-preview-cjk-gb-zh.html
    python3 _build_zh.py --dark     # 深色版 → charm-preview-cjk-gb-zh-dark.html
    python3 _build_zh.py --console  # 控制台皮肤 → charm-preview-cjk-gb-zh-console.html
    python3 _build_zh.py --sim      # 工程蓝品牌 → charm-preview-cjk-gb-zh-sim.html
    python3 _build_zh.py --sim --dark  # 工程蓝深色版 → charm-preview-cjk-gb-zh-sim-dark.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import _ds_zh
import _localize_zh
import _theme_brand
import _theme_console
import _theme_dark

HERE = Path(__file__).resolve().parent
SRC = HERE / "charm-preview-cjk-gb.html"
DST_LIGHT = HERE / "charm-preview-cjk-gb-zh.html"
DST_DARK = HERE / "charm-preview-cjk-gb-zh-dark.html"
DST_CONSOLE = HERE / "charm-preview-cjk-gb-zh-console.html"
DST_SIM = HERE / "charm-preview-cjk-gb-zh-sim.html"
DST_SIM_DARK = HERE / "charm-preview-cjk-gb-zh-sim-dark.html"


def need(cond, msg):
    if not cond:
        sys.exit(f"[编排失败] {msg}")


def main(argv=()):
    dark = "--dark" in argv
    console = "--console" in argv
    sim = "--sim" in argv
    unknown = [a for a in argv if a not in ("--dark", "--console", "--sim")]
    need(not unknown, f"不认识的参数：{unknown}（只支持 --dark / --console / --sim）")
    need(not (dark and console),
         "--dark 与 --console 不能同给：皮肤层换的就是深色壳的中性族，--console 已蕴含深色层")
    need(not (sim and console),
         "--sim 不与 --console 叠加：皮肤层的品牌恒等断言按珊瑚红写，蓝色控制台版要另做")
    need(SRC.exists(),
         f"缺少 {SRC.name}（先跑 python3 _build_charm.py --fonts=cjk-gb）")
    src = SRC.read_text(encoding="utf-8")

    if dark or console:
        out = _theme_dark.apply(src)
        if console:
            out = _theme_console.apply(out)
        if sim:
            out = _theme_brand.apply_dark(out, src)
        out = _ds_zh.apply(out)
        if console:
            _theme_console.check_after_ds()
        out = _theme_dark.apply_post(out)
        if sim:
            out = _theme_brand.apply_post(out, dark=True)
    elif sim:
        out = _theme_brand.apply(src)
        out = _ds_zh.apply(out)
        out = _theme_brand.apply_post(out)
    else:
        out = _ds_zh.apply(src)
    out, hits = _localize_zh.apply(out)

    # 自包含检查：各层都不该引入任何外部引用（与复刻层的 final_checks 同一套判据）
    probe = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    need(not re.search(r'\ssrc\s*=\s*["\'](?!data:)', probe), "出现了外部 src=")
    need(not re.search(r"<link\b", probe), "出现了 <link>")
    need(not re.search(r'url\(\s*(?!["\']?data:)(?!#)', probe), "CSS 里出现了非 data: 的 url()")
    need(not re.search(r'href\s*=\s*["\'](?!#)', probe), "出现了非页内锚点 href")
    ids = re.findall(r'(?<![-\w])id="([^"]*)"', probe)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    need(not dup, f"id 重复：{dup[:8]}")
    need(len(out) > len(src) - 4096, "产物意外缩水，某一层可能吃掉了内容")

    dst = (DST_CONSOLE if console else DST_SIM_DARK if sim and dark else DST_DARK if dark
           else DST_SIM if sim else DST_LIGHT)
    dst.write_text(out, encoding="utf-8")
    print(f"已生成 {dst.name}（{len(out.encode()) / 1048576:.1f} MB）")
    if dark or console:
        print(f"  {_theme_dark.summary()}")
    if console:
        print(f"  {_theme_console.summary()}")
    if sim:
        print(f"  {_theme_brand.summary(dark=dark)}")
    print(f"  {_ds_zh.summary()}")
    print(f"  {_localize_zh.summary(hits)}")


if __name__ == "__main__":
    main(sys.argv[1:])
