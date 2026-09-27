---
baseline_commit: 62af49d
jira_issue: CTOS-61
branch: agent/story-7-2-internal-technical-dashboards
---

# Story 7.2: Dashboards Técnicos Internos

Status: done

## Story

As a operador da plataforma,  
I want dashboards técnicos internos para serviços, APIs, NATS, bancos, integrações, segurança e deploys,  
so that incidentes sejam detectados e diagnosticados rapidamente.

## Acceptance Criteria

1. **Dashboards internos versionados:** dado o repositório do CreditOS, quando a story for implementada, então haverá especificações versionadas de dashboards técnicos internos em diretório operacional dedicado, com metadados de título, UID, tags, variáveis, painéis, queries e classificação `internal`.
2. **Saúde técnica por serviço:** dado um operador autorizado, quando acessar a visão de serviços, então verá erro, latência p95/p99, throughput, CPU, memória, saturação, health/readiness e versão/deploy por serviço e ambiente.
3. **APIs e gRPC:** dado tráfego HTTP/gRPC instrumentado, quando dashboards forem renderizados, então haverá painéis para taxa de requisições, taxa de erro, latência por operação/método, status, deadline/timeout quando aplicável e propagação de contexto.
4. **Mensageria e DLQ:** dado fluxos assíncronos do MVP, quando dashboards forem consultados, então haverá visão planejada para NATS JetStream, backlog, lag, retries, DLQ, replay/reprocessamento e idade de mensagens, sem exigir NATS real em teste local.
5. **Integrações, auditoria e segurança:** dado falhas de integração, auditoria ou segurança, quando dashboards forem consultados, então permitirão isolar por classe técnica, adapter/provedor configurado, produto, serviço e tenant somente quando a dimensão for explicitamente permitida, sem expor dados sensíveis identificáveis.
6. **Deploys e regressão operacional:** dado release/deploy emitido pela pipeline futuramente, quando dashboards forem consultados, então haverá painéis ou placeholders versionados para versão, commit/digest, erro pós-deploy, latência pós-deploy e comparação antes/depois.
7. **Privacidade e cardinalidade:** dado qualquer dashboard, variável ou query, quando validado em teste, então não referenciará payloads, logs crus, traces crus, CPF/CNPJ/e-mail, tokens, segredos, `proposal_id`, `decision_id`, `correlation_id`, `request_id` ou `tenant_id` como label livre sem allowlist explícita.
8. **Sem dependência de stack externa no CI:** dado o ambiente local/CI, quando a suíte rodar, então validará a estrutura, catálogo, queries e regras de segurança sem exigir Grafana, Prometheus, Loki, Tempo, NATS, Docker, rede ou credenciais.
9. **Documentação operacional atualizada:** dado o fim da story, quando documentação for revisada, então `docs/observability.md` e/ou documento operacional de dashboards explicarão os dashboards internos, fontes de dados previstas, limites de exposição e o que fica diferido para alertas, projeções de negócio e dashboards customer-facing.

## Tasks / Subtasks

- [x] CTOS-378 — Criar catálogo de dashboards internos como código (AC: 1, 8)
  - [x] Definir estrutura em `ops/observability/grafana/` para provisionamento futuro, com dashboards separados de data sources.
  - [x] Criar catálogo testável no pacote `creditos_observability`, sem dependência de Grafana runtime.
  - [x] Classificar cada dashboard como `internal` e impedir reutilização direta em customer-facing.
- [x] CTOS-379 — Definir dashboards e painéis técnicos mínimos (AC: 2, 3, 4, 5, 6)
  - [x] Incluir dashboards para plataforma/serviços, API pública, gRPC interno, NATS/DLQ, integrações externas, auditoria/segurança e deploys.
  - [x] Para cada dashboard, definir painéis, queries PromQL seguras, variáveis permitidas e fonte de dados esperada.
  - [x] Usar placeholders explícitos para métricas ainda não materializadas, sem fingir que a métrica existe em produção.
- [x] CTOS-380 — Implementar validação de privacidade/cardinalidade dos dashboards (AC: 5, 7, 8)
  - [x] Validar queries, variáveis, tags, títulos e descrições contra denylist de dados sensíveis e identificadores de alta cardinalidade.
  - [x] Bloquear uso de `tenant_id` como label livre; permitir apenas dimensão tenant quando houver decisão/configuração explícita e documentada.
  - [x] Garantir que dashboards internos não consultem payloads, logs crus ou traces crus como fonte primária.
