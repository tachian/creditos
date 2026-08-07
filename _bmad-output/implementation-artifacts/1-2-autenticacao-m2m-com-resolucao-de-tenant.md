---
baseline_commit: 07b98349246fc32625dd25051d1fd2174b94b08b
jira_issue: CTOS-24
branch: agent/story-1-2-autenticacao-m2m-tenant
---

# Story 1.2: Autenticação M2M com Resolução de Tenant

Status: done

## Story

As a cliente técnico,
I want autenticar chamadas de API via Client Credentials,
so that minhas requisições sejam associadas ao tenant correto sem confiar no body.

## Acceptance Criteria

1. **Token válido resolve tenant confiável**
   - **Given** uma requisição com token M2M válido
   - **When** a API valida o token
   - **Then** resolve `tenant_id` e `tenant_isolation_tier` pelo contexto autenticado e pelo catálogo do `Identity & Tenant`
   - **And** propaga contexto mínimo confiável para uso por adapters/casos de uso internos.

2. **Payload não é fonte de verdade de tenant**
   - **Given** uma requisição autenticada cujo payload contém `tenant_id`
   - **When** o tenant do payload diverge do tenant autenticado
   - **Then** a operação não usa o `tenant_id` do payload como autoridade
   - **And** rejeita tentativa explícita de spoofing cross-tenant com erro padronizado.

3. **Falhas de autenticação são seguras e padronizadas**
   - **Given** uma requisição sem token, com token expirado, issuer inválido, audiência inválida, assinatura inválida, `kid` desconhecido ou claims obrigatórias ausentes
   - **When** a API recebe a chamada
   - **Then** rejeita com erro padronizado
   - **And** não expõe detalhes internos, token bruto, segredo, stack trace ou motivo criptográfico sensível.

4. **Rastreabilidade sem vazamento sensível**
   - **Given** uma tentativa de autenticação ou resolução de tenant
   - **When** a operação é processada
   - **Then** logs estruturados incluem `correlation_id`, `request_id`, `trace_id`, operação, status, duração e `tenant_id` quando confiável
   - **And** headers `Authorization`, access token, client secret, JWK privada, CPF/CNPJ, e-mail completo e payload sensível nunca aparecem em logs.

## Tasks / Subtasks

- [x] CTOS-115 — Modelar porta de verificação de token M2M e contexto autenticado (AC: 1, 3)
  - [x] Criar porta em `application/ports` para validação de access token M2M, sem acoplar domínio a JWT, FastAPI, gRPC, JWKS real ou provedor específico.
  - [x] Criar modelo de aplicação para contexto autenticado com `client_id`, `subject`, `scopes`, `tenant_id`, `tenant_isolation_tier`, `issuer`, `audience`, `token_id`/`jti`, `issued_at` e `expires_at`.
  - [x] Validar que `tenant_id` e `tenant_isolation_tier` usados pela aplicação vêm de claims autenticadas e/ou catálogo confiável, não do body.

- [x] CTOS-116 — Implementar adapter determinístico de token para harness local (AC: 1, 3)
  - [x] Criar adapter local/fake em `adapters/external` ou `adapters/api` para simular validação de token sem depender de IdP real.
  - [x] Cobrir cenários de assinatura/algoritmo aceito, `iss`, `aud`, `sub`/`client_id`, `exp`, `nbf` quando presente, `iat`, `jti`, `scope`, `tenant_id` e `kid`.
  - [x] Não introduzir provedor real de identidade nesta story; escolha de IdP, introspection real, FAPI 2.0, DPoP, `private_key_jwt` e mTLS de cliente ficam para ADR/story futura.

- [x] CTOS-117 — Resolver tenant pelo contexto autenticado e catálogo interno (AC: 1, 2)
  - [x] Reutilizar `GetTenantUseCase` e o repositório de tenant existente para confirmar existência/status/tier do tenant autenticado.
  - [x] Ignorar `tenant_id` de payload como fonte de verdade; aceitar apenas para comparação defensiva quando o contrato de borda trouxer esse campo.
  - [x] Rejeitar tenant inexistente, inativo ou incompatível com erro seguro e sem consulta cross-service direta a banco.

