# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

本仓库的注释、文档、验证输出全部使用中文，沿用这一约定。

**先读 [README.md](README.md)。** 它是本项目的权威设计文档：产物构成、构建管线、
每一条关键决策及其踩坑过程、六层验证清单、与原页面的已知差异，都在那里，且都有实测数据支撑。
本文件不复述那些内容，只记录**动手改代码之前必须知道的约束**，以及 README 里没有的操作细节。

## 项目一句话

把 typeui.sh 上 Charm 设计系统的四个预览页复刻成一个零外部依赖、双击即用的单文件 HTML
（`charm-preview.html`）。源文件只有两个：[_build_charm.py](_build_charm.py)（构建，~1700 行）
与 [_verify_charm.mjs](_verify_charm.mjs)（验证，129 项）。其余全是输入（保存件、字体 JSON）
或产物（`charm-*.html`、`_shot_*.png`）。

## 常用命令

```bash
python3 _build_charm.py                    # 合并版 → charm-preview.html
python3 _build_charm.py --only=<slug>      # 单页版（components → charm-components.html，其余 charm-single-<slug>.html）
python3 _build_charm.py --all              # 合并版 + 四个单页版（像素回归的前置条件）
python3 _build_charm.py --fonts=cjk        # 中文字体版 → charm-preview-cjk.html（72.8 MB）
python3 _build_charm.py --fonts=cjk-gb     # GB2312 子集版 → charm-preview-cjk-gb.html
python3 _make_cjk_fonts.py [--gb2312]      # 重建字体包（全量约 2 分钟，子集约 45 秒）
python3 _make_cjk_fonts.py --export        # 包里的更纱黑体 → SarasaMonoSC-Woff2/ 独立文件

NODE_PATH=<装了 puppeteer-core 的 node_modules> node _verify_charm.mjs
node _verify_charm.mjs --no-visual         # 跳过 Phase 5，不需要单页产物
```

slug 只有 `marketing` `application` `ecommerce` `components` 四个。

关于跑这两个脚本的实测情况：

- 构建是**确定性**的——同输入逐字节同输出，全量 `--all` 约 0.2 秒。改完随手重跑没有成本，
  `git diff` 式的字节比对可以直接当回归信号用。
- **当前环境未安装 puppeteer-core**（全局与各级 `node_modules` 都没有），验证脚本跑不起来。
  它刻意用 `createRequire` 认 `NODE_PATH`，因为本目录是自包含可分发单元、不放 `node_modules`。
  Chrome 路径在脚本里是硬编码常量 `CHROME`，换机器要改。
- 验证器**没有单条用例的过滤开关**，`--no-visual` 是唯一的裁剪方式。失败 exit 1；
  像素不一致会导出 `_diff_<slug>_{merged,single}.png`；每次运行都会覆盖 `_shot_<slug>.png`。
- 改默认 tab 只改 `_build_charm.py` 的 `DEFAULT_SLUG`，验证脚本从产物的 `data-default` 读。

## 动手之前：容易破坏的不变量

**产物不要手改。** `charm-*.html` 全是生成的，改构建器再重跑。

**断言不要为了让构建通过而放宽。** `need()` 是唯一失败出口，`CleanRule` 带命中数闭区间、
`Restore` 锚点必须精确命中 N 次、`restore_menus` 双向断言（没有触发器落空、也没有模板闲置）、
`expect_class_counts` 机械计数、`check_icons` 逐字节自证、`assemble` 校验「有样式却无 DOM 的
`ds__*`」。断言失败几乎总是意味着保存件变了或规则表写漏了——去查真实原因，别改阈值。

**补回来的文案一律从 chunk 正则提取，绝不手抄**（`js_array` / 各页的 `extract_*`）。

**不引入 HTML parser**，坚持字节级 regex：重新序列化会破坏 `<clipPath>` `<linearGradient>`
这类 SVG 标签名的大小写，引用静默失效。

**CSS 合并顺序不可颠倒**：`@font-face → 4309 令牌+reset → 1mf3 白名单切片 → 1l8ijtal3t07p 全量 → 各页 patch → 外壳补丁`。

**切换器必须保持 `position:fixed` 浮层、绝不占布局。** 这不是审美选择：共享 CSS 里有
21 个宽度断点、0 个高度断点，一旦占位就要在四页里逐处补偿（README「关键决策」有完整推演）。
它同时是像素回归能做到零容差的前提。

**外壳的深色玻璃样式故意用字面值而非 Charm 令牌**——它是 typeui.sh 的站点 chrome、不是被预览的
组件，必须一眼可辨。CSS 注释里写明了，不要"修正"它。同理外壳按钮用自己的 `.pv-switch__btn`
而非页面的 `.segmented__btn`，否则 `SHARED_JS` 的规则会顺带命中外壳。

**每个页面根节点外面那层 `.pv` 不能去掉**：四个根的 display 各异（`.page` / `.appshell` 是 flex），
直接挂 `[hidden]` 会被自身 display 覆盖；它还是每页独立的滚动容器与滚动位置记忆的载体。

**下拉面板是触发器的紧邻兄弟，不用 portal。** 滚动发生在 `.pv` / `.appmain` 上，所以重定位
监听必须 `capture:true`——漏了这个，面板在滚动时不跟随。

**交互状态只存在 DOM 上**（`[hidden]` / `aria-selected` / `dataset.*` / `:checked`），
不设第二份 JS 状态。表格选中态直接从 DOM 数 `:checked`，promote 开关是纯 CSS。

**路由只认 `#p=<slug>`**：四页里有 13 个形如 `#components` 的页内死锚点，裸 slug 会撞名。

**换字体走 `FontPack`，不要去改页面 CSS。** 四页的字体栈形如
`var(--font-inter), "Inter", …`，内嵌字体占第一顺位令牌，所以一套字体 = 三个令牌值
（`sans` / `display` / `mono`）+ 一个字体包 JSON。加新字体包就往 `FONT_PACKS` 里加一项，
`suffix` 决定产物文件名后缀（空串即默认产物）。**改完必须回归验证拉丁版逐字节不变**——
`--fonts` 的全部意义就是不影响既有交付物。

## 单页版是对照组，不是交付物

`charm-single-*.html` / `charm-components.html` 只为验证器 Phase 5 存在：合并版逐页与单页版
要求**逐像素相等**（0 差异、无掩码、无容差）。改了任何可能影响布局的东西，跑 `--all` 再跑
验证——这是"合并没有误伤页面内容"的最强证据。

## 文档同步

README.md 是交付文档，「关键决策」一节记录的是**为什么这么做**及其实测依据。
如果改动推翻了其中任何一条决策，或新增了同量级的决策，要一并更新 README，别让它与代码脱节。
产物顶部的 `<!-- -->` 说明块由 `render_note()` 生成，「已知差异」清单也在那里，同样要同步。

已知的小陈旧：`render_note()` 里两处「生成：design skill/_build_charm.py」还是旧目录名
（现在是 `Design_Preview`），它会写进每个产物顶部的说明块，改动需重跑 `--all`。
`NotoSansCJK-Woff2/` 当前未被构建器或验证器引用。
