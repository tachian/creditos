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

## Dashboard customer-facing curado

- A visão customer-facing é um contrato interno de leitura, montado pelo
  `CustomerDashboardService` a partir dos snapshots já projetados pelo
  `Reporting & Insights`.
- O tenant autorizado vem exclusivamente de `CustomerDashboardAccessContext`;
  qualquer tentativa de sobrescrever o tenant da consulta deve ser rejeitada
  antes de retornar dados.
- Os escopos mínimos aceitos no MVP são `dashboard:read` ou `reporting:read`.
- A saída expõe cards determinísticos de funil, decisões, reason codes
  governados, integrações por classe, callbacks, revisão, custos em unidades
  inteiras, latência agregada, erros, freshness e saúde operacional curada.
- Saúde operacional customer-facing usa estados lógicos (`operational`,
  `degraded`, `unavailable`, `unknown`) e placeholders explícitos quando o
  sinal ainda não existe. Ela não replica métricas técnicas internas.
- Esta entrega não define UI final, layout visual, navegação, API HTTP/gRPC
  pública ou dashboard Grafana customer-facing. Esses pontos dependem de
  refinamento posterior com `bmad-ux` e contratos públicos aprovados.

## Privacidade e limites

- Não persistir CPF, CNPJ, e-mail, nome, endereço, payloads, prompts, outputs, documentos, tokens, secrets ou identificadores brutos de proposta/decisão.
- Não usar `proposal_id`, `decision_id`, `correlation_id`, `request_id` ou `trace_id` como dimensão de dashboard.
- Não consultar Prometheus, Loki, Tempo, logs crus, traces crus, bancos
  transacionais de outros serviços ou dashboards Grafana internos para montar a
  visão customer-facing.
- Não expor CPU, memória, pods, nós, hosts, topologia interna, stack traces,
  payloads de provedores, evidências restritas, scores brutos sensíveis, moeda,
  preço comercial ou faturamento.
- Duplicatas são tratadas antes dos contadores por `source + event_id` e por `tenant + event_type + schema_version + idempotency_key`.
- Eventos fora de ordem são aceitos sem reduzir `last_event_time` ou `last_processed_at`.

## Antiobjetivos desta story

- Não cria API HTTP/gRPC pública.
- Não cria broker NATS real.
- Não cria banco, migrations ou dashboards Grafana.
- Não define contratos públicos novos para decisão, IA ou callback.
