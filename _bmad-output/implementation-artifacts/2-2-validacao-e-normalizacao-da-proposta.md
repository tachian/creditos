---
jira_issue: CTOS-29
branch: agent/story-2-2-validacao-normalizacao-proposta
baseline_commit: bb94b88f29dc82145fc667e38db4fb0956d2562d
---

# Story 2.2: Validação e Normalização da Proposta

Status: done

## Story

As a `Proposal Intake Service`,
I want validar e normalizar campos recebidos,
so that os demais serviços recebam uma proposta canônica e consistente.

## Acceptance Criteria

1. **Serviço `Proposal Intake` com fronteira DDD/hexagonal**
   - **Given** o primeiro recorte implementável do bounded context `Proposal Intake`
   - **When** a Story 2.2 for implementada
   - **Then** existe um pacote `services/proposal-intake` instalável no workspace Python
   - **And** a estrutura respeita camadas `domain`, `application`, `adapters` e `bootstrap`
   - **And** o domínio não importa FastAPI, Pydantic, SQLAlchemy, gRPC, NATS, observabilidade, segurança ou infraestrutura.

2. **Validação runtime do contrato canônico v1**
   - **Given** um payload público de proposta e headers de requisição
   - **When** o caso de uso de validação/normalização é executado
   - **Then** valida `schema_version`, campos obrigatórios, tipos, enums MVP, coerência `PF/CPF` e `PJ/CNPJ`, `product_type` compatível com `product_data`, campos proibidos, participantes críticos, callback governado e limites operacionais
   - **And** usa `Idempotency-Key` do header como fonte canônica de idempotência
   - **And** rejeita `idempotency_key`, `tenant_id`, `selected_plan`, `plan_id`, `extra_data`, `raw_payload`, `payload`, `custom`, `metadata` e `attributes` no body público.

3. **Normalização canônica segura**
   - **Given** uma proposta válida com formatos aceitos pelo contrato v1
   - **When** a normalização é concluída
   - **Then** retorna uma representação canônica imutável com valores monetários como inteiros em centavos, datas/datetimes normalizados em ISO 8601 UTC quando houver horário, identificadores sanitizados e bloco de produto único
   - **And** preserva apenas dados necessários para `Proposal Intake`
   - **And** não converte dinheiro por `float`.

4. **Regras mínimas além do JSON Schema**
   - **Given** uma proposta estruturalmente válida, mas semanticamente inconsistente
   - **When** a validação runtime roda
   - **Then** rejeita ao menos `down_payment > amount`, `first_due_date` inválida quando informada, participante crítico sem identificação completa, `receivables.payer_ref` sem participante correspondente e callback sem `callback_profile_ref`
   - **And** retorna erro padronizado, seguro e rastreável.

5. **Persistência canônica mínima via porta de aplicação**
   - **Given** uma proposta válida e normalizada
   - **When** o caso de uso conclui
   - **Then** persiste somente uma representação canônica mínima por uma porta `CanonicalProposalRepository`
   - **And** a implementação desta story usa adapter in-memory para testes
   - **And** não implementa banco real, migrations, idempotência transacional, status inicial, outbox, evento, decisão, IA, integrações externas ou endpoint HTTP público completo.

6. **Logs, erros e testes sem vazamento sensível**
   - **Given** submissões aceitas e rejeitadas
   - **When** logs, erros e testes são produzidos
   - **Then** não expõem CPF, CNPJ, e-mail completo, payload bruto, valores financeiros detalhados, tokens, secrets ou dados de autorização
   - **And** logs estruturados incluem tenant confiável, correlação, operação, contrato, versão, status e duração quando aplicável.

## Tasks / Subtasks

- [x] CTOS-29 — Detalhar e implementar validação/normalização runtime de proposta v1 (AC: 1, 2, 3, 4, 5, 6)
  - [x] Criar `services/proposal-intake` como microsserviço DDD/hexagonal instalável no workspace.
  - [x] Criar domínio puro para proposta canônica, dinheiro, datas, documentos, erros seguros e invariantes mínimas.
  - [x] Criar caso de uso `ValidateAndNormalizeProposal` com comando contendo payload, headers confiáveis mínimos e contexto propagado/observável.
  - [x] Criar porta `CanonicalProposalRepository` e adapter `InMemoryCanonicalProposalRepository`.
  - [x] Implementar validações runtime explícitas para contrato v1 e decisões da Story 2.1.
  - [x] Implementar normalização canônica sem `float`, sem payload arbitrário e sem autoridade de tenant no body.
  - [x] Integrar logs estruturados com payload omitido/mascarado, preservando rastreabilidade.
  - [x] Adicionar testes unitários e de aplicação para casos válidos, inválidos, segurança e persistência mínima.
  - [x] Atualizar `pyproject.toml` e documentação do serviço conforme necessário.
  - [x] Atualizar esta story, `sprint-status.yaml` e Jira conforme avanço.

