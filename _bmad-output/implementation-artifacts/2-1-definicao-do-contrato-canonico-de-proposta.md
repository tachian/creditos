---
baseline_commit: 0dab881
jira_issue: CTOS-28
branch: agent/story-2-1-contrato-canonico-proposta
---

# Story 2.1: Definição do Contrato Canônico de Proposta

Status: done

## Story

As a cliente técnico,
I want enviar propostas em um contrato público versionado,
so that a integração seja previsível e não dependa de payload arbitrário.

## Acceptance Criteria

1. **Schema público canônico versionado**
   - **Given** o contrato público de proposta do CreditOS
   - **When** a Story 2.1 for implementada
   - **Then** `packages/contracts/schemas/proposal/v1/proposal.schema.json` define o contrato canônico v1 para CPF/CNPJ e produtos MVP
   - **And** o schema usa JSON Schema Draft 2020-12, `additionalProperties: false`/fechamento equivalente nos blocos governados e metadados `x-creditos` consistentes com o catálogo.

2. **Núcleo comum e produtos MVP**
   - **Given** uma proposta `PF` ou `PJ`
   - **When** `product_type` for `personal_credit`, `bnpl`, `business_credit` ou `receivables`
   - **Then** o contrato exige núcleo comum: `schema_version`, `external_proposal_id`, `person_type`, `product_type`, `channel`, `operation.requested_terms`, `borrower` e `product_data`
   - **And** `product_data` permite exatamente o sub-bloco compatível com `product_type`.
   - **And** a idempotência da API pública é governada pelo header obrigatório `Idempotency-Key`.

3. **Rejeição de payload arbitrário e planos externos**
   - **Given** campos proibidos como `selected_plan`, `plan_id`, `extra_data` livre, `tenant_id` como autoridade no body ou payload sem dono
   - **When** eles aparecem em qualquer payload público de submissão
   - **Then** os testes de contrato falham com erro padronizado e rastreável
   - **And** a evidência não expõe CPF, CNPJ, e-mail completo, payload bruto, valores financeiros detalhados ou secrets.

4. **Contrato alinhado ao OpenAPI público**
   - **Given** `packages/contracts/openapi/public/proposal-intake/v1/openapi.json`
   - **When** o endpoint público de submissão for descrito
   - **Then** o request body referencia o schema canônico de proposta v1
   - **And** preserva headers obrigatórios/esperados de rastreabilidade e idempotência: `X-Correlation-Id`, `X-Request-Id` e `Idempotency-Key`.

5. **Gates de governança e exemplos verificáveis**
   - **Given** os checks locais de contrato
   - **When** `scripts/check_contracts.py` e testes relacionados são executados
   - **Then** validam presença de campos obrigatórios, enums MVP, ausência de campos proibidos e fechamento de schema
   - **And** incluem exemplos mínimos válidos e inválidos para CPF, CNPJ, produto fora do MVP e campo proibido.

## Tasks / Subtasks

- [x] CTOS-28 — Detalhar e materializar o contrato canônico de proposta v1 (AC: 1, 2, 3, 4, 5)
  - [x] CTOS-142 — Substituir o placeholder de `packages/contracts/schemas/proposal/v1/proposal.schema.json` por um JSON Schema canônico v1.
  - [x] CTOS-142 — Modelar núcleo comum, `operation.requested_terms`, `borrower`, `participants`, `consents`, `provided_data`, `risk_context`, `product_data`, `decision_options` e `callback` conforme PRD OQ-3.
  - [x] CTOS-142 — Proibir explicitamente `selected_plan`, `plan_id`, `extra_data`, `tenant_id` como autoridade de body e anexos/payloads brutos.
  - [x] CTOS-143 — Atualizar `packages/contracts/openapi/public/proposal-intake/v1/openapi.json` para referenciar o schema canônico no request body.
  - [x] CTOS-144 — Endurecer `scripts/check_contracts.py` apenas com validações estruturais necessárias, sem adicionar ferramenta externa de diff/contract testing nesta story.
  - [x] CTOS-144 — Adicionar testes e/ou fixtures de contrato para payloads válidos e rejeições críticas.
  - [x] CTOS-145 — Atualizar documentação de `packages/contracts/README.md` se a política de schema público precisar ficar explícita.
  - [x] CTOS-145 — Atualizar `sprint-status.yaml`, esta story e Jira conforme avanço.

### Review Findings

