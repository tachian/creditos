# Adendo ao Brainstorm - Microsserviços, Escopo Generico, Logs e Observabilidade

Data: 2026-07-22
Fonte base: `docs/input/project-technical-premises.md`
Artefato relacionado: `brainstorm-premissas-tecnicas.md`

## Resumo da revisão

As novas premissas adicionam quatro mudanças relevantes:

- Preferência explicita por arquitetura de microsserviços.
- Ausencia de cliente inicial, exigindo desenho flexivel para diferentes tipos de requisição.
- Obrigatoriedade de logs de requisições e integrações com rastreabilidade e mascaramento.
- Observabilidade técnica e de negócio como requisito central, incluindo dashboards.

A recomendação é aceitar essas direções com ajustes. Microsserviços podem ser a arquitetura alvo, mas devem ser definidos por domínios/bounded contexts claros, contratos versionados, isolamento de tenant e observabilidade desde o início. A ausência de cliente não deve virar suporte irrestrito a qualquer payload; deve virar uma plataforma extensível por tipos de produto, schemas versionados, adapters e políticas configuráveis.

## Alteração de premissa arquitetural

### Premissa original impactada

O documento original recomenda evolução incremental e preferência inicial por monólito modular, evitando microsserviços sem justificativa.

### Nova premissa do usuário

Utilizar arquitetura de microsserviços em vez de monólito; ao criar os domínios do projeto, usar essa premissa.

### Análise crítica

Microsserviços podem fazer sentido para esta plataforma porque crédito e risco tendem a ter capacidades com necessidades diferentes de escala, segurança, auditoria, ciclo de release e isolamento operacional. Ainda assim, a decisão aumenta complexidade em transações distribuídas, observabilidade, testes de contrato, versionamento, deploy, custo operacional, consistência de dados, propagação de tenant e troubleshooting.

Minha recomendação é registrar a arquitetura como "microsserviços orientados a domínios, com modularidade interna obrigatória". Ou seja: cada serviço deve nascer pequeno, coeso e dono de seus dados/contratos; nenhum serviço deve existir apenas para refletir uma tabela, entidade CRUD ou preferência técnica.

### Texto proposto

A arquitetura alvo será baseada em microsserviços orientados a domínios/bounded contexts. Cada microsserviço deve possuir responsabilidade de negócio clara, contrato versionado, ownership de dados, isolamento de tenant, observabilidade própria e critérios de deploy independentes. A criação de serviços deve ser justificada por fronteira de domínio, escala, segurança, isolamento de falhas, ciclo de entrega, requisitos regulatórios ou integração operacional. Mesmo em microsserviços, cada serviço deve manter arquitetura interna modular e evitar abstrações especulativas.

### Consequências

- Exige API gateway ou camada equivalente de entrada e roteamento.
- Exige estratégia de identidade, propagação de claims, tenant e correlation ID entre serviços.
- Exige padrão de contratos, versionamento, compatibilidade e testes de contrato desde cedo.
- Exige observabilidade distribuída com traces ponta a ponta.
- Define gRPC como padrão para comunicação interna síncrona entre microsserviços, ainda exigindo decisão sobre eventos, retries, DLQ e idempotência.
- Exige estratégia para consistência eventual e limites de transação.
- Aumenta custo de CI/CD, deploy, segurança e operação.

### Riscos

- Distribuir cedo demais capacidades que ainda não tem fronteira clara.
- Criar acoplamento por banco compartilhado ou contratos instáveis.
- Dificultar reproduzibilidade de decisões se dados e eventos ficarem fragmentados.
- Aumentar chance de vazamento cross-tenant por propagação incompleta de contexto.
- Transformar "qualquer requisição" em modelo de dados genérico demais e difícil de governar.

## Domínios iniciais sugeridos

Estes domínios devem ser tratados como candidatos a microsserviços, não como obrigação cega. A Architecture deve validar fronteiras, dependências e contratos.