### Review Findings

- [x] [Review][Patch] Aplicar decisão híbrida para blocos opcionais — Persistir `decision_options` e `risk_context` mínimos normalizados; validar e descartar explicitamente `provided_data` e `consents` nesta story, com documentação/testes de descarte seguro.
- [x] [Review][Patch] Completar validação runtime das subestruturas do contrato v1 [services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py:274]
- [x] [Review][Patch] Tornar a representação canônica profundamente imutável [services/proposal-intake/src/creditos_proposal_intake/domain/entities/canonical_proposal.py:34]
- [x] [Review][Patch] Endurecer sanitização e pattern de identificadores públicos [services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py:640]
- [x] [Review][Patch] Rejeitar datas fora de `YYYY-MM-DD` e datetimes sem timezone explícito [services/proposal-intake/src/creditos_proposal_intake/domain/value_objects/dates.py:8]
- [x] [Review][Patch] Padronizar erros seguros para headers inválidos, callbacks malformados e payloads aninhados profundos [services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py:160]
- [x] [Review][Patch] Evitar retorno de histórico acumulado de logs por instância de serviço [services/proposal-intake/src/creditos_proposal_intake/application/service.py:38]
- [x] [Review][Patch] Registrar ou implementar validação de dígito verificador CPF/CNPJ [services/proposal-intake/src/creditos_proposal_intake/domain/value_objects/documents.py:10]

## Dev Notes

### Escopo desta story

- Esta story cria o primeiro recorte de código do `Proposal Intake Service`, mas ainda **não** cria endpoint HTTP público completo, banco real, migration, idempotência transacional, publicação de evento, outbox/inbox, status inicial, chamada gRPC para `Identity & Tenant`, decisão, IA ou integrações externas.
- O objetivo é produzir um núcleo testável de validação e normalização runtime que será consumido pelas próximas stories do Epic 2.
- O contrato público canônico já existe em `packages/contracts/schemas/proposal/v1/proposal.schema.json`; não recriar esse contrato dentro do domínio.
- A validação de JSON Schema completa por dependência externa não está aprovada nesta story. Se o dev agent entender que precisa adicionar `jsonschema`, `pydantic`, `fastapi` ou qualquer dependência nova, deve parar e pedir decisão/ADR antes.
- Pydantic v2 é baseline arquitetural para validação/DTOs de borda, mas o workspace atual ainda não declara `pydantic` como dependência; portanto não adicionar nesta story sem aprovação explícita.

### Decisões herdadas da Story 2.1

- `Idempotency-Key` é obrigatório no header público e é a fonte canônica de idempotência; `idempotency_key` é proibido no body.
- `tenant_id` confiável vem de autenticação/contexto validado pelo Epic 1, nunca do body público.
- Callbacks externos não aceitam URL livre no payload; usar `callback.callback_profile_ref` quando houver callback por proposta.
- Produtos MVP: `personal_credit`, `bnpl`, `business_credit`, `receivables`.
- `product_data` deve conter exatamente um bloco compatível com `product_type`.
- Papéis críticos em `participants` exigem identificação completa: `guarantor`, `co_borrower`, `payer`, `shareholder`, `legal_representative` e `beneficial_owner`.
- BNPL não deve duplicar valor em `purchase_amount`; a fonte de valor solicitada é `operation.requested_terms.amount`.
- Relações cruzadas complexas, como `down_payment <= amount`, foram deliberadamente deixadas para validação runtime nesta story.

### Regras de domínio e normalização

