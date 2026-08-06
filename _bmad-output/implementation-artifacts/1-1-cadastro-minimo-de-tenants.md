---
baseline_commit: 99570418e2df42e68697133694121ea6474528cf
jira_issue: CTOS-23
branch: agent/story-1-1-cadastro-minimo-tenants
---

# Story 1.1: Cadastro Mínimo de Tenants

Status: done

## Story

As a operador da plataforma,
I want criar e consultar tenants com status e tier de isolamento,
so that todas as operações futuras tenham um contexto confiável de tenant.

## Acceptance Criteria

1. **Criação mínima de tenant**
   - **Given** um operador autorizado
   - **When** ele cria um tenant com nome e status, opcionalmente informando `tenant_isolation_tier`
   - **Then** o tenant é persistido com identificador único
   - **And** o status inicial e o tier informado, com default `bridge`, são registrados.

2. **Consulta segura de tenant existente**
   - **Given** uma consulta por tenant existente
   - **When** o serviço recebe o identificador do tenant
   - **Then** retorna os metadados mínimos do tenant
   - **And** não expõe dados de outro tenant.

3. **Validações e rejeições determinísticas**
   - **Given** uma tentativa de cadastro com nome ausente, status inválido, tier inválido ou identificador duplicado
   - **When** o caso de uso é executado
   - **Then** a operação é rejeitada com erro padronizado, sem gravar estado parcial
   - **And** nenhum dado sensível é registrado em logs.

4. **Rastreabilidade técnica mínima**
   - **Given** operações de criação e consulta de tenant
   - **When** a operação é processada
   - **Then** logs estruturados incluem `correlation_id`, `request_id`, operação, status e duração
   - **And** `tenant_id` e `tenant_isolation_tier` aparecem quando aplicável.

## Tasks / Subtasks

- [x] CTOS-108 — Criar microsserviço `identity-tenant` a partir do template DDD/hexagonal (AC: 1, 2)
  - [x] Criar `services/identity-tenant` como membro do workspace `uv`, sem alterar `services/service-template`.
  - [x] Usar pacote Python `creditos_identity_tenant` com camadas `domain`, `application`, `adapters` e `bootstrap`.
  - [x] Preservar `domain` sem dependências de FastAPI, Pydantic de borda, SQLAlchemy, gRPC, NATS ou OpenTelemetry.

- [x] CTOS-109 — Modelar domínio mínimo de tenant (AC: 1, 2, 3)
  - [x] Implementar entidade/agregado `Tenant` com identificador único, nome, status, `tenant_isolation_tier` e timestamps/audit metadata mínimos.
  - [x] Implementar value objects/enums para status e tier, com default obrigatório `bridge`.
  - [x] Bloquear `pooled` puro para dados transacionais sensíveis; aceitar apenas tiers aprovados para o MVP.

- [x] CTOS-110 — Implementar casos de uso de criação e consulta (AC: 1, 2, 3)
  - [x] Criar portas de aplicação para persistência de tenant, sem expor banco como contrato.
  - [x] Implementar repositório inicial adequado ao harness local, com comportamento determinístico para duplicidade e inexistência.
  - [x] Garantir que consulta por tenant não aceite fonte não confiável de `tenant_id` como autoridade de segurança.

- [x] CTOS-111 — Expor adapters mínimos para execução e testes (AC: 1, 2, 4)
  - [x] Preferir adapter interno simples/testável nesta story; não implementar autenticação M2M completa, RBAC completo ou console humano.
  - [x] Se houver API pública local, exigir placeholder explícito de operador autorizado e documentar que autenticação real entra na Story 1.2.
  - [x] Avaliar se o contrato gRPC `ResolveTenantContext` existente precisa ser implementado ou apenas preparado sem quebra de contrato.

- [x] CTOS-112 — Aplicar logs, mascaramento e contexto de observabilidade (AC: 3, 4)
  - [x] Reutilizar `creditos_observability.ObservabilityContext` e `build_structured_log`; não criar formato novo de log.
  - [x] Reutilizar `creditos_security.mask_sensitive_data` para qualquer campo livre ou extra de log.
  - [x] Não logar payload bruto, secrets, tokens, documentos, e-mail completo, CPF/CNPJ completo ou identificadores sensíveis diretos.

