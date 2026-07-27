# Addendum - PRD CreditOS

Este addendum preserva detalhes de arquitetura, decisões técnicas e próximos documentos derivados. O PRD principal descreve o comportamento e os requisitos de produto; este arquivo captura o que deve alimentar Architecture, ADRs, padrões técnicos e CI/CD.

## Fontes usadas

- `_bmad-output/planning-artifacts/briefs/brief-CreditOS-2026-07-22/brief.md`
- `_bmad-output/planning-artifacts/briefs/brief-CreditOS-2026-07-22/addendum.md`
- `_bmad-output/brainstorming/brainstorm-servico-saas-analise-credito-risco-2026-07-22/brainstorm-premissas-tecnicas.md`
- `_bmad-output/brainstorming/brainstorm-servico-saas-analise-credito-risco-2026-07-22/adendo-microsservicos-logs-observabilidade.md`
- `docs/input/project-technical-premises.md`

## Decisões técnicas já sinalizadas

- Arquitetura alvo baseada em microsserviços orientados a domínios/bounded contexts.
- Todo backend deve seguir Domain-Driven Design, com separação entre domínio, aplicação e infraestrutura.
- A decomposição de microsserviços deve partir de bounded contexts e linguagem ubíqua, não de camadas técnicas.
- Comunicação interna síncrona entre microsserviços via gRPC.
- Eventos continuam necessários para fan-out, processamento assíncrono, retry durável, DLQ, replay, callbacks, reporting e consistência eventual.
- NATS JetStream será o backbone assíncrono de referência do MVP.
- Integrações com serviços externos devem ser assíncronas e paralelizáveis por padrão, com concorrência controlada por tenant, provedor, produto e credencial.
- Fornecedores externos concretos não serão escolhidos no PRD; o MVP deve preparar classes de integração por adapters substituíveis, mocks/sandbox e modelo de custo por operação.
- APIs externas para clientes devem ser definidas separadamente; gRPC interno não implica exposição pública.
- Logs estruturados são obrigatórios em requisições, chamadas internas e integrações externas.
- Dados sensíveis devem ser mascarados, omitidos, tokenizados, criptografados ou hasheados conforme classificação e contexto de uso.
- Máscara forte é padrão em logs e dashboards; máscara moderada é permitida apenas em tela autorizada para reconhecimento visual; dados completos exigem permissão elevada e auditoria.
- Observabilidade deve cobrir métricas técnicas internas, métricas de negócio e dashboards customer-facing curados por tenant.
- OpenTelemetry será o padrão obrigatório de instrumentação; a stack de referência inicial será Grafana OSS com Prometheus, Loki, Tempo e Alertmanager.
- Toda infraestrutura de produção deve ser descrita e reproduzida por Infrastructure as Code.

## ADRs que a Architecture deve produzir ou confirmar

- Microsserviços vs monólito modular.
- Decomposição de domínios e mapa de serviços.
- Estratégia de multi-tenancy.
- Autenticação e autorização.
- Contratos versionados e schemas de proposta.
- Comunicação interna via gRPC.
- Eventos, mensageria e fluxos assíncronos.
- NATS JetStream em AWS/EKS, incluindo sizing, retenção, replicação, storage, backup, DLQ e operação.
- Estratégia de integrações externas assíncronas, paralelização, fan-out/fan-in, DLQ e resultados parciais.
- Logging estruturado, mascaramento e redação.
- Retenção, mascaramento contextual, tokenização, hash seguro e descarte.
- Observabilidade técnica e de negócio.
- Dashboards customer-facing e limites de exposição de telemetria por tenant.
- Auditoria e proteção contra alteração.
- Banco append-only, hash encadeado, checkpoints assinados e exportação imutável para auditoria.
- Governança de modelos de risco e IA.
- Estratégia futura de captura, curadoria e uso de dados para modelos próprios e IA.
- Persistência e ownership de dados por serviço.
- Estratégia de Infrastructure as Code, ambientes, módulos, estados, secrets e automação de isolamento por tenant.

## Domínios candidatos para arquitetura

