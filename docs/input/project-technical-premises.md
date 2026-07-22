# Premissas Técnicas e Diretrizes do Projeto

## 1. Objetivo deste documento

Este documento apresenta as premissas técnicas, restrições, padrões de qualidade, segurança e arquitetura que devem orientar a concepção e o desenvolvimento da plataforma SaaS de análise de crédito e risco.

Durante o Brainstorm do BMAD, estas premissas devem ser:

1. analisadas criticamente;
2. agrupadas por área;
3. questionadas quando houver ambiguidades;
4. classificadas como obrigatórias, recomendadas ou pendentes de decisão;
5. transformadas em requisitos não funcionais;
6. relacionadas aos riscos do produto;
7. distribuídas posteriormente nos documentos e configurações adequados do projeto.

O Brainstorm não deve eliminar ou alterar uma premissa obrigatória sem registrar:

- a premissa original;
- a alteração proposta;
- a justificativa;
- os impactos;
- os riscos;
- a decisão necessária.

## 2. Contexto do produto

O produto será uma plataforma SaaS B2B para análise de crédito, análise de risco e automação de decisões.

A plataforma deverá atender, entre outros:

- bancos;
- financeiras;
- fintechs;
- cooperativas de crédito;
- FIDCs;
- empresas de BNPL;
- varejistas;
- marketplaces;
- instituições que concedem ou administram crédito.

A solução deverá permitir:

- recebimento de propostas de crédito;
- integração com fontes internas e externas;
- execução de regras e políticas de crédito;
- cálculo de indicadores de risco;
- análise antifraude;
- aprovação, reprovação ou encaminhamento para análise manual;
- explicabilidade das decisões;
- monitoramento posterior à concessão;
- auditoria completa;
- operação em ambiente multi-tenant.

## 3. Princípios gerais

### 3.1 Segurança por padrão

A plataforma deverá ser segura por padrão.

Todos os recursos, endpoints, serviços e dados devem ser considerados privados, salvo decisão explícita e documentada em contrário.

### 3.2 Privacidade por padrão

A coleta e o processamento de dados devem ser limitados ao necessário para a finalidade definida.

Dados pessoais, financeiros e sensíveis não devem ser armazenados, transmitidos ou registrados sem necessidade documentada.

### 3.3 Auditabilidade

Toda decisão relevante deve ser auditável.

Deve ser possível identificar:

- quem solicitou a análise;
- quando ela ocorreu;
- quais dados foram utilizados;
- qual política foi aplicada;
- qual versão do modelo foi utilizada;
- qual decisão foi tomada;
- quais fatores influenciaram o resultado;
- se houve intervenção manual.

### 3.4 Explicabilidade

As decisões de crédito e risco não devem retornar somente um resultado.

Quando aplicável, a plataforma deverá retornar:

- códigos de motivo;
- fatores favoráveis;
- fatores desfavoráveis;
- regras acionadas;
- indicadores calculados;
- versão da política;
- versão do modelo.

### 3.5 Evolução incremental

A solução deverá iniciar com a arquitetura mais simples que atenda aos requisitos atuais e permita evolução segura.

Não criar microsserviços, filas, bancos separados ou abstrações apenas pela possibilidade de uso futuro.

## 4. Organização do repositório

O projeto deverá utilizar um monorepo.

Estrutura inicial sugerida:

```text
services/
packages/
tests/
docs/
deploy/
scripts/
_bmad-output/
.github/
```

### 4.1 Serviços

Componentes implantáveis devem ficar em:

```text
services/
```

### 4.2 Bibliotecas compartilhadas

Bibliotecas reutilizáveis e tecnicamente genéricas devem ficar em:

```text
packages/
```

Não compartilhar:

- entidades específicas de domínio;
- regras de negócio entre bounded contexts;
- repositórios de persistência específicos;
- modelos internos apenas para evitar duplicação pequena.

### 4.3 Testes

Testes transversais devem ficar em:

```text
tests/integration/
tests/contract/
tests/e2e/
tests/performance/
tests/security/
```

Testes unitários específicos podem permanecer próximos ao código de cada serviço ou módulo.

## 5. Estratégia arquitetural inicial

A solução deverá começar preferencialmente como um monólito modular.

Módulos iniciais sugeridos:

- identidade e autenticação;
- tenants;
- usuários e permissões;
- clientes;
- propostas;
- integrações de dados;
- políticas de crédito;
- motor de decisão;
- análise de risco;
- análise antifraude;
- auditoria;
- notificações;
- relatórios.

