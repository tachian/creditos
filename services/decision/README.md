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

## Arquitetura

O serviço segue DDD + arquitetura hexagonal:

- `domain`: entidades, value objects e erros sem dependência de infraestrutura;
- `application`: casos de uso, comandos e portas;
- `adapters`: implementações de infraestrutura, iniciando por persistência in-memory;
- `bootstrap`: ponto futuro de composição.

Políticas não devem carregar CPF, CNPJ, e-mail completo, nome, endereço, token, segredo, payload bruto de proposta ou payload proprietário de fornecedor.

O `tenant_id` e o ator efetivo nunca são aceitos como autoridade do comando de aplicação; ambos vêm do contexto confiável propagado.
