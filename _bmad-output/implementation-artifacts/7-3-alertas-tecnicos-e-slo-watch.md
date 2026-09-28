---
jira_issue: CTOS-62
branch: agent/story-7-3-technical-alerts-slo-watch
baseline_commit: c74cfe624ffb1ae5105b260090fee013cfdcc7fd
---

# Story 7.3: Alertas Técnicos e SLO Watch

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a operador da plataforma,
I want alertas por SLO, erro, latência, saturação, DLQ, auditoria e segurança,
so that degradações sejam tratadas antes de afetar clientes criticamente.

## Acceptance Criteria

1. **Catálogo de alertas como código:** dado o repositório do CreditOS, quando a story for implementada, então haverá um catálogo versionado e testável de alertas técnicos internos e SLO watch no pacote `creditos_observability`, com classificação `internal`, severidade, serviço alvo, ambiente, classe de sinal, anotações operacionais e runbook esperado.
2. **Alertas técnicos mínimos:** dadas métricas técnicas críticas, quando erro, latência, saturação, health/readiness, backlog/lag/replay, DLQ, falha de auditoria, tentativa cross-tenant, vazamento potencial de dados sensíveis, falha de integração externa ou degradação de banco exceder limite configurado, então a regra correspondente é representada no catálogo e exportada em artefato operacional versionado.
3. **SLO watch para deploy e mudança crítica:** dado deploy ou mudança crítica, quando o SLO watch for avaliado, então as regras correlacionam versão, `release_ref`/commit/digest, erro, latência e impacto por serviço, com anotações que apoiam rollback ou roll-forward.
4. **Privacidade, segurança e cardinalidade:** dado qualquer alerta, query, label, annotation ou template, quando validado, então não expõe CPF, CNPJ, e-mail, payload bruto, prompt/output, segredo, token, mensagem de erro bruta, `tenant_id`, `proposal_id`, `decision_id`, `request_id`, `correlation_id` ou `trace_id` como label métrica livre/de alta cardinalidade.
5. **Provisionamento seguro:** dado o ambiente local/CI, quando os artefatos de Prometheus/Alertmanager/Grafana forem exportados, então a saída é determinística, não contém receivers reais, webhooks reais, endpoints externos, credenciais ou segredos, e usa placeholders explícitos para integrações de incidentes futuras.
6. **Validação sem runtime externo:** dado o CI do monorepo, quando os testes rodarem, então validam estrutura, PromQL, labels, annotations, severidades, runbooks, placeholders e ausência de dados sensíveis sem exigir Prometheus, Alertmanager, Grafana, Loki, Tempo, NATS, Docker, rede ou credenciais.
7. **Documentação operacional:** dado o fim da story, quando a documentação for revisada, então `docs/observability.md` e/ou documento dedicado explicam catálogo de alertas, severidade, SLO watch, runbooks esperados, roteamento placeholder, limites de privacidade e o que fica diferido para integração real com ferramentas de incidentes.

## Tasks / Subtasks

- [x] CTOS-384 — Criar catálogo de alertas técnicos e SLO watch como código (AC: 1, 6)
  - [x] Definir modelo em `creditos_observability.alerts` ou módulo equivalente do pacote técnico de observabilidade.
  - [x] Classificar todos os alertas como `internal` e bloquear reutilização direta em dashboards customer-facing.
  - [x] Exigir severidade, classe de sinal, serviço/ambiente, expressão, duração, runbook e metadados de exportação.
- [x] CTOS-385 — Definir regras mínimas de alertas técnicos críticos (AC: 1, 2, 4)
  - [x] Cobrir erro, latência, saturação, health/readiness, NATS JetStream, DLQ, backlog, lag, replay/reprocessamento e idade de mensagens.
  - [x] Cobrir falhas de auditoria, tentativa cross-tenant, possível vazamento de dados sensíveis, integrações externas e degradação de banco.
  - [x] Usar somente labels Prometheus de baixa cardinalidade e explicitamente permitidas.
- [x] CTOS-386 — Definir SLO watch de deploy e mudança crítica (AC: 3, 4)
  - [x] Correlacionar versão, `release_ref`, commit/digest, erro pós-deploy, latência pós-deploy e impacto por serviço.
  - [x] Incluir annotations de runbook para análise de rollback/roll-forward sem embutir IDs crus ou payloads.
