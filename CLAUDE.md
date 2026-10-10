# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

本仓库的注释、文档、验证输出全部使用中文，沿用这一约定。

**先读 [README.md](README.md)。** 它是本项目的权威设计文档：产物构成、构建管线、
每一条关键决策及其踩坑过程、六层验证清单、与原页面的已知差异，都在那里，且都有实测数据支撑。
本文件不复述那些内容，只记录**动手改代码之前必须知道的约束**，以及 README 里没有的操作细节。

## 项目一句话

把 typeui.sh 上 Charm 设计系统的四个预览页复刻成一个零外部依赖、双击即用的单文件 HTML
（`charm-preview.html`）。复刻本身只有两个源文件：[_build_charm.py](_build_charm.py)
（构建，~1700 行）与 [_verify_charm.mjs](_verify_charm.mjs)（验证，129 项）。
在它之外还有一条**试验台支线**（只作用于 zh 那五个产物，绝不回流复刻层）：
[_make_cjk_fonts.py](_make_cjk_fonts.py) 造字体包，[_theme_dark.py](_theme_dark.py) 深色层、
[_theme_console.py](_theme_console.py) 皮肤层、[_theme_brand.py](_theme_brand.py) 品牌层、[_ds_zh.py](_ds_zh.py) 设计层、
[_localize_zh.py](_localize_zh.py) 内容层，由 [_build_zh.py](_build_zh.py) 编排。
其余全是输入（保存件、字体 JSON、`ref/` 参考图）或产物（`charm-*.html`、`_shot_*.png`）。

## 常用命令