- [x] CTOS-113 — Criar testes unitários, integração local e gates mínimos (AC: 1, 2, 3, 4)
  - [x] Testar criação com tier default `bridge` e tier informado válido.
  - [x] Testar rejeição de status/tier inválidos e duplicidade.
  - [x] Testar consulta existente, tenant inexistente e ausência de vazamento cross-tenant.
  - [x] Testar que logs não expõem payload bruto nem dados sensíveis completos.
  - [x] Rodar `uv run pytest`, `uv run ruff check .` e `uv run pyright` antes de review.

- [x] CTOS-114 — Sincronizar rastreamento BMAD/Jira (AC: 1, 2, 3, 4)
  - [x] Manter `CTOS-23` em WIP durante desenvolvimento e mover para Review QA antes de `bmad-code-review`.
  - [x] Atualizar subtarefas no Jira conforme forem concluídas.
  - [x] Atualizar esta story com arquivos alterados, notas de conclusão e resultado dos testes.

### Review Findings

- [x] [Review][Patch] Aplicar logging operacional best-effort com fallback — Decisão do usuário: opção 1, logging não deve quebrar operação já persistida nesta story. Ajustar `TenantApplicationService` para isolar falhas do logger e preservar o resultado do caso de uso. Evidência: `services/identity-tenant/src/creditos_identity_tenant/application/service.py:56` e `services/identity-tenant/src/creditos_identity_tenant/application/service.py:142`.

- [x] [Review][Patch] Autorização permissiva por padrão viola `deny-by-default` [services/identity-tenant/src/creditos_identity_tenant/application/security.py:11]
- [x] [Review][Patch] Consulta pode usar `tenant_id` sem contexto confiável ou permissão explícita de catálogo [services/identity-tenant/src/creditos_identity_tenant/application/use_cases/get_tenant.py:17]
- [x] [Review][Patch] Normalizadores aceitam `None` e tipos arbitrários como strings válidas [services/identity-tenant/src/creditos_identity_tenant/domain/entities/tenant.py:66]
- [x] [Review][Patch] Verificação de duplicidade usa padrão check-then-write não atômico [services/identity-tenant/src/creditos_identity_tenant/application/use_cases/create_tenant.py:41]
- [x] [Review][Patch] Erros de domínio não possuem código estável ou mensagem segura padronizada [services/identity-tenant/src/creditos_identity_tenant/domain/errors.py:4]

## Dev Notes

### Escopo desta story

- Implementar apenas o cadastro e a consulta mínima de tenants no serviço `Identity & Tenant`.
- Não implementar ainda autenticação OAuth/OIDC real, Client Credentials, RBAC/scopes completos, mTLS, console humano, migração bridge→silo, IaC de recursos dedicados ou dashboards customer-facing.
- O operador autorizado pode ser representado por contexto explícito/controlado para teste local; a fonte real de autorização será tratada nas Stories 1.2 e 1.3.
- Esta story deve deixar um caminho claro para a Story 1.2 resolver tenant pelo contexto autenticado sem confiar no body.

### Guardrails de domínio e arquitetura

- `Identity & Tenant` é a fonte de verdade para tenant, cliente técnico, usuário, role, scope e tier de isolamento.
- O primeiro deploy possui sete microsserviços de domínio; esta story cria apenas `Identity & Tenant` e não deve criar serviço técnico genérico.
- Todo backend segue DDD + arquitetura hexagonal: regras e invariantes em `domain`, orquestração em `application`, infraestrutura em `adapters`/`bootstrap`.
- Cada microsserviço possui dados próprios; joins, queries e transações cross-service são proibidos.
- Comunicação cross-service futura deve usar gRPC, eventos NATS JetStream ou projeções autorizadas; não introduzir REST interno como atalho.

### Multi-tenancy e isolamento

- O MVP usa modelo `bridge`: infraestrutura compartilhada com isolamento forte por tenant.
- `tenant_isolation_tier` default é `bridge`; `pooled` puro é proibido para dados transacionais sensíveis de crédito/risco.
- O catálogo de tenants deve armazenar tier, status e metadados necessários para roteamento futuro, sem implementar ainda criação automática de recursos dedicados.
- `tenant_id` confiável deve vir futuramente de autenticação/contexto e catálogo do `Identity & Tenant`; payload de negócio nunca é fonte final de identidade/tenant sem validação.

