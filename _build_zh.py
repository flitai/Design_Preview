# -*- coding: utf-8 -*-
"""编排 `charm-preview-cjk-gb-zh.html`：复刻产物 → 设计系统层 → 内容层。

分层与各自的职责
----------------
    _build_charm.py   复刻层   四页 → 五个产物，忠实复刻，**不含任何设计改动**
    _ds_zh.py         设计层   令牌 / 色板 / 组件（只作用于 zh 产物）
    _localize_zh.py   内容层   文案（只作用于 zh 产物）
    _build_zh.py      编排     本文件

为什么设计改动不进复刻层：那五个产物的价值在于「与原站一致」这一可验证的性质
——像素回归、逐字节比对都以此为前提。设计上的试验一旦混进去，这些性质就全废了。
所以 zh 这一个产物承担试验台的角色，改动都落在设计层与内容层。

顺序是「设计层先、内容层后」：设计层加进来的色块标签（info / warning-soft 等）
是设计令牌名，本就该保持英文，不该被内容层翻译。

运行（需要先有 charm-preview-cjk-gb.html）：
    python3 _build_charm.py --fonts=cjk-gb
    python3 _build_zh.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import _ds_zh
import _localize_zh

HERE = Path(__file__).resolve().parent
SRC = HERE / "charm-preview-cjk-gb.html"
DST = HERE / "charm-preview-cjk-gb-zh.html"


def need(cond, msg):
    if not cond:
        sys.exit(f"[编排失败] {msg}")


def main():
    need(SRC.exists(),
         f"缺少 {SRC.name}（先跑 python3 _build_charm.py --fonts=cjk-gb）")
    src = SRC.read_text(encoding="utf-8")

    out = _ds_zh.apply(src)
    out, hits = _localize_zh.apply(out)

    # 自包含检查：两层都不该引入任何外部引用（与复刻层的 final_checks 同一套判据）
    probe = re.sub(r"<!--.*?-->", "", out, flags=re.S)
    need(not re.search(r'\ssrc\s*=\s*["\'](?!data:)', probe), "出现了外部 src=")
    need(not re.search(r"<link\b", probe), "出现了 <link>")
    need(not re.search(r'url\(\s*(?!["\']?data:)(?!#)', probe), "CSS 里出现了非 data: 的 url()")
    need(not re.search(r'href\s*=\s*["\'](?!#)', probe), "出现了非页内锚点 href")
    ids = re.findall(r'(?<![-\w])id="([^"]*)"', probe)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    need(not dup, f"id 重复：{dup[:8]}")
    need(len(out) > len(src) - 4096, "产物意外缩水，某一层可能吃掉了内容")

    DST.write_text(out, encoding="utf-8")
    print(f"已生成 {DST.name}（{len(out.encode()) / 1048576:.1f} MB）")
    print(f"  {_ds_zh.summary()}")
    print(f"  {_localize_zh.summary(hits)}")


if __name__ == "__main__":
    main()
