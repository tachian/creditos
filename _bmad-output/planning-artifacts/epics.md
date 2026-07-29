---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - "_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md"
  - "_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md"
  - "_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/revisao-consolidacao-prd-2026-07-27.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md"
  - "_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/handoffs/legal-contractual-validation-final-task.md"
  - "_bmad-output/specs/spec-CreditOS/SPEC.md"
  - "_bmad-output/specs/spec-CreditOS/capability-map.md"
  - "_bmad-output/specs/spec-CreditOS/quality-constraints.md"
---

# CreditOS - Decomposição de Épicos

## Visão Geral

Este documento consolida o inventário de requisitos para decompor o CreditOS em épicos e histórias implementáveis. A extração usa o PRD, addendum, revisão consolidada, Architecture Spine, tarefa jurídica final e SPEC canônico como fontes de entrada. O contrato UX formal não foi incluído nesta rodada por decisão do projeto; ele será produzido posteriormente com `bmad-ux` e deverá refinar dashboards, jornadas administrativas, consulta de decisões e visualização de evidências.

## Inventário de Requisitos

### Requisitos Funcionais

- **FR-1:** Autenticar chamadas de API para clientes técnicos e usuários humanos conforme credenciais válidas.
- **FR-2:** Autorizar operações por usuário, papel, permissão, tenant, recurso e contexto.
- **FR-3:** Gerenciar tenants com identificador único, status, configuração mínima, métricas e logs associados.
- **FR-4:** Receber propostas por contrato versionado, com tenant resolvido pela plataforma, produto MVP e schema aprovado.
- **FR-5:** Validar e normalizar proposta, incluindo campos obrigatórios, tipos, datas, valores monetários e consistência mínima.
- **FR-6:** Garantir idempotência na submissão de proposta para evitar duplicidade e detectar payload incompatível.
- **FR-7:** Configurar fontes de dados por tenant e produto, com auditoria de configurações relevantes.
- **FR-8:** Executar integrações externas de forma assíncrona, paralelizável e resiliente pelo `Integration Service`.
- **FR-9:** Usar sandbox ou mock para integrações em ambientes não produtivos e testes de contrato.
- **FR-10:** Criar e versionar políticas de crédito com regras, critérios, fatores, limites e metadados.
- **FR-11:** Publicar política aprovada para uso por produto, tenant ou contexto configurado.
- **FR-12:** Simular política antes de publicação sem alterar decisões reais e respeitando mascaramento.
- **FR-13:** Executar decisão automática determinística para propostas validadas quando critérios forem suficientes.
- **FR-14:** Tratar proposta inconclusiva sem fila manual, usando `fallback_action` controlado.
- **FR-15:** Retornar explicabilidade da decisão com códigos de motivo, fatores relevantes, regras acionadas e versões.
- **FR-16:** Executar revisão automatizada consultiva por IA quando configurada por política.
- **FR-17:** Registrar resultado da revisão automatizada como evidência consultiva vinculada à proposta.
- **FR-18:** Impedir decisão final autônoma por IA generativa sem política determinística, validação formal e governança.
- **FR-19:** Registrar auditoria de decisões com tenant, proposta, solicitante, versões, resultado, justificativas e correlation ID.
- **FR-20:** Registrar auditoria de alterações sensíveis em política, modelo, agente de IA, permissão, exportação e acesso a dados.
- **FR-21:** Registrar logs estruturados de requisições com campos mínimos de rastreabilidade e mascaramento.
- **FR-22:** Registrar logs de integrações internas e externas com origem, destino, contrato, tenant, trace, status, tentativas e timeout.
- **FR-23:** Expor dashboards técnicos para saúde da plataforma, APIs, microsserviços, tracing, bancos, filas, integrações, segurança e deploys.
- **FR-24:** Expor dashboards de negócio internos e customer-facing por tenant via `Reporting & Insights Service`.
- **FR-25:** Consultar decisão por proposta, respeitando tenant, permissões, contrato versionado e minimização de dados.
- **FR-26:** Enviar callbacks ou webhooks assinados, versionados, idempotentes e com retry controlado.

### Requisitos Não Funcionais

- **NFR-1:** Todo endpoint exige autenticação por padrão, exceto endpoints explicitamente aprovados como públicos.
- **NFR-2:** Toda operação sensível valida usuário, tenant, papel, permissão, recurso e contexto.
- **NFR-3:** Nenhum `tenant_id` recebido no payload é fonte de verdade sem validação contra identidade autenticada.
- **NFR-4:** Respostas de API não expõem stack trace, mensagens internas de banco, nomes de tabela, tokens, secrets ou detalhes de infraestrutura.
- **NFR-5:** Autenticação e identidade usam OIDC/OAuth 2.0, Client Credentials para clientes técnicos e Authorization Code + PKCE para usuários humanos.
- **NFR-6:** Tokens possuem duração curta, rotação de chaves e validação de `iss`, `aud`, `sub`, `exp`, `iat`, `jti`, scopes e claims de tenant.
- **NFR-7:** Autorização usa RBAC, scopes e claims de tenant no MVP, com evolução planejada para ABAC e avaliação de FAPI 2.0.
- **NFR-8:** Contexto de autenticação/autorização é propagado entre microsserviços via gRPC metadata e eventos.
- **NFR-9:** Logs, traces, dashboards e respostas operacionais não registram nem exibem dados pessoais/sensíveis completos.
- **NFR-10:** Dados de teste são sintéticos.
- **NFR-11:** Dados pessoais ou sensíveis persistidos possuem `data_class`, finalidade, base legal, owner, retenção, descarte e política de mascaramento antes de produção.
- **NFR-12:** Toda entidade pertencente a cliente possui contexto de tenant.
- **NFR-13:** Isolamento entre tenants cobre dados, cache, eventos, filas, arquivos, logs, métricas, relatórios, jobs, notificações e integrações.
- **NFR-14:** Testes demonstram que um tenant não acessa dados de outro.
- **NFR-15:** O MVP adota modelo `bridge`, com serviços compartilhados e isolamento por tenant ou grupo controlado de tenants em dados e recursos críticos.
- **NFR-16:** Todo tenant possui `tenant_isolation_tier`, inicialmente `bridge`, com evolução para `silo` quando necessário.
- **NFR-17:** O sistema mantém catálogo de tenant para localizar dados, credenciais, limites, configurações, recursos dedicados e tier de isolamento.
- **NFR-18:** Cache, filas, DLQs, objetos, jobs, callbacks, secrets, métricas e traces usam chave/contexto de tenant.
- **NFR-19:** APIs críticas declaram timeout, comportamento de retry e meta de latência antes de produção.
- **NFR-20:** Operações de decisão automática possuem SLO de latência definido por fluxo e tipo de integração.
- **NFR-21:** Componentes implantáveis expõem health check e readiness check.
- **NFR-22:** Operações com risco de duplicidade implementam idempotência ou justificativa aprovada.
- **NFR-23:** Fluxos assíncronos usam NATS JetStream no MVP e tratam duplicidade, ordem, retries, DLQ, versionamento, tenant, correlation ID, replay e consumidores duráveis.
- **NFR-24:** Integrações externas críticas possuem processamento assíncrono, paralelização controlada, contingência, idempotência, retry seguro, DLQ ou equivalente e limites por tenant/provedor.
- **NFR-25:** Auditoria é separada de logs operacionais.
- **NFR-26:** Registros de auditoria usam banco append-only no MVP, com proibição de update/delete, hash encadeado, checkpoints assinados, verificação periódica e exportação imutável.
- **NFR-27:** Decisões são reproduzíveis dentro dos limites técnicos, legais e de retenção definidos.
- **NFR-28:** Todos os microsserviços produzem logs estruturados, métricas, traces, health check, readiness check e correlation ID.
- **NFR-29:** Funcionalidades críticas definem métricas técnicas, métricas de negócio, limites esperados e condições de alerta.
- **NFR-30:** Observabilidade preserva mascaramento, minimização e isolamento por tenant.
- **NFR-31:** Dashboards customer-facing usam projeções curadas por tenant e não expõem telemetria bruta, logs crus, traces, payloads, segredos, dados pessoais ou detalhes de outros tenants.
- **NFR-32:** APIs possuem schemas explícitos, validação, respostas e erros padronizados, versionamento, OpenAPI, paginação quando aplicável e correlation ID.
- **NFR-33:** APIs, eventos, webhooks, schemas e integrações externas possuem testes de contrato quando alterados.
- **NFR-34:** Mudanças incompatíveis geram nova versão, período de compatibilidade, plano de migração e documentação.
- **NFR-35:** Todo backend segue Domain-Driven Design, com separação explícita entre domínio, aplicação e infraestrutura.
- **NFR-36:** Microsserviços refletem bounded contexts ou capacidades de domínio, não camadas técnicas ou preferência de ferramenta.
- **NFR-37:** Regras de negócio, políticas, invariantes, entidades, value objects e eventos de domínio não dependem diretamente de frameworks, bancos, provedores externos, HTTP/gRPC ou payloads de terceiros.
- **NFR-38:** Cada microsserviço possui ownership lógico exclusivo dos seus dados desde o início.
- **NFR-39:** No MVP, serviços podem compartilhar cluster PostgreSQL físico, desde que usem database/schema/usuário separados e permissões isoladas.
- **NFR-40:** Joins, queries e transações diretas cross-service são proibidos.
- **NFR-41:** `Audit & Evidence` possui isolamento reforçado e caminho de evolução para storage separado, append-only, hash encadeado e exportação imutável.
- **NFR-42:** `Reporting & Insights` usa banco de leitura/projeções alimentado por eventos ou pipelines autorizados.