| Domínio/serviço candidato | Responsabilidade primária | Observações |
| --- | --- | --- |
| Identity & Access | Autenticação, usuários, roles, permissões, clients técnicos e tokens | Pode integrar IdP externo; deve emitir claims de tenant e permissões. |
| Tenant Management | Cadastro de tenants, planos, configurações, limites, isolamento e chaves | Fronteira crítica para multi-tenancy. |
| Application Intake | Recebimento, validação e normalização de propostas/requisições | Deve suportar schemas versionados por produto/canal. |
| Data Integration | Conectores para fontes internas/externas, sandbox, mocks e contingência | Deve isolar formatos de provedores. |
| Policy Management | Cadastro, versionamento, aprovação e publicação de políticas de crédito | Mudanças devem ser auditadas. |
| Decision Engine | Execução de políticas, regras, combinação de sinais e decisão final | Núcleo crítico; precisa ser determinístico e reproduzível. |
| Risk Scoring | Calculo de indicadores, scores e features de risco | Modelos entram como insumo versionado. |
| Fraud Analysis | Regras e sinais antifraude, listas, device/context signals quando aplicável | Pode evoluir com fontes e modelos próprios. |
| Manual Review | Fila, análise humana, override, aprovação/reprovação e justificativa | Precisa de trilha de auditoria forte. |
| Audit & Evidence | Registro de auditoria, evidências, acesso sensível e proteção contra alteração | Deve ser separado de logs operacionais. |
| Reporting & Insights | Relatórios, métricas de negócio e consultas agregadas | Cuidado para não expor dados cross-tenant. |
| Notification | Webhooks, callbacks, emails/eventos e comunicação externa | Precisa de idempotência, retries e assinatura. |

## Ajuste sobre "qualquer tipo de requisição"

### Premissa do usuário

Ainda não há cliente; o serviço deve estar pronto para qualquer tipo de requisição.

### Análise crítica

"Qualquer tipo de requisição" é amplo demais para virar requisito verificável. Se interpretado literalmente, cria risco de produto sem foco, modelo de dados amorfo, API instavel e regras impossíveis de testar. O caminho mais seguro é transformar essa premissa em extensibilidade controlada.

### Texto proposto

Como ainda não há cliente inicial definido, a plataforma deve aceitar múltiplos tipos de proposta, produto de crédito, canal e fonte de dados por meio de contratos versionados, schemas configuráveis, normalização de entrada e adapters. O sistema não deve aceitar payloads arbitrários sem contrato; novas requisições devem ser incorporadas por tipo de produto/schema aprovado, com validação, versionamento, documentação, testes de contrato e política de compatibilidade.

### Decisões pendentes

- Quais tipos de produto serão suportados no MVP: crédito pessoal, consignado, BNPL, recebíveis, capital de giro, financiamento, cartão, limite recorrente ou outros.
- O contrato de entrada será único e extensível ou separado por produto.
- Haverá schema registry ou catálogo interno de schemas.
- Quem aprova um novo tipo de requisição.
- Como tenants customizam campos sem quebrar contratos globais.

## Logging obrigatório com mascaramento

### Premissa proposta

Toda requisição recebida deve gerar logs estruturados com dados suficientes para rastreabilidade. Integrações com serviços externos e internos também devem ser logadas. Informações sensíveis devem ser mascaradas.

### Texto recomendado

Todos os serviços devem emitir logs estruturados para requisições de entrada, saída, chamadas internas e integrações externas. Os logs devem incluir dados de rastreabilidade e operação, mas nunca expor informações sensíveis em claro. Campos sensíveis devem ser mascarados, tokenizados, omitidos ou hasheados conforme classificação de dados.

### Campos mínimos para logs de requisição

- `timestamp` em UTC.
- `service_name`, `service_version` e `environment`.
- `correlation_id` e `trace_id`.
- `request_id` quando aplicável.
- `tenant_id` ou identificador técnico equivalente.
- `actor_id`, `client_id` ou origem técnica, quando aplicável.
- `operation` ou rota lógica.
- `http_method`, `path_template` e status.
- `duration_ms`.
- Resultado resumido: sucesso, erro validado, erro técnico, timeout ou rejeição.
- Código de erro padronizado, quando aplicável.
- Chave de idempotência, quando aplicável.

### Campos mínimos para logs de integração

- Serviço de origem e destino.
- Tipo de integração: interna, externa, webhook, callback, batch ou evento.
- Contrato/schema e versão.
- `correlation_id`, `trace_id` e tenant.
- Timeout configurado, duracao, status e tentativas.
- Resultado: sucesso, erro de negócio, erro técnico, timeout, circuit open ou fallback.
- Identificador seguro da transação externa, quando disponivel.

