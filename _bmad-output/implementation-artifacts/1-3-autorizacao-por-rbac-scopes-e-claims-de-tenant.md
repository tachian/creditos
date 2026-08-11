---
baseline_commit: 3da4d6a865cebd9589a8f19457a9c6a5eb7898a1
jira_issue: CTOS-25
branch: agent/story-1-3-rbac-scopes-claims-tenant
---

# Story 1.3: Autorização por RBAC, Scopes e Claims de Tenant

Status: done

## Story

As a serviço de domínio,
I want validar permissões antes de executar operações sensíveis,
so that usuários ou clientes técnicos não acessem recursos indevidos.

## Acceptance Criteria

1. **Scope obrigatório bloqueia operação sensível**
   - **Given** um sujeito autenticado sem scope necessário
   - **When** ele tenta executar operação sensível
   - **Then** a operação é rejeitada com erro padronizado
   - **And** o evento é registrado para rastreabilidade.

2. **Isolamento cross-tenant é obrigatório**
   - **Given** um sujeito de um tenant
   - **When** ele tenta acessar recurso de outro tenant
   - **Then** a operação é bloqueada
   - **And** o teste negativo cross-tenant passa.

3. **Deny-by-default para contexto incompleto**
   - **Given** um contexto autenticado sem tenant, sujeito, roles/scopes válidos ou operação declarada na registry
   - **When** a autorização é avaliada
   - **Then** a operação é rejeitada com erro seguro
   - **And** nenhum acesso implícito é concedido por ausência de regra.

4. **Logs de autorização são rastreáveis e minimizados**
   - **Given** uma tentativa de autorização aceita ou rejeitada
   - **When** o serviço registra o evento
   - **Then** logs estruturados incluem operação, status, duração, correlation ID, request ID, trace ID, tenant confiável quando aplicável, sujeito e decisão segura
   - **And** não expõem token, header `Authorization`, payload bruto, CPF/CNPJ, e-mail completo, segredo ou detalhes internos de policy.

## Tasks / Subtasks

- [x] CTOS-122 — Modelar contexto de autorização e taxonomia de permissões (AC: 1, 2, 3)
  - [x] Criar modelos de aplicação para sujeito autenticado autorizável, recurso protegido, requisitos de operação e resultado autorizado.
  - [x] Normalizar `roles` e `scopes` com validação estrita, rejeitando valores vazios, tipos inválidos, mapping/bytes e itens com whitespace.
  - [x] Definir erros seguros de autorização com `code`, `safe_message` e `grpc_status`, preservando o padrão de `TenantDomainError`.

- [x] CTOS-123 — Implementar policy de autorização RBAC/scopes/tenant (AC: 1, 2, 3)
  - [x] Implementar avaliação `deny-by-default`: sem operação declarada na registry, sem contexto válido, sem scope exigido ou sem role exigida deve rejeitar.
  - [x] Validar scopes obrigatórios por operação e roles obrigatórias por padrão, permitindo `scope-only` apenas quando a registry declarar explicitamente.
  - [x] Validar claim/contexto de tenant contra o tenant do recurso protegido e bloquear divergência cross-tenant.

- [x] CTOS-124 — Criar caso de uso de autorização para operações sensíveis (AC: 1, 2, 3)
  - [x] Criar use case em `application/use_cases` que receba contexto autenticado, operação e recurso protegido, resolvendo requisitos pela registry.
  - [x] Retornar metadados minimizados de autorização em caso de sucesso, sem expor token nem payload bruto.
  - [x] Garantir que o use case seja reutilizável por futuras bordas HTTP, gRPC e eventos, sem depender de framework.

- [x] CTOS-125 — Integrar autorização ao `TenantApplicationService` com logs seguros (AC: 1, 2, 4)
  - [x] Expor método de aplicação para autorizar operação sensível e registrar evento aceito/rejeitado.
  - [x] Em rejeições, registrar tenant somente quando vier do contexto autenticado normalizado; nunca confiar em tenant de payload/recurso externo para log de falha.
  - [x] Manter logging best-effort, mascarado e sem `Authorization`, access token, segredo ou payload sensível.

