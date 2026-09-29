---
jira_issue: CTOS-64
branch: agent/story-7-5-customer-facing-tenant-dashboards
baseline_commit: 1a50608
---

# Story 7.5: Dashboards Customer-facing Curados por Tenant

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a cliente autorizado,  
I want acompanhar métricas e saúde operacional do meu tenant,  
so that eu entenda o funcionamento das análises sem ver telemetria interna bruta.

## Acceptance Criteria

1. **Visão customer-facing curada por tenant:** dado um contexto autenticado/autorizado de tenant, quando o dashboard for consultado, então a resposta conterá somente projeções agregadas do próprio tenant e nunca dados de outro tenant.
2. **Fonte única em projeções:** dado o escopo customer-facing, quando a visão for montada, então usará snapshots/projeções do `Reporting & Insights` e entradas curadas de impacto operacional, sem consultar Prometheus, Loki, Tempo, logs crus, traces crus ou bancos transacionais de outros serviços.
3. **Cards mínimos de negócio:** dado que existem projeções da Story 7.4, quando o dashboard for gerado, então apresentará funil, decisões, reason codes governados, integrações, callbacks/revisão quando disponível, custos em unidades inteiras, latência agregada, erros e freshness.
4. **Saúde operacional visível ao tenant:** dado que há sinais curados ou placeholders explícitos de impacto, quando o dashboard apresentar saúde operacional, então mostrará status de APIs, callbacks, integrações configuradas, incidentes/degradações relevantes, timeouts e indisponibilidades sem expor CPU, memória, pods, nós, topologia ou nomes internos.
5. **Privacidade e minimização:** dado qualquer saída do dashboard, quando serializada ou testada, então não conterá CPF, CNPJ, e-mail, nome, endereço, documento, payload, provider payload, prompt/output, token, segredo, trace/correlation/request ID, proposal ID, decision ID, evidência restrita, score bruto sensível ou detalhes reversíveis de política.
6. **Autorização por escopo:** dado um solicitante sem escopo/permissão de dashboard, quando tentar consultar a visão, então a operação será negada de forma segura antes de carregar dados; dado solicitante autorizado, então o tenant virá do contexto confiável e não de payload livre.
7. **Limites de UX explícitos:** dado que ainda não rodamos `bmad-ux`, quando a story for concluída, então haverá contrato/modelo de dados e documentação suficientes para uma UI futura, com telas/experiências marcadas como dependentes de refinamento posterior por `bmad-ux`.
8. **Gates locais sem infraestrutura externa:** dado o CI/local, quando a suíte rodar, então validará mapeamento de cards, isolamento por tenant, autorização, privacidade, documentação e tipagem sem exigir Grafana, Prometheus, Loki, Tempo, banco real, NATS real, rede ou credenciais.

## Tasks / Subtasks

- [x] CTOS-396 — Modelar contrato interno do dashboard customer-facing (AC: 1, 2, 3, 5, 7)
  - [x] Criar DTOs/value objects em `services/reporting-insights` para visão customer-facing, seção/card e metadados de freshness.
  - [x] Definir campos permitidos por seção: `tenant_ref` seguro, produto, canal, período, funil, decisão, reason code, integração, callback/revisão, custo, latência, erro e freshness.
  - [x] Bloquear campos livres de alta cardinalidade e identificadores proibidos na própria construção dos DTOs.
- [x] CTOS-397 — Implementar consulta curada por tenant no `Reporting & Insights` (AC: 1, 2, 6, 8)
  - [x] Criar caso de uso/application service para montar dashboard a partir de `BusinessMetricsSnapshot` retornados pelo repositório de projeções.
  - [x] Validar contexto autorizado com tenant confiável e escopo mínimo, sem aceitar `tenant_id` de payload como autoridade.
  - [x] Retornar erro seguro para tenant sem projeção, escopo ausente ou tentativa cross-tenant.