- [x] CTOS-118 — Padronizar erros seguros de autenticação M2M (AC: 3)
  - [x] Adicionar erros estáveis para token ausente, token inválido, token expirado, audiência inválida, issuer inválido, claim obrigatória ausente e contexto de tenant inválido.
  - [x] Mapear erros para códigos seguros de aplicação e `grpc_status`/equivalente, preservando a convenção de `TenantDomainError`.
  - [x] Garantir que mensagens públicas sejam genéricas e que detalhes internos fiquem fora de resposta/log operacional.

- [x] CTOS-119 — Aplicar logs mascarados e rastreabilidade para autenticação (AC: 4)
  - [x] Reutilizar `ObservabilityContext`, `build_structured_log` e `creditos_security.mask_sensitive_data`.
  - [x] Registrar operação, status, duração, correlation/request/trace IDs, `client_id` quando seguro e `tenant_id` apenas depois de confiável.
  - [x] Tornar logging best-effort, seguindo o aprendizado da Story 1.1: falha de logger não deve mascarar o resultado real da autenticação/resolução.

- [x] CTOS-120 — Criar testes de autenticação, spoofing e logs seguros (AC: 1, 2, 3, 4)
  - [x] Testar token válido resolvendo tenant e tier.
  - [x] Testar token ausente, expirado, audience inválida, issuer inválido, `kid` desconhecido e claims obrigatórias ausentes.
  - [x] Testar tentativa de spoofing via payload com `tenant_id` divergente.
  - [x] Testar tenant inexistente/inativo quando a claim aponta para tenant não utilizável.
  - [x] Testar que token, segredo, header `Authorization` e payload sensível não aparecem em logs.

- [x] CTOS-121 — Sincronizar BMAD/Jira e registrar evidências da Story 1.2 (AC: 1, 2, 3, 4)
  - [x] Manter `CTOS-24` em WIP durante desenvolvimento e mover para Review QA antes de `bmad-code-review`.
  - [x] Atualizar subtarefas no Jira conforme forem concluídas.
  - [x] Atualizar esta story com arquivos alterados, notas de conclusão e resultado dos gates.

### Review Findings

- [x] [Review][Patch] Modelar assinatura inválida no adapter local [services/identity-tenant/src/creditos_identity_tenant/adapters/external/local_m2m_token_verifier.py:20] — A story exige rejeitar assinatura inválida, mas o adapter só valida `kid` e `algorithm`. Adicionar uma representação determinística de assinatura válida/inválida no harness local e teste que rejeite assinatura inválida com erro seguro.

- [x] [Review][Patch] Endurecer validação de claims, scopes e datas malformadas [services/identity-tenant/src/creditos_identity_tenant/adapters/external/local_m2m_token_verifier.py:83] — Claims como `algorithm=None`, `key_id=[]`, `issued_at=None`, `expires_at` não-`datetime`, `scopes` como mapping/bytes/iterável aninhado ou itens não-string podem gerar exceções não padronizadas ou aceitação silenciosa. Validar tipos em runtime, normalizar `required_scopes` da mesma forma que `scope`, rejeitar `clock_skew_seconds` negativo e validar relações temporais `iat <= exp` e `nbf <= exp`; adicionar testes para `nbf`, `iat` futuro, scopes obrigatórios e tipos inválidos.

- [x] [Review][Patch] Converter tenant inexistente para erro M2M seguro [services/identity-tenant/src/creditos_identity_tenant/application/use_cases/resolve_m2m_tenant_context.py:80] — O fluxo M2M hoje propaga `TenantNotFoundError`/`NOT_FOUND`, permitindo inferir existência no catálogo de tenants. No contexto de autenticação M2M, tenant inexistente ou inválido deve virar `InvalidTenantContextError`/mensagem segura sem enumeração.

- [x] [Review][Patch] Impedir exposição de `Authorization` no `repr` do comando M2M [services/identity-tenant/src/creditos_identity_tenant/application/use_cases/resolve_m2m_tenant_context.py:25] — O logger omite payload, mas `ResolveM2MTenantContextCommand` ainda pode expor o header em debug/repr/falhas futuras. Marcar `authorization_header` com `repr=False` e testar que token bruto não aparece no `repr`.

