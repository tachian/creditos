# CreditOS

CreditOS é uma plataforma SaaS de análise de crédito e risco. Este repositório usa um monorepo Python com `uv`, lock único, Ruff, Pyright progressivo e pytest.

## Requisitos Locais

- Python 3.13
- `uv`

## Comandos de Desenvolvimento

Execute sempre a partir da raiz do repositório:

```bash
uv sync
uv lock
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Também é possível usar o wrapper:

```bash
./scripts/dev sync
./scripts/dev lock
./scripts/dev lint
./scripts/dev format-check
./scripts/dev typecheck
./scripts/dev test
./scripts/dev all
```

## Estrutura Inicial

- `services/`: futuros microsserviços de domínio.
- `packages/`: futuros pacotes técnicos compartilhados, sem domínio compartilhado.
- `tests/`: testes automatizados.
- `infra/`: artefatos futuros de infraestrutura e IaC.
- `docs/`: documentação técnica e operacional.
- `scripts/`: comandos auxiliares de desenvolvimento.

## Adicionando Serviços ou Pacotes

Novos membros do workspace devem ficar em `services/<nome>` ou `packages/<nome>` e sempre conter seu próprio `pyproject.toml`. Depois de adicionar um membro:

```bash
uv lock
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

Ou execute o fluxo completo:

```bash
./scripts/dev all
```

Não adicione `requirements.txt`, Poetry, Pipenv, Hatch, tox, nox ou lockfiles paralelos sem nova decisão explícita.
