# =============================================================================
# 名称: Interactive Explanation Prompt Template
# 来源: https://simonwillison.net/guides/agentic-engineering-patterns/interactive-explanations/
# 用途: 为难以直觉理解的算法生成可视化 HTML 动画，消除线性导读后的认知盲区
# 依赖: Claude Code / any coding agent with web access; Showboat (uvx showboat)
# 适用场景: 时序性算法（布局、搜索、排序、物理模拟）；核心算法在线性导读后仍无直觉理解
# 日期: 2026-07-13
# =============================================================================

## 何时使用交互式解释

**判断规则**（满足任一条件即触发）：
- 读完 walkthrough.md 仍然无法在脑海中"播放"这个过程
- 算法包含时序性/空间性步骤（螺旋放置、图遍历、排序、碰撞检测）
- 需要向他人解释这个算法，文字说不清楚

**不适用场景**：
- CRUD、数据映射、配置解析（文字足够）
- 算法外部已有充分可视化资料（经典排序算法）
- 一次性脚本，生命周期极短

---

## Step 1：先生成线性导读（Linear Walkthrough）

交互式解释**依赖**线性导读作为上下文输入。务必先完成此步。

```
Read the source and then plan a linear walkthrough of the code that
explains how it all works in detail.

Then run "uvx showboat --help" to learn showboat - use showboat to
create a walkthrough.md file in the repo and build the walkthrough
in there, using showboat note for commentary and showboat exec plus
sed or grep or cat or whatever you need to include snippets of code
you are talking about.
```

> **关键**：要求 Agent 用 `sed/grep/cat` 引用真实代码片段，**禁止手动复制代码**，
> 防止 Agent 在复制时引入细微错误（变量名改动、逻辑细节遗漏）。

---

## Step 2：生成交互式解释 HTML

以下是可填空的模板（`[...]` 部分按实际情况替换）：

```
Fetch [walkthrough.md 的 raw URL 或本地路径] to /tmp using curl
so you can read the whole thing.

Inspired by that, build [output-filename].html - a self-contained
page that visualizes [算法名称，如 "the Archimedean spiral word
placement algorithm"] using the algorithm described in that document,
animated to make the algorithm as clear to understand as possible.

Include:
- Animation controls: play/pause button, speed slider, frame-by-frame
  stepping while paused
- [输入控件，如：a text input area that accepts pasted text; persists
  in the URL #fragment so the page auto-submits on load with that input]
- A download button to save the current visualization state as PNG
- [如需要：labels/annotations showing what each step is doing]

Use canvas for the animation. Make the visualization teach the
algorithm, not just show the result.
```

### 本地 walkthrough 的变体（不通过 URL fetch）

```
Read [walkthrough.md 的本地路径] for the algorithm details.

Build [output-filename].html - a self-contained animated visualization
of [算法名称] that makes the algorithm's step-by-step process
intuitively clear. [接上方的 Include 部分]
```

---

## 生成的 HTML 质量检查清单

在接收 Agent 输出后，检查以下项目：

- [ ] **单文件自包含**：可以直接双击 .html 打开，无需服务器
- [ ] **Canvas 动画**：用 `<canvas>` 渲染，而非静态图片序列
- [ ] **播放控制**：至少有 play/pause 和速度调整
- [ ] **逐帧步进**：暂停时可以一帧一帧手动推进（学习关键时刻）
- [ ] **视觉注解**：动画中有文字标注当前在执行的步骤（否则只是"看"而非"理解"）
- [ ] **URL 状态持久**：如果有用户输入，存入 `#fragment`（刷新不丢失、可分享）
- [ ] **PNG 下载**：可以把理解瞬间固定为截图

---

## 实际案例参考

Simon Willison 的词云算法动画演示：
- 工具地址：https://tools.simonwillison.net/animated-word-cloud
- 算法：Archimedean 螺旋放置（每个词沿螺旋寻找不与已放置词重叠的位置）
- 模型：Claude Opus 4.6（在解释性动画方面"品味不错"）
- 原始 walkthrough：https://raw.githubusercontent.com/simonw/research/refs/heads/main/rust-wordcloud/walkthrough.md

---

## 持久化建议

- 把核心算法的交互式解释 HTML 保存到 `html-tools/` 目录（可复用、可分享）
- 把 walkthrough.md 提交到 repo（后续 session 可作为 context 资产重复使用）
- 在 PR description 中链接可视化页面（替代文字算法描述）

---

## 认知债务分级（配套决策规则）

| 代码类型 | 认知债务风险 | 处理方式 |
|---------|------------|---------|
| CRUD、数据获取、配置解析 | 低 | 接受，或瞄一眼代码 |
| 多步骤业务逻辑 | 中 | 线性导读即可 |
| 核心算法（时序/空间/递归） | 高 | 线性导读 → 交互式解释 |
| 应用架构（多模块协作） | 高 | 线性导读（重点讲模块边界） |

---

## 相关文档

- `analysis/simon-willison-interactive-explanations.md` — 完整精读（含蕴含链、反模式、衍生想法）
- `analysis/simon-willison-agentic-patterns.md` — 系列总览
- `analysis/simon-willison-red-green-tdd.md` — 与 TDD 并列的 Agent 输出质量管理机制
