---
jira_issue: CTOS-63
branch: agent/story-7-4-business-metrics-projections
baseline_commit: 7fc6774
---

# Story 7.4: Projeções de Métricas de Negócio

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a gestor de negócio ou risco,  
I want projeções de funil, decisões, integrações e custos por tenant/produto,  
so that eu acompanhe operação e performance de crédito sem acessar dados transacionais brutos.

## Acceptance Criteria

1. **Microsserviço `Reporting & Insights` inicial:** dado o monorepo CreditOS, quando a story for implementada, então haverá o serviço `services/reporting-insights` seguindo DDD/arquitetura hexagonal, com domínio, aplicação, ports, adapters in-memory, README e testes, sem API pública/customer-facing ainda.
2. **Projeções por eventos autorizados:** dados eventos minimizados de proposta, decisão, integração, IA consultiva e callbacks, quando `Reporting & Insights` consumir esses sinais, então atualizará projeções de funil, volume, status, decisão, motivo, custo, latência e erro por tenant/produto/canal/classe permitida, sem consultar bancos transacionais de outros serviços.
3. **Idempotência e ordem de eventos:** dados eventos duplicados, replayados ou fora de ordem, quando forem aplicados à mesma projeção, então o serviço deduplicará por `source + id` e/ou `idempotency_key`/identificador canônico, preservará contadores corretos e registrará evento atrasado sem corromper agregados.
4. **Freshness e consistência eventual controlada:** dado que projeções são assíncronas, quando uma projeção for atualizada ou consultada por testes, então ela carregará `last_event_time`, `last_processed_at`, atraso/freshness e status operacional suficiente para validar o SLO interno de freshness planejado para reporting.
5. **Privacidade e minimização:** dado qualquer projeção, snapshot, log ou erro, quando validado em teste, então não persistirá CPF, CNPJ, e-mail, nome, endereço, payload bruto, prompt/output, provider payload, documento, token, segredo, `external_proposal_id` como dimensão de dashboard, ou telemetria bruta de Prometheus/Loki/Tempo.
6. **Isolamento bridge por tenant:** dado um tenant confiável, quando eventos de tenants diferentes forem processados, então projeções e consultas in-memory retornam somente agregados do tenant solicitado e bloqueiam mistura cross-tenant, mantendo `tenant_id` como chave de projeção de negócio, não como label de métrica técnica.
7. **Contratos existentes respeitados:** dado o catálogo atual de contratos, quando eventos de proposta e integração forem consumidos, então o serviço reutilizará os contratos/schemas v1 existentes (`proposal-submitted-event`, `integration-events`, `integration-result-schema`, `integration-cost-schema`) e tratará eventos de decisão/IA/callback como DTOs internos minimizados até contratos governados existirem.
8. **Gates locais sem infraestrutura externa:** dado o CI/local, quando a suíte rodar, então validará projeções, idempotência, freshness, privacidade, isolamento por tenant, documentação e tipagem sem exigir NATS real, banco real, Grafana, Prometheus, Loki, Tempo, rede ou credenciais.

## Tasks / Subtasks

- [x] CTOS-390 — Criar base do `Reporting & Insights Service` (AC: 1, 6, 8)
  - [x] Criar `services/reporting-insights/pyproject.toml`, pacote `creditos_reporting_insights` e estrutura DDD/hexagonal alinhada aos serviços existentes.
  - [x] Atualizar `pyproject.toml` raiz com `services/reporting-insights/src` em `pyright.extraPaths` e `pytest.pythonpath`.
  - [x] Usar dependências workspace já existentes (`creditos-observability`, `creditos-security`) somente se necessárias; não adicionar framework HTTP, banco ou broker nesta story.
- [x] CTOS-391 — Modelar eventos de negócio minimizados e chaves de projeção (AC: 2, 5, 7)
  - [x] Definir value objects/DTOs para proposta, decisão, integração, IA consultiva e callback com `tenant_id`, produto, status, timestamps, idempotência e dimensões permitidas.
  - [x] Reutilizar contratos existentes de proposta/integração como referência obrigatória; não criar contrato público novo para decisão/IA/callback sem ADR/story própria.
  - [x] Bloquear campos sensíveis e objetos abertos usando allowlist/denylist compatível com `creditos_security`.