- [x] CTOS-126 — Criar testes de autorização, escopos e isolamento cross-tenant (AC: 1, 2, 3, 4)
  - [x] Testar autorização aceita com scope obrigatório, role exigida e tenant compatível.
  - [x] Testar falta de scope, falta de role, contexto malformado, requisitos vazios e recurso cross-tenant.
  - [x] Testar erros padronizados e logs de autorização sem vazamento sensível.
  - [x] Executar regressão do `identity-tenant` e suíte completa antes de review.

- [x] CTOS-127 — Sincronizar BMAD/Jira e registrar evidências da Story 1.3 (AC: 1, 2, 3, 4)
  - [x] Manter `CTOS-25` em WIP durante desenvolvimento e mover subtarefas conforme conclusão.
  - [x] Atualizar esta story com arquivos alterados, notas de conclusão e resultado dos gates.
  - [x] Atualizar `sprint-status.yaml` para `review` somente após todos os gates passarem.

### Review Findings

- [x] [Review][Patch] Definir ponto obrigatório de enforcement da autorização — resolvido com `AuthorizedOperationFacade`, que concentra a entrada obrigatória para bordas futuras HTTP/gRPC/eventos.
- [x] [Review][Patch] Definir se toda operação sensível exige role além de scope — resolvido com `AuthorizationOperationRegistry`; `scope-only` exige `allow_scope_only=True` explícito.
- [x] [Review][Patch] Requisito auto-declarado enfraquece a policy [services/identity-tenant/src/creditos_identity_tenant/application/security.py:155] — resolvido bloqueando instanciação direta de `AuthorizationRequirement` fora da registry.
- [x] [Review][Patch] Derivação autorizável aceita contexto M2M ainda não resolvido pelo catálogo e roles externas [services/identity-tenant/src/creditos_identity_tenant/application/security.py:97] — resolvido com factory `from_resolved_tenant_context` e validações explícitas de principal/tier.
- [x] [Review][Patch] Logging de rejeição pode mascarar erro seguro com comando malformado [services/identity-tenant/src/creditos_identity_tenant/application/service.py:166] — resolvido validando comando pela fachada antes de acessar campos inseguros.
- [x] [Review][Patch] Roles/scopes aceitam string agregada como container em autorização local [services/identity-tenant/src/creditos_identity_tenant/application/security.py:319] — resolvido rejeitando `str`, mappings, bytes e containers inválidos.
- [x] [Review][Patch] Identificadores de autorização não têm formato, enum ou limite de tamanho [services/identity-tenant/src/creditos_identity_tenant/application/security.py:267] — resolvido com regex e limite de 128 caracteres para identificadores/tokens.
- [x] [Review][Patch] `to_log_metadata` pode retornar `token_id` bruto fora do logger mascarado [services/identity-tenant/src/creditos_identity_tenant/application/security.py:115] — resolvido removendo `token_id` dos metadados públicos.
- [x] [Review][Patch] Fonte de log de autorização continua como `operator-context` [services/identity-tenant/src/creditos_identity_tenant/application/service.py:231] — resolvido usando `source=authorization-context`.
- [x] [Review][Patch] Negação cross-tenant lançada pela policy não pertence à hierarquia de `AuthorizationError` [services/identity-tenant/src/creditos_identity_tenant/application/security.py:218] — resolvido tornando `CrossTenantAccessDeniedError` subtipo de `AuthorizationError`.

## Dev Notes

### Escopo desta story

- Implementar autorização local/testável no `Identity & Tenant Service` para operações sensíveis usando RBAC, scopes e claims/contexto de tenant.
- Não implementar provedor real de identidade, console humano, ABAC completo, FAPI 2.0, mTLS/service mesh de produção, PDP externo, OPA, Cedar, Casbin ou engine externa de policy nesta story.
- A autorização deve ser uma capacidade de aplicação/domínio local, substituível e reutilizável por bordas futuras HTTP, gRPC e eventos.
- Esta story prepara a Story 1.4 para propagar contexto confiável entre serviços, mas não implementa ainda metadata gRPC nem contratos novos.