- [x] [Review][Patch] Expor composição M2M no bootstrap local [services/identity-tenant/src/creditos_identity_tenant/bootstrap/app.py:12] — O README promete fluxo M2M local/testável, mas `build_local_tenant_application_service` não aceita nem injeta verificador M2M. Permitir composição explícita do `m2m_token_verifier` no bootstrap local e testar esse caminho.

- [x] [Review][Patch] Evitar confusão entre cliente técnico e sujeito humano [services/identity-tenant/src/creditos_identity_tenant/adapters/external/local_m2m_token_verifier.py:67] — `sub` e `client_id` só precisam ser textos não vazios. Para o adapter M2M local, exigir relação determinística segura, como `subject == client_id`, e testar rejeição quando divergirem.

- [x] [Review][Patch] Limpar tenant não confiável em logs de falha M2M [services/identity-tenant/src/creditos_identity_tenant/application/service.py:160] — Em falhas, o serviço registra o `ObservabilityContext` recebido; se ele vier pré-populado com tenant ainda não autenticado, o log pode associar rejeições a tenant falso. Limpar `tenant_id` e `tenant_isolation_tier` no caminho de erro M2M, exceto após validação bem-sucedida.

- [x] [Review][Patch] Validar sintaxe Bearer de forma estrita [services/identity-tenant/src/creditos_identity_tenant/application/ports/m2m_token_verifier.py:75] — `Bearer abc def`, CR/LF, vírgulas ou múltiplos valores podem avançar ao verifier como token literal. Aplicar parser estrito para token sem whitespace/caracteres de controle e cobrir headers anômalos em teste.

## Dev Notes

### Escopo desta story

- Implementar autenticação M2M local/testável e resolução confiável de tenant dentro do `Identity & Tenant Service`.
- Não implementar provedor real de identidade, console humano, RBAC completo, gestão completa de roles/scopes, emissão real de tokens, rotação real de chaves, introspection remota, API pública definitiva, service mesh, mTLS de produção ou autorização ABAC/FAPI.
- O objetivo é criar o contrato interno de aplicação e o caminho seguro para que chamadas M2M futuras nunca confiem em `tenant_id` vindo do body.
- Esta story deve continuar compatível com o harness local e preparar a Story 1.3 para autorização por RBAC, scopes e claims.

### Regras de arquitetura obrigatórias

- Backend segue DDD + arquitetura hexagonal: `domain` contém invariantes puras; `application` orquestra casos de uso/portas; `adapters` integram borda, logging, token verification e persistência; `bootstrap` compõe dependências.
- `Identity & Tenant` é a fonte de verdade para tenants, clientes técnicos, usuários, roles, permissões, scopes, claims, chaves e contexto confiável.
- Segurança é `deny-by-default`; qualquer bypass local para testes precisa ser explícito, limitado e coberto por teste.
- `tenant_id` confiável vem de autenticação/contexto e catálogo interno; payload de negócio nunca é autoridade final para identidade ou tenant.
- Comunicação interna futura entre microsserviços continua sendo gRPC com metadata confiável; não introduzir REST interno como atalho.
- Eventos, filas, integrações externas, NATS JetStream, dashboards e auditoria completa ficam fora desta story, salvo logs mínimos necessários.

### OAuth/JWT guardrails

- Usar OAuth 2.0 Client Credentials como modelo funcional para clientes técnicos M2M.
- Para access tokens JWT, validar pelo menos: assinatura/algoritmo permitido, `iss`, `aud`, `sub` ou `client_id`, `exp`, `nbf` quando presente, `iat`, `jti`, `scope`, `tenant_id`, `kid` e tipo adequado quando representado.
- Não aceitar algoritmo `none`, token sem assinatura, token com `aud` ambígua, token com tenant ausente em endpoint tenant-scoped ou token que permita confundir `sub` humano com cliente técnico.
- O conteúdo de access token é visível ao cliente; manter claims minimizadas e não inserir CPF, CNPJ, nome, endereço, e-mail completo ou dados financeiros no token.
- Como não há IdP escolhido, o adapter da story deve ser determinístico e substituível por implementação real via porta.

