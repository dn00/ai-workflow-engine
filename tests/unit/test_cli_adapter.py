"""Unit tests for the CLI LLM adapter (all subprocess calls are mocked)."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.llm.base import LLMAdapterError, LLMResponse
from app.llm.cli_adapter import CliLLMAdapter


def _make_mock_workflow():
    """Create a mock workflow module with prompt attributes."""
    wf = MagicMock()
    wf.SYSTEM_PROMPT = "You are a test system."
    wf.PROMPT_VERSION = "1.0"
    wf.build_user_prompt = lambda text: f"Extract: {text}"
    return wf


class TestCliAdapterSubprocessArgs:
    # Task002 AC-1 `test_cli_adapter_subprocess_args`
    """Task002 AC-1 test_cli_adapter_subprocess_args"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_cli_adapter_subprocess_args(self, mock_run, mock_get_wf, tmp_path):
        """AC-1: CliLLMAdapter constructs correct subprocess args."""
        mock_get_wf.return_value = _make_mock_workflow()
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        adapter = CliLLMAdapter(model="sonnet", timeout=120)
        # We need to intercept the subprocess call to check args.
        # The adapter writes temp files and reads response - mock that flow.
        with patch.object(Path, "read_text", return_value='{"result": "ok"}'):
            try:
                adapter.generate_proposal("request text", "access_request")
            except Exception:
                pass

        assert mock_run.called
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == sys.executable
        assert "--model" in cmd
        assert "sonnet" in cmd
        assert "--timeout" in cmd
        assert "--prompt-file" in cmd
        assert "--response-file" in cmd
        assert "--system-prompt-file" in cmd


class TestCliAdapterReadsResponse:
    # Task002 AC-2 `test_cli_adapter_reads_response`
    """Task002 AC-2 test_cli_adapter_reads_response"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_cli_adapter_reads_response(self, mock_run, mock_get_wf, tmp_path):
        """AC-2: CliLLMAdapter reads response file and returns LLMResponse."""
        wf = _make_mock_workflow()
        mock_get_wf.return_value = wf
        expected_response = '{"request_type": "access_request"}'

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        # Patch tempfile to use our tmp_path
        adapter = CliLLMAdapter(model="sonnet")

        def run_side_effect(cmd, **kwargs):
            # Write response to the response file (find it in cmd args)
            resp_idx = cmd.index("--response-file") + 1
            Path(cmd[resp_idx]).write_text(expected_response)
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        mock_run.side_effect = run_side_effect

        result = adapter.generate_proposal("input", "access_request")
        assert isinstance(result, LLMResponse)
        assert result.raw_response == expected_response
        assert result.prompt_version == "1.0"


class TestCliAdapterResolvesPrompt:
    # Task002 AC-3 `test_cli_adapter_resolves_prompt`
    """Task002 AC-3 test_cli_adapter_resolves_prompt"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_cli_adapter_resolves_prompt(self, mock_run, mock_get_wf):
        """AC-3: CliLLMAdapter resolves prompt via workflow registry."""
        wf = _make_mock_workflow()
        mock_get_wf.return_value = wf

        written_files = {}

        def run_side_effect(cmd, **kwargs):
            # Capture what was written to prompt files
            prompt_idx = cmd.index("--prompt-file") + 1
            sys_idx = cmd.index("--system-prompt-file") + 1
            resp_idx = cmd.index("--response-file") + 1
            written_files["prompt"] = Path(cmd[prompt_idx]).read_text()
            written_files["system"] = Path(cmd[sys_idx]).read_text()
            Path(cmd[resp_idx]).write_text('{"ok": true}')
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        mock_run.side_effect = run_side_effect

        adapter = CliLLMAdapter()
        adapter.generate_proposal("test input", "access_request")

        mock_get_wf.assert_called_once_with("access_request")
        assert written_files["system"] == "You are a test system."
        assert "test input" in written_files["prompt"]


