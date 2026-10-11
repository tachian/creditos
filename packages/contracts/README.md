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

## Decisão pública v1

O OpenAPI `openapi/public/decision/v1/openapi.json` define a consulta pública
`GET /v1/proposals/{proposal_id}/decision`. Por ser leitura idempotente, o
contrato não exige `Idempotency-Key`; os headers obrigatórios são
`X-Correlation-Id` e `X-Request-Id`.

A resposta pública v1 cobre tanto status pré-decisão quanto decisão final ou
controlada. O campo `status` usa enum versionado com `submitted`, `processing`,
`completed`, `requires_input` e `unable_to_decide`. O campo `outcome` só aparece
com valor quando há decisão e usa `approve`, `reject`, `approve_with_changes`,
`request_more_data` ou `unable_to_decide`; para status pré-decisão ele é nulo.
Toda resposta aceita inclui `message` pública segura e `correlation_id`.

Status pré-decisão deve vir de porta/projeção governada por tenant, preparada
para integração interna via gRPC, e não de acesso direto a repositórios ou
tabelas internas do `Proposal Intake Service`. Para estados `submitted` ou
`processing`, a resposta não inventa `decision_id`, política, reason codes ou
fatores.

A resposta pública deve permanecer fechada e minimizada. Campos internos como
`tenant_id`, `triggered_rule_ids`, `decision_fingerprint`, `input_fingerprint`,
payloads, dados pessoais, headers, tokens e detalhes técnicos internos não
pertencem ao contrato público. `required_data_refs`, `validation_issue_codes` e
`fallback_action` também ficam fora da v1 até serem governados por contrato
próprio. Referências alternativas a proposta ficam fora da v1 até serem
governadas por contrato próprio.

Os exemplos oficiais ficam em `components.examples` do OpenAPI e são validados
por `scripts/check_contracts.py` e por testes de contrato. Eles cobrem status
pendente, decisão aprovada, decisão recusada, decisão inconclusiva e erro
público. As expectativas de consumidor ficam em
`consumer-expectations/decision-public/v1/README.md`.

Erros públicos usam `ErrorResponse` fechado com `error_code` versionado:
`invalid_request`, `decision_not_available` ou `decision_query_failed`. O código
`decision_not_available` continua indistinguível para proposta inexistente,
cross-tenant, decisão ausente sem status governado e permissão insuficiente.
Enquanto não houver cliente externo ativo integrado, este contrato v1 permanece
experimental em estágio MVP pré-produção: ajustes incompatíveis podem ocorrer na
própria v1 quando registrados no catálogo e cobertos por testes de contrato. A
partir do primeiro cliente externo integrado, a v1 deve ser congelada; mudanças
incompatíveis em campos, enums, mensagens públicas ou semântica exigem nova
versão, janela de compatibilidade, plano de migração e testes de contrato.

## Integração canônica v1

O contrato `asyncapi/events/integration/v1/asyncapi.json` governa eventos e
comandos assíncronos do `Integration Service` usando AsyncAPI 3.1.0 e
CloudEvents `specversion: "1.0"`.

Os schemas `schemas/integration/v1/integration-result.schema.json`,
`schemas/integration/v1/integration-cost.schema.json` e
`schemas/integration/v1/integration-retry.schema.json` e
`schemas/integration/v1/integration-dlq.schema.json` mantêm dados fechados,
minimizados e sem payload proprietário. O runtime atual publica resultado,
custo, retries agendados, DLQ e reprocessamento em eventos separados, e o
contrato deixa essa decisão explícita para evitar divergência entre documentação
e código.

As expectativas de consumidores ficam em
`consumer-expectations/integration-events/v1/README.md` e cobrem `Decision`,
`Audit & Evidence` e `Reporting & Insights`.

## Configuração Pública de Webhooks v1

O contrato `webhook-configuration-public-api` governa a configuração de
webhooks por tenant em `packages/contracts/openapi/public/webhooks/v1/openapi.json`.
A v1 cobre cadastro, listagem, desativação da configuração e expectativas
públicas do callback assinado. A execução assíncrona, broker real, retry
operacional e DLQ runtime continuam pertencendo às Stories 8.4 e 8.5.

A configuração aceita somente endpoints `https://` validados pelo `Integration
Service`, eventos versionados (`decision.status_changed` e `decision.completed`),
status público controlado, referência de chave de assinatura e política de retry. A allowlist de domínios é política confiável do tenant no `Integration Service`, não campo controlado pelo payload público.
O contrato não expõe `tenant_id` como autoridade, segredo em claro, headers
privados, payload bruto ou campos livres. A assinatura inicial usa
`hmac_sha256` com `signing_key_ref`; armazenamento real em KMS/Secret Manager
fica fora do escopo desta story. Os exemplos oficiais cobrem configuração,
listagem, erro, payload público de callback, headers públicos de assinatura,
retry `standard_exponential_backoff`, `no_retry` e metadados seguros de DLQ.
As expectativas de consumidor ficam em
`consumer-expectations/webhook-public/v1/README.md`.

Enquanto não houver cliente externo ativo integrado, a v1 permanece
experimental em estágio MVP pré-produção. A partir do primeiro cliente externo,
a v1 deve ser congelada e mudanças incompatíveis passam a exigir nova versão,
plano de migração, janela de compatibilidade e testes de contrato.
