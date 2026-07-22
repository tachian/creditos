# Brainstorm BMAD - Plataforma SaaS de Analise de Credito e Risco

Data: 2026-07-22
Fonte obrigatoria: `docs/input/project-technical-premises.md`
Modo: Parceiro Criativo

## Resumo executivo

O documento de premissas tecnicas ja estabelece uma base madura para um SaaS B2B de credito e risco: seguranca por padrao, privacidade por padrao, multi-tenancy, auditabilidade, explicabilidade, arquitetura incremental e governanca tecnica. A principal recomendacao deste brainstorming e preservar essas preocupacoes como invariantes do projeto, mas separar com rigor o que e obrigatorio, o que e recomendacao inicial e o que ainda depende de decisao formal.

O risco central nao e falta de direcao tecnica; e excesso de decisoes implicitas. O documento sugere tecnologias, estrutura, modulos, testes, Kubernetes, observabilidade, modelos e qualidade, mas nem todas essas escolhas devem nascer como obrigacoes no Product Brief ou PRD. Algumas pertencem a Architecture, ADRs, padroes tecnicos, CI/CD ou documentacao operacional.

A direcao consolidada recomenda comecar por um monolito modular, API B2B segura, PostgreSQL relacional, trilha de auditoria separada de logs, isolamento forte por tenant e motor de decisao explicavel. Mensageria, Redis, ABAC, Kubernetes avancado, modelos de IA e extracao para microsservicos devem ser tratados como decisoes condicionais, nao automaticas.

## Visao consolidada do produto

A plataforma deve permitir que instituicoes que concedem, administram ou intermediam credito recebam propostas, integrem dados, apliquem politicas, calculem risco, detectem fraude, decidam automaticamente ou encaminhem para analise manual, expliquem as decisoes e monitorem o pos-concessao.

O diferencial do produto nao deve ser apenas "calcular score". A proposta mais forte e um sistema operacional de decisao de credito: governavel, auditavel, explicavel, multi-tenant, integravel e preparado para regulacao, operacao B2B e evolucao de modelos.

Trabalhos reais que o cliente contrataria o produto para fazer:

- Reduzir tempo de decisao sem perder governanca.
- Padronizar politicas de credito entre canais, produtos e tenants.
- Explicar aprovacoes, recusas e revisoes de forma auditavel.
- Integrar dados externos sem contaminar o dominio com formatos de fornecedores.
- Detectar risco e fraude antes, durante e depois da concessao.
- Provar para auditoria, compliance e diretoria que cada decisao foi tomada com dados, regras e versoes identificaveis.

## Analise critica das premissas

### Conflitos e tensoes

- Simplicidade inicial vs. preparacao para Kubernetes: preparar workloads para Kubernetes nao deve forcar complexidade prematura, microsservicos ou manifests completos antes de haver componente implantavel real.
- Auditabilidade ampla vs. minimizacao de dados: registrar tudo que influenciou a decisao pode conflitar com privacidade e retencao; o projeto precisa definir quais dados sao armazenados, referenciados, mascarados, resumidos ou descartados.
- Explicabilidade vs. modelos complexos: modelos estatisticos ou de IA podem melhorar performance preditiva, mas piorar explicabilidade; o motor de decisao deve tratar modelos como insumos, nao como autoridade final sem controles.
- Cobertura alta vs. qualidade real: metas de cobertura sao uteis, mas podem gerar testes artificiais; gates devem combinar cobertura, testes criticos, analise estatica, contrato, seguranca e revisao.
- Stack sugerida vs. decisao arquitetural: Python e monorepo aparecem como premissas fortes; FastAPI, SQLAlchemy, Alembic, Redis, OpenTelemetry, uv e ferramentas de tipagem precisam de ADR ou padrao tecnico antes de virarem obrigatorias.
- Multi-tenancy transversal vs. velocidade de entrega: exigir isolamento em banco, cache, eventos, arquivos, logs, metricas e jobs desde o inicio e correto como principio, mas a estrategia concreta precisa ser escolhida para nao travar o MVP.

