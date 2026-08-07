# Identity & Tenant Service

Microsserviço responsável pelo catálogo mínimo de tenants do CreditOS.

## Escopo atual

- Cadastro mínimo de tenants com status e `tenant_isolation_tier`.
- Consulta segura de metadados mínimos de tenant.
- Resolução local/testável de contexto M2M por token determinístico e catálogo de tenant.
- Logs estruturados com rastreabilidade e mascaramento por meio dos pacotes compartilhados.

## Fora do escopo desta story

- Provedor OAuth/OIDC real, emissão real de tokens, rotação real de JWKS, RBAC completo e console humano.
- Migração `bridge → silo` e criação automática de recursos dedicados.
- Implementação completa do servidor gRPC.

## Autenticação M2M local

- O fluxo implementado nesta etapa usa uma porta de aplicação para verificação M2M e um adapter determinístico para harness/testes.
- O adapter local simula validações de `iss`, `aud`, `sub`/`client_id`, `exp`, `iat`, `jti`, `scope`, `tenant_id`, `kid` e algoritmo aceito.
- O `tenant_id` confiável vem do token validado e é confirmado no catálogo interno; `tenant_id` vindo de payload não é fonte de verdade.
- Tokens, secrets e header `Authorization` não devem aparecer em logs.

## Camadas

- `domain`: entidades, value objects, erros e invariantes puros.
- `application`: casos de uso, portas e serviço de aplicação.
- `adapters`: persistência em memória, logger em memória e futuras bordas.
- `bootstrap`: composição local para testes e harness.