- [x] CTOS-392 — Implementar agregados/projeções de funil, decisão, integração e custo (AC: 2, 4, 6)
  - [x] Criar entidade ou read model de projeção por tenant/produto/período com contadores de recebidas, validadas, enriquecidas, decididas, aprovadas, recusadas, aprovadas com alterações, inconclusivas e dados adicionais solicitados.
  - [x] Agregar motivos/reason codes somente como códigos governados de baixa cardinalidade; não armazenar explicação textual sensível ou evidência restrita.
  - [x] Agregar custos em unidades inteiras (`estimated_cost_units`, `actual_cost_units`), latência e erro por classe de integração/adapter/provedor opcional log-safe.
- [x] CTOS-393 — Garantir idempotência, replay e eventos fora de ordem (AC: 3, 4)
  - [x] Criar repositório in-memory para projeções e índice de eventos aplicados por tenant, `source`, `id`, `idempotency_key` e identificador canônico quando aplicável.
  - [x] Reprocessar evento duplicado sem alterar contadores; aceitar evento atrasado sem reduzir freshness incorretamente.
  - [x] Registrar metadados seguros de replay/late event sem ecoar payload, documento ou erro bruto.
- [x] CTOS-394 — Adicionar testes de privacidade, tenant e consistência eventual (AC: 3, 4, 5, 6, 8)
  - [x] Cobrir eventos duplicados, fora de ordem, cross-tenant, evento com campo sensível, schema version inválida e status desconhecido.
  - [x] Cobrir consulta por tenant que não retorna dados de outro tenant e não expõe identificadores de proposta/decisão como dimensões de dashboard.
  - [x] Rodar regressões relevantes de observabilidade, mascaramento e contratos quando a implementação tocar esses pacotes.
- [x] CTOS-395 — Atualizar documentação operacional e rastreabilidade BMAD/Jira (AC: 1, 2, 4, 5, 7, 8)
  - [x] Atualizar `services/reporting-insights/README.md` com ownership, eventos consumidos, projeções, freshness, limitações e antiobjetivos.
  - [x] Atualizar `docs/observability.md` e/ou criar documento dedicado para projeções de negócio, separando projeções de telemetria técnica e dashboards customer-facing.
  - [x] Atualizar esta story, `sprint-status.yaml` e Jira conforme avanço real.

### Review Findings

- [x] [Review][Patch] Contratos v1 existentes não são reutilizados nem há `schema_version` validado [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py:111]
- [x] [Review][Patch] Idempotência não é aplicada de forma atômica antes de criar/alterar projeções [services/reporting-insights/src/creditos_reporting_insights/application/service.py:39]
- [x] [Review][Patch] Integração com status `failed` incrementa funil `enriched` indevidamente [services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py:173]
- [x] [Review][Patch] Custo, latência e erro não são agregados por dimensão de integração [services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py:111]
- [x] [Review][Patch] Freshness aceita `processed_at` inseguro e mascara lag negativo como zero [services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py:186]
- [x] [Review][Patch] Enums e status não são validados em runtime antes de aplicar projeção [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py:137]
- [x] [Review][Patch] Reason codes e dimensões de integração aceitam cardinalidade livre sem limite governado [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py:391]
- [x] [Review][Patch] Custos, latência e contadores não têm teto operacional seguro [services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py:383]

## Dev Notes

### Contexto do Epic 7

- Epic 7 entrega observabilidade e dashboards por tenant para operadores e clientes autorizados acompanharem saúde técnica, funil, volumes, custos, integrações, incidentes e métricas curadas por tenant. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 7`]
- Story 7.4 é a primeira entrega do `Reporting & Insights` para observabilidade de negócio; ela prepara projeções curadas, mas não entrega dashboards customer-facing completos, UI, API pública de consulta ou UX final. [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.4`]
- Story 7.5 depende destas projeções para dashboards customer-facing curados por tenant. Story 7.6 deve validar exposição segura, RBAC/scopes, privacidade e gates de observabilidade. [Source: `_bmad-output/planning-artifacts/epics.md#Stories 7.5-7.6`]

### Regras de arquitetura obrigatórias