- [x] CTOS-399 — Mapear funil, decisão, integrações, custos e freshness para cards seguros (AC: 3, 5, 8)
  - [x] Converter `funnel_counts`, `decision_counts`, `reason_code_counts`, contadores de integração, custos, latência, erro e freshness para cards determinísticos.
  - [x] Calcular percentuais/razões apenas quando denominadores existirem; evitar divisão por zero e floats sem semântica clara.
  - [x] Preservar custos como unidades inteiras e não apresentar moeda/preço comercial/faturamento.
- [x] CTOS-398 — Modelar saúde operacional e incidentes visíveis ao tenant (AC: 4, 5, 7)
  - [x] Criar estrutura curada para status de APIs, callbacks e integrações configuradas com estados seguros (`operational`, `degraded`, `unavailable`, `unknown`).
  - [x] Representar incidentes/degradações por impacto no tenant/produto/classe, sem nomes de pod, nó, host, stack trace, fornecedor sensível ou topologia interna.
  - [x] Marcar dados ainda não disponíveis como placeholders explícitos com razão segura, sem simular saúde real.
- [x] CTOS-400 — Garantir RBAC, scopes, privacidade e isolamento cross-tenant (AC: 1, 5, 6, 8)
  - [x] Criar testes que provem que tenant A não lê snapshots/cards do tenant B.
  - [x] Criar testes de negação para escopo ausente, tenant não confiável e tentativa de sobrescrever tenant por argumento livre.
  - [x] Criar regressões que serializam a resposta e bloqueiam termos/dados proibidos.
- [x] CTOS-401 — Atualizar documentação operacional e limites de UX (AC: 2, 4, 7, 8)
  - [x] Atualizar `services/reporting-insights/README.md` com visão customer-facing, fontes permitidas, campos proibidos e limites.
  - [x] Atualizar `docs/observability.md` e `docs/observability-dashboards.md` para separar dashboard customer-facing de dashboards internos Grafana.
  - [x] Registrar que a UI final, layout, linguagem visual e jornadas dependem de `bmad-ux`; esta story entrega contrato/back-end view model e artefatos testáveis.
- [x] CTOS-402 — Criar testes e gates de dashboard customer-facing (AC: 1-8)
  - [x] Adicionar testes unitários focados em `services/reporting-insights/tests/unit/`.
  - [x] Rodar gates focados do serviço e regressões de observabilidade/segurança quando aplicável.
  - [x] Atualizar esta story, `sprint-status.yaml` e Jira conforme avanço real.

### Review Findings

- [x] [Review][Patch] Corrigir teste de privacidade falso-negativo que usa `set.isdisjoint` contra string serializada [services/reporting-insights/tests/unit/test_customer_facing_dashboards.py:88]
- [x] [Review][Patch] Validar que todo snapshot retornado pelo repositório pertence ao tenant confiável do contexto [services/reporting-insights/src/creditos_reporting_insights/application/customer_dashboard_service.py:51]
- [x] [Review][Patch] Bloquear termos de score bruto e evidências restritas na saída customer-facing [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard.py:14]
- [x] [Review][Patch] Congelar profundamente ou copiar/revalidar cards para impedir mutação pós-validação [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard.py:133]
- [x] [Review][Patch] Endurecer textos de incidentes/impactos contra URLs, endpoints e identificadores operacionais sensíveis [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard.py:69]
- [x] [Review][Patch] Mesclar múltiplos impactos operacionais por componente com severidade determinística [services/reporting-insights/src/creditos_reporting_insights/application/customer_dashboard_service.py:241]
- [x] [Review][Patch] Validar timestamps de incidentes com timezone e ordem temporal segura [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard.py:66]
- [x] [Review][Patch] Negar scopes malformados sem `TypeError` ou falha insegura [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard_access.py:24]
- [x] [Review][Patch] Preservar ausência de amostras de latência de integração como `None`, não `0 ms` [services/reporting-insights/src/creditos_reporting_insights/application/customer_dashboard_service.py:180]
- [x] [Review][Patch] Adicionar gate local que valida documentação customer-facing obrigatória [services/reporting-insights/tests/unit/test_customer_facing_dashboards.py:47]

