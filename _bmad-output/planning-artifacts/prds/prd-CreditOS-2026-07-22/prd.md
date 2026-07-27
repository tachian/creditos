---
title: "PRD: CreditOS"
status: draft
created: 2026-07-22
updated: 2026-07-27
---

# PRD: CreditOS

## 0. Propósito do documento

Este PRD transforma o Product Brief e os artefatos de brainstorming do CreditOS em requisitos de produto para PM, arquitetura, UX, engenharia, QA e stakeholders de negócio. O documento usa termos definidos no glossário, agrupa funcionalidades por capacidade e numera requisitos funcionais com IDs estáveis. Detalhes de implementação, decisões arquiteturais, alternativas técnicas e decisões derivadas ficam no `addendum.md`.

## 1. Visão

CreditOS é uma plataforma SaaS B2B para análise de crédito, análise de risco e automação de decisões. A plataforma permite que instituições recebam propostas, integrem fontes de dados, apliquem políticas, calculem indicadores de risco, detectem fraude, decidam automaticamente, solicitem dados adicionais quando necessário, executem revisão automatizada consultiva por IA, expliquem decisões e preservem auditoria completa.

A proposta central é ser um sistema operacional de decisão de crédito: governável, auditável, explicável, multi-tenant, extensível e observável. O produto deve reduzir tempo de decisão e inconsistências operacionais sem comprometer segurança, privacidade, rastreabilidade, segregação por tenant ou capacidade de provar como cada decisão foi tomada.

Como ainda não há cliente inicial definido, o MVP deve suportar análises para CPF e CNPJ em um recorte multi-produto controlado: crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis. A plataforma não deve aceitar payloads arbitrários; a flexibilidade deve vir de contratos versionados, schemas aprovados, validação, normalização e adapters de integração.

## 2. Usuários-alvo

O ICP inicial do MVP são instituições B2B que precisam automatizar decisões de crédito e risco via API, incluindo originadores digitais, fintechs, financeiras, FIDCs, varejistas/marketplaces com BNPL e empresas com operação relevante de crédito pessoal ou PJ.

### 2.1 Jobs To Be Done

- Como gestor de crédito, quero padronizar políticas por produto, canal e tenant para reduzir decisões inconsistentes.
- Como analista de risco, quero entender quais dados, regras e fatores influenciaram uma decisão para ajustar políticas e monitorar exposição.
- Como time de compliance/auditoria, quero reconstruir decisões relevantes com versões, dados usados, solicitante, tenant, resultado, revisão automatizada e evidências.
- Como time de engenharia de uma instituição cliente, quero integrar propostas, consultar decisões e receber callbacks sem depender de formatos internos de fornecedores.
- Como operador da plataforma, quero observar saúde técnica, volume por tenant, falhas de integração e funil de decisão para operar o serviço com confiança.

### 2.2 Não usuários do MVP

- Consumidores finais solicitando crédito diretamente ao CreditOS.
- Marketplaces públicos de modelos, políticas ou dados de terceiros.
- Clientes que exigem customizações profundas sem contrato de schema aprovado.
- Times que buscam apenas um score isolado sem governança, auditoria ou explicabilidade.

### 2.3 Jornadas-chave

- **UJ-1. Instituição cliente submete uma proposta e recebe decisão explicável.**
  - **Persona + contexto:** engenheiro ou sistema de uma fintech envia uma proposta de crédito por API para reduzir tempo de resposta.
  - **Entrada:** cliente autenticado, tenant identificado, contrato de proposta versionado.
  - **Caminho:** envia proposta; o sistema valida schema e tenant; enriquece dados por integrações configuradas; executa política; registra decisão e auditoria.
  - **Clímax:** a API retorna decisão com status, códigos de motivo, fatores relevantes, versão da política e correlation ID.
  - **Resolução:** a instituição usa a decisão em seu fluxo e pode consultar evidências depois.
  - **Falha relevante:** se uma integração externa falhar ou faltar dado crítico, o sistema aplica contingência configurada, solicita dados adicionais ou retorna estado inconclusivo controlado.

- **UJ-2. Gestor de crédito publica uma nova versão de política.**
  - **Persona + contexto:** gestor ajusta política para um produto ou tenant sem alterar código.
  - **Entrada:** usuário autenticado com permissão adequada.
  - **Caminho:** cria ou edita política; valida regras; revisa impacto; publica nova versão; alteração é auditada.
  - **Clímax:** novas propostas passam a usar a versão publicada, mantendo histórico de versões anteriores.
  - **Resolução:** decisões futuras registram a versão da política aplicada.

- **UJ-3. Proposta inconclusiva passa por revisão automatizada consultiva.**
  - **Persona + contexto:** sistema cliente envia proposta que não possui dados suficientes ou apresenta inconsistência relevante.
  - **Entrada:** proposta validada, política aplicável, dados disponíveis, lacunas, sinais de risco e contexto de execução.
  - **Caminho:** o motor aplica política determinística; quando configurado, um agente de IA revisa inconsistências, resume lacunas e sugere fatores para explicabilidade; a decisão final continua controlada por política versionada.
  - **Clímax:** o sistema retorna decisão, aprovação com ajustes, solicitação de dados adicionais ou estado inconclusivo, sempre com motivos e correlation ID.
  - **Resolução:** a instituição consulta evidências, usa o resultado no próprio fluxo e mantém responsabilidade por eventual contestação ou revisão fora do fluxo operacional do MVP.

