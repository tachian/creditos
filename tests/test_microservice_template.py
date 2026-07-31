from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
PACKAGES = ROOT / "packages"
SERVICE_TEMPLATE = ROOT / "services" / "service-template"
SERVICE_PACKAGE = SERVICE_TEMPLATE / "src" / "creditos_service_template"

REQUIRED_SERVICE_DIRECTORIES = [
    "domain",
    "domain/entities",
    "domain/value_objects",
    "domain/services",
    "domain/events",
    "domain/policies",
    "application",
    "application/use_cases",
    "application/ports",
    "adapters",
    "adapters/api",
    "adapters/grpc",
    "adapters/events",
    "adapters/persistence",
    "adapters/external",
    "bootstrap",
]

FORBIDDEN_DOMAIN_IMPORT_PARTS = {
    "adapters",
    "alembic",
    "aiohttp",
    "anthropic",
    "application",
    "bootstrap",
    "boto3",
    "botocore",
    "fastapi",
    "grpc",
    "httpx",
    "kubernetes",
    "nats",
    "openai",
    "opentelemetry",
    "pydantic",
    "requests",
    "redis",
    "sqlalchemy",
}

ALLOWED_SHARED_PACKAGE_NAMES = {
    "contracts",
    "observability",
    "security",
    "testing",
    "utilities",
    "utils",
}

FORBIDDEN_SHARED_PACKAGE_PARTS = {
    "business_rules",
    "domain",
    "entity",
    "entities",
    "policy",
    "policies",
    "repository",
    "repositories",
    "value_object",
    "value_objects",
}


def service_package_paths() -> list[Path]:
    package_paths: list[Path] = []

    for service_path in SERVICES.iterdir():
        if service_path.name.startswith(".") or not service_path.is_dir():
            continue

        src_path = service_path / "src"
        if not src_path.is_dir():
            continue

        package_paths.extend(
            package_path
            for package_path in src_path.iterdir()
            if package_path.is_dir() and (package_path / "domain").is_dir()
        )

    return package_paths


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
            elif node.level > 0:
                modules.update(alias.name for alias in node.names)

    return modules


def module_parts(module: str) -> set[str]:
    return {part.replace("-", "_") for part in module.split(".") if part}


def forbidden_domain_imports(path: Path) -> set[str]:
    forbidden_imports: set[str] = set()

    for module in imported_modules(path):
        forbidden_parts = module_parts(module) & FORBIDDEN_DOMAIN_IMPORT_PARTS
        forbidden_imports.update(forbidden_parts)

    return forbidden_imports


def test_service_template_is_workspace_member() -> None:
    pyproject_path = SERVICE_TEMPLATE / "pyproject.toml"
    assert pyproject_path.is_file(), "Template deve ser um membro válido do workspace uv"

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "creditos-service-template"
    assert pyproject["project"]["requires-python"] == ">=3.13"
    assert pyproject["project"]["dependencies"] == []
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    assert (SERVICE_PACKAGE / "__init__.py").is_file()


def test_service_template_has_ddd_hexagonal_layers() -> None:
    for relative_directory in REQUIRED_SERVICE_DIRECTORIES:
        assert (SERVICE_PACKAGE / relative_directory).is_dir(), (
            f"Diretório obrigatório ausente no template: {relative_directory}"
        )

    for relative_directory in ["unit", "integration", "contract"]:
        assert (SERVICE_TEMPLATE / "tests" / relative_directory).is_dir(), (
            f"Diretório obrigatório de testes ausente: {relative_directory}"
        )


def test_domain_layer_has_no_framework_or_infrastructure_imports() -> None:
    package_paths = service_package_paths()
    assert package_paths, "Workspace deve possuir ao menos um pacote de serviço com camada domain"

    for package_path in package_paths:
        domain_files = list((package_path / "domain").rglob("*.py"))
        assert domain_files, (
            f"Serviço deve possuir arquivos Python mínimos na camada domain: "
            f"{package_path.relative_to(ROOT)}"
        )

        for path in domain_files:
            forbidden_imports = forbidden_domain_imports(path)
            assert not forbidden_imports, (
                f"Import proibido no domínio em {path.relative_to(ROOT)}: "
                + ", ".join(sorted(forbidden_imports))
            )


def test_shared_packages_do_not_define_domain_constructs() -> None:
    for package_path in PACKAGES.iterdir():
        if package_path.name.startswith(".") or not package_path.is_dir():
            continue

        normalized_package_name = package_path.name.replace("-", "_")
        assert normalized_package_name in ALLOWED_SHARED_PACKAGE_NAMES, (
            f"Pacote compartilhado fora das categorias permitidas: {package_path.relative_to(ROOT)}"
        )

        forbidden_paths = [
            path
            for path in package_path.rglob("*")
            if any(
                part.replace("-", "_") in FORBIDDEN_SHARED_PACKAGE_PARTS
                for part in path.relative_to(package_path).parts
            )
        ]
        assert not forbidden_paths, (
            f"Pacote compartilhado não pode definir domínio: {package_path.relative_to(ROOT)}"
        )
