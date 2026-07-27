# Brainstorm BMAD - Plataforma SaaS de Análise de Crédito e Risco

Data: 2026-07-22
Fonte obrigatória: `docs/input/project-technical-premises.md`
Modo: Parceiro Criativo

## Resumo executivo

O documento de premissas técnicas já estabelece uma base madura para um SaaS B2B de crédito e risco: segurança por padrão, privacidade por padrão, multi-tenancy, auditabilidade, explicabilidade, arquitetura incremental e governança técnica. A principal recomendação deste brainstorming é preservar essas preocupações como invariantes do projeto, mas separar com rigor o que é obrigatório, o que é recomendação inicial e o que ainda depende de decisão formal.

O risco central não é falta de direção técnica; é excesso de decisões implícitas. O documento sugere tecnologias, estrutura, módulos, testes, Kubernetes, observabilidade, modelos e qualidade, mas nem todas essas escolhas devem nascer como obrigações no Product Brief ou PRD. Algumas pertencem a Architecture, ADRs, padrões técnicos, CI/CD ou documentação operacional.

A direção consolidada recomenda começar por um monólito modular, API B2B segura, PostgreSQL relacional, trilha de auditoria separada de logs, isolamento forte por tenant e motor de decisão explicável. Mensageria, Redis, ABAC, Kubernetes avançado, modelos de IA e extração para microsserviços devem ser tratados como decisões condicionais, não automáticas.

## Visão consolidada do produto

A plataforma deve permitir que instituições que concedem, administram ou intermediam crédito recebam propostas, integrem dados, apliquem políticas, calculem risco, detectem fraude, decidam automaticamente ou encaminhem para análise manual, expliquem as decisões e monitorem o pós-concessão.

O diferencial do produto não deve ser apenas "calcular score". A proposta mais forte é um sistema operacional de decisão de crédito: governável, auditável, explicável, multi-tenant, integrável e preparado para regulação, operação B2B e evolução de modelos.

Trabalhos reais que o cliente contrataria o produto para fazer:

- Reduzir tempo de decisão sem perder governança.
- Padronizar políticas de crédito entre canais, produtos e tenants.
- Explicar aprovações, recusas e revisões de forma auditável.
- Integrar dados externos sem contaminar o domínio com formatos de fornecedores.
- Detectar risco e fraude antes, durante e depois da concessão.
- Provar para auditoria, compliance e diretoria que cada decisão foi tomada com dados, regras e versões identificáveis.

## Análise crítica das premissas

### Conflitos e tensões

- Simplicidade inicial vs. preparação para Kubernetes: preparar workloads para Kubernetes não deve forçar complexidade prematura, microsserviços ou manifests completos antes de haver componente implantável real.
- Auditabilidade ampla vs. minimização de dados: registrar tudo que influenciou a decisão pode conflitar com privacidade e retenção; o projeto precisa definir quais dados são armazenados, referenciados, mascarados, resumidos ou descartados.
- Explicabilidade vs. modelos complexos: modelos estatísticos ou de IA podem melhorar performance preditiva, mas piorar explicabilidade; o motor de decisão deve tratar modelos como insumos, não como autoridade final sem controles.
- Cobertura alta vs. qualidade real: metas de cobertura são úteis, mas podem gerar testes artificiais; gates devem combinar cobertura, testes críticos, análise estática, contrato, segurança e revisão.
- Stack sugerida vs. decisão arquitetural: Python e monorepo aparecem como premissas fortes; FastAPI, SQLAlchemy, Alembic, Redis, OpenTelemetry, uv e ferramentas de tipagem precisam de ADR ou padrão técnico antes de virarem obrigatórias.
- Multi-tenancy transversal vs. velocidade de entrega: exigir isolamento em banco, cache, eventos, arquivos, logs, métricas e jobs desde o início é correto como princípio, mas a estratégia concreta precisa ser escolhida para não travar o MVP.

