# Contratos Versionados

O CreditOS usa contratos versionados para APIs públicas, chamadas internas,
eventos, webhooks e schemas de payload. Esta fundação evita payload arbitrário,
breaking change silencioso e acoplamento entre consumidores e detalhes internos.

## Localização

- `packages/contracts/openapi/public`: OpenAPI para APIs HTTP/JSON públicas.
- `packages/contracts/protobuf/internal`: protobuf para gRPC interno.
- `packages/contracts/asyncapi/events`: AsyncAPI para eventos/comandos assíncronos.
- `packages/contracts/schemas`: JSON Schema para payloads e fragmentos de contrato.
- `packages/contracts/catalog/contracts.toml`: catálogo oficial de contratos.
- `packages/contracts/consumer-expectations`: expectativas/testes de consumidores.

## Metadados Obrigatórios

Cada contrato registrado no catálogo deve declarar:

- `id`: identificador estável do contrato.
- `kind`: `openapi`, `protobuf`, `asyncapi` ou `json-schema`.
- `version`: versão explícita no formato `vN`.
- `owner`: serviço ou capacidade responsável.
- `path`: caminho do artefato dentro de `packages/contracts`.
- `compatibility`: `backward-compatible`, `breaking` ou `experimental`.
- `breaking_change_policy`: política aplicável a mudanças incompatíveis.

## Breaking Changes

Contratos marcados como `breaking` precisam declarar `replacement_version`,
`migration_plan`, `compatibility_window` e `contract_tests_required = true`.
Sem esses controles, `./scripts/dev contracts` falha.

## Validação Local

Use:

```bash
./scripts/dev contracts
./scripts/dev all
```

O check usa apenas Python stdlib nesta etapa. Ferramentas como Buf, Spectral,
OpenAPI Generator ou AsyncAPI CLI dependem de ADR ou aprovação futura.

## API Pública de Decisão v1

O contrato `decision-public-api` governa a consulta pública de decisão por
proposta em `packages/contracts/openapi/public/decision/v1/openapi.json`. A
versão inicial expõe somente `GET /v1/proposals/{proposal_id}/decision` como
consulta idempotente, sem `Idempotency-Key`, exigindo `X-Correlation-Id` e
`X-Request-Id` para rastreabilidade.

A resposta é minimizada e contém apenas status, resultado disponível,
identificadores técnicos permitidos, política/versão, reason codes/fatores
visíveis para cliente, termos aprovados seguros e `correlation_id`. Ela não
expõe `tenant_id`, payload bruto, dados pessoais, fingerprints internos,
`triggered_rule_ids`, `required_data_refs`, `validation_issue_codes`,
`fallback_action`, headers, tokens ou stack trace.

Nesta versão, a única referência pública permitida é `proposal_id`. Consultas
por `external_proposal_id`, `customer_reference` ou referências livres exigem
contrato e índice governado futuros. Proposta inexistente, decisão ausente,
cross-tenant e permissão insuficiente usam erro público indistinguível para não
revelar existência de dados de outro tenant.

## Eventos de Integração v1

O `Integration Service` possui contratos assíncronos versionados para execução
solicitada, conclusão completa, resultado parcial, falha, retry, DLQ,
reprocessamento e projeção de custo.

Esses contratos usam AsyncAPI 3.1.0, CloudEvents `specversion: "1.0"` e schemas
JSON fechados em `packages/contracts/schemas/integration/v1`. O envelope exige
tenant confiável, tier de isolamento, correlação, request, idempotência, versão
de schema e `traceparent`. Dados sensíveis, payload bruto, headers, exceções e
respostas proprietárias são bloqueados por testes e pelo checker.

O runtime in-memory do `Integration Service` possui teste focado que compara a
serialização CloudEvents da execução com o contrato de integração, incluindo
resultado, projeção minimizada de custo, retry, DLQ, reprocessamento e prevenção
de duplicidade em replay idempotente.

## Limitação Atual

A Story 0.3 adota estratégia `metadata-only`: o check valida estrutura,
metadados, versionamento declarado e controles de breaking change informados no
catálogo. Ele ainda não executa diff semântico entre versões de OpenAPI,
protobuf, AsyncAPI ou JSON Schema. Essa decisão está registrada para ADR/tooling
futuro no Jira.
