import sys
from pathlib import Path

import pytest

from ipsw_parser.process import ProcessExecutionError, run


def test_run_returns_stdout() -> None:
    assert run(sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)").splitlines() == ["out"]


def test_run_accepts_path_arguments(tmp_path: Path) -> None:
    script = tmp_path / "script with space.py"
    script.write_text("import sys; print(sys.argv[1])")

    assert run(sys.executable, script, tmp_path).strip() == str(tmp_path)


def test_run_reports_a_failing_tool_with_its_output() -> None:
    with pytest.raises(ProcessExecutionError) as excinfo:
        run(sys.executable, "-c", "import sys; print('partial'); print('the reason', file=sys.stderr); sys.exit(3)")

    error = excinfo.value
    assert error.returncode == 3
    assert error.stdout.strip() == "partial"
    assert error.stderr.strip() == "the reason"
    assert "Unexpected exit code: 3" in str(error)
    assert "the reason" in str(error)


def test_a_failing_tool_is_an_oserror() -> None:
    # Callers that guard an extraction with `except OSError` keep catching a failed tool
    with pytest.raises(OSError):
        run(sys.executable, "-c", "raise SystemExit(1)")


def test_run_of_a_missing_tool_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        run("ipsw-parser-no-such-tool")
