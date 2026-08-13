---
baseline_commit: 7df1a8c
jira_issue: CTOS-27
branch: agent/story-1-5-gates-seguranca-isolamento-epic-1
---

# Story 1.5: Gates de Segurança e Isolamento do Epic 1

Status: done

## Story

As a equipe de engenharia,
I want testes e gates de autenticação, autorização e isolamento,
so that o acesso seguro seja validado antes de avançar para propostas reais.

## Acceptance Criteria

1. **Gate consolidado cobre autenticação M2M negativa**
   - **Given** a suíte de segurança do Epic 1
   - **When** os testes são executados
   - **Then** cobre token ausente, token inválido, token expirado, issuer inválido, audience inválida, algoritmo/chave inválidos e claims obrigatórias ausentes
   - **And** erros retornam códigos/safe messages padronizados, sem detalhes internos.

2. **Gate consolidado cobre autorização e isolamento**
   - **Given** um sujeito autenticado sem permissões suficientes
   - **When** ele tenta executar operação sensível
   - **Then** permissão insuficiente, scope ausente, role ausente e operação desconhecida são rejeitados
   - **And** tentativa de acesso cross-tenant é bloqueada antes de qualquer execução de caso de uso.

3. **Gate consolidado cobre contexto confiável entre serviços**
   - **Given** metadata gRPC ou atributos CloudEvents recebidos por um serviço
   - **When** o contexto está ausente, malformado, duplicado, com chave sensível, com tenant incompatível ou com `traceparent` inválido
   - **Then** o contexto é rejeitado com erro seguro
   - **And** nenhum sujeito autorizável é reconstruído a partir de contexto não validado.

4. **Logs de autenticação/autorização são rastreáveis e mascarados**
   - **Given** logs gerados durante autenticação, autorização e validação de contexto confiável
   - **When** os testes de segurança verificam os registros
   - **Then** encontram `correlation_id`, `request_id`, `trace_id` e tenant apenas quando o tenant é confiável
   - **And** não encontram bearer token, `Authorization`, `token_id`, secrets, CPF, CNPJ, e-mail completo, payload bruto ou dados financeiros detalhados.

5. **Falhas críticas impedem merge**
   - **Given** o pipeline de CI e o comando local equivalente
   - **When** há regressão nos gates de segurança, isolamento, contratos, harness, lint, formatação, tipagem, lockfile ou secret scan
   - **Then** o PR fica bloqueado por falha de check
   - **And** o desenvolvedor consegue reproduzir localmente o conjunto obrigatório com `./scripts/dev all` ou comando equivalente documentado.

## Tasks / Subtasks

- [x] CTOS-135 — Mapear matriz de gates do Epic 1 (AC: 1, 2, 3, 4, 5)
  - [x] Consolidar matriz que relacione ACs, riscos, arquivos de teste, comandos e evidências esperadas.
  - [x] Registrar explicitamente o que já é coberto por testes existentes e o que deve virar teste consolidado.
  - [x] Preferir documentação operacional simples; não criar ferramenta nova se uma matriz em README/doc bastar.

- [x] CTOS-136 — Cobrir autenticação M2M negativa no gate (AC: 1, 4)
  - [x] Reutilizar `LocalM2MTokenVerifier`, `ResolveM2MTenantContextUseCase`, `AuthenticatedClientContext` e erros de domínio existentes.
  - [x] Cobrir token ausente, desconhecido, expirado, ainda não válido, issuer/audience inválidos, algoritmo `none`, `kid` não confiável, assinatura inválida, scope mínimo ausente e claim temporal ausente.
  - [x] Confirmar que `TenantApplicationService.resolve_m2m_tenant_context` limpa tenant em falha e não registra token bruto.

- [x] CTOS-137 — Cobrir autorização e cross-tenant no gate (AC: 2, 4)
  - [x] Reutilizar `AuthorizationOperationRegistry`, `AuthorizedOperationFacade`, `AuthorizationSubject`, `ProtectedResource` e `TenantApplicationService.authorize_operation`.
  - [x] Cobrir deny-by-default, operação desconhecida, scope insuficiente, role insuficiente, sujeito inválido e recurso de outro tenant.
  - [x] Garantir que requisitos de autorização nunca sejam autodeclarados fora da registry.

