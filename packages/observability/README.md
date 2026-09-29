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
- Instrumentar operações HTTP, gRPC, evento, job e integração com uma API
  framework-agnostic e testável.

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

## Instrumentação técnica de operações

Use `InMemoryTelemetry.record_operation` para instrumentar operações técnicas em
adapters, middleware, interceptors, workers e integrações. A API aceita
`TelemetryOperationType.HTTP`, `GRPC`, `EVENT`, `JOB` e `INTEGRATION`, valida o
envelope antes de emitir qualquer sinal e retorna o log estruturado seguro.

O helper emite:

- span OpenTelemetry com `correlation_id`, `request_id`, `trace_id`, tenant
  confiável e atributos técnicos sanitizados;
- métricas `creditos.requests.total` e `creditos.request.duration` com labels de
  baixa cardinalidade;
- log estruturado mascarado via `build_structured_log`.

Se o contexto trouxer `traceparent` válido, o span herda o parent remoto real.
Se houver apenas `trace_id` local, o helper inicia um root span OpenTelemetry e
mantém o `trace_id` do CreditOS como atributo sanitizado, sem criar parent
artificial.

Labels de métricas permitem apenas `channel`, `contract`, `contract_version`,
`destination`, `operation`, `operation_type`, `product_type`, `source`, `status`
e `tenant_isolation_tier`. Não use `tenant_id`, `correlation_id`, `request_id`,
`trace_id`, `proposal_id`, `decision_id`, CPF, CNPJ, e-mail, payload,
prompt/output, erro bruto, token ou segredo como label.

Use `technical_signal_taxonomy()` para consultar programaticamente a taxonomia
mínima de sinais permitidos nesta fase. Dashboards customer-facing ficam fora
deste pacote e devem consumir apenas projeções agregadas e autorizadas por
tenant.

## Gates de observabilidade e exposição segura

Use `observability_gate_catalog()` e `validate_observability_gate_catalog()`
para verificar, de forma local e determinística, a cobertura mínima de logs
estruturados, métricas, traces/spans, health/readiness e correlation ID para
operações HTTP, gRPC, evento, job e integração por serviço real do MVP. Esse
gate valida contrato e cobertura; ele não prova disponibilidade real de
Collector, Prometheus, Grafana ou qualquer backend externo.

Use `validate_observability_exposure_payload()` para artefatos técnicos internos
e `validate_customer_facing_observability_payload()` para respostas
customer-facing. O gate customer-facing exige tenant esperado, escopo autorizado
(`dashboard:read` ou `reporting:read`) e fonte curada do `Reporting & Insights`,
além de bloquear Prometheus, Grafana, Loki, Tempo, PromQL, logs/traces crus,
infraestrutura, payloads, CPF/CNPJ/e-mail/telefone, documentos pessoais
numéricos, identificadores livres, billing, preço/moeda e segredos.

## Dashboards técnicos internos

Use `internal_dashboard_catalog()` para consultar o catálogo de dashboards
técnicos internos e `export_grafana_dashboard()` para gerar JSON determinístico
compatível com provisionamento futuro do Grafana.

O catálogo é validado por `validate_dashboard_catalog()` e bloqueia queries,
variáveis e metadados que tentem usar payloads, logs crus, traces crus, dados
pessoais, segredos ou identificadores de alta cardinalidade como labels.

Os dashboards assumem que o Collector/exporter Prometheus normaliza os
instrumentos OpenTelemetry `creditos.requests.total` e
`creditos.request.duration` para `creditos_requests_total` e
`creditos_request_duration_bucket`, promovendo `service.name` e
`deployment.environment` para labels controladas `service` e `environment`.

## Limites

- Não contém domínio de produto.
- Não cria dashboards, SLOs, alertas, stack Grafana OSS ou infraestrutura de
  produção.
- Não substitui a trilha oficial de auditoria append-only.
- Não fornece dashboards customer-facing; esses dashboards devem consumir dados
  agregados e curados por tenant, nunca logs brutos.
