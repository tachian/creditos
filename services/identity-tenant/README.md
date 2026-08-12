# Identity & Tenant Service

Microsserviço responsável pelo catálogo mínimo de tenants do CreditOS.

## Escopo atual

- Cadastro mínimo de tenants com status e `tenant_isolation_tier`.
- Consulta segura de metadados mínimos de tenant.
- Resolução local/testável de contexto M2M por token determinístico e catálogo de tenant.
- Autorização local/testável por RBAC, scopes e claims/contexto de tenant para operações sensíveis.
- Logs estruturados com rastreabilidade e mascaramento por meio dos pacotes compartilhados.

## Fora do escopo desta story

- Provedor OAuth/OIDC real, emissão real de tokens, rotação real de JWKS, catálogo persistido completo de roles/permissions/scopes e console humano.
- Migração `bridge → silo` e criação automática de recursos dedicados.
- Implementação completa do servidor gRPC.
- ABAC, FAPI 2.0, engines externas de policy e propagação completa de contexto entre serviços.

## Autenticação M2M local

- O fluxo implementado nesta etapa usa uma porta de aplicação para verificação M2M e um adapter determinístico para harness/testes.
- O adapter local simula validações de `iss`, `aud`, `sub`/`client_id`, `exp`, `iat`, `jti`, `scope`, `tenant_id`, `kid` e algoritmo aceito.
- O `tenant_id` confiável vem do token validado e é confirmado no catálogo interno; `tenant_id` vindo de payload não é fonte de verdade.
- Tokens, secrets e header `Authorization` não devem aparecer em logs.

## Autorização local

- A autorização aplica `deny-by-default`: operações sensíveis precisam existir na registry local, com scopes obrigatórios e roles obrigatórias por padrão.
- Operações `scope-only` só são permitidas quando declaradas explicitamente na registry com `allow_scope_only=True`; callers não podem autodeclarar requisitos arbitrários.
- Bordas futuras HTTP, gRPC e eventos devem chamar a fachada de autorização antes de executar operações sensíveis, em vez de instanciar requisitos manualmente.
- O tenant do recurso protegido é comparado ao tenant autenticado; divergência gera bloqueio cross-tenant com erro seguro.
- O modelo inicial é local e substituível, sem engine externa de policy; catálogo persistido e ABAC ficam para evolução futura.
- Logs de autorização usam `source=authorization-context` e registram decisão minimizada em `authz_decision`, operação, requisitos, sujeito e tenant confiável, sem payload bruto, token ou segredo.

## Propagação de contexto confiável

- O serviço expõe adapters locais para derivar contexto propagável a partir de
  `AuthorizationSubject` e `ResolvedM2MTenantContext`, sem propagar `token_id`.
- Chamadas internas gRPC devem serializar o contexto como metadata técnica e
  validar a metadata recebida e o tenant esperado antes do caso de uso.
- Eventos CloudEvents devem transportar tenant, sujeito, scopes, correlação,
  request ID, `traceparent` e versão de schema em atributos/extensões, não em
  payload sensível; consumidores validam envelope core e `idempotencykey`.
- A validação rejeita metadata ou atributos ausentes, malformados, binários,
  com uppercase/underscore inválido, token, segredo, CPF/CNPJ ou e-mail bruto.
- Rejeições de contexto podem ser registradas com `source=trusted-context`,
  sempre limpando tenant recebido antes da validação.
- O protobuf `TenantContextService` permanece backward-compatible: a propagação
  padronizada nesta etapa usa metadata gRPC, portanto não exige novos campos na
  mensagem estrutural.

## Camadas

- `domain`: entidades, value objects, erros e invariantes puros.
- `application`: casos de uso, portas e serviço de aplicação.
- `adapters`: persistência em memória, logger em memória e futuras bordas.
- `bootstrap`: composição local para testes e harness.