- **UJ-4. Operador monitora saúde técnica e funil de decisão.**
  - **Persona + contexto:** operador da plataforma acompanha estabilidade, volume e comportamento por tenant.
  - **Entrada:** dashboards e alertas configurados.
  - **Caminho:** visualiza taxa de erro, latência, throughput, integrações externas, volume por tenant e funil de decisão.
  - **Clímax:** identifica degradação ou queda de conversão antes de virar incidente grave.
  - **Resolução:** aciona runbook, alerta responsável ou acompanha recuperação.

## 3. Glossário

- **Tenant** — cliente lógico da plataforma. Todas as entidades e operações sensíveis devem estar associadas a um tenant.
- **Proposta** — requisição de análise de crédito recebida por API, vinculada a tenant, produto de crédito e schema versionado.
- **Produto de crédito** — categoria da proposta. No MVP, inclui crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis; demais categorias exigem schema aprovado e decisão de roadmap.
- **Schema de proposta** — contrato versionado que define campos aceitos, obrigatórios, opcionais e validações por produto/canal.
- **Política de crédito** — conjunto versionado de regras e critérios usados para decidir ou encaminhar uma proposta.
- **Motor de decisão** — capacidade que executa políticas, combina sinais, calcula resultado e gera explicabilidade.
- **Indicador de risco** — score, feature, métrica ou classificação usada como insumo da decisão.
- **Análise antifraude** — avaliação de sinais, regras e fontes que indicam risco de fraude.
- **Decisão** — resultado de uma proposta: aprovada, reprovada, aprovada com alterações, dados adicionais solicitados, inconclusiva ou erro controlado.
- **Código de motivo** — código padronizado que explica fatores favoráveis, desfavoráveis ou regras relevantes da decisão.
- **Revisão automatizada consultiva** — análise automatizada, inclusive por agente de IA quando configurado, usada para identificar lacunas, inconsistências, sinais relevantes e explicações; não substitui a política versionada como fonte da decisão final.
- **Auditoria** — trilha separada dos logs operacionais, usada para evidenciar ações, decisões, versões, acessos sensíveis e alterações relevantes.
- **Log operacional** — registro estruturado usado para rastreabilidade técnica e troubleshooting, com dados sensíveis mascarados.
- **Integração externa** — chamada para provedor fora da plataforma, como bureau, KYC, antifraude, Open Finance ou fonte cadastral.
- **Integração interna** — comunicação entre microsserviços da plataforma.
- **Correlation ID** — identificador usado para rastrear uma operação ponta a ponta em logs, traces, decisões e integrações.

## 4. Funcionalidades

### 4.1 Identidade, tenant e autorização

**Descrição:** A plataforma deve garantir que toda operação seja autenticada, autorizada e vinculada ao tenant correto antes de qualquer processamento sensível. Realiza UJ-1, UJ-2, UJ-3 e UJ-4.

#### FR-1: Autenticar chamadas de API

Clientes e usuários autenticados podem acessar APIs e superfícies internas conforme credenciais válidas.

**Consequências testáveis:**
- Requisições sem credencial válida são rejeitadas.
- Endpoints públicos exigem allowlist e justificativa documentada.
- Health checks não expõem dados sensíveis.
- APIs máquina-a-máquina usam OAuth 2.0 Client Credentials.
- Console de usuários humanos usa OIDC Authorization Code + PKCE quando existir.

#### FR-2: Autorizar por usuário, papel, permissão, tenant, recurso e contexto

O sistema valida autorização antes de executar casos de uso sensíveis.

**Consequências testáveis:**
- Usuário sem permissão adequada recebe erro padronizado.
- Operação com tenant incompatível é rejeitada.
- Testes cobrem acesso cross-tenant e alteração indevida de tenant.
- O MVP usa RBAC, scopes e claims de tenant como base de autorização.
- ABAC fica planejado para regras contextuais futuras por produto, canal, risco, origem e sensibilidade de dado.

#### FR-3: Gerenciar tenants

Usuários autorizados podem criar, consultar e configurar tenants conforme limites de plano e regras operacionais.

**Consequências testáveis:**
- Todo tenant possui identificador único, status e configuração mínima.
- Entidades pertencentes a cliente sempre persistem ou trafegam com contexto de tenant.
- Métricas e logs incluem tenant quando aplicável.

### 4.2 Recebimento e validação de propostas

**Descrição:** A plataforma deve receber propostas por API, validar contratos versionados, normalizar dados e iniciar o fluxo de decisão. Realiza UJ-1.

#### FR-4: Receber proposta por contrato versionado

Clientes técnicos autenticados podem submeter propostas com contexto de tenant resolvido pela plataforma, produto de crédito, schema versionado e dados exigidos.

**Consequências testáveis:**
- Payload fora do schema é rejeitado com erro padronizado.
- Propostas indicam `person_type` como PF ou PJ e `product_type` como crédito pessoal, BNPL, crédito PJ/capital de giro ou recebíveis no MVP.
- Schema desconhecido ou obsoleto é rejeitado ou roteado conforme política de compatibilidade.
- O sistema nunca aceita payload arbitrário sem contrato aprovado.

#### FR-5: Validar e normalizar proposta

O sistema valida campos obrigatórios, tipos, formatos, datas, valores monetários e consistência mínima da proposta.

**Consequências testáveis:**
- Datas usam UTC e ISO 8601.
- Valores monetários não usam ponto flutuante binário.
- Dados sensíveis não aparecem em mensagens de erro.

#### FR-6: Garantir idempotência na submissão de proposta