- [x] [Review][Patch] Autoridade de idempotência resolvida: usar header canônico — Decisão do review: `Idempotency-Key` será a fonte canônica da idempotência em APIs públicas. Remover/relaxar `idempotency_key` do body público e tornar `Idempotency-Key` obrigatório no OpenAPI.
- [x] [Review][Patch] Estratégia de validação resolvida: híbrido mínimo com stdlib — Decisão do review: não adicionar dependência nova nesta story; reforçar checks manuais e testes negativos críticos, registrando que validação runtime completa permanece na Story 2.2.
- [x] [Review][Patch] Política de callback resolvida: sem URL livre no payload — Decisão do review: callbacks externos devem ser previamente cadastrados/governados por tenant; o body público não deve aceitar `callback.url` livre. Quando necessário, a proposta referencia apenas callback pré-configurado.
- [x] [Review][Patch] Limites operacionais resolvidos: contrato híbrido — Decisão do review: adicionar tetos seguros e remover duplicidade óbvia de valor no BNPL agora; deixar relações cruzadas mais complexas, como `down_payment <= amount`, para validação/normalização runtime na Story 2.2.
- [x] [Review][Patch] Identificação de participantes resolvida: obrigatória por papel crítico — Decisão do review: exigir identificação completa para papéis de risco/legal como `guarantor`, `co_borrower`, `payer`, `shareholder`, `legal_representative` e `beneficial_owner`; manter referência mínima possível para papéis operacionais.
- [x] [Review][Patch] Regras de CPF/CNPJ por tipo de pessoa e documento permitem combinações incoerentes [`packages/contracts/schemas/proposal/v1/proposal.schema.json:126`]
- [x] [Review][Patch] Identificadores externos podem carregar CPF/CNPJ em campos logáveis [`packages/contracts/schemas/proposal/v1/proposal.schema.json:20`]
- [x] [Review][Patch] Campos proibidos não têm cobertura negativa completa em exemplos/testes [`packages/contracts/schemas/proposal/v1/proposal.schema.json:619`]
- [x] [Review][Patch] Condicionais `if` sem `required` podem produzir semântica imprecisa de validação [`packages/contracts/schemas/proposal/v1/proposal.schema.json:61`]
- [x] [Review][Patch] OpenAPI ainda descreve o endpoint como placeholder [`packages/contracts/openapi/public/proposal-intake/v1/openapi.json:16`]
- [x] [Review][Patch] Testes de governança não exercitam payloads reais para mismatch de produto e blocos extras [`tests/test_contracts_structure.py:237`]

## Dev Notes

### Escopo desta story

- Esta story define contrato e gates de contrato; não cria ainda o `Proposal Intake Service`, endpoint executável, persistência, idempotência transacional, publicação de evento ou normalização runtime.
- A validação runtime completa entra na Story 2.2. Nesta story, “validado contra o schema” significa que o contrato versionado e os testes/checks de contrato conseguem aceitar exemplos válidos e rejeitar exemplos proibidos.
- Não adicionar dependência externa como `jsonschema`, `datamodel-code-generator`, Pydantic runtime ou ferramenta de breaking-change sem justificativa, alternativas e consequência. A fundação atual usa Python stdlib + pytest para governança.
- Se um validador JSON Schema real for necessário para cumprir os exemplos, registrar a decisão técnica antes de adicionar dependência.

### Guardrails de domínio e produto

- Produtos MVP permitidos: `personal_credit`, `bnpl`, `business_credit`, `receivables`.
- `person_type` deve ser `PF` ou `PJ`; `borrower.document_type` deve ser coerente: `CPF` para PF e `CNPJ` para PJ.
- `selected_plan` e `plan_id` são proibidos por decisão de produto; o cliente envia somente `operation.requested_terms`.
- `tenant_id` confiável vem de autenticação/contexto validado pelo Epic 1, não do body público.
- `borrower` deve ser mínimo e não virar cadastro mestre; dados financeiros, contato, endereço e relacionamento ficam em `provided_data`.
- `risk_context` deve ser opcional e não exigir sinais sofisticados como reputação de dispositivo, idade de e-mail ou velocidade de tentativas.
- `product_data` deve conter exatamente um sub-bloco compatível com `product_type`; não aceitar bloco de produto genérico livre.

### Segurança, privacidade e logs

- Não incluir payload bruto sensível em exemplos, mensagens de erro, logs de teste ou comentários.
- Exemplos devem usar documentos claramente fictícios ou mascarados quando não estiverem validando formato.
- `external_proposal_id` e `idempotency_key` não devem conter CPF, CNPJ, e-mail, telefone ou segredo.
- `callback.secret_reference` deve ser referência a segredo previamente cadastrado; nunca segredo bruto.
- A saída de erro dos checks deve apontar o motivo técnico de contrato sem imprimir o payload completo.

### Contratos e compatibilidade

