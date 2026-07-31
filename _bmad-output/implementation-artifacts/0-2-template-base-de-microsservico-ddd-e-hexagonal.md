---
baseline_commit: f1774ff01b3a1058416327f58335684c6962b67d
---

# Story 0.2: Template Base de Microsserviço DDD e Hexagonal

Status: done

## Story

Como desenvolvedor,
quero um template base de microsserviço alinhado a DDD e arquitetura hexagonal,
para que cada bounded context comece com fronteiras claras e sem acoplamento indevido.

## Acceptance Criteria

1. **Given** um microsserviço criado a partir do template, **when** a estrutura é inspecionada, **then** contém `domain`, `application`, `adapters` e `bootstrap`, **and** o domínio não depende de FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, provedores externos ou Kubernetes.
2. **Given** bibliotecas em `packages/`, **when** uma dependência compartilhada é adicionada, **then** ela se limita a contratos, observabilidade, segurança, testes ou utilidades técnicas genéricas, **and** não compartilha entidades, regras, policies ou repositories de domínio entre bounded contexts.

## Tasks / Subtasks

- [x] Criar template de microsserviço no workspace (AC: 1)
  - [x] Criar `services/service-template/pyproject.toml` como membro válido do workspace `uv`.
  - [x] Criar pacote Python em `services/service-template/src/creditos_service_template/`.
  - [x] Criar camadas `domain`, `application`, `adapters` e `bootstrap`.
  - [x] Criar subpastas canônicas conforme AD-16: `domain/entities`, `domain/value_objects`, `domain/services`, `domain/events`, `domain/policies`, `application/use_cases`, `application/ports`, `adapters/api`, `adapters/grpc`, `adapters/events`, `adapters/persistence` e `adapters/external`.
- [x] Preservar isolamento do domínio (AC: 1)
  - [x] Não adicionar dependências de FastAPI, Pydantic, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, Redis, Kubernetes ou provedores externos no domínio.
  - [x] Documentar dependências permitidas por camada.
  - [x] Adicionar teste que falhe se arquivos Python em `domain` importarem frameworks ou infraestrutura proibidos.
- [x] Proteger política de `packages/` compartilhados (AC: 2)
  - [x] Documentar que `packages/` só pode conter contratos, observabilidade, segurança, testes ou utilidades técnicas genéricas.
  - [x] Adicionar teste que falhe se um pacote compartilhado definir `domain`, `entities`, `value_objects`, `policies`, `repositories` ou regras de negócio compartilhadas.
  - [x] Não criar entidades, policies, repositories ou serviços de domínio compartilhados.
- [x] Integrar template ao tooling existente (AC: 1, 2)
  - [x] Atualizar `uv.lock` pelo próprio `uv`.
  - [x] Garantir que `./scripts/dev all` roda com o novo membro do workspace.
  - [x] Não introduzir lockfiles paralelos, ferramenta alternativa ou dependência fora do `uv`.
- [x] Atualizar documentação operacional do template (AC: 1, 2)
  - [x] Criar documentação em `docs/` explicando como copiar/adaptar o template para um novo bounded context.
  - [x] Reforçar que a Story 0.2 cria apenas template, não os sete microsserviços reais.
- [x] Atualizar rastreamento BMAD e Jira (AC: 1, 2)
  - [x] Ao iniciar desenvolvimento, atualizar `sprint-status.yaml` para `in-progress`.
  - [x] Ao concluir implementação, mover story para `review`.
  - [x] Manter `CTOS-17` atualizado no Jira durante a execução.

### Review Findings

- [x] [Review][Patch] Testes locais de serviços não são coletados pelo pytest padrão [pyproject.toml:50]
- [x] [Review][Patch] Template não é configurado como pacote instalável do workspace [services/service-template/pyproject.toml:1]
- [x] [Review][Patch] Guardrail de domínio cobre apenas `services/service-template` [tests/test_microservice_template.py:90]
- [x] [Review][Patch] Guardrail de domínio permite imports de camadas internas externas ao domínio [tests/test_microservice_template.py:53]
- [x] [Review][Patch] Guardrail de `packages/` bloqueia contratos/eventos permitidos e não usa categorias permitidas [tests/test_microservice_template.py:42]

## Dev Notes

### Escopo da Story