### Requisitos Adicionais de Arquitetura

- O primeiro deploy possui exatamente sete microsserviços de domínio: `Identity & Tenant`, `Proposal Intake`, `Decision`, `Automated Review`, `Integration`, `Audit & Evidence` e `Reporting & Insights`.
- O backend usa Python 3.13 como baseline, FastAPI para APIs públicas, Pydantic v2 para DTOs/schemas de borda, gRPC Python + protobuf para chamadas internas, PostgreSQL com SQLAlchemy 2.x/Alembic 1.x, pytest/pytest-asyncio, Ruff, Pyright progressivo, OpenTelemetry Python e `uv` workspace com lock único.
- A estrutura base do repositório deve incluir `services/`, `packages/`, `tests/`, `infra/`, `docs/` e `scripts/`, com uma imagem por serviço implantável.
- Cada microsserviço deve materializar DDD + arquitetura hexagonal com `domain`, `application`, `adapters` e `bootstrap`; o domínio não pode depender de FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, Redis, OpenTelemetry, provedores externos ou Kubernetes.
- Bibliotecas compartilhadas em `packages/` só podem conter contratos, observabilidade, segurança, testes e utilidades técnicas genéricas; domínio não é compartilhado entre bounded contexts.
- APIs públicas usam HTTP/JSON + OpenAPI versionado; gRPC não é exposto publicamente por padrão.
- Contratos públicos aceitam apenas schemas versionados e aprovados para CPF/CNPJ e produtos MVP: crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis.
- Eventos usam CloudEvents v1.0.2 e contratos assíncronos usam AsyncAPI 3.1.0.
- Publicação confiável usa transactional outbox por serviço produtor; consumo confiável usa inbox/idempotência por consumidor.
- Fluxos síncronos internos com resposta imediata usam gRPC com deadlines, metadata de contexto e testes de compatibilidade.
- Fluxos assíncronos, integrações externas, callbacks, reporting, DLQ, replay e fan-out/fan-in usam NATS JetStream.
- NATS JetStream roda no EKS como cluster de referência de três nós, com streams críticos `Replicas: 3`, storage `file`, EBS gp3 criptografado por KMS, anti-affinity, backup/restore e runbooks.
- Integrações externas são ownership exclusivo do `Integration`, com adapters substituíveis, anti-corruption layer, fan-out/fan-in, deadlines, retry seguro, DLQ, replay, resultado parcial explícito e custo estimado/real.
- Classes MVP de integração incluem KYC/KYB, bureau/restritivos, antifraude, recebíveis/lastro, Open Finance/fonte autorizada e webhooks/callbacks.
- Fornecedores externos nominais não são escolhidos nesta etapa; cada adapter exige mock/sandbox, contrato versionado, testes de contrato, observabilidade e critérios de substituição.
- `Automated Review` é serviço separado e único autorizado a falar com provedores/modelos de IA; IA é consultiva e não decide crédito final.
- Entradas e saídas de IA exigem allowlist, minimização, mascaramento, schema validation, guardrails, auditoria, versionamento de prompt/configuração, custo, latência e fallback.
- `Decision` é o único dono de políticas, versões publicadas, execução determinística, decisão final, termos aprovados e reason codes.
- Políticas publicadas são imutáveis; correção ocorre por nova versão, com validação, simulação/regressão, aprovação, vigência e rollback/roll-forward.
- `Audit & Evidence` é trilha oficial de auditoria; logs, traces, métricas e eventos não substituem auditoria oficial.
- Auditoria usa append-only, `previous_hash`, `current_hash`, checkpoints assinados, verificação periódica e exportação para S3 Object Lock/WORM.
- Produção inicial usa AWS com Amazon EKS em subnets privadas multi-AZ, RDS/Aurora PostgreSQL, KMS, Secrets Manager, EKS Pod Identity, S3 Object Lock, network policies default-deny e tráfego interno privado.
- Produção usa Istio Ambient Mesh como baseline de service mesh para mTLS e autorização service-to-service no EKS.
- Observabilidade usa OpenTelemetry Collector, Prometheus, Loki, Tempo, Grafana e Alertmanager como stack de referência MVP.
- Observabilidade técnica é transversal; observabilidade de negócio e dashboards customer-facing pertencem ao `Reporting & Insights` por eventos/projeções, não por consulta direta a telemetria bruta.
- CI/CD usa GitHub Actions com OIDC para AWS, Amazon ECR, Sigstore/Cosign, GitHub Artifact Attestations, Argo CD, Kyverno e SLSA Build L2 inicial.
- Deploys usam artefatos imutáveis por digest, sem rebuild em produção, com promoção `dev` → `staging` → `prod`, aprovação explícita para produção, smoke tests, SLO watch e rollback/roll-forward.
- Produção inicial é single-region multi-AZ; multi-região active-active fica fora do MVP.
- SLOs internos MVP incluem API pública 99,9% mensal interno, submissão de proposta `p95 <= 500 ms`, decisão assíncrona `p95 <= 60 s` sob condições de timeout, auditoria crítica `p99 <= 300 ms` ou falha controlada e reporting `p95 <= 5 min`.
- Feature flags usam OpenFeature, contexto por tenant, owner, expiração, default seguro, auditoria e plano de remoção.
- Toda infraestrutura de produção deve ser provisionada por IaC com PR, plano, validação, scan, estado remoto protegido, apply controlado e drift detection.
- LGPD operacional usa modelo híbrido: tenant como controlador dos dados/decisão de crédito, CreditOS como operador para análise em nome do tenant e controlador independente apenas para operação SaaS própria sem identificadores.
- Validação jurídica/contratual final é gate obrigatório antes de produção com cliente real, incluindo DPA, RACI, catálogo jurídico de dados, bases legais, retenção/descarte, suboperadores, RIPD, incidentes e comunicações.
- O contrato UX formal fica fora desta etapa e deverá ser produzido posteriormente com `bmad-ux`.

