# Agentic Engineering Anti-patterns 精读

**来源**: [Anti-patterns: things to avoid](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/)
**日期**: 2026-03-09
**标签**: agentic-engineering, code-review, pr-hygiene, collaboration, validation, professional-ethics

---

## 30秒 TL;DR

> Agent 让写代码的成本降到接近零，但**验证代码的成本没有变**——这个不对称在 PR 提交中表现得最明显。核心反模式是"把验证工作外包给代码审查者"。你的价值 = 上下文 + 判断力 + 验证，而不是代码生成速度。

---

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| 未审查 PR 反模式 | 提交 AI 代码但未自己验证 = 把实际工作转嫁给审查者 | 任何 AI 辅助协作开发 |
| 验证证据原则 | PR 必须包含你已做过验证的证据（测试记录、截图、视频） | PR 提交标准流程 |
| PR 粒度纪律 | Agent 让拆 commit 变容易，大 PR 的最后借口消失了 | PR 最佳实践 |
| Description 审查 | AI 生成的 PR description 看起来合理但可能错误，你必须亲自验证 | 所有 AI 辅助 PR |

---

## 深读

### 反模式一：Inflicting Unreviewed Code on Collaborators（把未审查代码强加给协作者）

**具体表现**：提交含数百/数千行 AI 代码的 PR，但自己没有做过验证。

**为什么这是个问题**：
- 你把实际工作（验证代码是否可行）转嫁给了审查者
- 审查者本可以自己去 prompt agent——你没有提供任何增量价值
- PR description 由 AI 生成 + 未验证 = 审查者需要花时间 + 你的 description 没有信用

**好的 Agentic PR 特征清单**：
1. **代码能跑**，且你确信它能跑（[你的工作是交付能跑的代码](https://simonwillison.net/2025/Dec/18/code-proven-to-work/)）
2. **变更足够小**，可以高效审查。多个小 PR > 一个大 PR；用 agent 做 git 拆分不再有摩擦
3. **包含背景说明**：这个变更服务于什么更高层目标？链接相关 issue 或 spec
4. **亲自审查 AI 生成的 PR description**：它写得很像样，但这正是危险所在

**留下验证证据**：手动测试记录、实现选择的注释、截图、视频——这些大幅提升你的 PR 可信度，向审查者证明他们的时间不会被浪费。

---

## 心智模型

> **在 AI 时代，开发者的价值 = 上下文 + 判断力 + 验证，而不是代码生成速度。**

**适用条件**：存在代码审查的协作开发场景
**失效条件**：solo 项目、无代码审查流程、完全信任 AI 输出的环境
**在我的工作中如何用**：每次提交 AI 辅助 PR 时，强制问自己"我提供了什么价值是 reviewer 自己 prompt 得不到的？"

---

## 非显见洞见

- **洞见**：`"They could have prompted an agent themselves"` 是最尖锐的价值测试
  - 所以：如果你只是 prompt 转发，你没有提供任何价值
  - 所以：在 AI 时代，PR 的价值完全在于你的判断和验证层，不在于代码本身
  - 因此可以：把这句话作为每次提交 AI PR 的自问：我的贡献是什么？

- **洞见**：PR description 由 AI 生成时"看起来更有说服力"，这本身是风险，不是好事
  - 所以：外表上合理的 PR description 不等于内容被理解和验证
  - 所以：AI 时代 PR description 的可信度下降，需要额外信号（如验证证据）来补充
  - 因此可以：建立"哪些部分必须由人亲自写"的规则，至少 description 中的"测试方法"部分

- **洞见**：拆分 PR 的主要摩擦来源（手动 git 操作）现在被 agent 消除了
  - 所以："大 PR 难拆分"的借口彻底无效
  - 所以：继续提交大 PR 意味着主动选择了更差的流程，而不是被迫
  - 因此可以：把 PR 粒度纪律作为团队规则强制执行，agent 来做机械拆分

---

## 隐含假设

- **有协作团队**：若不成立（solo 项目），这些规则大多不适用
- **AI 代码可能包含错误**：若完全信任 AI 输出，验证的动机弱化
- **Reviewer 的时间是有限且宝贵的**：若无限时间/成本，外包验证的危害降低

---

## 反模式总结

| 反模式 | 具体表现 | 危害 | 修正做法 |
|-------|---------|------|---------|
| **Prompt 转发** | AI 生成代码直接提交，不验证 | 把验证成本转嫁审查者 | 亲自运行/测试，留下验证记录 |
| **Description 外包** | 不读 AI 生成的 PR description | 描述可能不准确，审查者被误导 | 亲自重写或验证 description |
| **大块转储** | 几千行 AI 代码作为单个 PR | 审查成本爆炸，质量无法保证 | 拆成多个小 PR，agent 做 git |

---

## 与现有知识库的连接

- 关联 `analysis/simon-willison-red-green-tdd.md`：Red/Green TDD 是**生成验证证据**的系统方法——测试通过截图就是最好的 PR 验证证据
- 关联 `analysis/simon-willison-first-run-tests.md`："First Run the Tests" 是接手已有代码库时的验证起点，直接减少"不了解代码就提 PR"的情况
- 关联 `analysis/simon-willison-linear-walkthroughs-manual-testing.md`：Agentic Manual Testing 生成的 Showboat 演练记录 = 最好的 PR 验证证据格式
- 关联 `python/mini_symphony.py`：编排器执行每个任务后可以自动要求生成"验证日志"——将反模式修正融入工作流

---

## 衍生项目想法

### PR 验证 Checklist 自动化

**来源组合**：[本次"必须留下验证证据"原则] + [`templates/WORKFLOW.md.template` 的 checklist 结构] + [`analysis/simon-willison-linear-walkthroughs-manual-testing.md` 的 Showboat 记录模式]
**为什么有意思**：验证证据生成不应该是手动步骤，而应该是工作流的必须输出。把"运行测试、截图、写记录"变成 agent task 的标准 exit criteria。
**最小 spike**：在 `templates/WORKFLOW.md.template` 中加一个 `EXIT_CRITERIA` 字段，要求 agent 在 task 完成时生成验证日志（测试结果 + 关键截图路径）
**潜在难点**：截图自动化需要额外工具（Playwright 或 Showboat），纯文本项目的验证证据格式标准化

### Agent PR 粒度守卫

**来源组合**：[本次"Several small PRs"纪律] + [已有 `python/sandbox_execute.py` 的 budget 控制模式]
**为什么有意思**：给 agent 编排器加一个"PR size budget"——如果 git diff 超过 N 行，自动触发拆分子任务而不是继续堆积
**最小 spike**：在 `mini_symphony.py` 的 task 完成检测中加 `git diff --stat` 行数检查，超过阈值时生成拆分建议
**潜在难点**：自动拆分逻辑需要理解代码语义，纯行数判断可能误触发
