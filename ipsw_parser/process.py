import os
import subprocess
from typing import Union


class ProcessExecutionError(OSError):
    """An external tool exited with a non-zero status."""

    def __init__(self, argv: list[str], returncode: int, stdout: str, stderr: str) -> None:
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        message = f"Unexpected exit code: {returncode}\nCommand line: {' '.join(argv)}"
        for name, output in (("Stdout", stdout), ("Stderr", stderr)):
            if output.strip():
                message += f"\n{name}: {output.strip()}"
        super().__init__(message)


def run(tool: str, *args: Union[str, "os.PathLike[str]"]) -> str:
    """Run an external tool to completion and return what it printed to stdout.

    :raises FileNotFoundError: if the tool is not installed.
    :raises ProcessExecutionError: if it exits with a non-zero status.
    """
    argv = [tool, *(os.fspath(arg) for arg in args)]
    result = subprocess.run(argv, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise ProcessExecutionError(argv, result.returncode, result.stdout, result.stderr)
    return result.stdout
