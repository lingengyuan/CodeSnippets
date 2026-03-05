# 本地优先的频道内容浏览器模式

> 来源: https://github.com/nolenroyalty/yt-browse
> 日期: 2026-03-05
> 语言: Go
> 标签: TUI, 缓存策略, 搜索, API 配额管理

---

## 核心洞察

yt-browse 是一个用 Go 写的 YouTube 频道 TUI 浏览器，解决了一个痛点：YouTube 原生搜索不能在单个频道内做高级过滤（regex、时间范围、全文描述搜索）。

它的设计哲学值得记录：**把昂贵的 API 调用和本地搜索彻底分离**。

```
初次访问频道 → API 全量拉取 → JSON 缓存到本地（24h TTL）
后续所有搜索 → 纯本地过滤，零 API 消耗
```

---

## 可复用的技术模式

### 1. Fetch-Cache-Search 架构

```
[外部 API / 昂贵数据源]
        ↓
  本地 JSON 缓存（~/.app/cache/<id>/）
        ↓
  客户端多模式搜索（word / regex / fuzzy）
```

- **缓存路径**: `~/.yt-browse/cache/<channelID>/`，按来源 ID 隔离
- **TTL**: 24 小时，写失败不影响功能（graceful degradation）
- **刷新**: 手动按 `r` 强制重拉

**适用场景**: 任何"数据变化不频繁、搜索频率高"的 API，比如 Substack 文章列表、Podcast 剧集、GitHub issues。

---

### 2. 两步批量拉取 —— API 配额优化

YouTube Search API 很贵（配额消耗大），yt-browse 的解法：

```
第一步: PlaylistItems.List → 只拿 video ID 列表（便宜）
第二步: Videos.List(ids=[...]) → 批量拿完整 metadata（便宜）
避免:  Search API → 按结果数计费（贵）
```

这是一个通用模式：**先拉 ID，再批量拉详情**，比直接 search 便宜很多倍。GitHub API、Notion API 等都有类似的"list vs get"成本差异。

---

### 3. 三层统一搜索接口

```go
// 统一接口：query, text → rune indices
func matchIndices(mode filterMode, query, text string, re *regexp.Regexp) []int

// 三种实现：
// filterWords  → 按词拆分，每词独立匹配
// filterRegex  → 编译好的 regexp，返回 match 区间
// fuzzy        → sahilm/fuzzy 库，返回 MatchedIndexes
```

关键细节：**全部返回 rune index（而非 byte offset）**，确保中文等多字节字符的高亮位置正确。

这个统一接口设计可以直接复用：用一个 enum 控制模式，返回统一的 `[]int` 高亮位置。

---

### 4. Bubble Tea / Elm 架构用于 TUI

```go
// 三个核心方法
func (m Model) Init() tea.Cmd      // 启动异步命令
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd)  // 状态机
func (m Model) View() string       // 纯渲染，无副作用
```

Update 的标准三步流水线：
```
1. sort 原始数据 ([]Playlist, []Video)
2. filter 得到展示列表
3. SetItems() 更新 list widget
```

三个独立 list model 维护各自的 scroll position，Tab 切换时位置不丢失。

---

### 5. 渐进加载 + 预取

- 打开频道后立刻开始**后台预取全部视频**（即使用户还在看 playlists tab）
- 切到 videos tab 时数据已经就绪 → 感知上是"即时"
- 进度通过 `videoLoadingMsg` 流式推送到 UI

本质是把等待时间"藏"进用户的浏览行为里。

---

## 可以延伸的方向

### 方向 A：通用内容归档 + 搜索 CLI
把这个模式抽象成通用工具：任何有分页 API 的内容源（Substack、Podcast RSS、GitHub Stars）都可以套用 fetch-cache-search 模板。

本地做索引 → FTS5 或 SQLite JSON 存储 → TUI / Web 前端搜索。
（可以和 `python/fts5_fuzzy_search.py` 结合）

### 方向 B：YouTube 数据 → 本地 LLM 问答
先用 yt-browse 思路拉取频道字幕/描述 → 存入本地向量库（参考 `python/zvec_inprocess_vector.py`）→ 用 LLM 做"问这个频道的任何问题"。

### 方向 C：多频道 cross-search
yt-browse 只支持单频道。多频道聚合搜索（"在我订阅的所有频道里找关于 X 的视频"）是自然的延伸，类似 Obsidian 的全库搜索。

---

## 依赖参考

| 库 | 用途 |
|----|------|
| [charmbracelet/bubbletea](https://github.com/charmbracelet/bubbletea) | Elm 架构 TUI 框架 |
| [charmbracelet/lipgloss](https://github.com/charmbracelet/lipgloss) | TUI 样式 |
| [charmbracelet/bubbles](https://github.com/charmbracelet/bubbles) | list、textinput、viewport 组件 |
| [sahilm/fuzzy](https://github.com/sahilm/fuzzy) | 模糊匹配 |
