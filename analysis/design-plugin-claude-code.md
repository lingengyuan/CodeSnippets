# 0xdesign/design-plugin 精读

**来源**: [0xdesign/design-plugin](https://github.com/0xdesign/design-plugin)
**日期**: 2026-03-09
**标签**: claude-code-plugin, ui-design, design-system, feedback-overlay, design-memory, agentic-workflow

---

## 30秒 TL;DR

> 一个 Claude Code 插件，把 UI 设计评审流程变成一个 agent 驱动的迭代循环：访谈需求 → 从你的代码库推断视觉语言 → 生成 5 个不同维度的变体 → 在你的 dev server 注入 Figma 风格的点击反馈覆盖层 → 综合你喜欢的部分 → 输出实施计划。**核心洞见：agent 不带预设样式，完全从你的 Tailwind config / CSS variables / 现有组件中提取视觉语言。**

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| 视觉语言推断（Style Inference）| 读 tailwind.config、CSS variables、扫描 2-3 个现有组件，提取颜色/字体/间距/圆角 | 任何需要与现有设计系统保持一致的代码生成 |
| 5 轴变体生成 | A=信息层级、B=布局模型、C=密度、D=交互模式、E=品牌表达 | 探索设计方案空间时的固定维度框架 |
| FeedbackOverlay | 在 dev server 注入 Figma 风格点击评论层，输出带 CSS selector 的结构化反馈 | 让 agent 知道"用户在说哪个元素" |
| DESIGN_MEMORY.md | 跨会话积累品牌决策：密度偏好、颜色策略、交互规范 | 加速后续设计会话，避免重复访谈 |
| design-brief.json | 访谈 → JSON artifact → 变体生成的源头 | 结构化需求捕获 |
| SessionEnd 钩子 | hooks.json 注册 SessionEnd/Stop 事件，自动检查并清理临时文件 | Claude Code 插件文件生命周期管理 |
| `__design_lab` 路由 | 临时注入 dev server 路由，用完即删 | Agent 在用户环境中"借用"基础设施而不永久改变它 |
| NEVER start dev server | 显式禁止 agent 运行 `pnpm dev`（会永久阻塞） | 长运行进程的 agent 防卡死模式 |

---

## 深读

### 插件文件结构

```
design-and-refine/
├── commands/
│   ├── start.md       # /design-and-refine:start 入口
│   └── cleanup.md     # /design-and-refine:cleanup 入口
├── hooks/
│   └── hooks.json     # SessionEnd/Stop → cleanup-check.sh
├── scripts/
│   └── cleanup-check.sh
├── skills/
│   └── design-lab/
│       ├── SKILL.md           # 完整工作流（~900行）
│       └── DESIGN_PRINCIPLES.md  # Nielsen 10 启发式 + 设计系统参考
└── templates/
    ├── DESIGN_PLAN.template.md
    ├── DESIGN_MEMORY.template.md
    └── feedback/
        ├── FeedbackOverlay.tsx    # Figma 风格覆盖层（React）
        ├── selector-utils.ts      # CSS selector 生成
        ├── format-utils.ts        # 反馈格式化
        ├── types.ts
        └── index.ts
```

### 完整工作流（8 阶段）

```
Phase 0: Preflight     — 检测框架(Next/Vite/Remix)、包管理器、样式系统
Phase 1: Interview     — AskUserQuestion 结构化访谈（5步：范围→痛点→灵感→品牌→约束）
Phase 2: Design Brief  — 访谈结果 → .claude-design/design-brief.json
Phase 3: Lab 生成      — 5个变体 + FeedbackOverlay → __design_lab 路由
Phase 4: 呈现          — 输出 URL，不启动服务器（关键！）
Phase 5: 反馈收集      — 交互式(点击评论) or 手动(文字描述)
Phase 6: 综合变体      — 把用户喜欢的元素合并成 Variant F
Phase 7: 最终预览      — __design_preview 路由，before/after 对比
Phase 8: 收尾          — 清理所有临时文件 + 生成 DESIGN_PLAN.md + 更新 DESIGN_MEMORY.md
```

### FeedbackOverlay 的技术实现

FeedbackOverlay 是整个插件最精妙的部分：

1. 用户点击"Add Feedback"按钮进入反馈模式
2. 点击任意 DOM 元素 → 生成 CSS selector（用 `selector-utils.ts`）
3. 在点击位置弹出评论输入框
4. 点击"Submit All Feedback" → 格式化为结构化 markdown → 复制到剪贴板
5. 用户粘贴回终端 → agent 用 CSS selector 定位元素并修改

反馈格式：
```markdown
## Design Lab Feedback
**Target:** ComponentName
### Variant A
1. **Button** (`[data-testid='submit']`, button with "Submit")
   "Make this more prominent"
### Overall Direction
Go with Variant B's structure...
```

**关键设计决策**：FeedbackOverlay 放在与 `page.tsx` 同目录（不是 `.claude-design/`），用相对 import，避免 bundler 路径问题。

### Visual Style Inference（最重要的设计决策）

```
SKILL.md 第 59 行："DO NOT use generic/predefined styles. Extract visual language from the project."
```

具体做法：
- Tailwind：读 `tailwind.config.js` 的 `theme.colors`, `theme.spacing`, `theme.borderRadius`, `theme.fontFamily`
- CSS Variables：读 `globals.css`/`variables.css` 中的 `:root` 自定义属性
- UI 库：读 `createTheme()` / `extendTheme()` / `ConfigProvider` 配置
- 总是扫描现有 2-3 个 Button、Card、Form，提取实际使用模式

### 5 个变体轴（固定框架）

| 变体 | 探索轴 | 关键问题 |
|------|-------|---------|
| A | 信息层级 | 最重要的信息是什么？Gestalt 邻近法则 |
| B | 布局模型 | Card vs List vs Table vs Split-pane |
| C | 信息密度 | Compact vs Spacious，与 brief 相反方向 |
| D | 交互模式 | Modal vs Inline vs Panel vs Drawer |
| E | 品牌表达 | 推到品牌方向极端，探索设计语言边界 |

### hooks.json：SessionEnd 自动清理

```json
{
  "hooks": {
    "SessionEnd": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-check.sh"}],
    "Stop": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-check.sh"}]
  }
}
```

这是 Claude Code 插件生命周期钩子的典型用法：用 SessionEnd 事件兜底清理临时文件，即使用户中途关闭了会话。

---

## 心智模型

> **"Agent 借用你的环境做实验，而不是在旁边建一个独立的预览系统。"**

`__design_lab` 路由直接注入到你正在运行的 dev server，使用你真实的组件库、CSS 变量、设计 token。这意味着变体在真实上下文中渲染，不是模拟环境。

**适用条件**：项目有 dev server、有实际的设计系统（Tailwind config 或 CSS variables）、框架可以动态添加路由

**失效条件**：
- 没有运行 dev server（plugin 不会帮你启动）
- 纯静态站点，路由不可动态添加
- 设计系统完全在运行时注入（无静态 config 可读）

---

## 非显见洞见

### 洞见 1：样式推断 > 样式预设，解决了 AI 生成 UI "总是一个味道"的根本问题

- **洞见**：所有 AI 工具生成 UI 都有统一的 "AI 审美"（过度使用 gradient、圆角、蓝色）。这个插件的关键是从你的代码库推断视觉语言，而不是用预设模板
  - 所以：在一个使用 Inter 字体、4px 圆角、灰色主题的项目里，生成的 5 个变体都会继承这些约束
  - 所以：用户看到的变体不是"AI 风格"，而是"我的设计系统风格的 5 种不同表达"
  - 因此可以：把这个样式推断逻辑（读 tailwind.config → 提取 token → 存入 design-brief.json）单独提取，用于任何需要"按现有设计系统生成代码"的场景

### 洞见 2：DESIGN_MEMORY.md 是把隐性设计知识变成显性的机制

- **洞见**：设计团队的"约定俗成"（这个产品用 inline validation 不用 modal，密度偏 compact）通常只活在脑子里。DESIGN_MEMORY.md 把每次设计会话的决策固化成文件
  - 所以：第二次用插件时，已知偏好可以跳过访谈，直接根据 Memory 生成
  - 所以：DESIGN_MEMORY.md 随时间积累，变成团队设计规范的"活文档"
  - 因此可以：把 DESIGN_MEMORY.md 提交进 git，让整个团队的 agent 会话共享设计约束

### 洞见 3：FeedbackOverlay 的 CSS selector 是 agent 与 UI 之间的精确坐标系

- **洞见**：当用户说"我喜欢 B 的按钮风格"，agent 不知道指的是哪个按钮。FeedbackOverlay 生成的 `[data-testid='submit']` 或 `.product-card > button:first-child` 提供了精确的 DOM 地址
  - 所以：agent 在修改时不需要猜测，直接定位元素
  - 所以：这个"结构化反馈 + 元素选择器"的模式可以用于任何 agent-UI 交互场景（不只是设计）
  - 因此可以：把 FeedbackOverlay 模式推广为"agent 辅助 UI 问题诊断工具"：用户点击有 bug 的元素，自动生成带 selector 的 bug report

### 洞见 4：不启动 dev server 是 agent 防卡死的工程规范，不是妥协

- **洞见**：SKILL.md 明确写："Do NOT attempt to start the dev server yourself (it runs forever and will block)"。这不是功能缺失，是对长运行进程会阻塞 agent 的显式知识
  - 所以：任何需要启动服务器/后台进程的 agent 工作流，都应该把"启动"这步留给人类，agent 只做之前和之后的部分
  - 所以：这个约束要写进 skill/prompt，不能靠 agent 自己推断（agent 不知道 `npm run dev` 会阻塞）
  - 因此可以：在 mini_symphony 的 WORKFLOW.md 中加一条明确约束："不要运行任何长运行进程（dev server、watch 模式、tail -f）"

---

## 隐含假设

- **假设 1：用户已有 dev server 在跑**。若不成立，整个 Phase 4-7 无法预览。应对：Phase 4 提示用户启动，提供具体命令
- **假设 2：框架可以通过添加文件来新增路由**（Next.js App Router 的文件系统路由）。若使用手动路由配置（如 React Router v5），需要修改 `App.tsx`，plugin 有处理但复杂
- **假设 3：设计系统有静态 config 可读**（tailwind.config.js 或 CSS variables）。若团队把 token 全放 JS runtime（如 stitches 的 JS-in-CSS），推断会失败
- **假设 4：5 个变体轴覆盖了用户真正想探索的设计空间**。有时用户关心的是"动画效果"或"数据可视化方式"，这 5 轴都不覆盖

---

## 反模式与陷阱

- **陷阱：FeedbackOverlay 放在 `.claude-design/` 而不是路由目录**
  → bundler 路径解析可能失败，整个交互式反馈系统瘫痪
  → 正确做法：FeedbackOverlay.tsx 与 page.tsx 同目录，用 `./FeedbackOverlay` 相对 import

- **陷阱：忘记在变体容器加 `data-variant="A"` 属性**
  → FeedbackOverlay 无法识别反馈属于哪个变体
  → 正确做法：所有变体外层 div 必须有 `data-variant` 属性

- **陷阱：把 results.tsv / DESIGN_MEMORY.md 设为 gitignored**
  → 团队成员的下次会话无法利用已有的设计决策
  → 正确做法：DESIGN_MEMORY.md 提交进 git，`.claude-design/` 加入 .gitignore

- **陷阱：在 Synthesis 阶段生成 Variant F 时完全替换 Design Lab**
  → 用户无法再比较 F 与原始变体
  → 正确做法：保留 1-2 个最接近的原始变体用于对比

---

## 与现有知识库的连接

- 关联 `analysis/simon-willison-hoard-things.md`：DESIGN_MEMORY.md 是"囤积你知道如何做的事"在 UI 设计领域的具体实现——每次设计决策都沉淀到文件，而不是留在脑子里或重新在下次访谈中发现

- 关联 `python/mini_symphony.py`：design-brief.json 和 mini_symphony 的 TASKS.md 都是"访谈/规划 → 结构化 artifact → 执行"的三段式。不同的是 design-brief 是单任务的需求捕获，TASKS.md 是多任务队列

- 关联 `analysis/pi-context-engineering.md`：DESIGN_PRINCIPLES.md（Nielsen 10 启发式 + 8px grid + 动效时间等）是"专家知识注入 context"的典型做法。pi agent 把 context engineering 的决策写进 system prompt，这里把设计原则写进 skill 文档

- 关联 `analysis/karpathy-autoresearch.md`：两个项目都使用 SessionEnd 钩子做清理，体现了"临时工件 + 自动清理"的工程模式。autoresearch 通过 git reset 清理，design-plugin 通过文件删除清理

---

## 衍生项目想法

### 想法 1：把 FeedbackOverlay 做成通用的 Agent-UI 坐标系工具

**来源组合**：[FeedbackOverlay 的 CSS selector 生成机制] + [mini_symphony.py 的 issue/bug 任务队列]

**为什么有意思**：目前 bug 报告通常是"第三个按钮不对"这种模糊描述。FeedbackOverlay 的核心创新是把用户的视觉定位（点击）转化为精确的 DOM 地址（CSS selector）。这个机制可以独立于设计场景使用：用户点击有 bug 的 UI 元素 → 自动生成 `{ selector, elementDescription, screenshotContext }` → 作为 mini_symphony 的任务输入

**最小 spike**：把 FeedbackOverlay.tsx 改造成 BugReport 模式（去掉"Design Lab"概念），注入到任何 localhost 页面，点击后生成结构化 bug report JSON 并复制到剪贴板

**潜在难点**：CSS selector 自动生成的稳定性（dynamically-generated class names 会让 selector 失效）

---

### 想法 2：DESIGN_MEMORY.md 作为项目级设计规范的"活文档"

**来源组合**：[DESIGN_MEMORY.md 跨会话积累] + [analysis/simon-willison-hoard-things.md 的囤积体系]

**为什么有意思**：大多数团队的设计规范要么是 Figma 里的 "Design System"（需要手动同步到代码），要么是 Confluence 文档（永远过时）。DESIGN_MEMORY.md 的特别之处是它**在代码仓库里**、**由 agent 在做设计决策时自动更新**、**直接影响下次设计生成**——形成闭环

→ 所以：提交到 git 的 DESIGN_MEMORY.md 对团队所有成员可见，PR review 时可以审查设计决策
→ 因此可以：把 DESIGN_MEMORY.md 的格式标准化，加进公司的项目模板，像 CLAUDE.md 一样在项目初始化时创建

**最小 spike**：在一个现有项目跑两次 design-plugin 会话，检查 DESIGN_MEMORY.md 的积累是否真正帮助第二次会话跳过了冗余访谈

**潜在难点**：DESIGN_MEMORY.md 随时间变大，影响 context window；需要定期精简

---

### 想法 3：Style Inference 模块作为独立工具

**来源组合**：[design-plugin 的 Visual Style Inference 逻辑] + [python/snippet_manager.py 的 LLM prompt 组合]

**为什么有意思**：Visual Style Inference（读 tailwind.config → 提取 token → 汇总成"设计系统摘要"）是一个有独立价值的工具，不只用于 UI 变体生成。任何需要"按你的设计系统风格生成代码"的场景都可以用：生成 email 模板、生成 landing page、生成 PDF 报告

**最小 spike**：写一个 Python 脚本，接收项目根目录，检测并输出一段"设计系统摘要" markdown（提取 Tailwind token / CSS variables），可直接粘贴进任意 LLM prompt

**潜在难点**：不同项目的 tailwind.config 结构差异很大（有的用 extend，有的直接覆盖 defaults）
