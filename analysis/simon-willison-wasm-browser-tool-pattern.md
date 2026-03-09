# WASM 浏览器工具构建模式精读

**来源**: [GIF optimization tool using WebAssembly and Gifsicle](https://simonwillison.net/guides/agentic-engineering-patterns/gif-optimization/)
**日期**: 2026-03-13
**标签**: wasm, emscripten, browser-tools, agentic-engineering, gifsicle, rodney, simonw-tools, cli-to-wasm

---

## 30秒 TL;DR

> 把任何 C/C++ CLI 工具编译到 WebAssembly，包一层 drag-drop HTML 界面，就得到一个零后端、可静态托管的浏览器工具——这个模式可以无限复用。编译复杂度（Emscripten trial-and-error）恰好是 coding agent 最擅长暴力破解的事；而让 agent 自测（`uvx rodney --help`）则是整个工作流能 close-loop 的关键。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| CLI → WASM → Web UI | C/C++ 命令行工具通过 Emscripten 编译到 WASM，包装成单页 HTML | 任何已有 C/C++ CLI 工具需要 Web 界面 |
| Agent WASM 暴力编译 | 让 agent 而非人类做 Emscripten trial-and-error | Emscripten 配置错误多、文档散 |
| `uvx tool --help` 自学习 | prompt 中直接引用工具名 + `--help`，agent 自学用法 | 任何 agent 需要使用的 CLI 工具 |
| drag-drop + download | 隐式 prompt 关键词，agent 知道对应完整的 JS/CSS 实现 | 文件处理类 Web 工具 |
| Rodney 浏览器自测 | 持久化 Chrome 进程 + 短命令序列，agent 驱动做视觉/功能测试 | 单页 HTML 工具开发 |
| patch + build script 提交 | WASM 源码不放 repo，但 patch + build script + 编译后的 .wasm 三者都提交 | 开源 C 代码的 WASM 封装 |

---

## 深读

### 一、完整 Prompt 解剖

Simon 的原始 Prompt（iPhone 上用 Claude App 输入）：

```
gif-optimizer.html

Compile gifsicle to WASM, then build a web page that lets you open or drag-drop
an animated GIF onto it and it then shows you that GIF compressed using gifsicle
with a number of different settings, each preview with the size and a download button

Also include controls for the gifsicle options for manual use - each preview has a
"tweak these settings" link which sets those manual settings to the ones used for
that preview so the user can customize them further

Run "uvx rodney --help" and use that tool to test your work - use this GIF for
testing https://static.simonwillison.net/static/2026/animated-word-cloud-demo.gif
```

每个片段的信息密度分析：

| Prompt 片段 | 隐式知识量 | agent 展开后执行什么 |
|------------|-----------|-------------------|
| `gif-optimizer.html`（第一行） | 文件命名即路由 | agent `ls` 仓库，理解"每个文件是独立工具"的模式 |
| `Compile gifsicle to WASM` | 隐含 Emscripten 工具链全流程 | 查找 Gifsicle 源码 → 安装 emsdk → 配置编译 → patch 源码 → 生成 .wasm |
| `drag-drop` | Web File API + DragEvent 标准模式 | 生成 drag-and-drop zone HTML + JS event handlers + CSS styling |
| `each preview with the size and a download button` | blob URL + `<a download>` 机制 | 生成 `URL.createObjectURL(blob)` + `<a href=.. download=..>` |
| `tweak these settings link` | 双向绑定：预设值 ↔ 手动控件 | 生成"点击后更新 slider/input 值"的 JS |
| `Run "uvx rodney --help"` | agent 自学工具模式 | 执行 help，读取用法，生成测试脚本 |
| 提供测试 GIF URL | 真实文件测试（非 mock） | 用真实动画 GIF 验证所有压缩级别，检查输出大小和视觉质量 |

**关键洞察**：这 7 行 Prompt 里，每一个"关键词"都是一个展开成完整实现的语义令牌。Simon 的技巧是**选择 agent 已经有完整知识的技术词汇**，而不是描述实现细节。

---

### 二、Gifsicle WASM 编译技术链

从 [simonw/tools lib 目录](https://github.com/simonw/tools/tree/main/lib/gifsicle) 可以看到 agent 产出的实际结构：

```
lib/gifsicle/
├── build.sh          # 构建脚本（克隆到 /tmp，切换到已知 commit，apply patch）
└── gifsicle.patch    # 使 Gifsicle 兼容 WASM 的源码补丁
lib/wasm/             # 其他工具的编译产物（参考模式）
```

build.sh 设计原则：
- **不把源码放 repo**：克隆到 `/tmp`，应用 patch，编译，复制产物
- **锁定到已知 commit**：`git checkout <hash>`，确保可复现
- **WASM 产物放 repo**：`gif-optimizer.html` 同级或 `lib/` 下，GitHub Pages 直接服务

Emscripten 标准编译参数（来自 simonw/tools 其他工具的实际 build 脚本）：

```bash
emcc source.c -o output.js \
  -s WASM=1 \
  -s EXPORTED_RUNTIME_METHODS='["callMain","FS"]' \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s FORCE_FILESYSTEM=1 \
  -s MODULARIZE=1 \
  -s EXPORT_NAME=createModule
```

参数含义速查：

| 参数 | 作用 | 何时必需 |
|------|------|---------|
| `WASM=1` | 输出 .wasm 而非 asm.js | 始终 |
| `EXPORTED_RUNTIME_METHODS=["callMain","FS"]` | 允许从 JS 调用 main() 并访问虚拟文件系统 | CLI 工具（通过文件传参） |
| `ALLOW_MEMORY_GROWTH=1` | 允许堆内存动态增长 | 处理大文件 |
| `FORCE_FILESYSTEM=1` | 强制包含文件系统支持 | 读写临时文件的 CLI 工具 |
| `MODULARIZE=1` | 生成工厂函数而非全局变量 | 多 WASM 模块共存时 |
| `EXPORT_NAME=createXxxModule` | 模块构造函数名（按工具命名） | 配合 MODULARIZE=1 |

WASM 模块在浏览器中的典型调用模式：

```javascript
// 加载模块
const module = await createGifsicleModule();

// 写输入文件到虚拟 FS
module.FS.writeFile('/input.gif', new Uint8Array(inputArrayBuffer));

// 调用 main() 相当于运行 CLI
module.callMain(['--optimize=3', '--lossy=80', '/input.gif', '-o', '/output.gif']);

// 读取输出文件
const output = module.FS.readFile('/output.gif');

// 创建下载 blob
const blob = new Blob([output], { type: 'image/gif' });
const url = URL.createObjectURL(blob);
```

---

### 三、Rodney 自测机制详解

Rodney 是 Simon 自建的 Chrome 自动化 CLI 工具（Go 语言，通过 Chrome DevTools Protocol 驱动持久化 Chrome 进程）。

**架构特点（与 Playwright 的差异）**：

| 维度 | Rodney | Playwright |
|------|--------|-----------|
| 进程模型 | Chrome 持久运行，命令短暂连接 | 每次测试启动新进程 |
| Tab 管理 | 跨命令共享 Tab 状态 | 每 test 独立 context |
| agent 使用 | `--help` 即完整文档，无需预知 | 需要了解 Python/JS/TS API |
| 安装 | `uvx rodney`（通过 PyPI 的 Go 二进制） | `pip install playwright` + `playwright install` |
| 适合场景 | agent 驱动的交互式手动测试 | 完整自动化测试套件 |

**Rodney 命令速查（最常用）**：

```bash
# 启动（带可见窗口便于 agent 截图分析）
rodney start --show

# 打开工具页面
rodney open https://localhost:8080/gif-optimizer.html
rodney waitstable    # 等待 DOM 稳定

# 视觉验证
rodney screenshot page.png    # 全页截图
rodney screenshot-el ".preview-grid" previews.png  # 元素截图

# DOM 检查
rodney text "h1"              # 读取标题
rodney exists ".error-msg"    # 检查错误元素
rodney visible "#download-btn" # 检查下载按钮可见

# JS 执行
rodney js "document.querySelectorAll('.preview-item').length"  # 计数预览项
rodney js "document.querySelector('.file-size').textContent"   # 读取文件大小

# Accessibility 验证
rodney ax-find --role button   # 找所有按钮（检查 a11y）
rodney ax-tree --depth 2       # 可访问性树（agent 用来理解页面结构）

# 文件输入（测试 drag-drop 的程序化替代）
rodney file "#file-input" /path/to/test.gif

# 退出码语义（重要）
# 0 = 成功  1 = 检查失败（条件不满足）  2 = 错误（Chrome 未启动等）
```

**agent 自测工作流（来自 session transcript 的实际模式）**：

```bash
# Step 1: 启动服务和浏览器
python -m http.server 8080 &
rodney start

# Step 2: 打开工具，上传测试文件
rodney open http://localhost:8080/gif-optimizer.html
rodney waitstable
rodney file "#file-input" /path/to/animated-word-cloud-demo.gif
rodney waitidle    # 等待 WASM 处理完成（可能较慢）

# Step 3: 视觉检查
rodney screenshot initial.png
# → agent 看截图，确认预览网格出现

# Step 4: 验证具体 bug（agent 在 transcript 中发现的实际问题）
rodney js "document.querySelector('.preview-item').style.display"
# → 发现 CSS display:none 优先级问题

# Step 5: 修复后重验证
rodney reload
rodney waitstable
rodney screenshot fixed.png
# → agent 对比截图确认修复
```

---

### 四、simonw/tools 仓库的无 AGENTS.md 现象

> "My simonw/tools repo currently lacks a CLAUDE.md or AGENTS.md file. I've found that agents pick up enough of the gist of the repo just from scanning the existing file tree and looking at relevant code in existing files."

这揭示了一个重要阈值：**当一个 repo 的文件结构足够规律（每个 .html 是独立工具），且现有文件质量足够高时，agent 通过 `ls` + 阅读几个相关文件，能自动推断 repo 惯例**。

对比：需要 CLAUDE.md 的情况：
- 多语言混合项目（惯例不明显）
- 特殊构建步骤（非标准工具链）
- 需要保护的敏感目录（不能让 agent 随意修改）
- 复杂的测试要求（需要特定环境变量）

不需要 CLAUDE.md 的情况：
- 高度规律的单一模式 repo（如：每个文件 = 独立工具）
- 现有文件本身就是最好的 few-shot 示例

---

### 五、从 iPhone 输入 Prompt 的约束与优势

Simon 明确说他是在 iPhone 上用 Claude App prompt 的。这个约束带来了一个隐藏优势：

> "This is a pretty clumsy prompt — I was typing it on my phone after all — but it expressed my intention well enough for Claude to build what I wanted."

**"笨拙 Prompt" 的反直觉洞见**：
- 手机输入限制了 prompt 长度和精确度
- 但这迫使 Simon 只写**意图**，而不是**实现步骤**
- 意图型 prompt 比实现型 prompt 更健壮（agent 有更多自由度做出好的工程决策）

---

## 心智模型

### 模型：CLI 工具的"WASM 封装成本曲线"

```
编译难度
    ↑
    │         复杂
    │        ╱╲
    │       ╱  ╲  (patch 源码 + 多文件依赖)
    │      ╱    ╲─── Gifsicle 这类
    │     ╱
    │    ╱  中等
    │   ╱  (单文件 C，无外部依赖)
    │  ╱
    │ ╱  简单
    │╱  (无状态纯计算函数)
    └──────────────────────────→  封装价值
              低           高
```

**关键洞见**：编译难度 ≠ 封装价值的上限。Gifsicle 属于"高难度 + 高价值"——正是因为难，才没有人已经做出好的浏览器版本。**难度是护城河，agent 的暴力破解能力抹平了这个护城河。**

**适用条件**：
- 原 CLI 工具是 C/C++ 写的（Emscripten 支持）
- 工具有清晰的"输入文件 → 输出文件"接口（通过 FS 传递）
- 工具不依赖网络或系统服务

**失效条件**：
- 工具依赖动态链接库（.so 文件）且无源码
- 工具需要真正的系统调用（非文件 I/O）
- 工具的配置状态复杂到无法用命令行参数表达

---

## 非显见洞见

### 洞见 1：`Compile gifsicle to WASM` 这 5 个词隐含了整个 Emscripten 工具链知识

**蕴含链**：
```
洞见：一个短语可以让 agent 展开完整的复杂工具链
→ 所以：agent 的能力边界不是"知道多少 API"，而是"知道多少命名模式"
→ 所以：好的 prompt 是选择 agent 已有完整知识的技术词汇，而不是描述步骤
→ 因此可以：建立自己的"高密度关键词词典"——每个词对应 agent 能展开的完整实现
```

**隐含假设**：Gifsicle 足够有名（30 年，广泛使用），agent 训练数据中有关于它的 WASM 编译尝试的文档。对于知名度不足的 C 工具，可能需要提供 GitHub URL + `emsdk` 安装命令作为补充。

**反事实**：如果 Simon 不知道 Gifsicle 这个名字，而是描述"一个能识别帧差异、只存储变化区域的 GIF 压缩算法的 C 实现"——agent 无法利用已有的 Gifsicle 知识，可能需要重新实现或搜索，失败率大幅上升。

---

### 洞见 2：测试工具的 `--help` 是 agent API 的真正合约

**蕴含链**：
```
洞见：Simon 没有告诉 agent "如何用 Rodney"，只说 "run --help"
→ 所以：Rodney 的 --help 输出质量 = 工具被 agent 正确使用的概率
→ 所以：面向 agent 的工具设计，--help 质量比代码质量更直接影响使用效果
→ 因此可以：设计任何内部 CLI 工具时，把"agent 能否通过 --help 独立使用它"作为
   设计目标，而不只是"人类能否读懂 --help"
```

Rodney README 中的实际 `--help` 设计验证了这一点：
- 完整的命令列表（不省略）
- 每个命令后面跟注释说明
- 包含 exit code 语义（agent 需要判断 0/1/2 的不同含义）
- 包含 shell 脚本组合示例

**边界**：如果工具的 `--help` 输出超过 agent 的上下文窗口，效果会降低。Rodney 的 `--help` 大约 200 行，在合理范围内。

---

### 洞见 3：drag-drop + download 是"免费"的 UX 升级

**蕴含链**：
```
洞见：Simon 在 prompt 中提了 drag-drop 和 download button，但没有描述实现
→ 所以：这两个关键词对 agent 来说是完整的实现模式（有标准 MDN 参考实现）
→ 所以：用 prompt 添加这类"知名 UX 模式关键词"，边际成本接近零
→ 因此可以：维护一个"UX 关键词列表"，每个词对应 agent 能生成的完整交互实现
  例如：drag-drop / download button / toast notification / infinite scroll /
        keyboard shortcut / dark mode toggle / copy-to-clipboard...
```

---

### 洞见 4：patch + build script 比 fork 源码更优雅

Simon 专门补充 prompt 要求将 build script 和 patch 放进 commit，而不是把 Gifsicle 源码整体放入 repo。

**蕴含链**：
```
洞见：只提交 patch + build script + 编译产物，不提交源码
→ 所以：repo 保持精简，但构建完全可复现（任何人都能重新编译）
→ 所以：这实际上是 Nixpkgs / Homebrew 的管理模式——"配方"而非"结果"
→ 因此可以：对所有基于开源 C 工具的 WASM 封装，统一采用：
  lib/{tool}/build.sh + lib/{tool}/{tool}.patch + lib/wasm/{tool}.js + lib/wasm/{tool}.wasm
  的目录结构作为标准模式
```

---

## 反模式与陷阱

- **陷阱：让 agent 自己选择测试工具，而不提供测试入口**
  → 描述：没有 `uvx rodney --help` 或类似指令时，agent 可能只做静态代码审查，不会真正运行代码
  → 正确做法：prompt 中明确指定测试机制，并提供真实的测试输入（如测试 GIF 的 URL）

- **陷阱：把 Gifsicle 完整源码放进 repo**
  → 描述：增大 repo 体积，未来版本更新困难，许可证归属不清晰
  → 正确做法：patch + build script + 编译产物三分离；build script 克隆到 /tmp 再编译

- **陷阱：不提交 .wasm 文件到 repo**
  → 描述：静态托管（GitHub Pages）无法动态编译，用户无法运行工具
  → 正确做法：.wasm 文件（通常 100-500KB）直接提交到 repo；如果用 Git LFS 则更好

- **陷阱：CORS 依赖（GIF URL 输入框）**
  → Simon 自己注意到了："只对带 open CORS headers 的 URL 有效，我可能会移除这个功能"
  → 正确做法：核心功能只依赖本地文件上传（file input + drag-drop），URL 输入作为可选功能并显示 CORS 提示

- **陷阱：不标注开源软件来源**
  → Simon 专门 prompt："Make sure the HTML page credits gifsicle and links to the repo"
  → 正确做法：footer 中标注工具名、作者、许可证链接——尤其对 GPL 工具（法律要求，不只是礼貌）

- **陷阱：WASM 模块全局化（不用 MODULARIZE=1）**
  → 描述：多个 WASM 模块共存时全局变量冲突，难以调试
  → 正确做法：`-s MODULARIZE=1 -s EXPORT_NAME=createXxxModule`，每个工具有自己的命名空间

---

## 与现有知识库的连接

- 关联 `analysis/simon-willison-agentic-patterns.md`：该文件 Section 6 是本文的简化版摘要，本文是完整精读展开。两者是互补关系——读摘要了解 GIF 模式存在，读本文了解如何实际操作。

- 关联 `analysis/simon-willison-linear-walkthroughs-manual-testing.md`：Rodney 工具在两篇文章中均出现——本文详细记录了 Rodney 的完整命令集（来自 GitHub README），与该文中"Agentic Manual Testing"部分形成互补。**本文是 Rodney 完整命令参考，该文是 Rodney 在测试工作流中的位置。**

- 关联 `html-tools/pdf_ocr.html` + `javascript/browser_ocr.html`：这些工具已经采用了"单页 HTML + WASM 库（Tesseract）"的模式，与本文的 Gifsicle WASM 模式同构。区别在于 Tesseract 有现成的 JS 包装（Tesseract.js），而 Gifsicle 需要从 C 源码编译。

- 关联 `javascript/pdf_to_images.html`：drag-drop + download button 的 UX 模式已经在这个工具中实现，可以作为新 WASM 工具的 UI 参考。

- 关联 `python/mini_symphony.py`：Rodney 的"持久化 Chrome + 短命令"架构可以成为 mini_symphony 编排器的一个子任务测试节点——把 `rodney screenshot` 的输出作为视觉验证 checkpoint 插入任务流。

---

## 衍生项目想法

### 想法一：WASM 工具构建配方库（wasm-recipes）

**来源组合**：[本文 patch + build script 模式] + [已有 `html-tools/` 目录中的单页工具集合]

**为什么有意思**：simonw/tools 仓库里已经有多个 WASM 工具（Gifsicle、SLOCCount 的 C counters、WebPerl 等），但这些配方散落在各工具的 `lib/` 子目录里。一个结构化的"WASM 工具配方库"——类似 Homebrew formula 的思路——可以：
1. 标准化 build.sh 格式（统一变量名、错误处理、产物路径）
2. 建立"哪些 C 工具已有 WASM 端口"的索引（避免重复工作）
3. 把 Emscripten 参数的常见组合模板化（文件 I/O 型、stdin/stdout 型、交互型）

**最小 spike**：在 `snippets/` 目录下创建 `emscripten-wasm-build-template.sh`，包含带注释的参数模板和三种典型场景（文件处理、stdin 管道、多文件输出）。附上一个 `snippets/wasm-tools-registry.md`，列出 5-10 个已有 WASM 端口的知名 C 工具及其编译复杂度评级。

---

### 想法二：Rodney 视觉验证 × mini_symphony 编排集成

**来源组合**：[本文 Rodney 完整命令集] + [已有 `python/mini_symphony.py` 任务编排器]

**为什么有意思**：mini_symphony 目前的 checkpoint 机制是"任务完成 → 人工 review"。如果在某些任务后插入 `rodney screenshot + vision` 验证步骤，可以：
1. 对 UI 类任务实现自动视觉 gate（布局符合预期才进入下一任务）
2. 生成任务执行过程的截图时间线（类似 CI 的 artifact）
3. 发现 agent 在 UI 层的静默错误（代码正确但渲染错误）

**最小 spike**：给 `mini_symphony.py` 增加一个可选的 `rodney_check` 任务类型：
```yaml
- name: "Verify gif-optimizer UI"
  type: rodney_check
  commands:
    - "rodney open http://localhost:8080/gif-optimizer.html"
    - "rodney waitstable"
    - "rodney screenshot {workspace}/ui-check.png"
    - "rodney exists '.preview-grid'"
```
执行完后把截图路径记录到 TASKS.md，供人工 review。一天内可以实现这个 YAML 解析 + rodney 子进程调用的扩展。

---

### 想法三：浏览器端"隐私优先"工具套件

**来源组合**：[本文 CLI → WASM → 零后端 Web 工具模式] + [已有 `html-tools/pdf_ocr.html` 零后端 OCR 工具]

**为什么有意思**：pdf_ocr.html 和 gif-optimizer.html 共享同一个核心价值主张：**文件不离开浏览器**。用户越来越关心把敏感文件上传到第三方服务的隐私风险。一个显式的"Privacy-First Tools"标签/主题，将现有工具（PDF OCR、GIF 压缩）和未来工具（图片压缩、视频截帧、文档格式转换）组织成一个可发现的套件，比单独的工具更有传播价值。

**候选工具清单**（均有成熟 C/C++ 实现，已有 WASM 端口或容易编译）：

| 工具 | C 实现 | 功能 | WASM 现状 |
|------|--------|------|-----------|
| pngquant | C | PNG 无损压缩 | 有（squoosh 用过） |
| ffmpeg | C | 视频截帧/转换 | 有（ffmpeg.wasm） |
| libvips | C | 图片处理（resize/crop） | 有（wasm-vips） |
| poppler | C++ | PDF 转图片 | 有（部分端口） |
| tesseract | C++ | OCR | 有（Tesseract.js）|
| optipng | C | PNG 优化 | 可编译 |

**最小 spike**：选 pngquant（最小依赖），用 Emscripten 编译到 WASM（让 agent 做），包装成 `html-tools/png-optimizer.html`，UI 参照 gif-optimizer 的模式（drag-drop + 多级压缩预览 + download）。预计半天 + agent 的 Emscripten 编译时间。

---

## Prompt 模式速查

### WASM 工具构建（基础模板）

```
{output-filename}.html

Compile {cli-tool-name} to WASM, then build a web page that lets you open or drag-drop
{file-type} files onto it and {core-feature-description}.

Include {additional-controls-description}.

Run "uvx rodney --help" and use that tool to test your work - use this {file-type} for
testing: {test-file-url}

Make sure the HTML page credits {cli-tool-name} and links to {upstream-repo-url}.
```

### WASM Build Script（agent 生成，标准结构）

```bash
#!/usr/bin/env bash
# Build {tool-name} to WebAssembly using Emscripten
set -euo pipefail

TOOL_NAME="{tool-name}"
TOOL_REPO="https://github.com/{owner}/{repo}"
TOOL_COMMIT="{known-good-commit-hash}"
BUILD_DIR="/tmp/${TOOL_NAME}-wasm-build"
OUTPUT_DIR="$(dirname "$0")/../wasm"

# Install/activate emsdk
if ! command -v emcc &>/dev/null; then
    git clone https://github.com/emscripten-core/emsdk.git /tmp/emsdk
    /tmp/emsdk/emsdk install latest
    /tmp/emsdk/emsdk activate latest
    source /tmp/emsdk/emsdk_env.sh
fi

# Clone source to /tmp (don't commit source to repo)
rm -rf "$BUILD_DIR"
git clone "$TOOL_REPO" "$BUILD_DIR"
cd "$BUILD_DIR"
git checkout "$TOOL_COMMIT"

# Apply compatibility patch (if needed)
PATCH_FILE="$(dirname "$0")/${TOOL_NAME}.patch"
if [ -f "$PATCH_FILE" ]; then
    git apply "$PATCH_FILE"
fi

# Compile to WASM
emcc {source-files} -o "${TOOL_NAME}.js" \
    -s WASM=1 \
    -s EXPORTED_RUNTIME_METHODS='["callMain","FS"]' \
    -s ALLOW_MEMORY_GROWTH=1 \
    -s FORCE_FILESYSTEM=1 \
    -s MODULARIZE=1 \
    -s EXPORT_NAME="create$(echo ${TOOL_NAME^})Module" \
    {additional-emcc-flags}

# Copy output
mkdir -p "$OUTPUT_DIR"
cp "${TOOL_NAME}.js" "${TOOL_NAME}.wasm" "$OUTPUT_DIR/"

echo "Build complete: ${OUTPUT_DIR}/${TOOL_NAME}.js + .wasm"
```

### Rodney 视觉测试（agent 自测模板）

```bash
# Start dev server + browser
python3 -m http.server 8080 &
SERVER_PID=$!
rodney start

# Load tool and provide test file
rodney open http://localhost:8080/{tool}.html
rodney waitstable
rodney file "#{file-input-id}" {test-file-path}
rodney waitidle

# Visual check
rodney screenshot {tool}-test.png
# [agent: look at screenshot to verify UI rendered correctly]

# Functional checks
rodney exists ".{output-container}"  # output appeared
rodney js "document.querySelectorAll('.{result-item}').length"  # count results
rodney visible "#{download-btn}"  # download button visible

# Cleanup
rodney stop
kill $SERVER_PID
```

---

## 参考链接

- [原文：GIF optimization tool - Agentic Engineering Patterns](https://simonwillison.net/guides/agentic-engineering-patterns/gif-optimization/)
- [Gifsicle 源码](https://github.com/kohler/gifsicle) — C GIF 处理库，~30 年历史，GPL-2.0
- [gif-optimizer.html 实际产出](https://tools.simonwillison.net/gif-optimizer) — Simon 的工具页面
- [simonw/tools 仓库](https://github.com/simonw/tools) — 所有工具源码，含 Gifsicle build script + patch
- [simonw/tools lib/ 目录](https://github.com/simonw/tools/tree/main/lib) — 含其他 C→WASM 编译模式参考（SLOCCount、WebPerl）
- [Rodney GitHub](https://github.com/simonw/rodney) — Chrome 自动化 CLI，agent 自测工具
- [Emscripten 官网](https://emscripten.org/) — C/C++ → WASM 工具链
- [session transcript](https://gist.github.com/simonw/gif-optimizer-session) — Claude Code 完整会话记录（含 debug 过程）
- 关联已有文件：
  - [`analysis/simon-willison-agentic-patterns.md`](./simon-willison-agentic-patterns.md) — Section 6 为本文简要版
  - [`analysis/simon-willison-linear-walkthroughs-manual-testing.md`](./simon-willison-linear-walkthroughs-manual-testing.md) — Rodney 在测试工作流中的位置
  - [`html-tools/pdf_ocr.html`](../html-tools/pdf_ocr.html) — 同类"零后端 WASM 工具"实例
