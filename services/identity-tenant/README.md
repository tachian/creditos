# Identity & Tenant Service

Microsserviço responsável pelo catálogo mínimo de tenants do CreditOS.

## Escopo atual

- Cadastro mínimo de tenants com status e `tenant_isolation_tier`.
- Consulta segura de metadados mínimos de tenant.
- Logs estruturados com rastreabilidade e mascaramento por meio dos pacotes compartilhados.

## Fora do escopo desta story

- OAuth/OIDC real, Client Credentials, RBAC completo e console humano.
- Migração `bridge → silo` e criação automática de recursos dedicados.
- Implementação completa do servidor gRPC.

## Camadas

- `domain`: entidades, value objects, erros e invariantes puros.
- `application`: casos de uso, portas e serviço de aplicação.
- `adapters`: persistência em memória, logger em memória e futuras bordas.
- `bootstrap`: composição local para testes e harness.