### Ambiguidades

- Geografia, jurisdição e requisitos regulatórios aplicáveis não estão definidos.
- Segmento inicial de cliente não está priorizado.
- Tipos de crédito e produtos suportados no MVP não estão delimitados.
- Fontes externas de dados não estão nomeadas.
- SLA, SLO, latência de decisão e volume esperado não estão definidos.
- Estratégia de tenant ainda está aberta.
- Provedor de identidade, modelo de roles e granularidade de permissões ainda estão abertos.
- Retenção, descarte e anonimização de dados ainda precisam de política.
- Papel de IA/modelos estatísticos no MVP ainda não está decidido.
- Auditoria imutável, tamper-evident ou WORM ainda precisa de decisão.

### Duplicidades saudáveis

- Autenticação, autorização, multi-tenancy e segurança aparecem em várias seções. Isso é intencionalmente redundante e deve virar regra transversal em `project-context.md`, `AGENTS.md` e gates de revisão.
- Idempotência aparece em APIs, eventos e segurança. Deve virar padrão técnico único com exemplos por tipo de operação.
- Correlation ID aparece em APIs, eventos, observabilidade e decisões. Deve virar requisito operacional transversal.
- Explicabilidade e auditabilidade aparecem em produto, decisões e modelos. Devem ficar conectadas, mas separadas: explicabilidade responde "por que"; auditoria responde "quem, quando, com quais dados e versões".

## Premissas confirmadas

- O produto será uma plataforma SaaS B2B para análise de crédito, risco e automação de decisões.
- Segurança e privacidade são defaults; tudo é privado salvo exceção aprovada e documentada.
- Toda decisão relevante deve ser auditável, explicável e associada a tenant, solicitante, política, modelo, dados usados e correlation ID.
- A arquitetura inicial deve ser incremental e evitar microsserviços, filas, bancos separados e abstrações especulativas sem justificativa.
- O repositório deve ser monorepo, com separação entre componentes implantáveis, pacotes compartilhados, testes e documentação.
- O backend deve ser escrito em Python.
- Controllers/endpoints não devem conter regra de negócio; casos de uso coordenam domínio, persistência, integrações e auditoria.
- Autenticação e autorização devem ser obrigatórias por padrão.
- O `tenant_id` recebido no payload nunca deve ser confiado sem validação contra a identidade autenticada.
- A estratégia de multi-tenancy deve ser formalizada em ADR.
- PostgreSQL, SQLAlchemy e Alembic são a direção inicial recomendada para persistência relacional e migrations, sujeitos a ADR/padrão técnico.
- Migrations devem ser versionadas, revisadas, testadas e evitar operações destrutivas imediatas.
- Testes unitários, integração, contrato, E2E e segurança devem existir de acordo com risco e tipo de mudança.
- APIs devem ter schemas explícitos, validação, erros padronizados, versionamento, OpenAPI, correlation ID, timeouts e proteção contra vazamento de detalhes internos.
- Valores monetários não devem usar ponto flutuante binário; datas devem usar UTC e ISO 8601.
- Integrações externas devem ser isoladas por portas/adapters e não contaminar o domínio com formato de fornecedor.
- Eventos e mensageria só devem ser adotados quando houver necessidade real.
- Modelos de risco e IA precisam de identificação, versão, owner, validação, explicabilidade, monitoramento, rollback, avaliação de viés e política de atualização.
- Auditoria deve ser separada de logs operacionais.
- Dados sensíveis não devem ser registrados em logs.
- Componentes implantáveis devem ter observabilidade, health/readiness e imagens de container seguras.
- ADRs devem registrar decisões arquiteturais relevantes com contexto, alternativas, consequências, riscos e status.
- Agentes de IA devem respeitar contexto, escopo, testes, documentação e limites de decisão irreversivel.

## Premissas ajustadas

### Stack inicial sugerida

