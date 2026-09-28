# Alertas Técnicos e SLO Watch

Esta documentação descreve os alertas técnicos internos do CreditOS. Eles são
artefatos operacionais para operadores da plataforma e não devem ser usados como
visão customer-facing nem como trilha oficial de auditoria.

## Escopo

Os alertas internos ficam em:

- `ops/observability/prometheus/rules/internal/technical-alerts.yaml`
- `ops/observability/alertmanager/routing/internal-placeholders.yaml`

O catálogo testável fica em `creditos_observability.alerts` e exporta regras
Prometheus determinísticas sem depender de Prometheus, Alertmanager, Grafana,
Docker, rede ou credenciais no ambiente local/CI.

## Catálogo de Alertas

| Grupo | Finalidade |
| --- | --- |
| `creditos-internal-platform-slo` | Erro, latência, saturação e health/readiness por serviço. |
| `creditos-internal-messaging-dlq` | Backlog, lag, DLQ e reprocessamento de mensageria. |
| `creditos-internal-audit-security` | Falhas críticas de auditoria, tentativa cross-tenant e gate de privacidade. |
| `creditos-internal-integrations` | Falha, timeout e fallback em integrações externas. |
| `creditos-internal-database` | Latência, erro e saturação de banco. |
| `creditos-internal-deploy-slo-watch` | Regressões de erro e latência pós-deploy. |

## Severidade

| Severidade | Uso esperado |
| --- | --- |
| `critical` | Impacto provável em decisão, isolamento, auditoria, disponibilidade ou privacidade. |
| `warning` | Degradação sustentada que exige atuação antes de impacto crítico. |
| `info` | Sinal operacional relevante para acompanhamento, sem acionar incidente crítico isoladamente. |

Cada regra deve declarar `severity`, `service`, `environment`, `signal_class` e
`runbook`. Labels são usadas apenas para roteamento e agrupamento estável;
contexto textual fica em annotations seguras.

## SLO Watch de Deploy

O SLO watch usa `version` e `release_ref` como metadados técnicos controlados para correlacionar
versão, commit/digest e regressão pós-deploy. As regras atuais cobrem:

- `PostDeployErrorRegression`;
- `PostDeployLatencyRegression`.

As annotations orientam análise de rollback ou roll-forward, mas não embutem IDs
por requisição. A investigação detalhada deve partir do dashboard interno e do
runbook autorizado.

## Privacidade e Cardinalidade

Alertas internos não podem expor:

- dados pessoais, documentos, contato, payloads, prompts ou respostas de IA;
- tokens, credenciais, URLs reais de incidentes ou canais reais de notificação;
- identificadores por requisição, proposta, decisão ou execução como labels;
- `tenant_id` como label livre de Prometheus;
- logs crus, traces crus ou consultas diretas a payloads.

Dimensões permitidas devem ser técnicas e de baixa cardinalidade, como
`environment`, `service`, `operation`, `operation_type`, `status`, `source`,
`destination`, `integration_class`, `pool`, `tenant_isolation_tier`, `version` e
`release_ref`.

## Provisionamento Seguro

O repositório versiona regras Prometheus internas e placeholders explícitos de
roteamento futuro em `ops/observability/alertmanager/routing/internal-placeholders.yaml`.
Esses placeholders não são contact points reais: não contêm webhooks, canais de
incidente, endpoints externos ou credenciais. A configuração real do
Alertmanager/Grafana deve ser feita por IaC e gestão de segredos quando a
infraestrutura operacional for criada.

## Limites

- Alertas técnicos internos não são auditoria oficial.
- Falhas de auditoria podem disparar alerta operacional, mas a fonte de verdade
  continua sendo `Audit & Evidence`.
- Dashboards customer-facing devem consumir projeções curadas do `Reporting &
  Insights`, nunca estes alertas internos ou telemetria bruta.
- Integrações reais com ferramentas de incidente ficam diferidas para hardening
  operacional, com IaC e gestão de segredos.