A extração de um módulo para microsserviço deve ser justificada por pelo menos um dos seguintes fatores:

- necessidade de escalabilidade independente;
- requisitos específicos de segurança;
- isolamento de falhas;
- ciclo de entrega independente;
- necessidade de tecnologia diferente;
- volume operacional;
- autonomia de equipe;
- exigência regulatória ou contratual.

Toda extração deverá ser registrada em ADR.

## 6. Backend

Todo código de backend deverá ser escrito em Python.

### 6.1 Stack inicial sugerida

- Python;
- FastAPI;
- Pydantic;
- SQLAlchemy;
- Alembic;
- PostgreSQL;
- Redis, quando necessário;
- pytest;
- Ruff;
- mypy ou Pyright;
- OpenTelemetry;
- uv para dependências e workspace.

As versões oficiais devem ser definidas no `pyproject.toml` e nos arquivos de lock.

### 6.2 Inclusão de dependências

Uma nova biblioteca somente deverá ser adicionada após avaliação de:

- necessidade;
- manutenção ativa;
- maturidade;
- documentação;
- segurança;
- licença;
- compatibilidade;
- impacto em performance;
- custo de operação;
- existência de biblioteca equivalente no projeto.

Não substituir frameworks ou bibliotecas apenas por preferência do desenvolvedor ou do agente de IA.

## 7. Arquitetura de código

O código deverá aplicar os princípios SOLID quando eles aumentarem:

- coesão;
- testabilidade;
- legibilidade;
- isolamento de responsabilidades;
- capacidade de evolução.

Evitar:

- excesso de interfaces;
- factories desnecessárias;
- abstrações especulativas;
- herança sem necessidade;
- wrappers que não adicionam comportamento;
- camadas apenas para atender formalmente a um padrão.

Preferir:

- composição;
- funções pequenas;
- módulos coesos;
- dependências explícitas;
- separação entre domínio e infraestrutura;
- contratos claros;
- inversão de dependência em integrações externas.

## 8. Separação de responsabilidades

Controllers e endpoints não devem conter regras de negócio.

Eles devem ser responsáveis por:

- receber a requisição;
- validar o contrato;
- verificar autenticação e autorização;
- chamar o caso de uso;
- transformar o resultado;
- devolver a resposta.

Casos de uso devem coordenar:

- regras de negócio;
- persistência;
- serviços externos;
- publicação de eventos;
- auditoria.

O domínio não deverá depender diretamente de:

- FastAPI;
- SQLAlchemy;
- brokers;
- Redis;
- provedores externos;
- Kubernetes;
- bibliotecas de observabilidade.

## 9. Autenticação

Todas as requisições devem ser autenticadas por padrão.

Um endpoint somente poderá ser público quando houver aprovação explícita.

A solicitação de endpoint público deve apresentar:

- finalidade;
- dados recebidos;
- dados retornados;
- riscos;
- estratégia de rate limiting;
- proteção contra abuso;
- necessidade de CAPTCHA, assinatura ou token técnico;
- métricas;
- logs;
- testes;
- responsável pela aprovação.

Endpoints como health checks poderão possuir regras próprias, sem expor informações sensíveis.

## 10. Autorização

Autenticação não substitui autorização.

Toda operação deve validar:

- usuário;
- tenant;
- papel;
- permissão;
- recurso;
- contexto da operação.

A plataforma deverá adotar inicialmente RBAC e avaliar ABAC para casos que exijam políticas contextuais.

Nenhum endpoint deve confiar em um `tenant_id` recebido no payload sem validá-lo contra a identidade autenticada.

## 11. Multi-tenancy

Toda entidade pertencente a um cliente deve possuir contexto de tenant.

O isolamento deve ser aplicado em:

- banco de dados;
- cache;
- eventos;
- filas;
- arquivos;
- logs;
- métricas;
- relatórios;
- jobs;
- notificações;
- integrações externas.

Devem existir testes específicos demonstrando que um tenant não consegue acessar dados de outro.

A estratégia de multi-tenancy deverá ser formalizada em ADR.

Alternativas a serem analisadas:

- banco compartilhado e schema compartilhado;
- banco compartilhado e schema por tenant;
- banco por tenant;
- modelo híbrido.

## 12. Banco de dados

O banco relacional inicial sugerido é PostgreSQL.

O acesso deverá utilizar SQLAlchemy.

As alterações de schema deverão utilizar Alembic.

Nenhuma mudança estrutural deverá ser executada manualmente nos ambientes.

## 13. Migrations

Toda alteração de banco deverá possuir migration versionada.

