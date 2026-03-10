# Ruff Python Linter & Formatter 精读

**来源**: [astral-sh/ruff](https://github.com/astral-sh/ruff)
**日期**: 2026-03-09
**标签**: python, linter, formatter, rust, tooling, code-quality, pre-commit

---

## 30秒 TL;DR

> Ruff 是用 Rust 写的 Python linter + formatter，比 Flake8 快 10-100x，一个工具替代 Flake8+插件、Black、isort、pyupgrade、pydocstyle、autoflake。最重要的不是速度，而是三件事：**`--add-noqa` 的渐进式迁移策略**、**`RUF100` 的 noqa 技术债追踪**、以及 **B023（闭包 bug）、B006（可变默认参数）等真正捉虫的规则**。

## 概念总览

| 概念/模式 | 核心思想 | 适用场景 |
|---------|---------|---------|
| 单工具替代 7 个 | Flake8+plugins+Black+isort+pyupgrade+pydocstyle+autoflake | 任何 Python 项目的 CI/tooling 简化 |
| Safe vs Unsafe fix | Safe: 不改变行为；Unsafe: 可能改变异常类型等 | 自动修复时的风险控制 |
| `--add-noqa` 迁移 | 全量插入 noqa 注释，再逐步清除 | 存量代码库接入 ruff 而不破坏 CI |
| `RUF100` unused-noqa | 检测并删除过时的 noqa 注释 | 防止 noqa 注释本身成为技术债 |
| `extend` 继承配置 | 子目录 config 继承父 config，局部覆盖 | Monorepo 分目录差异配置 |
| `target-version` 回退 | 未设置时自动读 `requires-python` | 不需要手动同步 Python 版本声明 |
| 退出码设计 | `--exit-non-zero-on-fix`：即使修复了也返回 1 | CI 强制要求提交代码不含违规 |

---

## 深读

### 最小可用配置（pyproject.toml）

```toml
[tool.ruff]
line-length = 88
target-version = "py310"          # 或省略，自动从 requires-python 推断

[tool.ruff.lint]
select = [
    "E4", "E7", "E9",             # pycodestyle errors（严重级别）
    "F",                          # Pyflakes（未使用导入、未定义名字）
    "B",                          # flake8-bugbear（真正的 bug，不只是风格）
    "I",                          # isort（导入排序）
    "UP",                         # pyupgrade（Python 3 现代化）
    "RUF",                        # Ruff 特有规则
]
ignore = [
    "E501",                       # 行长度（formatter 会处理，linter 不要重复）
]
fixable = ["ALL"]
unfixable = [
    "F401",                       # 未使用导入：不自动删，可能是 re-export
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]          # __init__.py 里的导入通常是 re-export
"tests/**" = ["S101"]            # 测试文件允许用 assert

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
```

### 规则分类与价值排序

| 前缀 | 来源 | 核心价值 | 是否默认启用 |
|-----|-----|---------|-----------|
| `F` | Pyflakes | 未使用导入/变量、未定义名字——真正的错误 | 是（部分） |
| `E`, `W` | pycodestyle | PEP8 风格，`E4/E7/E9` 是严重错误 | 是（部分） |
| `B` | flake8-bugbear | 可变默认参数、循环闭包、groupby 迭代器陷阱 | **否，需手动加** |
| `I` | isort | 导入排序 | **否** |
| `UP` | pyupgrade | `f-string`、`typing.Optional` → `X \| None`等 | **否** |
| `N` | pep8-naming | 命名规范（类大写、常量大写等） | 否 |
| `S` | flake8-bandit | 安全漏洞（eval、pickle、subprocess shell=True）| 否 |
| `RUF` | Ruff 原生 | unused-noqa (RUF100)、Python 特有 gotcha | 是（部分） |
| `PL` | Pylint | 更深层的逻辑错误 | 否 |

**最重要的 bug-catching 规则**（不只是风格）：

```
B006: 可变默认参数            def foo(x=[]):  → 所有调用共享同一个 list
B023: 循环变量未绑定到闭包     [lambda: i for i in range(3)]  → 全部返回 2
B031: groupby 迭代器多次使用   groupby() 的 group 是懒加载迭代器，只能消费一次
F601: 字典字面量重复 key       {"a": 1, "a": 2}  → 第一个 "a" 被静默覆盖
RUF015: 低效的首元素访问       list(range(n))[0]  → next(iter(range(n)))
```

### noqa 语法速查

```python
# 行级抑制
x = 1  # noqa: F841                    # 抑制单条规则
x = 1  # noqa: E741, F841             # 抑制多条规则
x = 1  # noqa                         # 抑制全部（不推荐）

# 块级抑制（需要相同缩进的 enable 配对）
# ruff: disable[E501]
VERY_LONG_LINE = "..."
# ruff: enable[E501]

# 文件级抑制（放文件顶部）
# ruff: noqa: F841
```

**isort 特有指令**（B 规则的导入控制）：
```python
import os  # isort: skip
# isort: skip_file
```

### 关键 CLI 用法

```bash
# 基础
ruff check .                          # 检查
ruff check . --fix                    # 自动修复（仅 safe fixes）
ruff check . --fix --unsafe-fixes     # 包含 unsafe fixes

# 格式化（独立命令）
ruff format .                         # 格式化
ruff format . --check                 # 只检查，不修改（CI 用）
ruff format . --diff                  # 显示 diff

# 迁移工具
ruff check . --add-noqa               # 批量插入 noqa（迁移大型代码库）
ruff check . --extend-select RUF100 --fix  # 清理过时的 noqa 注释

# 调试
ruff check file.py --select B023 --explain B023  # 查看规则说明
ruff check . --statistics            # 按规则统计违规数量（迁移规划用）
```

### CI 集成的退出码陷阱

```bash
# ⚠️ 这个配置有 bug！
ruff check . --fix      # 修复了问题，退出码 0 → CI 通过
# 但修复后的文件没有提交！下次还会有同样的问题

# ✅ 正确的 CI 配置：不做修复，只检查
ruff check .            # 有违规 → 退出码 1 → CI 失败
ruff format . --check   # 格式不对 → 退出码 1 → CI 失败

# 或者如果要用 --fix，加这个标志：
ruff check . --fix --exit-non-zero-on-fix
# 这样即使 fix 了也返回 1，提示"有问题被修复了，请 git add 后再提交"
```

### Monorepo 配置继承

```toml
# 根目录 pyproject.toml
[tool.ruff]
line-length = 88
[tool.ruff.lint]
select = ["E", "F", "B"]

# packages/api/pyproject.toml
[tool.ruff]
extend = "../../pyproject.toml"  # 继承根配置
line-length = 100                # 局部覆盖

[tool.ruff.lint]
extend-select = ["S"]            # 额外加安全规则（不覆盖父 select）
```

### Safe/Unsafe Fix 重分类

可以在项目级别调整哪些 fix 是"safe"的：

```toml
[tool.ruff.lint]
extend-safe-fixes = ["UP034"]   # 把这条规则的 fix 降低为 safe（你相信它不会破坏行为）
extend-unsafe-fixes = ["F401"]  # 把删除未使用导入升级为 unsafe（谨慎处理 re-exports）
```

---

## 心智模型

> **"速度是免费的副作用，真正的价值是把 7 个工具的知识压缩进一个接口。"**

Ruff 不是"更快的 Flake8"，它是一个工具链整合器。团队不再需要知道 isort 的配置语法、black 的行为、pyupgrade 支持哪些 Python 版本——全部统一到 `[tool.ruff]`。

**适用条件**：Python 项目，需要代码质量保证，特别是大型代码库（Flake8 太慢、多工具配置太复杂）

**失效条件**：
- 需要 Flake8 的自定义插件生态（Ruff 没有插件 API，只有内置规则）
- 需要 mypy/pyright 的类型检查（Ruff 不做类型推断，只做语法/风格/简单流分析）

---

## 非显见洞见

### 洞见 1：`--add-noqa` 是大型代码库迁移的解锁钥匙

- **洞见**：对一个有 10万行历史代码的项目，直接启用 ruff 会产生数千条违规。修复所有违规需要数周，但保持 CI 一直红灯也不现实
  - 所以：`ruff check . --add-noqa` 一键在所有违规行插入 `# noqa: RULE` 注释，让 CI 立刻变绿
  - 所以：之后每次有人修改文件，可以顺手清理该文件的 noqa，逐步减少技术债（而不是一次性大爆炸）
  - 因此可以：把这个模式写成标准"工具迁移 SOP"：1) 添加工具到 CI 2) `--add-noqa` 让 CI 变绿 3) 用 `RUF100` 追踪并逐步清除