Clientes podem enviar chave de idempotência para evitar criação duplicada de propostas.

**Consequências testáveis:**
- Repetição da mesma chave retorna o resultado documentado.
- Chaves iguais com payload incompatível geram erro controlado.
- Logs incluem chave de idempotência quando aplicável.

### 4.3 Integrações de dados

**Descrição:** A plataforma deve integrar fontes internas e externas por adapters, sem expor formatos de provedores ao domínio. Realiza UJ-1 e UJ-4.

#### FR-7: Configurar fontes de dados por tenant e produto

Usuários autorizados podem definir quais classes de fontes e adapters serão usados por produto, política ou tenant.

**Consequências testáveis:**
- Uma proposta usa apenas fontes permitidas para seu tenant e produto.
- Falta de configuração obrigatória bloqueia execução ou encaminha para contingência.
- Toda configuração relevante gera auditoria.

#### FR-8: Executar integrações externas de forma assíncrona, paralelizável e resiliente

O sistema executa integrações externas por meio do `Integration Service`, usando processamento assíncrono, paralelização controlada, timeout, retry, fallback e tratamento de indisponibilidade.

**Consequências testáveis:**
- Integrações externas críticas são enfileiradas ou orquestradas como tarefas assíncronas, mesmo quando a decisão síncrona aguarda o resultado até um deadline configurado.
- O sistema consegue executar múltiplas integrações externas em paralelo quando não houver dependência de ordem entre elas.
- Paralelização respeita limites por tenant, provedor, produto, credencial e classe de integração.
- Cada execução registra classe de integração, adapter, fornecedor quando existir, quantidade de chamadas, tentativas, fallback e custo estimado ou real quando configurado.
- Falha de provedor gera log estruturado, métrica e estado controlado.
- Resultados parciais são identificados e tratados pela política de decisão.
- Payload sensível do provedor não é registrado em log bruto.
- Resultado da integração é armazenado ou referenciado conforme política de retenção.

#### FR-9: Usar sandbox ou mock para integrações

Ambientes não produtivos devem permitir simulação de provedores externos.

**Consequências testáveis:**
- Testes de integração não dependem de serviços de produção.
- Contratos de integração externa podem ser validados com mocks ou sandbox.
- Dados de teste são sintéticos.

### 4.4 Políticas de crédito

**Descrição:** A plataforma deve permitir criar, versionar, revisar, aprovar e publicar políticas de crédito. Realiza UJ-2.

#### FR-10: Criar e versionar política de crédito

Usuários autorizados podem criar políticas com regras, critérios, fatores, limites e metadados.

**Consequências testáveis:**
- Cada política possui identificador, versão, status e owner.
- Alterações não sobrescrevem versões anteriores.
- Publicação exige validação mínima.

#### FR-11: Publicar política aprovada

Usuários autorizados podem publicar uma versão de política para uso por produto, tenant ou contexto configurado.

**Consequências testáveis:**
- Propostas novas usam a versão publicada aplicável.
- Decisões registram a versão usada.
- Publicação gera auditoria.

#### FR-12: Simular política antes de publicação

Usuários autorizados podem executar simulações controladas antes de publicar uma política.

**Consequências testáveis:**
- Simulações não alteram decisões reais.
- Resultados de simulação são marcados como não produtivos.
- Dados sensíveis seguem regras de mascaramento.

### 4.5 Motor de decisão e explicabilidade

**Descrição:** O motor de decisão aplica políticas, combina sinais de risco/fraude e retorna resultado explicável. Realiza UJ-1.

#### FR-13: Executar decisão automática

O sistema executa política aplicável a uma proposta validada e produz decisão automática quando os critérios forem suficientes.

**Consequências testáveis:**
- Decisão possui identificador, tenant, proposta, horário, resultado e correlation ID.
- Decisão registra política e modelo usados, quando aplicável.
- Decisão não depende diretamente de formato de provedor externo.

#### FR-14: Tratar proposta inconclusiva sem fila manual

O sistema trata propostas que não puderem ser decididas automaticamente sem criar fila manual no MVP.

**Consequências testáveis:**
- Motivo de inconclusão, lacuna de dados ou contingência é registrado.
- A política define `fallback_action`, como solicitar dados adicionais, retornar `unable_to_decide` ou aplicar reprovação por regra explícita.
- Métricas do funil distinguem decisões aprovadas, recusadas, aprovadas com alterações, inconclusivas e solicitações de dados adicionais.

#### FR-15: Retornar explicabilidade da decisão

O sistema retorna códigos de motivo, fatores relevantes, regras acionadas, indicadores calculados e versões aplicáveis.

**Consequências testáveis:**
- Toda decisão final possui ao menos um código de motivo ou justificativa equivalente.
- Resposta não expõe dados sensíveis além do necessário.
- Regras acionadas podem ser rastreadas para política e versão.

### 4.6 Revisão automatizada e governança de IA

**Descrição:** A plataforma deve permitir revisão automatizada consultiva, segura, explicável e auditável, sem fila manual no MVP. Realiza UJ-3.

#### FR-16: Executar revisão automatizada consultiva

Quando configurado por política, o sistema executa revisão automatizada consultiva para identificar lacunas, inconsistências, sinais de risco e fatores de explicabilidade.

**Consequências testáveis:**
- Revisão automatizada registra versão do agente/modelo, entradas permitidas, saídas, limitações e correlation ID.
- Dados sensíveis usados pela revisão seguem minimização, mascaramento e política de retenção.
- Revisão automatizada não aprova nem reprova proposta sem política determinística rastreável.

