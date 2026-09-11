---
jira_issue: CTOS-51
branch: agent/story-5-5-fallback-seguro-revisao-automatizada
baseline_commit: 42fde9c
created_at: 2026-09-11
subtasks:
  - CTOS-308
  - CTOS-309
  - CTOS-310
  - CTOS-311
  - CTOS-312
  - CTOS-313
  - CTOS-314
---

# Story 5.5: Fallback Seguro de Revisão Automatizada

Status: done

## Story

Como cliente técnico,
quero que falhas de IA resultem em estado controlado,
para que uma indisponibilidade, timeout, erro de schema ou bloqueio de guardrail nunca vire aprovação, reprovação ou alteração indevida de termos.

## Acceptance Criteria

1. **Fallback configurado para falhas de IA**
   - **Given** falha de provedor/modelo, timeout, exceção do executor, erro de schema ou guardrail bloqueando resposta
   - **When** a revisão automatizada falha
   - **Then** o sistema retorna fallback configurado pela configuração publicada do agente
   - **And** registra motivo técnico, limitação consultiva, versão de configuração/prompt/modelo quando aplicável e correlation ID.

2. **Sem alteração direta da decisão final**
   - **Given** qualquer fallback de revisão automatizada
   - **When** o resultado é produzido, persistido, logado ou auditado
   - **Then** não altera diretamente aprovação, reprovação, termos aprovados, required data ou status final do `Decision`
   - **And** preserva `Decision Service` e política determinística como única fonte da decisão final.

3. **Continuação sem revisão quando configurada**
   - **Given** política/configuração publicada com `fallback_action="continue_without_review"`
   - **When** a IA falha
   - **Then** o fluxo expõe ausência de revisão consultiva como limitação segura para a decisão determinística
   - **And** registra explicitamente que nenhuma evidência consultiva aceita foi criada.

4. **Ações de fallback seguras e governadas**
   - **Given** fallback configurado como `request_more_data` ou `unable_to_decide`
   - **When** a revisão automatizada falha
   - **Then** o resultado consultivo carrega apenas uma recomendação técnica de fallback para ser considerada pela política determinística
   - **And** não cria outcome final, reason code final de crédito, alteração de termos, callback, tool call ou integração externa.

5. **Rastreabilidade, idempotência e isolamento**
   - **Given** execução consultiva com tenant confiável e `tenant_isolation_tier=bridge`
   - **When** o fallback é produzido
   - **Then** preserva `tenant_id`, `proposal_id`, `execution_id`, produto, canal, propósito, config/version, prompt fingerprint, correlation ID e trace ID quando disponível
   - **And** mantém reserva/idempotência de execução, isolamento cross-tenant e ausência de evidência consultiva aceita.

6. **Logs e auditoria minimizados**
   - **Given** fallback por falha, schema inválido ou guardrail bloqueante
   - **When** logs e intenções auditáveis forem emitidos
   - **Then** incluem apenas metadados seguros, contagens, reason refs, limitation refs, fallback action e flags de não persistência bruta
   - **And** não incluem prompt bruto, payload bruto, output bruto, CPF, CNPJ, nome, e-mail, endereço, telefone, segredo, header sensível ou dado financeiro detalhado.

7. **Sem ampliação indevida de escopo**
   - **Given** que esta story controla fallback do `Automated Review Service`
   - **When** o dev agent implementar
   - **Then** não adiciona provedor/modelo real, SDK de IA, endpoint público, gRPC real, NATS, banco real, dashboard, fila manual ou trilha oficial append-only
   - **And** qualquer necessidade de integração com `Decision` deve ficar limitada a referência/contrato técnico futuro ou ser registrada como trabalho posterior.

## Tasks / Subtasks

- [x] CTOS-308 — Modelar resultado de fallback seguro de revisão automatizada (AC: 1, 2, 4, 6)
  - [x] Definir ou ajustar objeto/valor de fallback consultivo no domínio/aplicação sem usar `dict[str, Any]` livre como contrato principal.
  - [x] Representar `fallback_action`, `fallback_reason_ref`, `limitation_ref`, `output_validation_status`, `classification="consultative"` e flags de não persistência bruta.
  - [x] Rejeitar qualquer campo com semântica de decisão final: aprovação, reprovação, termos aprovados, callback, tool use ou integração externa.
  - [x] Reusar validadores existentes de refs técnicas, status e tokens antes de criar novos validadores.

