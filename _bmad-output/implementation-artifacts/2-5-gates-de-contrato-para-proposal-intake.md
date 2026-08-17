---
jira_issue: CTOS-32
branch: agent/story-2-5-gates-contrato-proposal-intake
baseline_commit: 959ed09
---

# Story 2.5: Gates de Contrato para Proposal Intake

Status: review

## Story

As a equipe de engenharia,
I want gates automatizados de contrato, compatibilidade e segurança do `Proposal Intake`,
so that mudanças em schemas públicos, validação runtime, idempotência e isolamento de tenant não quebrem clientes nem aceitem payloads indevidos.

## Acceptance Criteria

1. **Gates cobrem OpenAPI, JSON Schema e AsyncAPI**
   - **Given** os contratos versionados atuais do `Proposal Intake`
   - **When** a suíte de contratos for executada
   - **Then** valida OpenAPI pública, headers obrigatórios, respostas padronizadas, schema Draft 2020-12, exemplos válidos e inválidos para CPF/CNPJ e produtos MVP
   - **And** valida o evento `creditos.proposal.v1.submitted` em AsyncAPI 3.1.0, envelope CloudEvents `specversion: "1.0"` e payload `data` minimizado.

2. **Mudanças incompatíveis são bloqueadas ou exigem governança explícita**
   - **Given** alteração que remove campos obrigatórios, relaxa fechamento de objetos, altera enums MVP, muda `$ref` do request body, remove respostas/headers públicos ou remove extensões CloudEvents obrigatórias
   - **When** os gates de contrato forem executados
   - **Then** a suíte falha com erro claro
   - **And** contratos marcados como `breaking` só passam com versão sucessora maior, plano de migração concreto, janela de compatibilidade concreta e `contract_tests_required = true`.

3. **Contratos públicos continuam alinhados ao runtime**
   - **Given** exemplos válidos e inválidos do schema de proposta
   - **When** o serviço de validação/submissão processar payloads equivalentes com headers e contexto confiável
   - **Then** exemplos válidos são aceitos e normalizados
   - **And** exemplos inválidos, campos proibidos ou payload arbitrário são rejeitados com erro seguro, sem persistência indevida.

4. **Segurança e multi-tenancy têm testes negativos explícitos**
   - **Given** ausência de contexto autenticado, tenant não confiável, tentativa de `tenant_id` no body, contexto de evento inválido, mesma chave/id externo em tenants distintos ou reenvio cross-tenant
   - **When** os testes de segurança do `Proposal Intake` forem executados
   - **Then** a proposta é rejeitada ou isolada no tenant correto
   - **And** nenhum status, outbox, idempotência ou proposta canônica é criado fora do tenant confiável.

5. **Logs, erros e eventos permanecem minimizados**
   - **Given** submissões aceitas, rejeitadas, conflitadas e replays idempotentes
   - **When** os testes inspecionarem logs estruturados, erros e CloudEvents
   - **Then** encontram rastreabilidade por operação, tenant confiável, correlação, contrato, versão e identificadores técnicos permitidos
   - **And** não encontram CPF, CNPJ, nome, e-mail completo, endereço, payload bruto, tokens, secrets ou valores financeiros detalhados.

6. **CI e comandos locais executam os gates obrigatórios**
   - **Given** mudança em contratos ou código do `Proposal Intake`
   - **When** `./scripts/dev contracts`, `uv run python scripts/check_contracts.py` e o CI forem executados
   - **Then** os gates de contrato, testes focados e qualidade bloqueiam regressões relevantes
   - **And** a documentação local descreve expectativas de consumidor e qualquer limitação remanescente sem prometer diff semântico que não exista.

## Tasks / Subtasks

- [x] CTOS-32 — Detalhar e implementar gates de contrato para `Proposal Intake` (AC: 1, 2, 3, 4, 5, 6)
  - [x] Mapear lacunas atuais entre contratos, checker e runtime antes de alterar código. (AC: 1, 2, 3, 4)
  - [x] Adicionar testes de mutação/fixture para regressões de OpenAPI, JSON Schema e AsyncAPI. (AC: 1, 2)
  - [x] Adicionar testes de alinhamento runtime usando exemplos válidos/inválidos do schema quando praticável. (AC: 3)
  - [x] Ampliar testes negativos de segurança, isolamento de tenant, reenvio cross-tenant e ausência de persistência indevida. (AC: 4)
  - [x] Ampliar testes de minimização em logs, erros e eventos, preservando mascaramento. (AC: 5)
  - [x] Endurecer `scripts/check_contracts.py` somente onde os testes revelarem lacunas verificáveis. (AC: 1, 2, 6)
  - [x] Materializar expectativas de consumidor em `packages/contracts/consumer-expectations` quando a lacuna for confirmada. (AC: 2, 6)
  - [x] Atualizar documentação de contratos/desenvolvimento apenas se comandos, escopo ou limitações mudarem. (AC: 6)
  - [x] Atualizar subtarefas Jira, sprint status e registro da story conforme o avanço. (AC: 6)