### Multi-tenancy e contexto confiável

- O MVP usa modelo `bridge`; `tenant_isolation_tier` default é `bridge` e `pooled` puro segue proibido para dados transacionais sensíveis.
- A resolução deve confirmar que o tenant existe e recuperar `tenant_isolation_tier` do catálogo interno, mesmo quando a claim trouxer tenant.
- Se o payload trouxer `tenant_id`, tratar apenas como dado de negócio comparável: divergência explícita é spoofing e deve ser rejeitada.
- O contexto autenticado deve ser propagável futuramente por gRPC metadata com `tenant_id`, `tenant_isolation_tier`, sujeito/cliente técnico, scopes relevantes, correlation ID, trace ID e request ID.

### Padrões herdados da Story 1.1

- Reutilizar `OperatorContext`/segurança existente quando fizer sentido, mas não misturar operador humano de plataforma com cliente técnico M2M sem nomear claramente o contexto.
- Reutilizar `GetTenantUseCase` para consulta segura de tenant e preservar a regra de catálogo/contexto confiável.
- Preservar erros com `code`, `safe_message` e `grpc_status`; não voltar a exceções genéricas sem código estável.
- Preservar logging best-effort: falha de logging não deve transformar autenticação válida em falha nem esconder erro real de autenticação.
- Não quebrar testes existentes de Story 1.1: criação/consulta de tenant, `bridge` default, rejeição de `pooled`, validação de identificadores, duplicidade atômica e bloqueio cross-tenant.

### Estrutura esperada de arquivos

- Preferir alterações focadas em:
  - `services/identity-tenant/src/creditos_identity_tenant/application/security.py`
  - `services/identity-tenant/src/creditos_identity_tenant/application/service.py`
  - `services/identity-tenant/src/creditos_identity_tenant/application/ports/...`
  - `services/identity-tenant/src/creditos_identity_tenant/adapters/...`
  - `services/identity-tenant/src/creditos_identity_tenant/domain/errors.py`
  - `services/identity-tenant/tests/unit/...`
  - `services/identity-tenant/tests/integration/...`
- Criar arquivos novos apenas quando houver responsabilidade nova clara; não mover a estrutura do serviço nem alterar `services/service-template`.
- Atualizar `README.md` do serviço se houver novo modo de uso local relevante para autenticação M2M.
- Evitar dependências novas. Se a implementação precisar de biblioteca JWT real, justificar alternativa, impacto no `uv.lock` e razão para não manter adapter determinístico puro nesta story.

### Contratos e compatibilidade

- Já existe `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` com `TenantContextService.ResolveTenantContext`.
- Esta story não precisa alterar o protobuf se a resolução M2M ficar restrita à camada de aplicação/adapters locais.
- Se alterar contrato protobuf, manter backward compatibility ou criar nova versão conforme catálogo; não quebrar `identity-tenant-context-grpc` em `packages/contracts/catalog/contracts.toml`.
- A API pública final de autenticação/edge ainda não está definida; não criar contrato público definitivo sem decisão explícita.

### Observabilidade, privacidade e segurança de logs

- Usar `ObservabilityContext` para correlation/request/trace IDs e para `tenant_id`/tier após validação.
- Usar `build_structured_log` e `mask_sensitive_data` para todo payload/extra potencialmente sensível.
- Nunca logar access token, refresh token, `Authorization`, client secret, chave privada, JWK privada, payload bruto, documento completo, e-mail completo ou dados financeiros completos.
- `client_id` e `tenant_id` podem aparecer em logs quando necessários para rastreabilidade, mas devem seguir política de mascaramento se forem considerados identificáveis por contrato/risco.

### Testes obrigatórios