- [x] CTOS-309 — Aplicar fallback configurado no fluxo consultivo (AC: 1, 2, 4, 5, 7)
  - [x] Usar `ReviewAgentGuardrails.fallback_action` da configuração publicada como fonte governada.
  - [x] Diferenciar falha de executor/timeout, erro de schema/contrato e bloqueio de guardrail com reason refs estáveis.
  - [x] Garantir que `_fallback_execution_result(...)` ou equivalente não altere outcome, reason codes finais, termos ou status final do `Decision`.
  - [x] Preservar `execution_repository.reserve(...)` antes do executor e `execution_repository.create(...)` com auditoria antes de commit.

- [x] CTOS-310 — Garantir modo `continue_without_review` auditável (AC: 2, 3, 5, 6)
  - [x] Expor fallback como ausência governada de revisão consultiva, não como sucesso de IA.
  - [x] Registrar limitação técnica específica, `fallback_action="continue_without_review"` e ausência de evidência aceita.
  - [x] Manter a decisão determinística livre para prosseguir conforme política, sem conteúdo de IA e sem atalho de aprovação/reprovação.
  - [x] Cobrir idempotência quando a mesma execução já tiver fallback registrado.

- [x] CTOS-311 — Registrar logs e auditoria minimizados de fallback (AC: 1, 3, 5, 6)
  - [x] Emitir evento/intenção auditável de execução com `event_type` de fallback e detalhes seguros.
  - [x] Incluir tenant, produto, canal, propósito, config/version, prompt fingerprint, correlation ID, trace ID, fallback action, reason refs e limitation refs.
  - [x] Preservar flags `raw_payload_persisted=false`, `prompt_payload_persisted=false`, `raw_output_persisted=false` quando aplicável.
  - [x] Garantir que exceções, `repr`, `str`, logs e audit intents não ecoem conteúdo sensível ou saída bruta.

- [x] CTOS-312 — Preservar isolamento, idempotência e ausência de evidência aceita (AC: 3, 5, 6)
  - [x] Garantir que fallback não cria `ConsultativeEvidence` aceita nem retorna `consultative_evidence_created=true`.
  - [x] Manter consultas e persistência chaveadas por `tenant_id` confiável.
  - [x] Rejeitar contexto divergente, cross-tenant ou `tenant_isolation_tier` diferente de `bridge`.
  - [x] Não consultar diretamente banco/estado de outro serviço nem criar dependência circular com `Decision`.

- [x] CTOS-313 — Criar testes RED/GREEN de fallback seguro (AC: 1-7)
  - [x] Cobrir falha de executor/exceção, output malformado, status inválido, campo desconhecido, prompt injection/autonomia e guardrail bloqueante.
  - [x] Cobrir `continue_without_review`, `request_more_data` e `unable_to_decide` quando permitidos pela configuração.
  - [x] Cobrir que fallback não cria evidência aceita, não altera decisão final, não expõe payload/prompt/output bruto e mantém tenant isolation.
  - [x] Rodar testes focados de `services/automated-review` e gates Ruff/Pyright aplicáveis.

- [x] CTOS-314 — Atualizar README, story e sincronização BMAD/Jira (AC: 5, 6, 7)
  - [x] Atualizar `services/automated-review/README.md` com comportamento de fallback seguro quando a implementação alterar fluxo observável.
  - [x] Atualizar esta story com arquivos alterados, decisões locais, evidências de validação e achados de review.
  - [x] Atualizar `sprint-status.yaml` conforme avanço.
  - [x] Mover subtarefas Jira conforme execução (`Tarefas pendentes` → `Em andamento` → `Concluído`) e manter `CTOS-51` sincronizada.

### Review Findings