#### FR-17: Registrar resultado da revisão automatizada

O sistema registra o resultado da revisão automatizada como evidência consultiva vinculada à proposta.

**Consequências testáveis:**
- Resultado distingue lacunas, inconsistências, fatores sugeridos, recomendação consultiva e confiança quando aplicável.
- Resultado não contém prompt, payload sensível bruto ou dado não necessário para auditoria.
- Decisão final registra quais evidências automatizadas foram consideradas pela política.

#### FR-18: Impedir decisão final autônoma por IA generativa

A plataforma impede que IA generativa tome decisão final de crédito sem controles determinísticos, validação formal e política aprovada.

**Consequências testáveis:**
- Decisões finais sempre apontam política, versão, regras e códigos de motivo.
- Saídas de IA são classificadas como consultivas, salvo decisão formal futura em ADR e governança.
- Testes validam que fluxo de IA não consegue alterar resultado final sem passar pelo motor de decisão.

### 4.7 Auditoria e evidências

**Descrição:** A plataforma deve manter trilha de auditoria separada de logs operacionais para decisões e ações relevantes.

#### FR-19: Registrar auditoria de decisões

Toda decisão relevante gera registro de auditoria com dados mínimos necessários.

**Consequências testáveis:**
- Auditoria inclui tenant, proposta, solicitante, horário, dados usados ou referências, fontes, política, modelo, regras, resultado, justificativas e correlation ID.
- Auditoria é separada dos logs operacionais.
- Mecanismo de proteção contra alteração é definido na Architecture/ADR.

#### FR-20: Registrar auditoria de alterações sensíveis

Alterações em política, modelo, agente de IA, permissão, exportação e acesso a dados sensíveis geram evento de auditoria.

**Consequências testáveis:**
- Eventos de auditoria não podem ser omitidos silenciosamente.
- Falha na geração de auditoria crítica bloqueia publicação de decisão final ou marca a operação com estado técnico controlado.
- Auditoria preserva dados suficientes sem violar minimização.

### 4.8 Logs, observabilidade e dashboards

**Descrição:** A plataforma deve ser observável técnica e operacionalmente desde o MVP. Realiza UJ-4.

#### FR-21: Registrar logs estruturados de requisições

Todos os serviços registram requisições recebidas com campos mínimos de rastreabilidade.

**Consequências testáveis:**
- Logs incluem timestamp UTC, service name, version, environment, correlation ID, trace ID, tenant, operação, status e duração.
- Dados sensíveis são mascarados, omitidos, tokenizados ou hasheados.
- Testes ou gates verificam ausência de campos sensíveis em logs críticos.

#### FR-22: Registrar logs de integrações internas e externas

Chamadas internas e externas registram origem, destino, contrato, versão, tenant, trace, status, tentativas, timeout e resultado.

**Consequências testáveis:**
- Falhas de integração geram logs e métricas.
- Logs de provedores externos não contêm payload sensível bruto.
- Chamadas internas propagam contexto de rastreabilidade.

#### FR-23: Expor dashboards técnicos

Operadores podem visualizar saúde geral, API gateway, microsserviços, tracing, banco de dados, filas/eventos, integrações externas, segurança operacional e deploys.

**Consequências testáveis:**
- Dashboards exibem erro, latência p95/p99, throughput, CPU, memória e saturação quando aplicável.
- Falhas de provedor externo podem ser isoladas por provedor e tenant.
- Alertas existem para erros 5xx, latência acima do SLO, falha de auditoria e tentativas cross-tenant.
- Observabilidade técnica é capacidade transversal de plataforma e não pertence ao `Reporting & Insights Service` como fonte de verdade.

#### FR-24: Expor dashboards de negócio

Usuários internos autorizados e clientes autorizados podem acompanhar funil de decisão, volume por tenant, performance de decisão, políticas, motivos de decisão, propostas inconclusivas, revisão automatizada, risco/fraude, pós-concessão, saúde operacional do tenant e custo operacional por meio do `Reporting & Insights Service`.

**Consequências testáveis:**
- Métricas de negócio respeitam isolamento por tenant.
- Clientes visualizam apenas métricas curadas do próprio tenant, sem acesso a telemetria bruta, infraestrutura interna ou dados de outros tenants.
- Funil distingue propostas recebidas, validadas, enriquecidas, decididas, aprovadas, recusadas, aprovadas com alterações, inconclusivas e com dados adicionais solicitados.
- Dashboards customer-facing exibem status de APIs, webhooks, callbacks, integrações configuradas, incidentes que afetam o tenant, latência, taxa de erro, timeouts e indisponibilidades relevantes.
- Custo operacional é exibido por proposta, tenant, produto, classe de integração e fornecedor quando configurado.
- Explicabilidade agregada exibe motivos de decisão e tendências sem revelar dados pessoais, payloads de provedores, lógica sensível indevida ou evidências restritas.
- Dashboards não expõem dados sensíveis identificáveis.
- `Reporting & Insights Service` é dono de observabilidade de negócio, projeções e agregações, mas não da auditoria oficial nem da observabilidade técnica profunda.

### 4.9 Consulta de decisões e callbacks

**Descrição:** Clientes devem consultar decisões e receber notificações controladas quando aplicável. Realiza UJ-1 e UJ-3.

#### FR-25: Consultar decisão por proposta

Clientes autorizados podem consultar resultado, status, explicabilidade e evidências permitidas de uma proposta.

**Consequências testáveis:**
- Consulta respeita tenant e permissões.
- Resposta inclui correlation ID e versão de contrato.
- Dados sensíveis são minimizados.

