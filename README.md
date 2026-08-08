# Charm 预览页复刻

把 typeui.sh 上 Charm 设计系统的四个预览页（Marketing / Application / E-commerce / Components）复刻成**一个零外部依赖、双击即用的单文件 HTML**，供离线查阅组件的真实做法、间距与状态——比翻模版 HTML 快。

**交付物就是一个文件**：`charm-preview.html`（710 KB）。字体、CSS、四页 DOM、交互 JS 全部内嵌，不依赖同目录任何东西，也不联网。拷走它一个即可，深链形如 `charm-preview.html#p=ecommerce`。

底部居中一个悬浮切换器四选一，默认打开 Marketing。

```
产物构成（710 KB）
  <style>    219 KB   ← 其中内嵌 woff2 约 131 KB（Inter / DM Sans / Fragment Mono 的 latin 子集）
  四页 DOM   472 KB   ← 543 个内联 svg、23 份下拉面板
  <script>    19 KB
```

---

## 目录里都有什么

| | 文件 | 说明 |
|---|---|---|
| **产物** | `charm-preview.html` | **唯一要拷走的东西**，四页合集 |
| | `charm-components.html` | 组件库页的单页版（上一轮的交付物），兼作像素基线 |
| | `charm-single-{marketing,application,ecommerce}.html` | 纯构建中间产物，只给像素回归当对照，`--all` 可随时重生 |
| | `charm-preview-cjk.html` | 中文字体版（72.8 MB），字体换成思源黑体 + 更纱黑体，其余完全相同 |
| | `charm-preview-cjk-gb.html` | 同上的 GB2312 常用字子集版（16.0 MB），生僻字回退系统字体 |
| | `_shot_*.png` | 每次跑验证都会覆盖的截图记录 |
| **工具** | `_build_charm.py` | 构建脚本，约 1700 行 |
| | `_verify_charm.mjs` | 验证脚本，129 项（含像素回归） |
| | `_make_cjk_fonts.py` | 生成中文字体包：收 Noto 的 woff2，把更纱黑体的 TTF 转成 woff2 |
| | `_charm_fonts.json` | 预先下载的 woff2（base64），构建时内嵌 |
| | `_charm_fonts_cjk.json` | 中文字体包（72 MB 全量 CJK），`_make_cjk_fonts.py` 产出 |
| | `_charm_fonts_cjk_gb.json` | 中文字体包（15 MB GB2312 子集），`--gb2312` 产出 |
| | `SarasaMonoSC-Woff2/` | 更纱黑体转换后的独立 woff2（全量，3 个字重），`--export` 产出，供别的项目引用 |
| **源** | `NotoSansCJK-Woff2/` + `SarasaMonoSC-TTF-1.0.36/` | 中文字体原件，只有重建字体包时才用到 |
| **源** | `Charm Design Skill File _ TypeUI*.html` + 四个 `..._files/` 目录 | 浏览器保存件，约 10 MB，**只有重建时才用到** |

---

## 源为什么不能直接用

保存件依赖 3 个外部 CSS 与 40 多个 Next.js chunk，字体指向已失效的外链，而且**它只是首屏静态快照**——modal / drawer / 下拉菜单 / FAQ 的后三个分类，这些 DOM 在文件里根本不存在（React 当时没渲染）。

## 构建管线

`_build_charm.py` 用一张 `PageSpec` 表描述四个页面，逐页跑同一条流水线：

```python
@dataclass(frozen=True)
class PageSpec:
    slug, label, title, src_dir, src_html, root_anchor, id_prefix
    clean:    tuple[CleanRule, ...]    # 带 [lo,hi] 命中数断言的正则替换
    restores: tuple[Restore, ...]      # 锚定插入缺失的隐藏态 DOM
    menus:    tuple[MenuSpec, ...]     # 按触发器判别式插回下拉面板
    patch_css, js                      # 该页专属的还原补丁与交互层
    inline_imgs, fix_recharts, extra_css
    expect_class_counts                # 机械预言机：class 出现次数必须完全一致
```

| | clean | restores | menus | 其它 |
|---|---|---|---|---|
| marketing | 3 | 2 | — | `inline_imgs`（11 个 `<img>` → data URI） |
| application | — | 4 | 10 模板 → 21 个触发器 | `fix_recharts` |
| ecommerce | 2 | 2 | 2 | |
| components | 1 | 6 | — | 独有 `1l8ijtal3t07p.css` 全量并入 |