- [x] [Review][Patch] Mapear erros estruturais de schema para `reason_invalid_output_schema` [`services/automated-review/src/creditos_automated_review/application/service.py:923`]
- [x] [Review][Patch] Registrar metadados seguros de modelo/provedor no fallback quando aplicável [`services/automated-review/src/creditos_automated_review/application/service.py:983`]
- [x] [Review][Patch] Fortalecer invariantes de domínio para `status="fallback"` [`services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py:315`]
- [x] [Review][Patch] Validar `fallback_reason_refs` contra semântica decisória/autônoma [`services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py:299`]
- [x] [Review][Patch] Serializar todas as refs de fallback/limitação ou restringir cardinalidade [`services/automated-review/src/creditos_automated_review/application/service.py:1030`]
- [x] [Review][Defer] Executor ausente não vira fallback e pode deixar reserva órfã [`services/automated-review/src/creditos_automated_review/application/service.py:423`] — deferred, pre-existing

## Dev Notes

### Escopo desta story

- Esta story endurece o fallback do `Automated Review Service` para falhas de provedor/modelo, timeout/exceção do executor, erro de schema/contrato e bloqueio de guardrail.
- A implementação deve permanecer consultiva: o fallback pode informar limitação e ação configurada, mas não pode decidir crédito.
- O fallback pertence ao bounded context `Automated Review`; a decisão final continua no bounded context `Decision`.
- Não implementar fila manual, revisão humana, agente adicional, provedor real de IA, SDK externo, chamada HTTP, gRPC real, NATS, banco real, migration, dashboard ou trilha oficial append-only nesta story.

### Contexto funcional consolidado

- Epic 5 define revisão por IA como evidência consultiva com guardrails, versionamento, auditoria e sem autonomia para decisão final. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Epic 5]
- Story 5.5 exige que falha de provedor/modelo, timeout, erro de schema ou guardrail bloqueante retorne fallback configurado para o `Decision` sem alterar termos, aprovação, recusa ou status final diretamente. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Story 5.5]
- O contrato de proposta já prevê `decision_options.review_strategy="ai_advisory"` e `fallback_action`; o MVP remove `manual_review` e preserva decisão por política versionada. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/contrato-inicial-proposta-oq3.md`, `decision_options`]
- A configuração de agente usa `ReviewAgentGuardrails.fallback_action` com ações aceitas no código atual: `continue_without_review`, `request_more_data` e `unable_to_decide`. [Fonte: `services/automated-review/src/creditos_automated_review/domain/value_objects/review_agent_config.py`]
- Existe divergência documental antiga citando `reject_by_policy` no PRD inicial; o código atual não permite essa ação e ela não deve ser reintroduzida silenciosamente nesta story. Se necessária, abrir decisão/ADR antes de alterar contrato.

### Arquivos existentes a preservar

- `services/automated-review/src/creditos_automated_review/application/service.py`
  - `execute_consultative_review(...)` já exige scope `automated_review:execute`, contexto observável compatível com `PropagatedContext`, `tenant_isolation_tier=bridge`, configuração publicada, plano de minimização, reserva idempotente e executor por port.
  - `_validate_executor_output(...)` já transforma output válido em `ReviewOutputValidationResult.accepted(...)` e bloqueia campos legados, output vazio, excesso de itens e itens inválidos.
  - `_blocked_output_validation(...)`, `_output_block_reason_ref(...)` e `_fallback_execution_result(...)` já existem e devem ser estendidos com cuidado, preservando reason refs estáveis.
  - `_safe_execution_details(...)` já centraliza logs seguros e deve continuar sem prompt, payload ou output bruto.

- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
  - `AutomatedReviewExecutionResult` já restringe status a `completed`, `blocked`, `failed` ou `fallback`.
  - A entidade força `classification="consultative"` e rejeita `final_decision`, `approved_terms` e `external_actions`.
  - `input_fields` persistidos removem `safe_value`; não reintroduzir valores de entrada ou payload bruto para diagnosticar fallback.

- `services/automated-review/src/creditos_automated_review/domain/entities/consultative_evidence.py`
  - `ConsultativeEvidence.from_execution(...)` só deve ser criado para execução `completed` e output `accepted`.
  - Fallback por falha, schema inválido ou guardrail bloqueado não deve gerar evidência aceita.

- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_output.py`
  - `ReviewOutputItem` já valida schema fechado, refs seguras, limites, autonomia decisória e conteúdo sensível/prompt injection.
  - `ReviewOutputValidationResult.blocked(...)` deve continuar sendo a fonte de blocked counts e reason refs para fallback por output inválido.