- [x] CTOS-381 — Exportar artefatos Grafana compatíveis e determinísticos (AC: 1, 8)
  - [x] Gerar JSON estável para dashboards internos ou manter fixtures JSON versionadas derivadas do catálogo.
  - [x] Garantir `uid` determinístico, `id` nulo/ausente, tags consistentes, `editable=false` e time range/refresh seguros.
  - [x] Validar grid/painéis/variáveis sem depender de instância Grafana.
- [x] CTOS-382 — Atualizar documentação operacional e rastreabilidade BMAD/Jira (AC: 9)
  - [x] Atualizar `docs/observability.md` ou criar `docs/observability-dashboards.md` com inventário dos dashboards internos.
  - [x] Documentar explicitamente diferenças entre dashboards internos, alertas, projeções de negócio e customer-facing.
  - [x] Atualizar esta story com decisões locais, arquivos alterados, validações e limitações ambientais.
- [x] CTOS-383 — Executar gates de qualidade focados (AC: 7, 8, 9)
  - [x] Rodar testes focados de dashboards/observabilidade e regressões de mascaramento/Epic 6.
  - [x] Rodar Ruff format/check e Pyright.
  - [x] Rodar suíte ampla coerente com arquivos alterados antes de PR.

### Review Findings

- [x] [Review][Patch] Validar labels PromQL fora de matchers e queries `label_values()` para impedir bypass de labels sensíveis/de alta cardinalidade [`packages/observability/src/creditos_observability/dashboards.py:508`]
- [x] [Review][Patch] Completar percentis p95/p99 e p50/p95/p99 prometidos pelos painéis de latência [`packages/observability/src/creditos_observability/dashboards.py:171`]
- [x] [Review][Patch] Separar CPU, memória e saturação em painéis/queries explícitos ou renomear escopo técnico [`packages/observability/src/creditos_observability/dashboards.py:171`]
- [x] [Review][Patch] Adicionar cobertura versionada para commit/digest no dashboard de deploy/release [`packages/observability/src/creditos_observability/dashboards.py:171`]
- [x] [Review][Patch] Permitir isolamento por serviço no dashboard de integrações externas [`packages/observability/src/creditos_observability/dashboards.py:171`]
- [x] [Review][Patch] Definir variável `tenant_isolation_tier` usada pelo painel cross-tenant de auditoria/segurança [`packages/observability/src/creditos_observability/dashboards.py:171`]
- [x] [Review][Patch] Validar limites de `refresh`, `time_from`, tipos booleanos e tipos de visualização no catálogo [`packages/observability/src/creditos_observability/dashboards.py:508`]
- [x] [Review][Patch] Tornar placeholders explícitos no JSON Grafana exportado [`packages/observability/src/creditos_observability/dashboards.py:538`]
- [x] [Review][Patch] Alinhar/documentar nomes PromQL esperados e labels de resource OTel promovidas pelo Collector [`docs/observability-dashboards.md:35`]
- [x] [Review][Patch] Ajustar legendas Grafana por painel para evitar séries vazias/enganosas [`packages/observability/src/creditos_observability/dashboards.py:538`]

## Dev Notes

### Contexto do Epic 7

- Epic 7 cobre observabilidade e dashboards por tenant para operadores e clientes autorizados acompanharem saúde técnica, funil, volumes, custos, integrações, incidentes e métricas curadas por tenant. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 7`]
- Story 7.2 é interna e técnica. Ela não implementa dashboards customer-facing, projeções de negócio nem alertas/SLO watch; esses itens pertencem às Stories 7.3, 7.4, 7.5 e 7.6. [Source: `_bmad-output/planning-artifacts/epics.md#Stories 7.2-7.6`]
- OQ-9 define a stack de referência do MVP: OpenTelemetry Collector, Prometheus, Grafana, Loki, Tempo e Alertmanager. Esta story deve versionar dashboards internos e validações, mas não precisa subir a stack real. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]

### Arquitetura e Guardrails

