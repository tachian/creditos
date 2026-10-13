---
jira_issue: CTOS-72
branch: agent/story-8-7-e2e-mocked-analysis-flow
baseline_commit: cc9d7674988e9120bb48d9394f548357714a8630
---

# Story 8.7: Fluxo E2E de Análise com Integrações Mockadas

Status: done

## Story

Como cliente técnico avaliando o MVP,
quero enviar uma proposta e obter uma resposta analisada com integrações externas mockadas,
para validar a jornada completa sem fornecedores reais.

## Acceptance Criteria

1. **Submissão canônica e idempotente**
   - **Given** tenant configurado, contexto técnico autenticado, política publicada e adapters mock/sandbox habilitados
   - **When** o cliente envia payload válido de proposta CPF ou CNPJ de produto MVP
   - **Then** o sistema valida schema, normaliza a proposta, aplica idempotência e cria status inicial/outbox
   - **And** reenvio com a mesma `idempotency_key` não duplica efeitos críticos.

2. **Integrações externas mockadas enriquecem a análise**
   - **Given** plano de integrações aplicável ao tenant/produto
   - **When** o fluxo executa as integrações mock/sandbox
   - **Then** usa adapters existentes, resultados canônicos, fan-out/fan-in in-memory e custo projetável
   - **And** não usa fornecedor real, HTTP externo, NATS real, banco real ou payload sensível bruto.

3. **Decisão explicável com política publicada**
   - **Given** resultados canônicos das integrações e política publicada
   - **When** o fluxo executa a decisão
   - **Then** gera decisão final ou estado inconclusivo explicável com `policy/version`, reason codes, fatores permitidos e correlation ID
   - **And** preserva determinismo e não acopla o domínio de decisão a semântica proprietária de fornecedor.

4. **Consulta pública e callback versionados**
   - **Given** decisão disponível para o tenant correto
   - **When** o cliente consulta a proposta ou recebe callback configurado
   - **Then** obtém status/resultado pelo contrato público versionado
   - **And** nenhum dado sensível bruto, detalhe interno ou informação de outro tenant é exposto.

5. **Rastreabilidade ponta a ponta**
   - **Given** a suíte E2E roda em ambiente não produtivo
   - **When** a jornada submissão → mocks externos → decisão → auditoria/logs/métricas → consulta/callback é executada
   - **Then** cada etapa crítica é rastreável pelo mesmo correlation ID
   - **And** falha se faltar auditoria, log seguro, métrica/projeção de negócio ou evidência crítica esperada.

6. **Gates negativos de segurança e contrato**
   - **Given** tentativa cross-tenant, payload sensível em saída/log ou drift de contrato público
   - **When** a suíte automatizada é executada
   - **Then** a validação falha de forma determinística e segura
   - **And** erros públicos continuam indistinguíveis para inexistente, sem permissão ou outro tenant quando aplicável.

## Tasks / Subtasks

- [x] CTOS-452 — Montar harness E2E in-memory e fixtures governadas (AC: 1-5)
  - [x] Criar cenário E2E puro em memória, preferencialmente em `tests/test_epic8_e2e_mocked_analysis_flow.py`.
  - [x] Montar fixtures sintéticas de tenant, contexto propagado, proposta PF/PJ MVP, política publicada e catálogo de reason codes.
  - [x] Reutilizar builders/padrões de testes existentes; não criar servidor HTTP, broker real, fornecedor real ou storage real.

- [x] CTOS-453 — Submeter proposta idempotente e executar integrações mockadas (AC: 1, 2, 5)
  - [x] Reutilizar `ProposalIntakeApplicationService.submit_with_initial_status_and_outbox`.
  - [x] Reutilizar `IntegrationCatalogApplicationService.execute_mock_integration_plan` e adapters mock/sandbox existentes.
  - [x] Validar reenvio idempotente, plano aplicável, resultados canônicos, custo e logs sem payload sensível bruto.

- [x] CTOS-454 — Executar decisão explicável com política publicada (AC: 3, 5)
  - [x] Reutilizar `DecisionApplicationService.execute_credit_decision`.
  - [x] Passar somente field values e referências canônicas permitidas, sem payload bruto de fornecedor.
  - [x] Validar explicabilidade pública: política, versão, reason codes, fatores, termos quando aplicável e correlation ID.

