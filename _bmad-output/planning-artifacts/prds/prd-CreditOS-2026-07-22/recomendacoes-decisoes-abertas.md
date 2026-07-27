# Recomendações para questões abertas do PRD

Data: 2026-07-22
Status: consolidado após resolução das OQ-1 a OQ-12
Escopo: OQ-1 a OQ-12 do `prd.md`

## Síntese executiva

Recomendação principal ajustada após decisão do usuário: manter um MVP multi-produto controlado, preparado para análises de crédito e risco de CPF e CNPJ, incluindo crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis. Esse caminho aumenta a complexidade inicial, mas preserva o objetivo estratégico de uma plataforma extensível desde que cada produto tenha schema versionado, política própria, fluxo mínimo auditável, explicabilidade e integrações opcionais por adapter.

Arquiteturalmente, a direção confirmada é microsserviços orientados a domínio, mas com poucos serviços no primeiro deploy. A comunicação interna síncrona deve usar gRPC, enquanto fluxos assíncronos devem usar NATS JetStream para eventos, jobs, notificações, fan-out, retries duráveis, DLQ, replay e processos posteriores. Para multi-tenancy, a decisão inicial é modelo `bridge`, com evolução para `silo` quando risco, volume, contrato, região, performance ou compliance exigirem.

Para segurança e operação, recomendo OIDC/OAuth 2.0 como base de autenticação, com client credentials para clientes técnicos, autorização RBAC inicial com caminho claro para ABAC, OpenTelemetry como padrão de instrumentação, Prometheus/Grafana como baseline aberto de métricas/dashboards e logs estruturados com redaction antes de qualquer persistência.

## OQ-1: ICP inicial

### Decisão ajustada

Priorizar como ICP inicial: **instituições B2B com operação API-first de crédito e risco para PF e PJ**, incluindo originadores digitais, financeiras/fintechs, FIDCs, varejistas/marketplaces com BNPL e empresas que operam crédito pessoal ou PJ.

### Por quê

- Esse ICP tende a ter dor clara em decisão rápida, integração, política versionada, auditoria e evidência.
- A inclusão de CPF e CNPJ amplia o mercado endereçável, mas exige forte disciplina de contrato, privacidade, explicabilidade e segregação de políticas por produto.
- O Brasil tem mercado de crédito amplo e regulado; o Banco Central reportou estoque total de crédito do SFN de R$ 7,2 trilhões em abril de 2026.
- FIDCs têm prestação recorrente de informações à CVM e são um segmento natural para governança, risco, lastro e monitoramento de recebíveis.
- Open Finance amplia a disponibilidade de dados financeiros autorizados, mas exige consentimento, segurança e finalidade clara.

### Alternativas

| Opção | Vantagem | Desvantagem |
| --- | --- | --- |
| Bancos grandes | Alto valor de contrato e exigências maduras | Ciclo comercial longo, compliance pesado, customização alta |
| Varejo/BNPL | Dor forte de conversão e fraude | Pode puxar produto para jornada de checkout e antifraude mais que crédito |
| Cooperativas | Necessidade real de governança e modernização | Heterogeneidade operacional e possível menor velocidade comercial |
| Empresas B2B que vendem a prazo | Mercado amplo | Educação de mercado maior e menor maturidade de integração |

### Decisão registrada

Definir ICP MVP como **instituições B2B API-first com análise de crédito/risco para CPF e CNPJ**, mantendo segmentação comercial por subvertical.

## OQ-2: Produtos de crédito MVP

### Decisão ajustada

Incluir no MVP **crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis**, em um escopo mínimo por produto.

### Por quê

- Crédito PJ e recebíveis combinam bem com FIDCs, risco operacional, análise cadastral, dados financeiros, políticas por produto e monitoramento posterior.
- Crédito pessoal amplia cobertura PF e exige maior rigor de LGPD, renda, bureau, consentimento, explicabilidade e antifraude.
- BNPL amplia cobertura de decisão instantânea e exige baixa latência, antifraude, idempotência forte, contingência e dashboards de conversão.
- Recebíveis trazem necessidade natural de auditoria, elegibilidade, lastro, concentração e política por cedente/sacado.
- A decisão muda a recomendação original, que deixava crédito pessoal e BNPL para versões futuras.

### Alternativas