## Dev Notes

### Contexto do Epic 7

- Epic 7 entrega observabilidade e dashboards por tenant para operadores e clientes autorizados acompanharem saúde técnica, funil, volumes, custos, integrações, incidentes e métricas curadas por tenant. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 7`]
- Story 7.4 criou o serviço `Reporting & Insights`, projeções in-memory e snapshots de funil, decisão, integrações, custos, latência, erros e freshness. Story 7.5 deve consumir essa base, não recriar projeções. [Source: `_bmad-output/implementation-artifacts/7-4-projecoes-de-metricas-de-negocio.md`]
- Story 7.6 virá depois para gates amplos de observabilidade e exposição segura; esta story deve entregar a visão customer-facing curada e seus testes locais, não todos os gates finais do Epic 7. [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.6`]

### Regras de arquitetura obrigatórias

- `Reporting & Insights` é dono de funil, agregados, dashboards e visão customer-facing curada; projeções não são fonte de verdade transacional. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-1`]
- Observabilidade de negócio pertence ao `Reporting & Insights` por eventos/projeções, não por consulta direta a Prometheus, Loki, Tempo, logs crus ou bancos transacionais. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- Dashboards customer-facing usam apenas projeções curadas, RBAC/scopes, isolamento por tenant, minimização e retenção definida. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- O modelo multi-tenant do MVP é `bridge`: reporting e dashboards customer-facing devem ser filtrados por tenant e autorização, com evolução para read model dedicado quando volume, contrato ou performance exigirem. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-20`]
- O SLO interno de reporting é freshness de projeções operacionais/customer-facing `p95 <= 5 min` para dados não transacionais; não transformar isso em SLA contratual externo. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-22`]
- Backend deve seguir DDD/Hexagonal com Python 3.13, `uv`, pytest, Ruff e Pyright; domínio não deve depender de framework, SDK de broker, OpenTelemetry, Grafana ou banco real. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]

### Requisitos de produto e NFRs relevantes

- FR-24 exige dashboards de negócio para usuários internos autorizados e clientes autorizados acompanharem funil, volume por tenant, performance de decisão, políticas, motivos, inconclusivas, revisão automatizada, risco/fraude, saúde operacional do tenant e custo por `Reporting & Insights`. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-24`]
- NFR-31 exige que dashboards customer-facing derivem de projeções curadas por tenant e não exponham métricas brutas de infraestrutura, traces crus, logs, payloads, segredos, dados pessoais ou detalhes de outros tenants. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFR-31`]
- NFR-12 a NFR-18 exigem contexto/isolamento por tenant em dados, cache, eventos, filas, relatórios, jobs, notificações, integrações e caminho `bridge` para `silo`. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#Multi-tenancy`]
- Observabilidade customer-facing deve expor apenas visão curada, segura e isolada por tenant. Conteúdo permitido inclui status de APIs/callbacks/integrações, incidentes que afetam o tenant, funil, latência, erro, timeouts, custo e motivos agregados; conteúdo proibido inclui infraestrutura, telemetria bruta, payloads, credenciais, scores brutos restritos, evidências sensíveis e dados de outros tenants. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]

### Estado atual do código