### Segurança, privacidade e logs

- Segurança é `deny-by-default`; qualquer exceção local para bootstrap/testes deve estar explícita e limitada.
- Logs operacionais devem ser estruturados, rastreáveis e mascarados.
- Usar `ObservabilityContext` para `correlation_id`, `request_id`, `trace_id`, `tenant_id` e `tenant_isolation_tier` quando aplicável.
- Usar `build_structured_log` para manter campos obrigatórios e mascaramento via `mask_sensitive_data`.
- Nunca registrar payload bruto, token, segredo, CPF/CNPJ completo, e-mail completo, documento, imagem/biometria ou dado financeiro completo.

### Contratos e compatibilidade

- Já existe contrato protobuf `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` com `TenantContextService.ResolveTenantContext`.
- Se esta story alterar contrato, a mudança deve ser backward-compatible ou exigir novo major version conforme catálogo de contratos.
- Não remover nem quebrar o contrato `identity-tenant-context-grpc` registrado em `packages/contracts/catalog/contracts.toml`.
- Se a implementação gRPC ficar fora desta story, registrar claramente a limitação e manter testes de domínio/aplicação cobrindo o comportamento esperado.

### Estrutura esperada de arquivos

- Criar o serviço real em `services/identity-tenant`, não dentro de `services/service-template`.
- Nome do pacote: `creditos_identity_tenant`.
- Seguir estrutura base:
  - `services/identity-tenant/src/creditos_identity_tenant/domain/...`
  - `services/identity-tenant/src/creditos_identity_tenant/application/...`
  - `services/identity-tenant/src/creditos_identity_tenant/adapters/...`
  - `services/identity-tenant/src/creditos_identity_tenant/bootstrap/...`
  - `services/identity-tenant/tests/unit`, `tests/integration`, `tests/contract` quando aplicável.
- Atualizar `pyproject.toml` raiz apenas se necessário para `extraPaths`, `pythonpath` ou dependências workspace; evitar dependências novas sem justificativa.

### Padrões herdados do Epic 0

- Story 0.2 criou o template de microsserviço DDD/hexagonal e definiu a regra de dependência do domínio.
- Story 0.3 criou estrutura de contratos versionados com OpenAPI, protobuf, AsyncAPI e JSON Schema.
- Story 0.5 criou fundação de observabilidade/logs/segurança reutilizável.
- Story 0.7 criou trilha inicial de supply chain, container runtime e IaC placeholder; não transformar esta story em trabalho de container/IaC além do mínimo necessário.

### Testes obrigatórios

- Unitários de domínio para invariantes de `Tenant`, status, tier default e tier inválido.
- Unitários/aplicação para criação, consulta, duplicidade e inexistência.
- Teste negativo de isolamento: consulta não deve retornar metadados de outro tenant quando o identificador/contexto não corresponder.
- Teste de log/mascaramento garantindo que payload bruto e dados sensíveis completos não aparecem.
- Gates esperados antes de review: `uv run pytest`, `uv run ruff check .`, `uv run pyright`.

### Decisões e limitações registradas