| Produto | Recomendação | Motivo |
| --- | --- | --- |
| Crédito PJ/capital de giro | Entrar no MVP | Bom equilíbrio entre valor B2B, dados, política e risco |
| Recebíveis/FIDC | Entrar no MVP | Forte aderência a governança e monitoramento |
| BNPL | Entrar no MVP controlado | Exige latência e antifraude fortes; limitar ao fluxo mínimo auditável |
| Crédito pessoal | Entrar no MVP controlado | Alto volume e dados pessoais; limitar a contrato, política e integrações mínimas |
| Cartão/limite recorrente | Fora do MVP | Ciclo de produto mais complexo e monitoramento contínuo mais pesado |

### Decisão registrada

MVP cobre **crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis**, usando `person_type` e `product_type` versionados.

## OQ-3: Contrato inicial de proposta

### Decisão registrada

Criar um contrato canônico mínimo e extensível, versionado por `schema_version`, com núcleo comum, blocos condicionais e schemas fechados por produto. O contrato não usará `selected_plan` nem `plan_id`; o cliente envia somente `operation.requested_terms`, e a decisão retorna termos aprovados, ajustes, solicitação de dados adicionais, reprovação ou estado inconclusivo.

### Contrato conceitual definido

- Núcleo: `schema_version`, `external_proposal_id`, `idempotency_key`, `person_type`, `product_type` e `channel`.
- Operação: `operation.requested_terms` com `amount`, `currency`, parcelas, entrada e datas quando aplicável.
- Tomador: `borrower` com `document_type`, `document` e nome/razão social mínima.
- Participantes: `participants` com referências para sócios, representantes, avalistas, cedentes, sacados, lojistas ou outros envolvidos.
- Consentimentos: `consents` com `subject_ref`, base, finalidade, origem, vigência e referência externa quando aplicável.
- Dados fornecidos: `provided_data` para dados declarados, cadastrais, financeiros e relacionamento.
- Contexto de risco: `risk_context` com dados contextuais disponíveis, sem exigir sinais antifraude sofisticados.
- Produto: `product_data` com exatamente um sub-bloco compatível com `product_type`.
- Decisão: `decision_options` com `execution_mode`, `review_strategy`, `fallback_action` e `max_wait_ms`.
- Callback: `callback` obrigatório para execução assíncrona quando não houver webhook pré-configurado.

### Decisão registrada

Usar **schema canônico versionado + extensões por produto**, sem `selected_plan`, sem validação de catálogo de planos de financeiras e sem fila manual no MVP. Quando configurada, revisão por IA será automatizada e consultiva; a decisão final continuará dependente de política versionada e auditável.

## OQ-4: Domínios do primeiro deploy

### Decisão registrada

Começar com poucos microsserviços, evitando um serviço para cada capacidade do mapa futuro. A decomposição deve seguir Domain-Driven Design: bounded contexts, linguagem ubíqua, ownership de dados, invariantes de domínio e anti-corruption layers para integrações.

### Primeiro deploy definido

| Serviço | Responsabilidade |
| --- | --- |
| Identity & Tenant Service | clientes técnicos, usuários, tenants, roles, permissões e claims |
| Proposal Intake Service | submissão, validação, normalização e idempotência de propostas |
| Decision Service | políticas, execução de decisão, códigos de motivo e tratamento de propostas inconclusivas |
| Automated Review Service | revisão automatizada consultiva por IA, lacunas, inconsistências, governança de agente/modelo |
| Integration Service | adapters externos, jobs assíncronos, fan-out/fan-in, paralelização controlada, sandbox/mocks, timeouts, retries, DLQ e fallback |
| Audit & Evidence Service | eventos de auditoria, evidências, proteção contra alteração e consultas auditáveis |
| Reporting & Insights Service | observabilidade de negócio, dashboards de negócio, projeções e agregações por tenant |

### Serviços que podem ficar dentro dos anteriores no MVP

- Risk Scoring dentro de Decision Service.
- Fraud Analysis dentro de Decision Service ou Integration Service.
- Notification dentro de Integration Service ou Reporting & Insights Service até volume justificar separação.
- Data & Model Governance fora do primeiro deploy, como backlog final para captura e uso de dados em modelos próprios e IA.

### Decisão registrada

Primeiro deploy com **7 serviços**, não 12. Manter mapa futuro, mas só separar quando houver fronteira de domínio, escala, risco, privacidade ou ciclo de release claro. `Automated Review Service` está confirmado como serviço separado no MVP, porque IA terá ciclo próprio de segurança, custo, observabilidade, governança e auditoria.

### Divisão de observabilidade e evidência

- `Reporting & Insights Service`: observabilidade de negócio, funil, volume por tenant, motivos de decisão, uso de IA consultiva, integrações e custo.
- Stack transversal de observabilidade: observabilidade técnica, logs, métricas, traces, health checks, readiness checks, CPU, memória, latência, throughput, filas, DLQ, retries e alertas.
- `Audit & Evidence Service`: auditabilidade, evidências, proteção contra alteração, retenção e consultas auditáveis.