- [x] CTOS-138 — Cobrir propagação confiável gRPC e eventos no gate (AC: 3, 4)
  - [x] Reutilizar `TrustedContext`, `PropagatedContext`, `context_from_grpc_metadata`, `context_to_grpc_metadata`, `cloudevent_context_from_attributes` e adapters locais.
  - [x] Cobrir metadata duplicada, chave sensível, chave `-bin`, chave uppercase, valores malformados, `tenant_id` incompatível e `traceparent` inválido.
  - [x] Cobrir CloudEvents com `specversion` inválida, extensões com underscore, ausência de `tenantid`/`correlationid`/`idempotencykey`/`traceparent` e tentativa de transportar payload sensível.

- [x] CTOS-139 — Validar logs mascarados e rastreáveis no gate (AC: 4)
  - [x] Reutilizar `build_structured_log`, `mask_sensitive_data`, `ObservabilityContext` e `InMemoryOperationLogger`.
  - [x] Criar helper de teste, se útil, para serializar logs e procurar vazamentos sensíveis de forma consistente.
  - [x] Verificar presença de correlação técnica e ausência de `Authorization`, bearer token, `token_id`, `client_secret`, CPF, CNPJ, e-mail completo, payload bruto, renda e dados financeiros detalhados.

- [x] CTOS-140 — Integrar gate consolidado ao CI e scripts locais (AC: 5)
  - [x] Preservar no CI: secret scan com Gitleaks, `uv lock --check`, `uv sync --locked`, Ruff lint, Ruff format check, Pyright, contratos, harness local e pytest.
  - [x] Atualizar `scripts/dev` apenas se for necessário expor comando focado, sem quebrar `./scripts/dev all`.
  - [x] Atualizar `tests/test_ci_workflow.py` se o workflow ou a lista de comandos obrigatórios mudar.

- [x] CTOS-141 — Registrar evidências finais e sincronizar BMAD/Jira (AC: 5)
  - [x] Atualizar esta story com arquivos alterados, comandos executados e resultados.
  - [x] Mover subtarefas Jira conforme avanço: TODO → WIP → Review QA → Done.
  - [x] Atualizar `sprint-status.yaml` para `review` após implementação e para `done` após code review aprovado.

### Review Findings

- [x] [Review][Patch] Endurecer verificação de vazamento em logs para chaves sensíveis, variações de caixa e valores aninhados [services/identity-tenant/tests/integration/test_epic1_security_gates.py:552]
- [x] [Review][Patch] Verificar `code`, `safe_message` e `grpc_status` dos erros retornados pelos gates negativos [services/identity-tenant/tests/integration/test_epic1_security_gates.py:153]
- [x] [Review][Patch] Adicionar canários positivos para autenticação M2M, autorização, gRPC e CloudEvents válidos [services/identity-tenant/tests/integration/test_epic1_security_gates.py:101]
- [x] [Review][Patch] Ampliar cobertura de claims/campos obrigatórios e `traceparent` nos contextos confiáveis [services/identity-tenant/tests/integration/test_epic1_security_gates.py:260]
- [x] [Review][Patch] Tornar a validação de CI/scripts menos dependente de simples substrings [services/identity-tenant/tests/integration/test_epic1_security_gates.py:393]
- [x] [Review][Patch] Ajustar a matriz documental para não prometer duplicidade de atributos CloudEvents quando o contrato atual usa `Mapping` [services/identity-tenant/README.md:65]
- [x] [Review][Defer] Confirmar branch protection/required checks no GitHub como controle operacional fora do repositório [services/identity-tenant/README.md:67] — deferred, pre-existing
- [x] [Review][Defer] Criar teste de bloqueio antes de caso de uso sensível real quando o primeiro fluxo de negócio consumir o gate do Epic 1 [services/identity-tenant/tests/integration/test_epic1_security_gates.py:273] — deferred, pre-existing

## Dev Notes

### Escopo desta story

- Esta story é um gate de fechamento do Epic 1, não uma expansão funcional de autenticação/autorização.
- O resultado esperado é aumentar segurança verificável por testes, documentação e CI; produção de novo endpoint, novo serviço, provedor real de identidade, Istio/EKS real, NATS real ou integração externa fica fora do escopo.
- Se os testes revelarem lacuna pequena no código existente, corrigir a raiz mantendo o padrão DDD/hexagonal. Se revelarem decisão arquitetural nova, registrar como pendência/ADR em vez de improvisar.
- Preferir um teste consolidado como `services/identity-tenant/tests/integration/test_epic1_security_gates.py` para expressar os gates do Epic 1 ponta-a-ponta, reutilizando testes unitários já existentes como cobertura complementar.

### Regras de arquitetura obrigatórias

