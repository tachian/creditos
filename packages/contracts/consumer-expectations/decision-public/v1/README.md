# Consumer Expectations — Decisão Pública v1

Este documento descreve as expectativas mínimas para consumidores B2B da API pública `decision-public-api` v1. Ele complementa o OpenAPI em `packages/contracts/openapi/public/decision/v1/openapi.json` e é validado por testes de contrato.

## Cenários mínimos

- **Status pendente**: a consulta pode retornar `submitted` ou `processing` com `message` pública segura, `product_type`, `channel`, `correlation_id` e arrays vazios de `reason_codes`/`factors`; não há `decision_id`, `outcome`, política ou termos aprovados.
- **Decisão final aprovada**: a resposta contém `status=completed`, `outcome=approve`, `policy`, `reason_codes`, `factors` e `approved_terms` minimizados.
- **Decisão final recusada**: a resposta contém `status=completed`, `outcome=reject`, explicabilidade pública e não contém `approved_terms`.
- **Decisão inconclusiva**: a resposta contém `status=unable_to_decide`, `outcome=unable_to_decide`, reason codes/fatores públicos e não abre fila manual.
- **Erro público**: `decision_not_available` é usado de forma indistinguível para proposta inexistente, cross-tenant, ausência de decisão governada ou permissão insuficiente.

## Campos permitidos

Consumidores devem depender apenas dos campos versionados em `DecisionQueryResponse` e `ErrorResponse`. Exemplos oficiais ficam em `components.examples` do OpenAPI e cobrem sucesso, erro, status pendente, decisão inconclusiva e decisão final.

## Campos proibidos

A resposta pública não deve expor `tenant_id`, CPF, CNPJ, e-mail, nome, telefone, endereço, payload bruto, headers internos, tokens, segredo, stack trace, `triggered_rule_ids`, fingerprints ou campos internos de política.

## Versionamento

Enquanto não houver primeiro cliente externo integrado, a v1 permanece experimental em MVP pré-produção. Depois do primeiro cliente externo, a v1 deve ser congelada; breaking changes em campos obrigatórios, enums, mensagens públicas, exemplos ou semântica exigem nova versão, janela de compatibilidade, plano de migração e testes de contrato.