### Regras de arquitetura obrigatórias

- Backend segue DDD + arquitetura hexagonal: regras puras em `domain`/`application`, dependências externas em `adapters` e composição em `bootstrap`.
- `Identity & Tenant` é fonte de verdade para tenants, clientes técnicos, usuários, roles, permissões, scopes, claims e contexto confiável.
- Segurança é `deny-by-default`; ausência de operação na registry, ausência de contexto válido ou entrada malformada deve rejeitar.
- Toda operação sensível valida sujeito, tenant, papel, permissão/scope, recurso e contexto.
- `tenant_id` confiável vem de autenticação/contexto e catálogo; payload de negócio nunca é autoridade final.
- Não introduzir REST interno; comunicação cross-service futura continua por gRPC, eventos NATS JetStream ou projeções autorizadas.

### Modelo de autorização esperado

- `AuthenticatedClientContext` da Story 1.2 já carrega `client_id`, `subject`, `scopes`, `tenant_id`, `tenant_isolation_tier`, `issuer`, `audience` e `token_id`.
- A Story 1.3 deve criar uma representação autorizável derivável desse contexto, acrescentando `roles` quando fornecidas por claims ou resolução futura.
- Scopes representam capacidades de API, por exemplo `proposal:submit`, `decision:read`, `policy:write`, `tenant:admin`, `audit:read` e `report:read`.
- Roles representam papéis de RBAC, por exemplo `platform-admin`, `tenant-admin`, `service-client` ou papéis equivalentes; não criar catálogo persistido completo de roles nesta story.
- Requisitos de autorização devem vir de uma registry/factory por operação: operação, scopes exigidos, roles exigidas por padrão, exceção `scope-only` explícita e tenant do recurso protegido.
- Callers e bordas futuras não devem autodeclarar requisitos de autorização arbitrários; devem chamar a fachada autorizável.
- O tenant do recurso protegido deve ser comparado ao tenant autenticado; divergência deve gerar erro seguro de acesso cross-tenant.

### Padrões herdados das Stories 1.1 e 1.2

- Reutilizar o padrão de erros com `code`, `safe_message` e `grpc_status`.
- Reutilizar `ObservabilityContext`, `build_structured_log` e logging best-effort.
- Não quebrar a resolução M2M existente nem os testes de token, tenant spoofing e logs sem token bruto.
- Não confundir operador humano de plataforma (`OperatorContext`) com cliente técnico M2M; se reutilizar conceitos, nomear claramente o contexto de autorização.
- Falha de logging não deve alterar o resultado da autorização.
- Em falhas de autenticação/autorização, logs não devem associar tenant falso vindo de payload não confiável.

### Estrutura esperada de arquivos

- Alterações prováveis:
  - `services/identity-tenant/src/creditos_identity_tenant/application/security.py`
  - `services/identity-tenant/src/creditos_identity_tenant/application/service.py`
  - `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/authorize_operation.py`
  - `services/identity-tenant/src/creditos_identity_tenant/domain/errors.py`
  - `services/identity-tenant/tests/unit/test_authorization_context.py`
  - `services/identity-tenant/tests/unit/test_authorize_operation_use_case.py`
  - `services/identity-tenant/tests/integration/test_tenant_application_service.py`
  - `services/identity-tenant/README.md`
- Criar arquivos novos apenas para responsabilidade nova clara.
- Evitar dependências novas; uma engine externa de policy exige ADR e fica fora desta story.

### Observabilidade, privacidade e segurança de logs

- Logs devem conter `correlation_id`, `request_id`, `trace_id`, serviço, versão, ambiente, operação, status, duração e `tenant_id` somente quando confiável.
- Logs de autorização podem incluir sujeito, roles/scopes exigidos e decisão de forma minimizada, mas não devem expor payload bruto, token, header `Authorization`, segredo, CPF/CNPJ, e-mail completo ou detalhes internos de policy.
- Rejeições por falta de permissão devem registrar motivo seguro, como `missing_required_scope`, `missing_required_role`, `cross_tenant_access_denied` ou `invalid_authorization_context`.