### Decisão adicional de arquitetura

Todo backend deve seguir **Domain-Driven Design**. Isso significa que regras de crédito, risco, decisão, auditoria, integrações e tenant devem ser modeladas em seus respectivos domínios, sem depender diretamente de frameworks, banco de dados, protocolos, provedores externos ou formatos de terceiros.

### Backlog futuro de dados e IA

Criar no final do projeto um processo de captura, curadoria e uso de dados para modelos próprios e IA. Esse processo deve evitar identificadores diretos sensíveis por padrão, como CPF, nome, rua, telefone, e-mail, documentos e credenciais, e deve usar minimização, anonimização ou pseudonimização, segregação por tenant, versionamento de datasets, lineage, avaliação de viés, explicabilidade e rollback.

### Premissa de integrações externas

Integrações com provedores externos devem ser **assíncronas e paralelizáveis por padrão**. O `Integration Service` deve receber um plano de integrações, disparar chamadas independentes em paralelo, aplicar limites por tenant/provedor/produto/credencial, consolidar resultados por fan-in e devolver ao `Decision Service` resultados completos, parciais ou indisponíveis para tratamento por política.

## OQ-5: Banco por microsserviço

### Decisão registrada

Adotar **ownership lógico de dados por serviço desde o início**, mas permitir **PostgreSQL compartilhado fisicamente com schemas/databases separados por serviço no bootstrap**, se isso reduzir custo operacional.

### Alternativas

| Modelo | Vantagem | Risco |
| --- | --- | --- |
| Banco físico por serviço desde o início | Isolamento forte e disciplina de domínio | Operação mais cara e complexa |
| PostgreSQL compartilhado com schema por serviço | Menor custo inicial, mantém fronteiras lógicas | Risco de queries cruzadas e acoplamento indevido |
| Banco compartilhado com tabelas de todos os serviços | Simples no curto prazo | Viola fronteiras de microsserviços e dificulta evolução |

### Decisão registrada

Usar **database/schema/usuário por serviço**, proibir joins cross-service e registrar evolução para banco físico dedicado quando volume, compliance, risco, performance ou isolamento exigirem.

### Mapa inicial de persistência

| Serviço | Persistência recomendada no MVP |
| --- | --- |
| Identity & Tenant Service | database/schema lógico para tenants, usuários, clientes técnicos, permissões e configurações de capacidades |
| Proposal Intake Service | database/schema lógico para propostas recebidas, validações, schemas, idempotência e status inicial |
| Decision Service | database/schema lógico para políticas, versões, decisões, códigos de motivo e termos aprovados |
| Automated Review Service | database/schema lógico para revisões consultivas, versões de agente/modelo, guardrails e resultados |
| Integration Service | database/schema lógico para jobs, adapters, estado de retry/DLQ, snapshots/referências e resultados normalizados |
| Audit & Evidence Service | isolamento reforçado, append-only e caminho prioritário para storage separado/imutável |
| Reporting & Insights Service | banco de leitura/projeções alimentado por eventos; proibido consultar bancos transacionais diretamente |

### Regras obrigatórias

- Cada serviço usa credencial própria com acesso somente ao seu database/schema.
- Migrações são versionadas por serviço.
- Nenhum serviço acessa tabela, view, schema ou migration de outro serviço.
- Consultas interdomínio usam gRPC, API, eventos, projeções ou composição autorizada.
- Consistência entre serviços deve usar eventos, outbox/inbox, idempotência, projeções e Saga quando necessário.
- Reporting não é fonte transacional nem substituto de auditoria.

## OQ-6: Estratégia de multi-tenancy

### Decisão registrada

Adotar **modelo híbrido por tiers**:

- Tier inicial do MVP: `bridge`, com serviços compartilhados e dados/recursos críticos isolados por tenant ou grupo controlado de tenants.
- Evolução para `silo`: tenant com alto risco, alto volume, exigência regulatória, contrato enterprise, região dedicada, performance garantida ou isolamento operacional reforçado.

### Por quê

- Fontes de arquitetura SaaS tratam isolamento como espectro, com trade-offs entre custo, isolamento, performance e operação.
- Modelo totalmente dedicado desde o início aumenta custo e atrito operacional.
- Modelo totalmente compartilhado pode ser insuficiente para crédito/risco, CPF/CNPJ, auditoria, IA e integrações externas.
- Modelo `bridge` equilibra isolamento e custo: evita `pooled` puro, mas não exige ambiente completo dedicado para todo tenant.