class TestCliAdapterNonJsonResponse:
    # Task002 EC-1 `test_cli_adapter_non_json_response`
    """Task002 EC-1 test_cli_adapter_non_json_response"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_cli_adapter_non_json_response(self, mock_run, mock_get_wf):
        """EC-1: CliLLMAdapter handles non-JSON raw response."""
        mock_get_wf.return_value = _make_mock_workflow()
        plain_text = "This is just plain text, not JSON"

        def run_side_effect(cmd, **kwargs):
            resp_idx = cmd.index("--response-file") + 1
            Path(cmd[resp_idx]).write_text(plain_text)
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        mock_run.side_effect = run_side_effect

        adapter = CliLLMAdapter()
        result = adapter.generate_proposal("input", "access_request")
        assert result.raw_response == plain_text


class TestCallClaudeErrorOnFailure:
    # Task002 EC-2 `test_call_claude_error_on_failure`
    """Task002 EC-2 test_call_claude_error_on_failure"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_call_claude_error_on_failure(self, mock_run, mock_get_wf):
        """EC-2: CliLLMAdapter raises on subprocess non-zero with error info."""
        mock_get_wf.return_value = _make_mock_workflow()
        error_json = json.dumps({"error": "claude_cli_failed", "returncode": 1, "stderr": "bad"})

        def run_side_effect(cmd, **kwargs):
            resp_idx = cmd.index("--response-file") + 1
            Path(cmd[resp_idx]).write_text(error_json)
            return subprocess.CompletedProcess(args=cmd, returncode=1)

        mock_run.side_effect = run_side_effect

        adapter = CliLLMAdapter()
        with pytest.raises(LLMAdapterError) as exc_info:
            adapter.generate_proposal("input", "access_request")
        assert "failed" in str(exc_info.value).lower()


class TestCliAdapterTimeout:
    # Task002 ERR-1 `test_cli_adapter_timeout`
    """Task002 ERR-1 test_cli_adapter_timeout"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_cli_adapter_timeout(self, mock_run, mock_get_wf):
        """ERR-1: CliLLMAdapter raises on subprocess timeout."""
        mock_get_wf.return_value = _make_mock_workflow()
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)

        adapter = CliLLMAdapter(timeout=120)
        with pytest.raises(LLMAdapterError) as exc_info:
            adapter.generate_proposal("input", "access_request")
        assert "timed out" in str(exc_info.value).lower()


class TestCliAdapterClaudeNotFound:
    # Task002 ERR-2 `test_cli_adapter_claude_not_found`
    """Task002 ERR-2 test_cli_adapter_claude_not_found"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_cli_adapter_claude_not_found(self, mock_run, mock_get_wf):
        """ERR-2: CliLLMAdapter raises when script/claude not found."""
        mock_get_wf.return_value = _make_mock_workflow()
        mock_run.side_effect = FileNotFoundError("No such file")

        adapter = CliLLMAdapter()
        with pytest.raises(LLMAdapterError) as exc_info:
            adapter.generate_proposal("input", "access_request")
        assert "not found" in str(exc_info.value).lower()


class TestCliAdapterSubprocessFailure:
    # Task002 ERR-3 `test_cli_adapter_subprocess_failure`
    """Task002 ERR-3 test_cli_adapter_subprocess_failure"""

    @patch("app.llm.cli_adapter.get_workflow")
    @patch("app.llm.cli_adapter.subprocess.run")
    def test_cli_adapter_subprocess_failure(self, mock_run, mock_get_wf):
        """ERR-3: CliLLMAdapter raises on subprocess non-zero exit."""
        mock_get_wf.return_value = _make_mock_workflow()
        error_json = json.dumps({"error": "claude_cli_failed", "returncode": 2, "stderr": "error"})

        def run_side_effect(cmd, **kwargs):
            resp_idx = cmd.index("--response-file") + 1
            Path(cmd[resp_idx]).write_text(error_json)
            return subprocess.CompletedProcess(args=cmd, returncode=2)

        mock_run.side_effect = run_side_effect

        adapter = CliLLMAdapter()
        with pytest.raises(LLMAdapterError) as exc_info:
            adapter.generate_proposal("input", "access_request")
        assert "failed" in str(exc_info.value).lower()