Toda migration deverá:

- ser revisada;
- ser testada;
- considerar rollback ou recuperação;
- avaliar locks;
- avaliar volume de dados;
- avaliar índices;
- avaliar compatibilidade durante deployment;
- evitar operações destrutivas imediatas.

Alterações destrutivas devem utilizar estratégia expand-and-contract.

Exemplo:

1. criar a nova coluna;
2. disponibilizar código compatível;
3. migrar os dados;
4. alterar o uso da aplicação;
5. verificar a migração;
6. remover o campo antigo em uma entrega posterior.

Backfills extensos não devem ser executados obrigatoriamente dentro da mesma transação da migration.

## 14. Testes unitários

Toda alteração de comportamento deverá possuir testes automatizados.

Testes unitários são obrigatórios para:

- regras de negócio;
- casos de uso;
- validações;
- cálculos financeiros;
- políticas de crédito;
- políticas de risco;
- transformações;
- tratamento de erros;
- correções de bugs.

Toda correção de bug deverá incluir um teste de regressão.

O teste deve falhar antes da correção e passar após a correção.

Testes unitários não devem:

- acessar rede;
- acessar banco real;
- depender da ordem de execução;
- utilizar dados reais;
- acessar serviços de produção.

## 15. Testes de integração

A necessidade de teste de integração deve ser avaliada em toda alteração.

Testes de integração são obrigatórios quando houver mudança em:

- banco de dados;
- migrations;
- repositórios;
- cache;
- eventos;
- filas;
- autenticação;
- autorização;
- serialização;
- APIs externas;
- transações;
- configurações de infraestrutura;
- comunicação entre módulos ou serviços.

Quando um teste de integração não for criado, a justificativa deverá ser registrada na pull request ou story.

## 16. Testes de contrato

Testes de contrato são obrigatórios para alterações em:

- APIs;
- eventos;
- schemas;
- webhooks;
- integrações entre serviços;
- integrações com provedores externos.

Mudanças incompatíveis devem:

- gerar nova versão;
- manter período de compatibilidade;
- possuir plano de migração;
- estar documentadas.

## 17. Testes end-to-end

Testes end-to-end devem ser reservados aos fluxos críticos.

Fluxos iniciais sugeridos:

- autenticação;
- criação de tenant;
- submissão de proposta;
- coleta de informações;
- execução de política;
- decisão de crédito;
- análise manual;
- consulta da decisão;
- auditoria.

## 18. Testes de segurança

Devem existir testes para:

- autenticação ausente;
- token inválido;
- token expirado;
- permissão insuficiente;
- acesso entre tenants;
- alteração indevida de tenant;
- enumeração de recursos;
- entrada maliciosa;
- exposição de dados sensíveis;
- rate limiting;
- replay de requisições;
- idempotência.

## 19. Cobertura

A cobertura global de testes não deverá diminuir.

Metas iniciais sugeridas:

- cobertura global mínima de 80%;
- cobertura de código novo ou alterado de 90%;
- cobertura de domínio e motor de decisão de 95%.

Cobertura não substitui qualidade.

Não criar testes sem valor apenas para atingir um percentual.

Exclusões de cobertura devem ser justificadas.

## 20. APIs

As APIs devem possuir:

- schemas explícitos;
- validação de entrada;
- respostas padronizadas;
- erros padronizados;
- versionamento;
- documentação OpenAPI;
- paginação;
- correlation ID;
- idempotência quando necessária;
- timeouts;
- controle de retries.

Não retornar:

- stack trace;
- mensagens internas do banco;
- nomes de tabelas;
- detalhes de infraestrutura;
- tokens;
- secrets;
- dados de outros tenants.

Datas e horários deverão utilizar UTC e ISO 8601.

Valores monetários não devem utilizar ponto flutuante binário.

## 21. Idempotência

Operações como criação de proposta, execução de decisão, cobrança, publicação e callbacks devem avaliar idempotência.

Quando aplicável, a API deverá aceitar uma chave de idempotência.

O comportamento para repetição da chave deverá ser documentado.

## 22. Integrações externas

Toda integração externa deverá possuir:

- interface ou porta;
- adapter;
- timeout;
- retry controlado;
- circuit breaker quando necessário;
- métricas;
- logs seguros;
- tratamento de indisponibilidade;
- contrato versionado;
- ambiente de sandbox ou mock;
- testes de integração;
- estratégia de contingência.

As regras do domínio não devem depender diretamente do formato do provedor.

## 23. Eventos e mensageria

Eventos deverão ser utilizados quando houver necessidade real de:

- desacoplamento;
- processamento assíncrono;
- fan-out;
- resiliência;
- processamento posterior;
- integração entre contextos.

Todo consumidor deverá considerar:

- mensagens duplicadas;
- processamento fora de ordem;
- idempotência;
- dead-letter queue;
- retries;
- rastreabilidade;
- versionamento;
- tenant;
- correlation ID.

## 24. Decisões de crédito

Toda decisão deverá registrar:

- identificador;
- tenant;
- proposta;
- solicitante;
- horário;
- versão da política;
- versão do modelo;
- atributos utilizados;
- fontes de dados;
- regras executadas;
- resultado;
- códigos de motivo;
- score;
- limite recomendado;
- taxa recomendada, quando aplicável;
- intervenção manual;
- justificativa;
- correlation ID.

As decisões devem ser reproduzíveis dentro dos limites técnicos, legais e de retenção de dados.

## 25. Modelos de risco e inteligência artificial

Modelos não devem ser implantados sem:

- identificação;
- versão;
- owner;
- documentação;
- dados de treinamento conhecidos;
- métricas;
- validação;
- critérios de aprovação;
- explicabilidade;
- monitoramento;
- estratégia de rollback;
- avaliação de viés;
- política de atualização.

A saída de um modelo deve ser tratada como uma entrada da política de decisão, salvo decisão arquitetural explicitamente documentada.

Modelos generativos não devem tomar decisões finais de crédito sem controles determinísticos, validação e aprovação formal.

## 26. Auditoria

A trilha de auditoria deve ser separada dos logs operacionais.

Ela deverá registrar ações relevantes, incluindo:

- criação;
- alteração;
- exclusão lógica;
- decisão;
- override;
- aprovação;
- reprovação;
- exportação;
- acesso a dados sensíveis;
- alteração de política;
- alteração de modelo;
- alteração de permissão.

Registros de auditoria devem possuir proteção contra alteração indevida.

## 27. Dados sensíveis

Não registrar em logs:

- CPF completo;
- CNPJ completo quando desnecessário;
- dados bancários;
- tokens;
- senhas;
- dados biométricos;
- documentos;
- renda detalhada;
- informações de cartão;
- payloads completos de Open Finance;
- segredos;
- credenciais.

Dados de teste devem ser sintéticos.

A retenção deverá ser definida conforme finalidade, contrato e requisitos legais.

## 28. Observabilidade

Todos os componentes implantáveis devem possuir:

- logs estruturados;
- métricas;
- tracing;
- correlation ID;
- health check;
- readiness check;
- alertas;
- tratamento padronizado de erros.

Novas funcionalidades críticas devem definir:

- métricas técnicas;
- métricas de negócio;
- limites esperados;
- condições de alerta.

## 29. Containers

Todo componente implantável deverá possuir imagem de container.

As imagens devem:

- utilizar versões fixas;
- executar como usuário não root;
- utilizar multi-stage build quando necessário;
- conter apenas dependências de runtime;
- não conter secrets;
- possuir imagem mínima;
- permitir shutdown gracioso;
- possuir health check adequado;
- ser analisadas quanto a vulnerabilidades.

## 30. Kubernetes

Os serviços deverão ser preparados para execução em Kubernetes.

Cada workload deverá avaliar:

- requests de CPU e memória;
- limits;
- readiness probe;
- liveness probe;
- startup probe;
- autoscaling;
- disruption budget;
- graceful shutdown;
- configuração externa;
- secrets externos;
- network policies;
- service account;
- menor privilégio;
- estratégia de rollout;
- rollback.

Kubernetes não deve ser utilizado como justificativa automática para criação de microsserviços.

## 31. Infraestrutura como código

A infraestrutura deverá ser versionada.

Ferramentas sugeridas:

- Terraform para infraestrutura;
- Helm para empacotamento Kubernetes;
- manifests Kubernetes quando Helm não for necessário.

Nenhuma credencial deverá ser armazenada no código de infraestrutura.

## 32. Documentação

O `README.md` deve permanecer atualizado como porta de entrada.

Ele deve conter:

- visão geral;
- pré-requisitos;
- instalação;
- execução local;
- comandos principais;
- estrutura do projeto;
- links para documentação;
- instruções básicas de contribuição.

Documentação detalhada deverá ser distribuída em:

```text
docs/architecture/
docs/standards/
docs/adr/
docs/runbooks/
docs/api/
```

Toda mudança de código deverá avaliar a necessidade de atualização documental.