### 洞见 2：`RUF100` 是 noqa 注释本身的技术债检测器

- **洞见**：代码被修复了，但 `# noqa: F401` 注释没有删除，积累成"stale noqa"——它们什么都没抑制，只是噪音
  - 所以：随时间推移，`--add-noqa` 迁移留下的 noqa 注释需要主动清理，否则变成永久噪音
  - 所以：`RUF100` 配合 `--fix` 可以自动删除所有过时的 noqa，在代码库清理完毕后一键收尾
  - 因此可以：在迁移完成后，运行 `ruff check . --extend-select RUF100 --fix` 作为最后一步，验证迁移完成度

### 洞见 3：B023 捉住的是 Python 最难发现的 bug 之一

- **洞见**：循环内定义的 lambda/嵌套函数捕获的是变量名，不是变量值。`[lambda: i for i in range(3)]` 中所有 lambda 返回的都是循环结束后的 `i=2`，不是 0、1、2
  - 所以：这类 bug 在测试中极难被捉住（因为函数本身不报错，只是返回错误的值），只有 linter 才能静态检测
  - 所以：默认配置（只有 E/F）不会检测 B023，必须显式加 `"B"` 到 `select` 中
  - 因此可以：任何 Python 项目都应该默认开启 `B` 规则集，它捕获的是真正的 logic bug，而不只是风格问题