### Ambiguidades

- Geografia, jurisdicao e requisitos regulatorios aplicaveis nao estao definidos.
- Segmento inicial de cliente nao esta priorizado.
- Tipos de credito e produtos suportados no MVP nao estao delimitados.
- Fontes externas de dados nao estao nomeadas.
- SLA, SLO, latencia de decisao e volume esperado nao estao definidos.
- Estrategia de tenant ainda esta aberta.
- Provedor de identidade, modelo de roles e granularidade de permissoes ainda estao abertos.
- Retencao, descarte e anonimização de dados ainda precisam de politica.
- Papel de IA/modelos estatisticos no MVP ainda nao esta decidido.
- Auditoria imutavel, tamper-evident ou WORM ainda precisa de decisao.

### Duplicidades saudaveis

- Autenticacao, autorizacao, multi-tenancy e seguranca aparecem em varias secoes. Isso e intencionalmente redundante e deve virar regra transversal em `project-context.md`, `AGENTS.md` e gates de revisao.
- Idempotencia aparece em APIs, eventos e seguranca. Deve virar padrao tecnico unico com exemplos por tipo de operacao.
- Correlation ID aparece em APIs, eventos, observabilidade e decisoes. Deve virar requisito operacional transversal.
- Explicabilidade e auditabilidade aparecem em produto, decisoes e modelos. Devem ficar conectadas, mas separadas: explicabilidade responde "por que"; auditoria responde "quem, quando, com quais dados e versoes".

## Premissas confirmadas

- O produto sera uma plataforma SaaS B2B para analise de credito, risco e automacao de decisoes.
- Seguranca e privacidade sao defaults; tudo e privado salvo excecao aprovada e documentada.
- Toda decisao relevante deve ser auditavel, explicavel e associada a tenant, solicitante, politica, modelo, dados usados e correlation ID.
- A arquitetura inicial deve ser incremental e evitar microsservicos, filas, bancos separados e abstracoes especulativas sem justificativa.
- O repositorio deve ser monorepo, com separacao entre componentes implantaveis, pacotes compartilhados, testes e documentacao.
- O backend deve ser escrito em Python.
- Controllers/endpoints nao devem conter regra de negocio; casos de uso coordenam dominio, persistencia, integracoes e auditoria.
- Autenticacao e autorizacao devem ser obrigatorias por padrao.
- O `tenant_id` recebido no payload nunca deve ser confiado sem validacao contra a identidade autenticada.
- A estrategia de multi-tenancy deve ser formalizada em ADR.
- PostgreSQL, SQLAlchemy e Alembic sao a direcao inicial recomendada para persistencia relacional e migrations, sujeitos a ADR/padrao tecnico.
- Migrations devem ser versionadas, revisadas, testadas e evitar operacoes destrutivas imediatas.
- Testes unitarios, integracao, contrato, E2E e seguranca devem existir de acordo com risco e tipo de mudanca.
- APIs devem ter schemas explicitos, validacao, erros padronizados, versionamento, OpenAPI, correlation ID, timeouts e protecao contra vazamento de detalhes internos.
- Valores monetarios nao devem usar ponto flutuante binario; datas devem usar UTC e ISO 8601.
- Integracoes externas devem ser isoladas por portas/adapters e nao contaminar o dominio com formato de fornecedor.
- Eventos e mensageria so devem ser adotados quando houver necessidade real.
- Modelos de risco e IA precisam de identificacao, versao, owner, validacao, explicabilidade, monitoramento, rollback, avaliacao de vies e politica de atualizacao.
- Auditoria deve ser separada de logs operacionais.
- Dados sensiveis nao devem ser registrados em logs.
- Componentes implantaveis devem ter observabilidade, health/readiness e imagens de container seguras.
- ADRs devem registrar decisoes arquiteturais relevantes com contexto, alternativas, consequencias, riscos e status.
- Agentes de IA devem respeitar contexto, escopo, testes, documentacao e limites de decisao irreversivel.

## Premissas ajustadas

