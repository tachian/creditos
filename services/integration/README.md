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

## Fora de Escopo Atual

Esta fase não executa fornecedor real, NATS JetStream real, retry/DLQ, replay,
banco real, migration, transactional outbox/inbox real, AsyncAPI final ou gRPC real.
