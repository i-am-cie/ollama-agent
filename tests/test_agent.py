import json
import subprocess
from unittest.mock import Mock, patch

import agent


# ---------- read_file ----------

def test_read_file_returns_content(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("hello agent", encoding="utf-8")
    assert agent.read_file(str(f)) == "hello agent"


def test_read_file_truncates_to_8000(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 9000, encoding="utf-8")
    content = agent.read_file(str(f))
    assert len(content) == 8000


# ---------- write_file ----------

def test_write_file_creates_parent_dirs_and_report(tmp_path):
    target = tmp_path / "sub" / "dir" / "note.txt"
    msg = agent.write_file(str(target), "hello")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello"
    assert "5 字符" in msg
    assert str(target) in msg


# ---------- list_dir ----------

def test_list_dir_marks_folder_and_file(tmp_path):
    (tmp_path / "folder").mkdir()
    (tmp_path / "file.txt").write_text("a", encoding="utf-8")
    listing = agent.list_dir(str(tmp_path))
    assert "📁 folder" in listing
    assert "📄 file.txt" in listing


def test_list_dir_non_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("a", encoding="utf-8")
    assert "不是目录" in agent.list_dir(str(f))


# ---------- search_in_files ----------

def test_search_finds_keyword_case_insensitive(tmp_path):
    (tmp_path / "a.txt").write_text("TODO: fix this", encoding="utf-8")
    result = agent.search_in_files("todo", str(tmp_path))
    assert "a.txt" in result
    assert "TODO: fix this" in result


def test_search_no_match(tmp_path):
    (tmp_path / "a.txt").write_text("nothing here", encoding="utf-8")
    result = agent.search_in_files("missing", str(tmp_path))
    assert "未找到" in result


def test_search_skips_hidden_and_ignored(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.txt").write_text("KEYWORD hit", encoding="utf-8")
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.txt").write_text("KEYWORD hidden", encoding="utf-8")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "dep.txt").write_text("KEYWORD dep", encoding="utf-8")
    (tmp_path / ".secret.txt").write_text("KEYWORD dotfile", encoding="utf-8")

    result = agent.search_in_files("KEYWORD", str(tmp_path))
    assert "real.txt" in result
    assert "secret.txt" not in result
    assert "dep.txt" not in result
    assert ".secret.txt" not in result


# ---------- extract_action ----------

def test_extract_valid_action():
    text = '思考一下\n{"thought": "列目录", "action": "list_dir", "action_input": {"path": "."}}'
    action = agent.extract_action(text)
    assert action is not None
    assert action["action"] == "list_dir"
    assert action["action_input"] == {"path": "."}


def test_extract_unknown_tool_returns_none():
    text = '{"action": "rm_rf", "action_input": {}}'
    assert agent.extract_action(text) is None


def test_extract_plain_text_returns_none():
    assert agent.extract_action("这是最终答案，不需要调用工具。") is None


def test_extract_action_inside_markdown():
    text = '```json\n{"thought": "读文件", "action": "read_file", "action_input": {"path": "a.txt"}}\n```'
    action = agent.extract_action(text)
    assert action is not None
    assert action["action"] == "read_file"


# ---------- call_llm ----------

def test_call_llm_sends_payload_and_returns_content():
    fake_resp = Mock()
    fake_resp.raise_for_status.return_value = None
    fake_resp.json.return_value = {"message": {"content": "模型回复"}}

    with patch.object(agent.requests, "post", return_value=fake_resp) as mock_post:
        messages = [{"role": "user", "content": "hi"}]
        result = agent.call_llm(messages)

    assert result == "模型回复"
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == agent.MODEL
    assert kwargs["json"]["messages"] == messages
    assert kwargs["json"]["stream"] is False
    assert kwargs["timeout"] == 120


# ---------- run_command / git_status ----------

def test_run_command_success():
    fake = Mock(returncode=0, stdout="ok", stderr="")
    with patch.object(agent.subprocess, "run", return_value=fake):
        result = agent.run_command("echo ok")
    assert "[exit 0]" in result
    assert "ok" in result


def test_run_command_timeout():
    with patch.object(agent.subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=30)):
        result = agent.run_command("sleep 100")
    assert "超时" in result


def test_git_status_success():
    fake = Mock(stdout="M agent.py", stderr="")
    with patch.object(agent.subprocess, "run", return_value=fake):
        result = agent.git_status()
    assert "M agent.py" in result


# ---------- run_agent 主循环 ----------

def test_run_agent_final_answer_first_round():
    with patch.object(agent, "call_llm", return_value="这是最终答案") as mock_llm:
        result = agent.run_agent("随便做点什么")
    assert result == "这是最终答案"
    assert mock_llm.call_count == 1


def test_run_agent_runs_tool_then_finishes():
    action_json = json.dumps(
        {"thought": "列目录", "action": "list_dir", "action_input": {"path": "."}},
        ensure_ascii=False,
    )
    fake_tool = Mock(return_value="📄 a.txt")

    with patch.object(agent, "call_llm", side_effect=[action_json, "完成"]), \
            patch.dict(agent.TOOLS, {"list_dir": fake_tool}):
        result = agent.run_agent("列出文件")

    assert result == "完成"
    fake_tool.assert_called_once_with(path=".")


def test_run_agent_hits_max_steps(monkeypatch):
    monkeypatch.setattr(agent, "MAX_STEPS", 2)
    action_json = json.dumps(
        {"thought": "继续", "action": "list_dir", "action_input": {"path": "."}},
        ensure_ascii=False,
    )
    fake_tool = Mock(return_value="obs")

    with patch.object(agent, "call_llm", return_value=action_json) as mock_llm, \
            patch.dict(agent.TOOLS, {"list_dir": fake_tool}):
        result = agent.run_agent("卡住的任务")

    assert result is None
    assert mock_llm.call_count == 2
