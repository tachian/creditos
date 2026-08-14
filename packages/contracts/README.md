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

## Proposta canônica v1

O schema `schemas/proposal/v1/proposal.schema.json` é o contrato público canônico
de submissão de propostas do MVP. Ele cobre CPF e CNPJ para `personal_credit`,
`bnpl`, `business_credit` e `receivables`, com `operation.requested_terms` como
única fonte de termos solicitados.

O contrato não aceita `selected_plan`, `plan_id`, `tenant_id` como autoridade no
body, `idempotency_key` no payload, `extra_data` livre ou payload bruto sem dono.
A idempotência da API pública é governada pelo header obrigatório
`Idempotency-Key`, definido no OpenAPI público.

Callbacks externos não aceitam URL livre no payload da proposta. Quando houver
callback por proposta, o body deve referenciar um perfil previamente cadastrado e
governado por tenant via `callback.callback_profile_ref`.

Blocos governados devem ser fechados por schema para evitar extensão acidental
fora de versão aprovada.