### Decisão registrada

MVP começa com **modelo `bridge`**, serviços compartilhados e isolamento de dados/recursos críticos por tenant ou grupo controlado de tenants. O modelo `silo` fica como evolução para tenants que exigirem isolamento dedicado.

### Controles obrigatórios

- `tenant_id` ou contexto equivalente obrigatório em entidades, eventos, logs, métricas, traces, filas, jobs, arquivos, integrações, callbacks e auditoria.
- `tenant_id` do payload nunca é fonte de verdade sem validação contra identidade autenticada.
- `tenant_isolation_tier` obrigatório no cadastro do tenant.
- Catálogo de tenant resolve tier, localização dos dados, credenciais, limites, região, configurações e recursos dedicados.
- Cache, filas, DLQs, objetos, secrets e jobs exigem chave/contexto de tenant.
- Testes cross-tenant obrigatórios em todos os serviços.
- Alertas para tentativa de acesso cross-tenant e uso anômalo por tenant.
- Rate limits, quotas e concorrência por tenant.
- Reporting e exports sempre tenant-scoped.
- Evolução para `silo` deve ser automatizável por Infrastructure as Code e runbooks.

### Critérios para evoluir para `silo`

- Exigência contratual ou regulatória.
- Alto volume ou noisy neighbor.
- Região ou residência de dados dedicada.
- Backup/restore individual obrigatório.
- Chaves, secrets, rede ou storage dedicados.
- Auditoria reforçada ou retenção específica.
- SLO de performance garantido.
- Risco elevado por sensibilidade de dados.

## OQ-7: Autenticação e autorização

### Decisão registrada

Usar **OIDC/OAuth 2.0** como base:

- Client credentials para integrações máquina-a-máquina.
- Authorization Code + PKCE para usuários humanos do console.
- JWT curto, rotação de chaves, scopes e claims de tenant.
- RBAC no MVP, com ABAC planejado para políticas contextuais.
- Avaliar FAPI 2.0 para endpoints de alto risco ou integrações financeiras sensíveis.

### Por quê

- OAuth 2.0 define client credentials para clientes confidenciais agindo em nome próprio.
- OIDC adiciona camada de identidade sobre OAuth 2.0.
- FAPI 2.0 é perfil de segurança para aplicações de alta segurança baseadas em OAuth 2.0.

### Decisão registrada

Começar com **OIDC/OAuth 2.0 + RBAC + scopes + claims de tenant**, usando Client Credentials para APIs máquina-a-máquina e Authorization Code + PKCE para usuários humanos. ABAC e FAPI 2.0 ficam como evolução planejada conforme criticidade, risco e requisitos financeiros.

### Controles obrigatórios

- Access tokens curtos e validação de `iss`, `aud`, `sub`, `exp`, `iat`, `jti`, scopes e claims de tenant.
- Rotação de chaves e publicação de JWKS.
- `tenant_id` confiável vem do token/contexto autenticado, não do body.
- gRPC interno propaga `tenant_id`, sujeito, scopes, correlation ID e trace ID por metadata.
- API keys simples não são autenticação principal; se existirem, servem apenas como credencial bootstrap ou referência de cliente técnico.
- Para clientes de maior risco, avaliar `private_key_jwt`, mTLS, DPoP ou FAPI 2.0.
- Todo acesso sensível gera auditoria.

## OQ-8: Provedores externos prioritários

### Decisão registrada

Não escolher fornecedor nominal agora. O MVP deve especificar **classes de integração**, criar adapters substituíveis, mocks/sandbox e registrar custo estimado ou real por operação.

### Ordem priorizada para preparo do MVP

1. Cadastro, validação documental, KYC e KYB para PF/PJ.
2. Bureau de crédito, restritivos e indicadores de capacidade de pagamento quando permitidos.
3. Antifraude e contexto digital.
4. Recebíveis, lastro, sacados/pagadores e elegibilidade para produtos de recebíveis ou FIDC.
5. Open Finance ou fontes financeiras equivalentes, somente quando houver consentimento, base legal, parceiro ou instituição habilitada e escopo regulatório aplicável.
6. Webhooks/callbacks de clientes e provedores de notificação.

### Modelo de custo obrigatório

- O sistema deve calcular custo estimado antes ou durante a execução com base nas classes de integração acionadas.
- Cada execução deve registrar tenant, produto, proposta, classe de integração, adapter, fornecedor quando existir, quantidade de chamadas, tentativas, fallback e custo estimado ou real.
- A política do tenant deve poder definir teto de custo por proposta, produto ou estratégia de decisão.
- Quando um fornecedor real for configurado, sua tabela de preços deve preencher o cálculo real sem alterar o contrato de domínio.

