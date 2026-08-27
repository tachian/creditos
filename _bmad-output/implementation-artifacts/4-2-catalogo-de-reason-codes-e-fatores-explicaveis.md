---
jira_issue: CTOS-40
branch: agent/story-4-2-catalogo-reason-codes-fatores-explicaveis
baseline_commit: 5892c2e
---

# Story 4.2: Catálogo de Reason Codes e Fatores Explicáveis

Status: done

## Story

Como analista de risco,
quero manter reason codes e fatores relevantes versionados,
para que decisões possam ser explicadas de forma consistente.

## Acceptance Criteria

1. **Catálogo versionado de reason codes**
   - **Given** um analista autorizado com contexto confiável de tenant
   - **When** cria ou altera um catálogo de reason codes e fatores explicáveis
   - **Then** o catálogo recebe identificadores técnicos, versão, revisão, status, tenant, owner, produto/escopo aplicável, itens governados, changelog e correlation ID
   - **And** o catálogo em draft não pode ser tratado como referência produtiva para decisões finais.

2. **Referência obrigatória em regras de decisão**
   - **Given** uma política com regras de decisão
   - **When** uma regra contribui para aprovação, recusa, aprovação com alterações, solicitação de dados adicionais ou inconclusão
   - **Then** cada `reason_code_ref` da regra deve apontar para reason code válido, ativo, versionado e compatível com o resultado da regra
   - **And** regra sem reason code, com reason code inexistente, arquivado, duplicado ou incompatível deve ser rejeitada por erro de domínio.

3. **Descrições e fatores explicáveis seguros**
   - **Given** um reason code ou fator explicável exibível para instituição cliente
   - **When** o catálogo valida suas descrições
   - **Then** aceita apenas textos seguros, curtos, compreensíveis e sem CPF, CNPJ, e-mail, nome, endereço, token, segredo, payload bruto ou dado proprietário externo
   - **And** diferencia descrição interna segura de descrição externa/customer-facing quando necessário.

4. **Mudança incompatível exige nova versão**
   - **Given** um catálogo existente com decisões passadas ou políticas que referenciam reason codes
   - **When** uma alteração remove, renomeia semanticamente, troca categoria/resultado, altera descrição externa de forma incompatível ou muda fator obrigatório
   - **Then** a alteração deve criar nova versão do catálogo
   - **And** versões anteriores permanecem reidratáveis para explicar decisões passadas.

5. **Compatibilidade com políticas versionadas**
   - **Given** uma política draft criada na Story 4.1
   - **When** a política é criada ou alterada com `reason_code_refs`
   - **Then** a validação da aplicação deve conseguir checar as referências contra uma versão de catálogo confiável
   - **And** não deve acoplar a política a payload de fornecedor, IA ou contratos externos.

6. **Auditoria minimizada e isolamento por tenant**
   - **Given** criação, alteração ou rejeição sensível de catálogo
   - **When** a operação termina ou falha
   - **Then** emite intenção auditável minimizada por porta de aplicação com tenant, ator, catálogo, versão, operação, correlation ID e detalhes log-safe
   - **And** usa `creditos_security.PropagatedContext`, exige scopes adequados e bloqueia acesso cross-tenant.

## Tasks / Subtasks

