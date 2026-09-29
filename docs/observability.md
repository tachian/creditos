# Observabilidade, Logs e Segurança Base

Esta documentação descreve a base transversal criada para que novos serviços do
CreditOS nasçam com rastreabilidade e proteção de dados por padrão.

## Pacotes

- `creditos-security`: utilidades técnicas para mascaramento, omissão e HMAC de
  identificadores enumeráveis.
- `creditos-observability`: contexto de rastreabilidade, logs estruturados,
  health/readiness seguros e emissão mínima de métricas/traces via OpenTelemetry.

Esses pacotes são utilidades técnicas compartilháveis. Eles não devem conter
entidades, regras, policies ou repositories de domínio.

## Campos mínimos de log

Logs estruturados devem incluir, quando aplicável:

- `timestamp` em UTC;
- `service.name`, `service.version` e `deployment.environment`;
- `correlation_id`, `trace_id` e `request_id`;
- `tenant_id` e `tenant_isolation_tier`;
- `operation`, `source`, `destination`, `contract` e `contract_version`;
- `status`, `status_code` e `duration_ms`.

Payloads brutos não devem ser logados. Quando houver payload em um ponto técnico,
o helper `build_structured_log` omite o conteúdo por padrão.

Campos extras ficam agrupados em `extra` para não sobrescrever campos canônicos
como `status`, `trace_id`, `tenant_id` ou `duration_ms`. `error_type` deve ser um
tipo seguro, não uma mensagem de exceção com payload ou dado pessoal.

## Fronteiras de confiança

Headers HTTP externos não são fonte confiável para `tenant_id`. O tenant deve vir
de autenticação/contexto validado pelo `Identity & Tenant`.

Para exemplos técnicos:

- `from_http_headers` preserva correlation/request/trace, mas ignora tenant vindo
  de header externo;
- `from_grpc_metadata` aceita tenant porque representa propagação interna após a
  fronteira confiável;
- `from_cloudevent_attributes` aceita tenant para eventos internos normalizados.

`traceparent` deve seguir o formato W3C com trace ID e span ID hexadecimais,
válidos e não zerados.

## Mascaramento

Máscara forte é o padrão para logs, traces, dashboards, telemetria e respostas
operacionais.

Exemplos:

- CPF: `***.***.***-09`;
- CNPJ: `**.***.***/****-90`;
- e-mail: `j***@dominio.com`;
- telefone: `(**) *****-4321`;
- tokens, senhas, secrets, API keys, documentos, imagens e payloads brutos:
  `[OMITIDO]`;
- renda e dados financeiros detalhados: `[DADO_FINANCEIRO_OMITIDO]`.

Para correlação técnica de CPF, CNPJ ou e-mail, use HMAC com chave gerenciada.
Hash simples sem chave é proibido para valores enumeráveis.

## OpenTelemetry

A base técnica adota OpenTelemetry para métricas e traces, mas não materializa
Collector, Prometheus, Loki, Tempo, Grafana ou Alertmanager nesta etapa. Essa
base permite testes locais sem backend externo real e preserva a instrumentação
para evolução da stack observabilidade do MVP.

O helper `InMemoryTelemetry.record_operation` é a API transversal para adapters,
middleware, interceptors, workers e integrações instrumentarem operações HTTP,
gRPC, evento, job e integração sem acoplar domínio ao SDK OpenTelemetry. Ele
emite, em uma única operação validada:

- log estruturado seguro via `build_structured_log`;
- span OpenTelemetry com contexto de correlação e tenant confiável quando
  aplicável;
- métricas `creditos.requests.total` e `creditos.request.duration`.

Antes de emitir qualquer sinal, o helper valida duração, campos obrigatórios,
tipo da operação e atributos técnicos. Se a validação falhar, nenhuma métrica ou
span é registrado.

## Taxonomia técnica mínima

| Sinal | Tipo | Uso nesta story |
| --- | --- | --- |
| `operation.log` | log | Envelope operacional mascarado para rastreabilidade técnica. |
| `operation.trace` | trace/span | Correlação ponta a ponta entre API, gRPC, evento, job e integração. |
| `operation.duration` | metric | Latência e volume técnico com labels de baixa cardinalidade. |
| `customer-facing.dashboard` | projeção futura | Dados agregados e curados por tenant em stories posteriores. |

