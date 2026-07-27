# Addendum - Product Brief CreditOS

Este addendum preserva detalhes que informam PRD, Architecture e ADRs, mas que deixariam o Product Brief pesado demais.

## Fontes usadas

- `docs/input/project-technical-premises.md`
- `_bmad-output/brainstorming/brainstorm-servico-saas-analise-credito-risco-2026-07-22/brainstorm-premissas-tecnicas.md`
- `_bmad-output/brainstorming/brainstorm-servico-saas-analise-credito-risco-2026-07-22/adendo-microsservicos-logs-observabilidade.md`

## Assumptions marcadas no brief

- O ICP inicial ainda não foi escolhido.
- O posicionamento permanece horizontal até haver recorte de segmento.
- Custo operacional por decisão e por tenant deve ser tratado como métrica de sucesso, mas depende de modelo de precificação e provedores.

## Detalhes para PRD

- Definir fluxos MVP: autenticação, tenant, proposta, validação, enriquecimento, decisão, explicabilidade, auditoria, consulta e análise manual.
- Transformar logs estruturados em critérios de aceite por endpoint e integração.
- Definir funil de negócio: proposta recebida, validada, enriquecida, decidida, encaminhada, aprovada, recusada e revisada.
- Exigir schemas versionados para propostas e callbacks.
- Definir requisitos de dashboards por persona: operação, risco, compliance, tenant admin e plataforma.

## Detalhes para Architecture

- Criar ADR para microsserviços vs monólito, registrando reversão da recomendação inicial de monólito modular.
- Modelar domínios candidatos: Identity & Access, Tenant Management, Application Intake, Data Integration, Policy Management, Decision Engine, Risk Scoring, Fraud Analysis, Manual Review, Audit & Evidence, Reporting & Insights e Notification.
- Definir propagação obrigatória de `tenant_id`, `correlation_id` e `trace_id` entre serviços.
- Usar gRPC como padrão para comunicação interna síncrona entre microsserviços.
- Definir quais fluxos internos devem usar gRPC e quais devem usar eventos assíncronos.
- Definir ownership de dados por serviço e estratégia de consistência.
- Definir padrões de logs, métricas, traces, dashboards e alertas.

## ADRs recomendados

- Microsserviços vs monólito modular.
- Decomposição de domínios e mapa de serviços.
- Estratégia de multi-tenancy.
- Autenticação e autorização.
- Contratos versionados e schemas de requisição.
- Comunicação interna entre microsserviços via gRPC.
- Eventos, mensageria e fluxos assíncronos.
- Logging estruturado, mascaramento e redação.
- Observabilidade técnica e de negócio.
- Auditoria e proteção contra alteração.
- Governança de modelos de risco e IA.

## Decisão adicionada: gRPC interno

As integrações internas entre microsserviços devem usar gRPC para comunicação síncrona. Essa decisão deve ser formalizada em ADR, incluindo alternativas avaliadas, consequências operacionais e limites de uso.

Consequências principais:

- Contratos internos devem ser definidos em protobuf e versionados.
- CI deve validar compatibilidade dos contratos gRPC.
- Cada chamada gRPC deve propagar `tenant_id`, `correlation_id`, `trace_id`, identidade técnica e contexto de autorização necessário.
- Logs e traces devem registrar chamadas gRPC internas com mascaramento de dados sensíveis.
- Timeouts, retries, deadlines e circuit breakers devem ser padronizados.
- gRPC não elimina a necessidade de eventos para processos assíncronos, fan-out, retry durável, DLQ ou consistência eventual.
- APIs externas para clientes ainda devem ser definidas separadamente; gRPC interno não implica expor gRPC publicamente.

## Dashboards sugeridos

- Saúde geral da plataforma.
- API Gateway e tráfego de entrada.
- Microsserviços por latência, erro, CPU, memória e throughput.
- Tracing distribuído ponta a ponta.
- Banco de dados, locks, queries lentas e migrations.
- Filas, eventos, DLQ e retries quando existirem.
- Integrações externas por provedor.
- Segurança operacional.
- Funil de decisão.
- Volume e custo por tenant.
- Performance de decisão.
- Políticas e motivos de decisão.
- Análise manual.
- Risco, fraude e pós-concessão.

## Memlog audit

- Decisão: usar Product Brief como próximo passo BMAD.
- Decisão: seguir Fast path por haver contexto suficiente nos artefatos de brainstorming.
- Capturado no brief: visão, problema, solução, público, diferenciais, escopo, princípios, métricas, riscos e decisões pendentes.
- Capturado neste addendum: detalhes técnicos para PRD, Architecture, ADRs e dashboards.
