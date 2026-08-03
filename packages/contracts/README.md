# Contratos Versionados CreditOS

Este pacote centraliza contratos compartilháveis do CreditOS sem conter domínio
compartilhado. Ele existe para organizar artefatos versionados e permitir checks
locais antes que contratos reais de produto sejam implementados.

## Categorias

- `openapi/public`: contratos HTTP/JSON públicos.
- `protobuf/internal`: contratos protobuf para gRPC interno.
- `asyncapi/events`: contratos assíncronos para NATS JetStream e CloudEvents.
- `schemas`: schemas JSON de payloads e fragmentos reutilizáveis de contrato.
- `catalog/contracts.toml`: catálogo governado de contratos e políticas de compatibilidade.
- `consumer-expectations`: ponto de entrada para expectativas/testes de consumidores.

## Política

Todo contrato registrado no catálogo deve declarar versão, owner, compatibilidade
esperada e política de breaking change. Mudanças incompatíveis exigem nova versão,
janela de compatibilidade, plano de migração e testes de contrato.
