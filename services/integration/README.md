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

## Escopo da Story 3.5

- Registro canônico de custo por job de integração, usando unidades inteiras e sem `float`
  monetário.
- Projeção minimizada de custo e resultado no evento interno de execução, com totais por execução
  e granularidade por tenant, produto, classe, adapter e status.
- Custo estimado vindo do `IntegrationPlanItem.estimated_cost_units` e custo real mockado
  determinístico por tentativas efetivamente executadas.
- Idempotência preservada: replays retornam a execução existente sem republicar custo/projeção/log
  de custo, e mudanças de custo no plano alteram o fingerprint.
- Logs estruturados seguros para `integration_execution.cost_recorded`, sem payload bruto, summary,
  headers, exceções proprietárias, documento, nome, e-mail, token ou segredo.
- `provider_id` opcional e técnico, validado como log-safe, sem escolha de fornecedor real,
  SDK, endpoint, credencial ou contrato comercial.

## Escopo da Story 3.6

- Contrato AsyncAPI v1 para eventos/comandos de integração com CloudEvents `specversion: "1.0"`.
- Schemas JSON v1 fechados para resultado, custo, retry e DLQ/reprocessamento.
- Gates em `scripts/check_contracts.py` para bloquear envelope aberto, campos sensíveis,
  schema sem exemplos inválidos e cobertura incompleta de eventos esperados.
- Serialização CloudEvents testável no runtime via `IntegrationExecutionEvent.to_cloudevent_dict()`,
  alinhada ao contrato de projeção minimizada de custo.
- Expectativas de consumidores para `Decision`, `Audit & Evidence` e `Reporting & Insights`.
- Política `metadata-only` preservada para breaking changes, sem prometer diff semântico completo.

## Fora de Escopo Atual

Esta fase não executa fornecedor real, NATS JetStream real, replay durável,
banco real, migration, transactional outbox/inbox real, broker produtivo ou gRPC real.


## Configuração de Webhooks por Tenant

O `Integration Service` é o bounded context responsável por configurar webhooks
externos por tenant e evento. A configuração usa DDD/arquitetura hexagonal: o
domínio modela `WebhookConfiguration`, o caso de uso aplica tenant confiável,
escopos, validação de endpoint, auditoria e logs seguros, e o adapter in-memory
serve apenas para testes/harness.

A Story 8.3 implementa configuração, listagem e desativação lógica. Ela não
executa chamada HTTP ao cliente, não entrega eventos, não assina payload de
entrega, não agenda retry real e não envia itens para DLQ; esses comportamentos
ficam para a Story 8.4.

Regras principais:

- aceitar somente endpoints `https://` sem `userinfo`;
- rejeitar localhost, loopback, IP privado, link-local, multicast, reserved e
  unspecified;
- rejeitar query string com chaves sensíveis óbvias, como `token`, `secret`,
  `key`, `authorization` e `password`;
- aplicar allowlist confiável por tenant quando configurada no serviço, nunca a partir do payload público;
- persistir apenas referência de chave de assinatura (`signing_key_ref`), nunca
  segredo em claro;
- auditar criação, atualização, desativação e rejeição controlada via porta de auditoria;
- registrar logs estruturados com endpoint minimizado por host, sem payload bruto
  ou segredo.
