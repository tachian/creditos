---
jira_issue: CTOS-65
branch: agent/story-7-6-observability-exposure-gates
baseline_commit: aa0b5d4
---

# Story 7.6: Gates de Observabilidade e Exposição Segura

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a equipe de engenharia e segurança,  
I want validar telemetria, dashboards e projeções antes de produção,  
so that observabilidade seja útil sem vazar dados ou quebrar isolamento por tenant.

## Acceptance Criteria

1. **Telemetria mínima por capability crítica:** dado uma suíte de observabilidade, quando os testes rodam, então validam emissão de logs estruturados, métricas, traces/spans, health/readiness e correlation ID por serviço/capability crítica.
2. **Falha explícita em ausência de sinal obrigatório:** dado uma capability crítica sem telemetria mínima, quando os gates locais rodam, então a suíte falha de forma determinística indicando o sinal ausente.
3. **Privacidade e cardinalidade técnica:** dado logs, métricas, spans, dashboards internos e alertas, quando serializados ou exportados, então não contêm dados pessoais, payloads, prompts/outputs, segredos, IDs livres de proposta/decisão, `tenant_id` como label técnica ou telemetria bruta indevida.
4. **Exposição customer-facing segura:** dado dashboards customer-facing por tenant, quando gates de privacidade e tenancy rodam, então validam RBAC/scopes, isolamento por tenant, minimização, ausência de telemetria bruta e uso exclusivo de projeções curadas do `Reporting & Insights`.
5. **Separação entre observabilidade técnica e business:** dado dashboards internos, alertas e projeções de negócio, quando os gates rodam, então impedem que dashboards customer-facing consumam Prometheus, Loki, Tempo, Grafana, logs crus, traces crus ou bancos transacionais de outros serviços.
6. **Gates locais sem infraestrutura externa:** dado CI/local, quando a suíte roda, então valida artefatos e contratos sem exigir Grafana, Prometheus, Alertmanager, Loki, Tempo, OpenTelemetry Collector, NATS, Docker, rede ou credenciais reais.

## Tasks / Subtasks

- [x] CTOS-403 — Consolidar matriz de sinais observáveis obrigatórios (AC: 1, 2, 6)
  - [x] Criar ou ampliar um manifesto/catálogo local de capabilities críticas com os sinais esperados: `log`, `metric`, `trace/span`, `health`, `readiness` e `correlation_id`.
  - [x] Cobrir pelo menos operações HTTP, gRPC, evento, job e integração, alinhadas a `TelemetryOperationType`.
  - [x] Documentar explicitamente que o gate valida contrato/cobertura local e não disponibilidade real da stack de observabilidade.
- [x] CTOS-404 — Criar gates técnicos de telemetria mínima (AC: 1, 2, 3, 6)
  - [x] Validar que `InMemoryTelemetry.record_operation` emite log, métricas e span para cada tipo de operação sem aceitar payload sensível bruto.
  - [x] Validar propagação segura de `correlation_id`, `request_id`, `trace_id` e tenant apenas quando vier de contexto confiável.
  - [x] Garantir falha atômica quando duração, operação, labels ou atributos críticos forem inválidos.
- [x] CTOS-405 — Validar dashboards internos e alertas técnicos seguros (AC: 3, 5, 6)
  - [x] Reforçar gates de `internal_dashboard_catalog` e `internal_alert_catalog` para escopo interno, labels permitidas, baixa cardinalidade e ausência de logs/traces crus.
  - [x] Validar que exports versionados continuam determinísticos e sem datasources, contact points, URLs, tokens ou credenciais reais.
  - [x] Se houver validação Prometheus/Grafana adicional, mantê-la opcional/local e sem exigir binários externos no CI base.
- [x] CTOS-406 — Validar dashboards customer-facing por tenant (AC: 4, 5, 6)
  - [x] Reusar e ampliar testes de `CustomerDashboardService` para RBAC/scopes, tenant confiável, cross-tenant e minimização.
  - [x] Garantir que a visão customer-facing não contenha PromQL, datasource, logs, traces, payloads, identificadores livres, infraestrutura, preço comercial ou billing.
  - [x] Validar que os cards vêm de snapshots/projeções curadas e não de telemetria técnica bruta.