### Dados que devem ser mascarados ou omitidos

- CPF/CNPJ completos.
- Dados bancarios, cartão, renda detalhada e documentos.
- Tokens, senhas, API keys, secrets e credenciais.
- Payloads completos de Open Finance ou bureaus.
- Biometria e documentos de identidade.
- Dados sensíveis de terceiros.

### Observacao importante

Logs operacionais não substituem auditoria. Auditoria deve registrar evidências de decisão e eventos sensíveis com proteção contra alteração; logs devem apoiar troubleshooting, performance e rastreabilidade técnica.

## Observabilidade técnica e de negócio

### Requisito consolidado

Todos os microsserviços devem produzir métricas, logs e traces com propagação obrigatória de `correlation_id`, `trace_id` e contexto de tenant. A observabilidade deve cobrir tanto saúde técnica quanto comportamento de negócio, sempre respeitando mascaramento, minimização e isolamento por tenant.

### Dashboards técnicos recomendados

| Dashboard | Objetivo | Métricas principais |
| --- | --- | --- |
| Saúde geral da plataforma | Visão executiva operacional | Disponibilidade, taxa de erro, latência p95/p99, throughput, incidentes ativos. |
| API Gateway / Entrada | Monitorar tráfego recebido | Requisições por rota, status, tenant, latência, rate limiting, autenticação falha. |
| Microsserviços | Comparar serviços | CPU, memória, restart count, saturação, latência, erro, throughput por serviço. |
| Tracing distribuído | Diagnosticar fluxo ponta a ponta | Tempo por span, dependência lenta, erro por chamada, propagação de correlation ID. |
| Banco de dados | Proteger persistência | Conexoes, queries lentas, locks, deadlocks, uso de índices, tempo de migration. |
| Filas e eventos | Operar assincronia quando existir | Lag, DLQ, retries, mensagens duplicadas, throughput, idade da mensagem. |
| Integrações externas | Controlar terceiros | Latencia, erro por provedor, timeout, circuit breaker, fallback, custo por chamada. |
| Segurança operacional | Detectar abuso | Falhas de login, tokens inválidos, rate limit acionado, tentativas cross-tenant, enumeração. |
| Deploy e releases | Controlar mudança | Frequencia de deploy, rollback, erro pós-release, lead time, falhas de pipeline. |

### Dashboards de negócio recomendados

| Dashboard | Objetivo | Métricas principais |
| --- | --- | --- |
| Funil de decisão | Entender conversão operacional | Propostas recebidas, validadas, enriquecidas, decididas, manuais, aprovadas, recusadas. |
| Volume por tenant | Acompanhar uso e capacidade | Requisições, propostas, decisões, chamadas externas e erros por tenant/plano. |
| Performance de decisão | Medir eficiencia de negócio | Tempo até decisão, tempo por etapa, SLA por tenant, gargalos de integração. |
| Políticas de crédito | Governar regras | Versões ativas, decisões por política, regras mais acionadas, overrides por política. |
| Motivos de decisão | Explicabilidade agregada | Codigos de motivo mais frequentes, fatores favoráveis/desfavoráveis, distribuicao por produto. |
| Análise manual | Operar fila humana | Backlog, aging, tempo médio, taxa de override, decisão por analista, motivos de escalonamento. |
| Risco e fraude | Monitorar sinais | Score médio, faixas de risco, flags antifraude, taxa de suspeita, confirmacoes posteriores. |
| Pos-concessão | Acompanhar performance posterior | Inadimplência por safra, atraso, perda esperada, revisões de limite, alertas. |
| Custo operacional | Controlar margem | Custo por decisão, custo por provedor, chamadas por proposta, custo por tenant. |

### Alertas iniciais recomendados

- Aumento de erro 5xx por serviço, rota ou tenant.
- Latencia p95/p99 acima do SLO.
- Falha ou latência elevada em provedor externo crítico.
- Crescimento de DLQ, retries ou mensagens antigas.
- Tentativas de acesso cross-tenant.
- Logs rejeitados por vazamento de campo sensível.
- Queda abrupta no funil de decisão.
- Aumento anormal de análises manuais.
- Falha na geracao de eventos de auditoria.
- Decisões sem código de motivo, policy version ou correlation ID.