#### FR-26: Enviar callbacks ou webhooks

O sistema pode notificar clientes sobre decisão ou mudança de status por webhook configurado.

**Consequências testáveis:**
- Webhooks possuem assinatura, retry controlado e idempotência.
- Falhas são rastreadas por logs, métricas e alertas.
- Contrato de webhook é versionado.

## 5. Requisitos não funcionais transversais

### 5.1 Segurança

- **NFR-1:** Todo endpoint exige autenticação por padrão, exceto endpoints explicitamente aprovados como públicos.
- **NFR-2:** Toda operação sensível valida usuário, tenant, papel, permissão, recurso e contexto.
- **NFR-3:** Nenhum `tenant_id` recebido no payload é fonte de verdade sem validação contra identidade autenticada.
- **NFR-4:** Respostas de API não expõem stack trace, mensagens internas de banco, nomes de tabela, tokens, secrets ou detalhes de infraestrutura.
- **NFR-5:** Autenticação e identidade usam OIDC/OAuth 2.0 como base, com Client Credentials para clientes técnicos e Authorization Code + PKCE para usuários humanos.
- **NFR-6:** Tokens possuem duração curta, rotação de chaves, validação de `iss`, `aud`, `sub`, `exp`, `iat`, `jti`, scopes e claims de tenant quando aplicável.
- **NFR-7:** Autorização usa RBAC, scopes e claims de tenant no MVP, com evolução planejada para ABAC e avaliação de FAPI 2.0 em endpoints financeiros sensíveis.
- **NFR-8:** Contexto de autenticação/autorização deve ser propagado entre microsserviços via gRPC metadata e eventos, incluindo `tenant_id`, sujeito, scopes, correlation ID e trace ID quando aplicável.

### 5.2 Privacidade e dados sensíveis

- **NFR-9:** Logs, traces, dashboards e respostas operacionais não registram nem exibem CPF/CNPJ completos, dados bancários, cartões, tokens, senhas, biometria, documentos, renda detalhada, credenciais ou payloads sensíveis completos.
- **NFR-10:** Dados de teste são sintéticos.
- **NFR-11:** Dados pessoais ou sensíveis persistidos possuem `data_class`, finalidade, base legal, owner, retenção, descarte e política de mascaramento definidos antes de produção.

### 5.3 Multi-tenancy

- **NFR-12:** Toda entidade pertencente a cliente possui contexto de tenant.
- **NFR-13:** Isolamento entre tenants é aplicado em dados, cache, eventos, filas, arquivos, logs, métricas, relatórios, jobs, notificações e integrações.
- **NFR-14:** Testes demonstram que um tenant não acessa dados de outro.
- **NFR-15:** O MVP deve adotar modelo `bridge`: serviços podem ser compartilhados, mas dados e recursos críticos devem ter isolamento por tenant ou grupo controlado de tenants.
- **NFR-16:** Todo tenant possui `tenant_isolation_tier`, inicialmente `bridge`, com caminho de evolução para `silo` quando volume, risco, contrato, performance, região ou compliance exigirem.
- **NFR-17:** O sistema mantém catálogo de tenant para resolver localização de dados, credenciais, limites, configurações, recursos dedicados e tier de isolamento.
- **NFR-18:** Cache, filas, DLQs, objetos, jobs, callbacks, secrets, métricas e traces usam chave/contexto de tenant e não podem ser compartilhados sem segregação explícita.

### 5.4 Performance e disponibilidade

- **NFR-19:** APIs críticas declaram timeout, comportamento de retry e meta de latência antes de produção.
- **NFR-20:** Operações de decisão automática possuem SLO de latência definido por fluxo e tipo de integração.
- **NFR-21:** Componentes implantáveis expõem health check e readiness check.

### 5.5 Resiliência

- **NFR-22:** Operações com risco de duplicidade implementam idempotência ou registram justificativa aprovada.
- **NFR-23:** Fluxos assíncronos usam NATS JetStream como backbone de referência no MVP e tratam duplicidade, ordem, retries, DLQ, versionamento, tenant, correlation ID, replay e consumidores duráveis.
- **NFR-24:** Integrações externas críticas possuem processamento assíncrono, paralelização controlada, contingência documentada, idempotência, retry seguro, DLQ ou equivalente e limites por tenant/provedor.

### 5.6 Auditabilidade

- **NFR-25:** Auditoria é separada de logs operacionais.
- **NFR-26:** Registros de auditoria usam banco append-only no MVP, com proibição de update/delete na trilha principal, hash encadeado, checkpoints assinados, verificação periódica e exportação imutável.
- **NFR-27:** Decisões são reproduzíveis dentro dos limites técnicos, legais e de retenção definidos.

### 5.7 Observabilidade

- **NFR-28:** Todos os microsserviços produzem logs estruturados, métricas, traces, health check, readiness check e correlation ID.
- **NFR-29:** Funcionalidades críticas definem métricas técnicas, métricas de negócio, limites esperados e condições de alerta.
- **NFR-30:** Observabilidade preserva mascaramento, minimização e isolamento por tenant.
- **NFR-31:** Dashboards customer-facing são derivados de projeções curadas por tenant e não expõem métricas brutas de infraestrutura, traces crus, logs operacionais, payloads, segredos, dados pessoais ou detalhes de outros tenants.

### 5.8 Interoperabilidade e contratos

