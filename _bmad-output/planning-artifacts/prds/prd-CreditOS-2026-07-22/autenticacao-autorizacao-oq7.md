# Autenticação e autorização - OQ-7

Data: 2026-07-24
Status: decisão registrada para PRD e insumo de Architecture/ADRs

## Decisão

O CreditOS adotará OIDC/OAuth 2.0 como base de autenticação e identidade.

Para integrações máquina-a-máquina, o fluxo padrão será OAuth 2.0 Client Credentials. Para usuários humanos em console ou superfícies administrativas, o fluxo padrão será OIDC Authorization Code + PKCE.

A autorização inicial do MVP usará RBAC, scopes e claims de tenant. ABAC fica planejado para regras contextuais futuras. FAPI 2.0 deve ser avaliado para endpoints de maior risco, APIs financeiras sensíveis ou integrações que exigirem perfil de segurança avançado.

## Responsabilidade por serviço

`Identity & Tenant Service` é dono de:

- tenants;
- usuários;
- clientes técnicos;
- roles;
- permissions;
- scopes;
- claims;
- chaves;
- configuração de produtos/canais habilitados;
- contexto confiável do tenant.

Os demais serviços validam o contexto recebido e aplicam autorização local conforme padrão comum, mas não devem inventar modelos próprios de identidade.

## Fluxos

### Máquina-a-máquina

- Fluxo: OAuth 2.0 Client Credentials.
- Uso: submissão de propostas, consulta de decisões, callbacks autorizados e integração sistêmica.
- Cliente: instituição, financeira, originador, marketplace ou sistema parceiro.
- Token: access token curto com scopes e claims de tenant.

### Usuários humanos

- Fluxo: OIDC Authorization Code + PKCE.
- Uso: console administrativo, gestão de políticas, dashboards, evidências e operação interna.
- Token: access token curto; refresh token apenas quando necessário e com política de rotação.

## Claims e campos mínimos

Quando aplicável, tokens e contexto autenticado devem conter ou permitir resolver:

- `iss`.
- `aud`.
- `sub`.
- `exp`.
- `iat`.
- `jti`.
- `tenant_id`.
- `tenant_isolation_tier`.
- `scope`.
- `roles`.
- produtos/canais habilitados ou referência para consulta autorizada.

## Autorização

### MVP

- RBAC para papéis.
- Scopes para capacidades de API.
- Claims para contexto de tenant.
- Permissões sensíveis com auditoria obrigatória.

Exemplos de scopes:

- `proposal:submit`.
- `proposal:read`.
- `decision:read`.
- `policy:read`.
- `policy:write`.
- `tenant:admin`.
- `audit:read`.
- `report:read`.

### Evolução

ABAC deve ser avaliado quando regras exigirem contexto adicional, como:

- produto;
- canal;
- horário;
- origem/IP;
- risco da operação;
- sensibilidade do dado;
- tier do tenant;
- ação solicitada;
- estado da proposta.

## Propagação interna

Chamadas gRPC internas devem propagar por metadata:

- `tenant_id`.
- sujeito/cliente técnico.
- scopes relevantes.
- roles ou referência de autorização.
- correlation ID.
- trace ID.
- request ID quando aplicável.

Eventos devem carregar contexto mínimo de tenant, correlation ID, evento, versão e origem.

## Segurança obrigatória

- Access tokens curtos.
- Rotação de chaves.
- JWKS para validação de assinatura.
- Validação de `iss`, `aud`, `exp`, `nbf` quando aplicável, `jti`, scopes e claims de tenant.
- Rejeição de token sem tenant quando endpoint exigir tenant.
- Auditoria para alteração de usuário, cliente técnico, role, permissão, escopo, chave e acesso sensível.
- Proibição de segredo bruto em logs, eventos, callbacks e respostas.
- Rate limit por tenant e cliente técnico.

## Opções avançadas

Para clientes de maior risco ou endpoints financeiros sensíveis, avaliar:

- `private_key_jwt`.
- mTLS.
- DPoP.
- FAPI 2.0.
- ABAC.
- step-up authentication para ações humanas sensíveis.

## Decisões não tomadas

- Provedor concreto de identidade ainda não foi escolhido.
- Critérios exatos para FAPI 2.0 ainda serão definidos pela Architecture/ADR.
- Modelo completo de ABAC fica fora do MVP, salvo exigência antecipada.

## Fontes

- RFC 9700 OAuth 2.0 Security Best Current Practice: https://www.rfc-editor.org/info/rfc9700
- OpenID Connect Core 1.0: https://openid.net/specs/openid-connect-core-1_0.html
- NIST SP 800-63-4: https://pages.nist.gov/800-63-4/
- FAPI 2.0 Security Profile: https://openid.net/specs/fapi-security-profile-2_0.html