七个步骤：**切正文 → 清洗外链 → 补回隐藏态 DOM → 插回下拉面板 → 内联图片 → 修 recharts 容器 → 逐 svg 给 id 加页前缀**，最后收 class 白名单、按原 `data-precedence` 顺序合并 CSS、拼进 `.pv` 外壳。

CSS 合并顺序不可颠倒：`@font-face(内嵌) → 4309 令牌+reset → 1mf3 四页并集白名单切片(61 KB) → 1l8ijtal3t07p 全量 → 外壳补丁`。（`.btn:focus-visible` 在前者、`.btn.is-focus` 在后者，颠倒会改变焦点表现。）

每一步都带 `need()` 断言：源页面若更新导致锚点失效，会立刻报错而不是静默产出坏页面。

---

## 关键决策（含踩过的坑）

**合并成一个文件而不是四个** —— 131 KB 的内嵌字体只需出现一次；四个独立文件要重复四次。

**切换器必须是 `position:fixed` 浮层，绝不能占布局。** 一旦占了，被挤掉的那一维就要在四页里逐处补偿：

- 占**顶部**（竖向）要改写 `.ds` / `.page` / `.appshell` 的 `100vh`、`.modal` 的 `max-height`，外加 8 个 fixed 浮层逐个让出 bar 高——这是第一版的做法，能跑但补丁很重。
- 占**侧边**（横向）严格更糟：共享 CSS 里有 **21 个宽度断点、0 个高度断点**。竖向缩 56px 谁都不影响，横向缩一截则让**每一个断点都与真实内容宽度错位**（1440 视口配 200px 栏 → 内容 1240px 却仍套用 `@media (min-width:1280px)` 的排版）。要修只能把 `@media` 全改 `@container`，等于重写 61 KB 第三方 CSS。
- 做成浮层后，外壳补丁只碰 `html/body` 与 `.pv*`，**一条原页面规则都不覆盖**，合并版与单页版因此能做到逐像素相等。

**贴底而非贴顶**也是量出来的——顶部那条正是四页各自安放常驻导航的地方（1440×900、滚到顶时）：

| 位置 | marketing | application | ecommerce | components |
|---|---|---|---|---|
| 顶部居中 | 盖住 `Contact` | 盖住搜索框 | **盖住语言选择 + 5 个主导航项** | 无 |
| 底部居中 | 无 | 无 | 无 | 无 |

原站选 `bottom-4 left-1/2` 多半就是这个缘故。切换器的深色玻璃样式也照搬原站——它是 **typeui.sh 的站点 chrome、不是 Charm 组件**，一眼可辨"这是外壳不是被预览的页面"，故意用字面值而非 Charm 令牌（CSS 注释里写明了，免得后人"修正"它）。

**必须给每个页面根节点包一层 `.pv`。** 四个根的 display 各异（`.page` / `.appshell` 是 flex），直接挂 `[hidden]` 会被自身的 display 覆盖；wrapper 还承担每页独立的滚动容器与滚动位置记忆。

**补回来的文案一律从 chunk 里正则提取，不手抄。** 40 条 FAQ、3 档定价、application 的 5 份列表、12 个月营收——写错一个词不会有任何东西报警，手抄是不可接受的风险。`expect_class_counts` 再从 DOM 侧兜一层机械计数。

**逐 `<svg>` 局部改 id，坚持字节级 regex，不引入 HTML parser。** parser 重新序列化会把 `<clippath>` / `<lineargradient>` 这类 SVG 标签名的大小写破坏，导致引用静默失效。实测四页的 `url(#x)` 引用全部落在定义它的那个 `<svg>` 内部（跨 svg 引用 = 0）、svg 无嵌套、引用形式只有 `fill="url(#x)"` 一种，所以局部改名即充分。

**下拉面板不用 portal**，作为触发器的紧邻兄弟内联——`position:fixed` 不受祖先影响（已核祖先链无 transform/filter/contain），随 `.pv[hidden]` 自动隐藏，还省掉 21 个 `aria-controls` id。注意滚动发生在 `.pv` / `.appmain` 上，重定位监听必须 `capture:true`。

