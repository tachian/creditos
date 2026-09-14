---
jira_issue: CTOS-52
branch: agent/story-5-6-observabilidade-custo-gates-ia
baseline_commit: 6e0731c
created_at: 2026-09-11
subtasks:
  - CTOS-315
  - CTOS-316
  - CTOS-317
  - CTOS-318
  - CTOS-319
  - CTOS-320
---

# Story 5.6: Observabilidade, Custo e Gates de IA

Status: done

## Story

Como operador da plataforma,
quero observar uso, custo, latência, erro e qualidade da revisão por IA,
para que agentes/modelos sejam operados com segurança, governança e rastreabilidade sem expor dados sensíveis.

## Acceptance Criteria

1. **Telemetria segura de execução de IA**
   - **Given** uma execução de revisão automatizada concluída, bloqueada ou em fallback
   - **When** logs, auditoria e telemetria forem emitidos
   - **Then** registram tenant confiável, produto, canal, propósito, versão de agente/configuração/modelo/prompt, status, latência, fallback, custo e `correlation_id`
   - **And** não registram prompt bruto, payload bruto, output bruto, entrada minimizada com valor, CPF, CNPJ, nome, e-mail, endereço, telefone, token, segredo ou dado financeiro detalhado.

2. **Custo de IA em unidades inteiras e governadas**
   - **Given** execução consultiva com executor mockado ou futuro provedor real
   - **When** custo estimado/real for representado
   - **Then** usa inteiros `estimated_cost_units` e `actual_cost_units`, sem `float`, moeda real, billing, invoice ou preço comercial de fornecedor
   - **And** custo ausente deve ser explicitamente rastreável como não informado, sem inventar valor real.

3. **Métricas e traces técnicos com baixa cardinalidade**
   - **Given** instrumentação local/testável do `Automated Review Service`
   - **When** métricas e traces forem registrados
   - **Then** usam `creditos_observability`/OpenTelemetry já existente, atributos permitidos e cardinalidade controlada
   - **And** não criam Collector, Prometheus, Loki, Tempo, Grafana, Alertmanager, dashboard, endpoint público ou infraestrutura real nesta story.

4. **Separação entre observabilidade técnica e negócio/customer-facing**
   - **Given** dados de observabilidade da revisão automatizada
   - **When** forem preparados para uso futuro em dashboards ou projeções
   - **Then** permanecem minimizados e agregáveis para `Reporting & Insights`
   - **And** não expõem telemetria bruta, logs crus, traces crus, infraestrutura interna ou dados de outros tenants.

5. **Gates de governança contra autonomia da IA**
   - **Given** a suíte de governança de IA
   - **When** os testes rodam
   - **Then** falham se a IA aprovar, reprovar, alterar termos, executar callback, chamar ferramenta, acionar integração externa ou publicar decisão final
   - **And** continuam garantindo que a decisão final pertence ao `Decision Service` e à política determinística.

6. **Privacidade, isolamento e regressões de histórias anteriores**
   - **Given** as histórias 5.1 a 5.5 já implementadas
   - **When** a Story 5.6 adicionar telemetria/custo/gates
   - **Then** preserva configuração versionada, minimização de entrada, validação de saída, evidência consultiva, fallback seguro, idempotência e isolamento `bridge`
   - **And** mantém os gates Ruff, Pyright e testes unitários verdes.

7. **Sem ampliação indevida de escopo**
   - **Given** que esta story fecha o Epic 5 operacional
   - **When** o dev agent implementar
   - **Then** não adiciona provedor/modelo real, SDK externo de IA, NATS real, gRPC real, banco real, migration, outbox/inbox real, dashboard Grafana, métrica customer-facing final ou cobrança financeira
   - **And** qualquer necessidade dessas capacidades deve ser registrada como trabalho futuro/ADR.

## Tasks / Subtasks

- [x] CTOS-315 — Modelar métricas seguras de execução de IA (AC: 1, 2, 3, 6)
  - [x] Criar ou estender value object/estrutura fechada para metadados observáveis de revisão automatizada, sem `dict[str, Any]` livre como contrato principal.
  - [x] Representar `estimated_cost_units`, `actual_cost_units`, presença/ausência de custo, latência, status, fallback e refs de versão/configuração em formato log-safe.
  - [x] Reusar padrão da Story 3.5: custo em unidades inteiras, inteiro `>= 0`, sem `float`, moeda real ou preço comercial.
  - [x] Validar que qualquer provider/model ref seja técnico e não carregue segredo, chave, endpoint privado ou payload.

