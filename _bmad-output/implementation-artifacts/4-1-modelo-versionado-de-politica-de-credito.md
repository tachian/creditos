---
jira_issue: CTOS-39
branch: agent/story-4-1-modelo-versionado-politica-credito
baseline_commit: adab7c0
---

# Story 4.1: Modelo Versionado de Política de Crédito

Status: done

## Story

Como gestor de crédito,
quero criar políticas versionadas com regras, critérios, limites e metadados,
para que decisões futuras sejam governadas por artefatos rastreáveis.

## Acceptance Criteria

1. **Criação de política em draft**
   - **Given** um gestor autorizado com contexto confiável de tenant
   - **When** cria uma política de crédito em draft
   - **Then** a política recebe `policy_id`, `policy_version_id`, versão, status `draft`, owner, produto, tenant/contexto aplicável, aplicabilidade, regras, critérios, limites e changelog inicial
   - **And** a política em draft não pode ser usada para decidir propostas produtivas.

2. **Alteração rastreável de draft**
   - **Given** uma política em status `draft`
   - **When** o gestor salva uma alteração em regras, critérios, limites, metadados ou aplicabilidade
   - **Then** a alteração preserva histórico mínimo com ator, timestamp, resumo da mudança, versão/revisão anterior e versão/revisão resultante
   - **And** não sobrescreve nem altera nenhuma versão publicada.

3. **Invariantes de versionamento e imutabilidade**
   - **Given** uma política publicada ou arquivada
   - **When** qualquer fluxo tenta alterar regras, critérios, limites, aplicabilidade, owner, produto ou metadados governados
   - **Then** a alteração é rejeitada por regra de domínio
   - **And** correções futuras devem criar nova versão em draft, sem mutar artefatos publicados.

4. **Isolamento por tenant e contexto confiável**
   - **Given** políticas de tenants diferentes no mesmo serviço compartilhado
   - **When** uma política é criada, consultada ou alterada
   - **Then** o `tenant_id` usado vem exclusivamente do contexto confiável da aplicação
   - **And** tentativas cross-tenant são rejeitadas e cobertas por teste negativo.

5. **Modelo governado sem payload arbitrário**
   - **Given** regras, critérios, limites e metadados de política
   - **When** o modelo de domínio valida a política
   - **Then** aceita apenas estruturas governadas, fechadas e verificáveis para produtos MVP
   - **And** rejeita campos livres como `payload`, `raw_payload`, `metadata` arbitrário, dados de fornecedor, CPF, CNPJ, e-mail, nome, endereço, token ou segredo.

6. **Evento/intenção auditável de alteração sensível**
   - **Given** criação ou alteração de política
   - **When** a operação é concluída pela aplicação
   - **Then** emite uma intenção auditável minimizada por porta de aplicação, contendo tenant, ator, política, versão, tipo de mudança, correlation ID e dados log-safe
   - **And** não trata log estruturado como auditoria oficial.

## Tasks / Subtasks