- Valores monetários devem ser `int` em centavos; rejeitar `float`, valores negativos, zero quando `amount`/`face_value` exigirem positivo e valores acima do teto operacional `1_000_000_000_000`.
- Datas tipo `date` devem permanecer em formato ISO `YYYY-MM-DD`; datetimes com horário devem ser normalizados para UTC ISO 8601.
- CPF deve ter 11 dígitos quando `document_type = CPF`; CNPJ deve ter 14 dígitos quando `document_type = CNPJ`. Dígito verificador pode ser implementado nesta story se simples e sem dependência externa; se não for implementado, registrar explicitamente a limitação como próxima melhoria de validação sem expor documentos reais.
- `external_proposal_id`, `participant_ref`, `payer_ref`, `callback_profile_ref` e `Idempotency-Key` não podem parecer CPF, CNPJ, telefone, e-mail, token ou segredo.
- `borrower` continua mínimo; renda, faturamento, contato, endereço e relacionamento ficam em `provided_data`.
- `risk_context` é opcional; não exigir reputação de dispositivo, idade de e-mail, velocidade de tentativas ou outros sinais avançados para todos os clientes.
- Erros devem ter `code`, `safe_message`, `field_path`/localização segura quando útil e `details` sem valor sensível. Não imprimir payload.

### Estrutura esperada

```text
services/proposal-intake/
  README.md
  pyproject.toml
  src/creditos_proposal_intake/
    __init__.py
    domain/
      __init__.py
      entities/
      value_objects/
      errors.py
    application/
      __init__.py
      ports/
      use_cases/
      service.py
    adapters/
      __init__.py
      persistence/
    bootstrap/
      __init__.py
  tests/
    unit/
    integration/
```

### Arquivos existentes que provavelmente serão atualizados

- `pyproject.toml`: incluir `services/proposal-intake/src` em `tool.pyright.extraPaths` e `tool.pytest.ini_options.pythonpath`.
- `services/proposal-intake/pyproject.toml`: novo membro do workspace por padrão `services/*`, com dependências internas mínimas `creditos-observability` e `creditos-security` se o serviço de aplicação logar eventos.
- `services/proposal-intake/README.md`: documentar escopo, não escopo e comandos locais.
- Não alterar contratos públicos salvo se os testes revelarem inconsistência real; mudanças no schema/OpenAPI exigem cuidado de compatibilidade.

### Padrões de código a reutilizar

- Seguir layout e regra de dependência do `services/service-template`.
- Usar dataclasses `frozen=True, slots=True` para value objects e entidades de domínio, como o padrão do `Identity & Tenant`.
- Seguir padrão de erros seguros com `code` e `safe_message`, similar a `services/identity-tenant/src/creditos_identity_tenant/domain/errors.py`.
- Reusar `creditos_observability.logging.build_structured_log`; ele omite `payload` por padrão e mascara `extra`.
- Reusar `ObservabilityContext` para correlação e tenant observável.
- Usar `creditos_security.context.TrustedContext`/`PropagatedContext` quando precisar representar contexto confiável; não aceitar `tenant_id` no payload.
- Usar adapter in-memory apenas para provar persistência mínima e comportamento do caso de uso.

### Anti-padrões proibidos

- Criar domínio compartilhado em `packages/contracts` ou outro `packages/*`.
- Colocar Pydantic, FastAPI, SQLAlchemy, gRPC, NATS ou OpenTelemetry dentro de `domain`.
- Implementar endpoint HTTP público completo nesta story.
- Implementar idempotência transacional da Story 2.3 nesta story.
- Implementar status inicial/evento/outbox da Story 2.4 nesta story.
- Logar payload bruto, CPF, CNPJ, e-mail completo, valores financeiros detalhados, token, secret ou authorization.
- Usar `float` para valores monetários.
- Aceitar `tenant_id`, `idempotency_key`, `selected_plan`, `plan_id`, `extra_data`, `raw_payload`, `payload`, `custom`, `metadata` ou `attributes` no body.
- Persistir payload original completo “para auditoria”; auditoria oficial é responsabilidade de `Audit & Evidence` e entra em fluxo posterior.

### Testing Requirements

- Testes focados do serviço: `.venv/bin/python -m pytest services/proposal-intake/tests -q`.
- Contratos: `.venv/bin/python -m pytest tests/test_contracts_structure.py -q`.
- Checker de contratos: `.venv/bin/python scripts/check_contracts.py`.
- Qualidade: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright`.
- Suíte completa antes de PR: `.venv/bin/python -m pytest -q`; se falhar por sandbox em `tests/test_local_harness.py`, repetir fora do sandbox com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q`.
- Não adicionar testes a uma árvore sem padrão; neste repo já há testes unitários/integrados por serviço e testes globais em `tests/`.

### Casos mínimos de teste

