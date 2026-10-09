---
jira_issue: CTOS-70
branch: agent/story-8-5-observability-audit-consultation-callback
baseline_commit: 3fc446f
---

# Story 8.5: Observabilidade e Auditoria de Consulta/Callback

Status: done

## Story

Como operador da plataforma,
quero consultas de decisão e callbacks rastreados, observáveis e auditáveis,
para que incidentes, disputas de entrega e acessos sensíveis possam ser investigados sem exposição de dados sensíveis.

## Acceptance Criteria

1. **Consulta pública de decisão rastreável**
   - **Given** uma consulta pública de status/decisão por proposta
   - **When** a consulta é executada com tenant autenticado e contexto confiável
   - **Then** registra log estruturado seguro com tenant, operação, status, duração, `correlation_id`, `trace_id` e identificador técnico permitido
   - **And** não registra CPF, CNPJ, nome, e-mail, endereço, token, payload bruto, evidência restrita, segredo ou stack trace.

2. **Auditoria oficial para acesso sensível permitido**
   - **Given** uma consulta autorizada que acessa decisão, explicabilidade ou evidência sensível permitida
   - **When** a resposta pública é montada ou retornada
   - **Then** publica intenção/evento para a trilha oficial do `Audit & Evidence`
   - **And** a auditoria contém tenant, ator técnico, operação, recurso, resultado, `correlation_id`, `trace_id`, versão de contrato e referência segura da proposta/decisão.

3. **Falhas de consulta observáveis e seguras**
   - **Given** uma consulta inexistente, não autorizada, cross-tenant, inconclusiva ou com falha técnica
   - **When** o serviço responde com erro público ou estado controlado
   - **Then** registra sinal operacional com código de erro normalizado e sem revelar existência de recurso de outro tenant
   - **And** não vaza detalhe interno, query sensível, evidência, payload bruto ou identificador livre proibido.

4. **Callback/webhook com sinais operacionais normalizados**
   - **Given** tentativa de callback criada, enviada, falhada, retentada, enviada para DLQ ou reprocessada
   - **When** o `Integration Service` registra o ciclo de entrega
   - **Then** emite logs, métricas e eventos operacionais seguros com tenant, evento, status, tentativa, classe de falha, duração quando disponível, `correlation_id` e `trace_id`
   - **And** não inclui endpoint completo com query, payload sensível bruto, segredo de assinatura, body de resposta do cliente ou token.

5. **Projeções de negócio seguras para Reporting & Insights**
   - **Given** sinais de consulta de decisão e callback/webhook
   - **When** forem convertidos em eventos ou snapshots de negócio
   - **Then** produzem dados minimizados, tenant-scoped e idempotentes para volume, latência, erro, retry, DLQ, freshness e saúde operacional curada
   - **And** esses dados não consultam bancos transacionais de outros serviços nem dependem de Prometheus, Loki, Tempo, logs crus ou traces crus.

6. **Gates de privacidade, auditoria e exposição**
   - **Given** logs, métricas, eventos operacionais, auditoria simulada e projeções serializadas desta story
   - **When** os testes/gates locais são executados
   - **Then** falham se houver CPF, CNPJ, e-mail, nome, telefone, endereço, token, segredo, payload bruto, prompt/output, evidência restrita, endpoint sensível ou identificador livre proibido
   - **And** validam tenant obrigatório, escopos quando aplicável, correlação e separação entre observabilidade técnica, projeção de negócio e auditoria oficial.

7. **Compatibilidade com arquitetura aprovada**
   - **Given** as decisões arquiteturais do CreditOS
   - **When** a instrumentação for implementada
   - **Then** mantém DDD/hexagonal, domínio sem dependência de OpenTelemetry, sem leitura direta cross-service, gRPC apenas para comunicação interna síncrona e eventos assíncronos compatíveis com NATS JetStream/CloudEvents
   - **And** não cria novo microsserviço, dashboard visual ou dependência externa sem decisão registrada.

## Tasks / Subtasks

- [x] CTOS-440 — Instrumentar consulta pública de decisão com logs, métricas e auditoria segura (AC: 1, 2, 3, 7)
  - [x] Reutilizar o serviço de consulta pública de decisão criado nas Stories 8.1/8.2.
  - [x] Emitir log e métrica técnica com tenant, operação, status, duração, `correlation_id` e `trace_id`.
  - [x] Publicar intenção/evento de auditoria oficial quando houver acesso sensível permitido.
  - [x] Garantir que respostas negativas não revelem existência de proposta/decisão em outro tenant.