### Testes obrigatórios

- Unitários para normalização de contexto autorizável, roles e scopes.
- Unitários para policy/use case: sucesso, falta de scope, falta de role, operação desconhecida, registry inválida, contexto inválido e cross-tenant.
- Integração no `TenantApplicationService`: autorização aceita/rejeitada com logs estruturados e mascarados.
- Regressão completa: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `scripts/check_contracts.py` e `uv lock --check`.

### Decisões e limitações registradas

- Catálogo persistente completo de roles/permissions/scopes fica fora desta story; a modelagem inicial é local e testável.
- A registry de autorização inicial é em código e deve evoluir para catálogo/contrato governado em story futura se o volume de operações justificar.
- ABAC, FAPI 2.0, `private_key_jwt`, DPoP, mTLS de cliente, OPA/Cedar/Casbin e PDP externo ficam para ADR/story futura se o risco justificar.
- Propagação completa de contexto por gRPC metadata e eventos entra na Story 1.4.
- Gates consolidados de autenticação/autorização/isolamento do Epic 1 entram na Story 1.5.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 1 e Story 1.3.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/autenticacao-autorizacao-oq7.md` — decisão de OAuth/OIDC, RBAC, scopes e claims.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — ownership de `Identity & Tenant`, DDD/hexagonal e segurança.
- `_bmad-output/implementation-artifacts/1-1-cadastro-minimo-de-tenants.md` — padrões de tenant, deny-by-default e logs.
- `_bmad-output/implementation-artifacts/1-2-autenticacao-m2m-com-resolucao-de-tenant.md` — contexto M2M, erros seguros e logs sem token.
- `services/identity-tenant/src/creditos_identity_tenant/application/ports/m2m_token_verifier.py` — `AuthenticatedClientContext` e normalização de scopes.
- `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/resolve_m2m_tenant_context.py` — resolução M2M e contexto confiável.
- `packages/observability/src/creditos_observability/context.py` — contexto de observabilidade.
- `packages/observability/src/creditos_observability/logging.py` — logs estruturados e mascarados.
- `packages/security/src/creditos_security/masking.py` — mascaramento de dados sensíveis.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-11 — `bmad-dev-story` iniciou, mas o arquivo detalhado da Story 1.3 ainda não existia; criado artefato de story como pré-requisito direto.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_authorization_context.py -q` — RED inicial falhou com `ImportError` para modelos de autorização; GREEN passou com 5 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_authorization_context.py -q` — RED da policy falhou com `ImportError` para `AuthorizationPolicy`; GREEN passou com 9 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_authorize_operation_use_case.py -q` — RED inicial falhou com `ModuleNotFoundError` para `authorize_operation`; GREEN passou com a suíte nova.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_authorization_context.py services/identity-tenant/tests/unit/test_authorize_operation_use_case.py -q` — passou com 11 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/integration/test_tenant_application_service.py -q` — RED falhou pela ausência de `TenantApplicationService.authorize_operation`; GREEN passou com 10 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest services/identity-tenant/tests/unit/test_authorization_context.py services/identity-tenant/tests/unit/test_authorize_operation_use_case.py services/identity-tenant/tests/unit/test_m2m_authentication_errors.py services/identity-tenant/tests/integration/test_tenant_application_service.py -q` — passou com 33 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest -q` — tentativa no sandbox falhou apenas por `PermissionError` de socket no harness local; rerun fora do sandbox passou com 111 testes.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff check .` — passou.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run ruff format --check .` — passou com 99 arquivos formatados.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pyright` — passou com 0 erros.
- `./.venv/bin/python scripts/check_contracts.py` — passou com 4 contratos.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv lock --check` — passou.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest -q` — rerun final fora do sandbox passou com 111 testes.
- `.venv/bin/python -m pytest services/identity-tenant/tests/unit/test_authorization_context.py services/identity-tenant/tests/unit/test_authorize_operation_use_case.py services/identity-tenant/tests/unit/test_m2m_authentication_errors.py services/identity-tenant/tests/integration/test_tenant_application_service.py -q` — revisão adversarial GREEN passou com 39 testes.
- `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pyright` — revisão adversarial passou com lint, formatação e typecheck verdes.
- `.venv/bin/python -m pytest -q && .venv/bin/python scripts/check_contracts.py` — tentativa no sandbox falhou apenas por `PermissionError` de socket no harness local e ausência de `uv` no PATH do script `scripts/dev`.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest -q && ./.venv/bin/python scripts/check_contracts.py && PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv lock --check` — rerun final fora do sandbox passou com 117 testes, 4 contratos e lock válido.