- Original: FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis quando necessário, pytest, Ruff, mypy ou Pyright, OpenTelemetry e uv são listados como stack inicial sugerida.
- Proposta: classificar Python como premissa obrigatória; classificar os demais itens como stack recomendada que deve ser confirmada em ADRs ou padrões técnicos antes de virar gate obrigatório.
- Justificativa: o próprio documento exige justificativa para novas tecnologias e proíbe seleção por preferência.
- Impacto: evita bloqueio prematuro e preserva rastreabilidade de decisões.
- Risco: se adiado demais, o time pode divergir em ferramentas básicas; mitigar criando ADRs iniciais curtos.

### Kubernetes

- Original: os serviços deverão ser preparados para execução em Kubernetes.
- Proposta: componentes implantáveis devem ser containerizados e projetados para operação cloud-native; a adoção concreta de Kubernetes, Helm, autoscaling e policies deve ser decidida por ADR conforme ambiente alvo.
- Justificativa: preparação operacional é diferente de adoção imediata.
- Impacto: reduz complexidade inicial sem perder portabilidade.
- Risco: se o ambiente alvo já exigir Kubernetes, a decisão precisa ser antecipada.

### Cobertura de testes

- Original: cobertura global mínima de 80%, código novo de 90%, domínio e motor de decisão de 95%.
- Proposta: manter como metas iniciais recomendadas e transformar em quality gates graduais; domínio, políticas, cálculos financeiros e motor de decisão devem ter gate mais rigoroso desde cedo.
- Justificativa: cobertura global em repositório nascente pode oscilar e incentivar testes sem valor.
- Impacto: foca proteção onde o risco e maior.
- Risco: sem metas claras, cobertura pode degradar; mitigar com dashboard e bloqueio para código crítico.

### Eventos e filas

- Original: eventos devem ser utilizados quando houver necessidade real.
- Proposta: reforcar que o MVP pode começar sem broker externo; eventos de domínio podem existir internamente, com broker apenas se houver assincronia, fan-out, resiliência ou integração entre contextos.
- Justificativa: alinha com monólito modular e evita arquitetura distribuída prematura.
- Impacto: reduz custo operacional e complexidade de testes.
- Risco: certas integrações ou backfills podem exigir assincronia cedo; registrar gatilhos objetivos.

### Modelos de IA

- Original: modelos generativos não devem tomar decisões finais sem controles deterministicos, validação e aprovação formal.
- Proposta: no MVP, tratar qualquer modelo como insumo explicável da política de decisão; decisão final deve ser policy-driven até que um ADR aprove outro modelo operacional.
- Justificativa: crédito exige explicabilidade, reprodutibilidade e governança.
- Impacto: reduz risco regulatório e operacional.
- Risco: pode limitar automação avancada; mitigar com roadmap de modelos, validação e monitoramento.

### Auditoria

- Original: registros de auditoria devem possuir proteção contra alteração indevida.
- Proposta: decidir em ADR o nível de proteção: append-only log, trilha tamper-evident, armazenamento WORM, assinatura/hash encadeado ou controle via banco com permissões restritas.
- Justificativa: "proteção" é correto, mas não verificável sem mecanismo.
- Impacto: torna auditabilidade testavel e operável.
- Risco: mecanismo forte demais cedo pode elevar custo; fraco demais pode falhar em auditoria.

### Dados usados em decisão

- Original: toda decisão deve registrar atributos utilizados, fontes de dados e regras executadas.
- Proposta: registrar referencias, snapshots minimizados, hashes, versões e derivados explicáveis conforme política de retenção, evitando persistir payloads sensíveis completos quando desnecessario.
- Justificativa: concilia auditabilidade com privacidade por padrão.
- Impacto: melhora conformidade e reduz exposição.
- Risco: reprodutibilidade pode ficar limitada; documentar limites legais e técnicos.

## Decisões pendentes

