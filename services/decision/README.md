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

## Arquitetura

O serviço segue DDD + arquitetura hexagonal:

- `domain`: entidades, value objects e erros sem dependência de infraestrutura;
- `application`: casos de uso, comandos e portas;
- `adapters`: implementações de infraestrutura, iniciando por persistência in-memory;
- `bootstrap`: ponto futuro de composição.

Políticas não devem carregar CPF, CNPJ, e-mail completo, nome, endereço, token, segredo, payload bruto de proposta ou payload proprietário de fornecedor.

O `tenant_id` e o ator efetivo nunca são aceitos como autoridade do comando de aplicação; ambos vêm do contexto confiável propagado.
