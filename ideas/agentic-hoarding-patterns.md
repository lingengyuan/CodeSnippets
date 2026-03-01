# Agentic Engineering: Hoard Things You Know How to Do

**来源**: [Simon Willison — Hoard Things You Know How to Do](https://simonwillison.net/guides/agentic-engineering-patterns/hoard-things-you-know-how-to-do/)
**日期**: 2026-03-01
**状态**: 💡灵感

---

## 核心理念

> 构建软件的关键技能是知道什么可能、什么不可能，以及大致如何实现。

Simon 的做法：把每个解决过的问题都留下**可运行的代码证据**，而不只是"知道怎么做"。这些积累在 agent 时代变成了超级杠杆——你不需要重新解决问题，只需要告诉 agent "参考这个已有实现"。

**他的囤积体系**：
- 博客 + TIL 博客记录方案
- 1000+ GitHub 仓库存 proof-of-concept
- [tools.simonwillison.net](https://tools.simonwillison.net) — 单页 HTML 工具合集
- [simonw/research](https://github.com/simonw/research) — agent 生成的调研报告

---

## 关键技术片段

### 1. 浏览器端 PDF → 图片（PDF.js）

纯前端，零后端依赖。PDF 每页渲染到 canvas，导出为 JPEG。

**关键参数**：
- `desiredWidth = 800` — 控制输出分辨率
- `canvas.toDataURL('image/jpeg', 0.8)` — 0.8 质量压缩
- 异步生成器 `async function*` 逐页 yield，内存友好

**依赖**: `pdf.js v2.9.359`（CDN 加载）

```javascript
async function* convertPDFToImages(file) {
  const pdf = await pdfjsLib.getDocument(URL.createObjectURL(file)).promise;
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale: 1 });
    const canvas = document.createElement('canvas');
    canvas.width = desiredWidth;
    canvas.height = (desiredWidth / viewport.width) * viewport.height;
    await page.render({
      canvasContext: canvas.getContext('2d'),
      viewport: page.getViewport({ scale: desiredWidth / viewport.width }),
    }).promise;
    const imageURL = canvas.toDataURL('image/jpeg', 0.8);
    yield { imageURL, size: Math.ceil((imageURL.length - 23) * 0.75) };
  }
}
```

### 2. 浏览器端 OCR（Tesseract.js）

纯前端 OCR，WebAssembly 版 Tesseract，不需要后端。

**依赖**: `tesseract.js v2.1.0`（CDN 加载）

```javascript
async function ocrImages(images) {
  const worker = Tesseract.createWorker();
  await worker.load();
  await worker.loadLanguage("eng");
  await worker.initialize("eng");
  for (const img of images) {
    const { data: { text } } = await worker.recognize(img.src);
    // text 就是 OCR 结果
  }
  await worker.terminate();
}
```

### 3. 组合模式：PDF → OCR 全流程

PDF.js 渲染页面 → Tesseract.js OCR 识别 → 输出纯文本。整个流程在浏览器内完成，不需要服务器。

**实际工具**: [tools.simonwillison.net/ocr](https://tools.simonwillison.net/ocr)

---

## Agent 提示词模式

Simon 展示的核心技巧：**让 agent 读你的已有代码，然后组合/扩展**。

### 模式 A：抓取已有工具源码 → 组合出新工具

```
Use curl to fetch source from the OCR tool and gemini-bbox tool,
then build a new tool combining them for PDF page selection
and Gemini bounding box analysis.
```

**原理**：你不需要手写 spec，已有的可运行代码就是最好的 spec。

### 模式 B：从已有项目提取模式 → 迁移到新项目

```
Add mocked HTTP tests inspired by how [reference project] is doing it.
```

**原理**：参考实现比文档更准确，agent 可以直接读代码学习模式。

### 模式 C：克隆仓库 → 搜索特定实现 → 生成新代码

```
Clone simonw/research from GitHub to /tmp and find examples
of compiling Rust to WebAssembly, then create a demo HTML page.
```

**原理**：把你的 GitHub 仓库当成 agent 可检索的知识库。

---

## 对我们 CodeSnippets 项目的启示

| Simon 的做法 | 我们可以做的 |
|-------------|------------|
| 1000+ GitHub 仓库 | 本项目就是集中版——片段集中管理比散落在仓库里更好检索 |
| `tools.simonwillison.net` 单页工具 | 可以加一个 `html-tools/` 目录存单页 HTML 工具 |
| agent 读源码组合新工具 | `snippet_manager.py` 的 `combine_prompt()` 就是这个思路 |
| TIL 博客记录 | `ideas/` 目录 + 片段头部注释就是轻量版 TIL |

### 可以立刻收录的片段

1. **PDF.js 渲染器** → `javascript/pdf_to_images.html` — 纯前端 PDF 转图片
2. **Tesseract.js OCR** → `javascript/browser_ocr.html` — 纯前端 OCR
3. **PDF + OCR 组合** → `html-tools/pdf_ocr.html` — 完整的浏览器端 PDF OCR 工具

---

## 参考链接

- [tools.simonwillison.net/ocr](https://tools.simonwillison.net/ocr) — 在线 PDF OCR 工具
- [tools.simonwillison.net/gemini-bbox](https://tools.simonwillison.net/gemini-bbox) — Gemini 边界框工具
- [Tesseract.js](https://tesseract.projectnaptha.com/) — WebAssembly OCR 引擎
- [PDF.js](https://mozilla.github.io/pdf.js/) — Mozilla PDF 渲染库
- [Simon 的 OCR 博文](https://simonwillison.net/2024/Mar/30/ocr-pdfs-images/)
- [Simon 的 HTML Tools 博文](https://simonwillison.net/2025/Dec/10/html-tools/)