### 洞见 4：Formatter 和 Linter 是完全独立的 —— 不要用 Linter 规则检查格式

- **洞见**：`ruff format` 处理代码格式（等价 Black），`ruff check` 处理规则违规（等价 Flake8）。`E501`（行长度）是 linter 规则，但 formatter 已经处理了行长度
  - 所以：同时启用 `E501` 在 linter 里会产生"formatter 刚格式化过但还报告违规"的矛盾
  - 所以：正确做法是在 `lint.ignore = ["E501"]`，让 formatter 独立管理行长度
  - 因此可以：凡是 formatter 能处理的风格问题（行长度、引号、缩进），都从 linter rules 里删掉，减少噪音

---

## 隐含假设

- **假设 1：速度是采用 ruff 的主要动机**。实际上对于小项目（<1万行），Flake8 也足够快，速度不是关键。真正的价值是统一配置接口
- **假设 2：Ruff 的 unsafe fix 定义与用户期望一致**。"异常类型从 IndexError 变 StopIteration"对某些用户来说可能是完全可接受的，他们需要手动升级为 safe
- **假设 3：所有团队成员都在 CI 运行前手动跑 ruff**。若没有 pre-commit hook，CI 失败才是第一个信号，修复 → 重新 push 的循环成本很高

---

## 反模式与陷阱

- **陷阱：CI 中用 `--fix` 模式而不加 `--exit-non-zero-on-fix`**
  → CI 通过，但实际违规被"修复了但没提交"，下次 push 同样失败
  → 正确做法：CI 中只用 `--check` 模式，或 `--fix --exit-non-zero-on-fix`