Campos obrigatórios do envelope técnico, quando aplicável:

- `service.name`, `service.version`, `deployment.environment`;
- `operation`, `status`, `duration_ms`;
- `correlation_id`, `request_id`, `trace_id`;
- `tenant_id` e `tenant_isolation_tier` somente quando vierem de contexto
  confiável.

Labels permitidas para métricas de operação:

- `channel`, `contract`, `contract_version`, `destination`, `operation`,
  `operation_type`, `product_type`, `source`, `status`,
  `tenant_isolation_tier`.

Labels proibidas para métricas:

- `tenant_id`, `correlation_id`, `request_id`, `trace_id`, `proposal_id`,
  `decision_id`;
- CPF, CNPJ, e-mail, telefone, payload, headers, prompt/output, erro bruto,
  token, senha, secret ou API key.

Spans podem carregar `correlation_id`, `request_id`, `trace_id`, `tenant_id` e
`tenant_isolation_tier` quando o contexto for confiável, além dos atributos
técnicos de baixa cardinalidade. Esses atributos continuam sanitizados e
mascarados, e não devem conter payload, headers completos ou mensagens brutas de
erro.

Quando houver `traceparent` válido recebido, o span usa o parent remoto real.
Quando houver apenas `trace_id` local sem `parent_span_id`, o span inicia como
root span OpenTelemetry e preserva o `trace_id` do CreditOS apenas como atributo
sanitizado, sem fabricar parent remoto artificial.

Métricas usam allowlist de atributos de baixa cardinalidade. `correlation_id`,
`tenant_id`, `proposal_id`, CPF, CNPJ, e-mail, payloads, erro bruto e demais
identificadores livres não devem virar labels de métricas.

Como logs em OpenTelemetry Python ainda aparecem como área em desenvolvimento,
o contrato operacional de logs estruturados fica no próprio CreditOS; integração
com Collector pode evoluir sem trocar o formato seguro dos eventos.

Dashboards customer-facing não consomem logs crus, traces crus nem séries brutas
de Prometheus. Eles consomem apenas projeções agregadas, autorizadas e isoladas
por tenant, montadas no `Reporting & Insights` por contrato interno testável.
Essa visão é separada dos dashboards Grafana internos e não carrega queries,
datasources, credenciais, payloads, traces ou métricas de infraestrutura.

## Dashboards técnicos internos

Os dashboards técnicos internos são versionados como código em
`ops/observability/grafana/dashboards/internal/` e descritos em
`docs/observability-dashboards.md`. Eles são classificados como `internal`,
usam apenas fonte Prometheus planejada nesta fase e são validados localmente sem
Grafana, Prometheus, Loki, Tempo, NATS, Docker, rede ou credenciais.

Esses dashboards cobrem saúde geral, API pública, gRPC interno, NATS/DLQ,
bancos, integrações externas, auditoria/segurança operacional e deploys. Eles
não devem ser expostos a clientes nem usados como fonte de verdade de auditoria.

As queries PromQL versionadas assumem a normalização do exporter Prometheus para
nomes como `creditos_requests_total` e `creditos_request_duration_bucket`, a
partir dos instrumentos OpenTelemetry `creditos.requests.total` e
`creditos.request.duration`. O Collector também deve promover de forma
controlada `service.name` e `deployment.environment` para labels de baixa
cardinalidade `service` e `environment`.

## Alertas técnicos e SLO Watch

Os alertas técnicos internos são versionados como código em
`ops/observability/prometheus/rules/internal/technical-alerts.yaml`, possuem
placeholders seguros de roteamento em
`ops/observability/alertmanager/routing/internal-placeholders.yaml` e são descritos
em `docs/observability-alerts.md`. Eles são classificados como `internal`, usam
apenas métricas Prometheus planejadas nesta fase e são validados localmente sem
Prometheus, Alertmanager, Grafana, Loki, Tempo, NATS, Docker, rede ou
credenciais.