Código e documentação relacionados devem fazer parte da mesma alteração.

## 33. ADRs

Decisões arquiteturais relevantes devem ser registradas em ADR.

Exemplos:

- monorepo;
- monólito modular;
- framework web;
- banco de dados;
- multi-tenancy;
- autenticação;
- mensageria;
- storage;
- provedores de identidade;
- Kubernetes;
- estratégia de auditoria;
- estratégia de modelos.

Um ADR deve registrar:

- contexto;
- decisão;
- alternativas;
- consequências;
- riscos;
- status.

## 34. Qualidade de código

O projeto deverá possuir verificações automatizadas para:

- formatação;
- lint;
- tipagem;
- testes unitários;
- testes de integração;
- testes de contrato;
- segurança;
- dependências;
- migrations;
- build de imagens;
- vulnerabilidades.

O merge deverá ser bloqueado quando uma verificação obrigatória falhar.

## 35. Pull requests

Toda pull request deverá informar:

- objetivo;
- story relacionada;
- alterações;
- impactos;
- riscos;
- testes criados;
- testes executados;
- migrations;
- documentação;
- mudanças de contrato;
- evidências;
- pendências.

Não declarar que uma verificação foi executada sem que ela tenha sido efetivamente executada.

## 36. Uso de agentes de IA

Agentes de IA devem:

- ler o contexto do projeto antes de modificar código;
- respeitar as decisões arquiteturais;
- trabalhar dentro do escopo da story;
- não introduzir dependências sem justificativa;
- não criar endpoints públicos sem aprovação;
- não ignorar testes;
- não afirmar que testes passaram sem execução;
- atualizar a documentação;
- registrar dúvidas e riscos;
- preservar compatibilidade quando necessário.

Agentes não devem tomar decisões irreversíveis sobre:

- exposição pública;
- exclusão de dados;
- alteração destrutiva de banco;
- segurança;
- privacidade;
- mudança de arquitetura;
- mudança regulatória;
- adoção de fornecedor;
- substituição de tecnologia central.

## 37. Saídas esperadas do Brainstorm

Ao processar este documento, o Brainstorm deverá produzir:

### 37.1 Premissas confirmadas

Lista das premissas aceitas sem alterações.

### 37.2 Premissas ajustadas

Para cada ajuste:

- texto original;
- texto proposto;
- justificativa;
- impacto;
- risco.

### 37.3 Perguntas em aberto

Lista de decisões que precisam de esclarecimento.

### 37.4 Requisitos não funcionais

Converter as premissas em requisitos verificáveis nas categorias:

- segurança;
- privacidade;
- performance;
- disponibilidade;
- escalabilidade;
- resiliência;
- auditabilidade;
- observabilidade;
- manutenibilidade;
- testabilidade;
- interoperabilidade;
- portabilidade;
- continuidade.

### 37.5 Decisões arquiteturais necessárias

Listar os ADRs que deverão ser criados.

### 37.6 Distribuição documental

Indicar quais regras deverão ser colocadas em:

- `AGENTS.md`;
- `_bmad-output/project-context.md`;
- `docs/architecture/`;
- `docs/standards/`;
- `docs/adr/`;
- `README.md`;
- `CONTRIBUTING.md`;
- `pyproject.toml`;
- pipelines;
- manifests;
- templates de pull request.

### 37.7 Quality gates

Definir as verificações que deverão bloquear merge e deployment.

### 37.8 Riscos

Criar um registro inicial de riscos técnicos, operacionais, regulatórios e de segurança.

## 38. Restrições ao Brainstorm

O Brainstorm não deverá:

- transformar todas as sugestões em requisitos obrigatórios;
- escolher ferramentas sem justificativa;
- criar microsserviços automaticamente;
- tratar cobertura como único indicador de qualidade;
- confundir autenticação com autorização;
- ignorar multi-tenancy;
- ignorar auditoria;
- assumir que inteligência artificial será necessária em todas as decisões;
- definir tecnologia apenas por popularidade;
- alterar premissas sem registrar a alteração.

## 39. Resultado esperado

Ao final, as premissas deverão estar organizadas de forma que:

- o Product Brief registre objetivos e diferenciais;
- o PRD registre requisitos funcionais e não funcionais;
- a Architecture registre as decisões técnicas;
- os ADRs registrem decisões relevantes;
- o `project-context.md` contenha regras críticas para agentes;
- o `AGENTS.md` contenha instruções operacionais para o Codex;
- os padrões detalhados estejam em `docs/standards/`;
- as regras executáveis estejam nos arquivos de configuração e CI.