- **陷阱：`select = ["ALL"]` 开太多规则**
  → 800+ 规则大量冲突（文档风格规则互斥、pydantic 专用规则在非 pydantic 项目报错）
  → 正确做法：从 `["E4","E7","E9","F","B","I","UP","RUF"]` 出发，按需 extend

- **陷阱：在 `__init__.py` 不忽略 F401**
  → `__init__.py` 里的 import 通常是 re-export（让外部可以 `from pkg import Foo`），Ruff 不理解这个意图
  → 正确做法：`per-file-ignores = {"__init__.py" = ["F401"]}`

- **陷阱：忽略 block-level suppress 的缩进规则**
  → `# ruff: disable` 不在正确缩进位置会产生 `RUF104` 并可能意外扩大抑制范围
  → 正确做法：始终用 explicit enable/disable 配对，不依赖 implicit range

---

## 与现有知识库的连接

- 关联 `python/mini_symphony.py`、`python/session_tracker.py`、`python/insight_agent.py` 等：CodeSnippets 知识库的所有 Python 文件都可以用 ruff 做 linting。直接 `ruff check python/ snippets/*.py` 即可，特别是 B006/B023 这类不被默认检测的规则

- 关联 `analysis/karpathy-autoresearch.md`：autoresearch 的 `train.py` 和 `prepare.py` 也可以接入 ruff。对机器学习代码特别有价值的是 `B031`（groupby 迭代器）和 F601（dict 重复 key，这在 hyperparameter dict 里很常见）

- 关联 `templates/WORKFLOW.md.template`：可以在 workflow 模板里加一步 `ruff check --statistics` 作为代码质量快照，在任务开始前先了解代码库的 linting 状态

---

## 衍生项目想法

### 想法 1：ruff + mini_symphony 的自动代码质量修复任务

**来源组合**：[ruff 的 `--statistics` + `--fix` 自动修复] + [python/mini_symphony.py 的 TASKS.md 任务队列]

**为什么有意思**：`ruff check . --statistics` 输出按规则分类的违规计数，可以机械地转化为 TASKS.md 任务：`- [ ] Fix 47 B006 violations in src/`。mini_symphony 可以逐文件修复，每次提交后重新检查，循环直到 violations 归零

→ 所以：代码质量改善可以完全 agent 化，人类只需要审 PR
→ 因此可以：建立"代码质量 autoresearch"循环：ruff statistics → agent 修复 → git commit → 重新 statistics，类似 karpathy/autoresearch 但目标是 violation count 而不是 val_bpb

**最小 spike**：写一个 Python 脚本，解析 `ruff check . --statistics --output-format json` 的输出，生成 TASKS.md 的 checklist 格式任务列表

**潜在难点**：有些违规需要人类判断（F401 in __init__.py 是 re-export 还是真的未使用），不能完全自动化

---

### 想法 2：CodeSnippets 知识库的 ruff 基线配置

**来源组合**：[ruff 的 `--add-noqa` 迁移策略] + [CodeSnippets 现有 Python 文件]

**为什么有意思**：CodeSnippets 的 Python 文件是"可运行代码"——被人复制到项目里使用时，带着 linting 问题会影响目标项目的代码质量。给 CodeSnippets 加一个 `ruff.toml` + GitHub Actions 检查，保证每个新增 snippet 都通过 ruff

→ 所以：CodeSnippets 从"灵感库"升级为"可直接粘贴进项目的高质量代码库"
→ 因此可以：在 README 里加"所有 Python snippet 通过 ruff B+F+I+UP 检查"的质量声明

**最小 spike**：在 CodeSnippets 根目录创建 `ruff.toml`（见下方模板），运行 `ruff check python/ --statistics`，看当前有多少违规

**潜在难点**：部分 snippet 故意使用某些"反模式"来演示概念，需要加 noqa 注释说明