- [x] CTOS-407 — Criar gate transversal de exposição segura (AC: 3, 4, 5, 6)
  - [x] Serializar artefatos representativos de logs, spans, métricas, health/readiness, dashboards internos, alertas e dashboard customer-facing.
  - [x] Bloquear termos proibidos e valores sensíveis usando padrões já existentes de mascaramento e gates do Epic 6 quando aplicável.
  - [x] Evitar falsos positivos para nomes técnicos seguros já aprovados, mantendo mensagens de falha redigidas sem ecoar valores sensíveis.
- [x] CTOS-408 — Atualizar documentação e rastreabilidade BMAD (AC: 1-6)
  - [x] Atualizar `docs/observability.md`, `docs/observability-dashboards.md` e/ou `docs/observability-alerts.md` com os gates obrigatórios e seus limites.
  - [x] Atualizar `packages/observability/README.md` e `services/reporting-insights/README.md` somente se novos helpers/contratos forem criados.
  - [x] Atualizar esta story, `sprint-status.yaml` e Jira conforme o avanço real.
- [x] CTOS-409 — Rodar validações locais e regressões focadas (AC: 1-6)
  - [x] Rodar Ruff format/check e Pyright nos arquivos alterados.
  - [x] Rodar testes focados de observabilidade, alertas, dashboards internos, customer-facing, mascaramento e gates de dados sensíveis.
  - [x] Registrar comandos e resultados na seção `Dev Agent Record`.

### Review Findings

- [x] [Review][Patch] Corrigir `payload` técnico não-hashable e payload bruto para falhar com `ValueError` redigido [packages/observability/src/creditos_observability/gates.py:236]
- [x] [Review][Patch] Bloquear aliases comuns de segredo, `prompt`/`output` e CPF/CNPJ digit-only nos gates de exposição [packages/observability/src/creditos_observability/gates.py:47]
- [x] [Review][Patch] Exigir tenant esperado, escopo autorizado e fonte curada no gate customer-facing [packages/observability/src/creditos_observability/gates.py:212]
- [x] [Review][Patch] Alinhar denylist customer-facing com billing, preço, moeda e bancos transacionais proibidos pela story [packages/observability/src/creditos_observability/gates.py:91]
- [x] [Review][Patch] Validar explicitamente `exposure` inválido em vez de aplicar política customer-facing por fallback [packages/observability/src/creditos_observability/gates.py:198]
- [x] [Review][Patch] Amarrar health/readiness por serviço e reforçar teste comportamental de emissão real de sinais [packages/observability/src/creditos_observability/gates.py:159]
- [x] [Review][Patch] Limitar varredura a payloads JSON-like com proteção contra ciclos/iteráveis problemáticos e corrigir bytes vazios [packages/observability/src/creditos_observability/gates.py:228]
- [x] [Review][Patch] Reduzir falsos positivos de substring para termos seguros como `tempo_medio` usando matching por tokens [packages/observability/src/creditos_observability/gates.py:264]

## Dev Notes

### Contexto do Epic 7