- Backend segue DDD + Hexagonal Architecture: `domain` não depende de FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, Docker, Kubernetes ou provedores externos.
- `Identity & Tenant` é fonte de verdade para tenants, clientes técnicos, usuários, roles, permissions, scopes, claims e contexto confiável.
- Segurança é `deny-by-default`: todo endpoint/operação sensível exige autenticação e autorização explícita, exceto exceções públicas documentadas.
- `tenant_id` confiável vem de autenticação/contexto validado e catálogo de tenant; payload de negócio nunca é fonte de verdade.
- Modelo multi-tenant do MVP é `bridge`: recursos compartilhados com dados/recursos críticos isolados por tenant; testes cross-tenant são gate obrigatório.
- Chamadas internas síncronas usam gRPC; fluxos assíncronos usam NATS JetStream e CloudEvents/AsyncAPI. Esta story valida helpers/contratos locais, não infraestrutura real.

### Estado atual que deve ser preservado

- `.github/workflows/ci.yml` já possui job `quality-gates` com secret scan, lockfile, sync locked, Ruff, Pyright, contratos, harness local e pytest.
- `scripts/dev all` já executa os gates locais principais; mantenha equivalência com CI se alterar comandos.
- `tests/test_ci_workflow.py` já protege a presença dos gates no workflow.
- `LocalM2MTokenVerifier` já valida issuer, audience, temporalidade, assinatura simulada, algoritmo, `kid`, scopes mínimos e sujeito/cliente M2M.
- `TenantApplicationService` já centraliza logging operacional com `build_structured_log`, mascaramento e logger best-effort.
- `AuthorizationOperationRegistry` e `AuthorizedOperationFacade` já impedem requisitos de autorização autodeclarados.
- `TrustedContext`/`PropagatedContext` e helpers gRPC/CloudEvents já bloqueiam metadata duplicada, chaves sensíveis, documentos brasileiros embutidos, `traceparent` inválido e contexto malformado.

### Padrões de logging e mascaramento

- Logs devem ser estruturados, mascarados e conter rastreabilidade mínima: serviço, versão, ambiente, operação, origem, destino, contrato, status, duração, `correlation_id`, `request_id` e `trace_id`.
- `tenant_id` e `tenant_isolation_tier` só devem aparecer quando vierem de tenant criado/resolvido, sujeito autorizado ou contexto confiável validado.
- Em falha M2M, usar contexto sem tenant. Em falha de contexto gRPC/CloudEvents, limpar tenant recebido de carrier ainda não validado.
- Nunca registrar bearer token, header `Authorization`, `token_id`/`jti`, secret, API key, senha, payload bruto, CPF, CNPJ, e-mail completo, telefone completo, renda detalhada, documentos/imagens ou resposta externa sensível.
- Máscara forte é padrão para logs/traces/dashboards; identificação operacional usa `proposal_id`, `customer_reference`, correlation ID, trace ID ou HMAC, não CPF/CNPJ/e-mail visível.

### Testes obrigatórios

- Criar ou atualizar testes focados para consolidar os ACs, preferencialmente em `services/identity-tenant/tests/integration/test_epic1_security_gates.py`.
- Reutilizar fixtures/helpers existentes de `services/identity-tenant/tests/unit/*`, `packages/security/tests/unit/*`, `tests/test_observability_foundation.py` e `tests/test_sensitive_data_masking.py` em vez de duplicar infraestrutura de teste.
- Testar logs como estrutura serializável e também como texto serializado para detectar vazamentos em qualquer campo aninhado.
- Garantir que o gate falhe se alguém remover comandos críticos do CI ou de `scripts/dev all`.
- Rodar, no mínimo, teste focado antes da suíte completa. Antes de review, rodar:
  - `uv lock --check`
  - `uv sync --locked`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run pyright`
  - `uv run python scripts/check_contracts.py`
  - `uv run python scripts/local_harness.py check`
  - `uv run pytest`

### Arquivos prováveis

- Provável novo arquivo:
  - `services/identity-tenant/tests/integration/test_epic1_security_gates.py`
- Prováveis atualizações se necessário:
  - `services/identity-tenant/README.md`
  - `tests/test_ci_workflow.py`
  - `scripts/dev`
  - `.github/workflows/ci.yml`
  - `_bmad-output/implementation-artifacts/1-5-gates-de-seguranca-e-isolamento-do-epic-1.md`
  - `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Evitar alterar contratos nesta story:
  - `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto`
  - `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json`
  - `packages/contracts/catalog/contracts.toml`

### Anti-padrões proibidos

