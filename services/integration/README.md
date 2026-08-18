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

## Fora de Escopo Atual

Esta story não executa fornecedor real, NATS JetStream real, fan-out/fan-in,
retry/DLQ, adapter mock completo, banco real, migration ou gRPC real.