- Epic 7 entrega observabilidade e dashboards por tenant para operadores e clientes autorizados acompanharem saúde técnica, funil, volumes, custos, integrações, incidentes e métricas curadas por tenant. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 7`]
- Story 7.6 é a última story funcional do Epic 7 antes da retrospectiva; ela deve consolidar gates locais que protegem o que foi criado nas Stories 7.1 a 7.5. [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.6`]
- A implementação deve ser orientada por DDD/Hexagonal e por testes locais determinísticos. Não introduzir infraestrutura real, rede, credenciais ou containers como requisito para passar os gates desta story. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`]

### Estado atual da observabilidade técnica

- `packages/observability` já exporta `InMemoryTelemetry`, `TelemetryOperationType`, `technical_signal_taxonomy`, `build_structured_log`, `health_response`, `readiness_response`, `internal_dashboard_catalog`, `validate_dashboard_catalog`, `internal_alert_catalog` e `validate_alert_catalog`. [Source: `packages/observability/src/creditos_observability/__init__.py`]
- `InMemoryTelemetry.record_operation` é o helper transversal para operações HTTP, gRPC, evento, job e integração, emitindo log estruturado, span e métricas `creditos.requests.total` e `creditos.request.duration` de forma validada. [Source: `packages/observability/src/creditos_observability/telemetry.py`]
- Labels técnicas permitidas são de baixa cardinalidade. `tenant_id`, `correlation_id`, `request_id`, `trace_id`, `proposal_id`, `decision_id`, CPF, CNPJ, e-mail, payload, prompt/output, erro bruto, token e segredo não podem virar labels de métrica. [Source: `docs/observability.md`]
- Headers HTTP externos não são fonte confiável para tenant; gRPC interno e CloudEvents normalizados podem propagar tenant após fronteira confiável. [Source: `packages/observability/src/creditos_observability/context.py`]
- `health_response` e `readiness_response` já minimizam detalhes de dependências; checks sensíveis devem aparecer como `dependency_N`, não nomes internos, credenciais ou endpoints. [Source: `packages/observability/src/creditos_observability/health.py`]

### Estado atual de dashboards e alertas internos

- Dashboards técnicos internos são versionados em `ops/observability/grafana/dashboards/internal/` e gerados/validados pelo catálogo `creditos_observability.dashboards`. [Source: `docs/observability-dashboards.md`]
- Esses dashboards são internos, usam Prometheus planejado como fonte de métricas e não podem expor logs crus, traces crus, payloads, CPF/CNPJ/e-mail, tokens, segredos, IDs livres ou `tenant_id` como label Prometheus. [Source: `docs/observability-dashboards.md`]
- Alertas técnicos internos são versionados em `ops/observability/prometheus/rules/internal/technical-alerts.yaml`, com placeholders seguros em `ops/observability/alertmanager/routing/internal-placeholders.yaml`. [Source: `docs/observability-alerts.md`]
- Alertas não são auditoria oficial nem visão customer-facing; não devem conter contact points reais, webhooks, canais de incidente, endpoints externos ou credenciais. [Source: `docs/observability-alerts.md`]

### Estado atual de business/customer-facing

- `Reporting & Insights` é dono de projeções de negócio e dashboards customer-facing curados por tenant; não deve consultar bancos transacionais de outros serviços. [Source: `services/reporting-insights/README.md`]
- `CustomerDashboardService` monta a visão customer-facing a partir de `BusinessMetricsSnapshot`, validando contexto confiável, escopo mínimo e tentativa cross-tenant. [Source: `services/reporting-insights/src/creditos_reporting_insights/application/customer_dashboard_service.py`]
- A visão customer-facing não é Grafana nesta etapa. Ela é um view model backend com projeções agregadas, autorizado por `dashboard:read` ou `reporting:read`, e não pode conter PromQL, logs, traces, payloads, dados pessoais, infraestrutura, moeda, preço comercial ou billing. [Source: `docs/observability-dashboards.md`]
- `tenant_id` é permitido no read model de negócio porque a consulta é isolada por tenant; isso não autoriza usar `tenant_id` como label técnica ou dimensão livre de telemetria. [Source: `docs/observability.md`]

### Testes e padrões existentes a preservar

- `tests/test_observability_foundation.py` já cobre tenant não confiável em HTTP, contexto gRPC/CloudEvents, `traceparent`, logs estruturados, health/readiness e emissão segura de telemetria em memória.
- `packages/observability/tests/unit/test_telemetry_operations.py` já cobre taxonomia, emissão de log/métrica/span para todos os tipos de operação, atomicidade e bloqueio de alta cardinalidade.
- `packages/observability/tests/unit/test_internal_dashboards.py` e `packages/observability/tests/unit/test_internal_alerts.py` já validam catálogos internos, privacidade/cardinalidade, exports determinísticos e consistência com artefatos versionados.
- `services/reporting-insights/tests/unit/test_customer_facing_dashboards.py` já cobre isolamento por tenant, escopo, minimização, cross-tenant, outputs imutáveis e documentação customer-facing.
- `tests/test_epic6_audit_logs_sensitive_data_gates.py` contém helpers/padrões para gates de vazamento sensível e mensagens redigidas. Reusar padrões quando fizer sentido; não duplicar scanner de forma incompatível.

### O que esta story deve alterar

- Preferir adicionar um teste/gate transversal em `tests/test_epic7_observability_exposure_gates.py` ou ampliar suites existentes quando a cobertura pertencer claramente ao pacote/serviço já existente.
- Se for necessário código novo, manter helpers em `packages/observability/src/creditos_observability/` para gates técnicos genéricos; manter regras customer-facing dentro de `services/reporting-insights`.
- Atualizar documentação apenas para registrar gates e limites; não reabrir decisões de stack, não criar serviços novos e não materializar Collector/Prometheus/Grafana/Alertmanager reais.
- Não mover a fonte customer-facing para Grafana/Prometheus. A Story 7.5 definiu a visão como contrato/backend view model, com UX final diferida para `bmad-ux`.

### O que esta story não deve fazer

- Não implementar API pública, UI, BFF, autenticação real ou provisionamento de infraestrutura.
- Não criar dashboards customer-facing em Grafana.
- Não introduzir dados reais, CPF/CNPJ/e-mail reais, tokens ou credenciais em fixtures, docs ou testes.
- Não transformar freshness operacional em SLA contratual externo.
- Não alterar sem necessidade o contrato de `CustomerDashboardService` ou os catálogos internos já aprovados.

### Pesquisa técnica atualizada

- OpenTelemetry Python documenta traces e métricas como estáveis e logs ainda em desenvolvimento; por isso o contrato de logs estruturados do CreditOS deve continuar próprio e testável localmente, enquanto spans/métricas usam OTel SDK em memória. Source: https://opentelemetry.io/docs/languages/python/
- A especificação de métricas OpenTelemetry estável reforça o uso de instrumentos e atributos consistentes; no CreditOS isso deve continuar com allowlist e baixa cardinalidade. Source: https://opentelemetry.io/docs/specs/otel/metrics/api/
- Grafana recomenda provisionamento/dashboards como código para recursos versionados; para esta story, isso justifica validar JSONs/provisionamento localmente, sem instância Grafana real. Source: https://grafana.com/docs/grafana/latest/administration/provisioning/
- Prometheus suporta `promtool check rules` e `promtool test rules` para validar regras; nesta etapa, qualquer uso deve ser opcional e não substituir os validadores Python determinísticos já existentes. Sources: https://prometheus.io/docs/prometheus/3.7/command-line/promtool/ and https://prometheus.io/docs/prometheus/3.9/configuration/unit_testing_rules/

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- `python3 _bmad/scripts/resolve_customization.py --skill .agents/skills/bmad-dev-story --key workflow`
- `.venv/bin/pytest tests/test_epic7_observability_exposure_gates.py services/reporting-insights/tests/unit/test_customer_facing_dashboards.py::test_customer_dashboard_output_passes_epic7_exposure_gate -q`
- `.venv/bin/ruff format packages/observability/src/creditos_observability/gates.py packages/observability/src/creditos_observability/__init__.py tests/test_epic7_observability_exposure_gates.py services/reporting-insights/tests/unit/test_customer_facing_dashboards.py`
- `.venv/bin/ruff check packages/observability/src/creditos_observability/gates.py packages/observability/src/creditos_observability/__init__.py tests/test_epic7_observability_exposure_gates.py services/reporting-insights/tests/unit/test_customer_facing_dashboards.py`
- `.venv/bin/pyright packages/observability/src/creditos_observability/gates.py packages/observability/src/creditos_observability/__init__.py tests/test_epic7_observability_exposure_gates.py services/reporting-insights/tests/unit/test_customer_facing_dashboards.py`
- `.venv/bin/pytest tests/test_epic7_observability_exposure_gates.py tests/test_observability_foundation.py packages/observability/tests/unit services/reporting-insights/tests/unit/test_customer_facing_dashboards.py services/reporting-insights/tests/unit/test_business_metrics_projections.py tests/test_epic6_audit_logs_sensitive_data_gates.py tests/test_sensitive_data_masking.py -q`
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/pyright`
- `PATH="/tmp/creditos-bin:$PATH" .venv/bin/pytest -q`
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/pyright && PATH="/tmp/creditos-bin:$PATH" .venv/bin/pytest -q`
- `.venv/bin/ruff check packages/observability/src/creditos_observability/gates.py tests/test_epic7_observability_exposure_gates.py && .venv/bin/pyright packages/observability/src/creditos_observability/gates.py tests/test_epic7_observability_exposure_gates.py && .venv/bin/pytest tests/test_epic7_observability_exposure_gates.py -q`
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/pyright && PATH="/tmp/creditos-bin:$PATH" .venv/bin/pytest -q`

