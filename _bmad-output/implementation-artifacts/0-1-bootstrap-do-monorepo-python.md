# Story 0.1: Bootstrap do Monorepo Python

Status: ready-for-dev

## Story

Como equipe de engenharia,
quero criar a estrutura inicial do monorepo Python,
para que todos os serviços e pacotes sigam a mesma base técnica desde o início.

## Acceptance Criteria

1. **Given** o repositório greenfield, **when** o bootstrap inicial é aplicado, **then** existem diretórios base `services/`, `packages/`, `tests/`, `infra/`, `docs/` e `scripts/`, **and** existe configuração raiz de workspace `uv`, lock único, Ruff, Pyright progressivo e pytest.
2. **Given** um novo serviço ou pacote, **when** ele é incluído no workspace, **then** usa comandos padronizados de instalação, lint, typecheck e testes, **and** não introduz dependências fora do lock aprovado.

## Tasks / Subtasks

- [ ] Criar estrutura raiz do repositório (AC: 1)
  - [ ] Criar `services/`, `packages/`, `tests/`, `infra/`, `docs/` e `scripts/`.
  - [ ] Adicionar placeholders mínimos apenas quando necessário para versionamento de diretórios vazios.
  - [ ] Não criar ainda os sete microsserviços de domínio; isso pertence às stories seguintes.
- [ ] Configurar workspace Python com `uv` (AC: 1, 2)
  - [ ] Criar `pyproject.toml` raiz com metadata do projeto, `requires-python` alinhado a Python 3.13 e `[tool.uv.workspace]`.
  - [ ] Configurar membros futuros de workspace para `services/*` e `packages/*`, garantindo que nenhum diretório correspondente exista sem `pyproject.toml`.
  - [ ] Gerar `uv.lock` pelo próprio `uv`; o lock deve ser versionado e não editado manualmente.
  - [ ] Criar `.python-version` com baseline Python 3.13.
- [ ] Configurar comandos padronizados de desenvolvimento (AC: 1, 2)
  - [ ] Criar scripts ou comandos documentados para instalação/sync, lint, format check, typecheck e testes.
  - [ ] Os comandos devem usar `uv` como entrypoint principal e funcionar a partir da raiz do repositório.
  - [ ] Documentar como executar os comandos na raiz em `README.md` ou `docs/`.
- [ ] Configurar qualidade mínima inicial (AC: 1, 2)
  - [ ] Configurar Ruff no `pyproject.toml` para lint e format.
  - [ ] Configurar Pyright em modo progressivo, com alvo Python 3.13 e sem exigir cobertura estrita total em código ainda inexistente.
  - [ ] Configurar pytest para descobrir testes em `tests/`.
  - [ ] Adicionar um teste mínimo/smoke de tooling somente se necessário para validar a suíte sem introduzir domínio falso.
- [ ] Validar isolamento de dependências e lock (AC: 2)
  - [ ] Confirmar que dependências de desenvolvimento entram no grupo apropriado e passam pelo lock.
  - [ ] Confirmar que não existem `requirements.txt`, lockfiles paralelos ou dependências instaladas fora do fluxo `uv`.
  - [ ] Documentar o procedimento para adicionar futuro serviço/pacote ao workspace sem quebrar o lock.
- [ ] Atualizar rastreamento BMAD (AC: 1, 2)
  - [ ] Manter esta story como `ready-for-dev` até início de implementação.
  - [ ] Ao iniciar desenvolvimento, atualizar `sprint-status.yaml` para `in-progress`; ao concluir, mover para `review` e depois `done`.

## Dev Notes

### Escopo da Story

- Esta story cria a fundação mínima do repositório para permitir implementação consistente das demais stories.
- Esta story não deve implementar domínio, API pública, gRPC, NATS, banco, containers produtivos, CI completo, IaC completo ou microsserviços reais.
- O objetivo é deixar a raiz do monorepo pronta para que Story 0.2 crie o template DDD/hexagonal de microsserviço sem retrabalho.

### Requisitos Técnicos Obrigatórios

- Runtime baseline: Python 3.13.
- Gerenciador de projeto/dependências: `uv` workspace com `uv.lock` único.
- Lint e formatação: Ruff.
- Typecheck: Pyright progressivo.
- Testes: pytest; `pytest-asyncio` deve estar disponível quando necessário para serviços async, mesmo que esta story ainda não crie serviços async.
- A raiz do repositório deve ser a fonte dos comandos de desenvolvimento.
- Não adicionar Poetry, Pipenv, Hatch, tox, nox, Makefile obrigatório ou lockfile alternativo sem nova decisão explícita.

