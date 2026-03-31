# Progress-as-Code：自扫描式项目仪表盘

**来源**: [lingengyuan/claude-code](https://github.com/lingengyuan/claude-code) Python porting workspace
**日期**: 2026-03-31
**状态**: 💡灵感

---

## 核心理念

> 用代码扫描代码目录，自动生成进度报告和 README 目录表——迁移/知识库的进度追踪不依赖外部工具，而是从代码库本身的文件状态直接推导。

**解决的核心痛点**：每次新增 analysis/snippet/idea 都要手动更新 README 计数和目录表，容易遗漏、格式不一致。
**非显见之处**：这不只是"自动化"——它把"项目状态"从人类维护的文档变成了代码的派生物。状态永远不会过期，因为状态就是文件系统的事实。

---

## 关键技术要点

### 模式 1：Port Manifest（扫描→建模→渲染）

来源仓库的三层架构：

```python
# 1. 扫描：遍历目录，统计文件
files = [p for p in root.rglob('*.py') if p.is_file()]
counter = Counter(path.relative_to(root).parts[0] for path in files)

# 2. 建模：结构化数据
@dataclass(frozen=True)
class Subsystem:
    name: str
    path: str
    file_count: int
    notes: str

# 3. 渲染：生成 Markdown 报告
def to_markdown(self) -> str:
    for module in self.top_level_modules:
        lines.append(f'- `{module.name}` ({module.file_count} files)')
```

### 模式 2：声明式 Backlog

```python
PORTED_COMMANDS = (
    PortingModule('main', '...', 'src/main.py', 'implemented'),
    PortingModule('summary', '...', 'src/query_engine.py', 'implemented'),
)
```

元组 + status 字段 = 一眼看清进度，可编程查询，比 markdown checklist 更结构化。

### 模式 3：Frozen Dataclass 优先

所有模型用 `@dataclass(frozen=True)`——不可变优先，防止状态被意外修改。

### 适配到 CodeSnippets 的设想

```python
# codesnippets_manifest.py（概念草案）
from pathlib import Path
from dataclasses import dataclass

DIRS = {
    'analysis': ('🔵', '精读'),
    'ideas': ('💡', '灵感'),
    'python': ('🟢', '代码'),
    'snippets': ('🟢', '代码'),
    'templates': ('🟡', '模板'),
}

@dataclass(frozen=True)
class Entry:
    path: str
    category: str
    emoji: str
    title: str  # 从文件第一行 # 标题提取

def scan_kb(root: Path) -> list[Entry]:
    """扫描知识库目录，提取所有条目"""
    ...

def render_readme_table(entries: list[Entry]) -> str:
    """生成 README 目录表 Markdown"""
    ...

def check_sync(readme: str, entries: list[Entry]) -> list[str]:
    """检查 README 与实际文件的差异，返回不一致项"""
    ...
```

**三种使用模式**：
1. `python3 codesnippets_manifest.py check` — CI 检查 README 是否与文件同步
2. `python3 codesnippets_manifest.py render` — 生成最新目录表
3. `python3 codesnippets_manifest.py update` — 直接更新 README.md

---

## 蕴含链

项目进度用外部工具（JIRA/Linear/手动 README 编辑）追踪
→ 所以：进度信息与代码实际状态可能不同步（人忘记更新）
→ 所以：如果进度可以从代码文件系统直接推导，就消除了"同步"问题
→ 因此可以：**把 README 目录表变成代码的派生物**，每次 commit 前自动验证或自动生成

---

## 可行性分析

- ✅ 已验证可行：来源仓库的 port_manifest.py 已经实现了核心的 scan→model→render 三层
- ✅ 已验证可行：CodeSnippets 的目录结构规整（analysis/, ideas/, python/, snippets/, templates/），每个文件都有标准 header
- ⚠️ 待解决：如何从文件自动提取"功能描述"——可以读第一行 `# 标题` 或 header 中的 `用途:` 字段
- ⚠️ 待解决：README 的 EN/CN 双语表格需要同时更新，自动化时需要维护两套模板

**适用边界**：目录结构规整、文件有标准 header 的知识库项目。对于结构松散或文件命名不规律的项目效果有限。

---

## 与现有知识库的连接

- 关联 `python/mini_symphony.py`：manifest 脚本可以作为 mini_symphony 的一个 check 任务——每轮编排结束后自动检查 README 同步状态
- 关联 `python/snippet_manager.py`：snippet_manager 已经实现了"扫描 + 自然语言搜索"，manifest 可以复用其文件发现逻辑
- 关联 `analysis/claude-code-ai-reimplementation-ethics.md`：来源仓库的 port_manifest 模式在此精读中作为"元工具先行"模式被提取
- 关联 `templates/agents-md-template.md`：AGENTS.md 的"Important files"章节可以从 manifest 自动生成

---

## 下一步行动

- [ ] 写 `python/codesnippets_manifest.py`：scan→model→render 三层，支持 check/render/update 三个命令
- [ ] 为 README 中英文表格定义模板格式，支持自动双语更新
- [ ] 加入 git pre-commit hook 或 CI check，确保 README 与实际文件同步