### Stack inicial sugerida

- Original: FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, Redis quando necessario, pytest, Ruff, mypy ou Pyright, OpenTelemetry e uv sao listados como stack inicial sugerida.
- Proposta: classificar Python como premissa obrigatoria; classificar os demais itens como stack recomendada que deve ser confirmada em ADRs ou padroes tecnicos antes de virar gate obrigatorio.
- Justificativa: o proprio documento exige justificativa para novas tecnologias e proibe selecao por preferencia.
- Impacto: evita bloqueio prematuro e preserva rastreabilidade de decisoes.
- Risco: se adiado demais, o time pode divergir em ferramentas basicas; mitigar criando ADRs iniciais curtos.

### Kubernetes

- Original: os servicos deverao ser preparados para execucao em Kubernetes.
- Proposta: componentes implantaveis devem ser containerizados e projetados para operacao cloud-native; a adocao concreta de Kubernetes, Helm, autoscaling e policies deve ser decidida por ADR conforme ambiente alvo.
- Justificativa: preparacao operacional e diferente de adocao imediata.
- Impacto: reduz complexidade inicial sem perder portabilidade.
- Risco: se o ambiente alvo ja exigir Kubernetes, a decisao precisa ser antecipada.

### Cobertura de testes

- Original: cobertura global minima de 80%, codigo novo de 90%, dominio e motor de decisao de 95%.
- Proposta: manter como metas iniciais recomendadas e transformar em quality gates graduais; dominio, politicas, calculos financeiros e motor de decisao devem ter gate mais rigoroso desde cedo.
- Justificativa: cobertura global em repositorio nascente pode oscilar e incentivar testes sem valor.
- Impacto: foca protecao onde o risco e maior.
- Risco: sem metas claras, cobertura pode degradar; mitigar com dashboard e bloqueio para codigo critico.

### Eventos e filas

- Original: eventos devem ser utilizados quando houver necessidade real.
- Proposta: reforcar que o MVP pode comecar sem broker externo; eventos de dominio podem existir internamente, com broker apenas se houver assincronia, fan-out, resiliência ou integracao entre contextos.
- Justificativa: alinha com monolito modular e evita arquitetura distribuida prematura.
- Impacto: reduz custo operacional e complexidade de testes.
- Risco: certas integracoes ou backfills podem exigir assincronia cedo; registrar gatilhos objetivos.

### Modelos de IA

- Original: modelos generativos nao devem tomar decisoes finais sem controles deterministicos, validacao e aprovacao formal.
- Proposta: no MVP, tratar qualquer modelo como insumo explicavel da politica de decisao; decisao final deve ser policy-driven ate que um ADR aprove outro modelo operacional.
- Justificativa: credito exige explicabilidade, reprodutibilidade e governanca.
- Impacto: reduz risco regulatorio e operacional.
- Risco: pode limitar automacao avancada; mitigar com roadmap de modelos, validacao e monitoramento.

### Auditoria

- Original: registros de auditoria devem possuir protecao contra alteracao indevida.
- Proposta: decidir em ADR o nivel de protecao: append-only log, trilha tamper-evident, armazenamento WORM, assinatura/hash encadeado ou controle via banco com permissoes restritas.
- Justificativa: "protecao" e correto, mas nao verificavel sem mecanismo.
- Impacto: torna auditabilidade testavel e operavel.
- Risco: mecanismo forte demais cedo pode elevar custo; fraco demais pode falhar em auditoria.

### Dados usados em decisao

- Original: toda decisao deve registrar atributos utilizados, fontes de dados e regras executadas.
- Proposta: registrar referencias, snapshots minimizados, hashes, versoes e derivados explicaveis conforme politica de retencao, evitando persistir payloads sensiveis completos quando desnecessario.
- Justificativa: concilia auditabilidade com privacidade por padrao.
- Impacto: melhora conformidade e reduz exposicao.
- Risco: reprodutibilidade pode ficar limitada; documentar limites legais e tecnicos.

## Decisoes pendentes

