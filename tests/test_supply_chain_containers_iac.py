from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVICE_TEMPLATE = ROOT / "services" / "service-template"
DOCKERFILE = SERVICE_TEMPLATE / "Dockerfile"
CONTAINER_RUNTIME = (
    SERVICE_TEMPLATE / "src" / "creditos_service_template" / "bootstrap" / "container_runtime.py"
)
SUPPLY_CHAIN_PLAN = ROOT / "docs" / "standards" / "container-supply-chain.toml"
SUPPLY_CHAIN_DOC = ROOT / "docs" / "standards" / "container-supply-chain.md"
IAC_BACKLOG = ROOT / "infra" / "iac" / "backlog.toml"
RELEASE_METADATA_SCRIPT = ROOT / "scripts" / "container_release_metadata.py"


def dockerfile_text() -> str:
    assert DOCKERFILE.is_file(), "Imagem de exemplo deve existir no template de serviço"
    return DOCKERFILE.read_text(encoding="utf-8")


def load_toml(path: Path) -> dict[str, Any]:
    assert path.is_file(), f"Arquivo estruturado ausente: {path.relative_to(ROOT)}"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def effective_dockerfile_instructions() -> list[str]:
    instructions: list[str] = []
    current = ""

    for raw_line in dockerfile_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if current:
            current += " " + line
        else:
            current = line

        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue

        instructions.append(current)
        current = ""

    if current:
        instructions.append(current)

    return instructions


def test_service_template_container_uses_non_root_healthcheck_and_traceable_metadata() -> None:
    instructions = effective_dockerfile_instructions()
    dockerfile = "\n".join(instructions)
    from_instruction = instructions[0]

    assert re.fullmatch(
        r"FROM python:3\.13\.14-slim@sha256:[0-9a-f]{64} AS runtime",
        from_instruction,
    )
    assert "WORKDIR /app" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "sudo" not in dockerfile.lower()
    assert not any(instruction.startswith("EXPOSE ") for instruction in instructions)
    assert "HEALTHCHECK" in dockerfile
    assert "creditos_service_template.bootstrap.container_runtime" in dockerfile
    assert "healthcheck" in dockerfile
    assert "STOPSIGNAL SIGTERM" in dockerfile
    assert "org.opencontainers.image.revision" in dockerfile
    assert "org.opencontainers.image.version" in dockerfile
    assert "CREDITOS_COMMIT_SHA" in dockerfile
    assert "ARG COMMIT_SHA=unknown" not in dockerfile
    assert "ARG BUILD_CREATED=unknown" not in dockerfile
    assert 'test "${COMMIT_SHA}" != "unknown"' in dockerfile
    assert 'test "${BUILD_CREATED}" != "unknown"' in dockerfile


def test_container_runtime_handles_graceful_shutdown_without_domain_coupling() -> None:
    assert CONTAINER_RUNTIME.is_file(), "Runtime de exemplo deve existir para probes e shutdown"

    source = CONTAINER_RUNTIME.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    )

    assert {"signal", "time"}.issubset(imported_modules)
    assert "SIGTERM" in source
    assert "SIGINT" in source
    assert "shutdown_drain_seconds" in source
    assert "readiness_file_unavailable" in source
    assert 'choices=["serve", "healthcheck", "readiness"]' in source
    assert "domain" not in imported_modules
    assert "adapters" not in imported_modules
    assert "fastapi" not in imported_modules
    assert "kubernetes" not in imported_modules


