---
baseline_commit: 88cfee142d3c8f27edda33907161ca459ca6d03e
---

# Story 0.3: Estrutura Base de Contratos Versionados

Status: done

## Story

Como equipe de plataforma,
quero organizar contratos OpenAPI, protobuf, AsyncAPI e schemas versionados,
para que mudanças de API, gRPC, eventos e webhooks sejam testáveis antes das features de produto.

## Acceptance Criteria

1. **Given** a estrutura de contratos do repositório, **when** contratos públicos, internos ou assíncronos são adicionados, **then** há local padronizado para OpenAPI, protobuf, AsyncAPI e schemas, **and** cada contrato declara versão, owner, compatibilidade esperada e política de breaking change.
2. **Given** uma mudança de contrato, **when** os checks locais ou de CI são executados, **then** breaking changes sem nova versão ou plano de migração falham, **and** consumidores podem adicionar expectativas/testes de compatibilidade.

## Tasks / Subtasks

- [x] Criar pacote compartilhado de contratos (AC: 1)
  - [x] Criar `packages/contracts/pyproject.toml` como membro válido do workspace `uv`.
  - [x] Criar pacote Python mínimo `packages/contracts/src/creditos_contracts/` sem domínio compartilhado.
  - [x] Manter o pacote dentro da categoria permitida por Story 0.2: contratos.
- [x] Definir estrutura versionada de contratos (AC: 1)
  - [x] Criar diretórios padronizados para `openapi`, `protobuf`, `asyncapi`, `schemas`, `catalog` e expectativas de consumidores.
  - [x] Criar catálogo/manifest parseável por biblioteca padrão Python, declarando `id`, `kind`, `version`, `owner`, `path`, `compatibility`, `breaking_change_policy` e controles de migração.
  - [x] Garantir que paths de contratos usem versão explícita, preferencialmente `v1`.
- [x] Adicionar contratos mínimos de exemplo (AC: 1)
  - [x] Adicionar OpenAPI público mínimo apenas estrutural.
  - [x] Adicionar protobuf interno mínimo apenas estrutural.
  - [x] Adicionar AsyncAPI mínimo para evento/comando assíncrono apenas estrutural.
  - [x] Adicionar JSON Schema mínimo apenas estrutural.
  - [x] Não definir contrato final de produto nem schema completo de proposta nesta story.
- [x] Criar checks locais de governança (AC: 1, 2)
  - [x] Adicionar teste que valide estrutura, catálogo e arquivos referenciados.
  - [x] Adicionar check local que falhe quando contrato marcado como breaking não declarar nova versão e plano de migração.
  - [x] Integrar o check ao fluxo `./scripts/dev all` sem adicionar lockfile paralelo ou dependência fora do `uv`.
  - [x] Garantir ponto claro para consumidores adicionarem expectativas/testes de compatibilidade.
- [x] Atualizar documentação e rastreamento (AC: 1, 2)
  - [x] Documentar política de contratos versionados em `docs/`.
  - [x] Atualizar `sprint-status.yaml` para `in-progress` e, ao final, `review`.
  - [x] Registrar Jira `CTOS-18` e subtarefas `CTOS-79` a `CTOS-83`.

### Review Findings

- [x] [Review][Defer] Definir estratégia de detecção de breaking changes reais — deferred: opção metadata-only aprovada para a Story 0.3; diff semântico de OpenAPI, protobuf, AsyncAPI e JSON Schema exige ADR/tooling futuro.
- [x] [Review][Patch] `scripts` não são analisados pelo Pyright, embora `scripts/check_contracts.py` seja novo código Python [pyproject.toml:38]
- [x] [Review][Patch] Catálogo não rejeita `id`, `path` ou pares de contrato duplicados [scripts/check_contracts.py:89]
- [x] [Review][Patch] Catálogo não valida mapeamento entre `kind`, diretório e extensão do artefato [scripts/check_contracts.py:99]
- [x] [Review][Patch] Validador pode quebrar com TOML/JSON estruturalmente malformado em vez de falhar limpo [scripts/check_contracts.py:33]
- [x] [Review][Patch] Validação de OpenAPI, AsyncAPI e protobuf é superficial demais para os exemplos estruturais [scripts/check_contracts.py:51]
- [x] [Review][Patch] Controles de breaking change aceitam políticas, versões e planos fracos [scripts/check_contracts.py:126]
- [x] [Review][Patch] Testes de governança duplicam lógica e não exercitam casos negativos do checker [tests/test_contracts_structure.py:71]
- [x] [Review][Patch] OpenAPI mínimo não materializa guardrails AD-14 de correlation/request/idempotency/error [packages/contracts/openapi/public/proposal-intake/v1/openapi.json:13]
- [x] [Review][Patch] AsyncAPI mínimo não materializa extensões CloudEvents/NATS esperadas pelo AD-4 [packages/contracts/asyncapi/events/proposal/v1/asyncapi.json:41]