- Segmento inicial do ICP: banco, fintech, FIDC, BNPL, varejo, marketplace ou outro.
- Geografia e regime regulatorio prioritario.
- Produtos de credito cobertos no MVP.
- Fluxos MVP: originacao, decisao, analise manual, monitoramento ou todos em escopo reduzido.
- Fontes de dados internas e externas prioritarias.
- Estrategia de multi-tenancy: schema compartilhado, schema por tenant, banco por tenant ou hibrido.
- Modelo de autenticacao: provedor proprio, IdP externo, OIDC/SAML, chaves de API tecnicas ou combinacao.
- Modelo de autorizacao: RBAC inicial e criterios objetivos para evoluir para ABAC.
- Politica de retencao, mascaramento, anonimização e descarte.
- Nivel de imutabilidade da auditoria.
- Latencia alvo para decisao automatica e consulta.
- Disponibilidade alvo por plano/cliente.
- Estrategia de idempotencia por operacao.
- Escopo de IA/modelos no MVP.
- Necessidade e momento de Redis.
- Necessidade e momento de mensageria.
- Ambiente de execucao inicial: container simples, plataforma gerenciada, Kubernetes ou hibrido.
- Quality gates minimos para primeiro merge e para deployment.
- Estrategia de versionamento de API, eventos e schemas.
- Modelo de evidencias para PRs, auditoria e releases.

## Requisitos nao funcionais verificaveis

### Seguranca

- Todo endpoint deve exigir autenticacao, exceto endpoints explicitamente allowlisted em documento aprovado.
- Toda operacao deve validar usuario, tenant, papel, permissao, recurso e contexto antes de executar o caso de uso.
- Nenhum endpoint deve aceitar `tenant_id` do payload como fonte de verdade sem cruzamento com a identidade autenticada.
- APIs devem bloquear stack traces, mensagens internas de banco, tokens, secrets e detalhes de infraestrutura em respostas.
- Testes de seguranca devem cobrir token ausente, invalido, expirado, permissao insuficiente, acesso cross-tenant, enumeracao de recursos, entrada maliciosa, rate limiting, replay e idempotencia.

### Privacidade

- Logs nao devem conter CPF completo, dados bancarios, tokens, senhas, documentos, biometria, dados de cartao, credenciais ou payloads sensiveis completos.
- Dados de teste devem ser sinteticos.
- Cada dado pessoal ou sensivel persistido deve ter finalidade, base de uso, responsavel e politica de retencao definidos.
- Decisoes devem armazenar apenas dados necessarios para explicabilidade, auditoria e reprodutibilidade dentro dos limites aprovados.

### Performance

- Cada endpoint critico deve declarar timeout, comportamento de retry e meta de latencia antes de ser considerado pronto para producao.
- Operacoes de decisao automatica devem ter SLO de latencia definido por fluxo e por tipo de integracao.
- Migrations devem avaliar locks, volume, indices e compatibilidade de deployment antes de merge.

### Disponibilidade

- Todo componente implantavel deve expor health check e readiness check.
- Funcionalidades criticas devem definir alertas, limites esperados e plano de contingencia.
- Integracoes externas criticas devem definir timeout, fallback ou degradacao controlada.

### Escalabilidade

- A extracao para microsservico so pode ocorrer mediante ADR que comprove escalabilidade independente, isolamento de falhas, ciclo de entrega independente, exigencia regulatoria, volume operacional, autonomia de equipe ou tecnologia distinta.
- Componentes implantaveis devem permitir configuracao externa e shutdown gracioso.
- A estrategia de tenant deve declarar limites esperados de volume por tenant e caminho de evolucao.

### Resiliencia

- Operacoes com risco de duplicidade devem implementar idempotencia ou registrar justificativa para nao implementar.
- Consumidores de eventos, quando existirem, devem tratar duplicidade, ordem, retries, DLQ, versionamento, tenant e correlation ID.
- Integracoes externas devem ter tratamento documentado de indisponibilidade.

### Auditabilidade