- **NFR-32:** APIs possuem schemas explícitos, validação, respostas padronizadas, erros padronizados, versionamento, OpenAPI, paginação quando aplicável e correlation ID.
- **NFR-33:** APIs, eventos, webhooks, schemas e integrações externas possuem testes de contrato quando alterados.
- **NFR-34:** Mudanças incompatíveis geram nova versão, período de compatibilidade, plano de migração e documentação.

### 5.9 Arquitetura de domínio

- **NFR-35:** Todo backend deve seguir Domain-Driven Design, com separação explícita entre domínio, aplicação e infraestrutura.
- **NFR-36:** Microsserviços devem refletir bounded contexts ou capacidades de domínio; serviços não devem ser criados por camada técnica, conveniência operacional ou preferência de ferramenta.
- **NFR-37:** Regras de negócio, políticas, invariantes, entidades, value objects e eventos de domínio não devem depender diretamente de frameworks, banco de dados, provedores externos, transporte HTTP/gRPC ou formato de payload de terceiros.

### 5.10 Persistência e ownership de dados

- **NFR-38:** Cada microsserviço deve possuir ownership lógico exclusivo dos seus dados desde o início.
- **NFR-39:** No MVP, serviços podem compartilhar o mesmo cluster PostgreSQL, desde que usem database/schema/usuário separados por serviço e permissões que impeçam acesso direto a dados de outro serviço.
- **NFR-40:** Joins, queries e transações diretas entre bancos/schemas de serviços são proibidos; comunicação entre domínios deve ocorrer por API/gRPC, eventos, projeções ou composição autorizada.
- **NFR-41:** `Audit & Evidence` deve ter isolamento reforçado e caminho de evolução para storage separado, append-only, hash encadeado e exportação imutável.
- **NFR-42:** `Reporting & Insights` deve usar banco de leitura/projeções alimentado por eventos ou pipelines autorizados, não por leitura direta dos bancos transacionais dos demais serviços.

## 6. Integrações e dependências

### 6.1 Classes de integração externa

- Cadastro, validação documental, KYC e KYB para PF/PJ.
- Bureau de crédito, restritivos e indicadores de capacidade de pagamento quando permitidos.
- Antifraude e contexto digital.
- Recebíveis, lastro, sacados/pagadores e elegibilidade para produtos de recebíveis ou FIDC.
- Open Finance ou fontes financeiras equivalentes, somente quando houver consentimento, base legal, parceiro ou instituição habilitada e escopo regulatório aplicável.
- Webhooks/callbacks de clientes e provedores de notificação.
- Integrações externas devem ser executadas de forma assíncrona e paralelizável pelo `Integration Service`, com fan-out/fan-in, limites de concorrência, resultados parciais, DLQ ou equivalente e rastreabilidade ponta a ponta.
- Fornecedores concretos não são escolhidos no PRD; o MVP deve suportar adapters substituíveis, mocks/sandbox e modelo de custo por classe de integração.

### 6.2 Integrações internas

- Integrações síncronas entre microsserviços devem usar gRPC.
- Fluxos assíncronos devem usar eventos/mensagens com NATS JetStream como backbone de referência no MVP, mantendo fan-out, retry durável, DLQ, integrações externas, callbacks, reporting e consistência eventual.
- Eventos devem usar CloudEvents como envelope, AsyncAPI para documentação de contratos, transactional outbox para publicação confiável e inbox/idempotência para consumo confiável.
- gRPC permanece obrigatório para chamadas síncronas internas com resposta imediata; NATS JetStream é usado quando houver desacoplamento, durabilidade, replay, fan-out, DLQ ou processamento posterior.

### 6.3 Dependências pendentes

- Fornecedores externos concretos serão definidos por caso comercial, parceiro, homologação ou necessidade operacional, sem bloquear o desenho do MVP.
- Detalhes operacionais do NATS JetStream na cloud alvo, incluindo sizing, retenção, replicação, storage e backup, serão definidos pela Architecture.
- Modo de operação da stack de observabilidade, self-hosted, managed ou híbrido, será definido pela Architecture.
- Toda infraestrutura de produção deve ser provisionada por Infrastructure as Code; o desenvolvimento dos módulos IaC entra no backlog final do projeto.

## 7. Governança de dados, auditoria e compliance

- Dados sensíveis devem ser minimizados em coleta, persistência, transmissão, logs e respostas.
- Política de retenção, anonimização, mascaramento contextual, descarte e base legal precisa ser definida antes de produção.
- Máscaras fortes são padrão em logs, traces e dashboards; máscaras moderadas são permitidas apenas em telas autorizadas quando reconhecimento visual for necessário.
- O sistema não deve depender de CPF, CNPJ ou e-mail visível para identificação operacional; deve usar `proposal_id`, `customer_reference`, correlation ID, hash seguro ou busca exata com permissão elevada e auditoria.
- Toda decisão deve ser auditável e explicável.
- Decisão de crédito não deve ser publicada como final quando a gravação de evidência ou auditoria crítica falhar; o sistema deve retornar estado técnico controlado.
- Decisões automatizadas devem preservar evidências e critérios suficientes para apoiar solicitações de revisão, explicação ou contestação pela instituição cliente, sem criar fila manual operacional no MVP.
- Modelos de risco e IA precisam de owner, versão, documentação, validação, explicabilidade, monitoramento, rollback, avaliação de viés e política de atualização.
- Modelos generativos não podem tomar decisão final de crédito sem controles determinísticos, validação e aprovação formal.
- Jurisdição, regime regulatório, base legal e requisitos de conformidade precisam de validação jurídica/compliance antes de produção.