- `proposal-structural-schema` já existe no catálogo em `packages/contracts/catalog/contracts.toml`; manter `id`, `kind = "json-schema"`, `version = "v1"` e owner `Proposal Intake`.
- O schema atual é placeholder estrutural; esta story deve substituí-lo pelo contrato canônico real v1 sem mudar o path versionado.
- OpenAPI atual é estrutural; se passar a referenciar o schema canônico, preservar `openapi: 3.1.0`, `info.version = "v1"`, `ErrorResponse` e respostas `202`, `400`, `401`, `409`, `500`.
- JSON Schema deve manter `$schema = "https://json-schema.org/draft/2020-12/schema"` porque é a versão atual indicada pela especificação oficial.
- OpenAPI 3.1 usa modelos baseados em JSON Schema Draft 2020-12; isso permite alinhar schemas OpenAPI e JSON Schema sem duplicar modelos.
- Eventos continuam fora do escopo principal desta story; Story 2.4 detalha evento de proposta submetida com CloudEvents/NATS.

### Estrutura esperada

```text
packages/contracts/
  schemas/proposal/v1/proposal.schema.json
  openapi/public/proposal-intake/v1/openapi.json
  catalog/contracts.toml
  README.md
scripts/check_contracts.py
tests/test_contracts_structure.py
```

### Arquivos existentes que provavelmente serão atualizados

- `packages/contracts/schemas/proposal/v1/proposal.schema.json`: hoje contém apenas `contract_version` e `correlation_id`; deve virar o contrato canônico v1.
- `packages/contracts/openapi/public/proposal-intake/v1/openapi.json`: hoje é contrato estrutural; deve referenciar o schema canônico no request body, preservando guardrails existentes.
- `scripts/check_contracts.py`: hoje valida metadados e estrutura mínima de JSON Schema; pode receber validações específicas para o schema de proposta.
- `tests/test_contracts_structure.py`: hoje cobre governança e casos negativos; deve cobrir o schema canônico e payloads inválidos essenciais.
- `packages/contracts/README.md`: atualizar apenas se necessário para explicar a política do schema público de proposta.

### Anti-padrões proibidos

- Criar domínio compartilhado em `packages/contracts` ou classes Python de negócio de proposta.
- Criar serviço `Proposal Intake` nesta story.
- Aceitar `additionalProperties: true` em blocos governados do contrato público.
- Criar campo `custom`, `extra`, `metadata`, `attributes`, `raw_payload` ou equivalente como escape hatch sem schema fechado.
- Colocar `tenant_id` no body como fonte de autorização/isolamento.
- Reintroduzir `selected_plan`, `plan_id` ou catálogo de planos da financeira.
- Exigir sinais antifraude avançados de todos os clientes no MVP.

### Testing Requirements

- Rodar teste focado de contratos: `uv run pytest tests/test_contracts_structure.py -q`.
- Rodar checker de contratos: `uv run python scripts/check_contracts.py`.
- Rodar qualidade mínima: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`.
- Se alterar OpenAPI/AsyncAPI, garantir que `scripts/check_contracts.py` continua passando.
- Antes de PR, rodar suíte completa quando viável: `uv run pytest -q`; se o harness falhar por sandbox, repetir fora do sandbox como nas stories anteriores.

### Pesquisa técnica atualizada

- JSON Schema: versão atual da especificação é 2020-12; usar `$schema` explícito evita ambiguidade de dialeto.
- OpenAPI 3.1: schemas de dados são baseados em JSON Schema Draft 2020-12, então o OpenAPI pode referenciar o contrato canônico sem tradução para dialeto antigo.
- CloudEvents: versão estável atual é 1.0.2, mas esta story apenas preserva alinhamento futuro; evento de proposta submetida entra na Story 2.4.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 2 e Story 2.1.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/contrato-inicial-proposta-oq3.md` — contrato conceitual aprovado.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/recomendacoes-decisoes-abertas.md` — OQ-3, OQ-4 e decisões resolvidas.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-4 e bounded contexts.
- `_bmad-output/implementation-artifacts/0-3-estrutura-base-de-contratos-versionados.md` — padrões de contratos versionados e débitos de diff semântico.
- `_bmad-output/implementation-artifacts/1-5-gates-de-seguranca-e-isolamento-do-epic-1.md` — segurança, contexto confiável e logs mascarados consolidados.
- `packages/contracts/README.md` — política de contratos versionados.
- `scripts/check_contracts.py` — checker atual de governança.
- JSON Schema Specification: `https://json-schema.org/specification`.
- JSON Schema Draft 2020-12: `https://json-schema.org/draft/2020-12`.
- OpenAPI Specification 3.1.0: `https://spec.openapis.org/oas/v3.1.0.html`.
- CloudEvents Specification: `https://github.com/cloudevents/spec`.

## Checklist Validation