Esses alertas cobrem erro, latência, saturação, health/readiness, NATS/DLQ,
reprocessamento, integrações externas, banco, auditoria, segurança operacional e
regressões pós-deploy. O SLO watch usa `version` e `release_ref` como
metadados técnicos controlados para apoiar análise de rollback ou roll-forward.

As regras e placeholders não versionam contact points reais, webhooks,
endpoints externos, tokens ou credenciais. A configuração real de roteamento de
incidentes deve ser feita em IaC e gestão de segredos nas etapas operacionais
futuras.

## Projeções de métricas de negócio

As métricas de negócio customer-facing devem ser produzidas pelo
`Reporting & Insights Service` a partir de eventos minimizados e autorizados,
mantendo read models curados por tenant/produto/canal/período. Essas projeções
não são telemetria técnica e não devem consultar bancos transacionais de outros
serviços.

A primeira base de projeção cobre funil, decisões, reason codes governados,
integrações, custos em unidades inteiras, latência, erros e freshness. A
freshness usa `last_event_time`, `last_processed_at`, `lag_seconds` e status,
permitindo medir o objetivo interno de atualização das visões operacionais sem
transformá-lo em SLA contratual nesta etapa.

`tenant_id` é dimensão permitida no read model de negócio porque a consulta é
isolada por tenant. Isso não autoriza usar `tenant_id`, `proposal_id`,
`decision_id`, `correlation_id`, `request_id`, `trace_id`, CPF, CNPJ, e-mail,
payload, prompt/output ou erro bruto como label técnica, dimensão livre de
dashboard ou campo de agregação customer-facing.

Duplicatas devem ser ignoradas antes de alterar contadores, usando `source +
event_id` e `tenant + event_type + schema_version + idempotency_key` quando
disponível. Eventos fora de ordem podem atualizar contadores históricos, mas
não devem reduzir `last_event_time` nem `last_processed_at` da projeção.

## Dashboards customer-facing curados

O dashboard customer-facing do MVP é uma visão de leitura curada por tenant,
derivada das projeções de negócio do `Reporting & Insights`. Ele deve ser
consultado com contexto confiável e escopo mínimo `dashboard:read` ou
`reporting:read`; o tenant não pode vir de payload livre nem de parâmetro
externo com autoridade própria.

Campos permitidos nessa visão:

- tenant de referência seguro, produto, canal e período;
- funil, decisões e reason codes governados;
- integrações agregadas por classe, callbacks, revisão automatizada e custos em
  unidades inteiras;
- latência agregada, erros agregados, freshness e saúde operacional curada;
- incidentes/degradações descritos por impacto ao tenant, sem detalhes de
  infraestrutura.

Campos proibidos nessa visão:

- dados pessoais, documentos, endereço, identificadores livres de proposta ou
  decisão, tokens, credenciais, payloads, prompts/outputs e evidências
  restritas;
- logs crus, traces crus, spans, PromQL, nomes de pods/nós/hosts, CPU, memória,
  topologia, stack trace, datasource real ou URLs internas;
- moeda, preço comercial, tarifa, fatura ou billing derivado.

A UI final, layout, linguagem visual, navegação e jornadas de cliente ainda
dependem de uma etapa posterior com `bmad-ux`. A entrega atual é o contrato de
dados e os gates locais que garantem isolamento, autorização e minimização.

## Health e Readiness

Health indica se o processo está vivo. Readiness indica se o componente está
apto a receber tráfego. Respostas não devem expor credenciais, stack traces,
payloads, nomes internos sensíveis, strings de conexão ou detalhes excessivos.

Checks com nomes sensíveis são substituídos por identificadores genéricos como
`dependency_1`.
Nomes internos de dependências também são ocultados por padrão, salvo allowlist
explícita de nomes operacionais seguros como `database`, `cache`, `queue`,
`broker` e `storage`.

## Anti-padrões

- Logar payload bruto de requisição, resposta externa ou evento.
- Adicionar CPF, CNPJ, e-mail, proposal ID livre ou erro bruto como label de
  métrica de alta cardinalidade.
- Colocar OpenTelemetry dentro de `domain`.
- Ler dashboards customer-facing diretamente de Prometheus, Loki, Tempo, logs
  crus ou traces crus.
- Usar dados reais em testes, fixtures ou exemplos.