- [x] CTOS-455 — Validar consulta pública e callback assinado no fluxo (AC: 4, 6)
  - [x] Reutilizar `DecisionApplicationService.get_public_credit_decision_by_proposal`.
  - [x] Reutilizar `configure_webhook` e `dispatch_webhook_notification` com dispatcher in-memory quando o caminho de callback for exercitado.
  - [x] Validar isolamento cross-tenant, mensagem pública segura, assinatura/canonicalização e idempotência de callback.

- [x] CTOS-456 — Validar auditoria, logs, métricas e projeções de negócio (AC: 2, 5, 6)
  - [x] Reutilizar `AuditEvidenceApplicationService.register_event` ou adapters de auditoria já existentes nos serviços.
  - [x] Reutilizar `ReportingInsightsService.record_event` para projeções de funil, decisão, integração/custo e consulta/callback quando houver evento disponível.
  - [x] Validar `tenant_id`, `correlation_id`, `trace_id`, `request_id`, status, duração e ausência de CPF/CNPJ/e-mail/nome/telefone/token/payload bruto.

- [x] CTOS-457 — Automatizar cenários negativos e validações finais (AC: 1-6)
  - [x] Adicionar casos negativos para cross-tenant, ausência de etapa rastreável, vazamento de dado sensível e quebra de contrato público.
  - [x] Rodar testes focados, `scripts/check_contracts.py --contracts-root packages/contracts`, Ruff e Pyright.
  - [x] Atualizar File List, Change Log, `sprint-status.yaml` e Jira conforme avanço real.

### Review Findings

- [x] [Review][Patch] Callback usa `proposal_id` fixo e não prova vínculo com a proposta submetida [`tests/epic8_mocked_analysis_flow_support.py:224`]
- [x] [Review][Patch] Gates de dados sensíveis validam payload curado e não todas as saídas reais [`tests/epic8_mocked_analysis_flow_support.py:278`]
- [x] [Review][Patch] Callback não prova idempotência nem assinatura HMAC canonicalizada [`tests/test_epic8_e2e_mocked_analysis_flow.py:43`]
- [x] [Review][Patch] Gates negativos de vazamento, rastreabilidade e drift contratual estão incompletos [`tests/test_epic8_e2e_mocked_analysis_flow.py:77`]
- [x] [Review][Patch] Replay idempotente da proposta valida apenas ID, não ausência de efeitos duplicados [`tests/test_epic8_e2e_mocked_analysis_flow.py:17`]
- [x] [Review][Patch] Detecção de rastreabilidade não exige `correlation_id` em todas as etapas críticas [`tests/epic8_mocked_analysis_flow_support.py:841`]
- [x] [Review][Patch] Caminho obrigatório `execute_mock_integration_plan` não é exercitado pelo harness [`tests/epic8_mocked_analysis_flow_support.py:189`]
- [x] [Review][Patch] Auditoria crítica não cobre proposta, integração/custo e callback ponta a ponta [`tests/test_epic8_e2e_mocked_analysis_flow.py:49`]

## Dev Notes

### Escopo funcional

- Esta story prova o primeiro fluxo E2E utilizável do MVP com dependências mockadas: submissão da proposta, enriquecimento por integrações externas simuladas, decisão, rastreabilidade, consulta pública e callback quando configurado.
- O objetivo é demonstrar comportamento executável em ambiente não produtivo; não é o momento de criar APIs reais, gRPC real, NATS JetStream real, persistência real, IaC, dashboards reais ou integrações com bureaus reais.
- O fluxo deve ser determinístico, in-memory e testável em CI. Se alguma etapa real ainda não existir, criar apenas o menor adaptador/test helper necessário para orquestrar capacidades existentes, sem violar DDD/hexagonal.
- Não selecionar novas bibliotecas, frameworks ou tecnologias. Nenhuma pesquisa técnica externa foi necessária porque a story deve reutilizar contratos, serviços e testes já presentes no repositório.

### Reuso obrigatório

- Proposal Intake:
  - `services/proposal-intake/src/creditos_proposal_intake/application/service.py`
  - `submit_with_initial_status_and_outbox`, `submit_idempotent`, `validate_and_normalize`
  - Testes de referência: `services/proposal-intake/tests/unit/test_initial_status_and_outbox.py`, `test_idempotent_submission.py`, `test_validate_and_normalize_proposal.py`
- Integration:
  - `services/integration/src/creditos_integration/application/service.py`
  - `execute_mock_integration_plan`, `configure_webhook`, `dispatch_webhook_notification`
  - `services/integration/src/creditos_integration/adapters/external/in_memory_mock_integration_adapter.py`
  - Testes de referência: `services/integration/tests/unit/test_mock_integration_adapters.py`, `test_integration_async_execution.py`, `test_webhook_delivery.py`