- `services/reporting-insights` já existe com estrutura DDD/hexagonal, `ReportingInsightsService`, porta `BusinessProjectionRepository`, adapter in-memory e testes de projeção. [Source: `services/reporting-insights/src/creditos_reporting_insights/application/service.py`]
- `BusinessMetricsSnapshot` contém `ProjectionKey`, contadores de funil, decisão, reason codes, integração, custos, latência, erro, eventos atrasados e freshness. [Source: `services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py`]
- `BusinessEvent` já valida schema version, source CloudEvents permitido, reason codes governados, custos/latência/erro com teto e deduplicação por `source + event_id` e `tenant + event_type + schema_version + idempotency_key`. [Source: `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py`]
- `ReportingInsightsService.list_tenant_snapshots` já lista snapshots por tenant, mas ainda não aplica autorização por escopo nem transforma snapshots em visão customer-facing. [Source: `services/reporting-insights/src/creditos_reporting_insights/application/service.py`]
- `packages/observability.dashboards` atualmente é voltado a dashboards técnicos internos com Grafana/Prometheus e validação que bloqueia `tenant_id`, logs/traces crus, payloads e termos sensíveis. Não usar esse catálogo interno como fonte customer-facing. [Source: `packages/observability/src/creditos_observability/dashboards.py`]
- `ops/observability/grafana/dashboards/internal/` e `docs/observability-dashboards.md` são artefatos internos. Story 7.5 deve documentar separação e, se criar artefatos de dashboard, eles devem representar view models/projeções customer-facing, não PromQL direto. [Source: `docs/observability-dashboards.md`]

### O que esta story deve alterar

- Adicionar módulos em `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/` ou `domain/entities/` para modelo de dashboard customer-facing, com nomes em inglês e documentação em português.
- Estender `services/reporting-insights/src/creditos_reporting_insights/application/service.py` ou criar application service dedicado para montar `TenantDashboardSnapshot`/visão equivalente a partir de snapshots existentes.
- Adicionar uma representação de contexto autorizado, por exemplo `CustomerDashboardAccessContext`, contendo `tenant_id` confiável, scopes/roles permitidos, `tenant_isolation_tier` quando útil e sem payload livre.
- Criar estruturas de saúde/incidente curadas, inicialmente in-memory/DTO, com placeholders explícitos para sinais ainda não materializados.
- Atualizar testes em `services/reporting-insights/tests/unit/` cobrindo privacidade, autorização, cross-tenant, mapeamento de cards e ausência de telemetria bruta.
- Atualizar `services/reporting-insights/README.md`, `docs/observability.md` e `docs/observability-dashboards.md`.
- Não criar API HTTP/gRPC pública real se não houver contrato aprovado nesta story; a saída deve ser application-level/view model testável para futura exposição.
- Não criar UI final, design visual, layout responsivo, navegação, telas definitivas ou componentes front-end; registrar dependência de `bmad-ux`.

### Requisitos técnicos de implementação

- Toda consulta deve derivar tenant do contexto confiável; se algum método receber `tenant_id` como filtro, ele deve ser confrontado com o contexto e rejeitar mismatch.
- Scopes sugeridos para MVP: `reporting:read` ou `dashboard:read`; se usar ambos, documentar a regra exata e manter testes. Não inventar RBAC complexo sem necessidade.
- Saída deve ser determinística, serializável e estável para testes. Preferir dataclasses/value objects imutáveis com `to_dict()` seguro.
- Cards de funil devem preservar nomes canônicos de `ProposalFunnelStatus`; se calcular taxa, usar denominador explícito e retornar `None`/ausente quando não houver base.
- Cards de decisão devem usar `DecisionOutcome` e reason codes governados, sem textos explicativos livres ou evidências restritas.
- Cards de integração devem expor classe, adapter/provedor apenas como identificadores técnicos já validados e log-safe; se houver dúvida sobre `provider_id`, preferir classe/status/custo agregado.
- Custo continua em `cost_units` inteiros; não apresentar moeda, preço comercial, tarifa final, fatura ou billing.
- Saúde operacional customer-facing deve ser uma camada curada: estados e impacto, nunca métricas de CPU/memória/pod/nó ou queries PromQL.
- Incidentes/degradações devem ser modelados como impacto por tenant/produto/classe/serviço público lógico, com severidade segura e intervalo; não expor stack trace, erro bruto, trace ID ou topologia.
- Logs gerados pela consulta, se necessários, devem usar `build_structured_log` com metadados mínimos e sem serializar dashboard completo.

### Project Structure Notes

