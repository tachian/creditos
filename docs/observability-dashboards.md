# Dashboards Técnicos Internos e Visões Customer-facing

Esta documentação descreve os dashboards técnicos internos versionados para o
CreditOS. Eles são artefatos operacionais internos e não devem ser usados como
visão customer-facing.

## Escopo

Os dashboards internos ficam em:

- `ops/observability/grafana/dashboards/internal/`
- `ops/observability/grafana/provisioning/dashboards/internal.yaml`

O catálogo testável fica em `creditos_observability.dashboards` e exporta JSONs
Grafana determinísticos sem depender de uma instância Grafana local.

## Dashboards Disponíveis

| Dashboard | Finalidade |
| --- | --- |
| `platform-overview` | Saúde geral, erro, latência, throughput, saturação, readiness e versão por serviço. |
| `public-api` | Operação das APIs públicas, status, p50/p95/p99, erros e sinais futuros de idempotência/rate limit. |
| `internal-grpc` | Chamadas internas gRPC, latência, erros, deadlines e propagação de contexto. |
| `nats-jetstream-dlq` | Backlog, lag, retries, DLQ, idade de mensagens e reprocessamento. |
| `external-integrations` | Falhas, latência, timeout, retry, fallback e custo técnico de integrações. |
| `audit-security` | Sinais operacionais de falha de auditoria e segurança sem substituir a trilha oficial. |
| `database-health` | Disponibilidade, latência, saturação de conexões e erros técnicos de bancos. |
| `deploy-release-health` | Saúde pós-deploy, versão ativa e regressão operacional por serviço. |

## Fontes de Dados

Nesta fase, os dashboards usam apenas `Prometheus` como fonte planejada de
métricas técnicas. O manifesto de provisionamento não contém URLs, tokens,
credenciais ou data sources reais.

Os instrumentos OpenTelemetry atuais usam nomes com ponto. Para Prometheus, os
dashboards assumem a normalização do exporter/Collector para nomes com
underscore e sufixos de histograma, além da promoção controlada dos resource
attributes `service.name` e `deployment.environment` para labels Prometheus de
baixa cardinalidade `service` e `environment`.

Mapeamento esperado nesta fase:

- `creditos.requests.total` → `creditos_requests_total`;
- `creditos.request.duration` → `creditos_request_duration_bucket`;
- `creditos.ai.*` → família `creditos_ai_*`, quando aplicável.

Métricas de NATS, bancos, deploys, health/readiness, segurança e custo podem
aparecer como placeholders explícitos até a infraestrutura ou adapters reais
publicarem os sinais correspondentes.

## Privacidade e Cardinalidade

Dashboards internos não podem expor:

- logs crus, traces crus, payloads de requisição ou payloads de provedores;
- CPF, CNPJ, e-mail, telefone, tokens, segredos ou credenciais;
- `proposal_id`, `decision_id`, `correlation_id`, `request_id` ou `trace_id`
  como labels ou variáveis de dashboard;
- `tenant_id` como label livre de Prometheus.

Dimensões permitidas devem ser técnicas e de baixa cardinalidade, como
`environment`, `service`, `operation`, `operation_type`, `status`, `source`,
`destination`, `channel`, `product_type`, `tenant_isolation_tier` e
`integration_class`. A visão de banco usa `pool` apenas como identificador
lógico de baixa cardinalidade, sem host, schema, conexão ou credencial. O
dashboard de deploy também pode usar `release_ref` como metadado técnico
controlado de release para commit/digest publicado pela pipeline.

## Gates Locais

Os dashboards internos e a visão customer-facing devem passar por gates locais
de exposição segura antes de produção. Para dashboards internos, o gate valida
escopo interno, baixa cardinalidade, ausência de logs/traces crus, ausência de
identificadores livres e inexistência de datasources ou credenciais reais. Para
customer-facing, o gate valida RBAC/scopes, isolamento por tenant, minimização,
fonte curada do `Reporting & Insights` e ausência de billing, preço, moeda ou
bancos transacionais.

## Limites

- Dashboards técnicos internos não são auditoria oficial.
- Falhas de auditoria podem aparecer como sinal operacional, mas a fonte de
  verdade continua sendo `Audit & Evidence`.
- Dashboards customer-facing devem consumir projeções curadas do
  `Reporting & Insights`, nunca estes dashboards internos ou telemetria bruta.
- Consultas públicas de decisão e callbacks entram na visão customer-facing
  somente como contadores, latência agregada, erros agregados, retry/DLQ e
  freshness derivados de eventos minimizados.
- Alertas, SLO watch e regras do Alertmanager são responsabilidade da Story 7.3.

## Visão customer-facing curada

A visão customer-facing do Epic 7 não é um dashboard Grafana nesta etapa. Ela é
um view model do `Reporting & Insights`, criado a partir de snapshots de negócio
por tenant e validado localmente sem Grafana, Prometheus, Loki, Tempo, banco
real, rede ou credenciais.

Essa visão expõe apenas cards agregados e seguros:

- funil, consultas públicas de decisão, decisões, reason codes governados,
  revisão automatizada e callbacks;
- integrações por classe, custo em unidades inteiras, latência agregada, erros e
  freshness;
- saúde operacional por componente lógico (`api`, `callbacks`, `integrations`)
  com estados `operational`, `degraded`, `unavailable` ou `unknown`;
- incidentes/degradações por impacto visível ao tenant, sem topologia interna.

Essa visão não pode conter PromQL, datasource real, queries de telemetria bruta,
logs, traces, payloads, dados pessoais, identificadores livres, segredos, nomes
de pods/nós/hosts, CPU, memória, stack traces, moeda, preço comercial ou
faturamento.

O refinamento visual, layout, navegação, textos de interface e jornada do
cliente devem ser tratados posteriormente no fluxo `bmad-ux`. Até lá, o contrato
backend/view model é a referência para futura API ou UI.
