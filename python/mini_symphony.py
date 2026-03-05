#!/usr/bin/env python3
"""
mini_symphony.py — 轻量 Agent 编排器

基于 OpenAI Symphony SPEC 核心模式，使用 pi（或任何支持 --print 的 CLI agent）
作为执行后端。

组件：
  - WORKFLOW.md 解析（YAML front matter + Liquid 风格 prompt 模板）
  - TASKS.md 任务源（Markdown checklist 格式）
  - Workspace 隔离（per-task 目录，安全路径校验）
  - 生命周期钩子（after_create / before_run / after_run）
  - 两种重试策略（continuation 固定 1s；failure 指数退避上限 5min）
  - Stall 检测（turn_timeout 超时自动 kill）

用法：
  python mini_symphony.py                        # 使用 ./WORKFLOW.md，持续轮询
  python mini_symphony.py -w path/WORKFLOW.md    # 指定 workflow 文件
  python mini_symphony.py --once                 # 跑一轮后退出
  python mini_symphony.py --dry-run              # 只打印 prompt，不执行 agent

依赖：
  pip install pyyaml

来源参考：
  - https://github.com/openai/symphony (SPEC.md)
  - analysis/symphony-orchestration-spec.md
"""

import argparse
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

# =============================================================================
# 名称: mini_symphony
# 用途: 轻量 Agent 编排器，将 TASKS.md 任务自动分发给 pi 等 CLI agent 执行
# 依赖: pip install pyyaml
# 适用场景: 个人自动化任务、批量 coding agent 执行、异步任务队列
# 日期: 2026-03-05
# =============================================================================


# ─────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────

@dataclass
class Task:
    id: str           # sanitized key，用于 workspace 目录名
    title: str
    description: str = ""
    done: bool = False
    line_index: int = -1  # 在 TASKS.md 中的行号，用于 mark-done


# ─────────────────────────────────────────────
# 默认配置
# ─────────────────────────────────────────────

DEFAULT_CONFIG = {
    "agent": {
        "command": "pi --print",   # 替换为 "claude -p" 等任何 CLI agent
        "turn_timeout": 3600,      # 单次执行超时（秒）
        "max_retries": 3,
        "max_retry_backoff": 300,  # 失败重试最大等待（秒）
    },
    "workspace": {
        "root": "~/.mini-symphony/workspaces",
    },
    "hooks": {
        # after_create: 首次创建 workspace 时执行（克隆代码、安装依赖等）
        # before_run:   每次 attempt 前执行（git pull、清理等），失败则中止本次
        # after_run:    每次 attempt 后执行（收集结果等），失败仅记录
    },
    "tasks": {
        "source": "./TASKS.md",
    },
    "polling": {
        "interval": 30,  # 轮询间隔（秒）
    },
}

DEFAULT_PROMPT = """\
你是一个 coding agent，请完成以下任务。

**任务**: {{ task.title }}
{% if task.description %}
**描述**: {{ task.description }}
{% endif %}
{% if attempt %}
这是第 {{ attempt }} 次重试，请先检查 workspace 中已有工作再继续。
{% endif %}

完成后请提交相关改动，并确认任务已完成。
"""


# ─────────────────────────────────────────────
# WORKFLOW.md 解析
# ─────────────────────────────────────────────

def deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个 dict，override 优先"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def parse_workflow(path: str) -> tuple[dict, str]:
    """
    解析 WORKFLOW.md，返回 (config, prompt_template)。

    文件格式：
      ---
      agent:
        command: "pi --print"
        max_retries: 3
      hooks:
        before_run: "git pull"
      ---

      Prompt 模板正文（支持 {{ var }} 和 {% if %}...{% endif %}）
    """
    text = Path(path).read_text(encoding="utf-8")

    front_matter_match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if front_matter_match:
        yaml_str, prompt_template = front_matter_match.groups()
        user_config = yaml.safe_load(yaml_str) or {}
    else:
        user_config = {}
        prompt_template = text

    config = deep_merge(DEFAULT_CONFIG, user_config)
    prompt_template = prompt_template.strip() or DEFAULT_PROMPT
    return config, prompt_template