- Não adicionar `grpcio`, SDK CloudEvents, cliente NATS, provedor OIDC real, ferramenta nova de CI ou biblioteca de policy apenas para cumprir esta story.
- Não criar domínio compartilhado em `packages/`; pacotes compartilhados continuam restritos a contratos, segurança, observabilidade, testes e utilidades técnicas genéricas.
- Não transformar logs operacionais em trilha oficial de auditoria; auditoria oficial pertence ao futuro `Audit & Evidence`.
- Não usar CPF, CNPJ, e-mail ou `tenant_id` vindo de payload/body como fonte confiável.
- Não usar `# noqa`, skips, xfail ou relaxamento de Pyright/Ruff para esconder regressões de segurança.

### Pesquisa técnica atualizada

- Pytest suporta `--strict-markers` e erro para markers desconhecidos; o projeto já usa `--strict-config` e `--strict-markers`, então novos markers exigem registro explícito.
- Ruff recomenda `ruff check` como entrada principal do linter e `ruff format --check` para verificação de formatação; o projeto já usa ambos.
- Pyright suporta `typeCheckingMode` em `off`, `basic`, `standard` e `strict`; o projeto está em `basic` progressivo e esta story não deve relaxar tipagem.
- `uv lock --check` valida se o lockfile está atualizado em relação ao metadata do projeto, sem atualizar dependências automaticamente.
- GitHub Actions com checks obrigatórios pode bloquear merge quando checks falham ou ficam pendentes por filtros; evitar path filters para o gate principal enquanto ele for required check.
- Gitleaks suporta scan de repositório Git e `--redact=100`; o CI atual usa imagem Docker pinada e deve continuar redigindo segredos na saída.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 1 e Story 1.5.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-5, AD-6, AD-7, AD-16, AD-17 e AD-23.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/reviews/review-gate-summary.md` — gates arquiteturais e reforço de testes negativos cross-tenant.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/autenticacao-autorizacao-oq7.md` — OIDC/OAuth, M2M, RBAC, scopes, claims e propagação interna.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/multi-tenancy-oq6.md` — modelo `bridge`, controles de tenant e testes cross-tenant.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md` — política de mascaramento e requisitos verificáveis contra vazamento.
- `_bmad-output/implementation-artifacts/1-2-autenticacao-m2m-com-resolucao-de-tenant.md` — padrões M2M e logs seguros.
- `_bmad-output/implementation-artifacts/1-3-autorizacao-por-rbac-scopes-e-claims-de-tenant.md` — autorização local, registry e fachada.
- `_bmad-output/implementation-artifacts/1-4-propagacao-de-contexto-confiavel-entre-servicos.md` — metadata gRPC, CloudEvents e achados de review corrigidos.
- `.github/workflows/ci.yml` — job `quality-gates`.
- `scripts/dev` — comando local `all`.
- `pyproject.toml` — configuração pytest, Ruff, Pyright e workspace.
- Pytest docs: `https://docs.pytest.org/en/stable/reference/reference.html`
- Ruff linter docs: `https://docs.astral.sh/ruff/linter/`
- Ruff formatter docs: `https://docs.astral.sh/ruff/formatter/`
- Pyright configuration docs: `https://github.com/microsoft/pyright/blob/main/docs/configuration.md`
- uv lock/sync docs: `https://docs.astral.sh/uv/concepts/projects/sync/`
- GitHub required status checks docs: `https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks`
- GitHub Actions workflow syntax docs: `https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax`
- Gitleaks docs: `https://github.com/gitleaks/gitleaks`

## Checklist Validation

