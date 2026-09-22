# Segurança Técnica CreditOS

Este pacote concentra utilidades técnicas genéricas de proteção de dados para o
monorepo. Ele não contém domínio de produto, políticas de crédito, entidades,
repositories ou regras de bounded context.

## Responsabilidades

- Mascarar ou omitir dados sensíveis antes de logs, traces, métricas, erros e
  respostas operacionais.
- Gerar identificadores técnicos por HMAC quando for necessário correlacionar
  CPF, CNPJ, e-mail ou outro valor enumerável sem expor o valor original.
- Servir como base reutilizável para adapters, middleware, interceptors e
  bootstrap dos futuros microsserviços.

## Regras

- Máscara forte é o padrão operacional.
- Tokens, senhas, secrets, API keys, documentos, imagens e payloads brutos são
  omitidos por padrão.
- Headers, request body, response body, payload externo, prompts, completions e
  embeddings são omitidos quando chegam a logs, traces, métricas, erros ou
  respostas operacionais.
- CPF, CNPJ, e-mail e telefone em texto livre são mascarados; quando aparecem em
  chaves estruturadas identificáveis, são omitidos para evitar correlação direta.
- Dados financeiros detalhados são substituídos por
  `[DADO_FINANCEIRO_OMITIDO]`.
- Caracteres de controle e quebras de linha são normalizados antes da emissão
  operacional para reduzir risco de log injection.
- Hash simples sem chave é proibido para valores enumeráveis.
- Testes e exemplos devem usar somente dados sintéticos.

## Correlação segura

Use `hmac_sha256_identifier` quando for necessário correlacionar CPF, CNPJ,
e-mail, telefone ou outro valor enumerável sem expor o valor original. A função
exige `secret_key`; não use SHA simples, hash sem chave, valor parcialmente
visível ou máscara moderada em logs operacionais.

## Limite entre logs e auditoria

Logs operacionais ajudam troubleshooting e observabilidade, mas não substituem a
trilha oficial append-only do `Audit & Evidence`. Operações sensíveis devem
gerar evento oficial de auditoria minimizado e, quando também logadas, manter
apenas contexto técnico seguro como `correlation_id`, `trace_id`, tenant
confiável, operação, status e duração.

## Contexto confiável propagável

O módulo `creditos_security.context` define primitivas técnicas para transportar
contexto já autenticado/autorizado entre microsserviços sem copiar domínio de
produto entre bounded contexts.

### Metadata gRPC

- Use `context_to_grpc_metadata` para emitir pares ASCII lower-case.
- Use `context_from_grpc_metadata` no adapter receptor antes de chamar qualquer
  caso de uso.
- A metadata mínima inclui `x-correlation-id`, `x-request-id`, `traceparent`,
  `x-creditos-tenant-id`, `x-creditos-tenant-isolation-tier`,
  `x-creditos-subject-id`, `x-creditos-principal-type`,
  `x-creditos-scopes` e `x-creditos-schema-version`.
- `x-creditos-client-id` e `x-creditos-roles` são opcionais quando aplicáveis.
- `Authorization`, tokens, `token_id`, secrets, CPF/CNPJ, e-mail completo e
  payload bruto são proibidos.

### CloudEvents

- Use `context_to_cloudevent_attributes` para publicar contexto em extensões
  CloudEvents sem underscore, mantendo o payload focado no domínio do evento.
- Use `context_from_cloudevent_attributes` no consumidor antes de executar o
  caso de uso; ele valida o envelope CloudEvents mínimo e retorna apenas o
  contexto propagado.
- Use `cloudevent_context_from_attributes` quando o consumidor também precisar
  preservar `idempotencykey` e metadados core do evento.
- As extensões mínimas são `tenantid`, `tenanttier`, `subjectid`,
  `principaltype`, `scopes`, `correlationid`, `requestid`, `traceparent` e
  `schemaversion`.
- O envelope validado exige `specversion: "1.0"`, `id`, `source`, `type`,
  `subject`, `time`, `datacontenttype: "application/json"` e `idempotencykey`.
- `clientid` e `roles` são opcionais conforme o fluxo.
- A ausência de contexto obrigatório ou tentativa de propagar chaves sensíveis
  falha com `InvalidTrustedContextError`.