```bash
python3 _build_charm.py                    # 合并版 → charm-preview.html
python3 _build_charm.py --only=<slug>      # 单页版（components → charm-components.html，其余 charm-single-<slug>.html）
python3 _build_charm.py --all              # 合并版 + 四个单页版（像素回归的前置条件）
python3 _build_charm.py --fonts=cjk        # 中文字体版 → charm-preview-cjk.html（72.8 MB）
python3 _build_charm.py --fonts=cjk-gb     # GB2312 子集版 → charm-preview-cjk-gb.html
python3 _make_cjk_fonts.py [--gb2312]      # 重建字体包（全量约 2 分钟，子集约 45 秒）
python3 _make_cjk_fonts.py --export        # 包里的更纱黑体 → SarasaMonoSC-Woff2/ 独立文件
python3 _build_zh.py                       # 设计层+内容层 → charm-preview-cjk-gb-zh.html
python3 _build_zh.py --dark                # 深色层+设计层+内容层 → charm-preview-cjk-gb-zh-dark.html
python3 _build_zh.py --console             # 深色层+皮肤层+设计层+内容层 → charm-preview-cjk-gb-zh-console.html
python3 _build_zh.py --sim                 # 品牌层+设计层+内容层 → charm-preview-cjk-gb-zh-sim.html（蓝色品牌）
python3 _build_zh.py --sim --dark          # 深色层+品牌层深色段+设计层+内容层 → charm-preview-cjk-gb-zh-sim-dark.html
python3 _pack_sim.py                       # 上两者 → handoff/charm-sim-theme/ + .zip（交付给业务网页实现者）
python3 _audit_contrast.py                 # 深色产物逐元素渲染对比度审计（直接调本机 Chrome），退化即 exit 1

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

**设计上的改动不要动 `_build_charm.py`。** 那五个复刻产物的价值在于「与原站一致」这一
可验证的性质（像素回归、逐字节比对都以此为前提），设计试验混进去就全废了。分层是：
`_build_charm.py` 复刻层 → `_theme_dark.py` 深色层（`--dark` / `--console`）→
`_theme_console.py` 皮肤层（仅 `--console`）／`_theme_brand.py` 品牌层（仅 `--sim`，可叠 `--dark`）→
`_ds_zh.py` 设计层 → `_localize_zh.py` 内容层 → `_build_zh.py` 编排，**设计/内容/深色/皮肤/
品牌层只作用于 `charm-preview-cjk-gb-zh.html` 与其深色版、控制台皮肤版、工程蓝版及其深色版**
这五个试验台产物。
加设计改动 = 往 `_ds_zh.py` 的 `build_layers()` 加一个带命中数断言的 `Patch`；加文案 = 往
`_localize_zh.py` 的 `TABLE` 加一条（命中数要照产物数出来，别估）。深色配色改动 = 改
`_theme_dark.py` 的 `EXPECTED` 定稿表与对应映射表——推导复算断言（≤1/255）与多座面审计
（墨与状态字在 `INK_SEATS` / `STRONG_SEATS` 的每一种面上都不低于明亮版，封顶 `LC_CAP`，且至少
一面取等）会强制新值仍从明亮版按规则推得出来；改完必须重跑 `python3 _build_zh.py` 并与
改前产物 `cmp`，证明明亮路径逐字节不变，**再跑 `python3 _audit_contrast.py`**——令牌层的审计
看不见「文字实际坐在哪种底上」，tooltip 白字配近白底、卡片上的字变暗这类问题都是渲染审计
抓出来的。品牌前景（拿 Lc 换彩度）是唯一约定例外；文字一律不准用基色（基色恒等只给按钮面与图形）。

**皮肤层改动改 `_theme_console.py` 的 `EXPECTED_CONSOLE` 与三张映射表**（`ROOT_MAP` /
`RADIUS_MAP` / `SHADOW_MAP`）。它不重推导，只把深色层已审计的关系整体再锚定一次：面/线/
抬升平移到 `PAGE` 锚点、彩度归零，墨按深色层的多座面规则在冷面上重解；`verify_derivation()` 会强制
新值仍从这两条规则推得出来（≤1/255），外加冷度（C<0.002）、多座面审计、序关系、
保留族交叉审计与「输出值不与任何一版值域相交」。它的边界是**令牌 + 令牌在 body 里的
镜像**：改了中性色或圆角令牌，components 页那 8 个色块对与 7 个圆角演示块必须同步改
（`CHIP_MIRROR` / `RADIUS_MAP`），否则色板对自己撒谎。圆角演示块按令牌名锚整个单元，
绝不按值替换——`r-xs` 的旧值 `4px` 恰是 `r-xl` 的新值。改完同样要 `cmp` 证明明亮与
`--dark` 两条路径逐字节不变，并核对 `CENSUS_TOTAL/ADHOC` 这两个钉死值。

**品牌层改动改 `_theme_brand.py` 的 `ANCHOR` 与 `EXPECTED_SIM`。** `ANCHOR`（`#1a66ff`）是
设计指定的主色、钉死不推（取 DevTools 计算值，别从 Mac 截图读像素——截图带显示器 ICC 会偏）；其余七档从珊瑚红色阶按职能重推（≤1/255）：按钮面白字 Lc 整体平移到
锚点、前景在 page 上等 Lc、浅色调保 L 与绝对 C，彩度按珊瑚各档对 brand 的比例换算到锚点。
审计是求解 6 对 |Δ|≤0.5、按钮四档白字 Lc 严格递增（`.btn--primary` 渐变不倒挂）、派生 4 对
不退化、色相偏离按 ab 平面距离 ≤0.002、状态三族色相 ≥90°、图表 `--teal` `--purple` ΔE_OK ≥0.15。
换锚点后这些断言会逐条告诉你新色能不能用，别为了过构建去改阈值。info 族在设计层之后并入品牌
色阶（`apply_post`），所以**改 `INFO_HUES` 会同时牵动品牌层**（并入命中数与档位断言）。
`--sim --dark` 不改深色层：深色层按珊瑚跑完，`apply_dark` 再用深色层抽出的 `dark_soft()` /
`dark_series()` / `BRAND_FG_LC` / `BRAND_FG_FLOOR` 把品牌族换成深色蓝（定稿表 `EXPECTED_SIM_DARK`）。
所以**改深色层这几条规则或常数会同时牵动蓝色深色版**，两个深色版都要重建核对。
`--sim` 不与 `--console` 叠加（皮肤层的品牌恒等断言按珊瑚写）。色域计算用
`_theme_dark.lch_cmax`，不另写一份。改完同样要 `cmp` 证明另外三个 zh 产物逐字节不变。

**交付包由 `_pack_sim.py` 生成，`handoff/` 不入库、不要手改。** 改了品牌层、深色层或模版内容后
要重新打包。说明正文在 `_pack_sim_guide.html`，占位 `{{…}}` 由脚本填；令牌用途写在
`COLOR_GROUPS` / `OTHER_GROUPS`，与真实令牌双向断言——新增或删除令牌必须同步改说明，否则打包失败。
组件摘录按选择器取模版原文（`EXCERPTS`），顶层必须恰好一条。说明末尾的组件样例是组件页的
原样搬运（声明式影子 DOM，明暗各一份）：DOM/样式/脚本都从模版取，断言 8 分区 38 块、样式在
`SHELL_MARK` 处截断后不再有 `.ds` 规则、组件页脚本只用替身提供的三个 `document` 接口——组件页
加了新分区、或脚本用了别的 `document` 接口，打包会失败，要同步改 `_pack_sim.py`。已发布的说明
页面用 `handoff/_page/style-guide.html` 重新发布到同一地址。

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