- Toda decisao de credito deve registrar identificador, tenant, proposta, solicitante, horario, versoes de politica/modelo, atributos utilizados, fontes, regras, resultado, codigos de motivo, score, recomendacoes, intervencao manual, justificativa e correlation ID.
- Auditoria deve ser armazenada separadamente de logs operacionais.
- Alteracoes de politica, modelo, permissao, exportacao e acesso a dados sensiveis devem gerar evento de auditoria.
- O mecanismo de protecao contra alteracao de auditoria deve ser definido e testado.

### Observabilidade

- Todo componente implantavel deve gerar logs estruturados, metricas, traces e correlation ID.
- Novas funcionalidades criticas devem declarar metricas tecnicas, metricas de negocio, limites e condicoes de alerta.
- Logs devem ser seguros por desenho e testados contra vazamento de dados sensiveis.

### Manutenibilidade

- Dominio nao deve depender diretamente de FastAPI, SQLAlchemy, brokers, Redis, provedores externos, Kubernetes ou bibliotecas de observabilidade.
- Controllers devem limitar-se a contrato, autenticacao/autorizacao, chamada de caso de uso, transformacao e resposta.
- Dependencias novas devem apresentar necessidade, manutencao, maturidade, documentacao, seguranca, licenca, compatibilidade, performance, custo operacional e alternativas.

### Testabilidade

- Toda alteracao de comportamento deve ter teste automatizado proporcional ao risco.
- Regras de negocio, validacoes, calculos financeiros, politicas de credito/risco, transformacoes e erros devem ter testes unitarios.
- Mudancas em banco, migrations, repositorios, cache, eventos, autenticacao, autorizacao, serializacao, APIs externas, transacoes e infraestrutura devem avaliar teste de integracao.
- APIs, eventos, schemas, webhooks e integracoes externas devem ter testes de contrato quando alterados.

### Interoperabilidade

- APIs devem ter schemas explicitos, OpenAPI, versionamento, paginacao quando aplicavel e erros padronizados.
- Integracoes externas devem usar portas/adapters, contrato versionado e sandbox ou mock.
- Datas devem usar UTC e ISO 8601; valores monetarios devem evitar ponto flutuante binario.

### Portabilidade

- Componentes implantaveis devem possuir imagens de container com versoes fixas, usuario nao root, dependencias apenas de runtime, sem secrets e health check adequado.
- Infraestrutura deve ser versionada e nao conter credenciais.
- A adocao de Kubernetes, Helm ou manifests deve ser decidida conforme ambiente alvo.

### Continuidade

- Migrations destrutivas devem seguir expand-and-contract.
- Backfills extensos nao devem ser obrigatoriamente executados na mesma transacao da migration.
- Mudancas incompatíveis em contratos devem gerar nova versao, periodo de compatibilidade, plano de migracao e documentacao.
- Modelos devem possuir monitoramento, politica de atualizacao e estrategia de rollback.

## Riscos iniciais

- Risco regulatorio: falta de definicao de jurisdicao, retencao e requisitos legais pode invalidar decisoes de dados e auditoria.
- Risco de privacidade: auditabilidade excessiva pode levar ao armazenamento indevido de dados sensiveis.
- Risco de arquitetura prematura: Kubernetes, mensageria, Redis e microsservicos podem ser adotados antes de necessidade comprovada.
- Risco de tenant leakage: multi-tenancy transversal exige testes e padroes desde o primeiro modelo de dados.
- Risco de explicabilidade fraca: modelos ou regras opacas podem gerar decisoes impossiveis de justificar.
- Risco de vendor lock-in: integracoes externas ou IdP podem contaminar o dominio se nao forem isolados por portas/adapters.
- Risco operacional: quality gates amplos demais no inicio podem bloquear velocidade; fracos demais podem permitir regressao em dominio critico.
- Risco de reproducibilidade: minimizacao de dados pode limitar reproducao de decisoes se snapshots, versoes e derivados nao forem desenhados.
- Risco de autorizacao: RBAC pode ser insuficiente para politicas contextuais de credito; ABAC nao deve ser adotado sem caso concreto.
- Risco de governanca de IA: modelos sem owner, versao, vies, rollback e monitoramento podem criar risco tecnico e reputacional.