- [x] CTOS-387 — Exportar artefatos determinísticos de alertas (AC: 1, 5, 6)
  - [x] Gerar regras Prometheus e/ou provisioning Grafana/Alertmanager a partir do catálogo, com ordenação estável.
  - [x] Não versionar receiver real, webhook real, URL externa, token, senha, chave ou configuração de canal de incidente.
  - [x] Manter placeholders explícitos e seguros para roteamento futuro.
- [x] CTOS-388 — Atualizar documentação operacional de alertas (AC: 1, 3, 5, 7)
  - [x] Documentar severidades, SLO watch, runbooks esperados, limites de exposição e relação com dashboards técnicos internos.
  - [x] Explicitar que auditoria oficial continua no serviço de auditoria append-only, não em logs/alertas.
- [x] CTOS-389 — Executar gates de qualidade focados (AC: 4, 6, 7)
  - [x] Rodar testes focados de alertas/observabilidade e regressões de mascaramento/dados sensíveis.
  - [x] Rodar `ruff format --check`, `ruff check` e `pyright` nos alvos impactados, além de suíte ampla coerente com os arquivos alterados.

### Review Findings

- [x] [Review][Patch] Corrigir `HighErrorRate` para calcular proporção real de erro — Numerador e denominador usam agrupamento por `status`, o que transforma séries de erro em `error/error` e dispara 100% para qualquer erro. [packages/observability/src/creditos_observability/alerts.py:175]
- [x] [Review][Patch] Alinhar alertas de banco aos nomes de métricas dos dashboards e calcular erro percentual — Alertas usam métricas divergentes de `database-health` e `DatabaseErrorRateHigh` usa volume absoluto em vez de `erros / total`. [packages/observability/src/creditos_observability/alerts.py:375]
- [x] [Review][Patch] Completar SLO watch com `version` e razão de erro pós-deploy — Regras usam só `release_ref`; falta dimensão `version` exigida pela story e `PostDeployErrorRegression` usa volume absoluto de erro. [packages/observability/src/creditos_observability/alerts.py:416]
- [x] [Review][Patch] Endurecer validação PromQL para sintaxe mínima e `group_left/group_right` — Validação atual não bloqueia labels proibidas em modifiers `group_left(...)`/`group_right(...)` e não rejeita delimitadores desbalanceados. [packages/observability/src/creditos_observability/alerts.py:602]
- [x] [Review][Patch] Endurecer validação de `label_replace`/`label_join` com argumentos complexos — Regex atual pode deixar labels proibidas passarem quando o primeiro argumento da função contém agregações ou parênteses. [packages/observability/src/creditos_observability/alerts.py:157]
- [x] [Review][Patch] Ampliar bloqueio de termos sensíveis e erro bruto em annotations/templates — Denylist não cobre `error_message`, `exception`, `stacktrace`, `password`, `credential`, `api_key`, `authorization` ou `bearer`. [packages/observability/src/creditos_observability/alerts.py:76]
- [x] [Review][Patch] Adicionar placeholder versionado/testado de roteamento de incidentes — AC5 pede placeholders explícitos para integrações futuras; hoje só há regras Prometheus e documentação textual, sem artefato/metadado testado para roteamento seguro. [docs/observability-alerts.md:69]

## Dev Notes

### Contexto do Epic 7

- Epic 7 entrega observabilidade e dashboards por tenant para operadores e clientes autorizados acompanharem saúde técnica, funil, volumes, custos, integrações, incidentes e métricas curadas por tenant. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 7`]
- Story 7.3 é interna e técnica. Ela não implementa projeções de negócio, dashboards customer-facing, UI de cliente ou integrações reais de incidentes; esses itens pertencem às próximas histórias ou ao hardening operacional. [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.3`]
- OQ-9 definiu stack de referência com OpenTelemetry Collector, Prometheus, Grafana, Loki, Tempo e Alertmanager, mas nesta story a entrega deve ser versionada/testável sem subir essa stack. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]

### Regras de arquitetura obrigatórias