- `services/automated-review/tests/unit/test_consultative_review_execution.py`
  - Já cobre falhas básicas de executor, output inválido, ausência de evidência para fallback, auditoria e sanitização.
  - Novos testes devem ampliar cobertura sem duplicar fixtures frágeis e sem usar PII realista.

### Padrões arquiteturais obrigatórios

- Backend segue DDD + arquitetura hexagonal: domínio sem infraestrutura, application service orquestra, ports isolam executor/auditoria/repositório e adapters ficam fora do domínio.
- Multi-tenancy `bridge`: `tenant_id`, `tenant_isolation_tier`, ator e scopes vêm do `PropagatedContext`; payload ou output de IA nunca são fonte confiável de tenant/identidade.
- Logs e auditoria devem usar metadados seguros, minimização, mascaramento e contexto confiável/observável.
- Comunicação real cross-service futura deve ser gRPC para chamada síncrona curta ou NATS JetStream para fluxo assíncrono durável; esta story não implementa nenhum protocolo real.
- Não fazer join direto entre bancos/serviços e não importar `creditos_decision` dentro de `creditos_automated_review`.

### Contrato sugerido de fallback seguro

- Reusar `AutomatedReviewExecutionResult` quando suficiente, mas garantir campos/metadata seguros para:
  - `status="fallback"`;
  - `classification="consultative"`;
  - `fallback_action`;
  - `limitation_refs`, por exemplo `limitation_executor_failure`, `limitation_invalid_executor_output`, `limitation_output_guardrail_blocked` ou nome equivalente estável;
  - `blocked_output_counts_by_reason` e reason refs governados;
  - flags de não persistência bruta.
- Se criar value object dedicado, manter contrato fechado, imutável e validado. Não criar `metadata` livre para transportar dados sensíveis.
- `fallback_action` deve expressar orientação técnica consultiva para a política determinística:
  - `continue_without_review`: permite seguir sem evidência consultiva aceita, registrando limitação.
  - `request_more_data`: indica que a política pode solicitar dados adicionais, sem o `Automated Review` decidir isso sozinho.
  - `unable_to_decide`: indica limitação operacional/técnica para política decidir o resultado controlado.

### Segurança e privacidade

- Nunca logar ou persistir prompt bruto, payload bruto, output bruto, exceção com conteúdo externo, CPF, CNPJ, nome, e-mail completo, endereço, telefone, documento, token, segredo, header sensível ou dado financeiro detalhado.
- Usar somente IDs técnicos e fixtures sintéticas (`tenant_alpha`, `proposal_001`, `corr_review_context`, etc.).
- Não usar mensagem de exceção externa como `reason_ref`, `limitation_ref`, log ou audit detail; mapear para códigos técnicos internos.
- `safe_summary` e `output_items` bloqueados não devem reaparecer em fallback para “ajudar debug”.

### Previous Story Intelligence

- Story 5.1 criou configuração versionada publicada e imutável, guardrails obrigatórios, prompt fingerprint e model refs seguros.
- Story 5.2 criou execução consultiva minimizada, allowlist estrita, reserva atômica de `execution_id`, executor por port e persistência sem valores de entrada.
- Story 5.3 criou validação de saída com schema fechado, guardrails PT/EN, limite de cardinalidade, bloqueio de autonomia decisória, prompt injection e dados sensíveis.
- Story 5.4 criou evidência consultiva apenas para execução `completed` com output `accepted`, com idempotência por execução e auditoria antes de exposição no repositório.
- Correções recentes relevantes:
  - fallback não pode ser reportado como evidência criada;
  - `blocked_counts_by_reason` deve refletir o motivo real quando `status="blocked"` ou fallback por output inválido;
  - auditoria deve carregar `request_id`, `tenant_isolation_tier`, `correlation_id` e `trace_id` apenas a partir de contexto confiável;
  - refs técnicas não podem codificar decisão final (`approved_*`, `rejected_*`, `publicar_decisao`, etc.).