**21 个触发器靠判别式匹配模板，不用序号。** 序号会随 DOM 微调而错位，且其中 10 个是同一模板在表格行里的复用。判别式取 `aria-label`（优先）或按钮纯文本，并双向断言：**没有触发器落空，也没有模板闲置**。

**图标生成器先自证。** archive / pencil / trash-2 / log-out 四个图标在快照里根本没出现过，只能从 chunk 的 `iconNode` 定义生成。为此先拿快照里**已渲染**的 6 个图标（user / settings / credit-card / eye / x / ellipsis）做**逐字节对照断言**，证明生成器与 React 的序列化完全一致，才敢用它去补那四个。

**表格选中态不存 Set，直接从 DOM 数 `:checked`** —— 没有第二份状态可失同步。promote 那一列的开关纯 CSS `:checked` 驱动，零 JS。

**recharts 的病灶不是 viewBox。** `<svg class="recharts-surface">` 本就带 `viewBox` + `width:100%`。真正的问题是 ResponsiveContainer 在服务端渲染出一个 `width:0;height:0;overflow:visible` 的中间层（子元素的 100% 于是等于 0），加上 `.recharts-wrapper` 被写死成快照当时的像素尺寸。两处都改成 100%，图表就跟着容器缩放，不用引入 recharts 运行时。

**路由只认 `#p=<slug>`。** 四页里有 13 个形如 `#components` / `#overview` 的页内死锚点，裸 slug 会与它们撞名；其余 hash 一律交给浏览器做页内跳转。`replaceState` 不污染后退栈。

**`.hero-pattern` / `.shero-pattern` 引用的 `hero-pattern-swirl.svg` 四目录皆无**，只删掉那一条 `background-image`，保留 opacity/mask。不自造替代纹理——那是设计资产，猜错比没有更糟。

**换字体只改三个令牌值，一条页面 CSS 规则都不碰。** 四页的字体栈形如
`var(--font-inter), "Inter", ui-sans-serif, …`——内嵌字体占的永远是第一顺位那个令牌，
所以 `FontPack` 只需给出 `--font-inter` / `--font-display` / `--font-fragment-mono` 三个值。
`--fonts=cjk` 因此不产生任何布局风险，拉丁版产物也逐字节不变（改完实测过）。

**等宽不跟着换 Noto Sans SC，单独用更纱黑体。** Noto Sans SC 的拉丁是比例字体，
拿它当等宽会让 `.ds__file` / `.stat-tile__value` 这些位置失去列对齐。更纱黑体
（Sarasa Mono SC）把汉字宽度做成拉丁的整二倍，中英混排也不破列——`_make_cjk_fonts.py`
里有断言实测这一点（拉丁 500 / 汉字 1000 units），不成立就拒绝出包。

**中文版出两档，覆盖面与体积自己挑。** 全量 CJK 版 72.8 MB，任何汉字都能显示；
GB2312 子集版 16.0 MB，收录 6763 常用汉字 + 682 符号，生僻字/繁体/假名回退系统字体。
两版的英文渲染实测等价（逐像素比对：最大单通道色差 1/255，落在 6 个色块的圆角上，
按本项目像素回归自己的判据 ΣRGB>6 即为零差异）。

子集的字符集不手抄「常用字表」，而是**枚举 GB2312 的全部合法双字节码位**解出来
（必然 7445 个，不多不少），再并上拉丁与标点各区，最后并上**拉丁版产物里出现过的
每一个字符**——最后这一项是硬要求：四页正文是英文，漏掉任何一个在用字符都会让产物
当场退化成系统字体。实测这样兜回来 3 个字符。

两版都只内嵌页面真正用到的 8 个字面（Noto 5 + 更纱 3），并在 `@font-face` 上直接声明
字重区间把匹配钉死：Noto 无 600/800、更纱无 500，全靠区间落到真实字面，不触发合成粗体。
子集化之后会**重新量一遍等宽指标**（拉丁 500 / 汉字 1000），subset 若动了 advance width
就地报错——这条断言保证列对齐不会在子集化这一步悄悄丢掉。

