from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
LOCAL_INFRA = ROOT / "infra" / "local"
HARNESS_SCRIPT = ROOT / "scripts" / "local_harness.py"
DEV_SCRIPT = ROOT / "scripts" / "dev"


def load_harness_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("creditos_local_harness", HARNESS_SCRIPT)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def request_json(
    url: str,
    payload: dict[str, object] | list[object] | bytes,
) -> tuple[int, dict[str, object]]:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            response_body = response.read().decode("utf-8")
            status = int(response.status)
    except urllib.error.HTTPError as error:
        response_body = error.read().decode("utf-8")
        status = error.code

    decoded_body = json.loads(response_body)
    assert isinstance(decoded_body, dict)
    return status, decoded_body


def test_local_harness_documentation_and_config_exist() -> None:
    readme = LOCAL_INFRA / "README.md"
    env_example = LOCAL_INFRA / ".env.example"

    assert readme.is_file(), "Harness local deve documentar comandos de uso"
    assert env_example.is_file(), "Harness local deve fornecer .env.example seguro"
    assert HARNESS_SCRIPT.is_file(), "Harness local deve possuir script reproduzível"

    readme_content = readme.read_text(encoding="utf-8")

    assert "./scripts/dev harness-up" in readme_content
    assert "./scripts/dev harness-check" in readme_content
    assert "Ctrl+C" in readme_content
    assert "sem credenciais reais" in readme_content


def test_local_harness_env_example_does_not_contain_real_credentials_or_pii() -> None:
    content = (LOCAL_INFRA / ".env.example").read_text(encoding="utf-8").lower()

    forbidden_fragments = [
        "secret=",
        "password=",
        "token=",
        "cpf=",
        "cnpj=",
        "@gmail.com",
        "@hotmail.com",
        "@outlook.com",
        "-----begin",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in content, f"Configuração local contém fragmento sensível: {fragment}"

    assert "mock" in content
    assert "placeholder" in content


def test_local_harness_check_exercises_mocked_dependencies_without_external_access() -> None:
    result = subprocess.run(
        [sys.executable, str(HARNESS_SCRIPT), "check"],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "local harness check passed" in result.stdout
    assert "sample-service health=ok readiness=ready" in result.stdout
    assert "external-risk-mock=ok" in result.stdout
    assert "async-broker-mock=accepted" in result.stdout


def test_dev_script_harness_check_uses_documented_command() -> None:
    result = subprocess.run(
        [str(DEV_SCRIPT), "harness-check"],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "local harness check passed" in result.stdout


def test_async_mock_rejects_malformed_large_and_incomplete_payloads() -> None:
    harness = load_harness_module()
    servers = harness.start_harness(host="127.0.0.1", sample_service_port=0, mock_service_port=0)
    mock_service = next(server for server in servers if server.name == "creditos-local-mocks")
    publish_url = f"{mock_service.base_url}/mock/async-broker/v1/publish"

    try:
        invalid_json_status, invalid_json = request_json(publish_url, b"{invalid")
        large_status, large_payload = request_json(
            publish_url,
            b'{"oversized":"' + (b"x" * (harness.MAX_JSON_BODY_BYTES + 1)) + b'"}',
        )
        incomplete_status, incomplete_payload = request_json(
            publish_url,
            {
                "correlationid": "",
                "id": "event-id",
                "source": "creditos-local-harness",
                "specversion": "0.3",
                "tenantid": "tenant-placeholder",
                "type": "creditos.local.harness.ping",
            },
        )
    finally:
        harness.stop_harness(servers)

    assert invalid_json_status == 400
    assert invalid_json["error"] == "invalid_json"
    assert large_status == 413
    assert large_payload["error"] == "payload_too_large"
    assert incomplete_status == 400
    assert incomplete_payload["error"] == "invalid_cloudevent"
    assert incomplete_payload["invalid_fields"] == ["correlationid"]


def test_local_harness_rejects_non_loopback_bind() -> None:
    result = subprocess.run(
        [sys.executable, str(HARNESS_SCRIPT), "check", "--host", "0.0.0.0"],
        check=False,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
    )

    assert result.returncode == 1
    assert "só aceita bind loopback" in result.stderr


def test_local_harness_reports_invalid_env_port_cleanly() -> None:
    result = subprocess.run(
        [sys.executable, str(HARNESS_SCRIPT), "up"],
        check=False,
        cwd=ROOT,
        env={"CREDITOS_SAMPLE_SERVICE_PORT": "not-a-port"},
        text=True,
        capture_output=True,
        timeout=15,
    )

    assert result.returncode == 1
    assert "local harness error" in result.stderr
    assert "CREDITOS_SAMPLE_SERVICE_PORT" in result.stderr
