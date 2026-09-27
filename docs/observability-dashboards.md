# Dashboards Técnicos Internos

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

Métricas de NATS, deploys, health/readiness, segurança e custo podem aparecer
como placeholders explícitos até a infraestrutura ou adapters reais publicarem
os sinais correspondentes.

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
`integration_class`. O dashboard de deploy também pode usar `release_ref` como
metadado técnico controlado de release para commit/digest publicado pela
pipeline.

## Limites

- Dashboards técnicos internos não são auditoria oficial.
- Falhas de auditoria podem aparecer como sinal operacional, mas a fonte de
  verdade continua sendo `Audit & Evidence`.
- Dashboards customer-facing devem consumir projeções curadas do
  `Reporting & Insights`, nunca estes dashboards internos ou telemetria bruta.
- Alertas, SLO watch e regras do Alertmanager são responsabilidade da Story 7.3.