- [x] CTOS-39 — Implementar modelo versionado de política de crédito (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-225 — Criar a base do `Decision Service` em `services/decision` seguindo DDD + arquitetura hexagonal. (AC: 1, 4)
  - [x] CTOS-226 — Modelar value objects de política, versão, status, owner, produto, aplicabilidade, changelog, regras, critérios e limites. (AC: 1, 3, 5)
  - [x] CTOS-227 — Criar entidade/agregado de política com criação em draft, atualização rastreável e invariantes de imutabilidade. (AC: 1, 2, 3)
  - [x] CTOS-228 — Criar portas de aplicação para repositório de políticas e publicação de intenção auditável minimizada. (AC: 2, 4, 6)
  - [x] CTOS-229 — Implementar repositório in-memory com isolamento por tenant e proteção contra alteração cross-tenant. (AC: 2, 3, 4)
  - [x] CTOS-228 — Implementar application service para criar, consultar e alterar políticas draft usando contexto confiável. (AC: 1, 2, 4, 6)
  - [x] CTOS-230 — Adicionar testes unitários para criação, alteração, histórico, imutabilidade, tenant isolation, produtos MVP e rejeição de dados sensíveis/arbitrários. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-231 — Atualizar documentação do `Decision Service`, `sprint-status.yaml`, esta story e Jira conforme avanço. (AC: 1, 6)

### Review Findings

- [x] [Review][Patch] Usar `creditos_security.TrustedContext`/`TrustedApplicationContext` como fonte confiável de autorização e ator para operações de política [services/decision/src/creditos_decision/application/service.py:83]
- [x] [Review][Patch] Modelo aceita campos de regra/critério arbitrários e filtro sensível é contornável [services/decision/src/creditos_decision/domain/value_objects/policy.py:337]
- [x] [Review][Patch] Value objects e reidratação permitem bypass das factories e changelog inconsistente [services/decision/src/creditos_decision/domain/entities/credit_policy.py:120]
- [x] [Review][Patch] Tentativas rejeitadas sensíveis não emitem intenção auditável minimizada [services/decision/src/creditos_decision/application/service.py:134]
- [x] [Review][Patch] Persistência ocorre antes da auditoria sem rollback/atomicidade [services/decision/src/creditos_decision/application/service.py:108]
- [x] [Review][Patch] Atualização de draft pode perder changelog por falta de controle otimista [services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_policy_repository.py:25]
- [x] [Review][Patch] Operadores de regra não validam tipo semântico do valor [services/decision/src/creditos_decision/domain/value_objects/policy.py:343]
- [x] [Review][Patch] Janela de aplicabilidade aceita datetimes naive ou mistos [services/decision/src/creditos_decision/domain/value_objects/policy.py:102]
- [x] [Review][Patch] Contexto de tenant não valida `tenant_isolation_tier` bridge nem normaliza tenant antes do acesso [services/decision/src/creditos_decision/application/service.py:281]
- [x] [Review][Patch] `uv.lock` não inclui o novo pacote `creditos-decision` [uv.lock:17]

## Dev Notes

### Escopo desta story

- Esta story inicia o `Decision Service` com o modelo de política versionada; ela não implementa motor de execução de decisão, publicação produtiva, simulação, catálogo completo de reason codes, regras de IA, API HTTP/gRPC real, banco real ou NATS real.
- O foco é criar o núcleo de domínio e aplicação que permite governar políticas em draft sem comprometer decisões futuras.
- A implementação deve ser mínima, verificável e extensível para as Stories 4.2 a 4.8.
- Como não há nova tecnologia selecionada nesta story, manter a stack já aprovada: Python 3.13, DDD, arquitetura hexagonal, testes com pytest, qualidade com ruff/pyright e adapters in-memory.

### Fronteiras de domínio

- `Decision` é o bounded context dono de políticas, versões, decisões, códigos de motivo, inconclusivos e termos aprovados.
- `Proposal Intake` continua dono da proposta canônica.
- `Integration` continua dono de provedores externos e resultados canônicos de integração.
- `Automated Review` continua dono da IA consultiva; esta story não deve chamar nem acoplar IA ao modelo de política.
- `Audit & Evidence` é dono da auditoria oficial; o `Decision Service` deve apenas emitir intenção/evento minimizado por porta, sem implementar trilha oficial append-only nesta story.

### Modelo de política esperado

- Identificadores técnicos log-safe: `policy_id`, `policy_version_id`, `tenant_id`, `owner_subject_id`, `correlation_id`.
- Status mínimos de domínio: `draft`, `published`, `archived`. A Story 4.1 cria e altera apenas `draft`; `published` e `archived` existem para proteger imutabilidade e preparar a Story 4.4.
- Produtos MVP permitidos: `personal_credit`, `bnpl`, `business_credit` e `receivables`.
- Aplicabilidade mínima: tenant/contexto confiável, produto, canais opcionais governados e datas de validade opcionais, sem aceitar tenant no payload como autoridade.
- Changelog mínimo: ator, timestamp, tipo de mudança, resumo log-safe, revisão anterior, revisão resultante e correlation ID.
- Regras, critérios e limites devem ser estruturas fechadas e governadas. Se houver necessidade de expressões flexíveis, usar um modelo pequeno e tipado, não JSON livre.

### Segurança, privacidade e auditoria

- Política de crédito é configuração sensível: criação, alteração, tentativa de alteração proibida e tentativa cross-tenant devem ser auditáveis.
- Não gravar CPF, CNPJ, e-mail completo, nome, endereço, token, segredo, payload bruto de proposta, payload de fornecedor externo ou resposta proprietária em política, changelog, erro, evento, teste ou log.
- Logs estruturados ajudam rastreabilidade operacional, mas não substituem auditoria oficial.
- Falhas de autorização e cross-tenant devem falhar de forma controlada, sem revelar existência de política de outro tenant.

### Multi-tenancy

- O MVP usa modelo `bridge`: serviço compartilhado com dados e recursos isolados por tenant.
- `tenant_id` confiável deve vir do contexto autenticado/propagado pela aplicação, nunca de body, metadado livre ou parâmetro fornecido pelo cliente sem validação.
- Repositórios e consultas devem sempre receber tenant/contexto e filtrar por ele.
- Testes negativos cross-tenant são obrigatórios antes da story ir para review.

### Estrutura esperada

```text
services/decision/
  README.md
  pyproject.toml
  src/creditos_decision/
    __init__.py
    adapters/
      __init__.py
      persistence/
        __init__.py
        in_memory_credit_policy_repository.py
    application/
      __init__.py
      ports/
        __init__.py
        credit_policy_audit_publisher.py
        credit_policy_repository.py
      service.py
    bootstrap/
      __init__.py
    domain/
      __init__.py
      entities/
        __init__.py
        credit_policy.py
      errors.py
      value_objects/
        __init__.py
        policy.py
  tests/unit/
    test_credit_policy_model.py
    test_credit_policy_service.py
```

### Arquivos provavelmente afetados

- `services/decision/README.md`
- `services/decision/pyproject.toml`
- `services/decision/src/creditos_decision/**/*.py`
- `services/decision/tests/unit/*.py`
- `pyproject.toml`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/4-1-modelo-versionado-de-politica-de-credito.md`

### Anti-padrões proibidos

- Não implementar execução determinística de decisão nesta story; isso pertence à Story 4.5.
- Não implementar publicação imutável real nesta story; isso pertence à Story 4.4.
- Não implementar simulação de política; isso pertence à Story 4.3.
- Não implementar catálogo completo de reason codes; isso pertence à Story 4.2.
- Não criar API HTTP/gRPC real se domínio e application service bastarem para cumprir os ACs.
- Não adicionar banco, migrations, broker, SDK externo, motor de regras externo ou nova dependência sem decisão explícita.
- Não criar campo genérico `metadata`, `custom`, `attributes`, `payload`, `raw_payload` ou equivalente como escape hatch.
- Não acoplar política a payload proprietário de fornecedor externo ou a modelos de IA.
- Não usar logs como trilha oficial de auditoria.

### Testing Requirements

- Rodar testes focados do serviço: `uv run pytest services/decision/tests/unit -q`.
- Rodar qualidade mínima: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`.
- Rodar suíte completa quando viável antes de PR: `uv run pytest -q`.
- Se alguma validação falhar por ambiente/sandbox, registrar o bloqueio e repetir fora do sandbox quando autorizado.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 4 e Story 4.1.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/functional-requirements.md` — FR-10 a FR-15 sobre políticas, decisões e explicabilidade.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/autenticacao-autorizacao-oq7.md` — scopes `policy:read` e `policy:write`, RBAC e contexto de tenant.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md` — auditoria oficial append-only e falhas críticas.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-5, AD-6, AD-7, AD-9 e bounded contexts.
- `_bmad-output/implementation-artifacts/1-5-gates-de-seguranca-e-isolamento-do-epic-1.md` — segurança, contexto confiável, tenant isolation e mascaramento.
- `_bmad-output/implementation-artifacts/2-1-definicao-do-contrato-canonico-de-proposta.md` — produtos MVP e governança de payload canônico.
- `_bmad-output/implementation-artifacts/3-6-contratos-e-gates-de-integracao.md` — proteção contra payload proprietário e expectativas de consumidores.

## Checklist Validation

- [x] Story possui objetivo, ACs e tarefas verificáveis.
- [x] Story preserva DDD, arquitetura hexagonal e fronteira do `Decision Service`.
- [x] Story delimita explicitamente o que fica fora de escopo para evitar overbuild.
- [x] Story mantém segurança, privacidade, multi-tenancy, auditabilidade e explicabilidade como preocupações centrais.
- [x] Story evita nova tecnologia, dependência externa ou motor de regras sem decisão explícita.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-25 — Branch `agent/story-4-1-modelo-versionado-politica-credito` criada no início da Story 4.1 a partir de `main` em `adab7c0`.
- 2026-08-25 — `CTOS-39` movida para `Em andamento` no Jira antes do detalhamento.
- 2026-08-25 — `bmad-create-story` executado para detalhar Story 4.1 antes da implementação.
- 2026-08-25 — Subtarefas Jira `CTOS-225` a `CTOS-231` criadas para rastrear base do serviço, domínio, aplicação, persistência, testes e documentação.
- 2026-08-26 — `bmad-dev-story` iniciado; `CTOS-225` movida para `Em andamento`.
- 2026-08-26 — Testes RED criados para domínio e application service antes da implementação.
- 2026-08-26 — Subtarefas Jira `CTOS-225` a `CTOS-231` movidas para `Concluído` após validações verdes.
- 2026-08-26 — Code review adversarial executado; achados registrados e ciclo de patch iniciado.
- 2026-08-26 — Patches do code review aplicados com foco em contexto confiável, governança de campos, auditoria de rejeições, rollback, concorrência otimista, datetimes UTC e lockfile.

### Implementation Plan

- Criar testes RED do domínio e application service para criação, alteração e invariantes de política.
- Criar `Decision Service` mínimo seguindo o template DDD/hexagonal dos serviços existentes.
- Modelar value objects e agregado de política com estruturas fechadas e validações explícitas.
- Implementar repositório in-memory e porta de intenção auditável minimizada.
- Validar isolamento por tenant, ausência de dados sensíveis/arbitrários e imutabilidade de versões publicadas.

### File List

- `_bmad-output/implementation-artifacts/4-1-modelo-versionado-de-politica-de-credito.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `pyproject.toml`
- `uv.lock`
- `services/decision/README.md`
- `services/decision/pyproject.toml`
- `services/decision/src/creditos_decision/__init__.py`
- `services/decision/src/creditos_decision/adapters/__init__.py`
- `services/decision/src/creditos_decision/adapters/persistence/__init__.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_policy_repository.py`
- `services/decision/src/creditos_decision/application/__init__.py`
- `services/decision/src/creditos_decision/application/ports/__init__.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_repository.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/bootstrap/__init__.py`
- `services/decision/src/creditos_decision/domain/__init__.py`
- `services/decision/src/creditos_decision/domain/entities/__init__.py`
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`
- `services/decision/src/creditos_decision/domain/errors.py`
- `services/decision/src/creditos_decision/domain/value_objects/__init__.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy.py`
- `services/decision/tests/unit/test_credit_policy_model.py`
- `services/decision/tests/unit/test_credit_policy_service.py`

### Completion Notes List

- 2026-08-25 — Story 4.1 criada com status `ready-for-dev`, escopo limitado ao modelo versionado de política de crédito.
- 2026-08-26 — `Decision Service` criado com estrutura DDD/hexagonal, domínio puro, application service, portas e adapter in-memory.
- 2026-08-26 — Modelo versionado de política implementado com criação em draft, alteração rastreável, changelog, imutabilidade para snapshots publicados/arquivados e bloqueio de produção para drafts.
- 2026-08-26 — Isolamento por tenant implementado via `ObservabilityContext` confiável e repositório in-memory tenant-aware; consultas/alterações cross-tenant retornam erro controlado sem revelar a política.
- 2026-08-26 — Intenção auditável minimizada implementada para criação e alteração de política, sem usar logs como auditoria oficial.
- 2026-08-26 — Testes adicionados para criação, atualização, histórico, imutabilidade, tenant isolation, ausência de dados sensíveis/arbitrários e auditoria minimizada.
- 2026-08-26 — Code review aplicado: operações de política passam a exigir `PropagatedContext`, ator vem do contexto confiável, scopes `policy:write`/`policy:read` são obrigatórios e apenas tenant tier `bridge` é aceito nesta story.
- 2026-08-26 — Modelo reforçado com allowlist de campos governados, bloqueio de CPF/CNPJ/e-mail/campos sensíveis, validação semântica de operadores, datetimes UTC-aware, changelog consistente e construtores diretos revalidados.
- 2026-08-26 — Persistência in-memory reforçada com rollback em falha de auditoria e controle otimista por `expected_revision`.
- 2026-08-26 — Validações verdes finais: `uv run ruff format --check .`; `uv run ruff check .`; `uv run pyright`; `uv run pytest services/decision/tests/unit -q` com `15 passed`; suíte completa fora do sandbox com `426 passed`.

### Change Log

- 2026-08-25 — Criada a story detalhada da Story 4.1 e preparado o Epic 4 para início de desenvolvimento.
- 2026-08-26 — Implementada a Story 4.1 e movida para `review`.
- 2026-08-26 — Story retornou para `in-progress` para aplicar patches do code review.
- 2026-08-26 — Patches do code review aplicados e Story 4.1 marcada como `done`.