- [x] CTOS-441 — Normalizar sinais operacionais de webhook delivery e callback (AC: 4, 7)
  - [x] Consolidar nomes de eventos/sinais para `created`, `sent`, `failed`, `retry_scheduled`, `dlq_recorded`, `retry_due` e `reprocess_requested`, ou equivalentes documentados.
  - [x] Padronizar atributos seguros de status, tentativa, classe de falha, duração e rastreabilidade.
  - [x] Evitar labels técnicas de alta cardinalidade com `proposal_id`, `decision_id`, `trace_id`, `request_id` ou endpoint.

- [x] CTOS-442 — Projetar métricas de negócio seguras para consulta e callback (AC: 5, 7)
  - [x] Criar ou reutilizar modelo/evento minimizado para consumo futuro do `Reporting & Insights`.
  - [x] Cobrir volume, latência agregável, erro, retry, DLQ, freshness e saúde operacional curada por tenant/produto/canal/período quando disponível.
  - [x] Aplicar idempotência por `source + event_id` e por `tenant + event_type + schema_version + idempotency_key` quando disponível.

- [x] CTOS-443 — Adicionar gates contra vazamento em observabilidade e auditoria da Story 8.5 (AC: 1, 2, 3, 4, 5, 6)
  - [x] Validar artefatos de consulta e callback com os gates de observabilidade/exposição existentes.
  - [x] Adicionar casos negativos para CPF, CNPJ, e-mail, nome, telefone, token, segredo, payload bruto, endpoint com query e evidência restrita.
  - [x] Cobrir isolamento por tenant e ausência de dados cross-tenant em logs, auditoria e projeções.

- [x] CTOS-444 — Atualizar documentação operacional de rastreabilidade de consulta/callback (AC: 4, 5, 6, 7)
  - [x] Documentar taxonomia de logs, métricas, eventos operacionais e eventos de auditoria usados nesta story.
  - [x] Registrar explicitamente que observabilidade técnica não substitui auditoria oficial.
  - [x] Registrar que visões customer-facing usam projeções curadas e não telemetria bruta.

