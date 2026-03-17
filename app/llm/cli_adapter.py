"""CLI LLM adapter that shells out to claude via scripts/call-claude.py.

Uses file-based I/O through a subprocess boundary to invoke the Claude CLI
and return raw LLM responses.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from app.llm.base import AbstractLLMAdapter, LLMAdapterError, LLMResponse
from app.workflows.registry import get_workflow

_DEFAULT_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "call-claude.py"


class CliLLMAdapter(AbstractLLMAdapter):
    """Adapter that invokes claude -p via a subprocess wrapper script."""

    def __init__(
        self,
        model: str = "sonnet",
        timeout: int = 120,
        script_path: str | None = None,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.script_path = script_path or str(_DEFAULT_SCRIPT)

    def generate_proposal(self, input_text: str, workflow_type: str) -> LLMResponse:
        """Generate a proposal by shelling out to claude -p."""
        wf = get_workflow(workflow_type)
        system_prompt = wf.SYSTEM_PROMPT
        user_prompt = wf.build_user_prompt(input_text)
        prompt_version = wf.PROMPT_VERSION

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / "prompt.txt"
            system_file = Path(tmpdir) / "system.txt"
            response_file = Path(tmpdir) / "response.txt"

            prompt_file.write_text(user_prompt)
            system_file.write_text(system_prompt)

            cmd = [
                sys.executable,
                self.script_path,
                "--prompt-file", str(prompt_file),
                "--response-file", str(response_file),
                "--system-prompt-file", str(system_file),
                "--model", self.model,
                "--timeout", str(self.timeout),
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, timeout=self.timeout + 10)
            except subprocess.TimeoutExpired:
                raise LLMAdapterError(
                    f"LLM adapter timed out after {self.timeout}s"
                )
            except FileNotFoundError:
                raise LLMAdapterError(
                    f"Script not found: {self.script_path}"
                )

            if result.returncode != 0:
                error_detail = ""
                if response_file.exists():
                    error_detail = response_file.read_text()
                raise LLMAdapterError(
                    f"CLI adapter failed (exit {result.returncode}): {error_detail}"
                )

            raw_response = response_file.read_text()

        return LLMResponse(
            raw_response=raw_response,
            prompt_version=prompt_version,
            model_id=self.model,
        )