## ADRs necessarios

- ADR-001: Monorepo e estrutura inicial do repositorio.
- ADR-002: Monolito modular como arquitetura inicial e criterios de extracao.
- ADR-003: Stack backend Python e framework web.
- ADR-004: Persistencia relacional, PostgreSQL, SQLAlchemy e Alembic.
- ADR-005: Estrategia de multi-tenancy.
- ADR-006: Autenticacao e provedores de identidade.
- ADR-007: Autorizacao inicial RBAC e criterios para ABAC.
- ADR-008: Estrategia de auditoria e protecao contra alteracao.
- ADR-009: Explicabilidade e reproducibilidade de decisoes.
- ADR-010: Estrategia para modelos de risco, IA e governanca.
- ADR-011: Integracoes externas por portas/adapters.
- ADR-012: Idempotencia, correlation ID e rastreabilidade.
- ADR-013: Eventos/mensageria e gatilhos para adocao.
- ADR-014: Observabilidade.
- ADR-015: Containers e ambiente de deploy.
- ADR-016: Kubernetes, Helm/manifests e infraestrutura como codigo.
- ADR-017: Politica de dados sensiveis, retencao e descarte.
- ADR-018: Quality gates e estrategia de testes.

## Matriz de distribuicao das regras por arquivo

| Destino | Conteudo recomendado |
| --- | --- |
| Product Brief | Problema, publico B2B, proposta de valor, diferenciais de governanca, explicabilidade, auditabilidade, multi-tenancy e reducao de tempo de decisao. |
| PRD | Fluxos funcionais, personas, requisitos funcionais, NFRs verificaveis, escopo MVP, criterios de aceite, decisoes pendentes de produto e riscos. |
| Architecture | Monolito modular, modulos, fronteiras, dominio vs infraestrutura, dados, integracoes, observabilidade, deploy, seguranca e evolucao para servicos. |
| `docs/adr/` | Decisoes listadas em ADRs necessarios, sempre com alternativas, consequencias e riscos. |
| `_bmad-output/project-context.md` | Invariantes para agentes: seguranca, privacidade, tenant, auditabilidade, explicabilidade, nao microsservicos automaticos, nao dependencia sem justificativa. |
| `AGENTS.md` | Instrucoes operacionais para Codex: ler contexto, respeitar ADRs, nao introduzir libs sem justificativa, nao criar endpoint publico sem aprovacao, testar e documentar. |
| `docs/standards/` | Padroes de API, erros, idempotencia, logs seguros, testes, migrations, integracoes, modelos, audit trail e pull requests. |
| `docs/architecture/` | Visao C4 ou similar, fronteiras de modulo, estrategia de tenant, dados, seguranca, observabilidade, deploy e evolucao. |
| `docs/runbooks/` | Incidentes de integracao externa, falha de decisao, vazamento de dados, rollback de modelo, falha de migration, degradacao operacional. |
| `docs/api/` | Versionamento, schemas, erros, exemplos, idempotencia, paginacao, correlation ID e contratos. |
| `README.md` | Visao geral, pre-requisitos, execucao local, estrutura, comandos principais e links para docs. |
| `CONTRIBUTING.md` | Fluxo de PR, exigencias de teste, evidencias, migrations, contratos, documentacao e seguranca. |
| `pyproject.toml` | Versoes oficiais, lint, formatacao, tipagem, pytest, coverage e dependencias aprovadas. |
| Pipelines CI/CD | Gates de lint, typecheck, testes, coverage, seguranca, dependencias, migrations, contratos, build de imagem e vulnerabilidades. |
| Manifests/deploy | Containers, probes, recursos, secrets externos, rollout, rollback, service accounts, network policies e configuracao externa. |
| Template de PR | Objetivo, story, impactos, riscos, testes, migrations, contratos, docs, evidencias e pendencias. |