- Esta story cria um template versionável de microsserviço; não cria os sete microsserviços reais do MVP.
- O template deve ser pequeno, verificável e copiável, evitando domínio falso ou regras de negócio artificiais.
- A implementação deve estender o bootstrap criado na Story 0.1 sem alterar o padrão de `uv`, Ruff, Pyright, pytest e lock único.

### Requisitos Técnicos Obrigatórios

- Runtime: Python 3.13.
- Gerenciador: `uv` workspace com `uv.lock` único.
- Template de serviço: `services/service-template/`.
- Pacote Python: `creditos_service_template`.
- Camadas obrigatórias: `domain`, `application`, `adapters`, `bootstrap`.
- O domínio não pode importar ou depender diretamente de frameworks, transporte, banco, mensageria, observabilidade, provedores externos ou Kubernetes.
- `packages/` não pode conter domínio compartilhado entre bounded contexts.

### Arquitetura e Guardrails

- AD-1 define DDD + arquitetura hexagonal + microsserviços orientados a eventos; entradas chegam por adapters, casos de uso vivem em `application`, regras e invariantes vivem em `domain`.
- AD-2 define que os sete microsserviços reais virão depois e terão ownership próprio; esta story não deve materializar `identity-tenant`, `proposal-intake`, `decision`, `automated-review`, `integration`, `audit-evidence` ou `reporting-insights`.
- AD-16 define o layout canônico por serviço com `pyproject.toml`, `src/creditos_<service>/`, `domain`, `application`, `adapters`, `bootstrap` e testes `unit`, `integration`, `contract`.
- O domínio deve permanecer puro: sem FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, Redis, OpenTelemetry, provedores externos ou Kubernetes.
- Bibliotecas compartilhadas em `packages/` só podem conter contratos, observabilidade, segurança, testes e utilidades técnicas genéricas.

### Estrutura Esperada

```text
services/service-template/
  pyproject.toml
  README.md
  src/creditos_service_template/
    domain/
      entities/
      value_objects/
      services/
      events/
      policies/
    application/
      use_cases/
      ports/
    adapters/
      api/
      grpc/
      events/
      persistence/
      external/
    bootstrap/
  tests/
    unit/
    integration/
    contract/
```

### Testing Requirements

- Validar que `services/service-template` é membro válido do workspace e possui `pyproject.toml`.
- Validar que as camadas e subpastas canônicas existem.
- Validar por AST ou inspeção equivalente que `domain` não importa módulos proibidos.
- Validar que pacotes futuros em `packages/` não contenham estruturas de domínio compartilhado.
- Executar `./scripts/dev all` ao final.

### Previous Story Intelligence

- Story 0.1 criou o monorepo Python com `uv`, Python 3.13, `uv.lock`, Ruff, Pyright, pytest e `scripts/dev`.
- Code review da Story 0.1 expandiu Pyright para `services`, `packages` e `tests`; logo, qualquer Python criado nesta story será analisado pelo typecheck padrão.
- `./scripts/dev all` já executa `uv lock --check`, `uv sync --locked`, Ruff, Pyright e pytest.
- O teste de bootstrap atual exige que qualquer diretório não oculto em `services/` ou `packages/` possua `pyproject.toml`.

### Pesquisa Técnica Atual

- `uv` workspaces exigem que cada diretório incluído por `members` possua `pyproject.toml`; o workspace compartilha um único `uv.lock` e permite `uv run --package` para membros específicos. Fonte: https://docs.astral.sh/uv/concepts/projects/workspaces/
- `uv init` dentro de um workspace adiciona o novo projeto como membro, mas esta story deve criar o template de forma controlada para manter nomes e camadas arquiteturais. Fonte: https://docs.astral.sh/uv/reference/cli/
- Pyright usa `include` para definir diretórios analisados e `exclude` para remover caminhos específicos; a raiz já inclui `services`, `packages` e `tests`. Fonte: https://github.com/microsoft/pyright/blob/main/docs/configuration.md
- pytest recomenda `src` layout para novos projetos por reduzir armadilhas de importação; o template deve seguir `src/creditos_service_template`. Fonte: https://pytest.org/en/8.0.x/explanation/goodpractices.html

### Anti-Patterns a Evitar

- Criar microsserviços reais nesta story.
- Criar domínio compartilhado em `packages/`.
- Adicionar dependências de runtime sem necessidade.
- Colocar DTOs de borda ou models de infraestrutura dentro de `domain`.
- Fazer template que já dependa de FastAPI, SQLAlchemy, gRPC, NATS ou OpenTelemetry antes das stories que introduzem adapters concretos.
- Criar gerador de código complexo; esta story deve entregar template simples e verificável.