- AD-7 exige OpenTelemetry como padrão, Collector como ponto de coleta/redaction e stack Grafana OSS como referência; observabilidade de negócio pertence ao `Reporting & Insights` por eventos/projeções, não por consulta direta a Prometheus/Loki/Tempo. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- AD-5 exige propagação de tenant em logs, métricas, traces, jobs, filas e dashboards, mas o `tenant_id` confiável vem de autenticação/contexto, nunca do body sem validação. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-5`]
- AD-16 mantém Python 3.13, `uv`, pytest, Ruff, Pyright e DDD/Hexagonal; qualquer helper de dashboard deve ficar em pacote técnico/adapters, nunca em `domain`. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- AD-20 exige modelo `bridge` no MVP e dashboards filtrados por tenant/autorização. Não criar `pooled` puro para dados sensíveis nem expor dados cross-tenant. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-20`]
- NFR-28 a NFR-31 exigem logs, métricas, traces, health/readiness, correlation ID, observabilidade com minimização/isolamento e dashboards customer-facing derivados de projeções curadas. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFRs`]

### Estado Atual do Código

- `packages/observability/src/creditos_observability/telemetry.py` já possui `InMemoryTelemetry.record_operation`, `record_request`, `record_ai_usage` e `technical_signal_taxonomy()`.
- `technical_signal_taxonomy()` classifica `operation.log`, `operation.duration`, `operation.trace` e `customer-facing.dashboard`, mas ainda não possui catálogo de dashboards técnicos internos.
- `docs/observability.md` já documenta campos mínimos, OpenTelemetry, labels permitidas/proibidas, limites de logs/traces/métricas e separação entre observabilidade interna e customer-facing.
- Não existe diretório `ops/observability/`, `grafana/`, `prometheus/` ou dashboard JSON versionado no repositório.
- Testes atuais de observabilidade estão em `packages/observability/tests/unit/test_telemetry_operations.py` e `tests/test_observability_foundation.py`.

### O Que Esta Story Deve Alterar

- Criar uma representação de dashboards internos que seja testável sem backend externo. Caminho sugerido: `packages/observability/src/creditos_observability/dashboards.py`.
- Criar exportação/fixtures versionadas de dashboards Grafana internos. Caminho sugerido: `ops/observability/grafana/dashboards/internal/*.json`.
- Criar testes unitários para o catálogo e para a exportação/validação. Caminho sugerido: `packages/observability/tests/unit/test_internal_dashboards.py`.
- Atualizar `packages/observability/src/creditos_observability/__init__.py` apenas se uma API pública de dashboard for criada.
- Atualizar documentação operacional em `docs/observability.md` ou novo arquivo dedicado.
- Atualizar `sprint-status.yaml` e esta story ao longo da implementação.

### O Que Esta Story Não Deve Fazer

- Não subir Grafana, Prometheus, Loki, Tempo, Alertmanager, Collector, NATS ou Docker.
- Não criar dashboards customer-facing.
- Não criar `Reporting & Insights`.
- Não criar alertas, regras de Alertmanager ou SLO watch operacional; isso pertence à Story 7.3.
- Não introduzir `tenant_id`, `proposal_id`, `decision_id`, `correlation_id` ou `request_id` como labels livres de Prometheus.
- Não consultar logs crus ou traces crus como fonte primária de dashboard.
- Não alterar domínio de microsserviços para satisfazer dashboards.

### Catálogo Mínimo de Dashboards Internos

1. **Platform Overview**
   - Objetivo: saúde geral da plataforma.
   - Painéis esperados: disponibilidade, taxa de erro, p95/p99, throughput, saturação por serviço, readiness/health, versão/deploy.
   - Variáveis seguras: `environment`, `service`, `tenant_isolation_tier`.
2. **Public API**
   - Objetivo: operação das APIs públicas.
   - Painéis esperados: requisições por operação/status, latência p50/p95/p99, erros 4xx/5xx, rate limiting e idempotência.
   - Variáveis seguras: `environment`, `service`, `operation`, `status`, `channel`, `product_type`.
3. **Internal gRPC**
   - Objetivo: chamadas internas.
   - Painéis esperados: latência por método/operação, erro por método, deadline/timeout, retries/circuit breaker quando métricas existirem, propagação de contexto.
   - Variáveis seguras: `environment`, `service`, `operation`, `status`.
4. **NATS JetStream and DLQ**
   - Objetivo: fluxos assíncronos.
   - Painéis esperados: backlog, lag, retries, DLQ, replay/reprocessamento e idade de mensagens.
   - Observação: métricas podem ser placeholders até materialização da infraestrutura; não simular produção.
5. **External Integrations**
   - Objetivo: integração externa e custos técnicos.
   - Painéis esperados: falhas por classe, adapter/provedor configurado, timeout, retry, fallback, custo estimado/real quando métrica existir.
   - Variáveis seguras: `environment`, `service`, `integration_class`, `destination`, `product_type`, `status`.
6. **Audit and Security**
   - Objetivo: segurança operacional e falhas críticas.
   - Painéis esperados: autorização negada, tentativa cross-tenant, falha de auditoria crítica, vazamento potencial detectado por gates.
   - Observação: não transformar dashboard em fonte de verdade da auditoria oficial.
7. **Deploys and Release Health**
   - Objetivo: regressão pós-deploy.
   - Painéis esperados: versão, commit/digest quando eventos existirem, erro/latência antes/depois e serviço afetado.
   - Observação: release record real vem de CI/CD/AD-23 em evolução posterior.

### Query e Cardinalidade

- Preferir queries PromQL baseadas em métricas já existentes ou planejadas explicitamente:
  - `creditos.requests.total`;
  - `creditos.request.duration`;
  - `creditos.ai.*` quando aplicável;
  - métricas futuras de health/readiness, NATS, deploy e segurança somente como placeholder marcado.
- Para percentis, usar histograma/quantile no Prometheus de forma agregável; não exigir summaries client-side no MVP.
- Painéis devem usar labels de baixa cardinalidade: `environment`, `service`, `operation`, `operation_type`, `status`, `source`, `destination`, `contract`, `contract_version`, `channel`, `product_type`, `tenant_isolation_tier`, `integration_class` quando allowlisted.
- `tenant_id` só pode aparecer se houver decisão explícita de cardinalidade e isolamento; por padrão, dashboards técnicos internos devem usar `tenant_isolation_tier` ou projeções agregadas futuras.
- Variáveis de Grafana devem ter escopo seguro; não permitir textbox livre para compor query PromQL com labels sensíveis.

### Informação Técnica Atualizada

- Grafana representa dashboards como JSON com metadados, painéis, variáveis e settings; painéis têm `gridPos` em grade de 24 colunas, e variáveis ficam em `templating`. [Source: `https://grafana.com/docs/grafana-cloud/learn-and-build/visualizations/dashboards/build-dashboards/view-dashboard-json-model/`, consultado em 2026-09-23]
- Grafana suporta provisioning por configuração versionada; providers apontam para diretórios de dashboards e Grafana pode detectar mudanças em arquivos provisionados. [Source: `https://grafana.com/tutorials/provision-dashboards-and-data-sources/`, consultado em 2026-09-23]
- Prometheus recomenda histograms para quantis agregáveis no servidor via `histogram_quantile()`; native histograms são preferíveis quando disponíveis, mas classic histograms podem ser necessários por compatibilidade. [Source: `https://prometheus.io/docs/practices/histograms/`, consultado em 2026-09-23]
- OpenTelemetry define convenções semânticas para métricas de sistema, processo, container, Kubernetes e runtime, mas o status dessas convenções pode variar; a story deve tratar métricas de CPU/memória/saturação como contrato de dashboard interno sem inventar nomes finais fora de catálogo. [Source: `https://opentelemetry.io/docs/specs/semconv/system/`, consultado em 2026-09-23]
- OpenTelemetry também define convenções para métricas HTTP; use-as como referência para nomes futuros, mas não adicione instrumentação automática nova se a base `record_operation` já atender à story. [Source: `https://opentelemetry.io/docs/specs/semconv/http/http-metrics/`, consultado em 2026-09-23]

### Aprendizados da Story 7.1

- `record_operation` valida tudo antes de emitir sinais; preservar esse padrão para dashboards: validar catálogo/queries antes de exportar JSON.
- Spans locais sem `parent_span_id` iniciam como root spans; dashboards não devem assumir que o trace ID de atributo é o mesmo trace ID real do span quando não há parent remoto.
- `tenant_id`, `correlation_id`, `request_id`, `proposal_id`, `decision_id`, CPF/CNPJ/e-mail e payload não podem virar label de métrica.
- Campos livres como `channel` e `product_type` precisam passar por validação de baixa cardinalidade antes de uso em labels/variáveis.
- `extra` de logs operacionais usa allowlist explícita; dashboards não devem tentar extrair dimensão de `extra` arbitrário.

### Aprendizados do Epic 6

- Dashboards não substituem auditoria oficial; falhas de auditoria podem aparecer em painel, mas a trilha oficial continua no `Audit & Evidence`.
- Gates de vazamento não podem ecoar valores sensíveis ao falhar.
- Unicode, caracteres de controle e chaves ofuscadas precisam ser considerados em validações de strings, queries e metadados.
- Não usar dados reais em exemplos, fixtures, JSON de dashboards ou documentação.
- Separar claramente interno, customer-facing e auditoria para não gerar dívida de privacidade.

### File Structure Requirements

- `packages/observability/src/creditos_observability/dashboards.py` — NEW provável para catálogo, modelos simples e validação/exportação determinística.
- `packages/observability/src/creditos_observability/__init__.py` — UPDATE se novas APIs públicas forem expostas.
- `packages/observability/tests/unit/test_internal_dashboards.py` — NEW provável para catálogo/exportação/privacidade.
- `ops/observability/grafana/dashboards/internal/` — NEW provável para JSONs internos versionados ou fixtures exportadas.
- `ops/observability/grafana/provisioning/` — opcional; criar apenas se houver provider YAML simples e sem credenciais.
- `docs/observability.md` ou `docs/observability-dashboards.md` — UPDATE/NEW para documentação operacional.
- `_bmad-output/implementation-artifacts/7-2-dashboards-tecnicos-internos.md` — UPDATE durante implementação.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — UPDATE de status conforme fluxo BMAD.

### Testing Requirements

- Testes focados esperados:
  - `.venv/bin/pytest packages/observability/tests/unit/test_internal_dashboards.py packages/observability/tests/unit/test_telemetry_operations.py tests/test_observability_foundation.py -q`
  - `.venv/bin/pytest tests/test_epic6_audit_logs_sensitive_data_gates.py tests/test_sensitive_data_masking.py packages/security/tests/unit/test_masking.py -q`
- Gates antes de PR:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
  - `.venv/bin/pytest services packages tests/test_observability_foundation.py tests/test_epic6_audit_logs_sensitive_data_gates.py -q`
- Se `uv lock --check` falhar localmente por `uv` ausente e nenhuma dependência for adicionada, registrar limitação ambiental sem editar lockfile.
- Se dependência nova for adicionada, justificar e atualizar `uv.lock`; a expectativa desta story é não adicionar dependência.

### Anti-padrões Bloqueados

- Não criar dashboard customer-facing nesta story.
- Não adicionar Grafana SDK, Jsonnet, grafonnet, grafanalib ou dependência nova sem justificativa explícita.
- Não criar data source com URL, token ou credencial real.
- Não usar dados reais ou exemplos com CPF/CNPJ/e-mail reais.
- Não consultar ou renderizar logs crus/traces crus/payloads.
- Não usar IDs de proposta, decisão, request, correlation ou trace como labels/variáveis de alta cardinalidade.
- Não expor `tenant_id` como variável livre em dashboard sem decisão explícita de cardinalidade e autorização.
- Não colocar código de dashboard em `domain` de serviço.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-09-23 — Story 7.2 iniciada na branch `agent/story-7-2-internal-technical-dashboards`; Jira `CTOS-61` movido para `Em andamento`.
- 2026-09-23 — `bmad-create-story` executado com análise de Epic 7, Story 7.1, OQ-9, AD-5/AD-7/AD-16/AD-20, PRD, retrospectiva do Epic 6 e documentação oficial Grafana/Prometheus/OpenTelemetry.
- 2026-09-23 — Jira `CTOS-61` atualizado e subtarefas `CTOS-378` a `CTOS-383` criadas/sincronizadas antes da implementação.
- 2026-09-23 — `CTOS-378` movida para `Em andamento`; story marcada como `in-progress` no BMAD.
- 2026-09-23 — Testes RED criados em `packages/observability/tests/unit/test_internal_dashboards.py`; falharam inicialmente por API de dashboards inexistente.
- 2026-09-23 — Catálogo interno, validação de privacidade/cardinalidade, exportação Grafana e JSONs versionados implementados.
- 2026-09-23 — Documentação operacional de dashboards internos criada e referências em observabilidade/README atualizadas.
- 2026-09-23 — `CTOS-378` a `CTOS-382` movidas para `Concluído`; `CTOS-383` movida para `Em andamento` para execução de gates.
- 2026-09-23 — Gates executados: Ruff format/check, Pyright, testes focados, regressões de mascaramento/Epic 6 e suíte ampliada `services packages tests/test_observability_foundation.py tests/test_epic6_audit_logs_sensitive_data_gates.py`.
- 2026-09-23 — `pytest -q` completo passou fora do sandbox exceto `tests/test_local_harness.py::test_dev_script_harness_check_uses_documented_command`, por `uv` ausente no PATH local; sem dependências novas e sem alteração de `uv.lock`.
- 2026-09-23 — `CTOS-383` movida para `Concluído`; `CTOS-61` movida para `Em análise` para `bmad-code-review`.
- 2026-09-27 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 10 patches aplicados e validados.

### Completion Notes List

- Story criada como guia de implementação para dashboards técnicos internos.
- Escopo mantém dashboards internos separados de alertas, projeções de negócio e customer-facing.
- Guardrails de privacidade, cardinalidade e ausência de backend externo foram explicitados.
- Catálogo `internal_dashboard_catalog()` criado com sete dashboards técnicos internos e classificação `internal`.
- Validação `validate_dashboard_catalog()` bloqueia labels sensíveis/de alta cardinalidade, logs crus, traces crus e variáveis livres.
- Exportação `export_grafana_dashboard()` gera JSON Grafana determinístico sem instância externa.
- Artefatos versionados em `ops/observability/grafana/dashboards/internal/` e provider sem credenciais criado para provisionamento futuro.
- Gates passaram: `ruff format --check`, `ruff check`, `pyright`, 23 testes focados de observabilidade, 16 regressões de masking/Epic 6 e suíte ampliada com 712 testes.
- Limitação ambiental registrada: `pytest -q` completo falha apenas no harness local por `uv` ausente no PATH desta sessão; rerun escalado confirmou sockets ok e 713 testes passaram antes dessa falha.
- Review findings resolvidos: validação PromQL fortalecida, percentis completados, CPU/memória/saturação separados, commit/digest adicionado, isolamento por serviço nas integrações, variável `tenant_isolation_tier`, limites de exportação, placeholders explícitos, normalização OTel→Prometheus documentada e legendas ajustadas.
- Gates pós-review passaram: `ruff format`, `ruff check`, `pyright`, 24 testes focados de observabilidade, 16 regressões de masking/Epic 6 e suíte ampliada com 713 testes.

### File List

- `_bmad-output/implementation-artifacts/7-2-dashboards-tecnicos-internos.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/observability-dashboards.md`
- `docs/observability.md`
- `packages/observability/README.md`
- `packages/observability/src/creditos_observability/__init__.py`
- `packages/observability/src/creditos_observability/dashboards.py`
- `packages/observability/tests/unit/test_internal_dashboards.py`
- `ops/observability/grafana/dashboards/internal/audit-security.json`
- `ops/observability/grafana/dashboards/internal/deploy-release-health.json`
- `ops/observability/grafana/dashboards/internal/external-integrations.json`
- `ops/observability/grafana/dashboards/internal/internal-grpc.json`
- `ops/observability/grafana/dashboards/internal/nats-jetstream-dlq.json`
- `ops/observability/grafana/dashboards/internal/platform-overview.json`
- `ops/observability/grafana/dashboards/internal/public-api.json`
- `ops/observability/grafana/provisioning/dashboards/internal.yaml`

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-09-23 | 0.1 | Story criada via `bmad-create-story`; contexto do Epic 7, OQ-9, Story 7.1, Epic 6 e fontes técnicas oficiais consolidado. | Codex |
| 2026-09-23 | 1.0 | Dashboards técnicos internos implementados como catálogo validável, exportação Grafana determinística, JSONs versionados e documentação operacional. | Codex |
| 2026-09-27 | 1.1 | Achados do `bmad-code-review` corrigidos e validados antes de commit/push/draft PR. | Codex |
