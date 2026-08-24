---
jira_issue: CTOS-37
branch: agent/story-3-5-registro-custo-resultado-integracao
baseline_commit: 71ae554
---

# Story 3.5: Registro de Custo e Resultado de Integração

Status: done

## Story

Como gestor de negócio ou operador,
quero registrar custo estimado/real e resultado das integrações,
para que o custo operacional por decisão e tenant possa ser acompanhado sem expor payloads sensíveis.

## Acceptance Criteria

1. **Registro canônico de custo por integração**
   - **Given** uma execução de integração com um ou mais jobs
   - **When** cada job produzir sucesso, falha, resultado parcial, ausência controlada, retry, fallback ou DLQ
   - **Then** registra, por tenant e execução, `product_type`, `integration_class`, `adapter_id`, `provider_id` quando configurado, chamadas, tentativas, fallback, status do resultado, custo estimado e custo real
   - **And** usa unidades inteiras controladas de custo, sem `float` monetário e sem depender de fornecedor real.

2. **Resultado projetável para Reporting & Insights**
   - **Given** uma execução finalizada
   - **When** o `Integration Service` publicar o resultado canônico
   - **Then** inclui uma projeção minimizada/agregável de custo e resultado para uso futuro pelo `Reporting & Insights`
   - **And** a projeção preserva `tenant_id`, `execution_id`, `correlation_id`, `trace_id`, `schema_version` e granularidade por classe/adapter.

3. **Idempotência e consistência**
   - **Given** uma mesma `idempotency_key` para uma execução já registrada
   - **When** a solicitação for repetida
   - **Then** retorna a execução existente e não duplica custo, chamadas, projeções ou eventos de resultado
   - **And** conflitos de fingerprint continuam sendo rejeitados.

4. **Privacidade e minimização**
   - **Given** qualquer retorno de adapter mock/sandbox ou falha controlada
   - **When** logs, eventos, projeções ou estruturas de custo forem serializados
   - **Then** não registram payload bruto, documento, nome, e-mail, endereço, token, segredo, headers, request/response body ou erro proprietário
   - **And** expõem apenas dados canônicos, agregáveis e log-safe.

5. **Observabilidade de negócio segura**
   - **Given** a execução de integração com custo registrado
   - **When** logs estruturados forem inspecionados
   - **Then** existem eventos operacionais seguros para custo/projeção, com `tenant_id`, produto, classe, adapter, status, tentativas, custo estimado/real e correlation/trace
   - **And** nenhum log substitui auditoria oficial nem consulta direta ao backend transacional de outro serviço.

6. **Compatibilidade futura com fornecedores reais**
   - **Given** que fornecedores nominais não serão escolhidos nesta story
   - **When** o modelo de custo for criado
   - **Then** suporta `provider_id` opcional e substituível, sem SDK, credencial, endpoint, contrato comercial ou lógica proprietária
   - **And** mantém fronteira de anti-corruption layer no `Integration Service`.

## Tasks / Subtasks

