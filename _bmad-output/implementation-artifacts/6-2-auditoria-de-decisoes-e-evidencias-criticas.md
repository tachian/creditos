---
jira_issue: CTOS-54
branch: agent/story-6-2-decision-audit-evidence
baseline_commit: e771b0c
created_at: 2026-09-16
subtasks:
  - CTOS-330
  - CTOS-331
  - CTOS-332
  - CTOS-333
  - CTOS-334
  - CTOS-335
---

# Story 6.2: Auditoria de Decisões e Evidências Críticas

Status: done

## Story

Como auditor ou cliente autorizado,
quero que decisões tenham evidências mínimas e versões aplicáveis,
para que seja possível provar como cada decisão foi tomada.

## Acceptance Criteria

1. **Auditoria oficial de decisão final ou inconclusiva**
   - **Given** uma decisão final ou inconclusiva
   - **When** o `Decision` registra auditoria
   - **Then** inclui tenant, proposta, solicitante, fontes/referências, política, versão, regras, resultado, justificativas e correlation ID
   - **And** preserva dados mínimos suficientes sem violar minimização.

2. **Falha crítica de auditoria bloqueia publicação da decisão**
   - **Given** falha na gravação de auditoria ou evidência crítica
   - **When** o sistema tenta publicar decisão final
   - **Then** a publicação é bloqueada ou retorna estado técnico controlado
   - **And** a falha é registrada para operação.

3. **Contrato anti-corrupção entre `Decision` e `Audit & Evidence`**
   - **Given** que `Decision` já emite `CreditDecisionAuditIntent`
   - **When** a intent for entregue ao `Audit & Evidence`
   - **Then** ela é convertida para `RegisterAuditEventCommand`/`AuditEvent` oficial sem importar domínio de `Audit & Evidence` dentro do domínio de `Decision`
   - **And** a integração real por gRPC permanece preparada, mas não obrigatória nesta story.

4. **Evidências críticas minimizadas**
   - **Given** reason codes, regras acionadas, fatores, policy/catalog refs, fingerprint e integration refs
   - **When** forem auditados
   - **Then** ficam como metadados seguros, contagens ou referências técnicas
   - **And** payload bruto de proposta, renda detalhada, CPF, CNPJ, e-mail, fornecedor, IA, token ou segredo não é persistido.

5. **Regressão de atomicidade decisória**
   - **Given** uma falha no registro oficial de auditoria crítica de decisão
   - **When** a execução de decisão falhar
   - **Then** a decisão não fica visível por `decision_id` ou `proposal_id`
   - **And** há log operacional seguro com correlation ID, tenant e código técnico sem payload bruto.

## Tasks / Subtasks

- [x] CTOS-330 — Definir envelope oficial de auditoria de decisão (AC: 1, 3, 4)
  - [x] Mapear `CreditDecisionAuditIntent` para `aggregate_type`, `aggregate_id`, `event_type`, `action`, `resource_type`, `resource_id`, `source_service`, `source_kind`, `result`, `safe_details` e `operational_evidence_refs`.
  - [x] Padronizar `event_type` produtivo como `credit_decision.completed` e rejeições técnicas como `credit_decision.rejected` ou equivalente já usado.
  - [x] Manter `tenant_id`, ator, `correlation_id`, `trace_id` e `request_id` exclusivamente do `PropagatedContext` confiável.

- [x] CTOS-331 — Implementar adapter anti-corrupção `Decision` → `Audit & Evidence` (AC: 1, 2, 3)
  - [x] Criar adapter em camada de infraestrutura/aplicação, não no domínio, para converter intents atuais em comandos de auditoria oficial.
  - [x] Reusar `AuditEvidenceApplicationService.register_event` e `RegisterAuditEventCommand` nos testes/in-process; não criar gRPC real nesta story.
  - [x] Preservar a porta atual de auditoria do `Decision` ou evoluí-la minimamente sem quebrar testes existentes.

- [x] CTOS-332 — Completar metadados e referências críticas minimizadas (AC: 1, 4)
  - [x] Incluir política, versão, revisão, catálogo de reason codes, regras acionadas, contagens, outcome/status, fingerprint decisório e refs de integração em formato seguro.
  - [x] Usar `OperationalEvidenceReference` apenas para referências técnicas a log/trace/message/metric; não transformar log em auditoria oficial.
  - [x] Atualizar a allowlist de `safe_details` do `Audit & Evidence` somente com chaves canônicas necessárias, mantendo rejeição de chaves desconhecidas.

