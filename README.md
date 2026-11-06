# ollama-agent

> A tiny local AI agent that can read files, write files, search code, check git status, and run shell commands — powered entirely by Ollama. No API keys, no cloud, ~200 lines of Python.

```
🎯 任务: 帮我把当前目录下所有 .txt 文件合并成一个 notes.txt
🤖 步骤 1: 先看看目录里有什么文件
🔧 调用 list_dir({})
📤 结果: 📄 a.txt 📄 b.txt 📄 README.md
🤖 步骤 2: 读取两个 txt 文件内容
🔧 调用 read_file({"path": "a.txt"})
...
✅ 最终答案: 已合并完成，notes.txt 共 2340 字符。
```

## Why

Every "build an AI agent" tutorial tells you to install LangChain, pull in a vector DB, get an OpenAI key, and wire together 10 abstract classes. This repo is the opposite:

- **One file.** Read it in 5 minutes.
- **No frameworks.** Just `requests` + Ollama.
- **Fully offline.** Your code never leaves your machine.
- **ReAct loop.** Think → act → observe → repeat, implemented in ~200 lines.

## Quick Start

```bash
# 1. Install Ollama and pull a model
#    https://ollama.com/download
ollama pull qwen2.5:7b

# 2. Clone and run
git clone https://github.com/i-am-cie/ollama-agent.git
cd ollama-agent
pip install requests
python agent.py "帮我列出当前目录的文件，并总结每个文件是干什么的"
```

Or run interactively:

```bash
python agent.py
# 🎯 输入任务: 
```

## What it can do

| Tool | What it does |
|---|---|
| `read_file(path)` | Read any text file |
| `write_file(path, content)` | Create or overwrite a file |
| `run_command(cmd)` | Run a shell command (30s timeout) |
| `list_dir(path)` | List directory contents |
| `search_in_files(keyword, path)` | Search for keywords across files |
| `git_status()` | Show git status and recent commits |

Give it any task that involves reading files, writing notes, searching code, checking git, or running commands — it figures out the steps itself.

## Example Tasks

- "帮我找出项目里所有用到 `TODO` 的地方"
- "看看当前git状态，帮我写一个commit message"
- "把这个文件夹里所有的.md文件合并成一个文档"
- "分析这个Python项目的结构，总结每个模块的作用"

## How it works

The agent uses a simple **ReAct** loop:

```
User task
    ↓
LLM thinks: "I need to see what files exist first"
    ↓
LLM outputs JSON: {"action": "list_dir", "action_input": {}}
    ↓
Python executes list_dir() → returns the file list
    ↓
LLM sees the result: "Now I'll read a.txt"
    ↓
... repeat until LLM stops calling tools and gives a final answer
```

No function-calling API, no LangChain agents — just a well-crafted system prompt and JSON parsing.

## Configuration

```bash
# Use a different model (anything Ollama supports)
AGENT_MODEL=qwen2.5:3b python agent.py "你的任务"
```

Lower VRAM? Use `qwen2.5:3b` (~2 GB).

## Project Structure

```
ollama-agent/
├── agent.py    # The entire agent (system prompt + tools + loop)
└── README.md
```

## Roadmap

- [x] Add `search_in_files` tool
- [x] Add `git_status` tool
- [ ] Web UI (Gradio/Flask)
- [ ] Edit existing files (diff-based)
- [ ] Streaming output
- [ ] More tools (web search, python exec)

## License

MIT — do whatever you want.

---

⭐ Star if this saves you an afternoon of figuring out how ReAct actually works.
