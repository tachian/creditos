# Decision Service

Microsserviço responsável por políticas, versões, decisões, códigos de motivo, inconclusivos e termos aprovados no CreditOS.

## Story 4.1

O escopo inicial implementa somente o modelo versionado de política de crédito em draft:

- criação de política em `draft`;
- alteração rastreável de draft;
- proteção contra mutação de versões `published` e `archived`;
- isolamento por tenant usando `creditos_security.PropagatedContext`;
- autorização por scopes `policy:write` e `policy:read`;
- suporte inicial somente ao modelo multi-tenant `bridge`;
- intenção auditável minimizada para criação, alteração e rejeições sensíveis.

Ficam fora desta etapa: motor de decisão, publicação produtiva, simulação, catálogo completo de reason codes, banco real, NATS, HTTP/gRPC real e IA.

## Story 4.2

O catálogo versionado de reason codes e fatores explicáveis adiciona:

- reason codes governados por tenant, produto, versão, revisão, status e changelog;
- fatores explicáveis allowlistados sobre campos canônicos seguros;
- descrições internas e externas curtas, compreensíveis e sem dados sensíveis;
- validação obrigatória de `PolicyRule.reason_code_refs`;
- verificação de reason codes ativos e compatíveis com o outcome da regra;
- criação de nova versão quando uma mudança incompatível altera semântica, outcome, descrição externa, remoção ou fator obrigatório;
- repositório in-memory com isolamento por tenant;
- casos de uso de aplicação com `PropagatedContext`, scopes `policy:write`/`policy:read`, logs estruturados com payload omitido e intenção auditável minimizada.

Catálogos em `draft` podem apoiar validação de políticas em draft, mas não devem ser usados como referência produtiva para decisões finais. Para decisão final, o catálogo deve estar `published`.

Ficam fora desta etapa: motor de decisão determinística, simulação, publicação produtiva por API real, persistência em banco, NATS, gRPC/HTTP real, IA e resposta pública de decisão explicável.

## Story 4.3

A simulação e validação de política adiciona um fluxo não produtivo para avaliar drafts:

- casos de entrada minimizados e allowlistados por campos canônicos governados;
- rejeição de CPF, CNPJ, e-mail, nome, endereço, payload bruto, payload de fornecedor, `metadata`, `custom` e valores sensíveis identificáveis;
- execução determinística simples sobre critérios, limites e regras existentes, sem motor externo;
- resultado por caso com outcome, regras acionadas, reason codes, fatores explicáveis, IDs da política/catálogo e `correlation_id`;
- marcação explícita `simulation`/`non_production=true` em resultados e casos;
- repositório in-memory de execuções de simulação isolado por tenant;
- consulta segura de resultado de simulação com `policy:read`;
- limite operacional inicial de 100 casos por simulação;
- detecção de outcomes conflitantes entre regras acionadas, retornando resultado inconclusivo com issue log-safe;
- caso de uso `run_policy_simulation` com `PropagatedContext`, tier `bridge`, scope `policy:write`, logs com payload omitido e intenção auditável minimizada.

A simulação não cria decisão produtiva, não publica evento final de decisão, não altera status de proposta, não publica política e não chama IA, Integration Service ou fornecedor externo.

## Story 4.4

A publicação imutável de política aprovada adiciona o lifecycle produtivo de versões:

- publicação de política `draft` como `published` somente com vigência UTC explícita;
- exigência de catálogo de reason codes `published` para uso produtivo;
- exigência de simulação prévia da mesma política/versão/tenant com status `completed` e sem issues;
- proteção forte contra alteração de snapshot publicado;
- criação de nova versão `draft` para qualquer correção em política já publicada;
- consulta de versão publicada aplicável por tenant, produto, canal e data efetiva;
- bloqueio de janelas de vigência conflitantes para mesmo tenant/produto/canal;
- scope dedicado `policy:publish` para publicar ou derivar nova versão;
- auditoria minimizada para publicação/versionamento/rejeição e rollback quando auditoria crítica falha.

A publicação não executa decisão final, não cria `decision_id`, não publica evento final de decisão, não chama Proposal Intake, Integration Service, IA, NATS ou banco real.

## Story 4.5

A execução determinística de decisão adiciona o primeiro fluxo produtivo interno:

- entidade `CreditDecision` com `decision_id`, `proposal_id`, tenant, produto, canal, horário UTC, política/catálogo versionados, outcome, regras acionadas, reason codes, fatores explicáveis, issues controladas e fingerprint estável;
- input produtivo minimizado por campos canônicos governados, sem CPF, CNPJ, e-mail, nome, endereço, payload bruto, headers, tokens, secrets ou payload proprietário de fornecedor;
- avaliador determinístico comum para simulação e decisão real, preservando a restrição de que simulação continua não produtiva e limitada a políticas em `draft`;
- execução somente contra política `published` aplicável por tenant, produto, canal e data efetiva;
- catálogo de reason codes deve estar `published` para decisão final;
- `approve` produtivo exige termos aprovados completos; `approve_with_changes` fica bloqueado até existir modelo explícito e rastreável de termos ajustados;
- scope dedicado `decision:execute`, separado dos scopes de política;
- repositório in-memory próprio para decisões, com isolamento por tenant e controle de duplicidade por proposta;
- auditoria crítica minimizada antes da decisão ficar visível no repositório ou ser retornada como final;
- logs estruturados com payload omitido e apenas metadados seguros.