- Estrutura recomendada:
  - `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard.py`
  - `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard_access.py`
  - `services/reporting-insights/src/creditos_reporting_insights/application/customer_dashboard_service.py` ou extensão controlada de `application/service.py`
  - `services/reporting-insights/tests/unit/test_customer_facing_dashboards.py`
- Se houver helpers comuns para validação de texto/campos sensíveis em `business_events.py`, reutilize-os ou extraia cuidadosamente sem quebrar a Story 7.4.
- Não colocar regras de dashboard customer-facing em `packages/observability` se elas dependerem de domínio/projeções; esse pacote é técnico/transversal.
- Se for criado artefato JSON de dashboard, ele deve estar claramente em pasta customer-facing/projections e não conter PromQL, datasource real, endpoint real, token, senha ou URL.

### Previous Story Intelligence

- Story 7.4 entregou `Reporting & Insights` sem API pública, broker, banco ou dashboards. Story 7.5 deve evoluir a visão de leitura sobre a base existente, não trocar a persistência nem adicionar infraestrutura real.
- Code Review da 7.4 corrigiu quatro riscos diretamente relevantes: idempotência por tipo/schema, sources CloudEvents v1 canônicos, reason codes sensíveis/não governados e `enriched` contado apenas por evento de proposta. Não reintroduzir reason codes livres nem inferir funil a partir de integrações.
- Story 7.2 estabeleceu dashboards internos em Grafana/Prometheus como código e explicitou que customer-facing deve consumir projeções curadas, nunca aqueles dashboards internos.
- Story 7.3 estabeleceu alertas técnicos internos e SLO watch; incidentes visíveis ao cliente nesta story devem ser derivados/curados, não cópia de alertas internos crus.
- Retrospectiva do Epic 6 deixou action item aberto para checklist de privacidade e tenancy para dashboards/alertas; esta story deve materializar testes de privacidade/tenancy para a visão customer-facing.

### Latest Tech Information

- Grafana dashboards são objetos JSON com metadata, variáveis, painéis e configurações; isso reforça que qualquer artefato versionado deve ser determinístico e validável localmente. [Source: `https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/view-dashboard-json-model/`, consultado em 2026-09-29]
- A documentação atual do Grafana diferencia modelos JSON Classic, V1 Resource e V2 Resource; como esta story não deve depender de instância Grafana nem expor Prometheus ao cliente, prefira contrato/view model de `Reporting & Insights` a dashboard Grafana real customer-facing. [Source: `https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/view-dashboard-json-model/`, consultado em 2026-09-29]
- Provisionamento Grafana por arquivos versionados é útil para dashboards internos, mas customer-facing deve ser derivado de projeções autorizadas; se algum JSON for criado, não deve conter datasource real, credenciais, URLs ou queries de telemetria bruta. [Source: `https://grafana.com/docs/grafana/latest/administration/provisioning/`, consultado em 2026-09-29]

### Testing Requirements

- Teste focado esperado: `.venv/bin/pytest services/reporting-insights/tests/unit -q`.
- Regressões recomendadas: `.venv/bin/pytest packages/observability/tests/unit/test_internal_dashboards.py tests/test_sensitive_data_masking.py packages/security/tests/unit/test_masking.py -q` se tocar validações de dashboard/privacidade.
- Gates principais antes de PR: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright`.
- Se a suíte completa local falhar por ambiente (`uv` ausente ou sockets do harness), usar o shim local já validado em stories anteriores e registrar a limitação no Dev Agent Record sem mascarar falha funcional.
- Testes obrigatórios desta story devem serializar a resposta customer-facing e procurar termos proibidos: `cpf`, `cnpj`, `email`, `payload`, `provider_payload`, `token`, `secret`, `trace_id`, `correlation_id`, `request_id`, `proposal_id`, `decision_id`, `raw_log`, `raw_trace`, `prometheus`, `loki`, `tempo`.

### Referências

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.5`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-24`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFR-31`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-20`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-22`]
- [Source: `_bmad-output/implementation-artifacts/7-2-dashboards-tecnicos-internos.md`]
- [Source: `_bmad-output/implementation-artifacts/7-3-alertas-tecnicos-e-slo-watch.md`]
- [Source: `_bmad-output/implementation-artifacts/7-4-projecoes-de-metricas-de-negocio.md`]
- [Source: `services/reporting-insights/src/creditos_reporting_insights/application/service.py`]
- [Source: `services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py`]
- [Source: `docs/observability.md`]
- [Source: `docs/observability-dashboards.md`]
- [Source: `https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/view-dashboard-json-model/`]
- [Source: `https://grafana.com/docs/grafana/latest/administration/provisioning/`]