### Requisitos de Design UX

- Não há contrato UX formal incluído nesta rodada.
- Stories relacionadas a dashboards, portal do cliente, visualização de decisão, evidências permitidas e administração devem ser marcadas como dependentes de refinamento futuro por `bmad-ux`.

### Mapa de Cobertura de FR

FR-1: Epic 1 - Autenticação de APIs para clientes técnicos e usuários humanos.
FR-2: Epic 1 - Autorização por usuário, papel, permissão, tenant, recurso e contexto.
FR-3: Epic 1 - Gestão de tenants, status, configurações mínimas e contexto de isolamento.
FR-4: Epic 2 - Submissão de propostas por contrato versionado para CPF/CNPJ e produtos MVP.
FR-5: Epic 2 - Validação e normalização dos dados da proposta.
FR-6: Epic 2 - Idempotência da submissão de propostas.
FR-7: Epic 3 - Configuração de fontes de dados por tenant e produto.
FR-8: Epic 3 - Execução assíncrona, paralelizável e resiliente de integrações externas.
FR-9: Epic 3 - Uso de sandbox ou mock para integrações externas.
FR-10: Epic 4 - Criação e versionamento de políticas de crédito.
FR-11: Epic 4 - Publicação de políticas aprovadas.
FR-12: Epic 4 - Simulação de políticas antes da publicação.
FR-13: Epic 4 - Execução de decisão automática determinística.
FR-14: Epic 4 - Tratamento de propostas inconclusivas sem fila manual.
FR-15: Epic 4 - Retorno de explicabilidade da decisão.
FR-16: Epic 5 - Execução de revisão automatizada consultiva por IA.
FR-17: Epic 5 - Registro da revisão automatizada como evidência consultiva.
FR-18: Epic 5 - Bloqueio de decisão final autônoma por IA generativa.
FR-19: Epic 6 - Auditoria oficial de decisões.
FR-20: Epic 6 - Auditoria de alterações sensíveis.
FR-21: Epic 6 - Logs estruturados de requisições com rastreabilidade e mascaramento.
FR-22: Epic 6 - Logs de integrações internas e externas.
FR-23: Epic 7 - Dashboards técnicos para operação da plataforma.
FR-24: Epic 7 - Dashboards de negócio internos e customer-facing por tenant.
FR-25: Epic 8 - Consulta de decisão por proposta.
FR-26: Epic 8 - Callbacks/webhooks e validação E2E com integrações mockadas.

## Lista de Épicos

### Epic 1: Acesso Seguro e Gestão de Tenants
Usuários e clientes técnicos conseguem operar em tenants isolados, com autenticação, autorização e contexto confiável.
**FRs cobertos:** FR-1, FR-2, FR-3

**Notas de implementação:** Deve preservar `deny-by-default`, OIDC/OAuth 2.0, Client Credentials, Authorization Code + PKCE, RBAC/scopes/claims de tenant, propagação de contexto por gRPC metadata/eventos e testes negativos cross-tenant.

### Epic 2: Submissão Governada de Propostas
Clientes técnicos conseguem submeter propostas CPF/CNPJ dos produtos MVP por contratos versionados, com validação, normalização e idempotência.
**FRs cobertos:** FR-4, FR-5, FR-6

**Notas de implementação:** Deve aceitar apenas schemas versionados e aprovados para crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis, sem payload arbitrário, `selected_plan` ou `plan_id` externo.

### Epic 3: Enriquecimento Assíncrono por Integrações
A plataforma consegue configurar e executar integrações externas por tenant/produto com adapters, mocks, paralelização, resiliência e custos rastreáveis.
**FRs cobertos:** FR-7, FR-8, FR-9

**Notas de implementação:** Deve preservar ownership do `Integration Service`, adapters substituíveis, mocks/sandbox, fan-out/fan-in, deadlines, retry seguro, DLQ, resultados parciais, limites por tenant/provedor e custo estimado/real.

### Epic 4: Políticas e Decisão Explicável
Gestores conseguem criar, simular, publicar políticas, e clientes recebem decisões determinísticas explicáveis, inclusive estados inconclusivos controlados.
**FRs cobertos:** FR-10, FR-11, FR-12, FR-13, FR-14, FR-15

**Notas de implementação:** `Decision` permanece dono de políticas, versões publicadas, execução determinística, decisão final, termos aprovados e reason codes. Decisões devem ser rastreáveis, auditáveis e não depender diretamente de payloads proprietários de fornecedores.

### Epic 5: Revisão Automatizada Consultiva por IA
A plataforma executa revisão por IA como evidência consultiva, com guardrails, versionamento, auditoria e sem autonomia para decisão final.
**FRs cobertos:** FR-16, FR-17, FR-18

**Notas de implementação:** `Automated Review` é serviço separado e único autorizado a falar com provedores/modelos de IA. A IA pode sugerir lacunas, inconsistências e fatores, mas não aprova, reprova, altera termos, executa ação externa ou publica decisão final.

### Epic 6: Auditoria, Evidências e Rastreabilidade
Decisões, alterações sensíveis, requisições e integrações ficam rastreáveis com auditoria oficial, logs estruturados, mascaramento e integridade verificável.
**FRs cobertos:** FR-19, FR-20, FR-21, FR-22

**Notas de implementação:** Auditoria oficial fica separada dos logs operacionais, com append-only, hash encadeado, checkpoints assinados e exportação imutável. Logs e traces devem preservar mascaramento, minimização, correlation ID, trace ID e contexto de tenant.

### Epic 7: Observabilidade e Dashboards por Tenant
Operadores e clientes autorizados acompanham saúde técnica, funil de decisão, volumes, custos, integrações, incidentes e métricas curadas por tenant.
**FRs cobertos:** FR-23, FR-24

**Notas de implementação:** Observabilidade técnica é transversal e usa OpenTelemetry/Grafana OSS como referência. Observabilidade de negócio e dashboards customer-facing pertencem ao `Reporting & Insights`, usando projeções curadas por tenant, sem expor telemetria bruta ou dados sensíveis.

### Epic 8: Acesso à Decisão, Notificações e Validação E2E
Clientes conseguem consultar decisões, receber callbacks/webhooks e validar um fluxo completo de análise usando integrações externas mockadas.
**FRs cobertos:** FR-25, FR-26

**Notas de implementação:** Deve incluir uma story final obrigatória chamada **Fluxo E2E de Análise com Integrações Mockadas**, validando submissão da proposta, mocks externos, decisão, auditoria, logs, métricas, consulta e/ou callback.

## Epic 1: Acesso Seguro e Gestão de Tenants

Usuários e clientes técnicos conseguem operar em tenants isolados, com autenticação, autorização e contexto confiável.

### Story 1.1: Cadastro Mínimo de Tenants

