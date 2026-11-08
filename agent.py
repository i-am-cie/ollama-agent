#!/usr/bin/env python3
"""
ollama-agent — A tiny local AI agent that can read/write files and run commands.
Powered by Ollama + Qwen2.5. No API keys. No cloud. ~200 lines.

Usage:
    pip install -r requirements.txt
    ollama pull qwen2.5:7b
    python agent.py
"""
import json
import os
import subprocess
import sys

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_HOST.startswith(("http://", "https://")):
    OLLAMA_HOST = "http://" + OLLAMA_HOST
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"
MODEL = os.environ.get("AGENT_MODEL", "qwen2.5:7b")
MAX_STEPS = 15

SYSTEM_PROMPT = """你是一个能使用工具完成任务的 AI 助手。你运行在用户的电脑上。

可用工具：
- read_file(path)：读取文件内容
- write_file(path, content)：把内容写入文件
- run_command(cmd)：执行一条 shell 命令并返回输出
- list_dir(path=".")：列出目录下的文件
- search_in_files(keyword, path=".")：在文件中搜索关键词，返回匹配的文件和行号
- git_status()：查看当前git仓库的状态

工作方式：
1. 思考当前该做什么
2. 用 JSON 格式输出要调用的工具和参数，格式：
   {"thought": "...", "action": "工具名", "action_input": {参数}}
3. 工具执行后会返回结果，你根据结果继续
4. 任务完成后，直接用自然语言给出最终答案，不要再调用工具

注意：
- 每次只调用一个工具
- 用中文思考和回答
- 文件路径用相对路径即可
"""


# ---------- 工具实现 ----------

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return content[:8000]


def write_file(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入 {len(content)} 字符到 {path}"


def run_command(cmd: str) -> str:
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        out = result.stdout[-3000:]
        err = result.stderr[-1000:]
        return f"[exit {result.returncode}]\n{out}\n{err}".strip()
    except subprocess.TimeoutExpired:
        return "命令执行超时（30秒）"
    except Exception as e:
        return f"命令出错: {e}"


def list_dir(path: str = ".") -> str:
    if not os.path.isdir(path):
        return f"{path} 不是目录"
    items = os.listdir(path)
    lines = []
    for name in items:
        full = os.path.join(path, name)
        kind = "📁" if os.path.isdir(full) else "📄"
        lines.append(f"{kind} {name}")
    return "\n".join(lines) if lines else "(空目录)"


def search_in_files(keyword: str, path: str = ".") -> str:
    """Search for a keyword in files recursively."""
    matches = []
    for root, dirs, files in os.walk(path):
        # Skip hidden dirs and common ignores
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv")]
        for fname in files:
            if fname.startswith("."):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if keyword.lower() in line.lower():
                            matches.append(f"{fpath}:{i}: {line.strip()[:100]}")
                            if len(matches) >= 20:
                                return "\n".join(matches) + f"\n... (还有更多匹配，共 {len(matches)} 条)"
            except (OSError, UnicodeError):
                pass
    return "\n".join(matches) if matches else f"未找到包含 '{keyword}' 的文件"


def git_status() -> str:
    """Show git status of the current repo."""
    try:
        result = subprocess.run(
            "git status --short && echo '---' && git log --oneline -5",
            shell=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or "(干净的工作区)"
    except Exception as e:
        return f"不是git仓库或出错: {e}"


TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "list_dir": list_dir,
    "search_in_files": search_in_files,
    "git_status": git_status,
}


# ---------- LLM 调用 ----------

def call_llm(messages):
    resp = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


# ---------- Agent 主循环 ----------

def extract_action(text: str):
    """从 LLM 回复中提取 JSON action。"""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        if "action" in data and data["action"] in TOOLS:
            return data
    except (ValueError, json.JSONDecodeError):
        pass
    return None


def run_agent(task: str):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    print(f"\n🎯 任务: {task}\n" + "=" * 50)

    for step in range(1, MAX_STEPS + 1):
        reply = call_llm(messages)
        messages.append({"role": "assistant", "content": reply})

        action = extract_action(reply)

        if action is None:
            # 没有工具调用 = 任务完成
            print(f"\n✅ 最终答案:\n{reply}")
            return reply

        tool_name = action["action"]
        tool_args = action.get("action_input", {})
        thought = action.get("thought", "")

        print(f"\n🤖 步骤 {step}: {thought}")
        print(f"🔧 调用 {tool_name}({tool_args})")

        try:
            observation = TOOLS[tool_name](**tool_args)
        except Exception as e:
            observation = f"工具执行出错: {e}"

        preview = observation[:300].replace("\n", "\n   ")
        print(f"📤 结果: {preview}")

        messages.append({
            "role": "user",
            "content": f"工具执行结果:\n{observation}\n\n"
                       f"请继续。如果任务已完成，直接给出最终答案。",
        })

    print(f"\n⚠️ 达到最大步数 ({MAX_STEPS})，停止。")


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("🎯 输入任务: ")
    run_agent(task)