- O primeiro deploy possui sete microsserviços de domínio, incluindo `Reporting & Insights`; o serviço é dono de projeções, funil, dashboards, métricas de negócio, custos agregados e visão customer-facing curada. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-1`]
- `Reporting & Insights` usa banco de leitura/projeções alimentado por eventos ou pipelines autorizados e não consulta bancos transacionais diretamente. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFR-42`]
- Observabilidade de negócio pertence ao `Reporting & Insights` por eventos/projeções, não por consulta direta a Prometheus, Loki, Tempo, logs crus ou bancos transacionais. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- O modelo multi-tenant inicial é `bridge`; reporting deve filtrar por tenant e autorização, com evolução para read model dedicado por tenant quando volume, contrato ou performance exigirem. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-20`]
- O SLO interno de reporting é freshness de projeções operacionais/customer-facing `p95 <= 5 min` para dados não transacionais. Nesta story, implementar metadados para medir freshness, não SLA contratual. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-22`]
- Integrações externas registram custo estimado e real por operação em unidades inteiras e projetam custo/performance para `Reporting & Insights`. Não assumir moeda, preço comercial ou fornecedor real. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-10`]
- Backend deve seguir DDD/Hexagonal com Python 3.13, `uv`, pytest, Ruff e Pyright; domínio não deve depender de framework, SDK de broker, OpenTelemetry ou detalhes de banco. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]

### Estado atual do código

- Ainda não existe `services/reporting-insights`; esta story deve criar a base real do sétimo microsserviço planejado, usando o mesmo padrão de `services/proposal-intake`, `services/integration`, `services/decision`, `services/automated-review` e `services/audit-evidence`.
- O `pyproject.toml` raiz já usa workspace `services/*`, mas `pyright.extraPaths` e `pytest.pythonpath` listam serviços explicitamente; adicionar `services/reporting-insights/src` para evitar import quebrado no CI.
- `packages/contracts` já versiona contratos de `proposal-submitted-event`, `integration-events`, `integration-result-schema`, `integration-cost-schema`, `integration-dlq-schema` e `integration-retry-schema`.
- `packages/contracts/consumer-expectations/integration-events/v1/README.md` define que `Reporting & Insights` pode agregar volume por tenant, produto, classe de integração, adapter técnico, status e unidades de custo, tratando duplicados por `idempotencykey`/`execution_id`.
- `services/integration` já registra custo canônico por job/execução e projeção minimizada com totais por execução e granularidade por tenant, produto, classe, adapter e status.
- `services/decision` já contém dados de decisão final, reason codes e explicabilidade, mas ainda não há contrato assíncrono governado de evento de decisão publicado em `packages/contracts`.
- `services/automated-review` já registra custo/uso/latência/fallback de IA consultiva, mas métricas customer-facing continuam fora deste serviço e devem vir de projeções curadas.

### O que esta story deve alterar

- Criar `services/reporting-insights/` com `pyproject.toml`, `README.md`, pacote `src/creditos_reporting_insights/` e testes `services/reporting-insights/tests/unit/`.
- Criar domínio e aplicação suficientes para processar eventos minimizados em memória e retornar snapshots de projeção por tenant/produto/período.
- Criar ports e adapters in-memory para projeções e idempotência; não adicionar banco real, migrations, NATS real, API HTTP/gRPC real ou dashboard nesta story.
- Atualizar `pyproject.toml` raiz e `uv.lock` se o workspace exigir lock atualizado após adicionar o serviço.
- Atualizar documentação de observabilidade para registrar que projeções de negócio são read models curados e não telemetria técnica.
- Não modificar contratos existentes de outros serviços sem necessidade; se faltar contrato governado de decisão/IA/callback, modelar DTO interno minimizado e registrar limitação na story/README.

### Requisitos técnicos de implementação

- Projeção mínima esperada: funil por tenant/produto/canal/período; volume por tenant/produto; decisões por outcome/status/reason code; integrações por classe/adapter/provider opcional/status; custo em unidades inteiras; latência/erro agregados quando disponíveis; freshness por projeção.
- Use datas/hora UTC timezone-aware. Rejeite timestamp naive, futuro absurdo, formato inválido ou evento sem tempo de ocorrência/processamento suficiente.
- Chaves de projeção podem incluir `tenant_id`, `tenant_isolation_tier`, `product_type`, `channel`, `period`, `integration_class`, `adapter_id`, `provider_id` opcional e `reason_code`; não incluir `proposal_id`, `decision_id`, `correlation_id`, `request_id`, `trace_id`, documento ou e-mail como dimensão de consulta/dashboard.
- `tenant_id` é permitido no read model de negócio porque a projeção é por tenant; isso não autoriza usar `tenant_id` como label de métrica técnica em `creditos_observability`.
- Aplique idempotência antes de alterar contadores. Se a validação do evento falhar, não atualizar projeção parcialmente.
- Aplique consistência eventual: eventos fora de ordem podem atualizar contadores históricos, mas `last_event_time` deve representar o maior tempo de evento visto e `last_processed_at` deve representar processamento local seguro.
- Não usar floats para custos. Custos são inteiros (`*_cost_units`) e não representam moeda, preço comercial, tarifa final nem faturamento.
- Não emitir logs com payload de evento completo. Logs, se criados, devem usar `build_structured_log` e campos minimizados.

### Project Structure Notes

- Estrutura recomendada:
  - `services/reporting-insights/pyproject.toml`
  - `services/reporting-insights/README.md`
  - `services/reporting-insights/src/creditos_reporting_insights/__init__.py`
  - `services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py`
  - `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py`
  - `services/reporting-insights/src/creditos_reporting_insights/domain/errors.py`
  - `services/reporting-insights/src/creditos_reporting_insights/application/service.py`
  - `services/reporting-insights/src/creditos_reporting_insights/application/ports/business_projection_repository.py`
  - `services/reporting-insights/src/creditos_reporting_insights/adapters/persistence/in_memory_business_projection_repository.py`
  - `services/reporting-insights/tests/unit/test_business_metrics_projections.py`
- Use nomes em inglês para módulos/classes conforme padrão do código; documentação e story permanecem em português com acentuação.
- Evite criar `ops/observability/grafana/dashboards/customer-facing` nesta story; dashboards customer-facing pertencem à Story 7.5.

### Previous Story Intelligence

- Story 7.1 consolidou que métricas técnicas não devem carregar `tenant_id`, IDs por requisição, erro bruto ou valores de alta cardinalidade; mantenha essa separação entre telemetria técnica e projeção de negócio.
- Story 7.2 separou dashboards internos de customer-facing e bloqueou logs/traces crus, payloads, PII e `tenant_id` livre em PromQL. Story 7.4 deve produzir dados curados para a futura Story 7.5, não reutilizar dashboards internos.
- Story 7.3 corrigiu alertas para usar contratos de métricas versionados e adicionou teste para escaping YAML. Ao criar projeções, evite nomes de métricas/eventos “planejados” sem contrato ou teste.
- Reviews recentes cobraram alinhamento aos contratos existentes, validação de labels/dimensões, placeholders explícitos e ausência de segredos; aplique os mesmos princípios às projeções de negócio.

### Latest Tech Information

- CloudEvents exige que produtores garantam unicidade de `source + id` para eventos distintos; use essa combinação como uma das bases de deduplicação, além de `idempotencykey` quando existir. [Source: `https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md`, consultado em 2026-09-28]
- A própria especificação/primer de CloudEvents recomenda não reutilizar `id` para semânticas além de unicidade; não derive métricas de negócio a partir do formato do `id`. [Source: `https://github.com/cloudevents/spec/blob/main/cloudevents/primer.md`, consultado em 2026-09-28]
- NATS JetStream oferece deduplicação de publicação por `Nats-Msg-Id` dentro de uma janela configurável, mas consumidores ainda devem ser idempotentes para replay e falhas após processamento local. [Source: `https://github.com/nats-io/nats.docs/blob/master/using-nats/jetstream/model_deep_dive.md`, consultado em 2026-09-28]
- OpenTelemetry reforça convenções semânticas e preocupação com cardinalidade; projeções de negócio por tenant devem ficar em read models, não como labels técnicas de alta cardinalidade. [Source: `https://opentelemetry.io/docs/concepts/semantic-conventions/`, consultado em 2026-09-28]
- Prometheus recording rules são úteis para pré-computar séries técnicas, mas Story 7.4 não deve usar Prometheus como fonte de verdade de negócio; as projeções devem vir de eventos autorizados. [Source: `https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/`, consultado em 2026-09-28]

### Testing Requirements

- Rodar testes focados do novo serviço, por exemplo: `.venv/bin/pytest services/reporting-insights/tests/unit -q`.
- Rodar regressões de contratos/integração quando consumir schemas atuais: `.venv/bin/pytest packages/contracts tests -q` ou subconjunto aplicável se a suíte ampla for pesada.
- Rodar regressões de segurança/mascaramento quando validar campos sensíveis: `.venv/bin/pytest tests/test_sensitive_data_masking.py packages/security/tests/unit/test_masking.py -q`.
- Rodar gates principais antes de PR: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright` e suíte ampla coerente com arquivos alterados.
- Se a suíte completa local falhar por ambiente (`uv` ausente ou sockets do harness), usar o shim local já documentado em histórias anteriores e registrar a limitação no Dev Agent Record sem mascarar falha funcional.

### Referências

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.4`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-24`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/persistencia-oq5.md`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/integracoes-externas-oq8.md`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-1`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-10`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-20`]
- [Source: `_bmad-output/implementation-artifacts/7-1-instrumentacao-tecnica-base-com-opentelemetry.md`]
- [Source: `_bmad-output/implementation-artifacts/7-2-dashboards-tecnicos-internos.md`]
- [Source: `_bmad-output/implementation-artifacts/7-3-alertas-tecnicos-e-slo-watch.md`]
- [Source: `packages/contracts/consumer-expectations/integration-events/v1/README.md`]
- [Source: `docs/observability.md`]
- [Source: `docs/observability-dashboards.md`]
- [Source: `docs/observability-alerts.md`]
- [Source: `https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md`]
- [Source: `https://github.com/nats-io/nats.docs/blob/master/using-nats/jetstream/model_deep_dive.md`]
- [Source: `https://opentelemetry.io/docs/concepts/semantic-conventions/`]
- [Source: `https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/`]

## Dev Agent Record

### Agent Model Used

Codex CLI — bmad-dev-story

### Debug Log References

- 2026-09-28 — Story 7.4 criada a partir do Epic 7, PRD FR-24/NFR-42, AD-1/AD-7/AD-10/AD-20 e aprendizados das Stories 7.1–7.3.
- 2026-09-28 — `bmad-dev-story` iniciado; `CTOS-63` e `CTOS-390` movidos para `Em andamento`.
- 2026-09-28 — Criada base DDD/hexagonal do `Reporting & Insights Service`, DTOs internos minimizados, agregados in-memory e testes de projeções.
- 2026-09-28 — Validações executadas: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright`, testes focados e suíte completa com shim local de `uv` e permissão para sockets do harness.
- 2026-09-28 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 8 patches aplicados e validados.

### Completion Notes List

- 2026-09-28 — Story detalhada com escopo do `Reporting & Insights`, projeções in-memory, idempotência, freshness, privacidade e limites explícitos para contratos ainda ausentes.
- 2026-09-28 — Jira sincronizado: `CTOS-63` confirmado e subtarefas `CTOS-390` a `CTOS-395` criadas em `Tarefas pendentes`.
- 2026-09-28 — Implementado serviço inicial sem API pública, broker, banco ou dashboards; projeções usam eventos minimizados, idempotência por `source + event_id`/`idempotency_key`, custos inteiros e freshness segura.
- 2026-09-28 — Documentação atualizada para separar projeções de negócio de telemetria técnica e registrar limitações de contratos governados para decisão, IA e callback.
- 2026-09-28 — Revisão corrigida: dependência de contratos v1 declarada, schema version validado, idempotência atômica no adapter in-memory, chaves de dedupe estruturadas, integração `failed` sem impacto em `enriched`, métricas de integração por dimensão, freshness com processamento local seguro e limites operacionais para custo/latência/erro.

### File List

- `_bmad-output/implementation-artifacts/7-4-projecoes-de-metricas-de-negocio.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/observability.md`
- `pyproject.toml`
- `uv.lock`
- `services/reporting-insights/README.md`
- `services/reporting-insights/pyproject.toml`
- `services/reporting-insights/src/creditos_reporting_insights/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/adapters/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/adapters/persistence/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/adapters/persistence/in_memory_business_projection_repository.py`
- `services/reporting-insights/src/creditos_reporting_insights/application/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/application/ports/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/application/ports/business_projection_repository.py`
- `services/reporting-insights/src/creditos_reporting_insights/application/service.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/entities/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/entities/business_metrics_projection.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/errors.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/__init__.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/business_events.py`
- `services/reporting-insights/src/creditos_reporting_insights/domain/value_objects/contract_versions.py`
- `services/reporting-insights/tests/unit/test_business_metrics_projections.py`

### Change Log

- 2026-09-28 — Story 7.4 implementada e movida para `review`.
- 2026-09-28 — Achados de code review aplicados; Story 7.4 movida para `done`.