- Unitários de porta/modelo de contexto autenticado e erros.
- Unitários do adapter determinístico para token válido e falhas de issuer, audience, expiração, claims e assinatura/`kid`.
- Integração de aplicação validando resolução de tenant e tier a partir do token.
- Teste negativo de spoofing: payload com `tenant_id` divergente do tenant autenticado.
- Teste de logs garantindo ausência de token, segredo, header `Authorization` e payload sensível.
- Gates esperados antes de review: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright` e contratos quando aplicável.

### Decisões e limitações registradas

- Provedor concreto de identidade ainda não foi escolhido; esta story deve manter a porta substituível.
- RBAC completo, policies de autorização por scope e claims detalhadas entram na Story 1.3.
- Propagação completa de contexto confiável entre serviços entra na Story 1.4.
- Service identity, mTLS e autorização service-to-service de produção seguem AD-17 e não são implementados aqui.
- FAPI 2.0, `private_key_jwt`, DPoP, mTLS de cliente, token introspection real e rotação real de JWKS ficam para ADR/story futura conforme risco.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 1 e Story 1.2.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/autenticacao-autorizacao-oq7.md` — decisão de OAuth/OIDC, claims e propagação.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-2, AD-3, AD-5, AD-6 e AD-17.
- `_bmad-output/implementation-artifacts/1-1-cadastro-minimo-de-tenants.md` — aprendizados, padrões e review findings já resolvidos.
- `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` — contrato gRPC interno existente.
- `packages/observability/src/creditos_observability/context.py` — contexto de observabilidade.
- `packages/observability/src/creditos_observability/logging.py` — logs estruturados e mascarados.
- `packages/security/src/creditos_security/masking.py` — mascaramento de dados sensíveis.
- RFC 6749 — OAuth 2.0 Authorization Framework: https://www.rfc-editor.org/rfc/rfc6749
- RFC 9700 — OAuth 2.0 Security Best Current Practice: https://www.rfc-editor.org/rfc/rfc9700
- RFC 9068 — JWT Profile for OAuth 2.0 Access Tokens: https://www.rfc-editor.org/info/rfc9068/
- RFC 7519 — JSON Web Token: https://www.rfc-editor.org/rfc/rfc7519
- RFC 7517 — JSON Web Key: https://www.rfc-editor.org/rfc/rfc7517

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_m2m_authentication_context.py -q` — RED inicial falhou com `ModuleNotFoundError` para a porta M2M; GREEN passou com 4 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_local_m2m_token_verifier.py -q` — RED inicial falhou com `ModuleNotFoundError` para adapter local; GREEN passou junto da fatia M2M com 7 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_m2m_tenant_resolution_use_case.py -q` — RED inicial falhou com `ModuleNotFoundError` para o caso de uso; GREEN passou com 3 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_m2m_authentication_errors.py services/identity-tenant/tests/unit/test_m2m_authentication_context.py services/identity-tenant/tests/unit/test_local_m2m_token_verifier.py -q` — taxonomia de erros M2M passou com 14 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/integration/test_tenant_application_service.py -q` — RED falhou por ausência de `m2m_token_verifier` no serviço; GREEN passou com 5 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_m2m_authentication_context.py services/identity-tenant/tests/unit/test_m2m_authentication_errors.py services/identity-tenant/tests/unit/test_local_m2m_token_verifier.py services/identity-tenant/tests/unit/test_m2m_tenant_resolution_use_case.py services/identity-tenant/tests/integration/test_tenant_application_service.py -q` — suíte M2M passou com 23 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest -q` — tentativa no sandbox falhou apenas por `PermissionError` de socket no harness local; rerun fora do sandbox passou com 87 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff check .` — passou após correções de imports/estilo.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff format .` — aplicou formatação em 3 arquivos.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff format --check .` — passou com 96 arquivos formatados.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pyright` — passou com 0 erros.
- `./.venv/bin/python scripts/check_contracts.py` — passou com 4 contratos.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv lock --check` — passou.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_m2m_authentication_context.py services/identity-tenant/tests/unit/test_local_m2m_token_verifier.py services/identity-tenant/tests/unit/test_m2m_tenant_resolution_use_case.py services/identity-tenant/tests/integration/test_tenant_application_service.py -q` — RED dos achados de review confirmou 10 falhas; GREEN final passou com 22 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest -q` — tentativa no sandbox falhou apenas por `PermissionError` de socket no harness local; rerun fora do sandbox passou com 93 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff check . --fix` — corrigiu imports após patches de review.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff format .` — aplicou formatação em 1 arquivo após patches de review.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff check .` — passou.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff format --check .` — passou com 96 arquivos formatados.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pyright` — passou com 0 erros após patches de review.
- `./.venv/bin/python scripts/check_contracts.py` — passou com 4 contratos após patches de review.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv lock --check` — passou após patches de review.

