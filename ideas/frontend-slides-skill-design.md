# frontend-slides：Skill 架构设计分析

**来源**: https://github.com/zarazhangrui/frontend-slides
**日期**: 2026-03-06
**状态**: 🔬探索中

---

## 核心内容

一个让非设计师用自然语言生成动画丰富 HTML 演示文稿的 Claude Code Skill，8.4k stars。
核心洞察是：**用"展示选择"替代"描述选择"，消除与 AI 的风格沟通鸿沟。**

---

## 三个值得迁移的设计模式

### 模式一：Progressive Disclosure（渐进式披露）

SKILL.md 本身极精简，只是一张地图。真正的细节按需加载：

```
SKILL.md（入口 ~180 行）
  └── 仅当需要时才读：
      STYLE_PRESETS.md    ← Phase 2 才加载
      animation-patterns.md ← 生成代码时才加载
      html-template.md    ← 生成代码时才加载
      viewport-base.css   ← 生成代码时才加载
```

这与 `analysis/pi-context-engineering.md` 中 pi 的 P1 模式完全一致：
> 「不要把所有工具定义预加载进 context，按需披露」

**对 my-skills 的启示**：现有 skill 里，wechat2md、insight-collector 的 SKILL.md 已经相当详细。
可以考虑把 rules/ 子目录里的细节做成按需加载，入口文件只保留决策树。

---

### 模式二：Show Don't Tell（展示代替描述）

不问用户"你想要什么风格"（抽象），而是生成 3 个不同风格的真实预览，
用户通过视觉反应选择（具体）。

```
传统做法：
  用户描述 → AI 猜测 → 生成 → 不满意 → 反复迭代

frontend-slides 做法：
  AI 生成 3 个预览选项 → 用户选 → 一次命中
```

**可迁移场景**：
- tech-article skill：不问"你想要什么风格的文章"，而是生成 2 段不同风格的开头预览
- md2wechat：不问"你想要什么排版"，而是生成 3 个排版预览片段
- 任何涉及"风格选择"的 skill，都可以用这个模式替代抽象的 Q&A

---

### 模式三：Mode Detection as Phase 0（模式检测前置）

Skill 第一步不是问问题，而是先判断用户意图：

```
Phase 0: 检测模式
  → 新建演示文稿（Phase 1）
  → PPT 转换（Phase 4）
  → 增强已有（Mode C）
```

好处：不同意图走完全不同的路径，不会把 PPT 转换用户拖进"样式发现"流程。

**对比 insight-collector**：现在 insight-collector 无论什么输入都走同一条路。
如果输入是"帮我分析这段代码有没有值得归档的内容"和"收录这个 URL"，其实是两种不同意图，可以前置检测。

---

## 可复用的技术规则

### Viewport 强制适配规则（做任何 HTML 演示时都适用）

```css
/* 每一张幻灯片必须 */
.slide {
    height: 100vh;
    overflow: hidden;  /* 绝不允许内部滚动 */
}

/* 所有尺寸用 clamp，禁用固定像素 */
font-size: clamp(1rem, 2.5vw, 1.5rem);
max-height: min(50vh, 400px);  /* 图片上限 */

/* 响应式断点 */
@media (max-height: 700px) { ... }
@media (max-height: 600px) { ... }
@media (max-height: 500px) { ... }
```

### 内容密度上限（防止 AI 塞太多内容）

| 幻灯片类型 | 内容上限 |
|-----------|---------|
| 标题页 | 1 标题 + 1 副标题 |
| 内容页 | 1 标题 + 4-6 条 bullet |
| 功能网格 | 1 标题 + 6 张卡片 |
| 文字段落 | 1 标题 + 2 段文字 |

### CSS 负值陷阱

```css
/* ❌ 错误：前导负号会被静默忽略 */
margin-top: -clamp(1rem, 2vw, 2rem);

/* ✅ 正确 */
margin-top: calc(-1 * clamp(1rem, 2vw, 2rem));
```

### Accessibility：所有动画必须尊重用户设置

```css
@media (prefers-reduced-motion: reduce) {
    * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

---

## 12 种风格速查（供 md2wechat / 文章排版参考）

| 风格 | 基调 | 代表色 | 字体组合 |
|------|------|--------|---------|
| Bold Signal | 深色+强调 | #FF5722 on #1a1a1a | Archivo Black + Space Grotesk |
| Electric Studio | 极简深色 | #4361ee on #0a0a0a | Manrope |
| Creative Voltage | 赛博朋克 | #0066ff + #d4ff00 | Syne + Space Mono |
| Dark Botanical | 深色有机 | #c9b896 on #0f0f0f | Cormorant + IBM Plex Sans |
| Notebook Tabs | 纸质标签 | 5色 pastel | Bodoni Moda + DM Sans |
| Pastel Geometry | 几何粉彩 | #c8d9e6 | Plus Jakarta Sans |
| Split Pastel | 双色分割 | peach + lavender | Outfit |
| Vintage Editorial | 复古杂志 | #f5f3ee + #e8d4c0 | Fraunces + Work Sans |
| Neon Cyber | 霓虹科技 | cyan/magenta on navy | — |
| Terminal Green | 终端风 | green on dark | monospace |
| Swiss Modern | 包豪斯 | black/white + #ff3300 | — |
| Paper & Ink | 纸墨 | cream/charcoal | serif |

---

## 延伸方向

1. **把 Show Don't Tell 模式引入 tech-article skill** — 在 Stage 2 提供 2 种开头草稿供选择，而不是问抽象的"风格偏好"
2. **把内容密度规则用于公众号排版** — md2wechat 可以加类似的"每节最多 N 个 bullet"约束
3. **Viewport 规则提取为 html-tools 的通用基座** — 凡是 html-tools/ 下新增 HTML 工具，都引用这套响应式基础规则

---

## 参考链接

- 仓库主页：https://github.com/zarazhangrui/frontend-slides
- SKILL.md 原文：https://raw.githubusercontent.com/zarazhangrui/frontend-slides/main/SKILL.md
- 相关：`analysis/pi-context-engineering.md`（同一个 Progressive Disclosure 模式）
