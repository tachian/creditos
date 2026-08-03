# Observabilidade CreditOS

Este pacote fornece a base técnica de observabilidade para adapters,
middleware, interceptors, workers e bootstrap dos futuros microsserviços.

## Responsabilidades

- Padronizar contexto de rastreabilidade com correlation ID, request ID, trace ID
  e tenant quando aplicável.
- Gerar logs estruturados já mascarados antes de qualquer persistência ou envio a
  backends de observabilidade.
- Emitir métricas e traces via OpenTelemetry sem exigir Collector local nos
  testes.
- Padronizar respostas seguras de health/readiness.

## Limites

- Não contém domínio de produto.
- Não cria dashboards, SLOs, alertas, stack Grafana OSS ou infraestrutura de
  produção.
- Não substitui a trilha oficial de auditoria append-only.
