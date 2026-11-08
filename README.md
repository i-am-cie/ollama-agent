# ollama-agent

A ~200-line, single-file local AI agent that can read and write files, search
code, inspect git state, and run shell commands. It talks to a local model served
by [Ollama](https://ollama.com) — no API keys, no cloud, no agent framework.

## What it does

`agent.py` runs a small ReAct-style loop: the model writes a JSON action, Python
executes one of six local tools, the result is appended to the conversation, and
the loop repeats until the model stops requesting tools or the step limit is hit.
There is no function-calling API involved — only a system prompt plus JSON parsing.

Available tools:

| Tool | Behaviour |
|---|---|
| `read_file(path)` | Read a UTF-8 text file (first 8000 characters) |
| `write_file(path, content)` | Create/overwrite a file, creating parent directories |
| `run_command(cmd)` | Run a shell command via `subprocess`, 30 s timeout, captures stdout/stderr |
| `list_dir(path)` | List files and folders in a directory |
| `search_in_files(keyword, path)` | Case-insensitive recursive text search (stops at 20 matches) |
| `git_status()` | `git status --short` plus the last 5 commits |

## Requirements

- Python 3.8+
- [Ollama](https://ollama.com/download) installed and running locally
- A chat model that can follow the JSON-in-text instructions. The default is
  `qwen2.5:7b`, because the system prompt is written for Qwen 2.5; other
  instruction-following models generally work but may be less reliable.

```bash
ollama pull qwen2.5:7b
```

A smaller model such as `qwen2.5:3b` needs less RAM/VRAM but may make more
mistakes in the JSON format.

## Install

```bash
git clone https://github.com/i-am-cie/ollama-agent.git
cd ollama-agent
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Run

Pass the task on the command line:

```bash
python agent.py "List the files in this directory and summarise what each one does"
```

Or start it interactively and type the task when prompted:

```bash
python agent.py
```

At each step the script prints the model's thought, the tool call and a short
preview of the tool result. When the model stops calling tools, its reply is
printed as the final answer.

## Usage

Example tasks that fit the available tools:

- "Find every TODO in this project."
- "Check the git status and suggest a commit message."
- "Merge all Markdown files in this folder into one document."
- "Summarise what each Python file in this directory does."

The model decides which tools to call and in what order; the script only executes
one tool per step.

## Configuration

| Setting | Where it comes from | Default |
|---|---|---|
| `OLLAMA_HOST` | environment variable (a bare `host:port` is also accepted) | `http://localhost:11434` |
| `AGENT_MODEL` | environment variable | `qwen2.5:7b` |
| `MAX_STEPS` | constant in `agent.py` | `15` |

```bash
# Talk to an Ollama instance on another host/port
OLLAMA_HOST=192.168.1.20:11434 python agent.py "list the files here"

# Use a smaller model
AGENT_MODEL=qwen2.5:3b python agent.py "summarise README.md"
```

On Windows PowerShell use `$env:OLLAMA_HOST="..."` / `$env:AGENT_MODEL="..."`.

The tool list and the JSON output format are defined by `SYSTEM_PROMPT` at the
top of `agent.py`.

## How it works

```
task ──► system prompt + task
              │
              ▼
        POST /api/chat  ──► model reply (natural language, maybe JSON)
              │
              ▼
    extract_action() ── no action ──► print final answer, stop
              │ action
              ▼
      execute one tool, append observation to messages
              │
              └──► next step (up to MAX_STEPS)
```

`extract_action()` takes the text between the first `{` and the last `}` and
parses it as JSON. If parsing fails, or the action is not one of the known
tools, the reply is treated as the final answer. The script is intentionally
small: reading `agent.py` top to bottom is enough to change the tools, the
prompt, or the loop.

## Limitations

- **No sandbox and no confirmation.** `run_command` executes whatever the model
  writes, with your user permissions, and `write_file` can overwrite files.
  Run it only in a directory you are willing to let a model modify.
- **Model-dependent JSON.** If the model does not emit the expected JSON shape,
  the reply is treated as the final answer; there is no retry or repair.
- **Truncated observations.** File contents are cut at 8000 characters, command
  stdout at 3000 characters, stderr at 1000; searches stop after 20 matches.
- **Growing context.** Every observation is appended to the message list with no
  trimming or summarisation, so long sessions grow until the model's context
  limit is reached.
- **Text files only.** `read_file` assumes UTF-8 (invalid bytes are replaced);
  binary files are not handled.
- **Single tool per step.** It cannot batch calls, and there is no streaming.
- **Chinese system prompt.** The prompt asks the model to think and answer in
  Chinese; edit `SYSTEM_PROMPT` if you want English output.
- **No tests.** Correctness depends on the model's planning.

## License

[MIT](./LICENSE) © 2026 i-am-cie

## 中文说明

一个约 200 行、单文件的本地 AI Agent，用 Ollama 在本地跑模型，可以读写文件、
在文件里搜索关键词、查看 git 状态、执行 shell 命令。不需要 API key，也没有
LangChain 之类的框架。

- **依赖**：Python 3.8+、本地已运行的 Ollama、一个能按提示输出 JSON 的模型（默认 `qwen2.5:7b`）。
- **安装**：`pip install -r requirements.txt`，再 `ollama pull qwen2.5:7b`。
- **运行**：`python agent.py "任务描述"`，或直接 `python agent.py` 交互输入。
- **配置**：环境变量 `OLLAMA_HOST`（默认 `http://localhost:11434`）、`AGENT_MODEL`（默认 `qwen2.5:7b`）；`MAX_STEPS` 在 `agent.py` 里，默认 15。
- **原理**：模型按系统提示输出 `{"thought": ..., "action": ..., "action_input": ...}`，脚本解析后执行对应工具，把结果追加回对话，循环直到模型不再调用工具。
- **限制**：没有沙箱、没有执行确认，`run_command` 会以你的用户权限运行模型生成的命令，请只在可被修改的目录里使用；工具输出会被截断（文件 8000 字符、命令输出 3000 字符、搜索最多 20 条）；上下文不裁剪；只支持文本文件；系统提示是中文的。
- **License**：MIT。
