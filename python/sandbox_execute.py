# =============================================================================
# 名称: Sandbox Execute Pattern
# 用途: 在隔离子进程中执行代码，只捕获 stdout，控制输出大小
# 依赖: 标准库 (subprocess, tempfile)
# 适用场景: Agent 工具输出压缩、安全代码执行、context budget 管理
# 来源: https://github.com/mksglu/claude-context-mode (沙箱执行思路)
# 日期: 2026-03-01
#
# 核心思想：不要把原始数据放进 context/内存，在子进程里处理完，
# 只把 stdout（结果）收回来。原始数据留在子进程里随进程消亡。
# =============================================================================

import subprocess
import tempfile
import json
from pathlib import Path

RUNTIMES = {
    "python": ["python3", "-c"],
    "javascript": ["node", "-e"],
    "shell": ["bash", "-c"],
    "ruby": ["ruby", "-e"],
}

# Max bytes of stdout to capture (prevents context flooding)
MAX_OUTPUT = 5 * 1024  # 5 KB


def execute(code: str, language: str = "python",
            timeout: int = 30, max_output: int = MAX_OUTPUT) -> dict:
    """
    Execute code in an isolated subprocess. Only stdout is returned.
    Stderr and raw data stay in the subprocess boundary.
    """
    if language not in RUNTIMES:
        return {"ok": False, "error": f"Unsupported language: {language}"}

    cmd = RUNTIMES[language]
    try:
        result = subprocess.run(
            [*cmd, code],
            capture_output=True, text=True, timeout=timeout,
            env=None  # Inherit parent env for credential passthrough
        )
        stdout = result.stdout[:max_output]
        truncated = len(result.stdout) > max_output
        return {
            "ok": result.returncode == 0,
            "stdout": stdout,
            "truncated": truncated,
            "original_size": len(result.stdout),
            "returned_size": len(stdout),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute_file(file_path: str, script: str, language: str = "python",
                 timeout: int = 30, max_output: int = MAX_OUTPUT) -> dict:
    """
    Process a file in sandbox. The file content never enters the caller's memory
    beyond what the script's stdout returns.

    The script receives the file path as first argument.
    """
    if not Path(file_path).exists():
        return {"ok": False, "error": f"File not found: {file_path}"}

    # Wrap script to receive file path
    if language == "python":
        wrapped = f"import sys; sys.argv = ['script', '{file_path}']\n{script}"
    elif language == "shell":
        wrapped = f'FILE="{file_path}"\n{script}'
    else:
        wrapped = script

    return execute(wrapped, language, timeout, max_output)


def batch_execute(tasks: list[dict], timeout: int = 30) -> list[dict]:
    """
    Run multiple code executions in one call.
    Each task: {"code": str, "language": str}

    Inspired by context-mode's batch_execute — reduces round-trip overhead
    and keeps total context consumption predictable.
    """
    results = []
    budget_remaining = MAX_OUTPUT * 3  # Total budget for batch

    for task in tasks:
        per_task_budget = min(MAX_OUTPUT, budget_remaining)
        if per_task_budget <= 0:
            results.append({"ok": False, "error": "Context budget exhausted"})
            continue
        r = execute(
            task.get("code", ""),
            task.get("language", "python"),
            timeout, per_task_budget
        )
        budget_remaining -= r.get("returned_size", 0)
        results.append(r)

    return results


# --- Demo ---
if __name__ == "__main__":
    # Example 1: Simple execution
    r = execute("print(sum(range(1000)))", "python")
    print(f"Sum: {r['stdout'].strip()} (returned {r['returned_size']} bytes)")

    # Example 2: Process a large file, only get summary
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("name,value\n")
        for i in range(10000):
            f.write(f"item_{i},{i*3.14}\n")
        tmp_path = f.name

    r = execute_file(tmp_path, """
import csv, sys
with open(sys.argv[1]) as f:
    rows = list(csv.DictReader(f))
print(f"Rows: {len(rows)}")
print(f"Max value: {max(float(r['value']) for r in rows):.2f}")
print(f"Min value: {min(float(r['value']) for r in rows):.2f}")
    """, "python")

    print(f"\nFile processing result ({r['original_size']} B → {r['returned_size']} B):")
    print(r['stdout'])

    # Example 3: Batch execution
    results = batch_execute([
        {"code": "print('hello')", "language": "python"},
        {"code": "echo 'world'", "language": "shell"},
    ])
    for i, r in enumerate(results):
        print(f"Task {i}: {r['stdout'].strip()}")

    Path(tmp_path).unlink()