## Dev Agent Record

### Agent Model Used

Codex CLI — bmad-dev-story

### Debug Log References

- 2026-09-29 — Story 7.5 criada a partir do Epic 7, PRD FR-24/NFR-31, AD-7/AD-20/AD-22 e aprendizados das Stories 7.2–7.4.
- 2026-09-29 — Jira confirmado: `CTOS-64`; subtarefas `CTOS-396` a `CTOS-402` criadas em `Tarefas pendentes`.
- 2026-09-29 — Branch `agent/story-7-5-customer-facing-tenant-dashboards` criada no início da implementação; `CTOS-64` e `CTOS-396` movidos para `Em andamento`.
- 2026-09-29 — Teste vermelho inicial confirmado por módulo ausente: `.venv/bin/pytest services/reporting-insights/tests/unit/test_customer_facing_dashboards.py -q`.
- 2026-09-29 — Gates finais: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright`, `.venv/bin/pytest services/reporting-insights/tests/unit -q`, regressões de observabilidade/mascaramento e suíte completa com shim/sockets (`739 passed`).
- 2026-09-29 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 10 patches aplicados, sem decisões pendentes.
- 2026-09-29 — Gates pós-review: `.venv/bin/ruff format .`, `.venv/bin/ruff check .`, `.venv/bin/pyright`, `.venv/bin/pytest services/reporting-insights/tests/unit -q`, regressões de observabilidade/mascaramento e suíte completa com shim/sockets (`750 passed`).

### Completion Notes List

- 2026-09-29 — Story detalhada para entregar contrato/view model customer-facing curado por tenant, sem UI final e sem Prometheus/Loki/Tempo/logs/traces crus.
- 2026-09-29 — Escopo preserva `Reporting & Insights` como fonte de dashboards customer-facing e registra dependência futura de `bmad-ux`.
- 2026-09-29 — Implementado contrato customer-facing serializável com validação de privacidade, cards determinísticos, freshness e saúde operacional curada.
- 2026-09-29 — Implementado `CustomerDashboardService` com autorização por escopo, tenant confiável vindo do contexto, rejeição de override/cross-tenant e fonte única nas projeções do `Reporting & Insights`.
- 2026-09-29 — Documentação atualizada para separar dashboards internos Grafana da visão customer-facing e registrar limites de UX para etapa futura com `bmad-ux`.
- 2026-09-29 — Patches do code review aplicados: deep-freeze de cards, validação cross-tenant defensiva, denylist ampliada, incidentes com timestamps seguros, merge determinístico de impactos, scopes malformados negados com erro de domínio, latência ausente preservada como `None` e gate documental adicionado.

### File List

- `_bmad-output/implementation-artifacts/7-5-dashboards-customer-facing-curados-por-tenant.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/observability-dashboards.md`
- `docs/observability.md`
- `services/reporting-insights/README.md`
- `services/reporting-insights/src/creditos_reporting_insights/application/customer_dashboard_service.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/errors.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/customer_dashboard_access.py`
- `services/reporting-insights/tests/unit/test_customer_facing_dashboards.py`

### Change Log

- 2026-09-29 — Story 7.5 criada e marcada como `ready-for-dev`.
- 2026-09-29 — Story 7.5 implementada e marcada como `review`.
- 2026-09-29 — Achados do `bmad-code-review` aplicados e story marcada como `done`.