- Segmento inicial do ICP: banco, fintech, FIDC, BNPL, varejo, marketplace ou outro.
- Geografia e regime regulatório prioritario.
- Produtos de crédito cobertos no MVP.
- Fluxos MVP: originacao, decisão, análise manual, monitoramento ou todos em escopo reduzido.
- Fontes de dados internas e externas prioritarias.
- Estratégia de multi-tenancy: schema compartilhado, schema por tenant, banco por tenant ou hibrido.
- Modelo de autenticação: provedor próprio, IdP externo, OIDC/SAML, chaves de API técnicas ou combinação.
- Modelo de autorização: RBAC inicial e critérios objetivos para evoluir para ABAC.
- Política de retenção, mascaramento, anonimização e descarte.
- Nivel de imutabilidade da auditoria.
- Latencia alvo para decisão automática e consulta.
- Disponibilidade alvo por plano/cliente.
- Estratégia de idempotência por operação.
- Escopo de IA/modelos no MVP.
- Necessidade e momento de Redis.
- Necessidade e momento de mensageria.
- Ambiente de execução inicial: container simples, plataforma gerenciada, Kubernetes ou hibrido.
- Quality gates mínimos para primeiro merge e para deployment.
- Estratégia de versionamento de API, eventos e schemas.
- Modelo de evidências para PRs, auditoria e releases.

## Requisitos não funcionais verificáveis

### Segurança

- Todo endpoint deve exigir autenticação, exceto endpoints explicitamente allowlisted em documento aprovado.
- Toda operação deve validar usuário, tenant, papel, permissão, recurso e contexto antes de executar o caso de uso.
- Nenhum endpoint deve aceitar `tenant_id` do payload como fonte de verdade sem cruzamento com a identidade autenticada.
- APIs devem bloquear stack traces, mensagens internas de banco, tokens, secrets e detalhes de infraestrutura em respostas.
- Testes de segurança devem cobrir token ausente, invalido, expirado, permissão insuficiente, acesso cross-tenant, enumeração de recursos, entrada maliciosa, rate limiting, replay e idempotência.

### Privacidade

- Logs não devem conter CPF completo, dados bancarios, tokens, senhas, documentos, biometria, dados de cartão, credenciais ou payloads sensíveis completos.
- Dados de teste devem ser sinteticos.
- Cada dado pessoal ou sensível persistido deve ter finalidade, base de uso, responsável e política de retenção definidos.
- Decisões devem armazenar apenas dados necessários para explicabilidade, auditoria e reprodutibilidade dentro dos limites aprovados.

### Performance

- Cada endpoint crítico deve declarar timeout, comportamento de retry e meta de latência antes de ser considerado pronto para produção.
- Operações de decisão automática devem ter SLO de latência definido por fluxo e por tipo de integração.
- Migrations devem avaliar locks, volume, índices e compatibilidade de deployment antes de merge.

### Disponibilidade

- Todo componente implantável deve expor health check e readiness check.
- Funcionalidades críticas devem definir alertas, limites esperados e plano de contingência.
- Integrações externas críticas devem definir timeout, fallback ou degradação controlada.

### Escalabilidade

- A extração para microsserviço só pode ocorrer mediante ADR que comprove escalabilidade independente, isolamento de falhas, ciclo de entrega independente, exigencia regulatória, volume operacional, autonomia de equipe ou tecnologia distinta.
- Componentes implantáveis devem permitir configuracao externa e shutdown gracioso.
- A estratégia de tenant deve declarar limites esperados de volume por tenant e caminho de evolução.

### Resiliencia

- Operações com risco de duplicidade devem implementar idempotência ou registrar justificativa para não implementar.
- Consumidores de eventos, quando existirem, devem tratar duplicidade, ordem, retries, DLQ, versionamento, tenant e correlation ID.
- Integrações externas devem ter tratamento documentado de indisponibilidade.

### Auditabilidade