Ficam fora desta etapa: API HTTP/gRPC real, NATS JetStream, outbox transacional, banco real, callbacks/webhooks, Reporting, consulta pública de decisão, IA consultiva e chamadas diretas ao Integration Service ou fornecedores externos.

## Story 4.6

O tratamento de propostas inconclusivas sem fila manual adiciona fallback governado e rastreável:

- `fallback_action` passa a fazer parte da política versionada, com valores permitidos `request_more_data`, `unable_to_decide` e `reject_by_policy`;
- `request_additional_data` do épico é representado internamente pelo outcome governado existente `request_more_data`, evitando duplicidade semântica;
- políticas publicadas incluem o fallback no fingerprint governado, exigindo nova versão/revisão para mudança de comportamento;
- tentativas de usar `manual_review`, fila manual, `human_override` ou aliases equivalentes são rejeitadas no MVP;
- lacunas de dados, ausência de regra e conflitos geram outcome controlado, nunca aprovação implícita;
- `reject_by_policy` só produz outcome `reject` quando há condição governada e reason code compatível no catálogo;
- `approve_with_changes` passa a ser permitido somente com `approved_terms` completos, explicitamente derivados dos limites da política e diferentes dos `requested_terms`;
- auditoria e logs incluem outcome, fallback, contagem/referências seguras de dados requeridos, policy/catalog refs, correlation ID e fingerprint, mantendo payload omitido;
- os dados registrados preparam métricas futuras de funil por tenant, produto, canal, política, outcome e fallback sem expor PII.

Ficam fora desta etapa: contrato público de resposta explicável, dashboards, Reporting Service, Automated Review Service, API HTTP/gRPC real, NATS JetStream, banco real, outbox e integrações externas reais.

## Story 4.7

A resposta explicável de decisão adiciona uma projeção segura e governada para decisões produtivas:

- resposta `CreditDecisionExplanationResponse` derivada da decisão persistida e do catálogo versionado publicado;
- campos técnicos para rastreabilidade: decisão, proposta, tenant, produto, canal, outcome, status, data, correlação, política, catálogo, regras acionadas e fingerprint;
- reason codes e fatores filtrados por audiência, usando descrições externas por padrão e descrições internas somente com scope explícito;
- consultas internas por `decision_id` e `proposal_id` com scope `decision:read`, contexto confiável e tenant isolation `bridge`;
- cross-tenant continua indistinguível de decisão inexistente;
- execução produtiva passa a retornar `decision` e `explanation`, mantendo compatibilidade com consumidores que usam `result.decision`;
- decisões finais `approve`, `reject` e `approve_with_changes` exigem reason code ativo e coerente com o catálogo;
- estados controlados `request_more_data` e `unable_to_decide` exigem justificativa equivalente por lacunas, issues, fallback ou reason code;
- logs e auditoria de leitura/explicação registram apenas metadados seguros, contagens e referências técnicas, com payload omitido.

A resposta explicável não expõe `field_values`, `requested_terms`, CPF, CNPJ, e-mail, nome, telefone, endereço, headers sensíveis, tokens, secrets, payload bruto ou resposta bruta de fornecedor.

Ficam fora desta etapa: API pública HTTP, contrato OpenAPI externo, gRPC real, NATS JetStream, webhooks, dashboards, Reporting Service, banco real e integração com IA.

## Story 4.8

Os gates de decisão, política e explicabilidade consolidam regressões para encerrar o Epic 4:

- cobertura transversal do ciclo de política: criação, catálogo de reason codes, simulação, publicação, execução, inconclusão e resposta explicável;
- validação de que decisões finais sempre carregam refs de política, versão/revisão, catálogo versionado e reason codes governados quando aplicável;
- verificação de determinismo com fingerprint decisório estável para a mesma entrada canônica, sem depender de `decision_id`, timestamp ou `correlation_id`;
- proteção contra IA, integração externa, provider payload ou resultado proprietário como decisor final direto;
- preservação de `CreditDecision`/`Decision Service` como fonte única transacional da decisão final no MVP;
- regressões para justificativa visível em decisões finais e justificativa equivalente segura em estados controlados;
- gates de privacidade para impedir CPF, CNPJ, e-mail, nome, telefone, endereço, tokens, secrets, headers sensíveis, payload bruto ou renda detalhada em respostas, logs e auditoria;
- testes de autorização, `tenant_isolation_tier=bridge`, cross-tenant indistinguível de not found e auditoria/logs minimizados.

Esta etapa não adiciona tecnologia, dependência, endpoint público, OpenAPI externo, gRPC real, NATS, banco real, IA real, serviço novo ou outbox. Lacunas estruturais descobertas pelos gates devem ser registradas como trabalho futuro, não resolvidas com overbuild local.

## Arquitetura

O serviço segue DDD + arquitetura hexagonal:

- `domain`: entidades, value objects e erros sem dependência de infraestrutura;
- `application`: casos de uso, comandos e portas;
- `adapters`: implementações de infraestrutura, iniciando por persistência in-memory;
- `bootstrap`: ponto futuro de composição.

Políticas não devem carregar CPF, CNPJ, e-mail completo, nome, endereço, token, segredo, payload bruto de proposta ou payload proprietário de fornecedor.

O `tenant_id` e o ator efetivo nunca são aceitos como autoridade do comando de aplicação; ambos vêm do contexto confiável propagado.