## References

- `_bmad-output/planning-artifacts/epics.md` — Epic 0 e Story 0.2.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-16 e Structural Seed.
- `_bmad-output/implementation-artifacts/0-1-bootstrap-do-monorepo-python.md` — aprendizados e guardrails da Story 0.1.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — ordem de implementação.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-07-31: Branch `agent/story-0-2-microservice-template` criada antes do desenvolvimento.
- 2026-07-31: Jira `CTOS-17` movido para `Em andamento`; subtarefas `CTOS-73` a `CTOS-78` criadas.
- 2026-07-31: Início da implementação; baseline commit registrado.
- 2026-07-31: Teste red inicial executado com `uv run pytest tests/test_microservice_template.py` e falhou por ausência do template, como esperado.
- 2026-07-31: `services/service-template` criado como membro do workspace; `uv.lock` atualizado pelo `uv`.
- 2026-07-31: Validação final executada com `./scripts/dev all`; lint, format check, typecheck e pytest passaram.
- 2026-07-31: Code review adversarial executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor.
- 2026-07-31: Cinco findings de patch da revisão corrigidos; `./scripts/dev all` passou com 8 testes.

### Completion Notes List

- Story criada pelo workflow `bmad-create-story`.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Criado template estrutural em `services/service-template` com camadas DDD/hexagonais e subpastas canônicas do AD-16.
- Preservado domínio puro sem dependências de runtime, frameworks, transporte, banco, mensageria, observabilidade ou Kubernetes.
- Adicionados guardrails de teste para imports proibidos no domínio e domínio compartilhado indevido em `packages/`.
- Documentado o uso do template em `docs/microservice-template.md`.
- Confirmado que `./scripts/dev all` passa com o novo membro do workspace.
- Corrigida a coleta padrão de testes para incluir testes locais em `services/`.
- Template configurado como pacote instalável com `setuptools.build_meta` e `src/` layout.
- Guardrails ampliados para todos os serviços com camada `domain`, bloqueando frameworks, infraestrutura, providers externos e imports de camadas internas.
- Política de `packages/` ajustada para categorias permitidas, preservando contratos/eventos sem liberar domínio compartilhado.

### Change Log

- 2026-07-31: Story 0.2 criada e iniciada em branch dedicada.
- 2026-07-31: Implementado template base de microsserviço DDD/hexagonal e movida a story para `review`.
- 2026-07-31: Corrigidos findings do code review e movida a story para `done`.

### File List

- `_bmad-output/implementation-artifacts/0-2-template-base-de-microsservico-ddd-e-hexagonal.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/microservice-template.md`
- `pyproject.toml`
- `services/service-template/README.md`
- `services/service-template/pyproject.toml`
- `services/service-template/src/creditos_service_template/__init__.py`
- `services/service-template/src/creditos_service_template/adapters/__init__.py`
- `services/service-template/src/creditos_service_template/adapters/api/__init__.py`
- `services/service-template/src/creditos_service_template/adapters/events/__init__.py`
- `services/service-template/src/creditos_service_template/adapters/external/__init__.py`
- `services/service-template/src/creditos_service_template/adapters/grpc/__init__.py`
- `services/service-template/src/creditos_service_template/adapters/persistence/__init__.py`
- `services/service-template/src/creditos_service_template/application/__init__.py`
- `services/service-template/src/creditos_service_template/application/ports/__init__.py`
- `services/service-template/src/creditos_service_template/application/use_cases/__init__.py`
- `services/service-template/src/creditos_service_template/bootstrap/__init__.py`
- `services/service-template/src/creditos_service_template/domain/__init__.py`
- `services/service-template/src/creditos_service_template/domain/entities/__init__.py`
- `services/service-template/src/creditos_service_template/domain/events/__init__.py`
- `services/service-template/src/creditos_service_template/domain/policies/__init__.py`
- `services/service-template/src/creditos_service_template/domain/services/__init__.py`
- `services/service-template/src/creditos_service_template/domain/value_objects/__init__.py`
- `services/service-template/tests/contract/.gitkeep`
- `services/service-template/tests/integration/.gitkeep`
- `services/service-template/tests/unit/.gitkeep`
- `tests/test_microservice_template.py`
- `uv.lock`