- Proposta válida PF `personal_credit` normaliza e persiste representação canônica mínima.
- Proposta válida PJ `receivables` exige `payer_ref` compatível com participante `payer` identificado.
- Rejeitar `idempotency_key` no body e aceitar `Idempotency-Key` no comando/header.
- Rejeitar `tenant_id`, `selected_plan`, `plan_id`, `extra_data`, `raw_payload`, `payload`, `custom`, `metadata` e `attributes`.
- Rejeitar `PF` com CNPJ, `PJ` com CPF e participante crítico sem identificação completa.
- Rejeitar `product_type` incompatível com `product_data` e produto fora do MVP.
- Rejeitar `down_payment > amount`.
- Rejeitar dinheiro em `float` ou acima do teto operacional.
- Rejeitar callback com `url` livre e aceitar `callback_profile_ref`.
- Garantir que erros/logs não contêm documentos, e-mail completo, payload bruto, authorization, token ou valores financeiros detalhados.

### Pesquisa técnica atualizada

- JSON Schema permanece na versão 2020-12; a própria especificação separa `format` como anotação/assertion, então a validação runtime não deve assumir que `format` sempre valida semanticamente datas/e-mails/URIs sem lógica própria.
- Pydantic v2.13.4 é a versão documentada como atual nas docs oficiais consultadas em 2026-08-14 e segue sendo a linha v2; porém não está no workspace atual e não deve ser adicionado nesta story sem decisão.
- Python 3.13 é o baseline do repo e da arquitetura; usar `datetime.UTC`/timezone-aware datetimes para normalização de horário.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 2 e Story 2.2.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-5, FR-6 e guardrail contra payload arbitrário.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/contrato-inicial-proposta-oq3.md` — contrato conceitual e regras de normalização.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-4 e SLO de submissão.
- `_bmad-output/implementation-artifacts/2-1-definicao-do-contrato-canonico-de-proposta.md` — decisões finais do contrato canônico v1.
- `packages/contracts/schemas/proposal/v1/proposal.schema.json` — schema público v1 aprovado.
- `packages/contracts/openapi/public/proposal-intake/v1/openapi.json` — headers públicos e request body.
- `services/service-template/README.md` — estrutura DDD/hexagonal e regra de dependência.
- `services/identity-tenant/src/creditos_identity_tenant/application/service.py` — padrão de aplicação com logs estruturados.
- `packages/observability/src/creditos_observability/logging.py` — logs com payload omitido e mascaramento.
- `packages/security/src/creditos_security/context.py` — contexto confiável e rejeição de dados sensíveis em contexto.
- `packages/security/src/creditos_security/masking.py` — mascaramento de dados sensíveis.
- JSON Schema Specification: `https://json-schema.org/specification`.
- JSON Schema Draft 2020-12: `https://json-schema.org/draft/2020-12`.
- Pydantic Docs: `https://pydantic.dev/docs/validation/latest/get-started/`.

## Checklist Validation

- [x] Story identifica objetivo, ACs e tarefas verificáveis.
- [x] Story referencia Epic 2, PRD OQ-3, Architecture Spine e Story 2.1.
- [x] Story delimita que endpoint HTTP, idempotência transacional, evento/outbox e persistência real ficam fora do escopo.
- [x] Story evita dependência nova sem decisão explícita.
- [x] Story preserva segurança, privacidade, multi-tenancy, auditabilidade e explicabilidade como preocupações centrais.
- [x] Story orienta o dev agent a reutilizar padrões do template, `Identity & Tenant`, `observability` e `security`.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-14 — Branch `agent/story-2-2-validacao-normalizacao-proposta` criada no início da Story 2.2.
- 2026-08-14 — `CTOS-29` movida para `Em andamento` no Jira antes do detalhamento.
- 2026-08-14 — `bmad-create-story` executado para detalhar Story 2.2 antes da implementação.
- 2026-08-14 — `bmad-dev-story` iniciado com baseline `bb94b88f29dc82145fc667e38db4fb0956d2562d`; subtarefas Jira `CTOS-146` a `CTOS-150` criadas.
- 2026-08-14 — Teste vermelho inicial confirmado com `ModuleNotFoundError: No module named 'creditos_proposal_intake'`.
- 2026-08-14 — Validação focada final: `26 passed` em `services/proposal-intake/tests`.
- 2026-08-14 — Gates finais executados: contratos `21 passed`, `scripts/check_contracts.py`, `ruff check .`, `ruff format --check .`, `pyright`, `pytest -q -k 'not local_harness'` com `221 passed, 7 deselected`.
- 2026-08-14 — Suíte completa dentro do sandbox falhou somente em `tests/test_local_harness.py` por `Operation not permitted`/`uv: command not found`; repetição fora do sandbox foi solicitada duas vezes e expirou na aprovação automática.
- 2026-08-14 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 8 achados de patch aplicados.
- 2026-08-14 — Validação após patches de review: `services/proposal-intake/tests` com `42 passed`; contratos `21 passed`; `scripts/check_contracts.py`; `ruff check .`; `ruff format --check .`; `pyright`; `pytest -q -k 'not local_harness'` com `237 passed, 7 deselected`; suíte completa fora do sandbox com `244 passed`.