**puppeteer-core 装到本目录之外**（本目录是自包含的可分发单元，不该出现 `node_modules`），验证脚本用 `createRequire` 认 `NODE_PATH`。

---

## 与原页面的已知差异

1. 标题字体用 **DM Sans** —— 原设计首选商业字体 Circular Std，规范本身即以 DM Sans 作为其免费替代。
2. modal / drawer / 下拉菜单等浮层在快照里并不存在（React 未渲染），按各页的编译产物 chunk 逐字还原；原实现靠卸载节点隐藏，本复刻改用 `[hidden]` 切换。
3. 交互由原生 JS 重写，状态只存放在 DOM 属性上。
4. 每个 `<svg>` 内部的 id 都加了页前缀。**⚠ 这顺带修掉了原页面的一个 bug**：E-commerce 页的 `chBg1`/`chBg7` 各被定义了两次，导致其中 2 个商品图取到了别人的渐变。改名后各自独立，因此这两张图与原站有可见色差——是修正，不是回归。
5. `hero-pattern-swirl.svg` 不在保存件里（见上）。
6. application 的 recharts 容器已修复为跟随容器缩放（见上）。

需要 Chrome/Edge 119+、Safari 16.4+、Firefox 128+（用到 `color-mix()`、`rgb(from …)` 与 `:has()`）。

---

## 验证

129 项，六层：

| Phase | 项数 | 内容 |
|---|---|---|
| 0 静态检查 | 9 | 无外部 `src=`/`<link>`/非 data 的 `url(`/非页内 `href`；全文档 id 无重复；svg 引用全带页前缀；体积区间 |
| 1 加载与资源 | 13 | 零外部网络请求、无 pageerror/console error、三款字体 `fonts.check` 全过、令牌可解析、`color-mix()` 生效、切换器是 fixed 且不占布局 |
| 2 切换与页间隔离 | 37 | 初始恰一页可见；逐个切换后其余三页 `offsetParent===null`；隐藏页的 fixed 浮层不可见、元素不可 Tab 聚焦；**切换器不与各页顶部导航相交**；三档视口无横向溢出；滚动位置保留；深链与未知 hash；跨页链接；方向键 |
| 3 每页结构 | 27 | components 8 section / 37 块；marketing FAQ 4×10 + 11 张图；application 21 面板 / 8 图表 / 10 行；ecommerce 16 商品卡；svg 引用目标合法 |
| 4 交互矩阵 | 39 | 四页各自的交互 + Dropdown 定位四项（贴合、右对齐、贴底翻转、滚动跟随） |
| 5 像素回归 | 4 | 合并版逐页与单页版**逐像素相等**（0 差异，无容差） |

像素回归的做法：切换器是 fixed，截图前把它 `display:none` 不影响任何布局，于是两版视口与 clip 完全相同，可以要求 0 差异——不需要任何掩码或抗锯齿容差。这条同时也是"合并没有误伤页面内容"的最强证据。

---

## 常用命令

```bash
cd Design_Preview

python3 _build_charm.py                      # 只重建合并版 charm-preview.html
python3 _build_charm.py --only=components    # 单页版（components → charm-components.html）
python3 _build_charm.py --all                # 合并版 + 四个单页版（像素回归要用）

python3 _make_cjk_fonts.py                   # 全量 CJK 字体包（转 3 个 24 MB 的 TTF，约 2 分钟）
python3 _make_cjk_fonts.py --gb2312          # GB2312 子集字体包
python3 _build_charm.py --fonts=cjk          # 中文字体版 charm-preview-cjk.html
python3 _build_charm.py --fonts=cjk-gb       # 中文子集版 charm-preview-cjk-gb.html
python3 _make_cjk_fonts.py --export          # 把包里的更纱黑体解回独立 woff2（不必重跑转换）

NODE_PATH=<装了 puppeteer-core 的 node_modules> node _verify_charm.mjs
node _verify_charm.mjs --no-visual           # 跳过像素回归，不需要单页产物
```

改默认打开哪个 tab：`_build_charm.py` 顶部的 `DEFAULT_SLUG`（验证脚本从产物的 `data-default` 属性读，不必同步改）。

---

## 克隆之后：拉丁版直接能重建，中文版要先自备字体

仓库收了四个产物与全部构建输入，但**没收中文字体原件**（287 MB，且是第三方字体，
各自从上游取更合适）。所以：

