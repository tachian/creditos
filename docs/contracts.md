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

O contrato `decision-public-api` governa a consulta pública de status/decisão
por proposta em `packages/contracts/openapi/public/decision/v1/openapi.json`. A
versão v1 expõe somente `GET /v1/proposals/{proposal_id}/decision` como consulta
idempotente, sem `Idempotency-Key`, exigindo `X-Correlation-Id` e
`X-Request-Id` para rastreabilidade.

A resposta é minimizada e contém `contract_version`, `proposal_id`, `status`,
`message` pública segura e `correlation_id`. Quando há decisão, também pode
conter `decision_id`, `outcome`, `decided_at`, produto, canal, política/versão,
reason codes/fatores visíveis para cliente e termos aprovados seguros. Quando a
proposta ainda está em análise, `status` pode ser `submitted` ou `processing` e
a resposta não inventa decisão, política, reason codes ou fatores.

Os enums públicos versionados são:

- `status`: `submitted`, `processing`, `completed`, `requires_input`,
  `unable_to_decide`.
- `outcome`: `approve`, `reject`, `approve_with_changes`, `request_more_data`,
  `unable_to_decide`, ou nulo para status pré-decisão.
- `error_code`: `invalid_request`, `decision_not_available`,
  `decision_query_failed`.

Status pré-decisão deve ser obtido por porta/projeção governada por tenant,
preparada para gRPC interno, sem acesso direto a tabelas ou repositórios de
outro microsserviço. A API pública não expõe `tenant_id`, payload bruto, dados
pessoais, fingerprints internos, `triggered_rule_ids`, `required_data_refs`,
`validation_issue_codes`, `fallback_action`, headers, tokens ou detalhes técnicos
internos.

Nesta versão, a única referência pública permitida é `proposal_id`. Consultas
por `external_proposal_id`, `customer_reference` ou referências livres exigem
contrato e índice governado futuros. Proposta inexistente, decisão ausente sem
status governado, cross-tenant e permissão insuficiente usam erro público
indistinguível para não revelar existência de dados de outro tenant.

Enquanto não houver cliente externo ativo integrado, o `decision-public-api` v1
é tratado como experimental em estágio MVP pré-produção: ajustes incompatíveis
podem ocorrer na própria v1 desde que sejam registrados no catálogo e cobertos
por testes de contrato. A partir do primeiro cliente externo integrado, a v1 deve
ser congelada; mudanças incompatíveis passam a exigir nova versão, janela de
compatibilidade, plano de migração e testes de contrato.

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
