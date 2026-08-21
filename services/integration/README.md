# Integration Service

Microsserviço responsável pelo catálogo governado de classes de integração,
adapters substituíveis e, nas próximas stories, execução assíncrona de
integrações externas.

## Escopo da Story 3.1

- Catálogo por tenant confiável e produto MVP.
- Classes de integração governadas, sem fornecedor nominal obrigatório.
- Limites, timeout, fallback e custo planejável.
- Plano de integração com estado controlado quando configuração obrigatória está ausente.
- Logs estruturados minimizados e evento auditável de configuração.

## Escopo da Story 3.2

- Adapter mock/sandbox local e determinístico para `kyc_kyb`, `credit_bureau`,
  `anti_fraud` e `receivables`.
- Resultado canônico versionado, sem payload livre, resposta proprietária ou fornecedor nominal.
- Cenários sintéticos controlados: `synthetic_success`, `synthetic_partial`,
  `synthetic_not_found` e `synthetic_failure`.
- Execução permitida somente fora de `prod`/`production`, com tenant confiável,
  plano `ready` e escopo `integration_mock:execute`.
- Logs estruturados minimizados com rastreabilidade por tenant, produto, classe,
  adapter, status, cenário, correlação e trace.

## Escopo da Story 3.3

- Execução assíncrona local/testável de `IntegrationPlan` com fan-out/fan-in.
- Entidades canônicas de execução e job, com status versionados e rastreáveis.
- Portas hexagonais para dispatcher, store de idempotência e publicação futura de resultado.
- Dispatcher in-memory paralelizável, determinístico e sem broker real.
- Idempotência por tenant, `idempotency_key` e fingerprint seguro do plano.
- Logs estruturados minimizados para execução, job despachado, reutilização idempotente e fan-in.

## Escopo da Story 3.4

- Retry local/testável para falhas recuperáveis e timeouts, respeitando `max_attempts`.
- Backoff e jitter determinísticos, sem `sleep` real entre tentativas de retry.
- Classificação controlada de falhas: `recoverable`, `non_recoverable`, `timeout` e `invalid_result`.
- DLQ canônica in-memory, minimizada, append-like e sem payload proprietário.
- Reprocessamento controlado por `dlq_id`, `idempotency_key`, tenant confiável e escopo
  `integration_execution:reprocess`.
- Logs estruturados seguros para `integration_execution.retry_scheduled`,
  `integration_execution.dlq_recorded` e `integration_execution.reprocess_requested`.
- Conceitos compatíveis com evolução futura para NATS JetStream, sem acoplar domínio ou testes a NATS.

## Fora de Escopo Atual

Esta fase não executa fornecedor real, NATS JetStream real, replay durável,
banco real, migration, transactional outbox/inbox real, AsyncAPI final ou gRPC real.