- [x] CTOS-333 — Endurecer falha crítica de auditoria de decisão (AC: 2, 5)
  - [x] Garantir que falha de append oficial antes do commit impede persistência/visibilidade da decisão.
  - [x] Converter falha crítica em erro técnico controlado com código estável, por exemplo `credit_decision_audit_write_failed`, sem vazar detalhe interno sensível.
  - [x] Registrar log operacional seguro de falha com `status="rejected"` ou `technical_failure`, payload omitido e metadados mínimos.

- [x] CTOS-334 — Criar testes de integração unitária entre bounded contexts (AC: 1-5)
  - [x] Testar decisão aprovada auditada como `AuditEvent` oficial com tenant, proposta, decisão, política, versão, reason codes/regras/fingerprint e rastreabilidade.
  - [x] Testar decisão inconclusiva (`request_more_data`/`unable_to_decide`) com justificativas equivalentes e lacunas minimizadas.
  - [x] Testar falha do `Audit & Evidence` bloqueando visibilidade por `decision_id` e `proposal_id`.
  - [x] Testar que safe details e logs não contêm CPF/CNPJ/e-mail, renda detalhada, payload bruto, token ou segredo.

- [x] CTOS-335 — Atualizar documentação e rastreabilidade BMAD/Jira (AC: 1-5)
  - [x] Atualizar `services/decision/README.md` e `services/audit-evidence/README.md` com o fluxo `Decision` → auditoria oficial.
  - [x] Atualizar esta story com arquivos alterados, validações executadas, decisões locais e achados do review.
  - [x] Atualizar `sprint-status.yaml` conforme avanço.
  - [x] Criar/sincronizar subtarefas Jira antes de codificar e mover cards conforme execução.

### Review Findings

- [x] [Review][Decision] Definir composição do publisher oficial sem quebrar auditorias existentes — Resolvido com `CompositeDecisionAuditPublisher`, roteando `CreditDecisionAuditIntent` para `Audit & Evidence` e delegando demais intents ao publisher legado.
- [x] [Review][Patch] Corrigir `uv.lock` para adicionar `creditos-audit-evidence` ao pacote `creditos-decision`, sem self-dependency [`uv.lock:60`]
- [x] [Review][Patch] Gerar `event_id` compacto e único por ocorrência para evitar colisão e limite de 128 caracteres [`services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py:83`]
- [x] [Review][Patch] Mapear leitura de explicação bem-sucedida para `accepted`, não `technical_failure` [`services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py:107`]
- [x] [Review][Patch] Reforçar guardrail contra CPF/CNPJ embutido em IDs técnicos [`services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py:248`]
- [x] [Review][Patch] Usar rastreabilidade do `PropagatedContext` confiável na intent oficial de decisão [`services/decision/src/creditos_decision/application/service.py:1720`]
- [x] [Review][Patch] Impedir que `safe_details` sobrescreva identidades autoritativas do evento [`services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py:88`]
- [x] [Review][Patch] Incluir referências técnicas minimizadas de integrações e regras acionadas na auditoria oficial [`services/decision/src/creditos_decision/application/service.py:2240`]

## Dev Notes

### Escopo desta story

- Esta story conecta a execução de decisão produtiva ao `Audit & Evidence Service` como trilha oficial, usando evidências críticas minimizadas e versões aplicáveis.
- A Story 4.5 já implementou decisão determinística e auditoria crítica antes do commit por meio de `CreditDecisionAuditIntent`.
- A Story 6.1 criou a fundação append-only de auditoria oficial com `AuditEvent`, `RegisterAuditEventCommand`, `OperationalEvidenceReference`, `safe_details` allowlistado, `audit:write`/`audit:read` e logs operacionais seguros.
- O objetivo agora é fechar o gap entre a intent de auditoria do `Decision` e o evento oficial do `Audit & Evidence`, sem implementar hash encadeado, WORM, gRPC real ou banco real.

### Contexto funcional consolidado