- AD-7 exige OpenTelemetry como padrão, Collector como ponto futuro de redaction/filtering/batching/retry/routing e stack Grafana OSS como referência; alertas devem ser compatíveis com Prometheus/Alertmanager/Grafana sem acoplar domínio ao SDK ou à stack. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- AD-5 e AD-20 exigem multi-tenancy `bridge`, isolamento por tenant, controle de cardinalidade e dashboards/alertas filtrados/autorizados. Não criar label métrica com `tenant_id` livre. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-5`]
- AD-8 mantém auditoria oficial no banco append-only/audit trail; logs, métricas, traces e alertas ajudam operação, mas não substituem evidências oficiais. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`]
- AD-10 exige observabilidade para integrações externas assíncronas com retry, DLQ, replay e custo; esta story deve prever alertas para essas classes sem escolher fornecedores externos ainda. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-10`]
- AD-16 define Python 3.13, `uv`, pytest, Ruff, Pyright e DDD/Hexagonal; helpers de alertas ficam em pacote técnico/adapters, nunca em `domain`. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- AD-23 exige rastreabilidade de deploy por versão, commit/digest e pipeline; o SLO watch deve usar esses metadados como dimensão técnica de baixa cardinalidade. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-23`]

### Estado atual do código

- `packages/observability/src/creditos_observability/telemetry.py` já centraliza `InMemoryTelemetry`, `ObservabilityContext`, `technical_signal_taxonomy()` e validação de labels métricas de baixa cardinalidade.
- Labels métricas atuais permitidas incluem `channel`, `contract`, `contract_version`, `destination`, `operation`, `operation_type`, `product_type`, `source`, `status` e `tenant_isolation_tier`; qualquer nova label de alerta precisa ser adicionada conscientemente à allowlist e coberta por teste.
- `packages/observability/src/creditos_observability/dashboards.py` já possui catálogo interno, validação de PromQL, bloqueio de PII real, bloqueio de labels sensíveis e exportação Grafana determinística. Reutilize os padrões de dataclasses imutáveis, validação no construtor/exportador e testes focados.
- Dashboards versionados existentes ficam em `ops/observability/grafana/dashboards/internal/` e provisioning de dashboards em `ops/observability/grafana/provisioning/dashboards/internal.yaml`. Não alterar formato existente sem necessidade.
- `docs/observability.md` e `docs/observability-dashboards.md` já documentam separação entre observabilidade interna, alertas, projeções de negócio e customer-facing; a Story 7.3 deve complementar, não reescrever essa base.

### Requisitos técnicos de implementação

- Criar catálogo de alertas como código, preferencialmente em `packages/observability/src/creditos_observability/alerts.py`, com tipos explícitos para severidade, classe de sinal, escopo, expressão, duração, labels, annotations, runbook e placeholders.
- Validar nomes de alertas, grupos, labels e annotations com regras compatíveis com Prometheus/Alertmanager; labels devem usar identificadores seguros e baixa cardinalidade.
- Alertas devem carregar pelo menos `severity`, `service`, `environment`, `signal_class` e `runbook`; `release_ref` é permitido apenas para SLO watch/deploy por ser metadado técnico controlado.
- Não colocar `correlation_id` ou `trace_id` em labels. Se a história precisar referenciar correlação, use annotation genérica apontando para runbook/dashboard e explique que IDs específicos são consultados em ferramentas autorizadas, não embutidos no alerta.
- Não consultar logs crus, traces crus, payloads, prompts/outputs ou bancos transacionais para disparar alertas nesta fase. Use métricas agregadas/planejadas e placeholders explícitos quando a métrica ainda não existir.
- Não adicionar dependência nova para serialização YAML se o repositório já tiver alternativa simples; se dependência nova for indispensável, justificar, atualizar `pyproject.toml` e `uv.lock`, e cobrir no PR.
- Exportação deve ser determinística: ordenação estável de grupos/regras/labels/annotations, sem timestamp dinâmico e sem valores dependentes do ambiente local.

### Catálogo mínimo esperado

- `HighErrorRate` ou equivalente para taxa de erro por serviço/operação/status.
- `HighLatencyP95` e/ou `HighLatencyP99` para latência sustentada por serviço/operação.
- `ServiceSaturation` para CPU, memória, pool/conexões ou recurso equivalente quando houver métrica planejada.
- `HealthReadinessDown` para indisponibilidade de health/readiness.
- `NatsJetStreamBacklogHigh`, `NatsConsumerLagHigh`, `DeadLetterQueueGrowing` e `ReplayOrReprocessStalled` ou equivalentes para mensageria.
- `AuditCriticalFailure` para falha em emissão/persistência de evidência crítica.
- `CrossTenantAttemptDetected` para tentativa cross-tenant.
- `SensitiveDataLeakPotential` para sinal de gate/log/telemetria indicando possível vazamento.
- `ExternalIntegrationFailureRateHigh`, `ExternalIntegrationTimeoutHigh` e/ou `ExternalIntegrationFallbackHigh` para integrações externas.
- `DatabaseLatencyHigh`, `DatabaseErrorRateHigh` e/ou `DatabaseSaturationHigh` para banco.
- `PostDeployErrorRegression` e `PostDeployLatencyRegression` para SLO watch com `release_ref`.