- Identity & Access.
- Tenant Management.
- Application Intake.
- Data Integration.
- Policy Management.
- Decision Engine.
- Risk Scoring.
- Fraud Analysis.
- Automated Review.
- Audit & Evidence.
- Reporting & Insights.
- Notification.

## Contrato inicial de proposta - OQ-3

Arquivo detalhado: `contrato-inicial-proposta-oq3.md`.

- O contrato público será canônico, versionado e fechado por schema.
- `tenant_id` não será fonte confiável no body; o tenant vem de autenticação, token, chave de API ou contexto de rota.
- `document_type` permanece no contrato externo para clareza e extensibilidade, mesmo sendo derivável de `person_type` no Brasil.
- `selected_plan` e `plan_id` não entram no MVP; o cliente envia somente `operation.requested_terms`.
- Revisão manual, fila manual e override humano ficam fora do MVP.
- Revisão por IA, quando configurada, será automatizada e consultiva; decisão final exige política versionada, códigos de motivo e auditoria.
- `decision_options` deve usar `review_strategy` e `fallback_action`, não `allow_manual_review`.
- `consents` deve usar `subject_ref`, evitando repetição de CPF/CNPJ quando o titular for `borrower` ou um participante referenciado.

## Integrações externas - OQ-8

Arquivo detalhado: `integracoes-externas-oq8.md`.

- O MVP não escolhe fornecedores externos nominais no PRD.
- Classes prioritárias: KYC/KYB, bureau, antifraude, recebíveis/lastro, Open Finance condicional e webhooks/notificações.
- O custo operacional deve ser modelado por classe de integração, com custo estimado antes da escolha de fornecedor e custo real quando fornecedor estiver configurado.
- Fornecedores reais serão definidos por caso comercial, parceiro, homologação, requisito regulatório ou necessidade operacional.

## Observabilidade - OQ-9

Arquivo detalhado: `observabilidade-oq9.md`.

- OpenTelemetry será o padrão obrigatório de instrumentação.
- Stack de referência MVP: OpenTelemetry Collector, Prometheus, Grafana, Loki, Tempo e Alertmanager.
- Observabilidade técnica interna e dashboards customer-facing devem ser separados.
- Clientes acessam somente projeções curadas por tenant pelo `Reporting & Insights Service`, nunca telemetria bruta de infraestrutura, logs crus ou traces internos.

## Retenção, mascaramento e descarte - OQ-10

Arquivo detalhado: `retencao-mascaramento-descarte-oq10.md`.

- A política deve ser definida por classe de dado e contexto de uso.
- Máscara forte é padrão para logs, traces, dashboards e telemetria.
- Máscara moderada é permitida em telas autorizadas quando reconhecimento visual for necessário.
- O sistema deve usar `proposal_id`, `customer_reference`, correlation ID, hash seguro ou busca exata autorizada para identificação operacional, não CPF/CNPJ/e-mail visíveis.
- Dados completos só podem ser exibidos ou descriptografados com permissão elevada, justificativa e auditoria.

## Proteção da auditoria - OQ-11

Arquivo detalhado: `protecao-auditoria-oq11.md`.

- O MVP usará banco relacional append-only como trilha principal de auditoria.
- A trilha será reforçada por hash encadeado, checkpoints assinados, verificação periódica e exportação imutável.
- Escrita normal deve permitir apenas `INSERT`; `UPDATE` e `DELETE` são proibidos na trilha principal.
- Decisões de crédito não devem ser publicadas como finais se evidência ou auditoria crítica falhar.
- Ledger/database especializada ficam como evolução condicionada a cliente, contrato, auditoria externa ou regulação.

## Infrastructure as Code

Arquivo detalhado: `infrastructure-as-code-backlog.md`.

- Toda infraestrutura de produção deve ser provisionada por IaC.
- IaC deve cobrir rede, Kubernetes, bancos, mensageria, observabilidade, storage imutável, KMS/secrets, IAM e políticas de segurança.
- Desenvolvimento dos módulos IaC deve entrar no backlog final do projeto, antes da preparação de produção.
- IaC também deve suportar evolução de multi-tenancy de `bridge` para `silo`.