# ─────────────────────────────────────────────
# 模板引擎（Liquid 子集）
# ─────────────────────────────────────────────

def resolve_var(path: str, variables: dict):
    """解析 task.title 风格的点分路径变量"""
    parts = path.strip().split(".")
    current = variables
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None
        if current is None:
            return None
    return current


def render_template(template: str, variables: dict) -> str:
    """
    支持：
      {{ var }} / {{ obj.field }}   变量替换
      {% if var %}...{% endif %}    条件块（truthy 检测）
    """
    # 处理 {% if var %}...{% endif %} 块
    def handle_if(m):
        cond = m.group(1).strip()
        body = m.group(2)
        return body if resolve_var(cond, variables) else ""

    result = re.sub(
        r"\{%-?\s*if\s+(\S+)\s*-?%\}(.*?)\{%-?\s*endif\s*-?%\}",
        handle_if,
        template,
        flags=re.DOTALL,
    )

    # 处理 {{ variable }} 替换
    def handle_var(m):
        value = resolve_var(m.group(1).strip(), variables)
        return str(value) if value is not None else ""

    return re.sub(r"\{\{\s*(.+?)\s*\}\}", handle_var, result)


# ─────────────────────────────────────────────
# 任务源：TASKS.md
# ─────────────────────────────────────────────

def sanitize_key(title: str) -> str:
    """
    将 task title 转换为安全的文件系统 key。
    只允许 [A-Za-z0-9._-]，其余替换为 _。
    （Symphony 安全不变量 3）
    """
    key = re.sub(r"[^A-Za-z0-9._-]", "_", title).strip("_")
    return key[:64]  # 限制目录名长度


def parse_tasks(tasks_path: str) -> list[Task]:
    """
    从 TASKS.md 读取未完成任务。

    支持格式：
      - [ ] Fix login timeout bug
      - [x] Already done task
      - [ ] Task with description
            This is the description (indented lines after task)
    """
    path = Path(tasks_path)
    if not path.exists():
        logging.warning(f"TASKS.md 不存在: {tasks_path}")
        return []

    tasks = []
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0

    while i < len(lines):
        m = re.match(r"^-\s+\[([ x])\]\s+(.+)$", lines[i])
        if m:
            done = m.group(1) == "x"
            title = m.group(2).strip()

            # 读取缩进的描述行
            description_lines = []
            j = i + 1
            while j < len(lines) and re.match(r"^\s{2,}", lines[j]):
                description_lines.append(lines[j].strip())
                j += 1

            tasks.append(Task(
                id=sanitize_key(title),
                title=title,
                description="\n".join(description_lines),
                done=done,
                line_index=i,
            ))
            i = j
        else:
            i += 1

    return [t for t in tasks if not t.done]