- Epic 6 exige rastreabilidade de decisões, alterações sensíveis, requisições e integrações com auditoria oficial separada dos logs operacionais. [Fonte: `_bmad-output/planning-artifacts/epics.md#Epic 6`]
- Story 6.2 exige que decisões finais ou inconclusivas incluam tenant, proposta, solicitante, fontes/referências, política, versão, regras, resultado, justificativas e correlation ID. [Fonte: `_bmad-output/planning-artifacts/epics.md#Story 6.2`]
- FR-19 exige auditoria de decisões com tenant, proposta, solicitante, horário, dados usados ou referências, fontes, política, modelo, regras, resultado, justificativas e correlation ID. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-19`]
- FR-20 exige que falha de auditoria crítica não seja omitida silenciosamente e bloqueie decisão final ou gere estado técnico controlado. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-20`]
- OQ-11 definiu trilha principal append-only relacional no MVP e estados técnicos candidatos como `pending_evidence`, `audit_write_failed` e `technical_failure`. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`]

### Padrões arquiteturais obrigatórios

- Backend segue DDD + arquitetura hexagonal; domínio não depende de framework, banco, gRPC, NATS, OpenTelemetry ou outro serviço. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- `Audit & Evidence` é dono da trilha oficial; logs, traces, métricas e eventos de mensageria não substituem auditoria. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`]
- Cross-service deve respeitar ownership exclusivo de dados; usar porta/adapters e preparar evolução para gRPC sem joins ou transações diretas cross-service. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-3`]
- Contexto confiável propaga tenant, sujeito, scopes, correlation ID, trace ID e request ID; payload de negócio não é autoridade de tenant ou ator. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-6`]
- Minimização e mascaramento são obrigatórios; CPF/CNPJ/e-mail visíveis, payload bruto e dados sensíveis detalhados não podem entrar em auditoria/logs por padrão. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-9`]

### Arquivos existentes que devem ser lidos antes de alterar

- `services/decision/src/creditos_decision/application/service.py`
  - Estado atual: `execute_credit_decision` seleciona política publicada, avalia com `evaluate_policy_case`, cria `CreditDecision`, monta explicação e chama `repository.save(decision, before_commit=publish_audit_before_commit)`.
  - O que mudar: preservar o `before_commit` como gate crítico e fazer a intent chegar ao `Audit & Evidence` oficial via adapter/mapper.
  - Preservar: logs com payload omitido, `decision:execute`, `policy:read`, tenant `bridge`, rollback por falha de auditoria e consulta por decisão/proposta.

- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
  - Estado atual: contém `CreditPolicyAuditIntent`, `ReasonCodeCatalogAuditIntent`, `PolicySimulationAuditIntent`, `CreditDecisionAuditIntent` e protocolo `CreditPolicyAuditPublisher`.
  - O que mudar: se necessário, adicionar campos minimizados a `CreditDecisionAuditIntent` ou criar mapper sem quebrar publishers de políticas/simulação/catálogo.
  - Preservar: contrato leve por dataclasses e nenhuma dependência de domínio de outro serviço dentro do domínio de `Decision`.

- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_decision_repository.py`
  - Estado atual: `save` chama `before_commit` antes de tornar decisão visível e rejeita duplicidade por `(tenant_id, decision_id)` e `(tenant_id, proposal_id)`.
  - O que mudar: somente se necessário para reforçar atomicidade ou testes de falha; evitar mudar sem necessidade.
  - Preservar: decisão não visível se auditoria crítica falhar.

- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
  - Estado atual: `register_event` exige `audit:write`, contexto confiável, cria `AuditEvent`, faz append e registra log operacional seguro.
  - O que mudar: reutilizar como destino oficial do adapter; não criar caminho alternativo que ignore validações.
  - Preservar: tenant/ator/rastreabilidade vindos do `PropagatedContext`.

- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
  - Estado atual: `safe_details` tem allowlist fechada mínima (`decision_id`, `event_count`, `execution_id`, `idempotency_key`, `outcome`, `policy_id`, `policy_version`, `proposal_id`, `reason_code`, `schema_version`, `source_event_id`).
  - O que mudar: incluir apenas chaves canônicas necessárias para decisão, como `channel`, `operation`, `product_type`, `policy_version_id`, `policy_revision`, `reason_code_catalog_id`, `reason_code_catalog_version_id`, `reason_code_count`, `reason_code_refs`, `triggered_rule_count`, `triggered_rule_ids`, `factor_count`, `required_data_count`, `required_data_refs`, `validation_issue_count`, `validation_issue_codes`, `fallback_action`, `fingerprint`, `duration_ms`, `status`, `rejection_reason` e refs técnicas aprovadas.
  - Preservar: rejeição de chaves desconhecidas, strings apenas, limite de cardinalidade/tamanho, mascaramento/omissão de PII e padrões sensíveis.

- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_event.py`
  - Estado atual: `AuditEvent` é imutável, valida campos oficiais e permite `OperationalEvidenceReference` apenas como complemento.
  - O que mudar: só se a auditoria de decisão precisar de referência operacional adicional já suportada.
  - Preservar: logs/traces/messages/metrics não podem ser registrados como evento oficial.

### Contrato de mapeamento esperado

- Para `CreditDecisionAuditIntent(event_type="credit_decision.completed")`:
  - `aggregate_type`: `credit_decision`
  - `aggregate_id`: `decision_id`
  - `event_type`: `credit_decision.completed`
  - `action`: `execute`
  - `resource_type`: `credit_decision`
  - `resource_id`: `decision_id`
  - `source_service`: `decision`
  - `source_kind`: `grpc` quando vindo de chamada interna ou `system`/`worker` conforme contexto do adapter; documentar escolha local.
  - `result`: `accepted`
  - `safe_details`: ids técnicos e contagens minimizadas da decisão, incluindo `proposal_id`, política, catálogo, outcome, status, reason codes/regras/fatores como refs ou contagens.

- Para `CreditDecisionAuditIntent(event_type="credit_decision.rejected")`:
  - `aggregate_type`: `credit_decision`
  - `aggregate_id`: `decision_id` quando disponível, senão fallback técnico validado.
  - `action`: `execute` ou `read`, derivado de `operation`.
  - `result`: `rejected`, `blocked` ou `technical_failure` conforme erro.
  - `safe_details`: `operation`, `rejection_reason`, ids técnicos disponíveis e `status`, sem payload ou erro bruto.

- `model` em FR-19 não significa modelo de IA como decisor final nesta story; para decisões determinísticas do MVP, registrar política/catálogo/versionamento e manter qualquer evidência de IA consultiva apenas por referência quando existir.
- Refs de integração devem ser ids técnicos (`integration_result_refs`) e não payloads de provedores.
- Se for necessário representar múltiplas regras/reason codes em `safe_details`, usar strings curtas ordenadas e determinísticas, por exemplo CSV técnico, respeitando limite de 256 caracteres.

### Previous Story Intelligence

- Story 6.1 concluiu `Audit & Evidence Service` com `AuditEvent`, `OperationalEvidenceReference`, `AuditEvidenceApplicationService`, `AuditEventRepository` e adapter in-memory append-only.
- `safe_details` foi endurecido por review: allowlist fechada, mapping imutável, rejeição de chaves colidentes, strings apenas, masking/omissão de padrões sensíveis e detecção de CPF/CNPJ/e-mail.
- Leitura oficial por `get_event` já gera auto-auditoria de leitura/not-found; não duplicar este comportamento em `Decision`.
- Persistência SQLAlchemy/Alembic real, grants `INSERT`-only, hash/checkpoints/WORM e gRPC real continuam fora do escopo imediato, registrados como evolução.
- Testes do PR #54 validaram `.venv/bin/pytest services/audit-evidence/tests -q`, Ruff, Pyright e suíte ampla com limitação ambiental somente no harness local.

### Git Intelligence

- Baseline desta story: `e771b0c`, merge do PR #54 da Story 6.1.
- Padrão recente: criar story, sincronizar subtarefas Jira, criar branch no início do `bmad-dev-story`, mover card para `Em andamento`, implementar, rodar `bmad-code-review`, corrigir achados, então `commit/push/draft PR`.
- Commits devem usar `Andre Tachian <altachian@gmail.com>`.

### Pesquisa técnica recente

- Nenhuma tecnologia nova deve ser selecionada nesta story.
- A stack aprovada permanece Python 3.13, uv workspace, pytest, Ruff e Pyright.
- A integração interna real entre microsserviços deve ser via gRPC, mas esta story pode usar adapter in-process/test double para provar o contrato sem introduzir servidor/cliente gRPC antes do ciclo apropriado.

### Testes e validações esperadas

- Testes focados esperados:
  - `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py services/audit-evidence/tests/unit -q`
  - `.venv/bin/pytest services/decision/tests/unit/test_epic4_decision_governance_gates.py services/audit-evidence/tests/unit -q`
- Gates esperados:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Se o adapter criar dependência cruzada via workspace, rodar também `uv lock --check`; se o lock precisar mudar, executar `uv lock` antes do PR.
- Se a suíte completa falhar por limitação ambiental conhecida do harness local, registrar o comando focado bem-sucedido e a limitação explicitamente.

### Fora do escopo explícito

- gRPC real, servidor/cliente protobuf, service mesh ou deploy de integração entre pods.
- NATS JetStream, outbox transacional, worker real, retry/DLQ ou callbacks/webhooks.
- Persistência relacional real do `Audit & Evidence`, migrations Alembic e grants físicos de banco.
- Hash encadeado, canonicalização final de hash, checkpoints, assinatura, WORM/S3 Object Lock ou IaC.
- Dashboard, Reporting Service, consulta customer-facing de auditoria ou exportação operacional.
- Usar IA, integração externa ou payload de fornecedor como autoridade de decisão final.

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py -q` — RED inicial: falha por adapter inexistente.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py -q` — 3 passed após adapter in-process.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py -q` — 10 passed após evolução da intent de decisão.
- `uv lock` — falhou localmente por `uv: command not found`; lockfile foi atualizado manualmente apenas para dependência workspace local `creditos-audit-evidence`.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/audit-evidence/tests/unit -q` — 51 passed.
- `.venv/bin/ruff check services/decision/tests/unit/test_credit_decision_service.py --fix` — import order corrigido.
- `.venv/bin/ruff check services/decision/src/creditos_decision/application/service.py services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py services/decision/src/creditos_decision/adapters/external services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py && .venv/bin/pyright` — lint e type check verdes.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/decision/tests/unit/test_epic4_decision_governance_gates.py services/audit-evidence/tests/unit -q` — 57 passed.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/pyright` — 291 files formatted, lint e type check verdes.
- `.venv/bin/pytest -q --ignore=tests/test_local_harness.py` — 641 passed.
- `.venv/bin/pytest -q` — 645 passed, 3 failed em `tests/test_local_harness.py` por limitação ambiental conhecida: socket `Operation not permitted` e `uv: command not found`.
- `bmad-code-review` Step 02 — Blind Hunter, Edge Case Hunter e Acceptance Auditor executados; 1 decisão e 7 patches identificados.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/decision/tests/unit/test_credit_decision_service.py services/audit-evidence/tests/unit/test_audit_event_model.py -q` — 42 passed após patches do review.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/decision/tests/unit/test_epic4_decision_governance_gates.py services/audit-evidence/tests/unit -q` — 62 passed após patches do review.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/pyright` — 291 files formatted, lint e type check verdes após patches do review.
- `.venv/bin/pytest -q --ignore=tests/test_local_harness.py` — 646 passed após patches do review.
- `uv lock --check` — não executável no ambiente local porque `uv` não está disponível no `PATH` nem como módulo da `.venv`; `uv.lock` foi corrigido manualmente para remover self-dependency e adicionar `creditos-audit-evidence` a `creditos-decision`.

### Completion Notes List

- Story iniciada na branch `agent/story-6-2-decision-audit-evidence`; Jira `CTOS-54` e `CTOS-330` movidos para `Em andamento` no início.
- `CreditDecisionAuditIntent` passou a transportar `tenant_isolation_tier`, `request_id` e `traceparent` derivados do contexto confiável/observabilidade.
- Criado `AuditEvidenceDecisionAuditPublisher` em adapter externo do `Decision`, convertendo intents de decisão em `RegisterAuditEventCommand` oficial com `AuditEvent` append-only.
- O adapter registra `credit_decision.completed` e `credit_decision.rejected` com agregado/recurso `credit_decision`, `source_service=decision`, `source_kind=grpc`, resultado controlado e `OperationalEvidenceReference` de trace.
- `safe_details` do `Audit & Evidence` foi expandido apenas com chaves canônicas de decisão, mantendo allowlist fechada e bloqueio de chaves sensíveis como `payload`.
- Falha crítica de auditoria durante `execute_credit_decision` agora gera `CreditDecisionAuditWriteError` com código `credit_decision_audit_write_failed` e impede visibilidade por decisão/proposta.
- Ajustada detecção de CPF/CNPJ em IDs técnicos para evitar falsos positivos em identificadores alfanuméricos gerados, preservando bloqueio para documentos puros/formatados.
- Documentação dos serviços `Decision` e `Audit & Evidence` atualizada com responsabilidades, limites e fora de escopo da Story 6.2.
- Review adversarial corrigido com publisher composto/roteador, `event_id` compacto por ocorrência, leitura de explicação como `accepted`, rastreabilidade do `PropagatedContext`, proteção contra sobrescrita de identidades autoritativas e refs minimizadas de integrações/regras.

### File List

- `_bmad-output/implementation-artifacts/6-2-auditoria-de-decisoes-e-evidencias-criticas.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/audit-evidence/README.md`
- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
- `services/audit-evidence/tests/unit/test_audit_event_model.py`
- `services/decision/README.md`
- `services/decision/pyproject.toml`
- `services/decision/src/creditos_decision/adapters/external/__init__.py`
- `services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/domain/errors.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy.py`
- `services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `uv.lock`

### Change Log

- 2026-09-16 — Story criada por `bmad-create-story` e marcada como `ready-for-dev`.
- 2026-09-16 — Implementado adapter oficial de auditoria de decisões, falha controlada de auditoria crítica, testes e documentação; story marcada para review.
- 2026-09-16 — Executado `bmad-code-review`, aplicados patches aprovados e story marcada como `done`.