### Por quê

- Open Finance exige autorização/consentimento, finalidade, prazo, instituição participante e segurança.
- OWASP API Security destaca risco de consumo inseguro de APIs de terceiros.
- Escolher fornecedor cedo demais pode criar lock-in antes do contrato de domínio estar maduro.
- O custo operacional precisa ser governado desde o MVP, mesmo que os preços reais de fornecedores ainda não estejam definidos.

### Critérios para escolha futura de fornecedores

- Cobertura PF/PJ e aderência aos produtos MVP.
- Latência, SLA, disponibilidade, limites de taxa e capacidade de paralelização.
- Qualidade, atualidade, explicabilidade e rastreabilidade dos dados retornados.
- Segurança, LGPD, minimização, retenção, logs seguros e contrato de tratamento de dados.
- Sandbox, mocks, versionamento de contrato, testes de contrato e suporte a idempotência.
- Custo por chamada, por pacote, por volume, por tenant e por enriquecimento.
- Risco de lock-in, complexidade de homologação e maturidade operacional.

### Consequência registrada

MVP implementa **adapter framework + mocks/sandbox**, modelo de custo por classe de integração e uma integração real somente quando houver caso comercial, parceiro, homologação ou necessidade operacional definida.

## OQ-9: Stack de observabilidade

### Decisão registrada

Adotar **OpenTelemetry** como padrão obrigatório de instrumentação e a stack **Grafana OSS** como referência inicial para o MVP:

- OpenTelemetry para instrumentação de traces, métricas e logs.
- OpenTelemetry Collector para receber, processar, redigir e exportar telemetria.
- Prometheus para métricas.
- Grafana para dashboards.
- Loki para logs.
- Tempo para tracing distribuído.
- Alertmanager para alertas.

A operação pode ser self-hosted ou managed, decisão que pertence à Architecture conforme custo, maturidade da equipe, segurança, requisitos de residência de dados e criticidade operacional.

### Por quê

- OpenTelemetry é padrão aberto e vendor-neutral para traces, métricas e logs.
- O Collector reduz acoplamento com fornecedor e permite processors, incluindo redaction.
- Prometheus/Grafana são baseline conhecido para métricas, dashboards e alertas em ambientes cloud-native.
- Loki e Tempo reduzem complexidade operacional no MVP e integram bem com Grafana e correlação por `trace_id`.
- Datadog, New Relic, AWS CloudWatch ou stacks equivalentes podem ser avaliados depois, mas não devem substituir a padronização de instrumentação via OpenTelemetry.

### Dashboards técnicos internos no MVP

- Saúde geral da plataforma.
- API Gateway/entrada.
- Microsserviços.
- gRPC interno.
- Tracing distribuído.
- Filas, eventos e DLQ.
- Integrações externas.
- Bancos de dados, cache e storage.
- Segurança operacional.
- Auditoria e falhas de registro de evidência.
- Serviço de revisão automatizada por IA.
- Deploys, versões e regressões operacionais.

### Dashboards de negócio internos no MVP

- Funil de decisão.
- Volume por tenant.
- Performance de decisão por produto, política e tenant.
- Políticas e motivos.
- Propostas inconclusivas e revisão automatizada.
- Custo por decisão, tenant, produto e classe de integração.
- Falhas por fornecedor ou classe de integração e impacto no funil.

### Dashboards customer-facing no MVP

Clientes devem ter acesso a uma visão curada de saúde dos serviços e análises do próprio tenant.

- Status de APIs, webhooks, callbacks e integrações configuradas.
- Incidentes ou degradações que afetam o tenant.
- Propostas recebidas, processadas, decididas, aprovadas, recusadas, inconclusivas e aprovadas com alterações.
- Latência p50/p95/p99 por produto e endpoint relevante.
- Taxa de erro, timeouts, retries e indisponibilidade de integrações relevantes.
- Custo estimado ou real por proposta, produto, período e classe de integração.
- Motivos de decisão agregados, sem dados pessoais ou evidências restritas.

### Restrições de exposição

- Clientes não acessam Prometheus, Loki, Tempo, traces crus, logs operacionais ou métricas brutas de infraestrutura.
- Dashboards customer-facing são servidos pelo `Reporting & Insights Service` a partir de projeções curadas por tenant.
- Métricas expostas ao cliente respeitam RBAC/scopes, mascaramento, minimização, retenção e isolamento cross-tenant.
- CPU, memória, pods, filas internas detalhadas, payloads de provedores, segredos, scores brutos restritos e evidências sensíveis não são expostos ao cliente.

