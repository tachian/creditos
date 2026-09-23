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
de Prometheus. Eles devem consumir projeções agregadas, autorizadas e isoladas
por tenant, definidas nas stories posteriores do Epic 7.

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