- Toda decisão de crédito deve registrar identificador, tenant, proposta, solicitante, horário, versões de política/modelo, atributos utilizados, fontes, regras, resultado, códigos de motivo, score, recomendações, intervenção manual, justificativa e correlation ID.
- Auditoria deve ser armazenada separadamente de logs operacionais.
- Alterações de política, modelo, permissão, exportacao e acesso a dados sensíveis devem gerar evento de auditoria.
- O mecanismo de proteção contra alteração de auditoria deve ser definido e testado.

### Observabilidade

- Todo componente implantável deve gerar logs estruturados, métricas, traces e correlation ID.
- Novas funcionalidades críticas devem declarar métricas técnicas, métricas de negócio, limites e condições de alerta.
- Logs devem ser seguros por desenho e testados contra vazamento de dados sensíveis.

### Manutenibilidade

- Domínio não deve depender diretamente de FastAPI, SQLAlchemy, brokers, Redis, provedores externos, Kubernetes ou bibliotecas de observabilidade.
- Controllers devem limitar-se a contrato, autenticação/autorização, chamada de caso de uso, transformação e resposta.
- Dependencias novas devem apresentar necessidade, manutenção, maturidade, documentação, segurança, licença, compatibilidade, performance, custo operacional e alternativas.

### Testabilidade

- Toda alteração de comportamento deve ter teste automatizado proporcional ao risco.
- Regras de negócio, validações, cálculos financeiros, políticas de crédito/risco, transformações e erros devem ter testes unitários.
- Mudanças em banco, migrations, repositórios, cache, eventos, autenticação, autorização, serialização, APIs externas, transações e infraestrutura devem avaliar teste de integração.
- APIs, eventos, schemas, webhooks e integrações externas devem ter testes de contrato quando alterados.

### Interoperabilidade

- APIs devem ter schemas explícitos, OpenAPI, versionamento, paginação quando aplicável e erros padronizados.
- Integrações externas devem usar portas/adapters, contrato versionado e sandbox ou mock.
- Datas devem usar UTC e ISO 8601; valores monetários devem evitar ponto flutuante binário.

### Portabilidade

- Componentes implantáveis devem possuir imagens de container com versões fixas, usuário não root, dependências apenas de runtime, sem secrets e health check adequado.
- Infraestrutura deve ser versionada e não conter credenciais.
- A adoção de Kubernetes, Helm ou manifests deve ser decidida conforme ambiente alvo.

### Continuidade

- Migrations destrutivas devem seguir expand-and-contract.
- Backfills extensos não devem ser obrigatoriamente executados na mesma transação da migration.
- Mudanças incompatíveis em contratos devem gerar nova versão, período de compatibilidade, plano de migração e documentação.
- Modelos devem possuir monitoramento, política de atualização e estratégia de rollback.

## Riscos iniciais

- Risco regulatório: falta de definição de jurisdição, retenção e requisitos legais pode invalidar decisões de dados e auditoria.
- Risco de privacidade: auditabilidade excessiva pode levar ao armazenamento indevido de dados sensíveis.
- Risco de arquitetura prematura: Kubernetes, mensageria, Redis e microsserviços podem ser adotados antes de necessidade comprovada.
- Risco de tenant leakage: multi-tenancy transversal exige testes e padrões desde o primeiro modelo de dados.
- Risco de explicabilidade fraca: modelos ou regras opacas podem gerar decisões impossíveis de justificar.
- Risco de vendor lock-in: integrações externas ou IdP podem contaminar o domínio se não forem isolados por portas/adapters.
- Risco operacional: quality gates amplos demais no início podem bloquear velocidade; fracos demais podem permitir regressao em domínio crítico.
- Risco de reprodutibilidade: minimização de dados pode limitar reprodução de decisões se snapshots, versões e derivados não forem desenhados.
- Risco de autorização: RBAC pode ser insuficiente para políticas contextuais de crédito; ABAC não deve ser adotado sem caso concreto.
- Risco de governança de IA: modelos sem owner, versão, viés, rollback e monitoramento podem criar risco técnico e reputacional.