def mark_task_done(tasks_path: str, task: Task):
    """将 TASKS.md 中对应行的 [ ] 改为 [x]"""
    path = Path(tasks_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if 0 <= task.line_index < len(lines):
        lines[task.line_index] = re.sub(r"\[ \]", "[x]", lines[task.line_index], count=1)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logging.info(f"[{task.id}] 标记完成 ✓")


# ─────────────────────────────────────────────
# Workspace 管理
# ─────────────────────────────────────────────

def prepare_workspace(task: Task, config: dict) -> tuple[Path, bool]:
    """
    创建 per-task workspace 目录。

    安全不变量（来自 Symphony SPEC）：
      1. workspace_path 必须在 workspace_root 下（防路径穿越）
      2. workspace key 只允许 [A-Za-z0-9._-]（已在 sanitize_key 保证）

    返回 (workspace_path, created_now)
    """
    root = Path(config["workspace"]["root"]).expanduser().resolve()
    workspace = (root / task.id).resolve()

    # 不变量 1
    if not str(workspace).startswith(str(root)):
        raise ValueError(f"路径穿越检测失败: {workspace} 不在 {root} 下")

    created_now = not workspace.exists()
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace, created_now


# ─────────────────────────────────────────────
# 生命周期钩子
# ─────────────────────────────────────────────

def run_hook(
    script: Optional[str],
    workspace: Path,
    config: dict,
    label: str = "hook",
) -> bool:
    """
    在 workspace 目录下以 bash -lc 执行钩子脚本。
    返回 True=成功，False=失败。

    环境变量注入：
      WORKSPACE_PATH  当前 workspace 绝对路径
    """
    if not script:
        return True

    timeout = config.get("hooks", {}).get("timeout", 60)
    env = {**os.environ, "WORKSPACE_PATH": str(workspace)}

    try:
        result = subprocess.run(
            script, shell=True, executable="/bin/bash",
            cwd=workspace, env=env,
            capture_output=True, text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logging.warning(f"[{label}] 失败（exit={result.returncode}）: {result.stderr[:300]}")
            return False
        if result.stdout.strip():
            logging.debug(f"[{label}] stdout: {result.stdout.strip()[:200]}")
        return True
    except subprocess.TimeoutExpired:
        logging.warning(f"[{label}] 超时（{timeout}s）")
        return False


# ─────────────────────────────────────────────
# Agent 执行
# ─────────────────────────────────────────────

def run_agent(
    prompt: str,
    workspace: Path,
    config: dict,
    dry_run: bool = False,
) -> tuple[int, str]:
    """
    以子进程方式运行 agent。

    Agent 命令通过 bash -lc 执行，cwd 固定为 workspace（不变量 1）。
    prompt 通过命令行参数传递。

    返回 (exit_code, stdout)
    """
    if dry_run:
        separator = "─" * 60
        print(f"\n{separator}\nDRY RUN prompt:\n{separator}\n{prompt}\n{separator}\n")
        return 0, "[dry-run]"

    agent_cfg = config.get("agent", {})
    command = agent_cfg.get("command", "pi --print")
    turn_timeout = agent_cfg.get("turn_timeout", 3600)

    # prompt 包含换行和引号，用临时文件传递更安全
    prompt_file = workspace / ".symphony_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    # 大多数 CLI agent 支持从文件读：cat file | agent 或 agent < file
    # pi 的用法：pi --print "$(cat file)" 或直接管道
    full_command = f'{command} "$(cat .symphony_prompt.txt)"'

    logging.info(f"[agent] 启动: {command} @ {workspace.name}")

    try:
        result = subprocess.run(
            full_command, shell=True, executable="/bin/bash",
            cwd=workspace,
            capture_output=True, text=True,
            timeout=turn_timeout,
        )
        prompt_file.unlink(missing_ok=True)
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        logging.warning(f"[agent] 超时（{turn_timeout}s），视为 stall")
        prompt_file.unlink(missing_ok=True)
        return -1, ""


# ─────────────────────────────────────────────
# 重试策略
# ─────────────────────────────────────────────

def get_retry_delay(attempt: int, is_failure: bool, config: dict) -> float:
    """
    两种重试延迟：
      continuation（exit_code=0 但任务未完成）: 固定 1s
      failure（exit_code!=0）: 指数退避，min(10s × 2^attempt, max_backoff)
    """
    if not is_failure:
        return 1.0  # continuation retry
    max_backoff = config.get("agent", {}).get("max_retry_backoff", 300)
    return min(10 * (2 ** attempt), max_backoff)


# ─────────────────────────────────────────────
# 单任务处理
# ─────────────────────────────────────────────

def process_task(
    task: Task,
    config: dict,
    prompt_template: str,
    dry_run: bool = False,
) -> bool:
    """
    处理单个任务，含完整重试逻辑。
    返回 True=任务完成。
    """
    hooks = config.get("hooks", {})
    max_retries = config.get("agent", {}).get("max_retries", 3)
    tasks_source = config.get("tasks", {}).get("source", "./TASKS.md")

    # 准备 workspace
    try:
        workspace, created_now = prepare_workspace(task, config)
    except ValueError as e:
        logging.error(f"[{task.id}] workspace 准备失败: {e}")
        return False

    # after_create hook（仅首次）
    if created_now:
        logging.info(f"[{task.id}] 新建 workspace: {workspace}")
        ok = run_hook(hooks.get("after_create"), workspace, config, label="after_create")
        if not ok:
            logging.error(f"[{task.id}] after_create 失败，跳过任务")
            return False

    # 重试循环
    for attempt in range(max_retries):
        logging.info(f"[{task.id}] attempt {attempt + 1}/{max_retries}")

        # before_run hook
        ok = run_hook(hooks.get("before_run"), workspace, config, label="before_run")
        if not ok:
            logging.warning(f"[{task.id}] before_run 失败，中止本次 attempt")
            delay = get_retry_delay(attempt, is_failure=True, config=config)
            logging.info(f"[{task.id}] {delay:.0f}s 后重试")
            time.sleep(delay)
            continue

        # 渲染 prompt（第一次 attempt=None，重试时 attempt=1,2,...）
        template_vars = {
            "task": {"title": task.title, "description": task.description},
            "attempt": attempt if attempt > 0 else None,
        }
        prompt = render_template(prompt_template, template_vars)

        # 执行 agent
        exit_code, output = run_agent(prompt, workspace, config, dry_run=dry_run)

        # after_run hook（失败也执行，仅记录）
        run_hook(hooks.get("after_run"), workspace, config, label="after_run")

        if exit_code == 0:
            logging.info(f"[{task.id}] 成功完成 ✓")
            if not dry_run:
                mark_task_done(tasks_source, task)
            return True

        # 失败处理
        is_timeout = exit_code == -1
        reason = "stall/timeout" if is_timeout else f"exit_code={exit_code}"
        logging.warning(f"[{task.id}] 失败: {reason}")

        if attempt < max_retries - 1:
            delay = get_retry_delay(attempt, is_failure=True, config=config)
            logging.info(f"[{task.id}] {delay:.0f}s 后重试...")
            time.sleep(delay)

    logging.error(f"[{task.id}] 达到最大重试次数（{max_retries}），放弃")
    return False


# ─────────────────────────────────────────────
# 主编排循环
# ─────────────────────────────────────────────

def orchestrate(workflow_path: str, once: bool = False, dry_run: bool = False):
    """
    主轮询循环：
      1. 读取 TASKS.md，获取 pending 任务
      2. 按顺序执行每个任务（含重试）
      3. 等待 poll_interval 后重复

    使用 --once 跑一轮后退出（适合 cron / CI）。
    """
    config, prompt_template = parse_workflow(workflow_path)
    poll_interval = config.get("polling", {}).get("interval", 30)
    tasks_source = config.get("tasks", {}).get("source", "./TASKS.md")

    logging.info(f"mini-symphony 启动 | workflow={workflow_path} | tasks={tasks_source}")
    if dry_run:
        logging.info("DRY RUN 模式：只打印 prompt，不执行 agent")

    while True:
        tasks = parse_tasks(tasks_source)

        if not tasks:
            logging.info("无待处理任务")
        else:
            logging.info(f"发现 {len(tasks)} 个待处理任务")
            for task in tasks:
                process_task(task, config, prompt_template, dry_run=dry_run)

        if once:
            logging.info("--once 模式，退出")
            break

        logging.info(f"下次轮询在 {poll_interval}s 后")
        time.sleep(poll_interval)


# ─────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="轻量 Agent 编排器（基于 Symphony SPEC 模式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python mini_symphony.py                    # 持续轮询 ./WORKFLOW.md
  python mini_symphony.py --once             # 跑一轮后退出
  python mini_symphony.py --dry-run          # 预览 prompt，不执行
  python mini_symphony.py -w my-flow.md      # 指定 workflow 文件
        """,
    )
    parser.add_argument("-w", "--workflow", default="WORKFLOW.md",
                        help="WORKFLOW.md 路径（默认 ./WORKFLOW.md）")
    parser.add_argument("--once", action="store_true",
                        help="处理一轮任务后退出，不轮询")
    parser.add_argument("--dry-run", action="store_true",
                        help="只渲染并打印 prompt，不启动 agent")
    args = parser.parse_args()

    if not Path(args.workflow).exists():
        print(f"错误: {args.workflow} 不存在\n"
              f"请创建 WORKFLOW.md 或用 -w 指定路径", file=sys.stderr)
        sys.exit(1)

    try:
        orchestrate(args.workflow, once=args.once, dry_run=args.dry_run)
    except KeyboardInterrupt:
        logging.info("已退出")


if __name__ == "__main__":
    main()
