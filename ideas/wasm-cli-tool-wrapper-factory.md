# WASM CLI 工具封装工厂

**来源**: https://simonwillison.net/guides/agentic-engineering-patterns/gif-optimization/
**日期**: 2026-03-13
**状态**: 💡灵感

---

## 核心理念

> 把任何 C/C++ CLI 工具编译到 WebAssembly + 包一层 drag-drop HTML 界面 = 零后端、隐私友好的浏览器工具。这个模式高度可复用，且正好利用了 coding agent 最擅长的能力（Emscripten trial-and-error 暴力调试）。

---

## 关键技术要点

### 通用架构

```
[C/C++ CLI 工具]
      ↓ emcc 编译（agent 暴力破解 Emscripten 配置）
[.wasm + .js glue]   ← 提交到 repo
      ↓ 浏览器加载
[单页 HTML 工具]
  ├── drag-drop 文件上传区
  ├── 多级预设压缩/处理选项（各自显示文件大小）
  ├── 手动参数控制 + "用这些设置调整" 按钮
  └── 各结果独立 download 按钮
```

### Emscripten 核心参数（文件 I/O 型工具）

```bash
emcc source.c -o output.js \
  -s WASM=1 \
  -s "EXPORTED_RUNTIME_METHODS=[\"callMain\",\"FS\"]" \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s FORCE_FILESYSTEM=1 \
  -s MODULARIZE=1 \
  -s "EXPORT_NAME=createToolModule" \
  -O2
```

### WASM 调用模式（文件输入/输出）

```javascript
const module = await createToolModule();

// 写输入到虚拟 FS
module.FS.writeFile('/input.gif', new Uint8Array(arrayBuffer));

// 调用 CLI（等价于命令行执行）
module.callMain(['--optimize=3', '--lossy=80', '/input.gif', '-o', '/output.gif']);

// 读取输出
const output = module.FS.readFile('/output.gif');
const blob = new Blob([output], { type: 'image/gif' });
const downloadUrl = URL.createObjectURL(blob);
```

### Repo 结构约定

```
lib/
└── {tool-name}/
    ├── build.sh           # 克隆到/tmp + apply patch + emcc 编译
    └── {tool-name}.patch  # 使工具兼容 WASM 的源码 patch
    
lib/wasm/                  # 编译产物（提交到 repo，供 GitHub Pages 使用）
    ├── {tool-name}.js     # Emscripten JS glue
    └── {tool-name}.wasm   # WebAssembly 二进制

html-tools/
└── {tool-name}-optimizer.html  # 单页工具（drag-drop + 预设 + download）
```

---

## 候选工具清单

| 工具 | 功能 | C 实现 | WASM 已有端口 | 难度 | 用户价值 |
|------|------|--------|-------------|------|---------|
| **pngquant** | PNG 无损压缩（减色） | C | 有（Squoosh 用过）| 低 | ⭐⭐⭐⭐⭐ |
| **optipng** | PNG 无损优化（zlib 压缩） | C | 可编译 | 低 | ⭐⭐⭐⭐ |
| **jpegoptim** | JPEG 有损/无损压缩 | C | 可编译 | 中 | ⭐⭐⭐⭐⭐ |
| **gifsicle** | GIF 压缩 + 帧优化 | C | **已完成**（Simon 做了）| 高 | ⭐⭐⭐⭐ |
| **cwebp/dwebp** | WebP 编码/解码 | C | 有（官方提供）| 低 | ⭐⭐⭐⭐ |
| **svgo** | SVG 优化 | Node.js | 已有（JS 直接运行）| N/A | ⭐⭐⭐ |
| **ffmpeg** | 视频处理 | C | 有（ffmpeg.wasm）| 极高 | ⭐⭐⭐⭐⭐ |
| **pdftk** | PDF 合并/分割 | C++ | 困难 | 高 | ⭐⭐⭐ |

**推荐优先级**：pngquant > jpegoptim > optipng（难度低、价值高、无现成好用的纯浏览器端工具）

---

## 可行性与挑战

- ✅ 已验证可行：Simon 的 gif-optimizer.html 证明了 agent 可以从零完成 Emscripten 编译（含 patch 调试）
- ✅ 已验证可行：`lib/wasm/` 中的 SLOCCount C counters 证明了多工具共存于同一 WASM 目录的模式
- ✅ 已验证可行：Tesseract.js 等已有 WASM 端口证明复杂库也可以在浏览器中运行
- ⚠️ 待解决：Emscripten 环境安装耗时（首次约 10-20 分钟），CI 中需要缓存 emsdk
- ⚠️ 待解决：某些工具依赖动态链接库（.so），静态链接可能导致 .wasm 体积过大
- ⚠️ 待解决：GPL 工具（如 gifsicle 是 GPL-2.0）要求在页面上标注许可证（法律义务）
- ⚠️ 待解决：WASM 模块首次加载耗时（100-500KB），需要加载进度提示

---

## Prompt 模板（交给 agent 时使用）

```
{tool-name}-optimizer.html

Compile {tool-name} (from {github-url}) to WASM, then build a web page that lets 
you open or drag-drop {file-type} files onto it and shows you the file processed 
with a number of different presets, each preview showing the file size and a 
download button.

Include manual parameter controls where each preset has a "tweak these settings" 
link that copies the preset values into the manual controls for further customization.

The build script should:
- Clone the repo to /tmp and switch to commit {commit-hash} before compiling
- Store only the patch (if any) and build script in lib/{tool-name}/
- Commit the compiled .js and .wasm files to lib/wasm/

Run "uvx rodney --help" and use that tool to test your work.
Use this {file-type} for testing: {test-file-url}

Make sure the page credits {tool-name} and links to the upstream repo. 
Include the license (it's {license}).
```

---

## 与现有知识库的连接

- 关联 `snippets/emscripten-wasm-build-template.sh`：本 idea 的配套构建脚本模板，直接可用于实现
- 关联 `html-tools/pdf_ocr.html`：已有的零后端 WASM 工具，与本 idea 同模式（Tesseract.js 版本是现成 npm 包，不需要从 C 编译）
- 关联 `analysis/simon-willison-wasm-browser-tool-pattern.md`：本 idea 的详细技术背景，含 Emscripten 参数速查表
- 关联 `javascript/browser_ocr.html`：UI 参考（drag-drop + 结果展示 + download button）

---

## 下一步行动

- [ ] **最小 spike**：选 `pngquant`（最小依赖，高频需求），让 agent 编译到 WASM，生成 `html-tools/png-optimizer.html`
  - 参考 `snippets/emscripten-wasm-build-template.sh` 作为 build script 骨架
  - 用 Simon 的 prompt 模板（上方）
  - 预计时间：1-2 小时（含 agent Emscripten 调试时间）
- [ ] 验证：WASM 文件大小是否在合理范围（目标 < 500KB）
- [ ] 验证：Rodney 视觉测试是否能发现"预览网格未渲染"类 bug
- [ ] 扩展：若 pngquant 成功，依次做 optipng 和 jpegoptim
