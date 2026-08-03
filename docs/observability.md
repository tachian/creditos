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

A Story 0.5 adota OpenTelemetry para métricas e traces, mas não materializa
Collector, Prometheus, Loki, Tempo, Grafana ou Alertmanager. Essa base permite
testes locais sem backend externo real e preserva a instrumentação para evolução
da stack observabilidade do MVP.

Métricas usam allowlist de atributos de baixa cardinalidade. `correlation_id`,
`tenant_id`, `proposal_id`, CPF, CNPJ, e-mail, payloads, erro bruto e demais
identificadores livres não devem virar labels de métricas.

Como logs em OpenTelemetry Python ainda aparecem como área em desenvolvimento,
o contrato operacional de logs estruturados fica no próprio CreditOS; integração
com Collector pode evoluir sem trocar o formato seguro dos eventos.

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