## 8. Não objetivos explícitos

- Não construir produto B2C para solicitante final no MVP.
- Não aceitar payload arbitrário sem schema aprovado.
- Não expor dados entre tenants.
- Não permitir decisão final por IA generativa sem governança formal.
- Não construir fila operacional de análise manual ou override humano no MVP.
- Não substituir auditoria por logs operacionais.
- Não criar microsserviço sem fronteira de domínio clara.
- Não escolher provedores externos sem justificativa, alternativas e consequências.
- Não expor gRPC publicamente por padrão.

## 9. Escopo MVP

### 9.1 Dentro do MVP

- Autenticação, autorização e tenant.
- Submissão de proposta por API com schema versionado.
- Suporte inicial a análises de CPF e CNPJ.
- Produtos MVP: crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis.
- Validação, normalização e idempotência.
- Integrações externas via adapters com sandbox ou mocks.
- Cadastro, versionamento e publicação de políticas.
- Execução de decisão determinística com explicabilidade.
- Revisão automatizada consultiva por IA quando configurada por política.
- Tratamento de propostas inconclusivas por solicitação de dados adicionais, aprovação com alterações, reprovação por regra explícita ou retorno `unable_to_decide`.
- Registro de auditoria para decisões e alterações sensíveis.
- Logs estruturados com mascaramento.
- Dashboards técnicos e de negócio iniciais.
- Consulta de decisão por API.

### 9.2 Fora do MVP

- Portal completo de administração visual para todos os domínios.
- Marketplace de modelos, políticas ou integrações.
- Treinamento de modelos próprio dentro da plataforma.
- Captura, curadoria e uso de dados para treinamento de modelos próprios ou IA fora do fluxo de revisão consultiva do MVP.
- Suporte irrestrito a qualquer produto de crédito sem schema aprovado.
- Cobertura profunda de todas as variações de produto, jornada, antifraude, checkout, pós-concessão e cobrança.
- Fila operacional de análise manual, decisão manual e override humano.
- Customização profunda por tenant sem governança.
- Otimização avançada de pós-concessão.

### 9.3 Backlog final do projeto

- Definir processo de captura, curadoria e uso de dados para modelos próprios e IA.
- Criar dataset analítico sem identificadores diretos sensíveis, como CPF, nome, rua, documentos, telefone, e-mail, credenciais ou payloads brutos.
- Definir política de anonimização, pseudonimização, minimização, retenção, segregação por tenant e base legal antes de qualquer uso para treinamento ou avaliação de modelo.
- Versionar datasets, features, modelos, avaliações, aprovações, métricas de viés, explicabilidade e rollback.
- Garantir que dados usados para IA possam ser auditados sem permitir reidentificação indevida.
- Desenvolver Infrastructure as Code para ambientes, rede, Kubernetes, bancos, mensageria, observabilidade, storage imutável, KMS/secrets, políticas de segurança e automação de isolamento por tenant.

## 10. Métricas de sucesso

### 10.1 Primárias

- **SM-1:** Percentual de decisões com explicabilidade completa: decisão final contém código de motivo, versão de política, correlation ID e fatores relevantes. Valida FR-13, FR-15 e FR-19.
- **SM-2:** Tempo p95 de decisão automática por produto e tenant. Valida FR-4, FR-8 e FR-13.
- **SM-3:** Percentual de requisições e integrações com logs estruturados completos e sem dados sensíveis em claro. Valida FR-21 e FR-22.
- **SM-4:** Taxa de isolamento cross-tenant em testes críticos: 100% dos testes de isolamento passam. Valida FR-2, FR-3 e NFR-14.

### 10.2 Secundárias

- **SM-5:** Volume de propostas, decisões e chamadas externas por tenant. Valida FR-23 e FR-24.
- **SM-6:** Percentual de propostas inconclusivas, revisadas automaticamente e resolvidas por solicitação de dados adicionais ou aprovação com alterações. Valida FR-14, FR-16, FR-17 e FR-18.
- **SM-7:** Taxa de falha por provedor externo e impacto no funil. Valida FR-8, FR-23 e FR-24.
- **SM-8:** Custo operacional por decisão e por tenant. Valida FR-24.

### 10.3 Contramétricas

- **SM-C1:** Aumentar aprovação automática não deve elevar decisões sem explicabilidade.
- **SM-C2:** Reduzir latência não deve aumentar falha de auditoria, vazamento de logs ou decisão com dados incompletos.
- **SM-C3:** Ampliar flexibilidade de schemas não deve permitir payload arbitrário sem governança.

## 11. Riscos e mitigações

- **R-1: MVP multi-produto amplo demais.** Mitigação: PRD limita o MVP a quatro famílias de produto com schemas versionados, fluxo mínimo auditável e integrações opcionais por adapter.
- **R-2: Complexidade de microsserviços.** Mitigação: Architecture deve justificar fronteiras, contratos e ownership de dados.
- **R-3: Vazamento cross-tenant.** Mitigação: tenant obrigatório, testes específicos e observabilidade por tenant.
- **R-4: Logs com dados sensíveis.** Mitigação: mascaramento, gates e política de classificação.
- **R-5: Auditoria insuficiente.** Mitigação: trilha separada, eventos obrigatórios e ADR de proteção contra alteração.
- **R-6: Provedores externos instáveis.** Mitigação: adapters, timeouts, retries, fallback, sandbox/mocks e dashboards por provedor.
- **R-7: Explicabilidade fraca.** Mitigação: códigos de motivo, fatores, versões e regras acionadas como requisitos de decisão.
- **R-8: IA fora de governança.** Mitigação: revisão automatizada por IA é consultiva no MVP; decisão final exige política versionada, códigos de motivo, validação e auditoria.
- **R-9: Ausência de fila manual no MVP.** Mitigação: proposta inconclusiva retorna estado controlado, solicitação de dados adicionais ou aprovação com alterações; evidências e critérios ficam disponíveis para revisão pela instituição cliente.