### Estrutura de arquivos esperada

- NEW `packages/observability/src/creditos_observability/alerts.py` — catálogo, modelos, validação e exportação.
- UPDATE `packages/observability/src/creditos_observability/__init__.py` — exportar API pública somente se seguir padrão existente e não causar acoplamento indevido.
- NEW `packages/observability/tests/unit/test_internal_alerts.py` — testes unitários do catálogo, validação, exportação e privacidade.
- NEW `ops/observability/prometheus/rules/internal/*.yaml` — regras Prometheus internas geradas ou fixtures versionadas determinísticas.
- NEW/OPTIONAL `ops/observability/grafana/provisioning/alerting/internal.yaml` — apenas se a implementação optar por provisioning de alerting Grafana seguro e sem receivers reais.
- NEW/UPDATE `docs/observability-alerts.md` e/ou UPDATE `docs/observability.md` — documentação operacional.
- UPDATE `_bmad-output/implementation-artifacts/7-3-alertas-tecnicos-e-slo-watch.md` — marcar execução real, decisões e gates durante `bmad-dev-story`.

### Testing Requirements

- Testar catálogo completo: nomes únicos, grupos válidos, severidade obrigatória, runbook obrigatório, classificação `internal` e cobertura das classes mínimas.
- Testar validação de privacidade/cardinalidade em labels, annotations, expressões, placeholders e documentação gerada.
- Testar parsing/inspeção de PromQL para bloquear labels proibidas em matchers, `by(...)`, `without(...)`, `on(...)`, `ignoring(...)`, `label_values`, `label_replace`, `label_join` e `count_values`, seguindo o padrão já criado para dashboards.
- Testar exportação determinística comparando snapshots/fixtures ou serialização ordenada estável.
- Rodar regressões relevantes:
  - `.venv/bin/pytest packages/observability/tests/unit/test_internal_alerts.py -q`
  - `.venv/bin/pytest packages/observability/tests/unit/test_internal_dashboards.py packages/observability/tests/unit/test_telemetry_operations.py -q`
  - `.venv/bin/pytest tests/test_epic6_audit_logs_sensitive_data_gates.py tests/test_sensitive_data_masking.py packages/security/tests/unit/test_masking.py -q`
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Se `.venv/bin/*` não existir no ambiente local, usar o executor configurado do projeto (`uv run ...`) e registrar a limitação no Dev Agent Record.

### Previous Story Intelligence

- Story 7.1 consolidou que métricas não podem carregar `tenant_id`, IDs por requisição, erro bruto ou valores de alta cardinalidade; mantenha a mesma postura para alertas.
- Story 7.1 corrigiu spoofing de atributos de contexto e validação de labels; não aceitar labels vindas diretamente de payload, headers externos ou atributos livres.
- Story 7.2 criou validadores para PromQL além de matchers; reaproveite essa lógica ou extraia helper compartilhado em vez de duplicar regex frágil.
- Story 7.2 tornou placeholders explícitos no JSON Grafana; a mesma disciplina vale para métricas planejadas, receivers e rotas de incidentes.
- Story 7.2 adicionou normalização OTel→Prometheus: `creditos.requests.total` vira `creditos_requests_total`, `creditos.request.duration` vira `creditos_request_duration_bucket`, e resource attributes `service.name`/`deployment.environment` são promovidos para labels `service`/`environment`.
- Reviews anteriores cobraram p95/p99, CPU/memória/saturação explícitas, commit/digest em deploy e labels de baixa cardinalidade; trate esses pontos como requisitos, não como opcionais.

### Latest Tech Information

- Prometheus define alerting rules por arquivos de regras com `alert`, `expr`, `for`, labels e annotations; `for` evita disparo imediato e `keep_firing_for` ajuda a reduzir flapping/resolução falsa. [Source: `https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/`, consultado em 2026-09-28]
- Prometheus recomenda usar annotations para informação operacional como descrição e runbook; use labels para roteamento/agrupamento estável e annotations para contexto textual seguro. [Source: `https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/`, consultado em 2026-09-28]
- Alertmanager configura roteamento e receivers via YAML e aceita reload por SIGHUP ou endpoint `/-/reload`; neste MVP, versionar apenas templates/placeholders seguros, sem credenciais reais. [Source: `https://prometheus.io/docs/alerting/latest/configuration/`, consultado em 2026-09-28]
- Alertmanager trata campos como URLs/tokens de integrações como segredos; não versionar `slack_api_url`, tokens, webhook de incidente, SMTP auth ou equivalente em fixtures do repositório. [Source: `https://prometheus.io/docs/alerting/latest/configuration/`, consultado em 2026-09-28]
- Grafana suporta provisioning de recursos de alerting por arquivos YAML/JSON; se usado, manter `uid`, títulos, condições, labels e annotations em arquivo versionado, sem contact points reais ou segredos. [Source: `https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/`, consultado em 2026-09-28]