- Decision:
  - `services/decision/src/creditos_decision/application/service.py`
  - `execute_credit_decision`, `get_public_credit_decision_by_proposal`
  - Repositórios in-memory em `services/decision/src/creditos_decision/adapters/persistence`
  - Testes de referência: `services/decision/tests/unit/test_credit_decision_service.py`, `test_credit_policy_publication_service.py`, `test_reason_code_catalog_service.py`
- Audit & Evidence:
  - `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
  - `register_event` para eventos críticos quando não houver adapter já integrado.
- Reporting & Insights:
  - `services/reporting-insights/src/creditos_reporting_insights/application/service.py`
  - `record_event`, `list_tenant_snapshots`, `build_projection_log`
  - Testes de referência: `services/reporting-insights/tests/unit/test_business_metrics_projections.py`, `test_customer_facing_dashboards.py`
- Contratos:
  - `packages/contracts/schemas/proposal/v1/proposal.schema.json`
  - `packages/contracts/openapi/public/decision/v1/openapi.json`
  - `packages/contracts/openapi/public/webhooks/v1/openapi.json`
  - `packages/contracts/consumer-expectations/decision-public/v1/README.md`
  - `packages/contracts/consumer-expectations/webhook-public/v1/README.md`

### Guardrails de arquitetura

- Manter DDD + arquitetura hexagonal: domínio sem dependência de transporte, framework, banco, fornecedor externo ou formato proprietário.
- Cada bounded context continua dono dos próprios dados. Não criar consulta direta entre repositórios transacionais de serviços como substituto de contrato.
- Para esta story, chamadas entre serviços podem ser composição in-memory de aplicações/ports em teste. Não implementar gRPC/NATS reais apenas para satisfazer o E2E.
- O `Integration Service` é o único responsável por adapters externos, mocks/sandbox, retries, DLQ, resultados e custos de integração.
- O `Decision Service` consome sinais canônicos e referências de resultado; não deve conhecer payloads de bureau, KYC, antifraude ou fornecedor.
- `Audit & Evidence` é a trilha oficial para evidências críticas; eventos e logs não substituem auditoria.
- `Reporting & Insights` recebe/projeta eventos de negócio; dashboards customer-facing não devem usar telemetria bruta.

### Segurança, privacidade e multi-tenancy

- `tenant_id` confiável vem de contexto autenticado/propagado; nunca do body da proposta sem validação.
- Cenários cross-tenant devem retornar erro seguro e indistinguível na superfície pública.
- Logs, métricas, auditoria e callbacks devem mascarar ou omitir CPF, CNPJ, e-mail, nome, telefone, endereço, token, segredo, headers privados e payload bruto.
- O teste deve procurar explicitamente termos/valores sensíveis serializados nos artefatos públicos e observáveis.
- Usar apenas dados sintéticos e identificadores técnicos não sensíveis.

### Testes mínimos esperados

- E2E feliz PF ou PJ MVP com proposta válida, integração mockada, decisão final e consulta pública.
- Caminho com callback configurado usando dispatcher in-memory e assinatura compatível com contrato v1.
- Reenvio idempotente da proposta sem duplicar status/outbox/efeitos críticos.
- Falha se qualquer etapa crítica não possuir correlation ID consistente.
- Falha se saída pública, callback, log, métrica, projeção ou auditoria expuser dado sensível bruto.
- Falha segura para consulta cross-tenant ou proposta inexistente.
- `scripts/check_contracts.py --contracts-root packages/contracts` continua passando.

### Arquivos prováveis

- `tests/test_epic8_e2e_mocked_analysis_flow.py`
- `services/proposal-intake/tests/unit/test_initial_status_and_outbox.py`
- `services/integration/tests/unit/test_mock_integration_adapters.py`
- `services/integration/tests/unit/test_webhook_delivery.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `services/reporting-insights/tests/unit/test_business_metrics_projections.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/8-7-fluxo-e2e-de-analise-com-integracoes-mockadas.md`

## Anti-Patterns

- Não criar API real, gateway, servidor HTTP, broker NATS real, gRPC real, banco real ou fornecedor real nesta story.
- Não criar um orquestrador de produção acoplado se um test harness in-memory resolver a validação do MVP.
- Não duplicar contratos públicos fora de `packages/contracts`.
- Não alterar contrato v1 para acomodar teste ruim; se houver incompatibilidade real, registrar decisão e ajustar via contrato governado.
- Não usar dados reais ou exemplos que pareçam credenciais.
- Não registrar payload bruto de proposta, payload bruto de provedor, headers privados, token ou segredo.
- Não fazer `time.sleep`, chamadas de rede, dependência de relógio real instável ou teste não determinístico.