### Review Findings

- [x] [Review][Patch] Header público `X-Request-Id` declarado mas não obrigatório — corrigido ao exigir `required=true` no OpenAPI e no checker.
- [x] [Review][Patch] Request body OpenAPI aceitava media types adicionais — corrigido para aceitar somente `application/json`.
- [x] [Review][Patch] Gates AsyncAPI permitiam extensões CloudEvents e campos `data` extras — corrigido com conjuntos estritos e exceção explícita apenas para `roles`.
- [x] [Review][Patch] Gates AsyncAPI não validavam `specversion`, `type: object` e fechamento do envelope — corrigido com novas regras e testes de mutação.
- [x] [Review][Patch] Testes runtime de exemplos não validavam normalização/minimização suficiente — reforçados com asserts de canônico, outbox, erro seguro e logs sem dados sensíveis.
- [x] [Review][Patch] Expectativas de consumidor omitiam o evento AsyncAPI/CloudEvents — documentação versionada atualizada.

## Dev Notes

### Escopo desta story

- Esta story cria e endurece gates de contrato, compatibilidade e segurança para o `Proposal Intake`; ela não cria novo endpoint público, banco real, migration, NATS real, gRPC real, serviço de decisão, integração externa ou nova versão de contrato.
- O foco é impedir regressões silenciosas nos contratos públicos e no comportamento já implementado nas Stories 2.1 a 2.4.
- Não adicionar ferramentas como Spectral, OpenAPI Generator, AsyncAPI CLI, Buf, `jsonschema` ou parser externo sem justificar alternativas, consequências e necessidade real. O padrão atual dos gates usa Python stdlib.
- Não declarar suporte a diff semântico completo entre versões se ele não for implementado. A decisão atual da Story 0.3 é `metadata-only`: validar estrutura, metadados e controles declarados de breaking change; diff semântico completo exige tooling/ADR futuro.

### Estado atual que deve ser preservado

- `packages/contracts/schemas/proposal/v1/proposal.schema.json` é o contrato canônico público v1 de proposta, em JSON Schema Draft 2020-12, com CPF/CNPJ, produtos MVP, exemplos válidos e `x-creditos.invalidExamples`.
- `packages/contracts/openapi/public/proposal-intake/v1/openapi.json` expõe `POST /v1/proposals`, referencia o schema canônico e exige `Idempotency-Key`.
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` define o evento `creditos.proposal.v1.submitted` em AsyncAPI 3.1.0, com CloudEvents e payload minimizado.
- `packages/contracts/catalog/contracts.toml` é o catálogo oficial; contratos `breaking` exigem governança explícita antes de passar nos gates.
- `scripts/check_contracts.py` já valida catálogo, OpenAPI, protobuf, AsyncAPI, schema de proposta, exemplos, campos proibidos, produtos MVP e parte das regras de breaking change.
- `tests/test_contracts_structure.py` já possui padrão de fixture temporária, mutação específica e assert de erro para garantir que o checker falhe por causa rastreável.
- `packages/contracts/consumer-expectations/README.md` existe como espaço de expectativas de consumidores; usar subpastas/arquivos reais se a story precisar materializar expectativas além do checker estrutural.
- O runtime do `Proposal Intake` já valida, normaliza, persiste canônico, aplica idempotência, cria status inicial e prepara outbox in-memory; esta story deve testar e endurecer esse comportamento sem duplicar regras de domínio.

### Regras técnicas obrigatórias

- Manter DDD + arquitetura hexagonal: domínio sem imports de FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry ou SDK externo.
- Tenant confiável vem de `ObservabilityContext`/contexto autenticado, nunca do body público; qualquer `tenant_id` no payload deve continuar proibido.
- Idempotência continua escopada por tenant, cliente técnico e `Idempotency-Key`; replay equivalente não cria nova proposta, status ou outbox.
- Eventos continuam usando CloudEvents estável com `specversion: "1.0"`; não usar campos WIP de versões futuras.
- Extensões CloudEvents devem permanecer sem underscore e dentro do padrão atual: `tenantid`, `tenanttier`, `subjectid`, `clientid`, `principaltype`, `scopes`, `correlationid`, `requestid`, `idempotencykey`, `schemaversion` e `traceparent`.
- OpenAPI permanece na baseline arquitetural atual `3.1.0`; não atualizar para OpenAPI 3.2.x nesta story sem ADR/decisão explícita.
- AsyncAPI permanece em `3.1.0`, que já está alinhado à baseline arquitetural atual.
- JSON Schema permanece em Draft 2020-12.

### Arquivos existentes que provavelmente serão atualizados

- `scripts/check_contracts.py`: adicionar validações somente quando houver teste cobrindo a lacuna.
- `tests/test_contracts_structure.py`: adicionar testes de mutação/fixture para OpenAPI, JSON Schema, AsyncAPI e breaking controls.
- `services/proposal-intake/tests/unit/test_validate_and_normalize_proposal.py`: adicionar/ajustar testes de alinhamento com exemplos do schema e rejeições públicas.
- `services/proposal-intake/tests/unit/test_idempotent_submission.py`: adicionar/ajustar testes de idempotência, tenant spoofing e minimização quando necessário.
- `services/proposal-intake/tests/unit/test_initial_status_and_outbox.py`: adicionar/ajustar testes de contrato CloudEvents, outbox, replay e ausência de vazamento sensível.
- `docs/contracts.md`: atualizar somente se a limitação `metadata-only` ou comandos de contrato forem alterados.
- `docs/development.md` e `.github/workflows/ci.yml`: atualizar somente se os comandos/gates obrigatórios mudarem.
- `_bmad-output/implementation-artifacts/sprint-status.yaml`: manter status de avanço da story.

### Anti-padrões proibidos

- Não criar contrato paralelo ao schema canônico de proposta.
- Não aceitar payload livre, `extra_data`, `raw_payload`, `payload`, `selected_plan`, `plan_id`, `tenant_id`, `custom`, `metadata` ou `attributes` no body público.
- Não mascarar erro removendo o teste; o gate deve falhar com mensagem rastreável.
- Não persistir payload original para auditoria, log, evento ou fixture de teste.
- Não transformar o checker em validador de negócio completo; regras de domínio continuam no `Proposal Intake`.
- Não introduzir dependência externa apenas para simplificar uma validação pequena já possível com stdlib.
- Não quebrar comandos existentes: `./scripts/dev contracts`, `uv run python scripts/check_contracts.py`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` e `uv run pyright`.