As a operador da plataforma,
I want criar e consultar tenants com status e tier de isolamento,
So that todas as operações futuras tenham um contexto confiável de tenant.

**Acceptance Criteria:**

**Given** um operador autorizado
**When** ele cria um tenant com nome, status e `tenant_isolation_tier`
**Then** o tenant é persistido com identificador único
**And** o status inicial e o tier `bridge` são registrados.

**Given** uma consulta por tenant existente
**When** o serviço recebe o identificador do tenant
**Then** retorna os metadados mínimos do tenant
**And** não expõe dados de outro tenant.

### Story 1.2: Autenticação M2M com Resolução de Tenant

As a cliente técnico,
I want autenticar chamadas de API via Client Credentials,
So that minhas requisições sejam associadas ao tenant correto sem confiar no body.

**Acceptance Criteria:**

**Given** uma requisição com token válido
**When** a API valida o token
**Then** resolve o tenant pelo contexto autenticado
**And** ignora qualquer `tenant_id` não confiável no payload.

**Given** uma requisição sem token, token expirado ou audiência inválida
**When** a API recebe a chamada
**Then** rejeita com erro padronizado
**And** não expõe detalhes internos.

### Story 1.3: Autorização por RBAC, Scopes e Claims de Tenant

As a serviço de domínio,
I want validar permissões antes de executar operações sensíveis,
So that usuários ou clientes técnicos não acessem recursos indevidos.

**Acceptance Criteria:**

**Given** um sujeito autenticado sem scope necessário
**When** ele tenta executar operação sensível
**Then** a operação é rejeitada com erro padronizado
**And** o evento é registrado para rastreabilidade.

**Given** um sujeito de um tenant
**When** ele tenta acessar recurso de outro tenant
**Then** a operação é bloqueada
**And** o teste negativo cross-tenant passa.

### Story 1.4: Propagação de Contexto Confiável entre Serviços

As a microsserviço CreditOS,
I want propagar tenant, sujeito, scopes, correlation ID e trace ID,
So that chamadas internas e eventos sejam rastreáveis e autorizáveis.

**Acceptance Criteria:**

**Given** uma chamada interna gRPC
**When** o serviço chama outro microsserviço
**Then** envia metadata com tenant, sujeito, scopes, correlation ID e trace ID
**And** o serviço receptor valida o contexto antes do caso de uso.

**Given** um evento publicado
**When** ele é emitido para fluxo assíncrono
**Then** inclui contexto mínimo autorizado de tenant e correlação
**And** não carrega payload sensível bruto.

### Story 1.5: Gates de Segurança e Isolamento do Epic 1

As a equipe de engenharia,
I want testes e gates de autenticação, autorização e isolamento,
So that o acesso seguro seja validado antes de avançar para propostas reais.

**Acceptance Criteria:**

**Given** a suíte de testes do Epic 1
**When** os testes são executados
**Then** cobre token ausente, token inválido, permissão insuficiente e acesso cross-tenant
**And** falhas críticas impedem merge.

**Given** logs gerados durante autenticação/autorização
**When** os testes de segurança verificam os registros
**Then** não encontram tokens, secrets ou dados sensíveis completos
**And** correlation ID e tenant aparecem quando aplicável.

## Epic 2: Submissão Governada de Propostas

Clientes técnicos conseguem submeter propostas CPF/CNPJ dos produtos MVP por contratos versionados, com validação, normalização e idempotência.

### Story 2.1: Definição do Contrato Canônico de Proposta

As a cliente técnico,
I want enviar propostas em um contrato público versionado,
So that a integração seja previsível e não dependa de payload arbitrário.

**Acceptance Criteria:**

**Given** um schema versionado aprovado
**When** o cliente envia uma proposta CPF ou CNPJ de produto MVP
**Then** o payload é validado contra o schema
**And** produtos fora do MVP ou schema desconhecido são rejeitados com erro padronizado.

**Given** campos como `selected_plan`, `plan_id` ou payload livre sem dono
**When** eles aparecem na submissão
**Then** o sistema rejeita a submissão com erro padronizado
**And** registra o motivo sem expor dado sensível.

### Story 2.2: Validação e Normalização da Proposta

As a `Proposal Intake Service`,
I want validar e normalizar campos recebidos,
So that os demais serviços recebam uma proposta canônica e consistente.

**Acceptance Criteria:**

**Given** uma proposta com campos obrigatórios válidos
**When** o intake processa a submissão
**Then** normaliza datas em UTC/ISO 8601, valores monetários sem ponto flutuante binário e identificadores conforme contrato
**And** persiste apenas a representação canônica necessária.

**Given** uma proposta com campo obrigatório ausente, tipo inválido ou inconsistência mínima
**When** o intake valida o payload
**Then** retorna erro padronizado
**And** não registra dados sensíveis em claro na mensagem de erro ou log.

### Story 2.3: Submissão Idempotente de Propostas

As a cliente técnico,
I want reenviar uma proposta com `idempotency_key`,
So that falhas de rede não criem propostas duplicadas.

**Acceptance Criteria:**

**Given** uma submissão válida com `idempotency_key` inédita
**When** o intake recebe a proposta
**Then** cria uma única proposta
**And** associa a chave ao tenant, cliente técnico e payload canônico.

**Given** a mesma `idempotency_key` com payload equivalente
**When** o cliente reenvia a requisição
**Then** o sistema retorna o resultado documentado da submissão original
**And** não cria nova proposta.

**Given** a mesma `idempotency_key` com payload incompatível
**When** o cliente reenvia a requisição
**Then** o sistema retorna erro controlado
**And** registra a tentativa para rastreabilidade.

### Story 2.4: Status Inicial e Evento de Proposta Submetida

As a plataforma CreditOS,
I want registrar o status inicial e publicar evento de proposta submetida,
So that decisão, auditoria, reporting e integrações possam continuar o fluxo de forma desacoplada.

**Acceptance Criteria:**

**Given** uma proposta válida e idempotente
**When** o intake conclui a transação local
**Then** registra status inicial da proposta
**And** prepara publicação confiável via outbox.

**Given** a outbox processa a proposta submetida
**When** o evento é publicado
**Then** usa CloudEvents com tenant, proposal ID, schema version, correlation ID e trace context
**And** não inclui payload sensível bruto.

### Story 2.5: Gates de Contrato para Proposal Intake

As a equipe de engenharia,
I want testes de contrato e compatibilidade para submissão de propostas,
So that mudanças em schemas públicos não quebrem clientes nem aceitem payloads indevidos.

**Acceptance Criteria:**

**Given** os contratos OpenAPI/schema de proposta
**When** a suíte de contrato é executada
**Then** valida exemplos válidos e inválidos para CPF, CNPJ e produtos MVP
**And** falha em breaking changes sem nova versão.

**Given** uma tentativa de submissão cross-tenant ou sem contexto autenticado
**When** os testes de segurança rodam
**Then** a proposta é rejeitada
**And** nenhum registro é criado fora do tenant correto.

## Epic 3: Enriquecimento Assíncrono por Integrações

A plataforma configura e executa integrações externas por tenant/produto com adapters, mocks, paralelização, resiliência e custos rastreáveis.

### Story 3.1: Catálogo de Classes de Integração por Tenant e Produto

As a gestor autorizado,
I want configurar classes de integração permitidas por tenant, produto e política,
So that cada análise use apenas fontes autorizadas e governadas.

**Acceptance Criteria:**

