# Consumer Expectations — Webhook Público v1

Este documento descreve as expectativas mínimas para clientes B2B que configuram e recebem callbacks do contrato `webhook-configuration-public-api` v1. Ele complementa o OpenAPI em `packages/contracts/openapi/public/webhooks/v1/openapi.json` e é validado por testes de contrato.

## Cenários mínimos

- **Configuração**: o cliente cadastra endpoint `https://`, eventos `decision.status_changed`/`decision.completed`, `signing_key_ref`, algoritmo `hmac_sha256` e política de retry permitida.
- **Listagem**: a API retorna itens minimizados por configuração, sem `tenant_id` público e sem segredo em claro.
- **Erro público**: erros usam `ErrorResponse` fechado e mensagens seguras.
- **Callback assinado**: o payload público contém `contract_version`, `event_id`, `event_type`, `proposal_id`, `decision_status`, `decision_outcome` quando aplicável, `occurred_at`, `correlation_id`, `trace_id` e `idempotency_key`.
- **Retry/DLQ**: exemplos oficiais cobrem `standard_exponential_backoff`, `no_retry`, limites de tentativas, backoff, timeout, retry agendado e DLQ sem exigir NATS real, HTTP real ou endpoint externo.
- **Indistinguibilidade cross-tenant**: configuração inexistente, configuração de outro tenant e acesso sem autorização não devem revelar existência de recurso; a resposta pública deve ser indistinguível quando o contrato não puder expor o motivo real.

## Headers públicos de entrega

Todo callback assinado deve expor os headers públicos `Content-Type`, `X-CreditOS-Correlation-Id`, `X-CreditOS-Event-Id`, `X-CreditOS-Event-Type`, `X-CreditOS-Idempotency-Key`, `X-CreditOS-Signature`, `X-CreditOS-Signature-Algorithm` e `X-CreditOS-Timestamp`.

A assinatura usa `X-CreditOS-Signature-Algorithm=hmac_sha256` e `X-CreditOS-Signature` com prefixo `sha256=`. A canonicalização dos testes usa a mesma função de runtime `canonical_webhook_payload` da entrega implementada na Story 8.4.

## Campos proibidos

Contratos e exemplos públicos não devem expor `tenant_id`, segredo, token, authorization, CPF, CNPJ, e-mail, nome, telefone, endereço, payload bruto, headers privados, request/response body externo ou stack trace.

## Versionamento e escopo

Enquanto não houver primeiro cliente externo integrado, a v1 permanece experimental em MVP pré-produção. Depois do primeiro cliente externo, breaking changes em schemas, enums, headers públicos, exemplos ou semântica exigem nova versão.

Estes testes de contrato não substituem a Story 8.7, que deve validar o fluxo E2E de análise com integrações mockadas.
