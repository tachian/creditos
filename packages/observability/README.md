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

## Logs estruturados seguros

Use `build_structured_log` como helper central para logs operacionais de
requisições, comandos, jobs, eventos, gRPC e integrações. O envelope mínimo
inclui:

- `timestamp` UTC.
- `service.name`, `service.version` e `deployment.environment`.
- `correlation_id`, `request_id`, `trace_id` e `tenant_id` quando o tenant vier
  de contexto confiável.
- `operation`, `source`, `destination`, `contract`, `contract_version`,
  `status`, `duration_ms` e `status_code` quando aplicável.
- `payload` sempre como `[OMITIDO]` quando informado.
- `extra` somente com metadados técnicos minimizados e mascarados.

Campos técnicos são sanitizados contra caracteres de controle e quebra de linha
para reduzir risco de log injection. Não registre headers completos, request
body, response body, payload de provider, token, secret, prompt/output de IA,
documento/imagem ou exceção bruta.

Logs de integração devem preservar origem, destino, contrato, versão, tenant,
trace, status, tentativas, timeout, duração e resultado seguro, sem payload bruto
do provedor. Para correlação por CPF, CNPJ ou e-mail, gere identificador técnico
por HMAC em fluxo explícito no pacote de segurança; não registre o valor original.

## Limites

- Não contém domínio de produto.
- Não cria dashboards, SLOs, alertas, stack Grafana OSS ou infraestrutura de
  produção.
- Não substitui a trilha oficial de auditoria append-only.
- Não fornece dashboards customer-facing; esses dashboards devem consumir dados
  agregados e curados por tenant, nunca logs brutos.