- [x] CTOS-40 — Implementar catálogo de reason codes e fatores explicáveis (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-232 — Criar value objects/enums para reason codes, fatores explicáveis, categoria, audiência, severidade, status e compatibilidade. (AC: 1, 2, 3, 4)
  - [x] CTOS-233 — Criar agregado versionado de catálogo com draft/update, changelog, imutabilidade de versões não-draft e criação de nova versão para mudança incompatível. (AC: 1, 4)
  - [x] CTOS-234 — Implementar validação de `reason_code_refs` de `PolicyRule` contra catálogo versionado, sem transformar o catálogo em payload livre da política. (AC: 2, 5)
  - [x] CTOS-236 — Criar portas e adapter in-memory para catálogo de reason codes com isolamento por tenant e versionamento por catálogo. (AC: 1, 4, 6)
  - [x] CTOS-235 — Estender application service ou criar serviço de aplicação do `Decision` para operações de catálogo com contexto confiável, scopes e auditoria minimizada. (AC: 1, 4, 6)
  - [x] CTOS-237 — Adicionar testes unitários para catálogo, incompatibilidade, privacidade, tenant isolation, auditoria e validação de política contra reason codes. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-238 — Atualizar README do `Decision Service`, story BMAD, `sprint-status.yaml` e Jira conforme avanço. (AC: 1, 6)

### Review Findings

- [x] [Review][Patch] Política pode burlar validação de catálogo e não preserva proveniência do catálogo validado [services/decision/src/creditos_decision/application/service.py:57]
- [x] [Review][Patch] `change_summary` do catálogo não é validado antes de changelog/auditoria log-safe [services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py:38]
- [x] [Review][Patch] Mudanças semânticas de reason code e produto podem ocorrer na mesma versão [services/decision/src/creditos_decision/domain/value_objects/reason_codes.py:195]
- [x] [Review][Patch] Fingerprint de catálogo publicado não cobre identidade, versão e proveniência crítica [services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py:151]
- [x] [Review][Patch] Criação de nova versão pode gerar número duplicado ou regressivo [services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py:357]
- [x] [Review][Patch] Rollback de catálogo após falha de auditoria pode remover estado concorrente válido [services/decision/src/creditos_decision/application/service.py:423]
- [x] [Review][Patch] Auditoria de rejeição de `create_version` pode apontar para a versão errada [services/decision/src/creditos_decision/application/service.py:816]

## Dev Notes

### Escopo desta story

- Implementar o núcleo de domínio e aplicação para catálogo versionado de reason codes e fatores explicáveis dentro de `Decision`.
- Integrar a validação de `PolicyRule.reason_code_refs` criada na Story 4.1 a uma versão de catálogo confiável.
- Não implementar motor de decisão determinística, simulação, publicação produtiva, resposta pública de decisão, API HTTP/gRPC real, banco real, NATS real, IA ou reporting nesta story.
- Não selecionar tecnologia nova; manter Python 3.13, DDD, arquitetura hexagonal, pytest, Ruff, Pyright e adapter in-memory.

### Contexto funcional

- FR-10 exige políticas com regras, critérios, fatores, limites e metadados.
- FR-15 exige explicabilidade da decisão com códigos de motivo, fatores relevantes, regras acionadas e versões.
- AD-15 define que `Decision` é dono de reason codes e que reason codes são catálogo versionado e estável; mudança incompatível exige nova versão.
- AD-18 exige que decisão automatizada preserve política, versão, reason codes, fatores relevantes e evidências para explicação/revisão pelo controlador.

### Modelo de domínio esperado

- Criar estruturas fechadas e governadas; não usar `metadata`, `payload`, `attributes`, `custom` ou JSON livre.
- Reason code deve ter, no mínimo: `reason_code_id`, `code`, `category/outcome`, `title`, descrição interna segura, descrição externa/customer-facing segura, status, severidade ou relevância quando útil, fatores explicáveis vinculados e versão do catálogo.
- Fator explicável deve ser allowlistado e técnico, por exemplo campos canônicos já governados (`monthly_income_units`, `requested_amount_units`, `requested_installments`, `requested_term_days`, `age_years`) ou fatores derivados seguros definidos explicitamente.
- Categorias/outcomes devem se alinhar aos outcomes existentes de `PolicyOutcome`: `approve`, `reject`, `approve_with_changes`, `request_more_data`, `unable_to_decide`.
- Status mínimos para reason code: `active`, `deprecated`, `archived`. Reason code arquivado não pode ser usado por regra nova; deprecated pode continuar explicando decisões passadas, mas deve ser tratado com cuidado em novas políticas.
- Catálogo deve ter status versionado similar à política (`draft`, `published`, `archived`) ou value object próprio equivalente, mantendo imutabilidade para versões não-draft.

### Integração com Story 4.1

Arquivos existentes que provavelmente serão estendidos:

- `services/decision/src/creditos_decision/domain/value_objects/policy.py`: contém `PolicyRule.reason_code_refs`, `PolicyOutcome`, validação de identificadores, textos seguros, campos governados e bloqueio de dados sensíveis com normalização de diacríticos.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`: contém `CreditPolicy`, versionamento, changelog, fingerprint de snapshots não-draft e atualização de draft.
- `services/decision/src/creditos_decision/application/service.py`: usa `PropagatedContext`, scopes `policy:write`/`policy:read`, auditoria minimizada, rollback e tenant tier `bridge`.
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_policy_repository.py`: padrão de repositório in-memory com lock, tenant key, controle otimista e cálculo de próxima versão.
- `services/decision/tests/unit/test_credit_policy_model.py` e `services/decision/tests/unit/test_credit_policy_service.py`: padrões de testes unitários RED→GREEN para domínio, aplicação, privacidade e isolamento.

Não duplicar validações de texto/identificador se a implementação puder extrair helpers técnicos privados para um módulo comum do bounded context, por exemplo `domain/value_objects/_validation.py`. Se extrair, preservar comportamento e testes existentes da Story 4.1.

### Regras de compatibilidade

- Alteração compatível: adicionar reason code novo ativo, adicionar fator opcional seguro, melhorar descrição interna sem alterar semântica externa.
- Alteração incompatível: remover code, reutilizar `code` com nova semântica, alterar `category/outcome`, alterar descrição externa de forma que mude explicação ao cliente, alterar fator obrigatório ou arquivar code usado por política/decisão passada.
- Mudança incompatível deve criar nova versão de catálogo; não reescrever a versão anterior.
- Decisões passadas ainda serão implementadas em stories futuras, mas esta story deve deixar o modelo preparado para reidratar versões antigas.

### Segurança, privacidade e auditoria

- Reason codes e fatores explicáveis não podem conter dados pessoais, dados financeiros detalhados de indivíduo específico, payload de fornecedor, stack trace, token, segredo, CPF, CNPJ, e-mail, nome ou endereço.
- Usar apenas descrições seguras, generalizáveis e compreensíveis para instituição cliente.
- Logs estruturados não substituem auditoria oficial; seguir o padrão da Story 4.1 de intenção auditável minimizada.
- Falhas de autorização e cross-tenant devem falhar de forma controlada, sem revelar existência de catálogo de outro tenant.
- `tenant_id` e ator efetivo vêm exclusivamente de `creditos_security.PropagatedContext`, nunca do comando como fonte de autoridade.

### Multi-tenancy e autorização

- MVP usa tenant tier `bridge`; operações de catálogo devem rejeitar tier diferente como a Story 4.1.
- Usar scopes existentes `policy:write` para criar/alterar catálogo e `policy:read` para consultar/validar catálogo. Não criar scope novo nesta story sem decisão explícita.
- Repositórios e consultas devem sempre receber tenant/contexto e filtrar por tenant.

### Estrutura esperada

Possíveis novos arquivos, mantendo DDD/Hexagonal:

```text
services/decision/src/creditos_decision/domain/value_objects/reason_codes.py
services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py
services/decision/src/creditos_decision/application/ports/reason_code_catalog_repository.py
services/decision/src/creditos_decision/adapters/persistence/in_memory_reason_code_catalog_repository.py
services/decision/tests/unit/test_reason_code_catalog_model.py
services/decision/tests/unit/test_reason_code_catalog_service.py
```

Arquivos existentes provavelmente afetados:

```text
services/decision/src/creditos_decision/domain/value_objects/__init__.py
services/decision/src/creditos_decision/domain/entities/__init__.py
services/decision/src/creditos_decision/application/ports/__init__.py
services/decision/src/creditos_decision/application/service.py
services/decision/src/creditos_decision/domain/value_objects/policy.py
services/decision/src/creditos_decision/domain/entities/credit_policy.py
services/decision/README.md
_bmad-output/implementation-artifacts/sprint-status.yaml
_bmad-output/implementation-artifacts/4-2-catalogo-de-reason-codes-e-fatores-explicaveis.md
```

### Anti-padrões proibidos

- Não criar motor de regras ou execução de decisão nesta story.
- Não publicar política ou catálogo em produção real nesta story.
- Não criar integração com IA ou fornecedores externos.
- Não criar banco/migration/API/gRPC real se domínio, aplicação e in-memory adapter bastarem para cumprir os ACs.
- Não aceitar reason code ou fator vindo de payload livre sem validação e allowlist.
- Não expor descrição com dado sensível ou detalhes internos que possam prejudicar cliente, solicitante ou fornecedor.
- Não quebrar os testes e invariantes da Story 4.1.

### Testing Requirements

- Criar testes RED antes da implementação para os seis ACs.
- Rodar testes focados do Decision: `uv run pytest services/decision/tests/unit -q`.
- Rodar qualidade mínima: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`.
- Rodar suíte completa quando viável antes de PR: `uv run pytest -q`.
- Se a suíte completa falhar por sandbox ao abrir sockets do harness local, repetir fora do sandbox e registrar o resultado.

### Checklist Validation

- [x] Story possui objetivo, ACs e tarefas verificáveis.
- [x] Story preserva DDD, arquitetura hexagonal e fronteira do `Decision Service`.
- [x] Story reaproveita padrões da Story 4.1 e evita reinventar autenticação, auditoria e validação sensível.
- [x] Story separa catálogo/versionamento de execução determinística de decisão.
- [x] Story mantém segurança, privacidade, multi-tenancy, auditabilidade e explicabilidade como preocupações centrais.
- [x] Story evita nova tecnologia, dependência externa ou motor de regras sem decisão explícita.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 4, Stories 4.2, 4.3, 4.5, 4.7 e 4.8.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-15, AD-16, AD-18.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/autenticacao-autorizacao-oq7.md` — scopes `policy:read` e `policy:write`, RBAC e contexto confiável.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md` — auditoria oficial append-only e falhas críticas.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md` — mascaramento, omissão de dados sensíveis e testes sintéticos.
- `docs/observability.md` — logs estruturados seguros, mascaramento e anti-padrões de telemetria.
- `_bmad-output/implementation-artifacts/4-1-modelo-versionado-de-politica-de-credito.md` — padrões e aprendizados da Story 4.1.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-26 — `CTOS-232` movida para `Em andamento` no Jira antes da implementação.
- 2026-08-26 — Testes RED criados para domínio e aplicação do catálogo de reason codes.
- 2026-08-26 — `uv run ...` não pôde ser usado localmente porque o binário `uv` não existe no PATH desta sessão.
- 2026-08-26 — Suíte completa repetida fora do sandbox; sockets locais passaram, mas `tests/test_local_harness.py::test_dev_script_harness_check_uses_documented_command` falhou por `uv: command not found`.
- 2026-08-26 — Branch `agent/story-4-2-catalogo-reason-codes-fatores-explicaveis` criada a partir de `main` em `5892c2e` após merge do PR #38.
- 2026-08-26 — `CTOS-40` movida para `Em andamento` no Jira antes do detalhamento, conforme fluxo acordado de branch/card no início.
- 2026-08-26 — `bmad-create-story` executado para detalhar Story 4.2 antes da implementação.
- 2026-08-27 — Revisão adversarial Step 02 concluída com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 7 achados classificados como patch.
- 2026-08-27 — `CTOS-232`, `CTOS-233`, `CTOS-234`, `CTOS-235`, `CTOS-236`, `CTOS-237` e `CTOS-238` movidas para `Concluído`; `CTOS-40` movida para `GQ`.

### Completion Notes List

- 2026-08-26 — Story 4.2 criada com status `ready-for-dev`, escopo limitado ao catálogo versionado de reason codes e fatores explicáveis.
- 2026-08-26 — Implementados value objects/enums seguros para reason codes, fatores explicáveis, status, severidade, audiência e changelog de catálogo.
- 2026-08-26 — Implementado agregado `ReasonCodeCatalog` com versionamento, imutabilidade de snapshots não-draft, compatibilidade semântica e criação de nova versão para mudança incompatível.
- 2026-08-26 — `PolicyRule` passou a exigir `reason_code_refs` não vazios e sem duplicidade.
- 2026-08-26 — Implementada validação de políticas contra catálogo versionado por tenant, produto, status ativo e outcome compatível.
- 2026-08-26 — Implementados porta e adapter in-memory de catálogo com isolamento por tenant e controle otimista de revisão.
- 2026-08-26 — Implementados casos de uso de catálogo no `DecisionApplicationService` com contexto confiável, scopes existentes, logs com payload omitido e auditoria minimizada.
- 2026-08-26 — Adicionados testes unitários de domínio/aplicação e atualizados testes de política para a obrigatoriedade de reason codes.
- 2026-08-26 — Validações verdes: `.venv/bin/python -m ruff format .`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pyright`, `.venv/bin/python -m pytest services/decision/tests/unit -q`.
- 2026-08-26 — Suíte completa: `.venv/bin/python -m pytest -q` passou 440 testes fora do sandbox e falhou 1 teste ambiental por ausência local do binário `uv`.
- 2026-08-27 — Aplicados patches da revisão adversarial: proveniência obrigatória do catálogo em políticas, validação log-safe de `change_summary`, fingerprint governado ampliado, incompatibilidade por status/audiência/produto, versionamento atômico e rollback condicional.
- 2026-08-27 — Validações verdes após review: `.venv/bin/python -m pytest services/decision/tests/unit -q` (33 testes), `.venv/bin/python -m ruff format --check .`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pyright` e `.venv/bin/python -m pytest -q --ignore=tests/test_local_harness.py` (437 testes).
- 2026-08-27 — Suíte completa local: `.venv/bin/python -m pytest -q` passou 441 testes e falhou 3 testes do harness por limitação ambiental desta sessão (`Operation not permitted` ao abrir sockets e `uv` indisponível no `PATH`).

### File List

- `_bmad-output/implementation-artifacts/4-2-catalogo-de-reason-codes-e-fatores-explicaveis.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/adapters/persistence/__init__.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_reason_code_catalog_repository.py`
- `services/decision/src/creditos_decision/application/ports/__init__.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
- `services/decision/src/creditos_decision/application/ports/reason_code_catalog_repository.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/domain/entities/__init__.py`
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py`
- `services/decision/src/creditos_decision/domain/errors.py`
- `services/decision/src/creditos_decision/domain/value_objects/__init__.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy.py`
- `services/decision/src/creditos_decision/domain/value_objects/reason_codes.py`
- `services/decision/tests/unit/test_credit_policy_model.py`
- `services/decision/tests/unit/test_credit_policy_service.py`
- `services/decision/tests/unit/test_reason_code_catalog_model.py`
- `services/decision/tests/unit/test_reason_code_catalog_service.py`

### Change Log

- 2026-08-26 — Implementado catálogo versionado de reason codes e fatores explicáveis, integrado à validação de políticas em draft e preparado para code review.
- 2026-08-27 — Patches da revisão adversarial aplicados e Story 4.2 marcada como `done` no BMAD; Jira permanece em `GQ` até PR/merge.