### Completion Notes List

- 2026-08-06 — Branch `agent/story-1-2-autenticacao-m2m-tenant` criada no início da Story 1.2.
- 2026-08-06 — `CTOS-24` movida para WIP no Jira.
- 2026-08-06 — Subtarefas `CTOS-115` a `CTOS-121` criadas no Jira para execução rastreável.
- 2026-08-06 — Implementada porta de verificação M2M com `AuthenticatedClientContext`, `TokenVerificationRequest` e erros seguros de autenticação.
- 2026-08-06 — Implementado adapter local determinístico para simular validação de tokens M2M sem provedor real de identidade.
- 2026-08-06 — Implementado caso de uso de resolução M2M que valida token, rejeita spoofing por payload e resolve tier pelo catálogo.
- 2026-08-06 — Padronizada taxonomia de erros M2M com códigos estáveis, mensagens públicas seguras e `grpc_status`.
- 2026-08-06 — Integrada resolução M2M ao `TenantApplicationService` com logs estruturados, mascarados e best-effort.
- 2026-08-06 — Consolidada cobertura de autenticação M2M, tenant spoofing, tenant inexistente/inativo e ausência de vazamento de token/log.
- 2026-08-06 — Atualizado README do serviço com escopo M2M local e executados gates finais: 87 testes, ruff, format, pyright, contratos e lock.
- 2026-08-06 — Story 1.2 movida para `review` e pronta para `bmad-code-review`.
- 2026-08-07 — Resolvidos 8 achados do `bmad-code-review`: assinatura determinística, claims/scopes/datas rígidas, tenant inexistente sem enumeração, `repr` seguro, bootstrap M2M, relação `subject == client_id`, limpeza de tenant falso em logs de falha e parser Bearer estrito.
- 2026-08-07 — Gates finais pós-review: 93 testes, ruff, format, pyright, contratos e lock verdes.
- 2026-08-07 — Story 1.2 movida para `done` após patches de review.

### Change Log

- 2026-08-06 — Story 1.2 criada com status `in-progress` para início de desenvolvimento.
- 2026-08-06 — Adicionado contrato de aplicação para autenticação M2M e contexto autenticado.
- 2026-08-06 — Adicionado verificador local de token M2M para harness/testes.
- 2026-08-06 — Adicionado caso de uso de resolução de tenant M2M por contexto autenticado.
- 2026-08-06 — Adicionados testes de taxonomia de erros seguros de autenticação M2M.
- 2026-08-06 — Adicionado método de aplicação para resolução M2M com logging seguro.
- 2026-08-06 — Ampliada suíte unitária e de integração para os cenários obrigatórios da Story 1.2.
- 2026-08-06 — Documentado M2M local no README do `identity-tenant` e concluída sincronização BMAD/Jira da Story 1.2.
- 2026-08-07 — Addressed code review findings — 8 patch items resolved.

### File List

- `_bmad-output/implementation-artifacts/1-2-autenticacao-m2m-com-resolucao-de-tenant.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/identity-tenant/README.md`
- `services/identity-tenant/src/creditos_identity_tenant/application/ports/m2m_token_verifier.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/resolve_m2m_tenant_context.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/service.py`
- `services/identity-tenant/src/creditos_identity_tenant/bootstrap/app.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/external/local_m2m_token_verifier.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/errors.py`
- `services/identity-tenant/tests/unit/test_m2m_authentication_context.py`
- `services/identity-tenant/tests/unit/test_m2m_authentication_errors.py`
- `services/identity-tenant/tests/unit/test_local_m2m_token_verifier.py`
- `services/identity-tenant/tests/unit/test_m2m_tenant_resolution_use_case.py`
- `services/identity-tenant/tests/integration/test_tenant_application_service.py`