def test_container_runtime_separates_liveness_from_readiness(tmp_path: Path) -> None:
    readiness_file = tmp_path / "service.ready"
    env = {
        "PYTHONPATH": str(SERVICE_TEMPLATE / "src"),
        "CREDITOS_READINESS_FILE": str(readiness_file),
    }

    liveness = subprocess.run(
        [
            sys.executable,
            "-m",
            "creditos_service_template.bootstrap.container_runtime",
            "healthcheck",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    not_ready = subprocess.run(
        [
            sys.executable,
            "-m",
            "creditos_service_template.bootstrap.container_runtime",
            "readiness",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    readiness_file.write_text("ready\n", encoding="utf-8")
    ready = subprocess.run(
        [
            sys.executable,
            "-m",
            "creditos_service_template.bootstrap.container_runtime",
            "readiness",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(liveness.stdout)["probe"] == "liveness"
    assert not_ready.returncode == 1
    assert json.loads(not_ready.stdout)["status"] == "not_ready"
    assert json.loads(ready.stdout)["status"] == "ready"
    assert json.loads(ready.stdout)["probe"] == "readiness"


def test_supply_chain_plan_covers_ecr_sbom_attestation_signing_and_slsa() -> None:
    plan = load_toml(SUPPLY_CHAIN_PLAN)
    container = plan["container_example"]  # type: ignore[index]
    supply_chain = plan["supply_chain"]  # type: ignore[index]
    attestations = plan["attestations"]  # type: ignore[index]
    permissions = plan["workflow_permissions"]  # type: ignore[index]

    assert re.fullmatch(r"python:3\.13\.14-slim@sha256:[0-9a-f]{64}", container["base_image"])
    assert container["exposed_port"] == "not-applicable-until-service-listens"  # type: ignore[index]
    assert "readiness" in container["readiness_probe"]  # type: ignore[index]
    assert container["digest_artifact_script"] == "scripts/container_release_metadata.py"  # type: ignore[index]
    assert supply_chain["registry"] == "amazon-ecr"  # type: ignore[index]
    assert supply_chain["immutable_digest_required"] is True  # type: ignore[index]
    assert set(supply_chain["sbom_formats"]) == {"spdx", "cyclonedx"}  # type: ignore[index]
    assert supply_chain["signing"] == "sigstore-cosign-keyless"  # type: ignore[index]
    assert supply_chain["slsa_initial_target"] == "build-l2"  # type: ignore[index]
    assert supply_chain["slsa_future_target"] == "build-l3"  # type: ignore[index]
    assert attestations["github_artifact_attestations"] == "applicable-while-public"  # type: ignore[index]
    assert (
        attestations["private_repository_action"] == "validate-plan-or-use-cosign-in-toto-fallback"
    )  # type: ignore[index]
    assert attestations["verification_required"] is True  # type: ignore[index]
    assert permissions["pull_request_id_token_write"] is False  # type: ignore[index]
    assert permissions["release_id_token_write"] is True  # type: ignore[index]
    assert SUPPLY_CHAIN_DOC.is_file(), "Documentação operacional da trilha deve existir"


def test_release_metadata_script_requires_and_records_image_digest(tmp_path: Path) -> None:
    metadata_file = tmp_path / "build-metadata.json"
    output = tmp_path / "release.json"
    digest = "sha256:" + "a" * 64
    metadata_file.write_text(json.dumps({"containerimage.digest": digest}), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(RELEASE_METADATA_SCRIPT),
            "--service",
            "creditos-service-template",
            "--image-ref",
            "creditos-service-template:test",
            "--commit-sha",
            "b" * 40,
            "--build-metadata-file",
            str(metadata_file),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    release = json.loads(output.read_text(encoding="utf-8"))

    assert release["schema"] == "creditos.container-release-metadata.v1"
    assert release["image_digest"] == digest
    assert release["commit_sha"] == "b" * 40

    invalid = subprocess.run(
        [
            sys.executable,
            str(RELEASE_METADATA_SCRIPT),
            "--service",
            "creditos-service-template",
            "--image-ref",
            "creditos-service-template:test",
            "--commit-sha",
            "unknown",
            "--image-digest",
            "sha256:not-valid",
            "--output",
            str(tmp_path / "invalid.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert invalid.returncode == 2
    assert not (tmp_path / "invalid.json").exists()


def test_supply_chain_markdown_matches_structured_plan() -> None:
    plan = load_toml(SUPPLY_CHAIN_PLAN)
    markdown = SUPPLY_CHAIN_DOC.read_text(encoding="utf-8")

    assert plan["supply_chain"]["registry"] == "amazon-ecr"  # type: ignore[index]
    assert "Amazon ECR" in markdown
    assert "SPDX ou CycloneDX" in markdown
    assert "Sigstore/Cosign keyless" in markdown
    assert "GitHub Artifact Attestations" in markdown
    assert "SLSA Build L2" in markdown
    assert "scripts/container_release_metadata.py" in markdown
    assert "Cosign/in-toto" in markdown


def test_iac_backlog_tracks_required_production_workstreams_without_blocking_product() -> None:
    backlog = load_toml(IAC_BACKLOG)

    metadata = backlog["metadata"]  # type: ignore[index]
    workstreams = backlog["workstreams"]  # type: ignore[index]
    workstream_ids = {workstream["id"] for workstream in workstreams}

    assert metadata["production_iac_scope"] == "deferred-pre-production-workstream"  # type: ignore[index]
    assert metadata["blocks_product_stories_after_minimum_foundation"] is False  # type: ignore[index]
    assert metadata["environments"] == ["dev", "sandbox", "staging", "prod"]  # type: ignore[index]
    assert {
        "iac-environments",
        "iac-network",
        "iac-eks",
        "iac-databases",
        "iac-nats-jetstream",
        "iac-observability",
        "iac-immutable-storage",
        "iac-kms-secrets",
        "iac-policies",
        "iac-tenant-isolation",
    }.issubset(workstream_ids)

    tenant_isolation = next(
        workstream for workstream in workstreams if workstream["id"] == "iac-tenant-isolation"
    )
    assert tenant_isolation["initial_model"] == "bridge"
    assert tenant_isolation["future_model"] == "silo"