**Given** um tenant e produto MVP
**When** uma classe de integração é configurada
**Then** a configuração registra classe, obrigatoriedade, adapter, limites, timeout e fallback
**And** a alteração gera auditoria.

**Given** uma proposta exige integração obrigatória não configurada
**When** o fluxo tenta montar o plano de integração
**Then** retorna estado controlado de configuração ausente
**And** não executa fornecedor/adapters indevidos.

### Story 3.2: Adapter Mock/Sandbox para Integrações Externas

As a equipe de engenharia,
I want adapters mock/sandbox para classes de integração MVP,
So that o fluxo possa ser testado sem depender de fornecedores reais.

**Acceptance Criteria:**

**Given** um ambiente não produtivo
**When** o plano de integração solicita KYC/KYB, bureau, antifraude ou recebíveis
**Then** o `Integration Service` usa adapter mock/sandbox configurado
**And** retorna resultado canônico versionado.

**Given** dados de teste sintéticos
**When** o adapter mock processa a requisição
**Then** produz respostas determinísticas ou cenários configuráveis
**And** não requer credenciais reais de fornecedor.

### Story 3.3: Execução Assíncrona com Fan-out/Fan-in

As a `Decision Service`,
I want solicitar enriquecimento externo de forma assíncrona e paralelizável,
So that múltiplas fontes sejam consultadas dentro de limites controlados.

**Acceptance Criteria:**

**Given** uma proposta que exige múltiplas integrações independentes
**When** o comando `integration.execute` é publicado
**Then** o `Integration Service` cria jobs paralelos por classe/adapter
**And** respeita limites por tenant, produto, credencial, classe e adapter.

**Given** jobs concluídos com sucesso, falha parcial ou timeout
**When** o fan-in consolida os resultados
**Then** publica resultado canônico como completo, parcial, faltante ou falho
**And** inclui correlation ID, tenant, tentativas e versão de schema.

### Story 3.4: Resiliência, Retry, DLQ e Reprocessamento Controlado

As a operador da plataforma,
I want falhas de integração sejam tratadas com retry seguro, DLQ e replay,
So that indisponibilidades externas não quebrem a jornada sem rastreabilidade.

**Acceptance Criteria:**

**Given** uma falha recuperável de adapter
**When** o job falha
**Then** aplica retry com limite, backoff e jitter
**And** preserva idempotência da execução.

**Given** uma falha final ou não recuperável
**When** o limite de tentativas é excedido
**Then** envia a mensagem para DLQ com causa, tenant, classe, adapter e contexto mínimo
**And** permite reprocessamento controlado sem duplicar resultado.

### Story 3.5: Registro de Custo e Resultado de Integração

As a gestor de negócio ou operador,
I want registrar custo estimado/real e resultado das integrações,
So that o custo operacional por decisão e tenant possa ser acompanhado.

**Acceptance Criteria:**

**Given** uma execução de integração
**When** o adapter retorna sucesso, falha, fallback ou resultado parcial
**Then** registra classe, adapter, fornecedor quando configurado, chamadas, tentativas, fallback e custo estimado/real
**And** publica projeção para `Reporting & Insights`.

**Given** payload sensível retornado por fornecedor/mock
**When** logs, eventos ou projeções são gerados
**Then** payload bruto não é registrado
**And** apenas dados minimizados, canônicos ou agregáveis são expostos.

### Story 3.6: Contratos e Gates de Integração

As a equipe de engenharia,
I want contratos e testes para adapters e eventos de integração,
So that mudanças em integrações não quebrem decisão, auditoria ou reporting.

**Acceptance Criteria:**

**Given** contratos AsyncAPI/CloudEvents de integração
**When** a suíte de contrato roda
**Then** valida comandos, resultados completos, parciais, falhos e DLQ
**And** falha em breaking changes sem nova versão.

**Given** um adapter novo ou alterado
**When** ele é homologado
**Then** possui mock/sandbox, testes de contrato, logs seguros, métricas e critérios de substituição
**And** não acopla `Decision` a payload proprietário.

## Epic 4: Políticas e Decisão Explicável

Gestores criam, simulam e publicam políticas; clientes recebem decisões determinísticas explicáveis, incluindo estados inconclusivos controlados.

### Story 4.1: Modelo Versionado de Política de Crédito

As a gestor de crédito,
I want criar políticas versionadas com regras, critérios, limites e metadados,
So that decisões futuras sejam governadas por artefatos rastreáveis.

**Acceptance Criteria:**

**Given** um gestor autorizado
**When** ele cria uma política em draft
**Then** a política recebe `policy_id`, versão, status, owner, produto, tenant/contexto aplicável e changelog inicial
**And** não decide propostas produtivas enquanto estiver em draft.

**Given** uma alteração em política draft
**When** o gestor salva a alteração
**Then** a alteração preserva histórico mínimo
**And** não sobrescreve versão publicada.

### Story 4.2: Catálogo de Reason Codes e Fatores Explicáveis

As a analista de risco,
I want manter reason codes e fatores relevantes versionados,
So that decisões possam ser explicadas de forma consistente.

**Acceptance Criteria:**

**Given** uma política com regras de decisão
**When** uma regra contribui para aprovação, recusa, alteração ou inconclusão
**Then** ela referencia reason code válido e versionado
**And** o reason code possui descrição apropriada para cliente/instituição.

**Given** uma mudança incompatível no catálogo de reason codes
**When** a alteração é proposta
**Then** exige nova versão
**And** mantém compatibilidade para decisões passadas.

### Story 4.3: Simulação e Validação de Política

As a gestor de crédito,
I want simular política antes da publicação,
So that eu avalie impacto sem afetar decisões reais.

**Acceptance Criteria:**

**Given** uma política draft
**When** o gestor executa simulação com dataset sintético ou minimizado
**Then** o resultado é marcado como não produtivo
**And** não altera decisões reais nem publica eventos de decisão final.

**Given** uma política sem reason codes, fallback ou validação mínima
**When** a simulação/validação roda
**Then** falha com erros acionáveis
**And** não permite publicação.

### Story 4.4: Publicação Imutável de Política Aprovada

As a gestor autorizado,
I want publicar uma política validada,
So that novas propostas usem a versão correta sem alterar decisões antigas.

**Acceptance Criteria:**

**Given** uma política validada e aprovada
**When** o gestor publica a versão
**Then** a política passa a status publicado com vigência e versão imutável
**And** a publicação gera auditoria.

**Given** uma correção necessária em política publicada
**When** o gestor altera regras ou reason codes
**Then** o sistema cria nova versão
**And** decisões passadas continuam apontando para a versão original.

### Story 4.5: Execução Determinística de Decisão

As a `Decision Service`,
I want executar política publicada sobre proposta canônica e resultados de integração,
So that o cliente receba uma decisão automática rastreável.

**Acceptance Criteria:**

**Given** uma proposta validada e uma política publicada aplicável
**When** o motor executa a decisão
**Then** gera `decision_id`, resultado, tenant, proposal ID, produto, timestamp, policy ID/version e correlation ID
**And** não depende diretamente de payload proprietário de fornecedor externo.

**Given** uma entrada insuficiente ou resultado parcial de integração
**When** a política avalia a proposta
**Then** aplica regra determinística para aprovação, recusa, aprovação com alterações, solicitação de dados adicionais ou inconclusão
**And** registra o motivo aplicável.

### Story 4.6: Tratamento de Propostas Inconclusivas sem Fila Manual