### Completion Notes

- Criado o módulo `creditos_observability.gates` com catálogo de capabilities críticas, sinais obrigatórios e validadores locais de exposição segura.
- Adicionados gates para cobertura de operações HTTP, gRPC, evento, job e integração, incluindo log, métrica, trace/span, correlation ID, health e readiness.
- Adicionados testes transversais da Story 7.6 e integração do gate customer-facing ao dashboard real de `Reporting & Insights`.
- Documentados os gates locais em `docs/observability.md`, `docs/observability-dashboards.md` e `packages/observability/README.md`.
- Validações: Ruff format/check dos arquivos alterados passou; Pyright focado e global pelo `pyproject` passou; regressões focadas passaram com `89 passed`; suíte completa passou com `755 passed` usando shim temporário de `uv` em `/tmp` porque `uv` não está no PATH desta sessão.
- Observação: o comando incorreto `.venv/bin/pyright .` analisou `.uv-python` e falhou fora do escopo do projeto; a execução correta `.venv/bin/pyright` passou com `0 errors`.
- Code review BMAD concluído com `0 decision-needed`, `8 patch`, `0 defer` e `0 dismissed`; todos os patches foram aplicados, incluindo endurecimento de payload JSON-like, bloqueio de aliases sensíveis, validação explícita de `exposure`, RBAC/tenant/fonte curada customer-facing e redução de falsos positivos.
- Validações após os patches de review: Ruff format/check global passou; Pyright global passou com `0 errors`; suíte completa passou com `770 passed` usando shim temporário de `uv` em `/tmp`.
- Code review externo do PR #67 tratado: catálogo passou a enumerar os 7 serviços reais do MVP, o gate passou a detectar CPF/CNPJ numéricos e telefones brutos, e a documentação foi alinhada.
- Validações após correções do PR #67: Ruff format/check global passou; Ruff check focado passou; Pyright focado/global passou com `0 errors`; suíte completa passou com `773 passed` usando shim temporário de `uv` em `/tmp`.

### File List

- `docs/observability.md`
- `docs/observability-dashboards.md`
- `packages/observability/README.md`
- `packages/observability/src/creditos_observability/__init__.py`
- `packages/observability/src/creditos_observability/gates.py`
- `services/reporting-insights/tests/unit/test_customer_facing_dashboards.py`
- `tests/test_epic7_observability_exposure_gates.py`
- `_bmad-output/implementation-artifacts/7-6-gates-de-observabilidade-e-exposicao-segura.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-09-29 — Story detalhada, subtarefas Jira criadas e status marcado como `ready-for-dev`.
- 2026-09-29 — Implementados gates de observabilidade/exposição segura, testes e documentação; status movido para `review`.
- 2026-09-29 — Aplicados 8 patches do `bmad-code-review`; validações globais passaram e status movido para `done`.
- 2026-09-29 — Corrigidos 3 pontos do code review externo no PR #67; validações globais passaram com `773 passed`.