### Implementation Plan

- Criar o novo microsserviço `Proposal Intake` como pacote de workspace com fronteiras `domain`, `application`, `adapters` e `bootstrap`.
- Manter domínio puro com dataclasses imutáveis, erros seguros e value objects de dinheiro, documentos e datas.
- Implementar `ValidateAndNormalizeProposal` como caso de uso runtime/manual, sem adicionar `jsonschema`, Pydantic, FastAPI, banco, gRPC ou NATS.
- Usar porta `CanonicalProposalRepository` e adapter in-memory para persistência mínima da representação canônica.
- Integrar `ProposalIntakeApplicationService` com logs estruturados de payload omitido usando `creditos_observability`.
- Cobrir validações semânticas, normalização, isolamento de tenant confiável, dados sensíveis e fronteira arquitetural com testes.

### Completion Notes List

- 2026-08-14 — Ultimate context engine analysis completed - comprehensive developer guide created.
- 2026-08-14 — Story 2.2 criada com status `ready-for-dev`, escopo focado em validação/normalização runtime e sem implementação de endpoint/idempotência transacional/evento.
- 2026-08-14 — Implementado `Proposal Intake Service` com estrutura DDD/hexagonal instalável no workspace.
- 2026-08-14 — Implementado núcleo de validação/normalização runtime do contrato canônico v1, usando `Idempotency-Key` do header e tenant confiável do contexto observável.
- 2026-08-14 — Implementadas regras semânticas de dinheiro inteiro em centavos, coerência PF/CPF e PJ/CNPJ, produto único compatível, participantes críticos, callback governado e recebíveis com `payer_ref`.
- 2026-08-14 — Implementada persistência mínima via `CanonicalProposalRepository` e adapter `InMemoryCanonicalProposalRepository`.
- 2026-08-14 — Implementados logs estruturados seguros com payload omitido, sem CPF/CNPJ/e-mail/authorization/valores financeiros detalhados nos testes.
- 2026-08-14 — Adicionados 26 testes unitários/de aplicação, incluindo guardrail de arquitetura para impedir dependências de infraestrutura no domínio.
- 2026-08-14 — Aplicados patches de code review: decisão híbrida para opcionais, validação explícita de subestruturas, imutabilidade profunda, identificadores sanitizados, datas estritas, headers seguros, logs por chamada e validação DV de CPF/CNPJ.
- 2026-08-14 — Testes do serviço ampliados para 42 casos e suíte completa validada fora do sandbox com 244 testes passando.

### Change Log

- 2026-08-14 — Criada Story 2.2 para desenvolvimento do núcleo de validação e normalização runtime do `Proposal Intake`.
- 2026-08-14 — Implementado microsserviço `Proposal Intake` e movida Story 2.2 para `review`.
- 2026-08-14 — Achados de `bmad-code-review` corrigidos e Story 2.2 movida para `done`.

### File List

- `_bmad-output/implementation-artifacts/2-2-validacao-e-normalizacao-da-proposta.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `pyproject.toml`
- `services/proposal-intake/README.md`
- `services/proposal-intake/pyproject.toml`
- `services/proposal-intake/src/creditos_proposal_intake/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/adapters/persistence/in_memory_canonical_proposal_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/ports/canonical_proposal_repository.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/use_cases/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/application/use_cases/validate_and_normalize_proposal.py`
- `services/proposal-intake/src/creditos_proposal_intake/bootstrap/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/entities/canonical_proposal.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/errors.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/value_objects/__init__.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/value_objects/dates.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/value_objects/documents.py`
- `services/proposal-intake/src/creditos_proposal_intake/domain/value_objects/money.py`
- `services/proposal-intake/tests/unit/test_domain_boundaries.py`
- `services/proposal-intake/tests/unit/test_validate_and_normalize_proposal.py`