As a cliente técnico,
I want receber estado controlado quando a proposta não puder ser decidida,
So that meu fluxo saiba solicitar dados adicionais ou tratar o caso sem fila manual no CreditOS.

**Acceptance Criteria:**

**Given** uma política com `fallback_action` configurado
**When** faltam dados críticos ou há contingência
**Then** retorna `request_additional_data`, `unable_to_decide`, reprovação por regra explícita ou aprovação com alterações
**And** registra lacuna, motivo e contexto decisório.

**Given** uma tentativa de criar revisão manual ou override humano no MVP
**When** o fluxo de decisão é configurado
**Then** o sistema rejeita a configuração
**And** orienta uso de fallback automatizado ou IA consultiva quando aplicável.

### Story 4.7: Resposta Explicável de Decisão

As a cliente técnico ou analista de risco,
I want receber decisão com explicabilidade suficiente,
So that eu entenda fatores, regras e versões usadas.

**Acceptance Criteria:**

**Given** uma decisão final ou inconclusiva
**When** a resposta é consultada ou retornada
**Then** inclui resultado, reason codes, fatores relevantes, política/versão, correlation ID e status
**And** minimiza dados sensíveis conforme permissões.

**Given** uma decisão sem reason code ou justificativa equivalente
**When** o sistema tenta publicá-la
**Then** a publicação é bloqueada ou marcada como erro controlado
**And** gera evidência para investigação.

### Story 4.8: Gates de Decisão, Política e Explicabilidade

As a equipe de engenharia,
I want testes de domínio, contrato e regressão para políticas e decisões,
So that alterações não quebrem determinismo, explicabilidade ou auditoria.

**Acceptance Criteria:**

**Given** a suíte de testes de decisão
**When** ela é executada
**Then** cobre criação, simulação, publicação, execução, inconclusão e explicabilidade
**And** valida que decisão final sempre aponta política, versão e reason codes.

**Given** uma tentativa de usar IA ou integração externa como decisor final direto
**When** testes de governança rodam
**Then** a tentativa falha
**And** preserva `Decision` como única fonte da decisão final.

## Epic 5: Revisão Automatizada Consultiva por IA

A plataforma executa revisão por IA como evidência consultiva, com guardrails, versionamento, auditoria e sem autonomia para decisão final.

### Story 5.1: Configuração Versionada de Agente de Revisão

As a gestor autorizado,
I want configurar agente/modelo/prompt de revisão consultiva com versionamento,
So that revisões por IA sejam controladas, auditáveis e promovidas com segurança.

**Acceptance Criteria:**

**Given** uma configuração de revisão automatizada
**When** ela é criada ou alterada
**Then** registra versão de agente, prompt/configuração, modelo/provedor quando aplicável, owner, status e escopo de uso
**And** não entra em produção sem aprovação autorizada.

**Given** uma configuração publicada
**When** uma alteração é necessária
**Then** o sistema cria nova versão
**And** preserva a versão usada em revisões passadas.

### Story 5.2: Execução Consultiva com Entradas Minimizadas

As a `Automated Review Service`,
I want executar revisão usando apenas entradas permitidas e minimizadas,
So that a IA ajude sem expor dados sensíveis além do necessário.

**Acceptance Criteria:**

**Given** uma solicitação de revisão por política configurada
**When** o serviço prepara a entrada para IA
**Then** aplica allowlist, minimização, mascaramento e referências técnicas
**And** não persiste prompt ou payload sensível bruto por padrão.

**Given** campos sensíveis não permitidos
**When** a entrada é montada
**Then** os campos são omitidos, mascarados, tokenizados ou referenciados
**And** o evento registra a política de minimização aplicada.

### Story 5.3: Validação de Saída, Guardrails e Classificação

As a plataforma CreditOS,
I want tratar saídas de IA como não confiáveis,
So that apenas evidências consultivas válidas sejam usadas pelo fluxo decisório.

**Acceptance Criteria:**

**Given** uma resposta de IA
**When** o serviço recebe a saída
**Then** valida schema, limites, tipo de recomendação, confiança quando aplicável e campos permitidos
**And** rejeita output fora de contrato.

**Given** tentativa de prompt injection, vazamento de dado sensível, tool use indevido ou saída com autonomia excessiva
**When** guardrails avaliam a resposta
**Then** bloqueiam a saída
**And** registram falha, motivo e fallback.

### Story 5.4: Evidência Consultiva Vinculada à Proposta

As a analista de risco ou auditor,
I want que o resultado da IA vire evidência consultiva rastreável,
So that a decisão possa explicar lacunas, inconsistências e fatores sugeridos.

**Acceptance Criteria:**

**Given** uma revisão automatizada válida
**When** o resultado é registrado
**Then** vincula proposta, tenant, correlation ID, versão de agente/modelo/prompt, lacunas, inconsistências, fatores sugeridos, limitações e confiança quando aplicável
**And** classifica explicitamente a evidência como consultiva.

**Given** uma decisão final que considerou evidência consultiva
**When** a decisão é registrada
**Then** referencia a evidência considerada
**And** mantém a política determinística como fonte da decisão final.

### Story 5.5: Fallback Seguro de Revisão Automatizada

As a cliente técnico,
I want falhas de IA resultem em estado controlado,
So that uma indisponibilidade de modelo nunca vire aprovação ou reprovação indevida.

**Acceptance Criteria:**

**Given** falha de provedor/modelo, timeout, erro de schema ou guardrail bloqueando resposta
**When** a revisão automatizada falha
**Then** o sistema retorna fallback configurado para o `Decision`
**And** não altera termos, aprovação, recusa ou status final diretamente.

**Given** política configurada para continuar sem revisão
**When** a IA falha
**Then** a decisão prossegue conforme política determinística
**And** registra limitação e ausência de revisão consultiva.

### Story 5.6: Observabilidade, Custo e Gates de IA

As a operador da plataforma,
I want observar uso, custo, latência, erro e qualidade da revisão por IA,
So that agentes/modelos sejam operados com segurança e governança.

**Acceptance Criteria:**

**Given** uma execução de revisão automatizada
**When** métricas e logs são emitidos
**Then** registram tenant, produto, versão de agente/modelo, latência, erro, fallback, custo e correlation ID
**And** não registram prompt ou payload sensível bruto.

**Given** a suíte de governança de IA
**When** os testes rodam
**Then** validam que IA não aprova, reprova, altera termos, executa callback, chama integração externa ou publica decisão final
**And** falham se a decisão final não passar pelo `Decision`.

## Epic 6: Auditoria, Evidências e Rastreabilidade

Decisões, alterações sensíveis, requisições e integrações ficam rastreáveis com auditoria oficial, logs estruturados, mascaramento e integridade verificável.

### Story 6.1: Trilha Oficial Append-only de Auditoria

As a time de compliance/auditoria,
I want uma trilha oficial de auditoria separada dos logs operacionais,
So that decisões e ações sensíveis possam ser provadas e reconstruídas.

**Acceptance Criteria:**

**Given** um evento auditável de decisão ou ação sensível
**When** o `Audit & Evidence` recebe o registro
**Then** persiste em trilha append-only com `event_id`, tenant, agregado, ação, recurso, ator, origem, resultado, UTC, correlation ID e trace ID
**And** operações normais não permitem update/delete na trilha principal.

**Given** logs, traces ou eventos de mensageria
**When** uma auditoria oficial é solicitada
**Then** eles não substituem a trilha oficial
**And** podem ser usados apenas como evidência operacional complementar.