- [x] CTOS-316 — Emitir logs e auditoria minimizados de uso/custo (AC: 1, 2, 4, 6)
  - [x] Estender `_safe_execution_details(...)` ou função equivalente com campos seguros de uso/custo/latência, preservando `payload="[OMITIDO]"`.
  - [x] Incluir `provider_ref`, `model_ref`, `model_version`, `agent_version`, `prompt_fingerprint`, `output_validation_status`, fallback e contagens quando aplicável.
  - [x] Garantir que falhas/exceções externas não sejam logadas por mensagem bruta; mapear para códigos técnicos.
  - [x] Manter auditoria oficial separada: logs/métricas/traces não substituem `Audit & Evidence`.

- [x] CTOS-317 — Integrar telemetria técnica local sem infraestrutura real (AC: 1, 3, 4, 7)
  - [x] Reusar `packages/observability/src/creditos_observability/telemetry.py` e suas allowlists quando possível.
  - [x] Se a allowlist precisar crescer para IA, adicionar somente atributos de baixa cardinalidade e seguros.
  - [x] Criar instrumentação testável em memória para contadores/histogramas/spans, sem depender de Collector local.
  - [x] Evitar `tenant_id` como atributo de métrica de alta cardinalidade; quando necessário, manter em logs/auditoria/projeções curadas.

- [x] CTOS-318 — Criar gates de governança contra autonomia da IA (AC: 5, 6)
  - [x] Adicionar testes que rejeitam aprovação/reprovação, termos aprovados, callbacks, tool calls, integrações externas e publicação de decisão final.
  - [x] Cobrir caminhos `completed`, `blocked`, `fallback`, schema inválido, guardrail e executor failure.
  - [x] Garantir que `Decision Service` não seja importado/acoplado ao `Automated Review Service`.
  - [x] Preservar testes já existentes de `ReviewOutputItem`, `AutomatedReviewExecutionResult` e fallback.

- [x] CTOS-319 — Validar cardinalidade, tenant isolation e privacidade (AC: 1, 3, 4, 6)
  - [x] Criar testes negativos para atributos de telemetria com PII, segredo, payload bruto, prompt bruto e output bruto.
  - [x] Validar que `tenant_id` e `tenant_isolation_tier` continuam vindo de `PropagatedContext`/`ObservabilityContext` confiáveis.
  - [x] Cobrir que telemetria customer-facing futura deve usar projeções curadas, não Prometheus/Loki/Tempo/logs crus.
  - [x] Usar somente fixtures sintéticas e IDs técnicos.

- [x] CTOS-320 — Atualizar README, story e sincronização BMAD/Jira (AC: 6, 7)
  - [x] Atualizar `services/automated-review/README.md` com observabilidade/custo/gates da Story 5.6.
  - [x] Atualizar esta story com decisões locais, arquivos alterados, evidências de validação e achados de review.
  - [x] Atualizar `sprint-status.yaml` conforme avanço.
  - [x] Mover subtarefas Jira conforme execução (`Tarefas pendentes` → `Em andamento` → `Concluído`) e manter `CTOS-52` sincronizada.

### Review Findings

- [x] [Review][Patch] Tornar emissão de telemetria best-effort para não falhar após persistência/auditoria [services/automated-review/src/creditos_automated_review/application/service.py:551]
- [x] [Review][Patch] Fazer span técnico cobrir a execução consultiva real, não apenas a emissão de métrica [services/automated-review/src/creditos_automated_review/application/service.py:868]
- [x] [Review][Patch] Rejeitar subclasses de `ReviewModelUsage` para evitar polimorfismo em logs/auditoria [services/automated-review/src/creditos_automated_review/application/ports/consultative_review_executor.py:40]
- [x] [Review][Patch] Separar atributos de métricas e spans para evitar cardinalidade alta em métricas técnicas [packages/observability/src/creditos_observability/telemetry.py:19]
- [x] [Review][Patch] Validar `total_token_count` contra componentes individuais mesmo quando só um componente existir [services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py:127]
- [x] [Review][Patch] Renomear `token_counts_present` para alias log-safe sem acionar mascaramento por chave [services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py:161]
- [x] [Review][Patch] Registrar custo/uso como medições técnicas, não apenas flag de presença [services/automated-review/src/creditos_automated_review/application/service.py:1159]
- [x] [Review][Patch] Incluir versão da configuração executada na telemetria segura, preferencialmente em span [services/automated-review/src/creditos_automated_review/application/service.py:1159]

