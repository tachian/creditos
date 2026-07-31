---
baseline_commit: e7573b30317384024cfb2d999e33dc665c1e95a6
---

# Story 0.1: Bootstrap do Monorepo Python

Status: done

## Story

Como equipe de engenharia,
quero criar a estrutura inicial do monorepo Python,
para que todos os serviços e pacotes sigam a mesma base técnica desde o início.

## Acceptance Criteria

1. **Given** o repositório greenfield, **when** o bootstrap inicial é aplicado, **then** existem diretórios base `services/`, `packages/`, `tests/`, `infra/`, `docs/` e `scripts/`, **and** existe configuração raiz de workspace `uv`, lock único, Ruff, Pyright progressivo e pytest.
2. **Given** um novo serviço ou pacote, **when** ele é incluído no workspace, **then** usa comandos padronizados de instalação, lint, typecheck e testes, **and** não introduz dependências fora do lock aprovado.

## Tasks / Subtasks

- [x] Criar estrutura raiz do repositório (AC: 1)
  - [x] Criar `services/`, `packages/`, `tests/`, `infra/`, `docs/` e `scripts/`.
  - [x] Adicionar placeholders mínimos apenas quando necessário para versionamento de diretórios vazios.
  - [x] Não criar ainda os sete microsserviços de domínio; isso pertence às stories seguintes.
- [x] Configurar workspace Python com `uv` (AC: 1, 2)
  - [x] Criar `pyproject.toml` raiz com metadata do projeto, `requires-python` alinhado a Python 3.13 e `[tool.uv.workspace]`.
  - [x] Configurar membros futuros de workspace para `services/*` e `packages/*`, garantindo que nenhum diretório correspondente exista sem `pyproject.toml`.
  - [x] Gerar `uv.lock` pelo próprio `uv`; o lock deve ser versionado e não editado manualmente.
  - [x] Criar `.python-version` com baseline Python 3.13.
- [x] Configurar comandos padronizados de desenvolvimento (AC: 1, 2)
  - [x] Criar scripts ou comandos documentados para instalação/sync, lint, format check, typecheck e testes.
  - [x] Os comandos devem usar `uv` como entrypoint principal e funcionar a partir da raiz do repositório.
  - [x] Documentar como executar os comandos na raiz em `README.md` ou `docs/`.
- [x] Configurar qualidade mínima inicial (AC: 1, 2)
  - [x] Configurar Ruff no `pyproject.toml` para lint e format.
  - [x] Configurar Pyright em modo progressivo, com alvo Python 3.13 e sem exigir cobertura estrita total em código ainda inexistente.
  - [x] Configurar pytest para descobrir testes em `tests/`.
  - [x] Adicionar um teste mínimo/smoke de tooling somente se necessário para validar a suíte sem introduzir domínio falso.
- [x] Validar isolamento de dependências e lock (AC: 2)
  - [x] Confirmar que dependências de desenvolvimento entram no grupo apropriado e passam pelo lock.
  - [x] Confirmar que não existem `requirements.txt`, lockfiles paralelos ou dependências instaladas fora do fluxo `uv`.
  - [x] Documentar o procedimento para adicionar futuro serviço/pacote ao workspace sem quebrar o lock.
- [x] Atualizar rastreamento BMAD (AC: 1, 2)
  - [x] Manter esta story como `ready-for-dev` até início de implementação.
  - [x] Ao iniciar desenvolvimento, atualizar `sprint-status.yaml` para `in-progress`; ao concluir, mover para `review` e depois `done`.

### Review Findings

- [x] [Review][Patch] Pyright padrão não cobre futuros serviços e pacotes do workspace [pyproject.toml:38]
- [x] [Review][Patch] `./scripts/dev all` não garante validação imutável do lock [scripts/dev:25]
- [x] [Review][Patch] Comando inválido do wrapper termina com sucesso [scripts/dev:32]
- [x] [Review][Patch] Política contra lockfiles alternativos só valida a raiz do repositório [tests/test_repository_bootstrap.py:29]
- [x] [Review][Patch] Validação de membros do workspace ignora qualquer diretório oculto [tests/test_repository_bootstrap.py:48]
- [x] [Review][Patch] Procedimento de novo serviço ou pacote omite lint e typecheck [README.md:44]

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

Codex

### Debug Log References

- 2026-07-31: Início da implementação; baseline commit registrado.
- 2026-07-31: Jira `CTOS-2` movido para `Em andamento`.
- 2026-07-31: Ambiente local ainda não possui `uv` nem Python 3.13 instalados; validação com `uv` será feita após instalação isolada da ferramenta.
- 2026-07-31: Teste red inicial executado com `python3 tests/test_repository_bootstrap.py` e falhou por ausência de `services/`, como esperado.
- 2026-07-31: `uv` 0.12.0 instalado de forma isolada em `/tmp/creditos-tools`; Python 3.13.14 gerenciado pelo `uv` baixado para `/tmp/creditos-uv-python`.
- 2026-07-31: `uv lock` e `uv sync` executados com cache em `/tmp/creditos-uv-cache`.
- 2026-07-31: Validação final executada com `./scripts/dev all`; lint, format check, typecheck e pytest passaram.
- 2026-07-31: Jira `CTOS-2` movido para `Em análise`; subtarefas `CTOS-3` a `CTOS-8` movidas para `Concluído`.
- 2026-07-31: Achados do code review aplicados: Pyright expandido, `all` com lock imutável, comando inválido com erro, guardrails recursivos de lockfile, allowlist de placeholder e documentação de fluxo completo.
- 2026-07-31: Validação pós-review executada com `./scripts/dev all`; lint, format check, typecheck e pytest passaram.

### Completion Notes List

- Story criada pelo workflow `bmad-create-story`.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Criada estrutura raiz mínima com `services/`, `packages/`, `tests/`, `infra/`, `docs/` e `scripts/`, sem criar microsserviços ou domínio real.
- Configurado monorepo Python com `uv`, Python 3.13, `uv.lock` único, Ruff, Pyright progressivo, pytest e pytest-asyncio.
- Adicionado wrapper `scripts/dev` e documentação em português para comandos de desenvolvimento e política de dependências.
- Adicionado teste smoke de bootstrap para validar estrutura, configuração do workspace e ausência de lockfiles alternativos.
- Confirmado que `./scripts/dev all` passa com Python 3.13.14 gerenciado pelo `uv`.
- Corrigidos todos os achados classificados como `patch` no code review da Story 0.1.

### Change Log

- 2026-07-31: Implementado bootstrap inicial do monorepo Python e movida a story para `review`.
- 2026-07-31: Aplicados patches do code review da Story 0.1 e movida a story para `done`.

### File List

- `.gitignore`
- `.python-version`
- `README.md`
- `_bmad-output/implementation-artifacts/0-1-bootstrap-do-monorepo-python.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/development.md`
- `infra/.gitkeep`
- `packages/.gitkeep`
- `pyproject.toml`
- `scripts/dev`
- `services/.gitkeep`
- `tests/test_repository_bootstrap.py`
- `uv.lock`