### Story 6.2: Auditoria de Decisões e Evidências Críticas

As a auditor ou cliente autorizado,
I want decisões tenham evidências mínimas e versões aplicáveis,
So that seja possível provar como cada decisão foi tomada.

**Acceptance Criteria:**

**Given** uma decisão final ou inconclusiva
**When** o `Decision` registra auditoria
**Then** inclui tenant, proposta, solicitante, fontes/referências, política, versão, regras, resultado, justificativas e correlation ID
**And** preserva dados mínimos suficientes sem violar minimização.

**Given** falha na gravação de auditoria ou evidência crítica
**When** o sistema tenta publicar decisão final
**Then** a publicação é bloqueada ou retorna estado técnico controlado
**And** a falha é registrada para operação.

### Story 6.3: Auditoria de Alterações Sensíveis

As a operador de governança,
I want alterações sensíveis gerem eventos obrigatórios de auditoria,
So that mudanças críticas não ocorram silenciosamente.

**Acceptance Criteria:**

**Given** alteração em política, modelo, agente de IA, permissão, exportação ou acesso a dado sensível
**When** a operação é executada
**Then** gera evento de auditoria com ator, recurso, antes/depois permitido, justificativa quando aplicável e correlation ID
**And** a operação falha ou fica marcada como estado controlado se auditoria crítica não puder ser registrada.

**Given** uma tentativa administrativa de manutenção ou bypass
**When** a ação ocorre
**Then** ela também gera auditoria
**And** exige permissão segregada.

### Story 6.4: Integridade Verificável com Hash Encadeado e Checkpoints

As a auditor técnico,
I want verificar integridade da trilha de auditoria,
So that alterações ou lacunas sejam detectadas.

**Acceptance Criteria:**

**Given** um novo evento crítico
**When** ele é registrado
**Then** calcula `previous_hash` e `current_hash` sobre payload canonicalizado
**And** mantém cadeia verificável por tenant, agregado ou janela aplicável.

**Given** uma janela de auditoria fechada
**When** o checkpoint é gerado
**Then** assina digest do lote
**And** registra versão de algoritmo, chave/referência e período coberto.

### Story 6.5: Exportação Imutável para WORM

As a responsável de compliance,
I want exportações/checkpoints protegidos por WORM,
So that evidências críticas tenham retenção imutável conforme política.

**Acceptance Criteria:**

**Given** checkpoints ou pacotes mínimos de evidência
**When** a exportação periódica é executada
**Then** grava no storage WORM/S3 Object Lock conforme classe e retenção
**And** não envia payload sensível bruto por padrão.

**Given** uma exportação WORM
**When** o job de reconciliação roda
**Then** verifica divergência entre trilha principal, checkpoint e objeto exportado
**And** registra resultado da verificação.

### Story 6.6: Logs Estruturados e Mascaramento Obrigatório

As a operador da plataforma,
I want logs estruturados em requisições e integrações,
So that problemas sejam rastreáveis sem expor dados sensíveis.

**Acceptance Criteria:**

**Given** uma requisição recebida por qualquer serviço
**When** o serviço registra log operacional
**Then** inclui timestamp UTC, service name, version, environment, correlation ID, trace ID, tenant, operação, status e duração
**And** mascara, omite, tokeniza ou hasheia dados sensíveis.

**Given** chamada interna ou externa
**When** a integração é registrada
**Then** inclui origem, destino, contrato, versão, tenant, trace, status, tentativas, timeout e resultado
**And** não registra payload bruto de provedor, token ou segredo.

### Story 6.7: Gates de Auditoria, Logs e Dados Sensíveis

As a equipe de engenharia e segurança,
I want gates que detectem ausência de auditoria e vazamento em logs,
So that rastreabilidade e privacidade sejam garantidas continuamente.

**Acceptance Criteria:**

**Given** a suíte de segurança e auditoria
**When** os testes rodam
**Then** validam eventos obrigatórios para decisões e alterações sensíveis
**And** falham quando auditoria crítica é omitida.

**Given** logs, traces e eventos gerados em testes
**When** o scanner de dados sensíveis roda
**Then** não encontra CPF/CNPJ completos, tokens, secrets, documentos, renda detalhada ou payload sensível bruto
**And** preserva correlation ID e contexto de tenant para troubleshooting.

## Epic 7: Observabilidade e Dashboards por Tenant

Operadores e clientes autorizados acompanham saúde técnica, funil de decisão, volumes, custos, integrações, incidentes e métricas curadas por tenant.

### Story 7.1: Instrumentação Técnica Base com OpenTelemetry

As a operador da plataforma,
I want todos os serviços emitindo métricas, logs e traces padronizados,
So that a saúde técnica seja observável ponta a ponta.

**Acceptance Criteria:**

**Given** um microsserviço do CreditOS
**When** ele processa requisição HTTP, gRPC, evento, job ou integração
**Then** emite telemetry com service name, version, environment, correlation ID, trace ID, tenant quando aplicável, status e duração
**And** não inclui payload sensível bruto.

**Given** uma chamada entre serviços ou fluxo assíncrono
**When** o contexto é propagado
**Then** traces correlacionam API, gRPC, NATS, jobs e integrações
**And** preservam controle de cardinalidade para tenant.

### Story 7.2: Dashboards Técnicos Internos

As a operador da plataforma,
I want dashboards técnicos internos para serviços, APIs, NATS, bancos, integrações, segurança e deploys,
So that incidentes sejam detectados e diagnosticados rapidamente.

**Acceptance Criteria:**

**Given** a stack de observabilidade interna
**When** dashboards são acessados por operador autorizado
**Then** exibem erro, latência p95/p99, throughput, CPU, memória, saturação, health/readiness e versão por serviço
**And** incluem visão de NATS JetStream, DLQ, retries, backlog, lag e replay.

**Given** falhas de integração, auditoria ou segurança
**When** os dashboards são consultados
**Then** permitem isolar falha por classe, adapter/provedor quando configurado, tenant quando permitido e produto
**And** não expõem dados sensíveis identificáveis.

### Story 7.3: Alertas Técnicos e SLO Watch

As a operador da plataforma,
I want alertas por SLO, erro, latência, saturação, DLQ, auditoria e segurança,
So that degradações sejam tratadas antes de afetar clientes criticamente.

**Acceptance Criteria:**

**Given** métricas técnicas críticas
**When** erro, latência, DLQ, falha de auditoria ou tentativa cross-tenant excede limite configurado
**Then** alerta é emitido com severidade, serviço, ambiente, correlation/trace quando aplicável e runbook esperado
**And** payload sensível não aparece no alerta.

**Given** deploy ou mudança crítica
**When** SLO watch é executado
**Then** correlaciona versão, commit/digest, erro, latência e impacto por serviço
**And** suporta decisão de rollback/roll-forward.

### Story 7.4: Projeções de Métricas de Negócio

As a gestor de negócio ou risco,
I want projeções de funil, decisões, integrações e custos por tenant/produto,
So that eu acompanhe operação e performance de crédito sem acessar dados transacionais brutos.

**Acceptance Criteria:**

**Given** eventos de proposta, decisão, integração, IA e callbacks
**When** `Reporting & Insights` consome os eventos
**Then** atualiza projeções de funil, volume, status, decisão, motivo, custo, latência e erro
**And** não consulta diretamente bancos transacionais de outros serviços.