## Dev Notes

### Escopo da Story

- Esta story cria a fundação de contratos versionados; não cria contratos definitivos de produto.
- Exemplos devem ser mínimos e voltados a validar estrutura, metadados e checks.
- Não escolher ferramenta externa de contract testing nesta story sem ADR ou aprovação; usar Python stdlib e pytest existentes.
- Não criar microsserviços reais e não mover DTOs de borda para `domain`.

### Requisitos Técnicos Obrigatórios

- Runtime: Python 3.13.
- Gerenciador: `uv` workspace com `uv.lock` único.
- Pacote compartilhado permitido: `packages/contracts`.
- Pacote Python: `creditos_contracts`.
- Contratos públicos HTTP/JSON: OpenAPI versionado.
- Contratos internos síncronos: protobuf versionado para gRPC.
- Contratos assíncronos: AsyncAPI versionado para NATS JetStream/CloudEvents.
- Schemas de payload: JSON Schema versionado quando aplicável.
- Catálogo de contratos deve ser parseável com `tomllib` para evitar dependência adicional nesta fundação.

### Arquitetura e Guardrails

- AD-4 define que propostas públicas usam schemas versionados e aprovados; gRPC cobre chamadas internas imediatas; NATS JetStream cobre fluxos assíncronos; eventos usam CloudEvents; contratos assíncronos usam AsyncAPI; outbox/inbox e idempotência são o padrão de confiabilidade.
- AD-4 também define extensões CloudEvents válidas como `tenantid`, `correlationid`, `idempotencykey`, `schemaversion` e `traceparent`.
- AD-14 exige OpenAPI versionado para API pública, callbacks/webhooks versionados, erro público padronizado, correlation ID, request ID e idempotency key quando aplicável; breaking changes exigem nova versão, período de compatibilidade, guia de migração e testes de contrato.
- AD-16 permite `packages/` apenas para contratos, observabilidade, segurança, testes e utilidades técnicas genéricas; entidades, regras, policies e repositories de domínio não podem ser compartilhados entre bounded contexts.
- Story 0.2 já adicionou guardrail em `tests/test_microservice_template.py` que permite `packages/contracts` e bloqueia estruturas de domínio compartilhado.

### Estrutura Esperada

```text
packages/contracts/
  pyproject.toml
  README.md
  catalog/contracts.toml
  openapi/public/<contract>/v1/openapi.json
  protobuf/internal/<contract>/v1/*.proto
  asyncapi/events/<contract>/v1/asyncapi.json
  schemas/<contract>/v1/*.schema.json
  consumer-expectations/README.md
  src/creditos_contracts/
    __init__.py
scripts/check_contracts.py
tests/test_contracts_structure.py
```

### Testing Requirements

- Validar que `packages/contracts` é membro válido do workspace e pacote instalável.
- Validar que todo contrato no catálogo possui metadados obrigatórios.
- Validar que todo `path` do catálogo existe, fica dentro de `packages/contracts` e contém segmento de versão `vN`.
- Validar que OpenAPI/AsyncAPI/JSON Schema de exemplo são JSON parseável.
- Validar que protobuf de exemplo declara `syntax = "proto3";`.
- Validar que contrato marcado como breaking exige `replacement_version`, `migration_plan`, `compatibility_window` e `contract_tests_required`.
- Executar `./scripts/dev all` ao final.

### Previous Story Intelligence

- Story 0.1 criou `uv`, Python 3.13, Ruff, Pyright, pytest, `scripts/dev` e guardrails de monorepo.
- Story 0.1 reforçou que `./scripts/dev all` deve executar `uv lock --check`, `uv sync --locked`, lint, format check, typecheck e pytest.
- Story 0.2 criou `services/service-template` e ampliou pytest para coletar `tests` e `services`.
- Story 0.2 adicionou guardrail de `packages/` com categorias permitidas; `contracts` é permitido, mas qualquer sinal de domínio compartilhado continua proibido.
- Story 0.2 tornou pacotes do workspace instaláveis via `setuptools.build_meta`; manter o mesmo padrão no novo pacote.

### Pesquisa Técnica Atual

- OpenAPI publica versões 3.2.0, 3.1.2/3.1.1/3.1.0, 3.0.x e 2.0; a especificação textual prevalece sobre schemas quando houver conflito. Fonte: https://spec.openapis.org/oas/
- AsyncAPI mantém 3.1.0 como versão latest estável, alinhada ao baseline arquitetural do CreditOS. Fonte: https://github.com/asyncapi/spec
- Protocol Buffers recomenda arquivos `.proto` em diretório language-agnostic e `syntax = "proto3";` para proto3. Fonte: https://protobuf.dev/programming-guides/proto3/
- JSON Schema informa 2020-12 como versão atual; usar `$schema` explícito nos exemplos de schema JSON. Fonte: https://json-schema.org/specification

