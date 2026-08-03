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
- Hash simples sem chave é proibido para valores enumeráveis.
- Testes e exemplos devem usar somente dados sintéticos.