- Autenticação e autorização reais serão implementadas nas Stories 1.2 e 1.3; esta story não deve fingir segurança completa.
- Persistência inicial pode ser mínima para o harness local, desde que a porta de persistência permita troca futura por PostgreSQL próprio do serviço.
- Métricas técnicas completas e dashboards ficam para Epic 7, mas esta story deve produzir logs/contexto compatíveis com a fundação de observabilidade.
- Recurso dedicado por tenant e migração `bridge → silo` ficam fora do escopo; o catálogo deve apenas carregar informações necessárias para essa evolução.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 1 e Story 1.1.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — glossário, OQ-4, OQ-5, OQ-6, OQ-7, OQ-9, OQ-10 e riscos.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-5, AD-6 e AD-20.
- `services/service-template/README.md` — estrutura DDD/hexagonal e regra de dependência.
- `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` — contrato gRPC existente de contexto de tenant.
- `packages/contracts/catalog/contracts.toml` — catálogo de contratos versionados.
- `packages/observability/src/creditos_observability/context.py` — contexto de correlação/tenant.
- `packages/observability/src/creditos_observability/logging.py` — logs estruturados e mascarados.
- `packages/security/src/creditos_security/masking.py` — mascaramento de dados sensíveis.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- `uv run pytest services/identity-tenant/tests -q` — tentativa inicial falhou porque `uv` não estava no PATH padrão.
- `python3 -m pytest services/identity-tenant/tests -q` — tentativa inicial falhou porque o Python global não possui `pytest`.
- `./.venv/bin/python -m pytest services/identity-tenant/tests -q` — RED inicial confirmado com `ModuleNotFoundError` antes da implementação.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache uv run pytest services/identity-tenant/tests tests/test_microservice_template.py tests/test_repository_bootstrap.py -q` — 17 testes passaram.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache uv run ruff check .` — passou.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache uv run ruff format --check .` — passou.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache uv run pyright` — passou com 0 erros.
- `./.venv/bin/python scripts/check_contracts.py` — passou com 4 contratos.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache uv lock --check` — passou.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache uv run pytest -q` fora do sandbox — 62 testes passaram.
- `PATH=/tmp/creditos-tools/local/bin:$PATH UV_CACHE_DIR=/tmp/creditos-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/creditos-uv-python uv run pytest -q` fora do sandbox — 67 testes passaram após patches de review.

### Completion Notes List

- 2026-08-04 — Epic 1 iniciado, branch criada e Story 1.1 preparada com status `in-progress`.
- 2026-08-04 — Implementado microsserviço `identity-tenant` com estrutura DDD/hexagonal, domínio mínimo de tenant, casos de uso de criação/consulta, repositório em memória e logging estruturado mascarado.
- 2026-08-04 — Adicionados testes unitários e de integração cobrindo tier default `bridge`, tier `silo`, rejeição de `pooled`, validações, duplicidade, consulta, bloqueio cross-tenant e logs sem payload sensível.
- 2026-08-04 — `uv.lock` atualizado para incluir o novo workspace member e validado com `uv lock --check` usando cache isolado em `/tmp`.
- 2026-08-06 — Resolvidos 6 achados do `bmad-code-review`: logging best-effort, `deny-by-default`, contexto confiável de tenant, validação forte de entradas, save atômico e erros padronizados.
- 2026-08-06 — Gates finais pós-review: `uv run pytest -q` com 67 testes passando, `ruff`, `format`, `pyright`, `uv lock --check` e contratos verdes.

### Change Log

- 2026-08-04 — Criado serviço `identity-tenant` e atualizado workspace Python para a Story 1.1.
- 2026-08-04 — Story movida para `review`; sprint status sincronizado para revisão.
- 2026-08-06 — Review findings corrigidos e Story 1.1 movida para `done`.

### File List

- `_bmad-output/implementation-artifacts/1-1-cadastro-minimo-de-tenants.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `pyproject.toml`
- `uv.lock`
- `services/identity-tenant/README.md`
- `services/identity-tenant/pyproject.toml`
- `services/identity-tenant/src/creditos_identity_tenant/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/api/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/events/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/external/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/grpc/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/logging/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/logging/in_memory_operation_logger.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/persistence/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/persistence/in_memory_tenant_repository.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/ports/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/ports/operation_logger.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/ports/tenant_repository.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/security.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/service.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/create_tenant.py`
- `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/get_tenant.py`
- `services/identity-tenant/src/creditos_identity_tenant/bootstrap/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/bootstrap/app.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/entities/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/entities/tenant.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/errors.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/events/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/policies/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/services/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/value_objects/__init__.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/value_objects/tenant_isolation_tier.py`
- `services/identity-tenant/src/creditos_identity_tenant/domain/value_objects/tenant_status.py`
- `services/identity-tenant/tests/contract/.gitkeep`
- `services/identity-tenant/tests/integration/test_tenant_application_service.py`
- `services/identity-tenant/tests/unit/test_tenant_domain.py`
- `services/identity-tenant/tests/unit/test_tenant_use_cases.py`
