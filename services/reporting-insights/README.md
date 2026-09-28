# Reporting & Insights Service

Microsserviço responsável por projeções curadas de métricas de negócio do CreditOS.

## Ownership

- Mantém read models de funil, decisão, integrações, custos, IA consultiva e callbacks por `tenant_id`, produto, canal e período.
- Consome somente eventos minimizados e autorizados. O serviço não consulta bancos transacionais de outros microsserviços.
- Separa observabilidade de negócio de telemetria técnica: `tenant_id` pode existir na chave do read model, mas não deve virar label técnica em Prometheus/OpenTelemetry.

## Eventos consumidos

- Proposta: status de funil, produto, canal, tenant e timestamps.
- Decisão: outcome governado, reason codes governados e status de funil derivado.
- Integração: classe, adapter, provider opcional, status, custo em unidades inteiras, latência e erro.
- IA consultiva: status, custo em unidades inteiras, latência e erro.
- Callback: status, latência e erro.

Contratos públicos de decisão, IA e callback ainda não estão governados em `packages/contracts`; por isso esta primeira entrega usa DTOs internos minimizados.

## Projeções

- Funil por tenant/produto/canal/período.
- Decisões por outcome e reason code de baixa cardinalidade.
- Integrações por classe, adapter, provider opcional e status.
- Custos em `estimated_cost_units` e `actual_cost_units`, sempre inteiros e sem inferir moeda, preço comercial ou faturamento.
- Freshness por projeção com `last_event_time`, `last_processed_at`, `lag_seconds` e status.

## Privacidade e limites

- Não persistir CPF, CNPJ, e-mail, nome, endereço, payloads, prompts, outputs, documentos, tokens, secrets ou identificadores brutos de proposta/decisão.
- Não usar `proposal_id`, `decision_id`, `correlation_id`, `request_id` ou `trace_id` como dimensão de dashboard.
- Duplicatas são tratadas antes dos contadores por `source + event_id` e por `idempotency_key`.
- Eventos fora de ordem são aceitos sem reduzir `last_event_time` ou `last_processed_at`.

## Antiobjetivos desta story

- Não cria API HTTP/gRPC pública.
- Não cria broker NATS real.
- Não cria banco, migrations ou dashboards Grafana.
- Não define contratos públicos novos para decisão, IA ou callback.
