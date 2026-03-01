# =============================================================================
# 名称: Tape Context Manager
# 用途: 用 Tape 模型管理多轮对话，不依赖历史继承，只用锚点重建上下文
# 依赖: 只需标准库，可替换任意 LLM client
# 适用场景: 群聊 Agent、多任务切换、无状态 Agent 服务
# 日期: 2026-03-01
#
# 一句话：演示了用"锚点+按需装配"替代"历史继承"的上下文管理，适合多话题群聊场景。
#
# 延伸场景:
#   - 客服系统：不同话题（退款/物流/投诉）各自打锚点，同一用户多话题并行不串
#   - 代码审查 Agent：PR 每个文件审完打锚点，崩溃重启后从锚点续，不重看已审代码
#   - 会议纪要 Agent：每个议题结束打锚点，最终只用锚点链生成纪要，原始发言不进 context
#   - 游戏 NPC：每段剧情结束打锚点，NPC 记住"关键事件"而非全部对话，省 token 且行为更稳定
#   - A/B 测试回溯：同一条纸带 fork 出两个锚点，比较不同 context 装配策略的效果差异
# =============================================================================

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Literal

@dataclass
class TapeEntry:
    ts: float
    type: Literal["message", "anchor"]
    role: str
    content: str
    tags: list[str] = field(default_factory=list)

class Tape:
    def __init__(self):
        self.entries: list[TapeEntry] = []

    def append(self, role: str, content: str, tags: list[str] = None):
        self.entries.append(TapeEntry(
            ts=time.time(), type="message",
            role=role, content=content, tags=tags or []
        ))

    def anchor(self, summary: str, tags: list[str] = None):
        """任务结束时打锚点，而不是继承历史"""
        self.entries.append(TapeEntry(
            ts=time.time(), type="anchor",
            role="system", content=summary, tags=tags or []
        ))

    def assemble_context(self, task_tags: list[str] = None, max_messages=10) -> list[dict]:
        """按需装配：找最近锚点 + 相关片段，不默认继承所有历史"""
        # 找最近的锚点作为起点
        last_anchor = None
        for e in reversed(self.entries):
            if e.type == "anchor":
                last_anchor = e
                break

        context = []
        if last_anchor:
            context.append({"role": "system", "content": f"[Anchor] {last_anchor.content}"})

        # 从锚点之后（或全部）取相关消息
        anchor_ts = last_anchor.ts if last_anchor else 0
        recent = [
            e for e in self.entries
            if e.type == "message" and e.ts > anchor_ts
            and (not task_tags or any(t in e.tags for t in task_tags))
        ][-max_messages:]

        context += [{"role": e.role, "content": e.content} for e in recent]
        return context

# --- 模拟使用 ---
if __name__ == "__main__":
    tape = Tape()

    # 第一个任务：写代码
    tape.append("user", "帮我写个 quicksort", tags=["coding"])
    tape.append("assistant", "def quicksort(arr): ...", tags=["coding"])
    tape.anchor("完成了 quicksort 实现，用户满意", tags=["coding"])

    # 第二个任务：群聊里别人在聊别的
    tape.append("user", "今天吃什么", tags=["chat"])
    tape.append("user", "接着刚才的，帮我加个单测", tags=["coding"])

    # 装配上下文时只取 coding 相关
    ctx = tape.assemble_context(task_tags=["coding"])
    print(json.dumps(ctx, ensure_ascii=False, indent=2))