### Arquitetura e Guardrails

- A arquitetura aprovada define Python 3.13, `uv` workspace, Ruff, Pyright, pytest/pytest-asyncio e lock único como base do backend.
- O domínio deve permanecer independente de frameworks e infraestrutura nas próximas stories; esta story deve preparar a estrutura sem violar esse princípio.
- `packages/` futuramente só pode conter contratos, observabilidade, segurança, testes e utilidades técnicas genéricas; não deve conter entidades ou regras de domínio compartilhadas.
- `services/` futuramente conterá os microsserviços de domínio, mas eles não devem ser criados nesta story para evitar serviços vazios ou fronteiras prematuras.

### Estrutura Esperada

```text
creditos/
  .python-version
  pyproject.toml
  uv.lock
  README.md
  services/
  packages/
  tests/
  infra/
  docs/
  scripts/
```

### Comandos Esperados

Os nomes exatos podem ser scripts em `scripts/` ou comandos documentados, mas a story deve entregar equivalentes verificáveis para:

- Instalação/sync: `uv sync`
- Lock: `uv lock`
- Lint: `uv run ruff check .`
- Format check: `uv run ruff format --check .`
- Typecheck: `uv run pyright`
- Testes: `uv run pytest`

Se a forma de executar Pyright exigir decisão de empacotamento adicional, não substituir por outra ferramenta silenciosamente; documentar a limitação e propor ajuste explícito.

### Pesquisa Técnica Atual

- `uv` workspaces usam membros definidos em `tool.uv.workspace`, cada membro tem seu próprio `pyproject.toml` e o workspace compartilha um único `uv.lock`; `uv lock` opera no workspace inteiro e `uv run`/`uv sync` aceitam `--package` para membros específicos. Fonte: https://docs.astral.sh/uv/concepts/projects/workspaces/
- `uv.lock` é um lockfile universal/cross-platform, gerenciado pelo `uv`, e deve ser versionado para instalações reproduzíveis. Fonte: https://docs.astral.sh/uv/concepts/projects/layout/
- Ruff pode ser configurado por `pyproject.toml`, `ruff.toml` ou `.ruff.toml`; para este repositório, preferir `pyproject.toml` raiz para manter a configuração junto do workspace. Fonte: https://docs.astral.sh/ruff/configuration/
- Ruff formatter é executado via `ruff format` e suporta `--check` para validar formatação sem modificar arquivos. Fonte: https://docs.astral.sh/ruff/formatter/
- Pyright suporta `typeCheckingMode` e `pythonVersion`; usar modo progressivo para permitir endurecimento por etapas. Fonte: https://github.com/microsoft/pyright/blob/main/docs/configuration.md
- pytest suporta configuração em `pyproject.toml`; para compatibilidade ampla, `[tool.pytest.ini_options]` continua aceitável. Fonte: https://docs.pytest.org/en/stable/reference/customize.html

### Project Structure Notes

- Não existe código Python inicial no repositório no momento desta story.
- Não há story anterior no Epic 0; esta é a primeira story da implementação.
- O sprint planning marcou `0-1-bootstrap-do-monorepo-python` como primeiro item de backlog.
- `project-context.md` ainda não existe; quando for criado futuramente, deve ser referenciado por stories seguintes.

### Testing Requirements

- Validar que `pyproject.toml` é parseável.
- Validar que `uv lock` gera ou confirma `uv.lock`.
- Validar que `uv sync` funciona a partir da raiz.
- Validar que lint, format check, typecheck e pytest rodam com sucesso no estado inicial.
- Não criar testes de domínio falsos apenas para satisfazer cobertura.

### Anti-Patterns a Evitar

- Criar microsserviços vazios nesta story.
- Criar domínio compartilhado em `packages/`.
- Criar múltiplos lockfiles.
- Instalar dependências fora do `uv`.
- Introduzir ferramenta alternativa por conveniência local.
- Fazer CI/CD completo nesta story; CI inicial é Story 0.6.
- Fazer template DDD/hexagonal completo nesta story; isso é Story 0.2.

## References

- `_bmad-output/planning-artifacts/epics.md` — Epic 0 e Story 0.1.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-16, AD-13, AD-23 e Structural Seed.
- `_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-30.md` — readiness final e warnings.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — ordem de implementação.

## Dev Agent Record

### Agent Model Used

TBD pelo agente de desenvolvimento.

### Debug Log References

TBD.

### Completion Notes List

- Story criada pelo workflow `bmad-create-story`.
- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

- `_bmad-output/implementation-artifacts/0-1-bootstrap-do-monorepo-python.md`