**Given** eventos fora de ordem ou duplicados
**When** as projeções são atualizadas
**Then** aplica idempotência e consistência eventual controlada
**And** registra freshness da projeção.

### Story 7.5: Dashboards Customer-facing Curados por Tenant

As a cliente autorizado,
I want acompanhar métricas e saúde operacional do meu tenant,
So that eu entenda o funcionamento das análises sem ver telemetria interna bruta.

**Acceptance Criteria:**

**Given** um usuário/cliente autenticado em um tenant
**When** acessa dashboard customer-facing
**Then** visualiza apenas projeções curadas do próprio tenant
**And** não acessa logs crus, traces internos, infraestrutura, dados pessoais, payloads, segredos ou dados de outros tenants.

**Given** métricas disponíveis
**When** o dashboard apresenta saúde e funil
**Then** mostra status de APIs, callbacks, integrações configuradas, incidentes que afetam o tenant, latência, taxa de erro, timeouts, indisponibilidades relevantes, volume e custo operacional
**And** marca telas/experiências como dependentes de refinamento posterior por `bmad-ux`.

### Story 7.6: Gates de Observabilidade e Exposição Segura

As a equipe de engenharia e segurança,
I want validar telemetria, dashboards e projeções antes de produção,
So that observabilidade seja útil sem vazar dados ou quebrar isolamento por tenant.

**Acceptance Criteria:**

**Given** uma suíte de observabilidade
**When** os testes rodam
**Then** validam emissão de logs, métricas, traces, health/readiness e correlation ID por serviço
**And** falham quando uma capability crítica não produz telemetria mínima.

**Given** dashboards internos ou customer-facing
**When** testes de privacidade e tenancy rodam
**Then** não expõem telemetria bruta indevida, dados pessoais, payloads sensíveis ou outro tenant
**And** validam RBAC/scopes e minimização.

## Epic 8: Acesso à Decisão, Notificações e Validação E2E

Clientes consultam decisões, recebem callbacks/webhooks e validam um fluxo completo de análise usando integrações externas mockadas.

### Story 8.1: Consulta de Decisão por Proposta

As a cliente técnico,
I want consultar decisão, status e explicabilidade por proposta,
So that meu sistema possa acompanhar o resultado da análise de crédito/risco.

**Acceptance Criteria:**

**Given** uma proposta pertencente ao tenant autenticado
**When** o cliente consulta a decisão por proposal ID ou referência permitida
**Then** retorna status, resultado quando disponível, reason codes, fatores permitidos, política/versão, contrato/version e correlation ID
**And** minimiza dados sensíveis conforme permissões.

**Given** uma proposta inexistente, de outro tenant ou sem permissão
**When** a consulta é feita
**Then** retorna erro padronizado
**And** não revela existência de dados de outro tenant.

### Story 8.2: Contrato Público de Status e Decisão

As a engenheiro de cliente B2B,
I want respostas de decisão com enums e erros versionados,
So that minha integração seja estável e compatível ao longo do tempo.

**Acceptance Criteria:**

**Given** uma decisão aprovada, recusada, aprovada com alterações, inconclusiva ou com dados adicionais solicitados
**When** a API retorna o resultado
**Then** usa enums documentados e versionados
**And** inclui mensagem pública segura sem stack trace ou detalhe interno.

**Given** mudança incompatível no contrato de resposta
**When** a alteração é proposta
**Then** exige nova versão, período de compatibilidade e testes de contrato
**And** preserva clientes na versão anterior durante a janela definida.

### Story 8.3: Configuração de Webhooks por Tenant

As a cliente técnico,
I want configurar endpoint de callback/webhook por tenant e evento,
So that meu sistema receba notificações de decisão ou mudança de status.

**Acceptance Criteria:**

**Given** um cliente autorizado
**When** configura webhook para eventos permitidos
**Then** registra endpoint, eventos, status, segredo/assinatura, versão de contrato e política de retry
**And** a configuração gera auditoria.

**Given** endpoint inválido, inseguro ou fora de allowlist/política
**When** a configuração é salva
**Then** rejeita com erro padronizado
**And** não armazena segredo em claro.

### Story 8.4: Entrega Assíncrona de Webhooks com Retry e DLQ

As a cliente técnico,
I want receber notificações assinadas e idempotentes,
So that meu sistema processe decisões sem polling constante.

**Acceptance Criteria:**

**Given** uma decisão ou mudança de status notificável
**When** o evento é publicado
**Then** cria job assíncrono de webhook
**And** envia payload minimizado, versionado, assinado, com event ID, proposal ID/status, correlation ID e idempotency key.

**Given** falha temporária no endpoint do cliente
**When** a entrega falha
**Then** aplica retry controlado
**And** envia para DLQ após limite de tentativas, com rastreabilidade e possibilidade de reprocessamento controlado.

### Story 8.5: Observabilidade e Auditoria de Consulta/Callback

As a operador da plataforma,
I want consultas e callbacks rastreados e auditáveis,
So that incidentes e disputas de entrega possam ser investigados.

**Acceptance Criteria:**

**Given** uma consulta de decisão
**When** ela é executada
**Then** registra log estruturado com tenant, operação, status, duração, correlation ID e trace ID
**And** gera auditoria quando acessar evidência sensível permitida.

**Given** uma tentativa de callback
**When** o webhook é enviado, falha, retentado ou enviado para DLQ
**Then** registra métricas, logs seguros e eventos operacionais
**And** não inclui payload sensível bruto.

### Story 8.6: Testes de Contrato para Consulta e Webhooks

As a equipe de engenharia,
I want testes de contrato para consulta e callbacks,
So that clientes B2B tenham integração previsível.

**Acceptance Criteria:**

**Given** contratos OpenAPI e webhook
**When** a suíte de contrato é executada
**Then** valida sucesso, erro, status pendente, inconclusivo, decisão final, assinatura e retry
**And** falha em breaking changes sem nova versão.

**Given** payloads de exemplo
**When** exemplos são validados
**Then** cobrem respostas minimizadas e cenários de tenant/permissão
**And** não contêm dados sensíveis reais.

### Story 8.7: Fluxo E2E de Análise com Integrações Mockadas

As a cliente técnico avaliando o MVP,
I want enviar uma proposta e obter uma resposta analisada com mocks externos,
So that eu valide a jornada completa sem fornecedores reais.

**Acceptance Criteria:**

**Given** um tenant configurado, cliente técnico autenticado, política publicada e adapters mock/sandbox habilitados
**When** o cliente envia payload válido de proposta CPF ou CNPJ de produto MVP
**Then** o sistema aceita a proposta, valida schema, aplica idempotência e dispara o fluxo de decisão
**And** usa integrações externas mockadas para enriquecer a análise.

**Given** os mocks retornam resultados canônicos
**When** o fluxo executa decisão
**Then** gera decisão ou estado inconclusivo explicável com policy/version, reason codes, fatores permitidos e correlation ID
**And** registra auditoria, logs, métricas e projeções de negócio.

**Given** a decisão fica disponível
**When** o cliente consulta a proposta ou recebe callback configurado
**Then** obtém status/resultado por contrato versionado
**And** nenhum dado sensível bruto ou informação de outro tenant é exposta.

**Given** o cenário E2E roda em ambiente não produtivo
**When** a suíte automatizada é executada
**Then** valida a jornada submissão → mocks externos → decisão → auditoria/logs/métricas → consulta/callback
**And** falha se qualquer etapa crítica não for rastreável por correlation ID.