| | 克隆后能否重建 | 缺什么 |
|---|---|---|
| `charm-preview.html` / `charm-components.html` | **能**，`python3 _build_charm.py --all` 即可 | — |
| `charm-preview-cjk.html` / `charm-preview-cjk-gb.html` | 不能，但**产物本身在仓库里，直接用没问题** | 两套中文字体原件 |

（拉丁版可重建这一条是实测的：把三个脚本 + 四个 `_files/` 目录 + `_charm_fonts.json`
复制到空目录当作新克隆跑 `--all`，产出与仓库已提交的版本逐字节一致。）

### 要重建中文版，补三步

**第一步，放字体原件。** 目录名与文件名必须与下面一致——`_make_cjk_fonts.py` 是按
字面量路径找的，缺哪个就报哪个的错，不会静默跳过：

```
NotoSansCJK-Woff2/                 思源黑体 SC，woff2，仅需这 5 个字重
    NotoSansSC-Thin.woff2  Regular  Medium  Bold  Black
SarasaMonoSC-TTF-1.0.36/           等距更纱黑体 SC，TTF，仅需这 3 个字重
    SarasaMonoSC-Regular.ttf  SemiBold  Bold
```

本仓库产物用的版本（字体 name 表里读出来的，照此取版本可复现同样的字节）：

| 字体 | 版本（读自 name 表） | 上游 | 许可 |
|---|---|---|---|
| Noto Sans SC | 2.004，Adobe hotconv 构建 | Google Fonts 的 **Noto Sans SC**（上游项目 `notofonts/noto-cjk`） | OFL |
| 等距更纱黑体 SC | 1.0.36 | `be5invis/Sarasa-Gothic` 的 release，取 `SarasaMonoSC-TTF-1.0.36` | OFL |

⚠ 认准字族名是 **`Noto Sans SC`**、字重叫 Thin/Regular/Medium/Bold/Black——这是 Google Fonts
那一支的命名。`notofonts/noto-cjk` 仓库里同一批字体叫 `Noto Sans CJK SC`、文件名形如
`NotoSansCJKsc-Regular.otf`，取回来还得改名并转 woff2 才能被脚本认出。

两者都是 OFL，可自由再分发；本仓库不收只是因为体积，不是许可问题。
更纱黑体的 release 里含 10 个字面（带斜体），**只有上面 3 个会被用到**，其余可不下载。
思源那 7 个字重里 Light / DemiLight 同样用不到。

**第二步，生成字体包。** 全量约 2 分钟（要把 3 个 24 MB 的 TTF 转成 woff2），
子集约 45 秒。两个包互不依赖，只要中文版就只跑对应那一条：

```bash
python3 _make_cjk_fonts.py            # → _charm_fonts_cjk.json     72 MB
python3 _make_cjk_fonts.py --gb2312   # → _charm_fonts_cjk_gb.json  15 MB
```

子集那条会读 `charm-preview.html` 来兜底取「产物里在用的字符」，所以**要先有拉丁版产物**
（克隆下来就有；若删过，先跑一次 `python3 _build_charm.py`）。

**第三步，构建。**

```bash
python3 _build_charm.py --fonts=cjk      # → charm-preview-cjk.html     72.8 MB
python3 _build_charm.py --fonts=cjk-gb   # → charm-preview-cjk-gb.html  16.0 MB
```

思源那 5 个字面是 woff2 原样收下，字节必然一致；更纱那 3 个要经 fontTools + brotli
转换/子集化，**同版本工具链才会得到同样的字节**。所以 `cmp` 与仓库产物一致是好消息
（字体版本与工具链都对上了），不一致也未必是错——先看字体 name 表的版本号对不对，
再看 `pip show fonttools brotli`。本仓库产物用的是 fontTools 4.61.1。

### 只想要中文字体，不想重建

`python3 _make_cjk_fonts.py --export` 把包里的更纱黑体解回独立 `.woff2`
（→ `SarasaMonoSC-Woff2/`，全量 3 个字重共 25 MB），供别的项目直接 `@font-face` 引用；
加 `--gb2312` 则导子集版（约 1.5 MB/字重）。这一步只做 base64 解码，不重跑转换。