### Project Structure Notes

- Não criar novo microsserviço para alertas nesta story; o escopo é biblioteca/artefato operacional de observabilidade.
- Não alterar contratos de domínio, contratos públicos de proposta/decisão ou schemas transacionais.
- Não criar dashboard customer-facing, projeção de negócio nem API de status para clientes.
- Não embutir dados reais nos exemplos. Usar valores sintéticos não identificáveis e evitar palavras que scanners de segredo possam interpretar como chave real.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.3`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]
- [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFRs`]
- [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- [Source: `_bmad-output/implementation-artifacts/7-1-instrumentacao-tecnica-base-com-opentelemetry.md`]
- [Source: `_bmad-output/implementation-artifacts/7-2-dashboards-tecnicos-internos.md`]
- [Source: `docs/observability.md`]
- [Source: `docs/observability-dashboards.md`]
- [Source: `https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/`]
- [Source: `https://prometheus.io/docs/alerting/latest/configuration/`]
- [Source: `https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/`]

## Dev Agent Record

### Agent Model Used

Codex CLI — bmad-dev-story

### Debug Log References

- 2026-09-28 — Branch `agent/story-7-3-technical-alerts-slo-watch` criada no início da implementação.
- 2026-09-28 — Jira `CTOS-62` e `CTOS-384` movidos para `Em andamento`.

### Implementation Plan

- Implementar catálogo de alertas como código no pacote técnico de observabilidade, seguindo padrões de dataclasses/validações dos dashboards.
- Validar PromQL, labels, annotations, placeholders e ausência de dados sensíveis sem dependência de runtime externo.
- Exportar regras Prometheus determinísticas e documentar operação, severidade, SLO watch e limites de privacidade.

### Completion Notes List

- 2026-09-28 — Story criada via `bmad-create-story`, sincronizada com Jira `CTOS-62` e subtarefas `CTOS-384` a `CTOS-389`.
- 2026-09-28 — Catálogo interno de alertas e SLO watch implementado em `creditos_observability.alerts`, com exportação Prometheus determinística e validações de privacidade/cardinalidade.
- 2026-09-28 — Regras mínimas cobrem erro, latência p95/p99, saturação, health/readiness, NATS/DLQ/reprocessamento, auditoria, segurança, integrações, banco e regressão pós-deploy.
- 2026-09-28 — Documentação operacional criada em `docs/observability-alerts.md` e referenciada em `docs/observability.md`.
- 2026-09-28 — Validações executadas: 37 testes focados/regressões, Ruff format/check, Pyright e suíte ampla com shim temporário de `uv` (`714 passed`).
- 2026-09-28 — Code review adversarial resolveu 7 findings: proporções de erro, métricas de banco, SLO watch com `version`, validação PromQL, denylist sensível e placeholder de roteamento.
- 2026-09-28 — Validações pós-review: 38 testes focados/regressões, Ruff format/check, Ruff check, Pyright e suíte ampla com shim temporário de `uv` (`714 passed`).

### File List

- `_bmad-output/implementation-artifacts/7-3-alertas-tecnicos-e-slo-watch.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/observability.md`
- `docs/observability-alerts.md`
- `ops/observability/prometheus/rules/internal/technical-alerts.yaml`
- `ops/observability/alertmanager/routing/internal-placeholders.yaml`
- `packages/observability/src/creditos_observability/__init__.py`
- `packages/observability/src/creditos_observability/alerts.py`
- `packages/observability/tests/unit/test_internal_alerts.py`

### Change Log

- 2026-09-28 — Implementada Story 7.3: catálogo de alertas técnicos internos, SLO watch, exportação Prometheus determinística, documentação operacional e testes de privacidade/cardinalidade.
- 2026-09-28 — Aplicados patches do `bmad-code-review` para endurecer alertas, validações PromQL, roteamento placeholder e consistência com dashboards.