## Recomendacoes para o Product Brief

- Posicionar o produto como plataforma de decisao de credito governavel, nao apenas score/rating.
- Priorizar beneficios de negocio: velocidade, consistencia, reducao de fraude, governanca, explicabilidade e auditabilidade.
- Definir ICP inicial e primeiro recorte de mercado.
- Explicitar diferenciais: multi-tenancy seguro, politicas versionadas, trilha de auditoria, codigos de motivo, integracoes isoladas e monitoramento pos-concessao.
- Registrar preocupacoes regulatórias e de privacidade como fatores de confianca e barreiras de entrada.
- Evitar prometer IA autonoma como valor central antes de decidir governanca de modelos.

## Recomendacoes para o PRD

- Definir escopo MVP com fluxos minimos: autenticacao, tenant, proposta, politica, decisao, explicabilidade, auditoria e consulta.
- Transformar os requisitos nao funcionais acima em criterios de aceite por feature.
- Incluir requisitos de tenant em toda entidade e operacao sensivel.
- Exigir codigos de motivo, regras acionadas e versoes de politica/modelo no resultado de decisao quando aplicavel.
- Definir fluxos de analise manual, override, aprovacao, reprovação e justificativa.
- Incluir historias para sandbox/mock de integracoes externas.
- Definir politica de idempotencia para criacao de proposta e execucao de decisao.
- Registrar perguntas pendentes como bloqueios ou assumptions rastreaveis.

## Recomendacoes para a Architecture

- Comecar com monolito modular, fronteiras explicitas e dominio isolado de frameworks, banco, provedores e observabilidade.
- Definir modulos iniciais por capacidade de negocio: identidade, tenants, propostas, politicas, motor de decisao, risco, antifraude, auditoria, integracoes, relatorios e notificacoes.
- Documentar alternativas para multi-tenancy antes de escolher uma estrategia.
- Tratar mensageria como decisao condicional, com gatilhos objetivos.
- Tratar Redis como dependencia opcional por caso de uso: cache, rate limiting, locks, filas leves ou sessoes, se necessario.
- Definir trilha de auditoria separada de logs e mecanismo de protecao.
- Definir estrategia de explicabilidade e reproducibilidade antes de introduzir modelos complexos.
- Criar padrao de adapters para fontes externas e impedir dependencia direta do dominio.
- Definir quality gates por risco: dominio e motor de decisao com rigor maior.

## Alteracoes sugeridas em relacao ao documento original

- Reclassificar "stack inicial sugerida" como recomendacao tecnica que requer ADR/padrao antes de virar obrigatoria, exceto Python backend.
- Reclassificar Kubernetes como preparo de portabilidade e operacao, nao como decisao automatica de plataforma no MVP.
- Transformar metas de cobertura em gates graduais por criticidade.
- Explicitar que broker/mensageria nao e requisito inicial; eventos podem comecar internos ao monolito.
- Explicitar que modelos sao insumos da politica de decisao no MVP, nao decisores finais.
- Especificar que auditoria precisa de ADR sobre mecanismo de protecao contra alteracao.
- Ajustar reproducibilidade para conviver com minimizacao, retencao e privacidade.
- Separar explicabilidade de auditabilidade como requisitos complementares, mas distintos.

## Proximos passos sugeridos no fluxo BMAD

- `bmad-product-brief`: criar o Product Brief com ICP, problema, proposta de valor e escopo estrategico.
- `bmad-prd`: transformar a visao em requisitos funcionais, NFRs e criterios de aceite.
- `bmad-architecture`: criar a arquitetura inicial com monolito modular, fronteiras, multi-tenancy, seguranca, auditoria e deploy.
- `bmad-spec`: destilar as decisoes em contrato operacional para downstream.
- `bmad-create-epics-and-stories`: quebrar o MVP em epicos e stories.
- `bmad-generate-project-context`: criar o contexto persistente para agentes.
- `bmad-check-implementation-readiness`: validar Product Brief, PRD, Architecture e epicos antes de desenvolvimento.
