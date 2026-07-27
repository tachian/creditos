# Eventos e mensageria - OQ-12

## Decisão registrada

O CreditOS usará gRPC para chamadas síncronas internas e NATS JetStream como backbone assíncrono de referência no MVP.

SQS, SNS, Lambda, EventBridge ou serviços AWS equivalentes podem ser usados como complementos quando houver justificativa específica, como integração nativa AWS, tarefa pontual, notificação simples, ponte externa ou redução de custo operacional. Eles não substituem o padrão principal de eventos internos do domínio no MVP.

## Regra de decisão

| Necessidade | Padrão |
| --- | --- |
| Resposta imediata entre serviços internos | gRPC |
| Deadline curto e resultado obrigatório | gRPC |
| Fan-out para múltiplos consumidores | NATS JetStream |
| Retry durável e DLQ | NATS JetStream |
| Replay/reprocessamento controlado | NATS JetStream |
| Reporting, projeções e dashboards | NATS JetStream |
| Integrações externas assíncronas | NATS JetStream |
| Callback/webhook com retry | NATS JetStream |
| Tarefa AWS pontual ou integração nativa | SQS/SNS/Lambda como complemento justificado |

## Padrões obrigatórios

- CloudEvents como envelope de evento.
- AsyncAPI para documentação dos contratos assíncronos.
- Transactional outbox para publicar eventos após transação local.
- Inbox ou tabela de idempotência para consumidores.
- Consumers duráveis para fluxos críticos.
- Ack explícito para confirmação de processamento.
- DLQ para fluxos críticos.
- Replay controlado para reprocessamento.
- Ordering por chave de agregado quando necessário, por exemplo `proposal_id`.
- Eventos não substituem auditoria oficial; auditoria crítica continua no `Audit & Evidence Service`.

## Envelope mínimo de evento

Todo evento deve conter:

- `specversion`.
- `id`.
- `type`.
- `source`.
- `subject`.
- `time`.
- `datacontenttype`.
- `tenant_id`.
- `correlation_id`.
- `trace_id`.
- `schema_version`.
- `data`.

## Exemplo de evento

```json
{
  "specversion": "1.0",
  "id": "evt_01HZXYZ",
  "type": "creditos.proposal.submitted.v1",
  "source": "proposal-intake-service",
  "subject": "proposal/prop_123",
  "time": "2026-07-27T12:00:00Z",
  "datacontenttype": "application/json",
  "tenant_id": "tenant_abc",
  "correlation_id": "corr_789",
  "trace_id": "trace_456",
  "schema_version": "1.0.0",
  "data": {
    "proposal_id": "prop_123",
    "product_type": "bnpl",
    "requested_amount": 850.00
  }
}
```

## Como o NATS JetStream funciona

- Publicadores enviam mensagens para subjects, como `creditos.proposal.submitted.v1`.
- Streams capturam subjects e persistem mensagens.
- Consumers duráveis leem mensagens no próprio ritmo.
- O consumidor confirma processamento com `ack`.
- Se o consumidor falhar, a mensagem pode ser reentregue.
- Após limite de tentativas, o fluxo envia a mensagem para DLQ.
- Mensagens persistidas podem ser replayadas para reprocessamento controlado.

## Topologia AWS de referência

| Item | Decisão de referência |
| --- | --- |
| Runtime | EKS em subnets privadas |
| Cluster NATS | 3 nós JetStream |
| Persistência | EBS gp3 criptografado por KMS |
| Distribuição | Anti-affinity e, quando possível, um nó por AZ |
| Exposição | ClusterIP interno ou NLB interno quando necessário |
| Segurança | mTLS/autenticação NATS, secrets gerenciados, network policies |
| Observabilidade | métricas NATS, lag, redelivery, DLQ, storage, quorum e latência |
| Backup | snapshots/configurações/exportações conforme criticidade |

## Streams iniciais candidatos

| Stream | Subjects candidatos |
| --- | --- |
| `proposal-events` | `creditos.proposal.*` |
| `decision-events` | `creditos.decision.*` |
| `integration-jobs` | `creditos.integration.command.*` |
| `callback-jobs` | `creditos.callback.command.*` |
| `audit-events` | eventos derivados não substitutivos da auditoria oficial |
| `dlq` | `creditos.dlq.*` |

## Alternativas consideradas

| Opção | Vantagem | Consequência |
| --- | --- | --- |
| NATS JetStream | Simples, rápido, bom para microsserviços, jobs, replay e consumidores duráveis | Ecossistema analítico menor que Kafka |
| Kafka/Redpanda | Excelente para event streaming, alto volume e replay analítico | Mais operação e custo no MVP |
| RabbitMQ | Ótimo para filas e roteamento | Menos natural para event log/replay |
| SQS/SNS/Lambda | Excelente integração AWS e baixa operação para tarefas pontuais | Lock-in AWS e modelo fragmentado como backbone de domínio |

## Consequências para Architecture

- Definir configuração final de cluster NATS JetStream.
- Definir retenção, storage, replicação e política de DLQ por stream.
- Definir convenção de subjects.
- Definir catálogo de eventos e comandos assíncronos.
- Definir uso exato de SQS/SNS/Lambda quando houver complemento AWS.
- Definir estratégia de contract testing para CloudEvents/AsyncAPI.
- Definir observabilidade operacional de mensageria.

## ADRs necessários

- gRPC para chamadas síncronas internas.
- NATS JetStream como backbone assíncrono do MVP.
- CloudEvents e AsyncAPI como padrões de contrato.
- Transactional outbox e inbox/idempotência.
- DLQ, replay e reprocessamento.
- Uso complementar de SQS/SNS/Lambda.

## Referências usadas

- NATS JetStream: `https://docs.nats.io/nats-concepts/jetstream`
- CloudEvents: `https://github.com/cloudevents/spec`
- AsyncAPI: `https://www.asyncapi.com/docs/reference/specification/v3.0.0`
- Transactional Outbox: `https://microservices.io/patterns/data/transactional-outbox.html`
- Amazon SQS: `https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html`
- Amazon SNS: `https://docs.aws.amazon.com/sns/latest/dg/welcome.html`
- AWS Lambda quotas: `https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html`
