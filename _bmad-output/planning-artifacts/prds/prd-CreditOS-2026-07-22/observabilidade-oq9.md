# Observabilidade - OQ-9

## Decisão registrada

O CreditOS adotará OpenTelemetry como padrão obrigatório de instrumentação e a stack Grafana OSS como referência inicial para o MVP:

- OpenTelemetry para instrumentação de métricas, logs, traces e propagação de contexto.
- OpenTelemetry Collector para receber, processar, redigir e exportar telemetria.
- Prometheus para métricas técnicas e alertas baseados em séries temporais.
- Grafana para visualização e dashboards.
- Loki para logs estruturados.
- Tempo para tracing distribuído.
- Alertmanager para alertas.

A operação poderá ser self-hosted ou managed, decisão que pertence à Architecture conforme custo, maturidade operacional, segurança, residência de dados, criticidade e capacidade da equipe.

## Princípio central

Observabilidade interna e observabilidade exposta a clientes são capacidades relacionadas, mas não são a mesma coisa.

- Observabilidade técnica interna usa telemetria detalhada para operação, incidentes, SLOs, troubleshooting e segurança.
- Observabilidade de negócio usa eventos e projeções para acompanhar funil, volume, decisões, custo e performance.
- Observabilidade customer-facing expõe apenas uma visão curada, segura e isolada por tenant.

## Dashboards técnicos internos

| Dashboard | Conteúdo esperado |
| --- | --- |
| Saúde geral da plataforma | disponibilidade, erros, latência, saturação e status dos serviços |
| API pública | throughput, latência p50/p95/p99, erros 4xx/5xx, rate limiting e idempotência |
| Microsserviços | CPU, memória, saturação, health check, readiness, erros e deploy atual |
| gRPC interno | latência, erros por método, deadlines, retries, circuit breaker e propagação de contexto |
| Eventos, filas e DLQ | backlog, lag, retries, falhas, reprocessamento e idade das mensagens |
| Integrações externas | falhas por classe, adapter, fornecedor, tenant, timeout, retry, fallback e custo |
| Banco/cache/storage | conexão, latência, erros, saturação e crescimento |
| Segurança operacional | autenticação falha, autorização negada, tentativas cross-tenant, replay e abuso |
| Auditoria | falha de registro de evidência, atraso de escrita e eventos sensíveis |
| Revisão automatizada por IA | uso, latência, erro, fallback, versão do agente/modelo e taxa de inconclusivos |
| Deploys | versão, regressão, erro pós-deploy e comparação antes/depois |

## Dashboards de negócio internos

| Dashboard | Conteúdo esperado |
| --- | --- |
| Funil de decisão | propostas recebidas, validadas, enriquecidas, decididas, aprovadas, recusadas, inconclusivas e aprovadas com alterações |
| Volume por tenant | requisições, propostas, decisões, integrações e callbacks por período |
| Performance por produto | latência, taxa de aprovação, taxa de recusa e inconclusivos por produto |
| Políticas e motivos | versões de política, motivos de decisão, regras acionadas e tendência por tenant |
| Integrações e custo | custo estimado/real por proposta, produto, tenant, classe de integração e fornecedor |
| Revisão automatizada | volume revisado por IA, taxa de recomendação, divergência com decisão final e fallback |
| Risco/fraude | sinais agregados, suspeitas, bloqueios e impacto no funil |

## Dashboards customer-facing

Clientes autorizados devem acompanhar a saúde dos serviços e das próprias análises por uma visão curada do seu tenant.

Conteúdo permitido:

- Status das APIs, webhooks, callbacks e integrações configuradas.
- Incidentes, degradações e indisponibilidades que afetam o tenant.
- Propostas recebidas, processadas, decididas, aprovadas, recusadas, inconclusivas e aprovadas com alterações.
- Latência p50/p95/p99 por produto e endpoint relevante.
- Taxa de erro, timeouts, retries, fallback e indisponibilidade de integrações relevantes.
- Custo estimado ou real por proposta, produto, período e classe de integração.
- Motivos de decisão agregados e tendências, sem dados pessoais ou evidências restritas.

Conteúdo proibido:

- CPU, memória, pods, nós, nomes internos de infraestrutura e detalhes de topologia.
- Prometheus, Loki, Tempo, traces crus, logs crus ou métricas brutas.
- Payloads de requisições, payloads de provedores, documentos, credenciais e segredos.
- Scores brutos restritos, evidências sensíveis ou lógica de decisão indevidamente reversível.
- Dados, métricas, incidentes ou custos de outros tenants.

## Requisitos verificáveis

- Toda telemetria técnica possui `service.name`, versão, ambiente, `tenant_id` quando aplicável, correlation ID e trace ID.
- Logs sensíveis passam por mascaramento, omissão, tokenização ou hash conforme classificação.
- Dashboards customer-facing são derivados de projeções do `Reporting & Insights Service`, não de consultas diretas aos backends de observabilidade técnica.
- Métricas customer-facing respeitam RBAC, scopes, isolamento por tenant, retenção e minimização.
- Incidentes podem ser correlacionados a impacto por tenant, produto, endpoint e classe de integração.
- Alertas existem para SLO de latência, erro 5xx, falha de auditoria, indisponibilidade de integração crítica, crescimento de DLQ, tentativa cross-tenant e vazamento potencial de dados sensíveis em logs.

## Alternativas consideradas

| Alternativa | Vantagens | Consequências |
| --- | --- | --- |
| Datadog ou New Relic | APM maduro, menor esforço inicial, correlação pronta | Maior custo, dependência de fornecedor e necessidade de governança de dados enviados |
| AWS CloudWatch/Application Signals | Integração forte se a cloud for AWS | Acoplamento maior à AWS e menor neutralidade de cloud |
| OpenSearch para logs | Busca textual poderosa e ecossistema conhecido | Operação mais pesada para o MVP em comparação com Loki |
| Jaeger para tracing | Projeto conhecido e maduro para traces | Menor integração nativa com a stack Grafana de referência em comparação com Tempo |

## Consequências para Architecture

- Definir se a stack será self-hosted, managed ou híbrida.
- Definir retenção por tipo de telemetria, ambiente, tenant e criticidade.
- Definir estratégia de cardinalidade para métricas com `tenant_id`, produto e fornecedor.
- Definir padrões de instrumentação para HTTP, gRPC, jobs, eventos, integrações externas, bancos, IA e callbacks.
- Definir taxonomia de métricas técnicas, métricas de negócio, logs, traces, exemplars, SLOs e alertas.
- Definir como incidentes técnicos são projetados para visão customer-facing sem vazar detalhes internos.

## Referências usadas

- OpenTelemetry: `https://opentelemetry.io/docs/`
- Prometheus: `https://prometheus.io/docs/introduction/overview/`
- Grafana: `https://grafana.com/docs/grafana/latest/`
- Grafana Loki: `https://grafana.com/docs/loki/latest/`
- Grafana Tempo: `https://grafana.com/docs/tempo/latest/`
- Alertmanager: `https://prometheus.io/docs/alerting/latest/alertmanager/`