- [x] CTOS-445 — Validar regressões locais de observabilidade e auditoria de consulta/callback (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Executar testes unitários específicos dos serviços alterados.
  - [x] Executar gates locais de auditoria/logs/dados sensíveis e observabilidade/exposição.
  - [x] Atualizar `uv.lock` apenas se a implementação alterar dependências ou metadata de projeto.

### Review Findings

- [x] [Review][Patch] Gate de telefone pode ignorar telefone real próximo de timestamp ou número hexadecimal puro [packages/observability/src/creditos_observability/gates.py:447]
- [x] [Review][Patch] IDs/idempotency keys de eventos de negócio incluem `occurred_at`, quebrando deduplicação em replay/retry [services/decision/src/creditos_decision/application/service.py:2618]
- [x] [Review][Patch] Rejeições de consulta podem gerar evento de negócio com tenant `unknown_tenant` e sem dimensão projetável segura [services/decision/src/creditos_decision/application/service.py:2652]
- [x] [Review][Patch] Falhas técnicas internas da consulta pública são classificadas como `rejected` na telemetria [services/decision/src/creditos_decision/application/service.py:1293]
- [x] [Review][Patch] Eventos de callback usam tier do contexto sem validar compatibilidade com tenant do job/schedule/DLQ [services/integration/src/creditos_integration/application/service.py:2478]
- [x] [Review][Patch] Evento `webhook_delivery.created` entra como `callback_status="skipped"` e pode poluir contadores customer-facing [services/integration/src/creditos_integration/application/service.py:1607]
- [x] [Review][Patch] Sinais de callback não propagam classe/código de falha normalizado para telemetria/eventos [services/integration/src/creditos_integration/application/service.py:2440]

## Dev Notes

### Escopo funcional

- Esta story é de instrumentação e governança de sinais para fluxos já criados nas Stories 8.1 a 8.4.
- O objetivo é tornar consulta pública de decisão e callbacks/webhooks investigáveis, auditáveis e seguros.
- Não implementar UI, dashboard visual, endpoint externo real, broker real, storage real ou novo microsserviço nesta story.
- Não alterar contrato público de consulta/callback salvo se for necessário para corrigir lacuna explícita; qualquer alteração exige testes de contrato e justificativa.
- A Story 8.6 continua responsável por testes de contrato abrangentes para consulta e webhooks; esta story cobre gates e regressões locais de observabilidade/auditoria.

### Arquitetura e ownership

- `Decision Service` é responsável pela consulta pública de status/decisão e pela emissão de intenção/evento de auditoria quando a consulta acessa decisão, explicabilidade ou evidência sensível permitida.
- `Integration Service` é responsável pelos sinais operacionais de webhook/callback, retry, DLQ e reprocessamento.
- `Audit & Evidence` é a trilha oficial; logs, métricas, traces e eventos operacionais não substituem auditoria.
- `Reporting & Insights` é o destino lógico das projeções customer-facing e de negócio; não deve consultar bancos transacionais de outros serviços nem backends técnicos de observabilidade.
- O domínio deve permanecer livre de dependências de OpenTelemetry, Grafana, Loki, Tempo, Prometheus, NATS real, HTTP externo real ou SDKs de infraestrutura.

### Dados permitidos e proibidos

- Campos permitidos em logs/sinais técnicos: `tenant_id` controlado, `tenant_isolation_tier`, operação, status, duração, classe de falha normalizada, tentativa, `correlation_id`, `trace_id`, `request_id` técnico e referências públicas/governadas.
- Campos permitidos em projeções de negócio: tenant de referência seguro, produto, canal, período, volumes agregáveis, status operacional curado, latência agregável, erros agregados, retries, DLQ e freshness.
- Campos proibidos: CPF, CNPJ, nome, e-mail, telefone, endereço, token, segredo, chave de assinatura, payload bruto, body de resposta externo, endpoint com query, prompt/output, evidência restrita, stack trace e dados de outro tenant.
- `tenant_id` pode existir em read model de negócio isolado, mas não deve virar label técnica livre de alta cardinalidade em métricas.

### Consulta pública de decisão

- Reutilizar o contrato público e a resposta explicável existentes, preservando minimização e versionamento.
- A auditoria deve registrar acesso autorizado a decisão/evidência por referência segura, não o conteúdo sensível completo.
- Erros públicos devem ser normalizados; para cross-tenant ou recurso inexistente, evitar mensagem que permita enumeração.
- Falha de auditoria crítica associada a decisão/evidência deve preservar comportamento seguro já adotado no projeto.

### Callback/webhook

- Reutilizar o job assíncrono, assinatura, retry, DLQ e reprocessamento da Story 8.4.
- Os sinais desta story devem ser consistentes com os eventos operacionais já emitidos: criação, envio, falha, agendamento de retry, DLQ e reprocessamento.
- Endpoint completo com query, segredo de assinatura e payload público do webhook não devem ser registrados em logs, métricas, auditoria operacional ou projeções.
- Métricas por tenant detalhadas devem ir para projeção de negócio, não para labels técnicas de alta cardinalidade.

### Testes mínimos esperados

- Consulta de decisão bem-sucedida emite log/métrica seguros e auditoria quando acessa dado sensível permitido.
- Consulta não autorizada, cross-tenant ou inexistente não vaza existência de recurso nem dados sensíveis.
- Callback enviado, falhado, retentado, enviado para DLQ e reprocessado produz sinais operacionais normalizados e seguros.
- Projeções de negócio para consulta/callback são tenant-scoped, minimizadas e idempotentes.
- Gates existentes detectam vazamento em logs, métricas, eventos, auditoria simulada e payloads customer-facing.
- Testes provam que observabilidade técnica, auditoria oficial e projeções de negócio permanecem separadas.

### Arquivos prováveis

- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/application/ports/audit_publisher.py`
- `services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/application/ports/webhook_delivery.py`
- `services/integration/tests/unit/test_webhook_delivery.py`
- `packages/observability/src/creditos_observability/telemetry.py`
- `packages/observability/src/creditos_observability/gates.py`
- `packages/observability/tests/unit/test_telemetry_operations.py`
- `tests/test_epic6_audit_logs_sensitive_data_gates.py`
- `tests/test_epic7_observability_exposure_gates.py`
- `docs/observability.md`
- `docs/observability-dashboards.md`
- `docs/observability-alerts.md`

## Anti-Patterns

- Não usar logs como auditoria oficial.
- Não expor telemetria bruta, logs crus ou traces crus em visão customer-facing.
- Não consultar diretamente bancos transacionais de outros serviços para montar projeções.
- Não criar labels técnicas de alta cardinalidade com proposta, decisão, correlação, request, trace, endpoint ou tenant sem controle explícito.
- Não registrar payload bruto, evidência restrita, segredo, token, endpoint com query ou body de resposta do cliente.
- Não adicionar dependência nova para observabilidade, mensageria, HTTP externo ou storage real sem justificativa e decisão registrada.
- Não criar novo microsserviço nem antecipar UI/dashboard visual desta story.

## Referências

- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`
- `docs/observability.md`
- `docs/observability-dashboards.md`
- `docs/observability-alerts.md`
- `_bmad-output/implementation-artifacts/8-1-consulta-de-decisao-por-proposta.md`
- `_bmad-output/implementation-artifacts/8-2-contrato-publico-de-status-e-decisao.md`
- `_bmad-output/implementation-artifacts/8-3-configuracao-de-webhooks-por-tenant.md`
- `_bmad-output/implementation-artifacts/8-4-entrega-assincrona-de-webhooks-com-retry-e-dlq.md`

## Dev Agent Record

### Branch

- Planejada: `agent/story-8-5-observability-audit-consultation-callback`

### Checklist de Implementação

- [x] Criar branch no início de `bmad-dev-story`.
- [x] Mover `CTOS-70` e primeira subtask para `Em andamento` ao iniciar implementação.
- [x] Atualizar subtarefas Jira conforme avanço real.
- [x] Rodar `bmad-code-review` antes de `commit/push/draft PR`.
- [x] Corrigir pontos de review no mesmo PR quando aplicável.

### Implementação

- Instrumentei a consulta pública de decisão com telemetry opcional, logs seguros já existentes, evento de negócio minimizado `decision_query` e preservação da publicação de intenção/evento para `Audit & Evidence`.
- Normalizei sinais de webhook/callback para criação, envio, falha, retry, retry due, DLQ e reprocessamento, com logs/telemetria seguros e eventos de negócio minimizados.
- Estendi `Reporting & Insights` com contadores `decision_query_counts`, seção customer-facing `decision_queries` e callbacks com DLQ/reprocessamento.
- Reforcei gates de observabilidade para não tratar timestamps ISO e identificadores hexadecimais como telefone bruto.
- Atualizei documentação operacional para registrar separação entre observabilidade técnica, projeções de negócio e auditoria oficial.

### Debug Log

- A suíte completa falhou no sandbox por bloqueio de sockets locais no `local_harness`; a mesma suíte passou fora do sandbox com permissão elevada.
- `uv.lock` não foi alterado porque não houve mudança de dependências ou metadata de projeto.

### Validações

- `.venv/bin/python -m pytest services/reporting-insights/tests/unit/test_business_metrics_projections.py services/reporting-insights/tests/unit/test_customer_facing_dashboards.py services/decision/tests/unit/test_credit_decision_service.py services/integration/tests/unit/test_webhook_delivery.py tests/test_epic7_observability_exposure_gates.py tests/test_epic6_audit_logs_sensitive_data_gates.py`
- `.venv/bin/python -m ruff check ...`
- `.venv/bin/python -m ruff format --check ...`
- `.venv/bin/python -m pyright`
- `.venv/bin/python -m pytest`

### File List

- `_bmad-output/implementation-artifacts/8-5-observabilidade-e-auditoria-de-consulta-callback.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/observability.md`
- `docs/observability-dashboards.md`
- `packages/observability/src/creditos_observability/gates.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `services/integration/src/creditos_integration/application/ports/webhook_delivery.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/domain/entities/webhook_delivery.py`
- `services/integration/tests/unit/test_webhook_delivery.py`
- `services/reporting-insights/src/creditos_reporting_insights/application/customer_dashboard_service.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py`
- `services/reporting-insights/tests/unit/test_business_metrics_projections.py`
- `services/reporting-insights/tests/unit/test_customer_facing_dashboards.py`

### Change Log

- 2026-10-08: Implementada observabilidade e projeção segura de consulta/callback; story movida para review.
- 2026-10-09: Corrigidos achados do code review; story movida para done.