## Eventos e mensageria - OQ-12

Arquivo detalhado: `eventos-mensageria-oq12.md`.

- gRPC permanece o padrão para chamadas síncronas internas com resposta imediata.
- NATS JetStream será o backbone assíncrono de referência do MVP.
- Eventos usam CloudEvents; contratos assíncronos usam AsyncAPI.
- Publicação confiável usa transactional outbox; consumo confiável usa inbox/idempotência.
- SQS, SNS, Lambda e EventBridge podem ser usados como complementos AWS com justificativa específica, mas não substituem o backbone principal de eventos internos do domínio no MVP.

## Padrões técnicos a criar

- Padrão de API pública: versionamento, erros, paginação, idempotência e correlation ID.
- Padrão gRPC interno: protobuf, versionamento, deadlines, retries, circuit breaker, propagação de contexto e testes de contrato.
- Padrão de eventos: CloudEvents, AsyncAPI, subjects, streams, tenant, correlation ID, trace ID, idempotência, DLQ, replay, reprocessamento, consumers duráveis e compatibilidade.
- Padrão de logging: campos mínimos, mascaramento contextual, classificação de dados e proibição de payload sensível bruto.
- Padrão de privacidade de dados: classificação, base legal, finalidade, owner, retenção, descarte, criptografia, tokenização, hash seguro, busca exata autorizada e auditoria de acesso.
- Padrão de observabilidade: métricas, logs, traces, dashboards, alertas, SLOs, taxonomia técnica, taxonomia de negócio e exposição customer-facing segura.
- Padrão de auditoria: eventos obrigatórios, evidências, retenção, banco append-only, hash encadeado, checkpoints assinados, exportação imutável, proteção contra alteração e consulta.
- Padrão de integrações externas: adapters, sandbox/mock, jobs assíncronos, fan-out/fan-in, concorrência controlada, timeout, retry, fallback, DLQ, resultados parciais, métricas e logs seguros.
- Padrão de custos de integração: custo estimado, custo real quando houver fornecedor configurado, tentativas, fallback, limites por tenant/produto/proposta e projeções para dashboards de negócio.
- Padrão de testes: unitários, integração, contrato, E2E, segurança e performance.
- Padrão DDD backend: agregados, entidades, value objects, domain services, application services, repositories, domain events, anti-corruption layers e isolamento de infraestrutura.
- Padrão de dados para IA: minimização, anonimização/pseudonimização, segregação por tenant, versionamento de datasets, feature lineage, consentimento/base legal, avaliação de viés, explicabilidade e rollback.
- Padrão de IaC: módulos reutilizáveis, estado remoto protegido, revisão em pull request, validação, plano de mudança, ambientes separados, secrets fora do código e drift detection.

## Backlog futuro de dados, modelos próprios e IA

Arquivo detalhado sugerido: `dados-modelos-ia-backlog-final.md`.

- A captura de dados para modelos próprios e IA não entra como capacidade operacional do MVP, exceto evidências necessárias à decisão e revisão automatizada consultiva.
- O processo futuro deve consumir eventos, decisões, features calculadas e resultados de política já minimizados.
- Identificadores diretos sensíveis, como CPF, nome, rua, telefone, e-mail, documentos e credenciais, não devem ser incluídos em datasets analíticos por padrão.
- Dados pseudonimizados ou anonimizados devem preservar utilidade estatística sem permitir reidentificação indevida.
- A Architecture deve decidir se essa capacidade será um domínio futuro separado, como `Data & Model Governance`, ou parte de uma plataforma analítica isolada.

## Quality gates sugeridos

- Lint, formatação e tipagem.
- Testes unitários para domínio, políticas, cálculo e motor de decisão.
- Testes de integração para banco, migrations, autenticação, autorização, integrações e comunicação entre serviços.
- Testes de contrato para APIs, gRPC, eventos, schemas, webhooks e provedores externos.
- Testes de segurança para autenticação ausente, token inválido, permissão insuficiente, cross-tenant, enumeração, rate limiting, replay e idempotência.
- Verificação de logs contra dados sensíveis.
- Verificação de cobertura mínima por criticidade.
- Build de imagens e análise de vulnerabilidades.