- [x] Story identifica objetivo, ACs e tarefas verificáveis.
- [x] Story referencia Epic 2, PRD OQ-3, Architecture Spine, Story 0.3 e Story 1.5.
- [x] Story evita reinvenção de serviço, domínio compartilhado ou ferramenta nova sem decisão.
- [x] Story delimita que validação runtime/persistência/idempotência entram em stories seguintes.
- [x] Story preserva segurança, privacidade, multi-tenancy, auditabilidade e explicabilidade como preocupações centrais.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-13 — Branch `agent/story-2-1-contrato-canonico-proposta` criada no início da Story 2.1.
- 2026-08-13 — `origin/main` atualizado após merge do PR #26 e branch avançada por fast-forward para `0dab881`.
- 2026-08-13 — `CTOS-28` movida para `Em andamento` no Jira antes do detalhamento.
- 2026-08-13 — `bmad-create-story` executado para detalhar Story 2.1 antes da implementação.
- 2026-08-13 — `bmad-dev-story` iniciado para implementação do contrato canônico v1.
- 2026-08-13 — Subtarefas Jira `CTOS-142` a `CTOS-145` criadas para rastrear schema, OpenAPI, gates e documentação.
- 2026-08-13 — `CTOS-142`, `CTOS-143`, `CTOS-144` e `CTOS-145` concluídas conforme avanço de implementação e rastreabilidade.
- 2026-08-13 — Suíte completa executada fora do sandbox com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q`: `197 passed`.
- 2026-08-14 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 11 achados resolvidos por patch após decisões do usuário.
- 2026-08-14 — Suíte completa executada fora do sandbox após patches de review com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q`: `202 passed`.

### Implementation Plan

- Escrever testes RED de contrato para schema canônico, OpenAPI, campos proibidos, produtos MVP e exemplos.
- Substituir o placeholder por JSON Schema v1 fechado, sem payload arbitrário e sem planos externos.
- Conectar o OpenAPI público ao schema canônico via request body.
- Endurecer `scripts/check_contracts.py` com validações estruturais específicas de proposta usando apenas stdlib.
- Validar foco, qualidade e suíte completa antes de mover a story para review.

### Completion Notes List

- 2026-08-13 — Ultimate context engine analysis completed - comprehensive developer guide created.
- 2026-08-13 — Story 2.1 criada com status `ready-for-dev`, com escopo limitado à materialização do contrato canônico e gates de contrato.
- 2026-08-13 — Schema canônico de proposta v1 implementado para CPF/CNPJ e produtos MVP, com blocos governados fechados e exemplos válidos/invalidos.
- 2026-08-13 — OpenAPI público de Proposal Intake atualizado para referenciar o schema canônico no request body.
- 2026-08-13 — Checker de contratos endurecido para validar campos obrigatórios, produtos MVP, campos proibidos, fechamento de schema e exemplos governados.
- 2026-08-13 — Documentação de contratos atualizada com política do schema público de proposta.
- 2026-08-13 — Validações verdes: `tests/test_contracts_structure.py` com `16 passed`, `scripts/check_contracts.py`, `ruff check .`, `ruff format --check .`, `pyright` e suíte completa fora do sandbox com `197 passed`.
- 2026-08-13 — Jira sincronizado com subtarefas da Story 2.1 e story preparada para revisão (`review`).
- 2026-08-14 — Patches do code review aplicados: `Idempotency-Key` tornou-se fonte canônica no header, `idempotency_key` saiu do body, callback por URL livre foi removido, limites operacionais foram adicionados, participantes críticos passaram a exigir identificação e testes negativos foram ampliados.
- 2026-08-14 — Validações finais verdes: `scripts/check_contracts.py`, `tests/test_contracts_structure.py` com `21 passed`, `ruff check .`, `ruff format --check .`, `pyright` e suíte completa fora do sandbox com `202 passed`.

### Change Log

- 2026-08-13 — Criada Story 2.1 para desenvolvimento do contrato canônico de proposta v1.
- 2026-08-13 — Story movida para `in-progress` para execução via `bmad-dev-story`.
- 2026-08-13 — Contrato canônico v1, OpenAPI, gates de contrato e documentação implementados; Story movida para `review`.
- 2026-08-14 — Achados do `bmad-code-review` resolvidos e Story movida para `done`.

### File List

- `_bmad-output/implementation-artifacts/2-1-definicao-do-contrato-canonico-de-proposta.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `packages/contracts/README.md`
- `packages/contracts/openapi/public/proposal-intake/v1/openapi.json`
- `packages/contracts/schemas/proposal/v1/proposal.schema.json`
- `scripts/check_contracts.py`
- `tests/test_contracts_structure.py`