## Referências

- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/integracoes-externas-oq8.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`
- `_bmad-output/implementation-artifacts/8-6-testes-de-contrato-para-consulta-e-webhooks.md`
- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
- `services/reporting-insights/src/creditos_reporting_insights/application/service.py`

## Dev Agent Record

### Agent Model Used

- Codex CLI

### Debug Log References

- `python3 _bmad/scripts/resolve_customization.py --skill .agents/skills/bmad-create-story --key workflow`
- `git switch main && git pull --ff-only origin main`
- `git log -5 --oneline`
- `parent = CTOS-72 ORDER BY key ASC`
- `git switch -c agent/story-8-7-e2e-mocked-analysis-flow`
- Jira: `CTOS-72` e `CTOS-452` movidos para `Em andamento`.
- `uv run pytest tests/test_epic8_e2e_mocked_analysis_flow.py` falhou porque `uv` não está disponível no PATH local.
- `.venv/bin/python -m pytest tests/test_epic8_e2e_mocked_analysis_flow.py` confirmou o RED inicial por módulo de suporte ausente.
- `.venv/bin/python -m pytest tests/test_epic8_e2e_mocked_analysis_flow.py` passou com 2 testes após implementação.
- `.venv/bin/python scripts/check_contracts.py --contracts-root packages/contracts` passou.
- `.venv/bin/python -m ruff format --check .` passou.
- `.venv/bin/python -m ruff check .` passou.
- `.venv/bin/python -m pyright` passou.
- `.venv/bin/python -m pytest` falhou no sandbox em `tests/test_local_harness.py` por `Operation not permitted` ao abrir socket local.
- `.venv/bin/python -m pytest` reexecutado fora do sandbox e passou com 861 testes.
- `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 8 findings de patch registrados.
- `.venv/bin/python -m pytest tests/test_epic8_e2e_mocked_analysis_flow.py` passou com 3 testes após correções de review.
- `.venv/bin/python scripts/check_contracts.py --contracts-root packages/contracts` passou após correções de review.
- `.venv/bin/python -m ruff format --check .` passou após correções de review.
- `.venv/bin/python -m ruff check .` passou após correções de review.
- `.venv/bin/python -m pyright` passou após correções de review.
- `.venv/bin/python -m pytest` falhou no sandbox em `tests/test_local_harness.py` por `Operation not permitted` ao abrir socket local.
- `.venv/bin/python -m pytest` reexecutado fora do sandbox e passou com 862 testes.

### Completion Notes List

- Story criada com contexto consolidado de Epic 8, Architecture Spine, OQ-8, OQ-9, OQ-12 e aprendizados da Story 8.6.
- Subtarefas Jira `CTOS-452` a `CTOS-457` criadas para acompanhar a implementação antes de codificar.
- Escopo limitado a fluxo E2E in-memory com mocks externos, sem novas tecnologias e sem infraestrutura real.
- Implementado teste E2E in-memory que compõe Proposal Intake, Integration, Decision, Audit & Evidence, Reporting & Insights e Webhook Delivery sem rede, broker, banco real ou fornecedor externo.
- Validada submissão idempotente, execução mockada de integrações, decisão explicável, consulta pública, callback assinado, auditoria oficial, projeções de negócio, correlação ponta a ponta e bloqueio cross-tenant indistinguível.
- Criado payload de observabilidade curado para provar ausência de dados sensíveis brutos sem expor `proposal_id`, `decision_id`, headers, payload bruto ou valores pessoais.
- Findings do code review resolvidos: callback vinculado à proposta submetida, idempotência de callback, assinatura HMAC canonicalizada, contrato público, gates negativos, rastreabilidade correlacionada, execução mock direta e evidência crítica ponta a ponta.

### File List

- `_bmad-output/implementation-artifacts/8-7-fluxo-e2e-de-analise-com-integracoes-mockadas.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `tests/epic8_mocked_analysis_flow_support.py`
- `tests/test_epic8_e2e_mocked_analysis_flow.py`

### Change Log

- 2026-10-12: Story criada por `bmad-create-story` com status `ready-for-dev`.
- 2026-10-12: Implementado fluxo E2E in-memory com integrações mockadas, consulta pública, callback assinado, auditoria, projeções e gates negativos; status atualizado para `review`.
- 2026-10-12: Corrigidos 8 findings do `bmad-code-review`; status atualizado para `done`.