- [x] CTOS-37 — Implementar registro de custo e resultado de integração (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-207 — Modelar value objects de custo em unidades inteiras e `provider_id` opcional log-safe. (AC: 1, 4, 6)
  - [x] CTOS-208 — Criar entidade/projeção canônica de custo por job/execução sem payload bruto. (AC: 1, 2, 4)
  - [x] CTOS-209 — Estender contratos/portas de execução para publicar projeção minimizada para Reporting & Insights. (AC: 2, 5)
  - [x] CTOS-212 — Integrar o cálculo de custo estimado/real ao fan-in, retry, fallback e DLQ sem duplicidade idempotente. (AC: 1, 3)
  - [x] CTOS-210 — Atualizar adapters in-memory para carregar custo estimado a partir do plano e custo real mockado determinístico. (AC: 1, 6)
  - [x] CTOS-211 — Adicionar logs estruturados seguros para custo e resultado agregável. (AC: 4, 5)
  - [x] CTOS-213 — Reforçar guardrails de privacidade, tenant, DDD e ausência de fornecedor real. (AC: 3, 4, 6)
  - [x] CTOS-214 — Criar testes unitários/aplicação para custo, projeção, idempotência, falhas, DLQ e não vazamento. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-215 — Atualizar exports, README, sprint status, story file e Jira conforme avanço. (AC: 2, 5)

### Review Findings

- [x] [Review][Patch] Validar cardinalidade e fronteiras de `cost_records` antes de logar/publicar projeção [services/integration/src/creditos_integration/application/ports/integration_execution.py:57]
- [x] [Review][Patch] Propagar `provider_id` opcional configurável até o registro de custo [services/integration/src/creditos_integration/domain/entities/integration_plan.py:9]
- [x] [Review][Patch] Marcar DLQ como reprocessada antes de publicar custo/evento de reprocessamento [services/integration/src/creditos_integration/application/service.py:857]
- [x] [Review][Defer] Durabilidade transacional de projeção/outbox para custo e resultado [services/integration/src/creditos_integration/application/service.py:644] — deferred, pre-existing

## Dev Notes

### Escopo desta story

- Implementar registro **local/testável** de custo e resultado sobre o `Integration Service` já existente.
- Reutilizar `IntegrationPlanItem.estimated_cost_units`, `IntegrationExecution`, `IntegrationExecutionJob`, `IntegrationResult`, `IntegrationExecutionDispatchResult`, `IntegrationExecutionStore`, `IntegrationExecutionEvent` e publishers existentes.
- Preparar uma projeção minimizada para `Reporting & Insights`, sem implementar o serviço de Reporting, banco real, stream real ou dashboard.
- O custo real deve ser mockado/determinístico e representado em unidades inteiras; não usar `float`, moeda real, arredondamento financeiro ou preço comercial de fornecedor.
- `provider_id` é opcional e deve ser um identificador técnico log-safe quando existir; não escolher fornecedor real nesta story.

### Fora de escopo explícito

- Não selecionar fornecedores externos, SDKs, contratos comerciais, endpoints reais ou credenciais.
- Não implementar billing, invoice, cobrança, moeda, impostos, margem, centro de custo contábil ou precificação de cliente.
- Não implementar `Reporting & Insights Service`; apenas publicar/projetar dados minimizados para consumo futuro.
- Não criar banco real, migration, tópico NATS real, AsyncAPI final ou dashboard Grafana/customer-facing.
- Não alterar `Decision Service` nem acoplar decisão a payload proprietário de integração.

### Estado atual que deve ser preservado

- `start_integration_execution` valida ambiente não produtivo, tenant confiável, escopo `integration_execution:start`, plano `ready`, cenário normalizado, fingerprint seguro, reserva idempotente atômica, preflight, fan-out/fan-in e logs seguros.
- `InMemoryIntegrationExecutionStore.reserve_or_get` impede execução duplicada para a mesma `idempotency_key` e rejeita conflito de fingerprint.
- `InMemoryIntegrationExecutionDispatcher` executa jobs em paralelo, aplica retry/backoff/jitter determinístico, classifica falhas, registra DLQ e retorna `IntegrationExecutionDispatchResult`.
- `IntegrationResult.to_log_safe_dict()` já omite `summary`; não reintroduzir payload bruto por outro caminho.
- `IntegrationExecutionEvent` já possui envelope CloudEvents-like com `data` minimizado; a extensão de custo deve permanecer agregável e versionada.
- Story 3.4 deixou item deferido: timeout com cancelamento/deadline real de adapter travado; não resolver nesta story salvo se estritamente necessário para custo.

### Modelo de domínio sugerido

Preferir criar value objects em `services/integration/src/creditos_integration/domain/value_objects/result.py` ou `execution.py`:

- `validate_cost_units(value)`: inteiro `>= 0`, limite superior explícito e código de erro controlado.
- `validate_call_count(value)`: inteiro `>= 0`, compatível com tentativa inicial, retries e resultado terminal.
- `validate_provider_id(value)`: opcional; aceitar apenas identificador técnico hash-safe, sem e-mail, CPF, CNPJ, URL com segredo, token ou nome de pessoa.

Preferir criar uma entidade/projeção canônica em `services/integration/src/creditos_integration/domain/entities/integration_execution.py` ou arquivo dedicado se ficar mais claro:

- `IntegrationExecutionCostRecord`
  - `execution_id`
  - `job_id`
  - `tenant_id`
  - `product_type`
  - `integration_class`
  - `adapter_id`
  - `provider_id | None`
  - `result_status`
  - `call_count`
  - `attempt_count`
  - `fallback_strategy`
  - `estimated_cost_units`
  - `actual_cost_units`
  - `schema_version`
  - `correlation_id`
  - `trace_id`

Não adicionar campos livres como `payload`, `raw_payload`, `provider_response`, `request_body`, `response_body`, `headers`, `exception`, `stack_trace`, `metadata` sem schema fechado ou `dict[str, Any]` com conteúdo externo.

### Regras de cálculo sugeridas

- `estimated_cost_units` vem de `IntegrationPlanItem.estimated_cost_units`.
- `actual_cost_units` no mock pode ser determinístico:
  - `0` quando não houve chamada externa real/simulada;
  - `estimated_cost_units * call_count` para execução mockada concluída, parcial, ausente ou falha controlada;
  - manter regra explícita e testável para retries e DLQ.
- `call_count` deve refletir chamadas/tentativas efetivamente executadas pelo dispatcher, sem duplicar em idempotency hit.
- `attempt_count` deve continuar vindo do job terminal, respeitando Story 3.4.
- Fallback deve registrar `fallback_strategy` do item/job, mesmo que fallback real completo ainda não exista.
- Resultado final deve usar status canônico (`completed`, `partial`, `not_found`, `failed`) e reason codes controlados já existentes.

### Portas e eventos sugeridos

Atualizar `services/integration/src/creditos_integration/application/ports/integration_execution.py`:

- Criar evento/projeção específica, por exemplo `IntegrationExecutionCostProjection`, ou estender `IntegrationExecutionEvent.data` com `cost_summary` e `cost_records`.
- Se criar publisher dedicado, manter protocolo simples como `IntegrationCostProjectionPublisher.publish(event)`.
- Implementar publisher in-memory em testes, se necessário.

Evento/projeção mínima sugerida:

- `type`: `creditos.integration.execution.cost_recorded.v1` ou campo equivalente no evento de execução.
- `source`: `integration`.
- `subject`: `integration-execution/{execution_id}`.
- `data`: `execution_id`, `product_type`, `status`, `job_count`, `result_count`, `total_estimated_cost_units`, `total_actual_cost_units`, `records`.

### Logs e observabilidade

- Adicionar log estruturado como `integration_execution.cost_recorded` ou `integration_execution.result_projected`.
- Extras permitidos: IDs técnicos, tenant, produto, classe, adapter, provider técnico opcional, status, chamadas, tentativas, custo estimado/real, schema, correlation/trace.
- Não usar logs como fonte oficial de auditoria; projeção de negócio deve ser consumível por Reporting no futuro.
- Métricas de negócio customer-facing derivam de projeções curadas, não de Prometheus/Loki/Tempo ou bancos transacionais.

### Regras arquiteturais obrigatórias

- Todo backend segue DDD + arquitetura hexagonal; domínio não importa FastAPI, Pydantic, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, `requests` ou `httpx`.
- `Integration` continua sendo o único bounded context autorizado a falar com provedores externos.
- `Decision` e `Reporting` não recebem payload proprietário; apenas resultado/custo canônico versionado.
- Multi-tenancy `bridge`: todo registro e projeção deve carregar `tenant_id` confiável do contexto/execução e impedir cross-tenant.
- Idempotência continua obrigatória; idempotency hit não pode publicar custo/projeção duplicado.
- Dados sensíveis devem ser omitidos, mascarados, tokenizados ou agregados antes de logs/projeções.

### Anti-padrões proibidos

- Não criar custo com `float`, `Decimal` monetário sem decisão, string de moeda ou preço real de fornecedor.
- Não escolher nomes de fornecedores reais para satisfazer `provider_id`.
- Não adicionar dependência nova para dinheiro/billing/analytics.
- Não persistir `summary` inteiro do adapter, payload de mock, exceptions, headers ou request/response body.
- Não calcular custo fora do `Integration Service`.
- Não quebrar testes de fan-out/fan-in, retry/DLQ/reprocessamento ou idempotência.

### Arquivos provavelmente afetados

- `services/integration/src/creditos_integration/domain/value_objects/result.py`
- `services/integration/src/creditos_integration/domain/value_objects/execution.py`
- `services/integration/src/creditos_integration/domain/entities/integration_execution.py`
- `services/integration/src/creditos_integration/domain/entities/integration_result.py`
- `services/integration/src/creditos_integration/application/ports/integration_execution.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`
- `services/integration/src/creditos_integration/adapters/external/in_memory_mock_integration_adapter.py`
- `services/integration/tests/unit/test_integration_async_execution.py`
- `services/integration/tests/unit/test_integration_resilience.py`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/**/__init__.py` quando houver novo export público.

### Testes mínimos esperados

- Execução concluída registra custo estimado/real por job e total por execução.
- Resultado parcial, `not_found`, falha controlada, retry excedido e DLQ preservam custo/call count/tentativas corretamente.
- Idempotency hit retorna execução existente sem duplicar projeção/evento/log de custo.
- `provider_id` inválido ou sensível é rejeitado/omitido conforme regra definida.
- Serialização de logs/projeções não contém CPF, CNPJ, e-mail, nome real, token, segredo, payload bruto, `summary` inteiro, headers, request/response body, exceção ou stack trace.
- Gates existentes continuam passando: `ruff format --check .`, `ruff check .`, `pyright`, `pytest -q`.

### Project Structure Notes

- Manter código do domínio em `services/integration/src/creditos_integration/domain`.
- Manter portas em `services/integration/src/creditos_integration/application/ports`.
- Manter orquestração de caso de uso em `services/integration/src/creditos_integration/application/service.py`.
- Manter adapters in-memory em `services/integration/src/creditos_integration/adapters`.
- Não criar pacote compartilhado novo para custo nesta story.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 3, Story 3.5.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/integracoes-externas-oq8.md` — modelo de custo por operação e não escolha de fornecedores.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md` — dashboard de negócio “Integrações e custo” e regra de projeções customer-facing.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — DDD, hexagonal, ownership do `Integration Service`, eventos e Reporting.
- `_bmad-output/implementation-artifacts/3-4-resiliencia-retry-dlq-e-reprocessamento-controlado.md` — base imediata de retry, DLQ, reprocessamento e aprendizados pós-review.
- `pyproject.toml` — Python 3.13, Ruff, Pyright, Pytest e workspace `uv`.

### Git Intelligence

- Baseline: `71ae554`, `main` sincronizada após merge do PR #35.
- Branch de desenvolvimento criada no início: `agent/story-3-5-registro-custo-resultado-integracao`.
- Autor local obrigatório: `Andre Tachian <altachian@gmail.com>`.
- Commits recentes reforçam padrão de correções pós-review, testes de privacidade e gates completos; manter patch pequeno e reviewable.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- 2026-08-24 — `CTOS-36` movida para `Concluído` no Jira após merge do PR #35.
- 2026-08-24 — Branch `agent/story-3-5-registro-custo-resultado-integracao` criada a partir de `main` em `71ae554`.
- 2026-08-24 — `bmad-create-story` executado para detalhar a Story 3.5 antes da implementação.
- 2026-08-24 — `CTOS-37` atualizado no Jira; subtarefas `CTOS-207` a `CTOS-215` criadas antes de codificar.
- 2026-08-24 — `CTOS-37` movida para `Em andamento`; subtarefas permanecem em TODO até início da implementação.
- 2026-08-24 — `CTOS-207` movida para `Em andamento`; implementação da Story 3.5 iniciada pelo fluxo `bmad-dev-story`.
- 2026-08-24 — Testes vermelhos criados para custo/projeção/idempotência/DLQ; `CTOS-207` implementada e movida para `Concluído`; `CTOS-208` movida para `Em andamento`.
- 2026-08-24 — Gates finais executados: `ruff format --check .`, `ruff check .`, `pyright`, `pytest services/integration/tests/unit -q` e `pytest -q`.
- 2026-08-24 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; três findings de patch corrigidos e revalidados.

### Completion Notes List

- Story 3.5 detalhada com base no Epic 3, OQ-8, OQ-9, Architecture Spine e Story 3.4.
- Escopo delimitado para custo/projeção local e testável, sem fornecedor real, billing, banco real, NATS real ou dashboard.
- Guardrails adicionados para custo em unidades inteiras, idempotência, privacidade, DDD, multi-tenancy e ausência de payload bruto.
- `IntegrationExecutionCostRecord` criado como projeção canônica log-safe por job, com `provider_id` técnico opcional, custo estimado/real em inteiros, chamadas e tentativas.
- Dispatcher in-memory passa a devolver `cost_records`; fan-in publica resumo minimizado no evento interno e loga `integration_execution.cost_recorded`.
- Idempotência preservada: replay não duplica custo/projeção/log/evento e mudança de `estimated_cost_units` passa a alterar o fingerprint.
- Testes adicionados para evento minimizado, não duplicidade idempotente, rejeição de `provider_id` sensível, conflito por custo alterado e custo real com retry/DLQ.
- Review findings resolvidos: `cost_records` agora são obrigatórios/validados contra a execução, `provider_id` é configurável e propagado até o custo, e DLQ é marcada antes de publicar evento/projeção de reprocessamento.

### File List

- `_bmad-output/implementation-artifacts/3-5-registro-de-custo-e-resultado-de-integracao.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/application/ports/integration_execution.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/integration_configuration.py`
- `services/integration/src/creditos_integration/domain/entities/integration_execution.py`
- `services/integration/src/creditos_integration/domain/entities/integration_plan.py`
- `services/integration/src/creditos_integration/domain/value_objects/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/execution.py`
- `services/integration/tests/unit/test_integration_async_execution.py`
- `services/integration/tests/unit/test_integration_catalog.py`
- `services/integration/tests/unit/test_integration_resilience.py`

### Change Log

- 2026-08-24 — Story 3.5 criada e marcada como `ready-for-dev`.
- 2026-08-24 — Story 3.5 implementada e marcada como `review`.
- 2026-08-24 — Findings de code review corrigidos; Story 3.5 marcada como `done`.