### Anti-Patterns a Evitar

- Adicionar `openapi-generator`, Buf, Spectral, AsyncAPI CLI ou ferramenta externa sem ADR/aprovação.
- Criar contrato final de proposta nesta story; isso pertence ao Epic 2.
- Criar domínio compartilhado em `packages/contracts`.
- Colocar CPF, CNPJ, e-mail real ou payload sensível completo em exemplos.
- Criar CI completo; Story 0.6 fará CI inicial, mas esta story deve deixar checks locais reaproveitáveis.

## References

- `_bmad-output/planning-artifacts/epics.md` — Epic 0 e Story 0.3.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-4, AD-14 e AD-16.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-4, FR-25, FR-26, NFR-32, NFR-33 e NFR-34.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/contrato-inicial-proposta-oq3.md` — futuro contrato canônico de proposta, fora do escopo de implementação desta story.
- `_bmad-output/implementation-artifacts/0-1-bootstrap-do-monorepo-python.md` — padrões de tooling e validação.
- `_bmad-output/implementation-artifacts/0-2-template-base-de-microsservico-ddd-e-hexagonal.md` — padrões de workspace e guardrails de `packages/`.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — ordem de implementação.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-07-31: Branch `agent/story-0-3-versioned-contracts` criada antes do desenvolvimento.
- 2026-07-31: Jira `CTOS-18` movido para `Em andamento`; subtarefas `CTOS-79` a `CTOS-83` criadas.
- 2026-07-31: Início da implementação; baseline commit registrado.
- 2026-07-31: Teste red inicial executado com `uv run pytest tests/test_contracts_structure.py` e falhou por ausência de `packages/contracts`, como esperado.
- 2026-07-31: Criado `packages/contracts` com catálogo TOML, exemplos OpenAPI/protobuf/AsyncAPI/JSON Schema e ponto de expectativas de consumidores.
- 2026-07-31: Criado `scripts/check_contracts.py` e integrado ao `./scripts/dev all`.
- 2026-07-31: Validação final executada com `./scripts/dev all`; lint, format check, typecheck, contracts check e pytest passaram.
- 2026-08-03: Code review adversarial executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor.
- 2026-08-03: Decisão metadata-only aprovada para detecção inicial de breaking changes; tarefa futura `CTOS-84` criada para ADR/tooling de diff semântico.
- 2026-08-03: Nove findings de patch da revisão corrigidos; `./scripts/dev all` passou com 18 testes.

### Completion Notes List

- Story criada pelo workflow `bmad-create-story`.
- Ultimate context engine analysis completed - comprehensive developer guide created.
- Criado pacote compartilhado `creditos-contracts` como membro instalável do workspace `uv`.
- Criada estrutura versionada para OpenAPI, protobuf, AsyncAPI, JSON Schema, catálogo e expectativas de consumidores.
- Adicionados quatro contratos mínimos estruturais, sem definir contrato final de produto.
- Adicionado check local de governança que valida metadados, paths versionados, arquivos referenciados e controles obrigatórios para breaking changes.
- Documentada a política de contratos versionados em `docs/contracts.md` e incluído o check no fluxo de desenvolvimento.
- Confirmado que `./scripts/dev all` passa com 14 testes.
- Corrigidos todos os patches do code review da Story 0.3.
- Pyright passou a analisar `scripts`, incluindo `scripts/check_contracts.py`.
- Checker de contratos passou a validar duplicidade, path por tipo, robustez de TOML/JSON, guardrails mínimos de OpenAPI/AsyncAPI/protobuf e controles mais fortes para breaking changes declarados.
- Testes de governança foram expandidos com fixtures negativas para validar o comportamento real do checker.
- Confirmado que `./scripts/dev all` passa com 18 testes após o code review.

### Change Log

- 2026-07-31: Story 0.3 criada e iniciada em branch dedicada.
- 2026-07-31: Implementada estrutura base de contratos versionados e movida a story para `review`.
- 2026-08-03: Aplicados patches do code review da Story 0.3 e movida a story para `done`.

### File List

- `_bmad-output/implementation-artifacts/0-3-estrutura-base-de-contratos-versionados.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/contracts.md`
- `docs/development.md`
- `packages/contracts/README.md`
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json`
- `packages/contracts/catalog/contracts.toml`
- `packages/contracts/consumer-expectations/README.md`
- `packages/contracts/openapi/public/proposal-intake/v1/openapi.json`
- `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto`
- `packages/contracts/pyproject.toml`
- `packages/contracts/schemas/proposal/v1/proposal.schema.json`
- `packages/contracts/src/creditos_contracts/__init__.py`
- `pyproject.toml`
- `scripts/check_contracts.py`
- `scripts/dev`
- `tests/test_contracts_structure.py`
- `tests/test_repository_bootstrap.py`
- `uv.lock`
