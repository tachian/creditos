from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from creditos_audit_evidence.bootstrap import container_runtime


def test_healthcheck_and_readiness_reflect_ready_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readiness_file = tmp_path / "audit.ready"
    monkeypatch.setattr(container_runtime, "READINESS_FILE", readiness_file)

    assert container_runtime.healthcheck() == 0
    assert container_runtime.readiness() == 1

    readiness_file.write_text("ready\n", encoding="utf-8")
    assert container_runtime.readiness() == 0


def test_serve_keeps_process_alive_until_shutdown(tmp_path: Path) -> None:
    readiness_file = tmp_path / "audit.ready"
    env = {
        **os.environ,
        "CREDITOS_READINESS_FILE": str(readiness_file),
        "CREDITOS_SHUTDOWN_DRAIN_SECONDS": "0",
        "PYTHONPATH": os.pathsep.join(
            (
                str(Path.cwd() / "services/audit-evidence/src"),
                str(Path.cwd() / "packages/observability/src"),
                str(Path.cwd() / "packages/security/src"),
                os.environ.get("PYTHONPATH", ""),
            )
        ),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "creditos_audit_evidence.bootstrap.container_runtime",
            "serve",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not readiness_file.exists():
            time.sleep(0.05)

        assert readiness_file.exists()
        assert process.poll() is None

        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0
        assert stdout == ""
        assert stderr == ""
        assert not readiness_file.exists()
    finally:
        if process.poll() is None:
            process.kill()
