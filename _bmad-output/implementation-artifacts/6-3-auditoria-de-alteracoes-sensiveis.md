---
jira_issue: CTOS-55
branch: agent/story-6-3-sensitive-change-audit
baseline_commit: aea5a97
created_at: 2026-09-16
subtasks:
  - CTOS-336
  - CTOS-337
  - CTOS-338
  - CTOS-339
  - CTOS-340
  - CTOS-341
  - CTOS-342
  - CTOS-343
  - CTOS-344
---

# Story 6.3: Auditoria de Alterações Sensíveis

Status: done

## Story

Como operador de governança,
quero que alterações sensíveis gerem eventos obrigatórios de auditoria,
para que mudanças críticas não ocorram silenciosamente.

## Acceptance Criteria

1. **Alterações sensíveis geram auditoria oficial**
   - **Given** alteração em política, modelo, agente de IA, permissão, exportação ou acesso a dado sensível
   - **When** a operação é executada
   - **Then** gera evento de auditoria oficial com ator, recurso, ação, antes/depois permitido, justificativa quando aplicável, correlation ID, trace ID e contexto de tenant
   - **And** o evento é persistido pelo `Audit & Evidence` como trilha append-only, não por log operacional, trace ou evento de mensageria.

2. **Falha crítica não é omitida**
   - **Given** uma alteração sensível que exige auditoria crítica
   - **When** o registro oficial não puder ser gravado
   - **Then** a operação falha antes do commit ou fica em estado técnico controlado
   - **And** a falha é registrada de forma segura para operação, sem expor payload bruto ou dados sensíveis.

3. **Manutenção e bypass exigem segregação**
   - **Given** uma tentativa administrativa de manutenção, bypass ou break-glass
   - **When** a ação ocorre
   - **Then** ela também gera auditoria oficial
   - **And** exige permissão segregada, distinta das permissões operacionais comuns.

4. **Antes/depois é minimizado e permitido**
   - **Given** uma alteração com estado anterior e resultante
   - **When** o evento de auditoria é montado
   - **Then** registra apenas versões, revisões, fingerprints, contagens, IDs técnicos, campos governados e resumo seguro
   - **And** não persiste snapshots completos, payloads brutos, prompts brutos, dados financeiros detalhados, CPF/CNPJ/e-mail completos, tokens ou segredos.

5. **Cobertura de MVP é explícita**
   - **Given** que nem todos os bounded contexts finais existem no repositório
   - **When** a story for implementada
   - **Then** cobre de forma executável os serviços já materializados que alteram política/catálogo/simulação e configuração de agente de IA
   - **And** registra gaps rastreáveis para permissão, exportação/WORM e acesso a dados sensíveis quando não houver serviço/fluxo materializado.

6. **Contexto confiável é a fonte de autoridade**
   - **Given** um comando de alteração sensível
   - **When** o adapter publicar auditoria
   - **Then** `tenant_id`, `tenant_isolation_tier`, ator, scopes, correlation ID, trace ID e request ID vêm de `PropagatedContext`/`ObservabilityContext`
   - **And** payload de negócio não pode sobrescrever identidades autoritativas do evento.

7. **Escopo controlado**
   - **Given** que esta story prepara auditoria de alterações sensíveis
   - **When** o dev agent implementar
   - **Then** não cria gRPC real, NATS real, outbox real, SQLAlchemy/Alembic real, WORM/S3 Object Lock, hash encadeado, endpoints públicos, dashboards ou IAM/cloud real
   - **And** deixa interfaces e documentação para evolução nas histórias/ADRs apropriadas.

8. **Gates locais de qualidade e regressão**
   - **Given** a suíte local do repositório
   - **When** a Story 6.3 for concluída
   - **Then** testes focados de `Decision`, `Automated Review` e `Audit & Evidence` passam
   - **And** Ruff format/check, Pyright e `uv lock --check` permanecem verdes ou qualquer limitação ambiental preexistente é registrada sem mascarar falha funcional.

## Tasks / Subtasks

- [x] CTOS-336 — Definir contrato canônico de auditoria de alterações sensíveis (AC: 1, 2, 3, 4, 5)
  - [x] Modelar intent/mapper para alteração sensível sem criar trilha paralela ao `Audit & Evidence`.
  - [x] Padronizar `aggregate_type`, `aggregate_id`, `event_type`, `action`, `resource_type`, `resource_id`, `result`, `safe_details` e `OperationalEvidenceReference`.
  - [x] Garantir que o contrato aceite justificativa segura quando aplicável e rejeite `payload`, snapshots livres, PII, tokens e segredos.
  - [x] Documentar o mapeamento para política, catálogo, simulação, agente de IA, manutenção/bypass e gaps futuros.

- [x] CTOS-337 — Expandir allowlist segura para metadados de mudança (AC: 1, 4, 5, 8)
  - [x] Adicionar apenas chaves canônicas necessárias a `safe_details`, como `resource_id`, `resource_type`, `change_type`, `change_reason`, `previous_revision`, `resulting_revision`, `previous_version_id`, `resulting_version_id`, `field_count`, `changed_fields`, `approval_reference`, `maintenance_reason`, `bypass_reason`, `permission_scope`, `export_reference`, `access_purpose` e refs técnicas equivalentes.
  - [x] Preservar limite de cardinalidade, limite de tamanho, strings apenas, mascaramento, omissão e rejeição de chaves desconhecidas.
  - [x] Testar dados sintéticos sensíveis dentro de campos allowlistados e em chaves proibidas.

- [x] CTOS-338 — Integrar auditoria oficial para políticas e catálogos do `Decision` (AC: 1, 2, 4, 6, 8)
  - [x] Reusar `CreditPolicyAuditIntent`, `ReasonCodeCatalogAuditIntent` e `PolicySimulationAuditIntent` em adapter oficial para `Audit & Evidence`.
  - [x] Mapear criação/alteração/publicação de política, catálogo de reason codes e simulação governada para eventos oficiais com metadados minimizados.
  - [x] Preservar `before_commit`/rollback já usado nas operações governadas e não quebrar o adapter de auditoria de decisões da Story 6.2.
  - [x] Garantir que `safe_details` não sobrescreva tenant, ator, recurso ou versões autoritativas.

- [x] CTOS-339 — Integrar auditoria oficial para configuração do agente de IA (AC: 1, 2, 4, 6, 8)
  - [x] Reusar `AutomatedReviewAuditIntent` e criar adapter oficial para `Audit & Evidence`.
  - [x] Cobrir criação, atualização, nova versão e publicação de configuração do agente de revisão automatizada.
  - [x] Registrar versões/revisões, prompt/model refs, fingerprint, status, escopo e justificativa sem prompt bruto, output bruto ou dados sensíveis.
  - [x] Garantir falha crítica controlada antes do commit nas operações já protegidas por `before_commit`.

- [x] CTOS-340 — Registrar cobertura controlada para permissões, exportações e acesso sensível (AC: 1, 3, 5, 7)
  - [x] Verificar se existem fluxos materializados de alteração de permissões, exportação/WORM ou acesso a dados sensíveis além de leitura operacional já criada.
  - [x] Se não houver fluxo real, não inventar serviço nem endpoint; registrar deferred work com critérios claros de implementação futura.
  - [x] Quando houver hook viável sem ampliar escopo, definir porta/intent mínima e testes de contrato sem execução operacional real.

- [x] CTOS-341 — Exigir permissão segregada para manutenção e bypass (AC: 3, 6, 8)
  - [x] Definir escopo/role segregado para manutenção ou break-glass em adapters/casos de uso da story.
  - [x] Garantir que permissões operacionais comuns não autorizem bypass.
  - [x] Auditar tentativas aceitas, bloqueadas ou rejeitadas com resultado explícito e motivo seguro.

- [x] CTOS-342 — Testar falhas críticas, rollback e ausência de vazamento (AC: 1, 2, 3, 4, 5, 8)
  - [x] Cobrir sucesso e falha do publisher oficial em `Decision`.
  - [x] Cobrir sucesso e falha do publisher oficial em `Automated Review`.
  - [x] Cobrir tenant divergente, ator ausente, scope ausente, tentativa de sobrescrita de campos autoritativos e tentativa de bypass sem permissão segregada.
  - [x] Validar que logs, eventos e erros não expõem CPF/CNPJ/e-mail, tokens, secrets, prompt bruto, payload bruto ou snapshots completos.

- [x] CTOS-343 — Atualizar documentação operacional e limites de escopo (AC: 5, 6, 7, 8)
  - [x] Atualizar READMEs dos serviços alterados com responsabilidades, limites, eventos auditáveis e fora de escopo.
  - [x] Atualizar `deferred-work.md` com gaps reais de permissões, exportações, acesso sensível, gRPC real, persistência real, WORM, hash/checkpoints e IaC quando aplicável.
  - [x] Registrar decisões locais tomadas durante a implementação no story file.

- [x] CTOS-344 — Sincronizar BMAD, Jira e validações da Story 6.3 (AC: 8)
  - [x] Atualizar subtarefas Jira conforme avanço da implementação.
  - [x] Atualizar `sprint-status.yaml` para `in-progress`, `review` e `done` nos momentos corretos.
  - [x] Registrar comandos de teste/lint/typecheck/lockfile executados e qualquer limitação ambiental.

### Review Findings

- [x] [Review][Patch] Auditoria de nova versão do Automated Review não está vinculada ao commit do repositório [`services/automated-review/src/creditos_automated_review/application/service.py:445`]
- [x] [Review][Patch] Intents de auditoria sensível aceitam contexto confiável fabricado por defaults [`services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py:16`]
- [x] [Review][Patch] Publisher composto pode rotear alterações sensíveis para fallback não oficial quando não configurado [`services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py:29`]
- [x] [Review][Patch] Eventos bloqueados ou falhas não técnicas podem ser mapeados como `accepted` [`services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py:292`]
- [x] [Review][Patch] Validação de `traceparent` aceita formatos W3C inválidos [`services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py:398`]
- [x] [Review][Patch] Adapter de auditoria do Automated Review ignora `occurred_at` da intent [`services/automated-review/src/creditos_automated_review/adapters/external/audit_evidence_publisher.py:72`]
- [x] [Review][Patch] Metadados de antes/depois estão incompletos em alterações de política e catálogo [`services/decision/src/creditos_decision/application/service.py:334`]
- [x] [Review][Patch] Chaves canônicas declaradas para mudança sensível faltam na allowlist de `safe_details` [`services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py:26`]

## Dev Notes

### Escopo desta story

- Esta story transforma auditorias de alterações sensíveis em eventos oficiais do `Audit & Evidence`, começando pelos bounded contexts já materializados: `Decision` e `Automated Review`.
- A Story 6.1 criou a trilha oficial append-only, separada de logs/traces/eventos operacionais.
- A Story 6.2 conectou decisões finais/inconclusivas ao `Audit & Evidence` por adapter in-process e publisher composto.
- A Story 6.3 deve reaproveitar a fundação existente e ampliar cobertura para alterações sensíveis; não deve criar outro serviço de auditoria, outro repositório oficial, outro formato de trilha ou persistência real fora do padrão já aprovado.

### Contexto funcional consolidado

- Epic 6 exige que decisões, alterações sensíveis, requisições e integrações sejam rastreáveis com auditoria oficial, logs estruturados, mascaramento e integridade verificável. [Fonte: `_bmad-output/planning-artifacts/epics.md#Epic 6`]
- Story 6.3 exige auditoria para alteração em política, modelo, agente de IA, permissão, exportação e acesso a dado sensível, com ator, recurso, antes/depois permitido, justificativa quando aplicável e correlation ID. [Fonte: `_bmad-output/planning-artifacts/epics.md#Story 6.3`]
- FR-20 exige que eventos de alterações sensíveis não sejam omitidos silenciosamente e que falha crítica bloqueie ou marque operação em estado controlado. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-20`]
- NFR-9 proíbe CPF/CNPJ completos, dados bancários, cartões, tokens, senhas, biometria, documentos, renda detalhada, credenciais ou payloads sensíveis completos em logs, traces, dashboards e respostas operacionais. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFR-9`]
- NFR-11 exige classificação, finalidade, base legal, owner, retenção, descarte e política de mascaramento antes de produção para dados pessoais/sensíveis persistidos. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFR-11`]

### Padrões arquiteturais obrigatórios

- Backend segue DDD + arquitetura hexagonal; domínio não depende de frameworks, banco, gRPC, NATS, OpenTelemetry, provedores externos ou Kubernetes. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- `Audit & Evidence` é dono da trilha oficial; logs, traces, métricas e eventos de mensageria não substituem auditoria. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`]
- Segurança é `deny-by-default`; ações sensíveis exigem permissão explícita, auditoria e mascaramento. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-6`]
- Comunicação service-to-service de produção deve evoluir para identidade de workload, mTLS e autorização local; nesta story, adapter in-process/test double é aceitável para provar contrato sem gRPC real. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-17`]
- Dados sensíveis devem ser minimizados, mascarados, omitidos, tokenizados ou hasheados; payload sensível bruto não entra na auditoria por padrão. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-9`]

### Arquivos existentes que devem ser lidos antes de alterar

- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
  - Estado atual: `AuditEvidenceApplicationService.register_event` exige `audit:write`, valida `PropagatedContext`/`ObservabilityContext`, cria `AuditEvent`, faz append e emite log operacional seguro.
  - O que mudar: reutilizar como destino oficial; evitar caminho alternativo que pule validação de tenant, ator, scopes e rastreabilidade.
  - Preservar: leitura oficial auto-audita `audit_event.read`, logs usam payload omitido/mascarado e a porta principal continua append-only.

- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
  - Estado atual: `safe_details` usa allowlist fechada e bloqueia padrões sensíveis, documentos brasileiros, e-mail, tokens, segredos, payload e chaves desconhecidas.
  - O que mudar: incluir apenas chaves canônicas necessárias para mudanças sensíveis.
  - Preservar: `_MAX_SAFE_DETAILS`, `_MAX_SAFE_DETAIL_VALUE_LENGTH`, strings apenas, ausência de metadados livres e rejeição/omissão de dados sensíveis.

- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_event.py`
  - Estado atual: `AuditEvent` valida campos oficiais, imutabilidade e impede evento puramente operacional.
  - O que mudar: somente se o contrato de alteração sensível exigir validação genérica adicional; preferir resolver via mapper/adapter.
  - Preservar: logs/traces/messages/metrics não podem substituir evento oficial.

- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
  - Estado atual: define `CreditPolicyAuditIntent`, `ReasonCodeCatalogAuditIntent`, `PolicySimulationAuditIntent`, `CreditDecisionAuditIntent` e protocolo `CreditPolicyAuditPublisher`.
  - O que mudar: mapear intents de política/catálogo/simulação para `Audit & Evidence`; adicionar campos mínimos apenas se necessário.
  - Preservar: `CreditDecisionAuditIntent` e o roteamento da Story 6.2 não podem regredir.

- `services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py`
  - Estado atual: `CompositeDecisionAuditPublisher` encaminha `CreditDecisionAuditIntent` para `AuditEvidenceDecisionAuditPublisher` e demais intents para fallback legado.
  - O que mudar: adicionar publisher oficial para alterações de política/catálogo/simulação e ajustar o composite para rotear todos os intents sensíveis suportados.
  - Preservar: validação de campos autoritativos, `event_id` compacto por ocorrência, `source_kind`, trace ref e proteção contra divergência em `safe_details`.

- `services/decision/src/creditos_decision/application/service.py`
  - Estado atual: operações de política/catálogo/simulação já publicam intents por `before_commit`/audit publisher.
  - O que mudar: somente se faltarem campos necessários ao contrato oficial.
  - Preservar: sem dependência do domínio de `Audit & Evidence` dentro do domínio de `Decision`; sem alterar semântica de decisão/política fora da auditoria.

- `services/automated-review/src/creditos_automated_review/application/ports/audit_publisher.py`
  - Estado atual: `AutomatedReviewAuditIntent` cobre configuração versionada do agente com event type, tenant, ator, config/version, correlation ID, occurred_at, change summary, revisions e `safe_details`.
  - O que mudar: criar adapter oficial para `Audit & Evidence`; adicionar request/trace/tier somente se necessário e de forma compatível.
  - Preservar: intent leve, sem prompt bruto/output bruto/payload bruto.

- `services/automated-review/src/creditos_automated_review/application/service.py`
  - Estado atual: `create_config`, `update_config`, `publish_config` e `create_config_version` usam audit publisher antes do commit em fluxos de configuração.
  - O que mudar: garantir que o publisher oficial receba contexto suficiente para auditoria crítica.
  - Preservar: scopes `automated_review:write` e `automated_review:publish`, contexto confiável e logs seguros.

- `services/identity-tenant/src/creditos_identity_tenant/application/use_cases/authorize_operation.py`
  - Estado atual: valida autorização por scopes/roles para operações sensíveis, mas não há fluxo materializado de alteração de permissões/roles.
  - O que mudar: não inventar CRUD de permissões nesta story; registrar gap se não houver operação real.
  - Preservar: Identity & Tenant continua dono de tenants, roles, scopes, claims e contexto confiável.

### Contrato de mapeamento esperado

- Para alterações de política do `Decision`:
  - `aggregate_type`: `credit_policy`
  - `aggregate_id`: `policy_id`
  - `event_type`: usar o tipo já emitido, por exemplo `credit_policy.created`, `credit_policy.updated` ou `credit_policy.published`
  - `action`: `create`, `update`, `publish`, `simulate` ou `validate`
  - `resource_type`: `credit_policy`
  - `resource_id`: `policy_version_id` quando a versão for o recurso alterado; caso contrário `policy_id`
  - `source_service`: `decision`
  - `source_kind`: `grpc` para adapter interno/testável de serviço; documentar se usar `system`
  - `result`: `accepted` para sucesso; `blocked`, `rejected` ou `technical_failure` para falha controlada
  - `safe_details`: `policy_id`, `policy_version_id`, `policy_revision`, `status`, `product_type`, `channel`, `operation`, `change_type`, `change_reason`, `previous_revision`, `resulting_revision`, `changed_fields`, `approval_reference` quando existir.

- Para catálogo de reason codes:
  - `aggregate_type`: `reason_code_catalog`
  - `aggregate_id`: `catalog_id`
  - `resource_type`: `reason_code_catalog`
  - `resource_id`: `catalog_version_id`
  - `safe_details`: ids/versionamento, contagens de reason codes/fatores, campos alterados e justificativa segura; nunca descrições livres com PII.

- Para configuração de agente de IA:
  - `aggregate_type`: `review_agent_config`
  - `aggregate_id`: `review_agent_config_id`
  - `resource_type`: `review_agent_config`
  - `resource_id`: `review_agent_config_version_id`
  - `source_service`: `automated_review`
  - `safe_details`: `review_agent_config_id`, `review_agent_config_version_id`, `agent_version`, `prompt_version`, `prompt_fingerprint`, `model_ref`, `model_version`, `provider_ref`, `previous_revision`, `resulting_revision`, `approval_reference`, `change_reason`, `field_count`, `changed_fields`, `fallback_action`, `status`.

- Para manutenção/bypass:
  - `event_type`: `governance.maintenance_attempted`, `governance.maintenance_accepted`, `governance.bypass_attempted`, `governance.bypass_blocked` ou nomenclatura equivalente, desde que fechada e testada.
  - `action`: `maintain` ou `bypass`.
  - `result`: `accepted`, `blocked`, `rejected` ou `technical_failure`.
  - Permissão segregada sugerida: `governance:maintenance` para manutenção controlada e `governance:break_glass` para bypass/break-glass. Se optar por outro nome, documentar justificativa no story file durante a implementação.

### Previous Story Intelligence

- Story 6.1 criou `AuditEvent`, `OperationalEvidenceReference`, `AuditEvidenceApplicationService`, `AuditEventRepository` e adapter in-memory append-only.
- Story 6.1 também endureceu `safe_details` com allowlist fechada, mascaramento/omissão e bloqueio de IDs sensíveis.
- Story 6.2 criou `AuditEvidenceDecisionAuditPublisher`, `CompositeDecisionAuditPublisher`, mapeamento oficial de `CreditDecisionAuditIntent` e proteção contra sobrescrita de identidades autoritativas.
- Story 6.2 evidenciou que alterações em dependências workspace podem exigir `uv lock`; conferir `uv lock --check` antes do PR.
- Falhas de auditoria crítica em decisão devem bloquear visibilidade da operação antes do commit. A mesma lógica deve ser aplicada às alterações sensíveis quando já houver `before_commit`.

### Git Intelligence

- Baseline desta story: `aea5a97`, merge do PR #55 da Story 6.2.
- Padrão recente: criar story, sincronizar subtarefas Jira, criar branch no início do `bmad-dev-story`, mover card para `Em andamento`, implementar, rodar `bmad-code-review`, corrigir achados, então `commit/push/draft PR`.
- Commits devem usar `Andre Tachian <altachian@gmail.com>`.

### Pesquisa técnica recente

- Nenhuma tecnologia nova deve ser selecionada nesta story.
- A stack aprovada permanece Python 3.13, uv workspace, pytest, Ruff, Pyright, Pydantic v2 quando houver borda, gRPC para integração real futura e OpenTelemetry para observabilidade.
- Como a story é de domínio/aplicação/adapters in-process já existentes, não há necessidade de pesquisa externa de versão para implementar; qualquer introdução de biblioteca nova deve ser recusada ou justificada com alternativa, consequência e atualização de ADR.

### Testes e validações esperadas

- Testes focados esperados:
  - `.venv/bin/pytest services/audit-evidence/tests/unit/test_audit_event_model.py -q`
  - `.venv/bin/pytest services/decision/tests/unit/test_epic4_decision_governance_gates.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py -q`
  - `.venv/bin/pytest services/automated-review/tests/unit/test_review_agent_configuration.py -q`
  - testes novos de adapters oficiais de auditoria de alterações sensíveis em `Decision` e `Automated Review`.
- Gates esperados:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
  - `uv lock --check` quando dependências/workspace mudarem; se o lock precisar mudar, executar `uv lock` antes do PR.
- Se a suíte completa falhar por limitação ambiental conhecida do harness local, registrar o comando focado bem-sucedido e a limitação explicitamente.

### Fora do escopo explícito

- Criar CRUD real de permissões, roles, chaves, IAM, break-glass cloud ou endpoint administrativo novo.
- Implementar exportação WORM/S3 Object Lock, S3 real, legal hold, bypass de retention ou IaC.
- Implementar hash encadeado, checkpoints, assinatura, verificação periódica ou canonicalização final de integridade.
- Implementar gRPC real, protobuf, NATS, outbox transacional, workers, retry/DLQ ou persistência SQLAlchemy/Alembic real.
- Implementar dashboard, Reporting Service, consulta customer-facing de auditoria ou exportação operacional.
- Persistir prompt bruto, output bruto, payload de fornecedor, snapshots completos de política/configuração ou dados sensíveis reais.

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py -q`
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py services/decision/tests/unit/test_credit_policy_service.py services/decision/tests/unit/test_reason_code_catalog_service.py services/decision/tests/unit/test_policy_simulation_service.py services/automated-review/tests/unit/test_review_agent_configuration.py -q`
- `.venv/bin/pytest services/audit-evidence/tests/unit/test_audit_event_model.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py services/decision/tests/unit/test_credit_policy_service.py services/decision/tests/unit/test_reason_code_catalog_service.py services/decision/tests/unit/test_policy_simulation_service.py services/automated-review/tests/unit/test_review_agent_configuration.py -q`
- `.venv/bin/ruff check services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py services/automated-review/src/creditos_automated_review/adapters/external/audit_evidence_publisher.py services/automated-review/src/creditos_automated_review/application/ports/audit_publisher.py services/automated-review/src/creditos_automated_review/application/service.py services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py services/decision/src/creditos_decision/application/service.py services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
- `.venv/bin/ruff format services/decision/src/creditos_decision/application/service.py`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/pyright`
- `.venv/bin/pytest services -q`
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/decision/tests/unit/test_reason_code_catalog_service.py services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py services/automated-review/tests/unit/test_review_agent_configuration.py services/audit-evidence/tests/unit/test_audit_event_model.py -q`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/pyright`
- `.venv/bin/pytest services -q`
- `uv lock --check` não executado localmente: `uv` não está instalado no shell e `.venv/bin/python -m uv` retornou `No module named uv`.

### Completion Notes List

- Story criada por `bmad-create-story`, subtarefas Jira CTOS-336 a CTOS-344 sincronizadas e status marcado como `ready-for-dev`.
- Branch `agent/story-6-3-sensitive-change-audit` criada no início do desenvolvimento e `CTOS-55`/`CTOS-336` movidos para `Em andamento`.
- `AuditEvidenceDecisionSensitiveChangeAuditPublisher` adicionado para publicar alterações de política, catálogo e simulação como eventos oficiais do `Audit & Evidence`.
- `AuditEvidenceAutomatedReviewAuditPublisher` adicionado para publicar alterações de configuração do agente de IA consultivo como eventos oficiais.
- Intents de `Decision` e `Automated Review` passaram a carregar tier de isolamento, request ID e traceparent derivados do contexto confiável.
- Allowlist de `safe_details` expandida apenas com metadados seguros de alteração sensível, mantendo bloqueio de PII, payload bruto, prompt/output bruto, tokens e segredos.
- Fluxos não materializados de permissão, manutenção/bypass, exportação/WORM, acesso sensível real, transporte/persistência reais, hash/checkpoints e IaC registrados como deferred work.

### File List

- `_bmad-output/implementation-artifacts/6-3-auditoria-de-alteracoes-sensiveis.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/audit-evidence/README.md`
- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
- `services/automated-review/README.md`
- `services/automated-review/pyproject.toml`
- `services/automated-review/src/creditos_automated_review/adapters/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/external/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/external/audit_evidence_publisher.py`
- `services/automated-review/src/creditos_automated_review/application/ports/audit_publisher.py`
- `services/automated-review/src/creditos_automated_review/application/service.py`
- `services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py`
- `services/automated-review/tests/unit/test_review_agent_configuration.py`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/adapters/external/__init__.py`
- `services/decision/src/creditos_decision/adapters/external/audit_evidence_publisher.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py`
- `services/decision/tests/unit/test_credit_policy_publication_service.py`
- `services/decision/tests/unit/test_credit_policy_service.py`
- `services/decision/tests/unit/test_reason_code_catalog_service.py`
- `uv.lock`

### Change Log

- 2026-09-16 — Story criada por `bmad-create-story` e marcada como `ready-for-dev`.
- 2026-09-17 — Implementada auditoria oficial de alterações sensíveis para `Decision` e `Automated Review`, com documentação, deferred work e validações focadas.
- 2026-09-17 — `bmad-code-review` executado; 8 achados de patch corrigidos e validados com Ruff, Pyright e regressão completa de serviços.