## Dev Notes

### Escopo desta story

- Esta story fecha o Epic 5 adicionando observabilidade operacional, custo técnico e gates de governança para revisão automatizada consultiva.
- A implementação deve permanecer local/testável: sem provedor real de IA, sem SDK externo, sem dashboard, sem infraestrutura Grafana/Prometheus/Collector e sem banco real.
- O foco é produzir metadados seguros, métricas/traces em memória quando útil, logs/auditoria minimizados e testes que impedem autonomia decisória da IA.
- Métrica técnica interna e métrica de negócio/customer-facing não são a mesma coisa: customer-facing deve ser projeção futura curada por `Reporting & Insights`, não exposição de telemetry backend.

### Contexto funcional consolidado

- Epic 5 define revisão por IA como evidência consultiva com guardrails, versionamento, auditoria e sem autonomia para decisão final. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Epic 5]
- Story 5.6 exige observar uso, custo, latência, erro e qualidade da revisão por IA, e criar gates que impeçam IA de aprovar, reprovar, alterar termos, chamar integração/callback ou publicar decisão final. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Story 5.6]
- A observabilidade do CreditOS usa OpenTelemetry como padrão, Collector como ponto de coleta/redaction e Grafana OSS como referência de stack; esta story não implementa essa infraestrutura. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]
- Dashboards customer-facing devem vir de projeções curadas por tenant e nunca de Prometheus, Loki, Tempo, logs crus, traces crus, payloads ou dados pessoais. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]
- Dados para IA/modelos próprios ficam no backlog futuro e devem ser minimizados, anonimizados ou pseudonimizados; esta story não cria datasets de treinamento. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/dados-modelos-ia-backlog-final.md`]

### Arquivos existentes a preservar

- `packages/observability/src/creditos_observability/telemetry.py`
  - Já fornece `InMemoryTelemetry`, `record_request(...)`, `start_span(...)`, sanitização via allowlist e recursos OpenTelemetry em memória.
  - `_METRIC_ATTRIBUTE_ALLOWLIST` é intencionalmente restrita. Se precisar expandir, adicionar apenas atributos seguros e de baixa cardinalidade.
  - `_SPAN_ATTRIBUTE_ALLOWLIST` permite `correlation_id` e `tenant_id`; métricas técnicas devem evitar cardinalidade explosiva por tenant.

- `packages/observability/src/creditos_observability/logging.py`
  - `build_structured_log(...)` já omite payload de comando e mascara `extra`.
  - Não bypassar `build_structured_log` para logs da aplicação.

- `services/automated-review/src/creditos_automated_review/application/service.py`
  - `_safe_config_details(...)`, `_safe_execution_details(...)` e `_safe_consultative_evidence_details(...)` centralizam metadados seguros.
  - `execute_consultative_review(...)` já mede duração com `monotonic()`, aplica contexto confiável, reserva idempotente, fallback e auditoria antes de commit.
  - `_publish_execution_audit(...)` recebe `config` para incluir metadados seguros de modelo/provedor.
  - Não logar `execution_input.input_for_execution`, prompt, payload, output ou exceção externa.

- `services/automated-review/src/creditos_automated_review/application/ports/consultative_review_executor.py`
  - `ConsultativeReviewOutput` hoje carrega `status`, refs legadas e `output_items`.
  - Se custo/uso do executor for modelado nesta story, manter contrato fechado, tipado, imutável e backward-compatible para testes existentes.

- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
  - `AutomatedReviewExecutionResult` continua consultivo e rejeita `final_decision`, `approved_terms` e `external_actions`.
  - Fallback exige `output_validation_status="blocked"`, limitation refs e contagens bloqueadas coerentes.

- `services/automated-review/tests/unit/test_consultative_review_execution.py`
  - Já cobre execução, minimização, evidência, fallback, metadata de modelo e não vazamento.
  - Adicionar testes nesta suíte antes de implementar mudanças de aplicação.

### Padrões arquiteturais obrigatórios

- Backend segue DDD + Hexagonal Architecture: domínio não depende de OpenTelemetry, logging framework, HTTP, gRPC, NATS, banco ou provider real.
- `Automated Review` é bounded context de revisão consultiva; `Decision` continua sendo fonte da decisão final e não deve ser importado por este serviço.
- Multi-tenancy `bridge`: `tenant_id` e `tenant_isolation_tier` vêm de contexto confiável, não de payload de IA.
- Logs, traces, métricas e dashboards devem respeitar mascaramento, minimização e isolamento por tenant.
- Auditoria oficial append-only pertence ao Epic 6/Audit & Evidence; telemetria operacional não substitui auditoria.

### Contrato sugerido de uso/custo de IA

- Reusar o padrão da Story 3.5 para custo:
  - `estimated_cost_units`: inteiro `>= 0`;
  - `actual_cost_units`: inteiro `>= 0`;
  - `cost_units_present` ou flag equivalente quando o mock/provedor informar custo;
  - sem `float`, `Decimal` monetário, moeda, cobrança, invoice ou preço real de fornecedor.
- Para uso do modelo, se necessário, preferir contagens inteiras seguras e opcionais:
  - `input_token_count`, `output_token_count`, `total_token_count` ou nomes equivalentes;
  - valores ausentes devem ficar ausentes ou marcados como não informados, nunca inferidos a partir de prompt bruto.
- Não registrar prompts, outputs ou mensagens do executor para calcular custo.

### Segurança e privacidade

- Nunca logar ou persistir prompt bruto, payload bruto, output bruto, exceção com conteúdo externo, CPF, CNPJ, nome, e-mail completo, endereço, telefone, documento, token, segredo, header sensível ou dado financeiro detalhado.
- Usar somente IDs técnicos e fixtures sintéticas (`tenant_alpha`, `proposal_001`, `provider_mock_ai`, `model_credit_review_mock`, etc.).
- Se um atributo de telemetria não estiver em allowlist explícita, ele deve ser omitido.
- Customer-facing futuro deve usar projeções agregadas e curadas; não expor `InMemoryTelemetry`, Prometheus, Loki, Tempo, spans, logs ou métricas brutas.

### Previous Story Intelligence

- Story 5.1 criou configuração versionada publicada e imutável, prompt fingerprint, guardrails e `ReviewModelRef` seguro.
- Story 5.2 criou execução consultiva minimizada, executor por port, reserva idempotente e persistência sem valores de entrada.
- Story 5.3 criou validação de saída, schema fechado, bloqueio de prompt injection, dados sensíveis, tool use e autonomia decisória.
- Story 5.4 criou `ConsultativeEvidence` apenas para execução `completed` e output `accepted`, com idempotência por execução e metadados de modelo quando aplicáveis.
- Story 5.5 criou fallback seguro, `fallback_action`, `fallback_reason_refs`, mapeamento de schema/guardrail/falha de executor e serialization de refs sem payload bruto.
- Correções recentes de review relevantes:
  - `automated_review_sensitive_reference` deve ser guardrail, não erro contratual;
  - `automated_review_invalid_technical_token` em output deve ser schema inválido;
  - fallback não pode conter achados aceitos, contagens aceitas positivas ou output accepted.

### Git Intelligence

- Branch base: `agent/story-5-6-observabilidade-custo-gates-ia`.
- Baseline: `6e0731c`, merge do PR #50 da Story 5.5.
- Commit inicial desta branch: `255c14a chore(bmad): start story 5.6`, contendo apenas a mudança inicial de `sprint-status.yaml`.
- Commits recentes reforçam padrão de PR pequeno, correção pós-review no mesmo PR, testes unitários focados e gates Ruff/Pyright antes de commit.

### Pesquisa técnica recente

- O projeto já usa `opentelemetry-api>=1.44.0` e `opentelemetry-sdk>=1.44.0` em `packages/observability/pyproject.toml`; não adicionar biblioteca nova para esta story sem ADR.
- A documentação oficial atual do OpenTelemetry mantém métricas por instrumentos como Counter/Histogram e recomenda atributos controlados; preserve a allowlist existente para evitar cardinalidade explosiva.
- Existem convenções semânticas oficiais para GenAI no OpenTelemetry, mas esta story não deve migrar para naming público definitivo se isso exigir contrato externo amplo; se usar nomes inspirados nessas convenções, manter escopo interno/testável e registrar decisão local.

### Testes e validações esperadas

- Testes focados:
  - `.venv/bin/pytest services/automated-review/tests/unit`
  - `.venv/bin/pytest packages/observability tests -q` apenas se tocar `packages/observability`
- Gates:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Se rodar `.venv/bin/pytest` completo, pode persistir falha ambiental conhecida do harness local por `uv: command not found`; registrar separadamente se ocorrer.

### Fora do escopo explícito

- Provedor/modelo real, SDK externo de IA, precificação real, moeda, billing, invoice ou centro de custo contábil.
- Dashboard Grafana, Prometheus real, Loki real, Tempo real, Collector real, Alertmanager, infraestrutura, IaC, Kubernetes ou deploy.
- Banco real, migration, outbox/inbox, NATS real, gRPC real ou endpoint público.
- Datasets de treinamento, feature store, avaliação de viés/drift real ou governança de modelos próprios.

### Checklist de implementação para o dev agent

- [ ] Antes de codificar, mover `CTOS-315` para `Em andamento`.
- [ ] Começar por testes RED de custo/telemetria/gates de autonomia.
- [ ] Reusar `creditos_observability` e padrões de custo da Story 3.5.
- [ ] Não criar dependência do domínio em OpenTelemetry.
- [ ] Não introduzir nova biblioteca ou infraestrutura sem aprovação/ADR.
- [ ] Atualizar README e esta story com arquivos alterados, decisões locais e evidências.
- [ ] Rodar `bmad-code-review` antes de commit/push/draft PR.

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

- `.venv/bin/pytest services/automated-review/tests/unit/test_consultative_review_execution.py -q` — 44 passed.
- `.venv/bin/pytest services/automated-review/tests/unit -q` — 63 passed.
- `.venv/bin/pytest tests/test_observability_foundation.py -q` — 8 passed.
- `.venv/bin/ruff format --check .` — 260 files already formatted.
- `.venv/bin/ruff check .` — All checks passed.
- `.venv/bin/pyright` — 0 errors, 0 warnings, 0 informations.

- `.venv/bin/pytest services/automated-review/tests/unit -q` — 65 passed.

- `.venv/bin/pytest tests/test_observability_foundation.py -q` — 8 passed após patches de review.

- `git diff --check` — sem whitespace errors.

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.
- Story detalhada com subtarefas Jira `CTOS-315` a `CTOS-320`.
- Jira `CTOS-52` está em `Em andamento` por solicitação operacional; subtarefas iniciam em `Tarefas pendentes`.
- Implementado `ReviewModelUsage` como contrato fechado e imutável para custo/uso de IA, com custos inteiros, ausência explícita e aliases log-safe para contagens do modelo.
- `ConsultativeReviewOutput` e `AutomatedReviewExecutionResult` agora propagam uso/custo sem ampliar autonomia decisória da IA.
- Logs, auditoria e telemetria técnica opcional registram metadados seguros de custo, latência, status, fallback e versões, preservando `payload="[OMITIDO]"` e sem prompt/output bruto.
- `creditos_observability` recebeu allowlist controlada para atributos técnicos de IA; métricas continuam sem `tenant_id`, enquanto spans mantêm rastreabilidade confiável.
- Gates de governança cobrem aprovação/reprovação, alteração de termos, callbacks, tool calls, integrações externas e publicação de decisão final por IA.
- Decisão local: campos de domínio mantêm `input_token_count`/`output_token_count`/`total_token_count`, mas logs/auditoria usam aliases `*_model_unit_count` para não acionar máscara sensível por nome de chave.
- Code review Step 02 concluído com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 8 achados patch aplicados.
- Telemetria tornou-se best-effort, com span cobrindo a execução consultiva e métricas de uso/custo como medições técnicas de baixa cardinalidade.
- `ReviewModelUsage` rejeita subclasses e valida `total_token_count` contra componentes individuais.

### File List

- `_bmad-output/implementation-artifacts/5-6-observabilidade-custo-e-gates-de-ia.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `packages/observability/src/creditos_observability/telemetry.py`
- `services/automated-review/README.md`
- `services/automated-review/src/creditos_automated_review/application/ports/consultative_review_executor.py`
- `services/automated-review/src/creditos_automated_review/application/service.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py`
- `services/automated-review/tests/unit/test_consultative_review_execution.py`

### Change Log

- 2026-09-11 — Story 5.6 detalhada por `bmad-create-story`, subtarefas Jira criadas e status BMAD atualizado para `ready-for-dev`.
- 2026-09-12 — Implementada observabilidade segura, custo técnico e gates de governança de IA; story movida para `review`.
- 2026-09-14 — Achados do `bmad-code-review` aplicados, validados e story movida para `done`.