## 12. Questões abertas e decisões recentes

### 12.1 Decisões recentes

- **OQ-1 resolvida:** ICP inicial são instituições B2B com operação API-first de crédito e risco para PF e PJ, incluindo originadores digitais, fintechs, financeiras, FIDCs, varejistas/marketplaces com BNPL e empresas com crédito pessoal ou PJ.
- **OQ-2 resolvida:** MVP inclui crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis, sempre com schema versionado, política própria, explicabilidade, auditoria e integrações opcionais por adapter.
- **OQ-3 resolvida:** contrato inicial de proposta será canônico, versionado e composto por núcleo comum, `borrower`, `participants`, `consents`, `provided_data`, `risk_context`, `product_data`, `decision_options` e `callback`; não haverá `selected_plan`, apenas `requested_terms`; não haverá revisão manual no MVP, apenas revisão automatizada consultiva quando configurada.
- **OQ-4 resolvida:** primeiro deploy terá 7 microsserviços: `Identity & Tenant`, `Proposal Intake`, `Decision`, `Automated Review`, `Integration`, `Audit & Evidence` e `Reporting & Insights`; observabilidade de negócio pertence a `Reporting & Insights`, observabilidade técnica é transversal e auditabilidade pertence a `Audit & Evidence`.
- **OQ-5 resolvida:** cada microsserviço terá ownership lógico exclusivo de dados desde o início; no MVP, poderá existir cluster PostgreSQL compartilhado com database/schema/usuário separados por serviço, sem joins cross-service e com evolução para isolamento físico quando volume, compliance, risco ou operação exigirem.
- **OQ-6 resolvida:** multi-tenancy começa em modelo `bridge` no MVP, com serviços compartilhados e dados/recursos críticos isolados por tenant ou grupo controlado de tenants, mantendo evolução para `silo` quando risco, volume, contrato, região, performance ou compliance exigirem.
- **OQ-7 resolvida:** autenticação e identidade usarão OIDC/OAuth 2.0; APIs máquina-a-máquina usarão Client Credentials; usuários humanos usarão Authorization Code + PKCE; autorização inicial será RBAC + scopes + claims de tenant, com evolução planejada para ABAC e avaliação de FAPI 2.0.
- **OQ-8 resolvida:** o MVP não escolherá fornecedores externos nominais agora; priorizará classes de integração por adapters substituíveis, mocks/sandbox e modelo de custo por operação, com fornecedores reais definidos somente por caso comercial, parceiro, homologação ou necessidade operacional.
- **OQ-9 resolvida:** observabilidade adotará OpenTelemetry como padrão obrigatório de instrumentação e stack de referência Grafana OSS no MVP, com Prometheus para métricas, Loki para logs, Tempo para traces, Grafana para visualização, Alertmanager para alertas e dashboards customer-facing curados por tenant via `Reporting & Insights Service`.
- **OQ-10 resolvida:** dados sensíveis usarão política por classe de dado e contexto de uso, com máscara forte por padrão, máscara moderada apenas em telas autorizadas, correlação por identificadores técnicos ou hash seguro, dado completo criptografado somente quando indispensável e acesso auditado.
- **OQ-11 resolvida:** auditoria usará banco append-only no MVP, reforçado por hash encadeado, checkpoints assinados, verificação periódica e exportação imutável; ledger ou database especializada ficam como evolução condicionada a cliente, contrato ou regulação.
- **OQ-12 resolvida:** integrações síncronas internas usarão gRPC e fluxos assíncronos usarão NATS JetStream como backbone de referência no MVP, com CloudEvents, AsyncAPI, transactional outbox, consumidores idempotentes, DLQ, replay e consumidores duráveis; SQS/SNS/Lambda ficam como complementos AWS quando houver justificativa específica.
- **Decisão arquitetural registrada:** todo backend deve seguir Domain-Driven Design, preservando bounded contexts, linguagem ubíqua, regras de domínio isoladas de infraestrutura e serviços derivados de fronteiras de domínio.
- **Decisão de roadmap registrada:** processo de captura e uso de dados para modelos próprios e IA será tratado como backlog final do projeto, com dados minimizados e sem identificadores diretos sensíveis.

### 12.2 Questões ainda abertas

- Não há questões abertas principais restantes de OQ-1 a OQ-12; detalhes de Architecture, ADRs e validação jurídica/compliance permanecem como próximos passos.

## 13. Índice de assumptions

- **A-1:** Limite recorrente e outros produtos de crédito ficam fora do MVP até haver decisão de roadmap e schema aprovado.
- **A-2:** Fontes de dados poderão ser configuradas por tenant e produto.
- **A-3:** Simulação de política antes de publicação será necessária no MVP.
- **A-4:** Falha na geração de auditoria pode bloquear ou marcar operação conforme severidade definida.
- **A-5:** Webhooks/callbacks serão necessários no MVP.
- **A-6:** Provedores de notificação serão classe de integração externa.
- **A-7:** Portal completo de administração visual não entra no MVP.
- **A-8:** Custo operacional por decisão e por tenant será métrica de sucesso.