- [x] Story identifica objetivo, ACs e tarefas verificáveis.
- [x] Story referencia Epic 1, PRD, Architecture Spine e aprendizados das Stories 1.2, 1.3 e 1.4.
- [x] Story evita reinvenção e aponta os helpers/classes existentes que devem ser reutilizados.
- [x] Story define escopo negativo para evitar novas tecnologias, serviços reais ou infraestrutura fora do ciclo.
- [x] Story inclui padrões de teste, CI, logging, mascaramento, multi-tenancy e rastreabilidade.
- [x] Story registra subtarefas Jira criadas para execução rastreável.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-12 — Branch `agent/story-1-5-gates-seguranca-isolamento-epic-1` criada no início da Story 1.5.
- 2026-08-12 — `CTOS-27` movida para WIP no Jira antes do detalhamento, conforme fluxo acordado.
- 2026-08-12 — `bmad-create-story` executado para detalhar Story 1.5 antes da implementação.
- 2026-08-12 — Subtarefas `CTOS-135` a `CTOS-141` criadas no Jira para execução rastreável.
- 2026-08-12 — `bmad-dev-story` iniciado; `CTOS-135` movida para WIP.
- 2026-08-12 — `CTOS-135` concluída com matriz de gates no README do serviço e teste consolidado correspondente.
- 2026-08-12 — `CTOS-136` concluída com gate negativo de autenticação M2M e validação de logs sem token/header sensível.
- 2026-08-12 — `CTOS-137` concluída com gate de autorização, deny-by-default, registry obrigatória e bloqueio cross-tenant.
- 2026-08-12 — `CTOS-138` concluída com gate de contexto confiável para metadata gRPC e CloudEvents.
- 2026-08-12 — `CTOS-139` concluída com helper de teste para logs serializados e bloqueio de vazamentos sensíveis.
- 2026-08-12 — `CTOS-140` concluída preservando comandos bloqueantes de CI e `scripts/dev all`.
- 2026-08-12 — Validações finais executadas; `CTOS-141` pronta para conclusão e Story 1.5 movida para review.
- 2026-08-12 — `bmad-code-review` executado com revisão adversarial; 6 patches aplicados, 2 itens operacionais diferidos e nenhum finding bloqueante remanescente.

### Completion Notes List

- 2026-08-12 — Story 1.5 criada como guia de implementação com status `ready-for-dev`.
- 2026-08-12 — Contexto de Epic 1, Architecture Spine, PRD OQ-6/OQ-7/OQ-10, Stories 1.2/1.3/1.4, CI atual, testes existentes e documentação técnica oficial analisados.
- 2026-08-12 — Registrado que a implementação deve consolidar gates e testes sem introduzir nova tecnologia, provedor real de identidade, service mesh real, NATS real ou contratos novos sem justificativa.
- 2026-08-12 — Matriz operacional de gates do Epic 1 registrada em `services/identity-tenant/README.md`.
- 2026-08-12 — Teste focado inicial `services/identity-tenant/tests/integration/test_epic1_security_gates.py` executado com `35 passed`.
- 2026-08-12 — Gate M2M consolidado cobre token ausente, desconhecido, expirado, `nbf`, issuer, audience, algoritmo, `kid`, assinatura, scope mínimo e claim temporal ausente.
- 2026-08-12 — Gate de autorização consolidado cobre scope ausente, role ausente, operação desconhecida, requisito fora da registry e recurso cross-tenant.
- 2026-08-12 — Gate de propagação consolidado bloqueia metadata/CloudEvents ausentes, duplicados, sensíveis, malformados, com tenant incompatível ou `traceparent` inválido.
- 2026-08-12 — Gate de logs consolidado verifica correlação técnica, tenant apenas confiável e ausência de tokens, secrets, documentos, e-mail completo, payload bruto e dados financeiros.
- 2026-08-12 — Gate de CI/scripts consolidado protege secret scan, lockfile, sync locked, lint, format, typecheck, contratos, harness local e pytest, sem path filters.
- 2026-08-12 — Validações finais verdes: `uv lock --check`, `uv sync --locked`, `ruff check .`, `ruff format --check .`, `pyright`, `scripts/check_contracts.py`, `scripts/local_harness.py check` e suíte completa `159 passed`.
- 2026-08-12 — Revisão adversarial fortaleceu o helper de vazamento de logs, validou forma segura de erros, adicionou canários positivos, ampliou campos obrigatórios gRPC/CloudEvents, endureceu verificação de CI/scripts e removeu `token_id` dos logs aceitos de M2M.
- 2026-08-12 — Validações pós-review verdes: `services/identity-tenant/tests` com `138 passed`, suíte completa com `191 passed`, `ruff check .`, `ruff format --check .` e `pyright`.

### Change Log

- 2026-08-12 — Adicionado gate consolidado do Epic 1 para autenticação, autorização, isolamento, contexto confiável, logs seguros e CI bloqueante.
- 2026-08-12 — Documentada matriz operacional de gates no README do `Identity & Tenant Service`.
- 2026-08-12 — Story movida para `review` após validações completas.
- 2026-08-12 — Patches de code review aplicados e Story movida para `done`.

### File List

- `_bmad-output/implementation-artifacts/1-5-gates-de-seguranca-e-isolamento-do-epic-1.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/identity-tenant/README.md`
- `services/identity-tenant/src/creditos_identity_tenant/application/service.py`
- `services/identity-tenant/tests/integration/test_epic1_security_gates.py`