## Notas para UX

- UX visual completa ainda não é o foco, mas dashboards, administração de políticas, evidências de decisão e acompanhamento de propostas inconclusivas provavelmente exigirão especificação de telas.
- Personas de operação, risco, compliance e engenharia cliente devem ser detalhadas antes de desenhar fluxos.
- Dashboards devem separar visão interna da plataforma e visão por tenant.

## Memlog audit

- Capturado no PRD: visão, usuários, jornadas, glossário, funcionalidades, FRs, NFRs, integrações, governança, não objetivos, MVP, métricas, riscos e questões abertas.
- Capturado neste addendum: decisões técnicas, ADRs, domínios candidatos, padrões, gates e notas para UX/Architecture.
- Decidido nesta iteração: ICP inicial inclui instituições B2B API-first que operam crédito/risco para CPF e CNPJ; MVP inclui crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis.
- Decidido nesta iteração: contrato inicial de proposta usa núcleo canônico, `requested_terms`, extensões por produto, `subject_ref` em consentimentos, sem `selected_plan`, sem fila manual e com revisão por IA apenas consultiva.
- Decidido nesta iteração: backend deve seguir DDD; processo de dados para modelos próprios e IA fica no backlog final, sem identificadores diretos sensíveis por padrão.
- Decidido nesta iteração: `Automated Review Service` entra no MVP como microsserviço separado.
- Decidido nesta iteração: integrações externas devem ser assíncronas e paralelizáveis no `Integration Service`, com limites de concorrência, resultados parciais e resiliência.
- Decidido nesta iteração: OQ-4 fechada com 7 microsserviços no primeiro deploy; `Reporting & Insights` é dono da observabilidade de negócio, observabilidade técnica é transversal e auditabilidade pertence a `Audit & Evidence`.
- Decidido nesta iteração: OQ-5 fechada com ownership lógico por serviço, database/schema/usuário separados no MVP, proibição de joins cross-service e evolução para isolamento físico quando necessário.
- Decidido nesta iteração: OQ-6 fechada com modelo `bridge` no MVP e evolução para `silo` conforme risco, volume, contrato, região, performance ou compliance.
- Decidido nesta iteração: OQ-7 fechada com OIDC/OAuth 2.0, Client Credentials para M2M, Authorization Code + PKCE para usuários humanos, RBAC/scopes/claims no MVP e evolução para ABAC/FAPI.
- Decidido nesta iteração: OQ-8 fechada sem escolha de fornecedores nominais; o MVP prioriza classes de integração por adapters substituíveis, mocks/sandbox e modelo de custo por operação.
- Decidido nesta iteração: OQ-9 fechada com OpenTelemetry como padrão obrigatório, stack Grafana OSS de referência no MVP e dashboards customer-facing curados por tenant via `Reporting & Insights Service`.
- Decidido nesta iteração: OQ-10 fechada com política contextual de retenção, mascaramento e descarte; máscara forte por padrão, máscara moderada apenas em telas autorizadas, dado completo somente com permissão elevada e auditoria.
- Decidido nesta iteração: OQ-11 fechada com banco append-only, hash encadeado, checkpoints assinados, verificação periódica e exportação imutável para auditoria.
- Decidido nesta iteração: infraestrutura de produção deve ter Infrastructure as Code; desenvolvimento dos módulos IaC entra no backlog final do projeto.
- Decidido nesta iteração: OQ-12 fechada com gRPC para síncrono e NATS JetStream como backbone assíncrono de referência do MVP.
- Definido como pendente: não há questões abertas principais restantes de OQ-1 a OQ-12; próximos passos pertencem a Architecture, ADRs, PRD review e validações de compliance.
- Decidido nesta iteração: revisão/consolidação do PRD removeu assumptions já decididas, alinhou pendências restantes como validações externas e preparou o handoff para Architecture/ADRs.