### Consequência registrada

Padronizar **OpenTelemetry + Collector + Prometheus + Grafana + Loki + Tempo + Alertmanager** no MVP, mantendo abertura para operação managed ou troca futura de backend sem trocar a instrumentação. Clientes recebem dashboards curados por tenant pelo `Reporting & Insights Service`, separados da observabilidade técnica interna.

## OQ-10: Retenção, mascaramento e descarte

### Decisão registrada

Criar política por classificação de dado e contexto de uso. Máscaras fortes são padrão para logs, traces, dashboards e telemetria; máscaras moderadas são permitidas apenas em telas autorizadas quando houver necessidade legítima de reconhecimento visual; dados completos só podem ser descriptografados ou exibidos com permissão elevada, justificativa e auditoria.

| Classe | Exemplos | Tratamento recomendado |
| --- | --- | --- |
| Identificador direto | CPF, CNPJ, e-mail, telefone | Mascarar por contexto; hashear para correlação; criptografar ou tokenizar em storage quando necessário |
| Dado financeiro sensível | renda, extrato, Open Finance, cartão | Minimizar; armazenar snapshot apenas se necessário |
| Evidência decisória | código de motivo, score, regra, versão | Persistir para auditoria e explicabilidade |
| Log operacional | rota, status, duração, tenant, trace | Retenção menor; sem payload sensível bruto |
| Auditoria | decisão, revisão automatizada, alteração de política | Retenção maior e proteção contra alteração |

### Máscaras por contexto

| Dado | Logs, traces e dashboards | Tela autorizada | Correlação técnica |
| --- | --- | --- | --- |
| CPF | `***.***.***-09` ou omissão | `123.***.***-09` | hash com salt/pepper |
| CNPJ | `**.***.***/****-90` ou omissão | `12.***.***/0001-90` | hash com salt/pepper |
| E-mail | `j***@dominio.com` ou omissão | `jo***@dominio.com` | hash normalizado |
| Telefone | `(**) *****-4321` ou omissão | `(11) *****-4321` | hash normalizado |
| Nome | `J*** S***` ou omissão | `João S***` quando indispensável | evitar correlação por nome |
| Endereço | omissão | cidade/UF ou endereço mascarado | evitar correlação por endereço |
| Conta bancária | `****5-6` ou omissão | `****5-6` | hash/token |
| Cartão | nunca logar | últimos 4 dígitos quando aplicável | token PCI ou equivalente |
| Token, senha, secret, API key | nunca logar | nunca exibir | não aplicável |
| Renda/dado financeiro | faixa ou omissão | faixa ou valor criptografado sob permissão | bucket/agregação |

### Regras de identificação

- O sistema não deve depender de CPF, CNPJ ou e-mail visível para identificação operacional.
- Identificação e suporte devem usar `proposal_id`, `customer_reference`, correlation ID, trace ID, hash seguro do documento/e-mail ou busca exata com permissão elevada.
- Busca por dado original pode existir, mas não deve exibir o valor completo no resultado por padrão.
- Todo acesso a dado completo gera auditoria com usuário, tenant, finalidade, justificativa, recurso, timestamp e resultado.

### Por quê

- LGPD exige finalidade, adequação, necessidade, segurança, prevenção e responsabilização.
- OWASP recomenda remover, mascarar, sanitizar, hashear ou criptografar dados sensíveis em logs.
- Máscara forte demais pode prejudicar suporte e conciliação; por isso a política separa privacidade padrão de reconhecimento visual autorizado.

### Política inicial

Definir política inicial:

- Logs operacionais: 90 dias hot + arquivo conforme contrato, sujeito à validação jurídica/compliance.
- Auditoria de decisão: 5 anos ou prazo contratual/regulatório maior, sujeito à validação jurídica/compliance.
- Payloads sensíveis brutos: não persistir por padrão; armazenar referência, hash ou snapshot minimizado.
- Dados de teste: sempre sintéticos.
- Prazos finais devem ser validados antes de produção por jurídico/compliance por produto, tenant, jurisdição, contrato e tipo de instituição.

## OQ-11: Proteção da auditoria

### Decisão registrada

Usar **banco relacional append-only** como trilha principal de auditoria no MVP, reforçado por hash encadeado, checkpoints assinados, verificação periódica e exportação imutável. Ledger ou database especializada ficam como evolução condicionada a cliente, contrato ou regulação.

### Controles obrigatórios