### Git Intelligence

- Branch base: `agent/story-5-5-fallback-seguro-revisao-automatizada`.
- Baseline: `42fde9c`, merge do PR #49 da Story 5.4.
- Commits recentes do Epic 5 estabeleceram o padrão de testes unitários em `services/automated-review/tests/unit`, adapters in-memory com `RLock`, portas em `application/ports` e domínio imutável com dataclasses frozen/slots.

### Testes e validações esperadas

- Testes focados:
  - `.venv/bin/pytest services/automated-review/tests/unit`
- Gates:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Se qualquer teste exigir `.venv` ausente, criar/reusar venv local do projeto conforme padrão já adotado, sem commitar ambiente virtual.

### Pesquisa técnica recente

- Nenhuma tecnologia nova deve ser selecionada nesta story.
- Não há necessidade de pesquisa web para versões externas: a implementação deve permanecer em Python/stdlib + padrões já existentes.
- Se surgir necessidade de biblioteca, protocolo, storage, provedor externo ou mudança de contrato público, interromper e registrar decisão/ADR antes de implementar.

### Checklist de implementação para o dev agent

- [ ] Antes de codificar, mover a primeira subtarefa Jira para `Em andamento`.
- [ ] Começar por testes RED que comprovem falha segura e ausência de autonomia decisória.
- [ ] Reusar validadores e reason refs existentes quando possível.
- [ ] Não persistir conteúdo bruto por conveniência de debug.
- [ ] Atualizar README e esta story com decisões locais, arquivos alterados e evidências.
- [ ] Rodar `bmad-code-review` antes de commit/push/draft PR.

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

.venv/bin/pytest services/automated-review/tests/unit/test_consultative_review_execution.py -q
.venv/bin/pytest services/automated-review/tests/unit
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/pyright
.venv/bin/pytest

### Completion Notes List

- Implementado contrato governado de fallback em `AutomatedReviewExecutionResult` com `fallback_action` e `fallback_reason_refs`, restrito a `status="fallback"`.
- `AutomatedReviewApplicationService` agora preenche `fallback_action` a partir de `ReviewAgentGuardrails`, diferencia falha de executor, schema inválido e guardrail bloqueante, e mantém fallback consultivo sem autonomia decisória.
- Logs/auditoria seguros incluem `fallback_action`, `fallback_reason_ref`, `limitation_ref`, contagens e flags de não persistência bruta.
- Fallbacks continuam sem criar `ConsultativeEvidence` aceita e sem alterar outcome, reason codes finais, termos aprovados ou status final do `Decision`.
- Atualizado `services/automated-review/README.md` com o comportamento da Story 5.5.
- Jira sincronizado: `CTOS-308` a `CTOS-314` concluídas; `CTOS-51` movida para `Em análise` para code review.
- Revisão BMAD Step 02 concluída: patches aplicados para mapeamento de erros estruturais de schema, metadados seguros de modelo/provedor, invariantes fortes de fallback, bloqueio de refs decisórias em `fallback_reason_refs` e serialização indexada de refs.
- Observação ambiental: `.venv/bin/pytest` completo passou 589 testes e falhou 1 teste local por `uv: command not found` em `scripts/dev harness-check`; não relacionado às mudanças da story. No sandbox, o harness também sofre bloqueio de socket local.

### File List

- `_bmad-output/implementation-artifacts/5-5-fallback-seguro-de-revisao-automatizada.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/automated-review/README.md`
- `services/automated-review/src/creditos_automated_review/application/service.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_output.py`
- `services/automated-review/tests/unit/test_consultative_review_execution.py`

### Change Log

- 2026-09-11 — Story detalhada por `bmad-create-story`, subtarefas Jira criadas e status BMAD atualizado para `ready-for-dev`.
- 2026-09-11 — Implementado fallback seguro de revisão automatizada, com ação configurada, reason refs, limitation refs, auditoria/logs minimizados, testes e README.
- 2026-09-11 — Aplicados patches da revisão BMAD Step 02 e status local atualizado para `done`; Jira permanece em `Em análise` até PR/merge.