## ADRs necessários

- ADR-001: Monorepo e estrutura inicial do repositório.
- ADR-002: Monolito modular como arquitetura inicial e critérios de extração.
- ADR-003: Stack backend Python e framework web.
- ADR-004: Persistencia relacional, PostgreSQL, SQLAlchemy e Alembic.
- ADR-005: Estratégia de multi-tenancy.
- ADR-006: Autenticação e provedores de identidade.
- ADR-007: Autorização inicial RBAC e critérios para ABAC.
- ADR-008: Estratégia de auditoria e proteção contra alteração.
- ADR-009: Explicabilidade e reprodutibilidade de decisões.
- ADR-010: Estratégia para modelos de risco, IA e governança.
- ADR-011: Integrações externas por portas/adapters.
- ADR-012: Idempotência, correlation ID e rastreabilidade.
- ADR-013: Eventos/mensageria e gatilhos para adoção.
- ADR-014: Observabilidade.
- ADR-015: Containers e ambiente de deploy.
- ADR-016: Kubernetes, Helm/manifests e infraestrutura como código.
- ADR-017: Política de dados sensíveis, retenção e descarte.
- ADR-018: Quality gates e estratégia de testes.

## Matriz de distribuicao das regras por arquivo

| Destino | Conteudo recomendado |
| --- | --- |
| Product Brief | Problema, público B2B, proposta de valor, diferenciais de governança, explicabilidade, auditabilidade, multi-tenancy e redução de tempo de decisão. |
| PRD | Fluxos funcionais, personas, requisitos funcionais, NFRs verificáveis, escopo MVP, critérios de aceite, decisões pendentes de produto e riscos. |
| Architecture | Monolito modular, módulos, fronteiras, domínio vs infraestrutura, dados, integrações, observabilidade, deploy, segurança e evolução para serviços. |
| `docs/adr/` | Decisões listadas em ADRs necessários, sempre com alternativas, consequências e riscos. |
| `_bmad-output/project-context.md` | Invariantes para agentes: segurança, privacidade, tenant, auditabilidade, explicabilidade, não microsserviços automáticos, não dependência sem justificativa. |
| `AGENTS.md` | Instrucoes operacionais para Codex: ler contexto, respeitar ADRs, não introduzir libs sem justificativa, não criar endpoint público sem aprovação, testar e documentar. |
| `docs/standards/` | Padrões de API, erros, idempotência, logs seguros, testes, migrations, integrações, modelos, audit trail e pull requests. |
| `docs/architecture/` | Visão C4 ou similar, fronteiras de módulo, estratégia de tenant, dados, segurança, observabilidade, deploy e evolução. |
| `docs/runbooks/` | Incidentes de integração externa, falha de decisão, vazamento de dados, rollback de modelo, falha de migration, degradação operacional. |
| `docs/api/` | Versionamento, schemas, erros, exemplos, idempotência, paginação, correlation ID e contratos. |
| `README.md` | Visão geral, pré-requisitos, execução local, estrutura, comandos principais e links para docs. |
| `CONTRIBUTING.md` | Fluxo de PR, exigências de teste, evidências, migrations, contratos, documentação e segurança. |
| `pyproject.toml` | Versões oficiais, lint, formatação, tipagem, pytest, coverage e dependências aprovadas. |
| Pipelines CI/CD | Gates de lint, typecheck, testes, coverage, segurança, dependências, migrations, contratos, build de imagem e vulnerabilidades. |
| Manifests/deploy | Containers, probes, recursos, secrets externos, rollout, rollback, service accounts, network policies e configuracao externa. |
| Template de PR | Objetivo, story, impactos, riscos, testes, migrations, contratos, docs, evidências e pendências. |