- Tabela/event store append-only no `Audit & Evidence Service`.
- Escrita normal com permissão apenas de `INSERT`; sem `UPDATE` ou `DELETE` na trilha principal.
- Cada evento grava `previous_hash` e `current_hash`.
- Eventos críticos podem usar HMAC ou assinatura com chave gerenciada.
- Checkpoints periódicos geram digest assinado por lote, tenant ou janela temporal.
- Lotes e checkpoints são exportados para storage imutável/WORM ou equivalente.
- Job periódico verifica cadeia de hashes, ausência de eventos esperados e divergência entre banco e exportação imutável.
- Qualquer leitura, exportação, tentativa administrativa ou falha de gravação na auditoria também gera evento auditável.
- Decisão de crédito não deve ser publicada como final se a gravação de auditoria ou evidência crítica falhar; deve retornar estado técnico controlado.

### Alternativas

| Modelo | Vantagem | Risco |
| --- | --- | --- |
| Append-only em banco relacional | Simples e rápido | Precisa hardening contra alteração administrativa |
| Hash encadeado + export WORM | Boa evidência de alteração | Mais operação e custo |
| Ledger/database especializada | Forte para auditoria | Pode ser prematuro e gerar lock-in |

### Consequência registrada

MVP: **banco append-only + hash encadeado + checkpoints assinados + exportação periódica imutável**; evoluir para ledger somente se cliente, regulação, auditoria externa ou contrato exigir.

## OQ-12: Eventos/mensageria

### Decisão registrada

Usar gRPC para chamadas síncronas internas e NATS JetStream como backbone assíncrono de referência no MVP.

SQS, SNS, Lambda, EventBridge ou serviços AWS equivalentes podem ser usados como complementos quando houver justificativa específica, como integração nativa AWS, tarefa pontual, notificação simples, ponte externa ou redução de custo operacional. Eles não substituem o padrão principal de eventos internos do domínio no MVP.

### Quando usar gRPC

- Consultas internas imediatas.
- Execução síncrona de decisão.
- Validação/normalização que precisa responder dentro da requisição.
- Chamada entre serviços com deadline curto e resposta obrigatória.

### Quando usar eventos

- Auditoria.
- Mudança de status de proposta.
- Publicação de política.
- Callback/webhook.
- Fan-out para reporting.
- Processamento posterior.
- Retry durável.
- DLQ.
- Integração com analytics.

### Padrão obrigatório

- CloudEvents como envelope de evento.
- AsyncAPI para documentação dos contratos assíncronos.
- Outbox pattern para publicar eventos após transação local.
- Inbox ou tabela de idempotência obrigatória em consumidores.
- `tenant_id`, `correlation_id`, `trace_id`, `event_type`, `schema_version` e `occurred_at` em todo evento.
- Integrações externas devem usar jobs/comandos assíncronos, com fan-out/fan-in, competing consumers, DLQ ou equivalente, controle de concorrência e rastreabilidade por integração.
- Fluxos síncronos de decisão podem aguardar resultados externos até `max_wait_ms` ou deadline configurado, mas a execução das integrações externas permanece assíncrona internamente.
- Ordering deve ser garantido por chave de agregado quando necessário, por exemplo `proposal_id`.
- Eventos não substituem auditoria oficial; auditoria crítica continua no `Audit & Evidence Service`.

### Broker de referência

NATS JetStream no MVP:

- Publicadores enviam mensagens para subjects.
- Streams capturam subjects e persistem mensagens.
- Consumers duráveis processam no próprio ritmo.
- Ack explícito confirma processamento.
- Falhas geram reentrega.
- DLQ recebe mensagens após limite de tentativas.
- Replay pode ser usado para reprocessamento controlado.
- Em AWS, a referência inicial é rodar NATS JetStream no EKS com cluster de 3 nós e volumes persistentes criptografados.

### Alternativas consideradas

| Opção | Vantagem | Consequência |
| --- | --- | --- |
| NATS JetStream | Simples, rápido, bom para microsserviços, jobs, replay e consumidores duráveis | Ecossistema analítico menor que Kafka |
| Kafka/Redpanda | Excelente para event streaming, alto volume e replay analítico | Mais operação e custo no MVP |
| RabbitMQ | Ótimo para filas e roteamento | Menos natural para event log/replay |
| SQS/SNS/Lambda | Excelente integração AWS e baixa operação para tarefas pontuais | Lock-in AWS e modelo fragmentado como backbone de domínio |

### Consequência registrada

MVP usa **gRPC para síncrono** e **NATS JetStream para assíncrono**, com CloudEvents, AsyncAPI, transactional outbox, consumidores idempotentes, DLQ, replay e consumers duráveis. Kafka/Redpanda e serviços AWS managed ficam como evolução ou complemento justificado.