## Atualizacoes recomendadas no artefato anterior

- Substituir a direção "começar por monólito modular" por "arquitetura alvo de microsserviços orientados a domínios, com modularidade interna obrigatória e ADR justificando fronteiras".
- Manter a recomendação contra microsserviços automáticos como "não criar microsserviços sem fronteira de domínio, ownership de dados, contrato e observabilidade".
- Trocar "extração para microsserviço" por "criação ou separação de microsserviço" nos NFRs.
- Adicionar um ADR especifico para decomposicao de domínios e mapa de serviços.
- Adicionar padrão técnico obrigatório de logging estruturado, mascaramento, redação e correlação.
- Adicionar padrão de observabilidade técnica e de negócio, incluindo dashboards e alertas.
- Reformular "qualquer tipo de requisição" como "extensibilidade controlada por schemas versionados e produtos configuráveis".

## Impacto nos documentos BMAD

| Artefato | Ajuste necessário |
| --- | --- |
| Product Brief | Apresentar a plataforma como produto horizontal de decisão de crédito, mas com extensibilidade controlada, não promessa de cobrir qualquer caso sem configuracao. |
| PRD | Adicionar requisitos para schemas versionados, funil de decisão, logs mascarados, dashboards de negócio e critérios de aceite de rastreabilidade. |
| Architecture | Modelar arquitetura de microsserviços por domínio, comunicação, contratos, dados, tenant, tracing, resiliência e deploy independente. |
| ADRs | Criar ADR de microsserviços vs monólito, decomposicao de domínios, gRPC interno, eventos/mensageria, observabilidade, logging e estratégia de schemas. |
| project-context | Registrar invariantes: microsserviços por domínio, tenant/correlation obrigatorios, logs mascarados e observabilidade técnica/de negócio. |
| AGENTS.md | Instruir agentes a não criar serviço novo sem fronteira clara, contrato, logs, métricas, tenant e testes de contrato. |
| docs/standards | Criar padrões de logging, mascaramento, schemas, métricas, traces, dashboards, alertas e contratos. |
| CI/CD | Bloquear merge em caso de contrato quebrado, teste cross-tenant ausente, log sensível detectado, falta de correlation ID em rotas críticas ou falha de observabilidade mínima. |

## Decisões pendentes adicionadas

- Arquitetura de microsserviços será adotada desde o primeiro deploy ou definida como arquitetura alvo com bootstrap mínimo?
- Haverá API gateway dedicado? Qual responsabilidade ele terá?
- Quais fluxos internos serão chamadas gRPC síncronas e quais serão eventos assíncronos?
- Cada serviço terá banco próprio desde o início?
- Como será feita consistência entre proposta, decisão, auditoria e notificacao?
- Qual ferramenta de observabilidade será adotada?
- Qual será a taxonomia oficial de métricas técnicas e de negócio?
- Qual será a política de mascaramento por campo?
- Como validar automaticamente que logs não contem dados sensíveis?
- Qual será o mecanismo para schemas versionados de requisição?

## Decisão adicionada: gRPC para comunicação interna

As integrações internas síncronas entre microsserviços devem usar gRPC. Essa decisão deve ser formalizada em ADR e detalhada na Architecture.

Consequências:

- Contratos internos devem ser definidos em protobuf e versionados.
- Testes de contrato devem validar compatibilidade entre produtores e consumidores.
- Chamadas gRPC devem propagar `tenant_id`, `correlation_id`, `trace_id`, identidade técnica e contexto de autorização.
- Timeouts, deadlines, retries, circuit breakers e tratamento de erro devem ser padronizados.
- Logs e traces devem cobrir chamadas gRPC internas, sempre com mascaramento de dados sensíveis.
- gRPC não substitui eventos quando houver fan-out, processamento assíncrono, retry durável, DLQ ou consistência eventual.
- A API pública para clientes deve ser decidida separadamente; gRPC interno não implica exposição pública via gRPC.

## Recomendação final

Aceitar a preferência por microsserviços, mas registrar uma decisão arquitetural forte: microsserviços por domínio e por necessidade operacional, não por entidade. Para este produto, a arquitetura distribuída só será defensável se tenant, contratos, logs, traces, auditoria, mascaramento e dashboards nascerem como requisitos de plataforma, não como itens posteriores.