### Inteligência das stories anteriores

- Story 2.1 estabeleceu o contrato canônico v1, proibiu payload arbitrário e removeu a dependência de planos da financeira.
- Story 2.2 implementou validação/normalização e padronização de erros seguros; não duplicar essa lógica no checker.
- Story 2.3 endureceu idempotência com fingerprint canônico, HMAC de identificadores sensíveis, rollback e concorrência; não enfraquecer o escopo tenant + cliente técnico + chave.
- Story 2.4 criou status inicial e outbox CloudEvents, e o review corrigiu riscos de replay sem status/outbox, rollback parcial, validação incompleta de contexto CloudEvents e logs emitidos antes da confirmação local.
- A Story 2.5 deve transformar essas correções em gates de regressão, especialmente em contrato AsyncAPI, minimização de evento, replays e cross-tenant.
- Se o OpenAPI ainda não declarar autenticação/security scheme, não inventar desenho de autenticação nesta story; registrar a lacuna ou implementar apenas se houver padrão já aprovado no Epic 1.

### Latest Technical Information

- OpenAPI: a especificação mais recente publicada inclui OpenAPI 3.2.0, mas a arquitetura do CreditOS está pinada em OpenAPI 3.1.0 para o MVP; esta story não deve fazer upgrade de versão por oportunismo.
- JSON Schema Draft 2020-12 continua adequado para o schema atual e suporta as restrições usadas no contrato canônico.
- AsyncAPI 3.1.0 é a baseline atual e compatível com o contrato assíncrono já registrado.
- CloudEvents possui release estável v1.0.2 para core e NATS binding; manter `specversion: "1.0"` e evitar campos WIP.

### Testing Requirements

- Primeiro escrever teste que falha para cada lacuna real antes de ajustar checker/runtime.
- Contratos estruturais: `.venv/bin/python -m pytest tests/test_contracts_structure.py -q`.
- Checker direto: `.venv/bin/python scripts/check_contracts.py`.
- Testes focados do serviço: `.venv/bin/python -m pytest services/proposal-intake/tests -q`.
- Teste recomendado se houver lacuna: `services/proposal-intake/tests/unit/test_contract_examples.py`, cobrindo exemplos válidos e inválidos do schema contra o runtime.
- Qualidade: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright`.
- Suíte antes de PR: `.venv/bin/python -m pytest -q`; se `tests/test_local_harness.py` falhar por sandbox/`uv`, repetir fora do sandbox com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q`.

### Checklist de criação da story