MVP usa **eventos para auditoria, reporting, callback e mudanças de status**, com broker definido em ADR.

## Sequência recomendada de decisão

1. Resolvido: ICP são instituições B2B API-first com análise de crédito/risco para CPF e CNPJ.
2. Resolvido: produtos MVP são crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis.
3. Resolvido: contrato canônico de proposta com núcleo comum, `requested_terms`, extensões por produto, decisão automatizada e revisão por IA consultiva.
4. Resolvido: primeiro deploy terá 7 microsserviços, com `Automated Review` separado e `Reporting & Insights` dono da observabilidade de negócio.
5. Resolvido: ownership lógico de dados por serviço, PostgreSQL compartilhado apenas como infraestrutura inicial e isolamento físico progressivo.
6. Resolvido: multi-tenancy começa em `bridge` e evolui para `silo` quando necessário.
7. Resolvido: OIDC/OAuth 2.0, Client Credentials, Authorization Code + PKCE, RBAC/scopes/claims e evolução para ABAC/FAPI.
8. Resolvido: classes de integração por adapters substituíveis, sem fornecedor nominal obrigatório, com modelo de custo por operação.
9. Resolvido: OpenTelemetry + Collector + Prometheus + Grafana + Loki + Tempo + Alertmanager, com dashboards customer-facing curados por tenant.
10. Resolvido: política contextual de retenção, mascaramento e descarte, com máscara forte por padrão e reconhecimento visual autorizado por contexto.
11. Resolvido: banco append-only com hash encadeado, checkpoints assinados, verificação periódica e exportação imutável para auditoria.
12. Resolvido: gRPC síncrono + NATS JetStream assíncrono com CloudEvents, AsyncAPI, transactional outbox, inbox/idempotência, DLQ, replay e consumidores duráveis.

## Fontes consultadas

- Banco Central do Brasil, IF.data: https://www3.bcb.gov.br/ifdata/index.html
- Banco Central do Brasil, Estatísticas monetárias e de crédito: https://www.bcb.gov.br/estatisticas/estatisticasmonetariascredito
- Banco Central do Brasil, Open Finance: https://www.bcb.gov.br/estabilidadefinanceira/openfinance/documentacao
- Banco Central do Brasil, FAQ Open Finance: https://www.bcb.gov.br/meubc/faqs/s/open-finance
- Open Finance Brasil, participantes: https://openfinancebrasil.org.br/quem-participa/
- CVM, dados abertos de informes mensais FIDC: https://dados.cvm.gov.br/dataset/fidc-doc-inf_mensal
- LGPD, Lei nº 13.709/2018: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
- ANPD, materiais e guias: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes
- ANPD, direitos dos titulares: https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares
- ANPD, IA e decisões automatizadas: https://www.gov.br/anpd/pt-br/assuntos/projetos-acoes-iniciativas/sandbox/por-que-inteligencia-artificial
- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
- OWASP API Security Top 10 2023: https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- gRPC Core Concepts: https://grpc.io/docs/what-is-grpc/core-concepts/
- gRPC Deadlines: https://grpc.io/docs/guides/deadlines/
- gRPC Retry: https://grpc.io/docs/guides/retry/
- OpenTelemetry Documentation: https://opentelemetry.io/docs/
- OpenTelemetry Collector: https://opentelemetry.io/pt/docs/collector/
- Azure Architecture Center, tenancy models: https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/tenancy-models
- Azure SQL Database SaaS tenancy patterns: https://learn.microsoft.com/en-us/azure/azure-sql/database/saas-tenancy-app-design-patterns
- AWS SaaS Tenant Isolation Strategies: https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/core-isolation-concepts.html
- AWS Prescriptive Guidance, event-driven architecture: https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-serverless/event-driven-architecture.html
- OpenID Connect Core 1.0: https://openid.net/specs/openid-connect-core-1_0.html
- OAuth 2.0 RFC 6749: https://www.rfc-editor.org/info/rfc6749/
- FAPI 2.0 Security Profile: https://openid.net/specs/fapi-security-profile-2_0.html
- CloudEvents specification: https://github.com/cloudevents/spec
- Microsoft Azure Architecture Center, asynchronous messaging options: https://learn.microsoft.com/en-us/azure/architecture/guide/technology-choices/messaging
- Microsoft Azure Architecture Center, competing consumers pattern: https://learn.microsoft.com/pt-pt/azure/architecture/patterns/competing-consumers
- Microsoft Azure Architecture Center, asynchronous request-reply pattern: https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply
