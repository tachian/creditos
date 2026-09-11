---
jira_issue: CTOS-50
branch: agent/story-5-4-evidencia-consultiva-vinculada-proposta
baseline_commit: 059fa16
created_at: 2026-09-10
subtasks:
  - CTOS-300
  - CTOS-301
  - CTOS-302
  - CTOS-303
  - CTOS-306
  - CTOS-304
  - CTOS-305
  - CTOS-307
---

# Story 5.4: Evidência Consultiva Vinculada à Proposta

Status: done

## Story

Como analista de risco ou auditor,
quero que o resultado da IA vire evidência consultiva rastreável,
para que a decisão possa explicar lacunas, inconsistências e fatores sugeridos sem tornar IA a fonte da decisão final.

## Acceptance Criteria

1. **Evidência consultiva rastreável**
   - **Given** uma execução consultiva válida do `Automated Review Service`
   - **When** o resultado validado é registrado
   - **Then** cria uma evidência consultiva vinculada a `tenant_id`, `proposal_id`, `execution_id`, `correlation_id`, `trace_id` quando disponível e timestamp com timezone
   - **And** classifica explicitamente a evidência como `consultative`.

2. **Proveniência versionada de agente/modelo/prompt**
   - **Given** uma evidência consultiva criada a partir de uma revisão automatizada
   - **When** a evidência é persistida, logada ou auditada
   - **Then** preserva `review_agent_config_id`, `review_agent_config_version_id`, `agent_version`, `prompt_fingerprint`, `minimization_policy_ref` e referências seguras de modelo/provedor quando existirem
   - **And** não persiste prompt bruto, output bruto, payload bruto, entrada minimizada com valores ou dados sensíveis.

3. **Conteúdo consultivo governado**
   - **Given** uma saída validada com itens `missing_data`, `inconsistency`, `explainability_factor` ou `limitation`
   - **When** a evidência é construída
   - **Then** registra apenas referências técnicas, tipo, severidade, `reason_ref`, confiança opcional e `evidence_refs` já validados
   - **And** mantém lacunas, inconsistências, fatores sugeridos e limitações separados por classificação.

4. **Isolamento e consulta segura**
   - **Given** uma consulta interna por proposta ou execução
   - **When** o serviço busca evidências consultivas
   - **Then** retorna somente evidências do `tenant_id` confiável e do `tenant_isolation_tier=bridge`
   - **And** rejeita cross-tenant, contexto divergente ou escopo insuficiente sem revelar existência de dados de outro tenant.

5. **Referência por decisão sem autonomia da IA**
   - **Given** uma decisão final que considerou evidência consultiva
   - **When** a decisão é registrada ou auditada
   - **Then** referencia apenas `consultative_evidence_refs` técnicos considerados
   - **And** preserva política determinística, reason codes governados e `Decision Service` como única fonte da decisão final.

6. **Logs, auditoria e repositório minimizados**
   - **Given** criação, consulta ou rejeição de evidência consultiva
   - **When** logs e intenções auditáveis forem emitidos
   - **Then** incluem apenas metadados seguros, contagens, IDs técnicos, versão, fingerprint, `correlation_id` e `trace_id`
   - **And** não incluem CPF, CNPJ, nome, e-mail, endereço, telefone, segredo, header sensível, dado financeiro detalhado, prompt, payload ou output bruto.

7. **Sem ampliação indevida de escopo**
   - **Given** que esta story materializa evidência consultiva vinculada à proposta
   - **When** o dev agent implementar
   - **Then** não adiciona provedor/modelo real, SDK de IA, endpoint público, gRPC real, NATS, banco real, dashboard ou trilha oficial append-only
   - **And** não usa evidência consultiva como critério de aprovação/reprovação automática.

## Tasks / Subtasks

- [x] CTOS-300 — Criar modelo de domínio para evidência consultiva vinculada à proposta (AC: 1, 2, 3, 6)
  - [x] Modelar entidade ou agregado em `services/automated-review/src/creditos_automated_review/domain/entities`.
  - [x] Incluir `consultative_evidence_id`, `tenant_id`, `proposal_id`, `execution_id`, `classification="consultative"`, `occurred_at`, `correlation_id` e `trace_id`.
  - [x] Incluir proveniência: `review_agent_config_id`, `review_agent_config_version_id`, `agent_version`, `prompt_fingerprint`, `minimization_policy_ref` e `model_ref` seguro quando existir.
  - [x] Validar todos os identificadores com validadores existentes ou novos validadores técnicos equivalentes.

- [x] CTOS-301 — Modelar itens de evidência a partir da saída validada (AC: 2, 3, 6)
  - [x] Reusar `ReviewOutputItem` e `ReviewOutputValidationResult` da Story 5.3 como fonte; não aceitar `dict[str, Any]` ou output bruto no modelo persistido.
  - [x] Preservar `item_ref`, `item_type`, `severity`, `reason_ref`, `confidence` e `evidence_refs`.
  - [x] Separar contagens/referências por `missing_data`, `inconsistency`, `explainability_factor` e `limitation`.
  - [x] Não persistir `safe_summary` se houver risco de texto livre; se for mantido, deve continuar curto, validado e não sensível.

- [x] CTOS-302 — Criar porta e adapter in-memory de evidências consultivas (AC: 1, 4, 6)
  - [x] Criar `ConsultativeEvidenceRepository` ou nome equivalente em `application/ports`.
  - [x] Implementar `InMemoryConsultativeEvidenceRepository` chaveado por `(tenant_id, consultative_evidence_id)` e índices seguros por proposta/execução.
  - [x] Garantir idempotência: mesma execução aceita não cria evidência duplicada.
  - [x] Fornecer consulta por `proposal_id` e por `execution_id` com isolamento por tenant.

- [x] CTOS-303 — Integrar criação de evidência ao fluxo de execução consultiva (AC: 1, 2, 3, 6)
  - [x] Estender `AutomatedReviewApplicationService` para receber o novo repositório opcional no construtor.
  - [x] Criar evidência somente quando `_validate_executor_output` retornar status `accepted` e a execução final for `completed`.
  - [x] Não criar evidência consultiva aceita para fallback por executor, schema inválido ou guardrail bloqueado; fallback ampliado pertence à Story 5.5.
  - [x] Garantir rollback/atomicidade local semelhante ao padrão `before_commit`: auditoria crítica não pode deixar evidência visível se falhar.

- [x] CTOS-306 — Expor referência segura para decisão considerar evidência consultiva (AC: 5, 7)
  - [x] Definir `consultative_evidence_ref` técnico como referência, não como payload de IA.
  - [x] Se tocar o `Decision Service`, limitar a mudança a armazenar refs consideradas (`consultative_evidence_refs`) em decisão/auditoria/logs; não alterar regras, outcomes, reason codes ou termos aprovados por causa da IA.
  - [x] Preservar o fingerprint determinístico conforme decisão arquitetural local: se a ref for parte da rastreabilidade da decisão, documentar se entra ou não no `decision_fingerprint` e cobrir com teste.
  - [x] Não criar chamada síncrona real entre `Decision` e `Automated Review`; integração real fica para contrato/gRPC/evento futuro.

- [x] CTOS-304 — Registrar logs e auditoria minimizados da evidência (AC: 1, 2, 4, 6)
  - [x] Emitir intenção auditável com `event_type` específico, por exemplo `automated_review.evidence.created`.
  - [x] Incluir contagens por tipo, quantidade de itens, refs técnicas e flags `raw_payload_persisted=false`, `prompt_payload_persisted=false`, `raw_output_persisted=false`.
  - [x] Registrar `correlation_id`, `request_id`, `trace_id`, `tenant_id` e `tenant_isolation_tier` somente a partir de contexto confiável/observável.
  - [x] Garantir que erros e `repr`/`str` de modelos não ecoem conteúdo sensível.

- [x] CTOS-305 — Criar testes RED/GREEN de domínio, aplicação, repositório e regressão (AC: 1-7)
  - [x] Cobrir criação de evidência aceita com lacuna, inconsistência, fator explicável, limitação e confiança opcional.
  - [x] Cobrir consulta por proposta/execução, idempotência e isolamento cross-tenant.
  - [x] Cobrir que fallback/guardrail bloqueado não cria evidência aceita.
  - [x] Cobrir que logs, auditoria, repositório e strings não contêm prompt/output/payload bruto ou dados sensíveis sintéticos.
  - [x] Cobrir que refs de evidência consultiva não alteram outcome, reason codes ou source determinística da decisão.

- [x] CTOS-307 — Atualizar documentação, story e Jira (AC: 1, 5, 6, 7)
  - [x] Atualizar `services/automated-review/README.md` com o fluxo da Story 5.4.
  - [x] Atualizar esta story com arquivos alterados, evidências de validação e decisões locais.
  - [x] Atualizar `sprint-status.yaml` conforme avanço.
  - [x] Mover subtarefas Jira conforme execução (`Tarefas pendentes` → `Em andamento` → `Concluído`) e manter `CTOS-50` sincronizada.

### Review Findings

- [x] [Review][Patch] Evidência é reportada como criada mesmo sem persistência [services/automated-review/src/creditos_automated_review/application/service.py:450]
- [x] [Review][Patch] Escrita de execução e evidência não preserva consistência em falha da evidência [services/automated-review/src/creditos_automated_review/application/service.py:456]
- [x] [Review][Patch] Consulta segura de evidência por proposta/execução não existe no application service [services/automated-review/src/creditos_automated_review/application/ports/consultative_evidence_repository.py:17]
- [x] [Review][Patch] Construtor direto de evidência aceita itens não sanitizados [services/automated-review/src/creditos_automated_review/domain/entities/consultative_evidence.py:175]
- [x] [Review][Patch] `consultative_evidence_id` pode estourar limite ao prefixar execução válida [services/automated-review/src/creditos_automated_review/domain/entities/consultative_evidence.py:265]
- [x] [Review][Patch] Evidência não valida consistência entre execução, configuração e saída validada [services/automated-review/src/creditos_automated_review/domain/entities/consultative_evidence.py:219]
- [x] [Review][Patch] Auditoria de evidência não carrega `request_id` e `tenant_isolation_tier` [services/automated-review/src/creditos_automated_review/application/ports/review_execution_audit_publisher.py:8]

## Dev Notes

### Escopo desta story

- Esta story transforma o resultado validado da Story 5.3 em uma evidência consultiva rastreável e vinculada à proposta.
- A evidência pertence ao bounded context `Automated Review`. A trilha oficial append-only continua pertencendo ao futuro `Audit & Evidence Service`.
- A evidência é consultiva: pode explicar lacunas, inconsistências, fatores sugeridos e limitações, mas nunca decide crédito.
- A decisão final continua no `Decision Service` e deve preservar política determinística, catálogo de reason codes e regras do Epic 4.
- Não implementar API pública, gRPC real, NATS, banco real, migration, outbox/inbox, dashboard ou fornecedor de IA real nesta story.

### Contexto funcional consolidado

- Epic 5 define que revisão por IA é evidência consultiva com guardrails, versionamento e sem autonomia para decisão final. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Epic 5]
- Story 5.4 exige vincular evidência a proposta, tenant, correlation ID, versão de agente/modelo/prompt, lacunas, inconsistências, fatores sugeridos, limitações e confiança quando aplicável. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Story 5.4]
- O segundo AC exige que decisões que considerarem evidência consultiva referenciem a evidência considerada sem deslocar a decisão final da política determinística. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Story 5.4]
- A arquitetura define `Automated Review` como dono de revisão consultiva por IA, versões de agente/modelo/prompt e evidência consultiva. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`, AD-2/AD-3]
- `Decision` é dono exclusivo de decisão final, termos aprovados, políticas e reason codes. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`, AD-2/AD-3]
- `Audit & Evidence` será dono da trilha oficial append-only; esta story não deve implementar storage oficial append-only. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`, AD-3/AD-11]

### Arquivos existentes a preservar

- `services/automated-review/src/creditos_automated_review/application/service.py`
  - `execute_consultative_review` já valida scope, contexto completo, tenant bridge, configuração publicada, reserva idempotente, executor mockado, validação de output e fallback.
  - Preservar `execution_repository.reserve(...)` antes do executor; não voltar para checagem não atômica.
  - Preservar `_safe_execution_details(...)` com payload/prompt/output bruto marcados como não persistidos.

- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
  - `AutomatedReviewExecutionResult` já força `classification="consultative"` e rejeita `final_decision`, `approved_terms` e `external_actions`.
  - `input_fields` persistidos removem `safe_value`; não reintroduzir valores de entrada.
  - `finding_refs` e `limitation_refs` hoje são referências técnicas derivadas da validação de saída, não evidências finais vinculadas.

- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_output.py`
  - `ReviewOutputItem` já valida schema fechado, tipo, severidade, confidence 0–100, refs seguras, limite de `evidence_refs`, `safe_summary` curta e guardrails PT/EN.
  - `ReviewOutputValidationResult.accepted(...)` fornece itens e contagens aceitas; use isso como input de evidência.
  - Não aceitar refs legadas `finding_refs`/`limitation_refs` como fonte principal de evidência.

- `services/automated-review/src/creditos_automated_review/adapters/persistence/in_memory_review_execution_repository.py`
  - Já tem padrão simples com `RLock`, `reserve`, `create`, `get` e chave por tenant.
  - Novo adapter in-memory deve seguir o mesmo estilo e não expor referências mutáveis.

- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`
  - `CreditDecision` calcula `decision_fingerprint` a partir de política, catálogo, outcome, reason codes, fatores, issues, integrações e input fingerprint.
  - Qualquer ref consultiva adicionada deve ser explicitamente tratada no fingerprint ou documentada como metadado de rastreabilidade; evitar alteração acidental de determinismo.

### Padrões arquiteturais obrigatórios

- Backend segue DDD + arquitetura hexagonal: domínio sem infraestrutura, adapters atrás de ports, application service orquestrando caso de uso.
- Comunicação real cross-service futura deve ser gRPC para chamada síncrona curta ou NATS JetStream para fluxo assíncrono durável; esta story não implementa nenhum protocolo real.
- Multi-tenancy `bridge`: `tenant_id` vem do `PropagatedContext`, não do payload, output de IA ou parâmetro livre.
- Logs, auditoria, métricas e traces devem usar contexto confiável/observável e mascaramento/minimização.
- Não fazer join ou consulta direta entre bancos/serviços.

### Contrato sugerido de evidência consultiva

Nome sugerido, ajustável conforme implementação:

- `ConsultativeEvidence`
  - `consultative_evidence_id`: referência técnica derivada de `execution_id` ou criada de forma determinística.
  - `tenant_id`, `proposal_id`, `execution_id`.
  - `classification`: constante `consultative`.
  - `review_agent_config_id`, `review_agent_config_version_id`, `agent_version`.
  - `model_provider_ref`, `model_ref`, `model_version`: opcionais e seguros.
  - `minimization_policy_ref`, `prompt_fingerprint`.
  - `correlation_id`, `trace_id`, `occurred_at`.
  - `items`: tupla de itens consultivos validados, sem output bruto.
  - `counts_by_type`, `confidence_counts`/`confidence_present_count` quando útil, sem métricas de alta cardinalidade.

Nome sugerido de item:

- `ConsultativeEvidenceItem`
  - `item_ref`, `item_type`, `severity`, `reason_ref`, `confidence`, `evidence_refs`.
  - `item_type` deve continuar limitado a `missing_data`, `inconsistency`, `explainability_factor`, `limitation`.
  - Não incluir decisão final, termos aprovados, callback, tool call, integração externa ou payload bruto.

### Vínculo com decisão

- A forma mínima recomendada é expor/armazenar uma referência técnica de evidência (`consultative_evidence_id`) para uso posterior pelo `Decision Service`.
- Se o dev agent optar por alterar `Decision`, a mudança deve ser pequena e explícita:
  - adicionar `consultative_evidence_refs` em `CreditDecisionInput`/`CreditDecision` ou DTO equivalente;
  - validar refs como IDs técnicos e únicos;
  - registrar contagem/refs seguras em logs/auditoria;
  - não usar o conteúdo da evidência para outcome, reason codes, termos aprovados ou fallback;
  - cobrir com testes que a política determinística continua fonte da decisão final.
- Não criar dependência direta do pacote `creditos_decision` dentro de `creditos_automated_review` nem o inverso.

### Segurança e privacidade

- Evidência não pode conter CPF, CNPJ, nome, e-mail completo, endereço, telefone, documento, segredo, token, header sensível, prompt, payload bruto, output bruto ou dado financeiro detalhado.
- Usar fixtures sintéticas já adotadas (`tenant_alpha`, `proposal_001`, `corr_review_context`, etc.) e evitar PII realista em testes.
- Erros devem retornar código técnico e `field_path`, sem ecoar conteúdo inválido.
- `safe_summary` continua opcional. Se qualquer texto livre for propagado para evidência, precisa permanecer validado pelos guardrails de `ReviewOutputItem`; preferir refs técnicas.

### Previous Story Intelligence

- Story 5.1 criou configuração versionada publicada e imutável, prompt fingerprint, model refs seguros e audit/log minimizados.
- Story 5.2 criou execução consultiva minimizada com allowlist estrita, reserva atômica de `execution_id`, `input_fields` persistidos sem `safe_value` e adapter mockado.
- Story 5.3 criou validação de saída com schema fechado, guardrails PT/EN, limite de cardinalidade, rejeição de campos legados e contagens de output aceito/bloqueado.
- Correções recentes relevantes:
  - `blocked_counts_by_reason` deve ser consistente quando `status="blocked"`.
  - refs técnicas não podem codificar decisão (`approved_proposal`, `rejected_*`, `publicar_decisao`, etc.).
  - `output_items` e `evidence_refs` têm limites para não materializar saída não confiável gigante.
  - campos legados `finding_refs`/`limitation_refs` do executor são rejeitados antes de aceitar `output_items`.

### Testes e validações esperadas

- Testes focados:
  - `.venv/bin/pytest services/automated-review/tests/unit`
  - Se tocar `Decision`: `.venv/bin/pytest services/decision/tests/unit`
- Gates:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Suíte completa local pode falhar por ambiente se `uv` não estiver disponível em `scripts/dev harness-check`; se ocorrer, registrar como limitação ambiental sem mascarar falhas reais.

### Pesquisa técnica recente

- Nenhuma tecnologia nova deve ser selecionada nesta story.
- Não há necessidade de pesquisa web para versões externas: a implementação deve permanecer em Python/stdlib + padrões já existentes no repositório.
- Se surgir necessidade de biblioteca, protocolo, storage ou provedor externo, interromper e registrar decisão/ADR antes de implementar.

### Checklist de implementação para o dev agent

- [ ] Antes de codificar, criar/sincronizar subtarefas Jira e mover a primeira subtarefa para `Em andamento`.
- [ ] Começar com testes RED para evidência consultiva e isolamento por tenant.
- [ ] Reusar validadores existentes antes de criar novos.
- [ ] Não persistir texto bruto por conveniência.
- [ ] Atualizar README e esta story com decisões locais, arquivos alterados e evidências.
- [ ] Rodar `bmad-code-review` antes de commit/push/draft PR.

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

.venv/bin/pytest services/automated-review/tests/unit/test_consultative_review_execution.py
.venv/bin/pytest services/automated-review/tests/unit
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/pyright

### Completion Notes List

- Implementado `ConsultativeEvidence` com proveniência, classificação consultiva, correlation/trace, refs técnicas e contagens por tipo.
- Implementado `ConsultativeEvidenceItem` derivado de `ReviewOutputValidationResult`, sem `safe_summary`, prompt, payload ou output bruto.
- Implementado `ConsultativeEvidenceRepository` e adapter in-memory com idempotência por execução e índices por proposta/execução isolados por tenant.
- Integrado `AutomatedReviewApplicationService` para criar evidência somente em execução `completed` com saída `accepted`, emitindo `automated_review.evidence.created` antes de exposição no repositório.
- Decisão local: não alterar `Decision Service` nesta story; a referência segura exposta é `consultative_evidence_id` para integração futura por contrato/gRPC/evento, preservando fingerprints e decisão determinística atuais.
- Atualizado Jira: subtarefas `CTOS-300`, `CTOS-301`, `CTOS-302`, `CTOS-303`, `CTOS-306`, `CTOS-304`, `CTOS-305` e `CTOS-307` concluídas; `CTOS-50` movida para `Em análise`.
- Resolvidos os 7 achados do `bmad-code-review`: persistência condicional correta, consistência execução/evidência, consultas seguras por contexto confiável, sanitização de itens, ID longo seguro, validação de proveniência/saída e auditoria com `request_id`/`tenant_isolation_tier`.

### File List

- `_bmad-output/implementation-artifacts/5-4-evidencia-consultiva-vinculada-a-proposta.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/automated-review/README.md`
- `services/automated-review/src/creditos_automated_review/adapters/persistence/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/persistence/in_memory_consultative_evidence_repository.py`
- `services/automated-review/src/creditos_automated_review/application/__init__.py`
- `services/automated-review/src/creditos_automated_review/application/ports/__init__.py`
- `services/automated-review/src/creditos_automated_review/application/ports/consultative_evidence_repository.py`
- `services/automated-review/src/creditos_automated_review/application/ports/review_execution_audit_publisher.py`
- `services/automated-review/src/creditos_automated_review/application/service.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/consultative_evidence.py`
- `services/automated-review/tests/unit/test_consultative_review_execution.py`

### Change Log

- 2026-09-10 — Implementada evidência consultiva vinculada à proposta, com repositório in-memory, integração no fluxo consultivo, logs/auditoria minimizados, testes e README.
- 2026-09-10 — Resolvidos achados do code review da Story 5.4 e status BMAD atualizado para `done`.