## Recomendações para o Product Brief

- Posicionar o produto como plataforma de decisão de crédito governável, não apenas score/rating.
- Priorizar benefícios de negócio: velocidade, consistência, redução de fraude, governança, explicabilidade e auditabilidade.
- Definir ICP inicial e primeiro recorte de mercado.
- Explicitar diferenciais: multi-tenancy seguro, políticas versionadas, trilha de auditoria, códigos de motivo, integrações isoladas e monitoramento pós-concessão.
- Registrar preocupações regulatórias e de privacidade como fatores de confiança e barreiras de entrada.
- Evitar prometer IA autônoma como valor central antes de decidir governança de modelos.

## Recomendações para o PRD

- Definir escopo MVP com fluxos mínimos: autenticação, tenant, proposta, política, decisão, explicabilidade, auditoria e consulta.
- Transformar os requisitos não funcionais acima em critérios de aceite por feature.
- Incluir requisitos de tenant em toda entidade e operação sensível.
- Exigir códigos de motivo, regras acionadas e versões de política/modelo no resultado de decisão quando aplicável.
- Definir fluxos de análise manual, override, aprovação, reprovação e justificativa.
- Incluir histórias para sandbox/mock de integrações externas.
- Definir política de idempotência para criação de proposta e execução de decisão.
- Registrar perguntas pendentes como bloqueios ou assumptions rastreaveis.

## Recomendações para a Architecture

- Começar com monólito modular, fronteiras explicitas e domínio isolado de frameworks, banco, provedores e observabilidade.
- Definir módulos iniciais por capacidade de negócio: identidade, tenants, propostas, políticas, motor de decisão, risco, antifraude, auditoria, integrações, relatórios e notificações.
- Documentar alternativas para multi-tenancy antes de escolher uma estratégia.
- Tratar mensageria como decisão condicional, com gatilhos objetivos.
- Tratar Redis como dependência opcional por caso de uso: cache, rate limiting, locks, filas leves ou sessoes, se necessário.
- Definir trilha de auditoria separada de logs e mecanismo de proteção.
- Definir estratégia de explicabilidade e reprodutibilidade antes de introduzir modelos complexos.
- Criar padrão de adapters para fontes externas e impedir dependência direta do domínio.
- Definir quality gates por risco: domínio e motor de decisão com rigor maior.

## Alterações sugeridas em relacao ao documento original

- Reclassificar "stack inicial sugerida" como recomendação técnica que requer ADR/padrão antes de virar obrigatória, exceto Python backend.
- Reclassificar Kubernetes como preparo de portabilidade e operação, não como decisão automática de plataforma no MVP.
- Transformar metas de cobertura em gates graduais por criticidade.
- Explicitar que broker/mensageria não é requisito inicial; eventos podem começar internos ao monólito.
- Explicitar que modelos são insumos da política de decisão no MVP, não decisores finais.
- Especificar que auditoria precisa de ADR sobre mecanismo de proteção contra alteração.
- Ajustar reprodutibilidade para conviver com minimização, retenção e privacidade.
- Separar explicabilidade de auditabilidade como requisitos complementares, mas distintos.

## Proximos passos sugeridos no fluxo BMAD

- `bmad-product-brief`: criar o Product Brief com ICP, problema, proposta de valor e escopo estratégico.
- `bmad-prd`: transformar a visão em requisitos funcionais, NFRs e critérios de aceite.
- `bmad-architecture`: criar a arquitetura inicial com monólito modular, fronteiras, multi-tenancy, segurança, auditoria e deploy.
- `bmad-spec`: destilar as decisões em contrato operacional para downstream.
- `bmad-create-epics-and-stories`: quebrar o MVP em épicos e stories.
- `bmad-generate-project-context`: criar o contexto persistente para agentes.
- `bmad-check-implementation-readiness`: validar Product Brief, PRD, Architecture e épicos antes de desenvolvimento.