- [x] Epic 2 e Story 2.5 analisados.
- [x] PRD e Architecture Spine consultados para contratos, tenant, segurança, CI e eventos.
- [x] Story 2.4 e aprendizados de review incorporados.
- [x] Arquivos existentes prováveis identificados para evitar duplicação.
- [x] Limitação `metadata-only` registrada para evitar promessa falsa de diff semântico.
- [x] Escopo delimitado para não implementar código funcional novo nesta etapa.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 2, Stories 2.1 a 2.5.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-4, AD-5, AD-6 e AD-23.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-4, FR-5, FR-6, NFR-14, NFR-30, NFR-32, NFR-33, NFR-34 e SM-4.
- `docs/contracts.md` — catálogo de contratos, breaking changes, validação local e limitação `metadata-only`.
- `docs/development.md` — comandos locais e gates de desenvolvimento.
- `scripts/check_contracts.py` — checker atual de contratos.
- `tests/test_contracts_structure.py` — padrão atual de testes de contrato por fixture/mutação.
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py` — runtime atual de validação, idempotência, status e outbox.
- `_bmad-output/implementation-artifacts/2-4-status-inicial-e-evento-de-proposta-submetida.md` — inteligência e review findings da Story 2.4.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- `.venv/bin/python -m pytest tests/test_contracts_structure.py services/proposal-intake/tests/unit/test_contract_examples.py -q` — primeiro ciclo vermelho com 5 falhas esperadas nos novos gates.
- `.venv/bin/python -m pytest tests/test_contracts_structure.py services/proposal-intake/tests/unit/test_contract_examples.py -q` — 28 passed após endurecimento do checker/schema.
- `.venv/bin/python -m pytest services/proposal-intake/tests -q` — primeiro ciclo revelou `missing_trusted_tenant` sem `code` específico.
- `.venv/bin/python -m pytest services/proposal-intake/tests -q` — 73 passed após correção do erro rastreável.
- `.venv/bin/python scripts/check_contracts.py` — `contracts check passed: 4 contracts`.
- `.venv/bin/python -m pytest tests/test_contracts_structure.py -q` — 26 passed.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — passed após formatar arquivos alterados.
- `.venv/bin/pyright` — 0 errors.
- `.venv/bin/python -m pytest -q` — falhou no sandbox por `tests/test_local_harness.py` exigir socket local e `uv` no PATH.
- `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q` fora do sandbox — 280 passed.
- `.venv/bin/python -m pytest tests/test_contracts_structure.py services/proposal-intake/tests/unit/test_contract_examples.py -q` — 34 passed após correções do code review.
- `.venv/bin/python -m pytest services/proposal-intake/tests -q` — 73 passed após correções do code review.
- `.venv/bin/python scripts/check_contracts.py`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright` — passaram após correções do code review.
- `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q` fora do sandbox — 286 passed após correções do code review.

### Implementation Plan

- Usar testes de mutação/fixture para transformar lacunas de contrato em falhas rastreáveis do checker.
- Reaproveitar o runtime existente do `Proposal Intake` para validar exemplos do schema, sem duplicar regras de domínio no pacote de contratos.
- Manter a estratégia `metadata-only` para breaking changes e adicionar apenas invariantes estruturais verificáveis sem ferramenta externa.
- Materializar expectativas de consumidor como documentação versionada em `packages/contracts/consumer-expectations`.

### Completion Notes List

- Adicionados gates para drift do `$ref` do request body do OpenAPI e obrigatoriedade real de `X-Correlation-Id`/`Idempotency-Key`.
- Adicionados gates para fechamento do payload/data do evento `ProposalSubmitted` no AsyncAPI.
- Alinhados `custom`, `metadata` e `attributes` como campos proibidos no schema e no checker, acompanhando o runtime.
- Criados testes que executam todos os exemplos válidos e inválidos do schema contra o fluxo real `submit_with_initial_status_and_outbox`.
- Reforçados testes de isolamento para mesmo `external_proposal_id` em tenants distintos e tenant confiável ausente sem persistência.
- Corrigido `missing_trusted_tenant` para emitir `code` específico e rastreável.
- Criada expectativa de consumidor versionada para o contrato público `Proposal Intake` v1.
- Corrigidos achados do code review: OpenAPI mais estrito, AsyncAPI/CloudEvents com envelope e dados minimizados, testes de exemplo com normalização e minimização verificadas.

### File List

- `_bmad-output/implementation-artifacts/2-5-gates-de-contrato-para-proposal-intake.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `packages/contracts/consumer-expectations/proposal-intake-public/v1/README.md`
- `packages/contracts/openapi/public/proposal-intake/v1/openapi.json`
- `packages/contracts/schemas/proposal/v1/proposal.schema.json`
- `scripts/check_contracts.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`
- `services/proposal-intake/tests/unit/test_contract_examples.py`
- `services/proposal-intake/tests/unit/test_initial_status_and_outbox.py`
- `tests/test_contracts_structure.py`

## Change Log

- 2026-08-17 — Implementados gates de contrato, exemplos runtime, expectativas de consumidor, reforços de tenant e validações finais da Story 2.5.
