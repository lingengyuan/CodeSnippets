# =============================================================================
# 名称: Snippet Manager
# 用途: 管理 code snippets，用自然语言搜索，组合成 prompt 喂给 LLM
# 依赖: pip install anthropic rich
# 适用场景: 本地 snippet 库 + agent 辅助组合
# 日期: 2026-03-01
# =============================================================================

import json, os, sys
from pathlib import Path
from datetime import datetime

STORE = Path("~/.snippets.json").expanduser()

def load():
    return json.loads(STORE.read_text()) if STORE.exists() else {}

def save(data):
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def add(name, code, tags="", desc=""):
    data = load()
    data[name] = {"code": code, "tags": tags.split(","), "desc": desc, "added": datetime.now().isoformat()}
    save(data)
    print(f"✅ Saved: {name}")

def search(query):
    data = load()
    hits = {k: v for k, v in data.items()
            if query.lower() in k.lower()
            or query.lower() in v.get("desc","").lower()
            or any(query.lower() in t for t in v.get("tags",[]))}
    for k, v in hits.items():
        print(f"\n── {k} ──\n{v['desc']}\n{v['code'][:200]}...")

def combine_prompt(*names):
    """输出一个可以直接喂给 LLM 的组合 prompt"""
    data = load()
    parts = []
    for name in names:
        if name in data:
            parts.append(f"Here's working code for {name}:\n```\n{data[name]['code']}\n```")
    print("\n".join(parts))
    print("\nCombine these examples to build: [YOUR GOAL HERE]")

# 用法示例
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "add":
        # python snippet_manager.py add "pdf-to-image" "$(cat pdf.js)" "pdf,browser" "PDF.js 渲染页面为图片"
        add(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "", sys.argv[5] if len(sys.argv) > 5 else "")
    elif cmd == "search":
        search(sys.argv[2])
    elif cmd == "combine":
        combine_prompt(*sys.argv[2:])
    else:
        print("用法: add <name> <code> [tags] [desc] | search <query> | combine <name1> <name2>")