### Completion Notes List

- 2026-08-11 — Branch `agent/story-1-3-rbac-scopes-claims-tenant` criada no início da Story 1.3.
- 2026-08-11 — `CTOS-25` movida para WIP no Jira.
- 2026-08-11 — Subtarefas `CTOS-122` a `CTOS-127` criadas no Jira para execução rastreável.
- 2026-08-11 — Modelados `AuthorizationSubject`, `ProtectedResource`, `AuthorizationRequirement`, `AuthorizationDecision` e erros seguros de autorização.
- 2026-08-11 — Implementada `AuthorizationPolicy` com bloqueio por falta de scope, falta de role e divergência cross-tenant.
- 2026-08-11 — Criado `AuthorizeOperationUseCase` com comando de aplicação reutilizável e retorno minimizado.
- 2026-08-11 — Integrada autorização ao `TenantApplicationService` com logs aceitos/rejeitados, tenant confiável e decisão minimizada em `authz_decision`.
- 2026-08-11 — Consolidada cobertura unitária e de integração para autorização aceita, falta de scope, falta de role, contexto inválido, requisitos vazios, cross-tenant, erros seguros e logs sem token/payload sensível.
- 2026-08-11 — Atualizado README do `identity-tenant` com autorização local, limitações e logs minimizados.
- 2026-08-11 — Gates finais verdes: 111 testes, ruff, format, pyright, contratos e lock.
- 2026-08-11 — Story 1.3 movida para `review` e pronta para `bmad-code-review`.
- 2026-08-11 — Patches da revisão adversarial aplicados: registry obrigatória, fachada autorizável, `scope-only` explícito, validações estritas, logs com `authorization-context`, remoção de `token_id` dos metadados e hierarquia correta de erros.
- 2026-08-11 — Gates finais pós-review verdes: 117 testes, ruff, format, pyright, contratos e lock.
- 2026-08-11 — Story 1.3 movida para `done` após correções da revisão.

### Change Log

- 2026-08-11 — Story 1.3 criada com status `in-progress` para início de desenvolvimento.
- 2026-08-11 — Adicionados modelos e normalizadores de contexto de autorização.
- 2026-08-11 — Adicionada policy local de autorização RBAC/scopes/tenant.
- 2026-08-11 — Adicionado caso de uso de autorização de operação sensível.
- 2026-08-11 — Integrado método de autorização ao serviço de aplicação com logs seguros.
- 2026-08-11 — Ampliada suíte de testes para RBAC/scopes/claims de tenant e regressão completa verde.
- 2026-08-11 — Documentada autorização local no README do serviço e concluída sincronização BMAD/Jira da Story 1.3.
- 2026-08-11 — Aplicadas correções do `bmad-code-review` com registry/fachada de autorização e endurecimento de logs/validação.

### File List

- `_bmad-output/implementation-artifacts/1-3-autorizacao-por-rbac-scopes-e-claims-de-tenant.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/identity-tenant/README.md`
- `services/identity-tenant/src/creditos_identity_tenant/application/security.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/authorize_operation.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/service.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/errors.py`
- `services/identity-tenant/tests/unit/test_authorize_operation_use_case.py`
- `services/identity-tenant/tests/unit/test_authorization_context.py`
- `services/identity-tenant/tests/unit/test_m2m_authentication_errors.py`
