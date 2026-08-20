---
jira_issue: CTOS-35
branch: agent/story-3-3-execucao-assincrona-com-fan-out-fan-in
baseline_commit: 406533c
---

# Story 3.3: Execução Assíncrona com Fan-out/Fan-in

Status: done

## Story

Como `Decision Service`,
quero solicitar enriquecimento externo de forma assíncrona e paralelizável,
para que múltiplas fontes sejam consultadas dentro de limites controlados e consolidadas em um resultado canônico rastreável.

## Acceptance Criteria

1. **Disparo assíncrono governado**
   - **Given** um `IntegrationPlan` com status `ready`, itens independentes e tenant confiável
   - **When** o comando `integration.execute` for iniciado pela aplicação
   - **Then** o `Integration Service` cria uma execução técnica rastreável e jobs por classe/adapter
   - **And** rejeita plano vazio, plano não pronto, cross-tenant, item inconsistente ou execução sem escopo autorizado.

2. **Fan-out paralelizável com limites**
   - **Given** múltiplos itens no plano
   - **When** os jobs forem despachados
   - **Then** cada job preserva `tenant_id`, `product_type`, `integration_class`, `adapter_id`, `timeout_ms`, `max_attempts`, `max_concurrency`, `correlation_id`, `trace_id` e `schema_version`
   - **And** a execução respeita limite de concorrência efetivo sem criar execução ilimitada.

3. **Fan-in canônico**
   - **Given** jobs concluídos com sucesso, falha parcial, ausência ou falha
   - **When** o fan-in consolidar os resultados
   - **Then** publica/retorna um resultado de execução canônico com status `completed`, `partial`, `missing` ou `failed`
   - **And** inclui resultados normalizados por classe/adapter, tentativas observadas e versão de schema sem payload bruto.

4. **Idempotência de execução**
   - **Given** a mesma `idempotency_key`, tenant, produto e plano
   - **When** o comando `integration.execute` for repetido
   - **Then** retorna a mesma execução sem duplicar jobs
   - **And** rejeita a reutilização da mesma `idempotency_key` para plano ou contexto diferente.

5. **Observabilidade segura**
   - **Given** execução aceita, rejeitada, job despachado e fan-in concluído
   - **When** logs estruturados forem inspecionados
   - **Then** há rastreabilidade por tenant, produto, classe, adapter, execução, correlação, trace, status e duração
   - **And** não há CPF, CNPJ, e-mail completo, nome real, token, secret, credencial, payload bruto ou resposta proprietária.

6. **Compatibilidade com NATS/CloudEvents sem antecipar infra**
   - **Given** a arquitetura adotou NATS JetStream, CloudEvents e AsyncAPI
   - **When** a execução assíncrona for modelada nesta story
   - **Then** comandos/jobs/eventos internos usam nomes, envelopes e metadados compatíveis com essa evolução
   - **And** não adicionam broker real, worker real, DLQ, replay ou contrato AsyncAPI final nesta story.

## Tasks / Subtasks

- [x] CTOS-35 — Detalhar e implementar execução assíncrona com fan-out/fan-in (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-189 — Modelar entidades/value objects de execução e job assíncrono. (AC: 1, 2, 3, 4)
  - [x] CTOS-190 — Criar portas hexagonais para dispatch, idempotência e consolidação de jobs. (AC: 1, 2, 4, 6)
  - [x] CTOS-191 — Implementar adapter in-memory assíncrono/paralelizável sobre mocks da Story 3.2. (AC: 2, 3, 6)
  - [x] CTOS-192 — Implementar caso de uso `start_integration_execution` com `idempotency_key` e tenant confiável. (AC: 1, 4, 5)
  - [x] CTOS-193 — Implementar fan-in e status canônico de execução. (AC: 3)
  - [x] CTOS-194 — Adicionar logs estruturados e métricas seguras de execução/job/fan-in. (AC: 5)
  - [x] CTOS-195 — Reforçar guardrails para payload sensível, produção indevida e fronteiras DDD. (AC: 1, 5, 6)
  - [x] CTOS-196 — Criar testes unitários e de aplicação para paralelismo, idempotência, fan-in, erros e logs seguros. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-197 — Atualizar exports, README, sprint status, story file e Jira conforme avanço. (AC: 5, 6)

### Review Findings

- [x] [Review][Patch] Reservar idempotência de forma atômica antes do dispatch [services/integration/src/creditos_integration/application/service.py:479]
- [x] [Review][Patch] Converter exceções de adapter em resultado canônico de fan-in [services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py:69]
- [x] [Review][Patch] Aplicar deadline/timeout por job ou explicitar status `timed_out` como falha canônica [services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py:69]
- [x] [Review][Patch] Bloquear CPF/CNPJ formatado em `idempotency_key` [services/integration/src/creditos_integration/domain/value_objects/execution.py:69]
- [x] [Review][Patch] Normalizar fingerprint com cenários padrão e ordenação semântica do plano [services/integration/src/creditos_integration/application/service.py:468]
- [x] [Review][Patch] Validar `correlation_id` e `trace_id` dos resultados contra o contexto da execução [services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py:157]
- [x] [Review][Patch] Validar no domínio que resultados pertencem aos jobs e não há órfãos/duplicados [services/integration/src/creditos_integration/domain/entities/integration_execution.py:217]
- [x] [Review][Patch] Calcular fan-in considerando obrigatoriedade/fallback para falhas opcionais [services/integration/src/creditos_integration/domain/entities/integration_execution.py:272]
- [x] [Review][Patch] Modelar envelope interno compatível com CloudEvents/NATS sem broker real [services/integration/src/creditos_integration/application/ports/integration_execution.py:57]
- [x] [Review][Patch] Remover terminologia de replay para idempotência, pois replay real é fora de escopo [services/integration/src/creditos_integration/application/service.py:492]
- [x] [Review][Patch] Emitir log `integration_execution.start` aceito para execução nova [services/integration/src/creditos_integration/application/service.py:541]

## Dev Notes

### Escopo desta story

- Esta story implementa a camada de aplicação e domínio para **execução assíncrona local/testável** de um `IntegrationPlan` usando fan-out/fan-in.
- A implementação deve reutilizar a base da Story 3.2: `ExecuteMockIntegrationCommand`, `execute_mock_integration_plan`, `IntegrationPlan`, `IntegrationPlanItem`, `IntegrationResult` e `MockIntegrationAdapterRegistry`.
- A execução deve ser preparada para evolução com NATS JetStream, mas o entregável desta story deve ser verificável sem infraestrutura externa.
- A estratégia recomendada é criar portas de mensageria/dispatch e um adapter in-memory assíncrono determinístico, usando `asyncio` da biblioteca padrão quando útil, sem adicionar dependência externa por padrão.

### Fora de escopo explícito

- Não implementar broker NATS JetStream real, cluster local, consumer durável real, stream real ou configuração de infra.
- Não implementar retry/backoff/jitter, DLQ, replay ou reprocessamento controlado; isso pertence à Story 3.4.
- Não implementar persistência real, migration, transactional outbox/inbox real ou banco de jobs; isso deve ser tratado em stories/ADRs posteriores.
- Não implementar custo real por fornecedor; isso pertence à Story 3.5.
- Não implementar contrato AsyncAPI final nem gates de contrato assíncrono; isso pertence à Story 3.6.
- Não escolher fornecedor externo real, SDK externo ou payload proprietário.

### Estado atual que deve ser preservado

- `IntegrationPlanItem` já possui `timeout_ms`, `max_attempts`, `max_concurrency`, `estimated_cost_units`, `fallback_strategy` e `configuration_id`.
- `execute_mock_integration_plan` já valida ambiente não produtivo, tenant confiável, escopo `integration_mock:execute`, plano `ready`, itens do plano, adapter registrado e resultado canônico.
- `IntegrationResult` já possui schema versionado, status controlado, cenário sintético, summary allowlist, `correlation_id`, `trace_id`, janela temporal e `duration_ms`.
- O domínio do `Integration Service` não deve importar FastAPI, Pydantic, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, `requests` ou `httpx`.

### Modelo de execução sugerido

Criar uma entidade/value object de domínio, por exemplo `IntegrationExecution`, com campos:

- `execution_id`: identificador técnico seguro, prefixo sugerido `iexec_`.
- `tenant_id`: sempre vindo de `ObservabilityContext`.
- `product_type`: produto MVP validado.
- `plan_fingerprint`: hash estável do plano executável, sem payload sensível.
- `idempotency_key`: chave técnica exigida no comando de execução.
- `status`: enum controlado, por exemplo `accepted`, `running`, `completed`, `partial`, `missing`, `failed`.
- `schema_version`: iniciar com `1.0`.
- `job_ids`: tupla de jobs criados.
- `correlation_id`, `trace_id`.
- `started_at`, `completed_at`, `duration_ms`.

Criar uma entidade/value object de domínio, por exemplo `IntegrationExecutionJob`, com campos:

- `job_id`: identificador técnico seguro, prefixo sugerido `ijob_`.
- `execution_id`.
- `tenant_id`, `product_type`, `integration_class`, `adapter_id`.
- `configuration_id`, `requirement`, `timeout_ms`, `max_attempts`, `max_concurrency`, `fallback_strategy`.
- `status`: enum controlado, por exemplo `pending`, `running`, `completed`, `partial`, `missing`, `failed`, `timed_out`.
- `attempt_count`: iniciar em `1` nesta story; retries reais ficam para 3.4.
- `result_id`: preenchido quando houver `IntegrationResult`.
- `correlation_id`, `trace_id`.

### Comandos/casos de uso sugeridos

Criar comando de aplicação, por exemplo `StartIntegrationExecutionCommand`:

- `plan`: `IntegrationPlan`.
- `idempotency_key`: obrigatória, técnica e validada.
- `scenario_by_class`: mapeamento opcional de classe para cenário controlado, herdando a semântica da Story 3.2.
- `synthetic_subject_reference`: referência técnica sintética; nunca CPF, CNPJ, e-mail, nome, telefone, endereço, token ou secret.
- `scopes`: deve exigir escopo específico, por exemplo `integration_execution:start`.

Criar caso de uso, por exemplo `start_integration_execution(command, context=...)`:

- Rejeita `plan.status != "ready"`, plano sem itens, cross-tenant e itens com tenant/produto divergentes.
- Rejeita execução sem registry/adapter de mock configurado quando o adapter in-memory for usado.
- Faz preflight completo antes de despachar qualquer job.
- Gera `execution_id` e `job_id` determinísticos por factory/clock injetáveis em testes.
- Aplica idempotência antes de despachar jobs.
- Executa jobs paralelizáveis no adapter in-memory respeitando concorrência efetiva.
- Consolida resultados em fan-in com status canônico da execução.

### Portas e adapters sugeridos

Criar portas em `services/integration/src/creditos_integration/application/ports/`:

- `IntegrationExecutionDispatcher`: despacha jobs e coleta resultados sem acoplar a NATS real.
- `IntegrationExecutionStore` ou `IntegrationExecutionIdempotencyStore`: registra execução por tenant + `idempotency_key` + fingerprint do plano.
- `IntegrationExecutionResultPublisher`: porta opcional para publicar resultado canônico; implementação in-memory pode apenas registrar eventos seguros.

Criar implementação em `services/integration/src/creditos_integration/adapters/events/`:

- `in_memory_integration_execution_dispatcher.py`: adapter local, determinístico, sem rede e sem broker real.

### Convenções assíncronas compatíveis com NATS/CloudEvents

Usar nomes de comandos/eventos compatíveis com a arquitetura, sem prometer publicação real nesta story:

- `creditos.integration.command.execute.v1`
- `creditos.integration.job.requested.v1`
- `creditos.integration.job.completed.v1`
- `creditos.integration.execution.completed.v1`
- `creditos.integration.execution.partial.v1`
- `creditos.integration.execution.failed.v1`

Metadados mínimos compatíveis com CloudEvents:

- `specversion`, `id`, `type`, `source`, `subject`, `time`, `datacontenttype`, `tenant_id`, `correlation_id`, `trace_id`, `schema_version`, `data`.

### Regras arquiteturais obrigatórias

- Todo backend segue DDD + arquitetura hexagonal; domínio não importa framework, transporte, banco, observabilidade, SDK externo ou broker.
- `Decision` não deve receber nem conhecer payload proprietário de fornecedor; somente resultado canônico versionado.
- A execução deve usar `tenant_id` confiável do contexto; nunca aceitar tenant vindo do payload como autoridade.
- Jobs devem carregar apenas metadados mínimos e referências técnicas sintéticas.
- Logs estruturados devem usar `creditos-observability` e omitir payload bruto por padrão.
- Métricas sugeridas devem evitar cardinalidade excessiva: tenant, produto, classe, adapter, status e duração em buckets são aceitáveis; CPF/CNPJ/e-mail/referência de sujeito não são dimensões.

### Anti-padrões proibidos

- Não adicionar `nats-py`, broker real ou docker compose de NATS nesta story sem ADR/justificativa explícita.
- Não usar `requests`, `httpx`, SDK de fornecedor, rede, arquivo externo ou segredo.
- Não criar campos livres como `raw_payload`, `payload`, `metadata`, `attributes`, `custom`, `provider_response` ou `external_response`.
- Não executar parte dos jobs se o preflight global falhar.
- Não duplicar jobs para a mesma `idempotency_key` válida.
- Não mascarar problema de fan-in parcial como sucesso total.
- Não implementar retry, DLQ ou replay nesta story.

### Arquivos esperados

Prováveis arquivos novos:

- `services/integration/src/creditos_integration/domain/entities/integration_execution.py`
- `services/integration/src/creditos_integration/domain/value_objects/execution.py`
- `services/integration/src/creditos_integration/application/ports/integration_execution.py`
- `services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`
- `services/integration/tests/unit/test_integration_async_execution.py`

Prováveis arquivos a atualizar:

- `services/integration/src/creditos_integration/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/__init__.py`
- `services/integration/src/creditos_integration/application/__init__.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/adapters/events/__init__.py`
- `services/integration/README.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Esta story file.

### Testes obrigatórios

Adicionar/atualizar testes para:

- Execução cria um `execution_id` e um job por item do plano.
- Jobs preservam tenant, produto, classe, adapter, timeout, concorrência, correlation ID, trace ID e schema version.
- Fan-out não executa nenhum adapter se o preflight global encontrar plano inválido, classe desconhecida, adapter ausente ou cross-tenant.
- Fan-in retorna `completed` quando todos os resultados completam.
- Fan-in retorna `partial` quando houver combinação controlada de sucesso e parcial/ausente/falha opcional.
- Fan-in retorna `failed` quando integração obrigatória falhar de forma final nesta story.
- Repetição com mesma `idempotency_key` e mesmo fingerprint retorna a mesma execução e não duplica jobs.
- Reutilização da mesma `idempotency_key` com fingerprint diferente é rejeitada com erro seguro.
- Limite de concorrência efetivo é respeitado no adapter in-memory.
- Logs e resultados não contêm CPF, CNPJ, e-mail completo, nome real, token, secret, credencial, `raw_payload`, `provider_response` ou payload proprietário.
- Domínio continua sem imports de infraestrutura; manter teste de fronteira DDD.

Comandos de validação esperados:

- `.venv/bin/python -m pytest services/integration/tests -q`
- `PATH=/tmp/creditos-uv-shim:$PATH uv lock --check`
- `.venv/bin/python scripts/check_contracts.py`
- `.venv/bin/ruff check .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/pyright`
- Se a `.venv` local continuar quebrada, registrar limitação e executar ao menos `ruff`, `ruff format --check`, `compileall`, `git diff --check` e teste de fronteira DDD com `python3`.

### Previous Story Intelligence

Da Story 3.2:

- O mock/sandbox é local, determinístico e não produtivo; fan-out/fan-in real ainda não foi implementado.
- `IntegrationResult` já valida status, cenário, reason codes, summary allowlist, schema, classe/adapter e duração.
- `execute_mock_integration_plan` já faz preflight completo antes de executar adapters e rejeita cenários/classes fora do plano.
- A execução mock exige escopo `integration_mock:execute`; a execução assíncrona deve ter escopo próprio para evitar ampliação indevida.
- O ambiente produtivo rejeita mock/sandbox; esta story não deve abrir caminho para chamadas externas reais.
- A `.venv` esteve quebrada em sessões anteriores por symlink ausente para `/tmp/creditos-uv-python`; registrar novamente se persistir.

### Git Intelligence

- Branch base: `406533c`, merge do PR #33 da Story 3.2.
- Branch de desenvolvimento já criada e publicada: `agent/story-3-3-execucao-assincrona-com-fan-out-fan-in`.
- Autor local obrigatório: `Andre Tachian <altachian@gmail.com>`.
- Estratégia do projeto: branch no início da story; commit/push/draft PR ao final da implementação da story.

### Latest Technical Information

- NATS JetStream usa streams persistidos e consumers duráveis/efêmeros; pull consumers são adequados para processamento horizontal escalável e ack explícito informa reentrega. Fonte oficial: https://docs.nats.io/using-nats/jetstream/develop_jetstream
- A documentação oficial do NATS recomenda usar JetStream publish/ack para garantir entrega quando confiabilidade importa; buffers de cliente não substituem confirmação de persistência. Fonte oficial: https://docs.nats.io/using-nats/developer/connecting/reconnect/buffer
- CloudEvents define atributos obrigatórios como `id`, `source`, `specversion` e `type`; `subject` e `datacontenttype` são atributos úteis para roteamento e contrato. Fonte oficial: https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md
- AsyncAPI 3.1.0 é a versão estável mais recente observada para documentação de APIs assíncronas; contratos finais pertencem à Story 3.6. Fonte oficial: https://github.com/asyncapi/spec

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 3, Story 3.3 e dependências 3.4–3.6.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-10 sobre integrações externas, fan-out/fan-in, limites, custo, retry, DLQ e observabilidade.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md` — NATS JetStream, CloudEvents, AsyncAPI, outbox/inbox e topologia AWS de referência.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/recomendacoes-decisoes-abertas.md` — premissa de integrações externas assíncronas e paralelizáveis.
- `_bmad-output/implementation-artifacts/3-2-adapter-mock-sandbox-para-integracoes-externas.md` — base mock/sandbox e aprendizados da story anterior.
- `services/integration/README.md` — escopo atual do `Integration Service`.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- 2026-08-20 — `bmad-create-story` executado para detalhar a Story 3.3 antes da implementação.
- 2026-08-20 — `bmad-dev-story` iniciado; `CTOS-189` movida para WIP no Jira.
- `.venv/bin/python -m pytest services/integration/tests/unit/test_integration_async_execution.py -q` — não executado: `.venv/bin/python` aponta para runtime ausente em `/tmp/creditos-uv-python`.
- `PYTHONPATH=services/integration/src:packages/observability/src:packages/security/src python3 -m pytest services/integration/tests/unit/test_integration_async_execution.py -q` — não executado: Python local sem `pytest`.
- `PYTHONPATH=services/integration/src:packages/observability/src:packages/security/src python3 -m compileall -q services/integration/src/creditos_integration services/integration/tests/unit/test_integration_async_execution.py` — passed.
- `.venv/bin/ruff check services/integration/src services/integration/tests/unit/test_integration_async_execution.py` — passed.
- `.venv/bin/ruff format services/integration/src services/integration/tests/unit/test_integration_async_execution.py` — 1 arquivo reformatado.
- `.venv/bin/ruff format --check services/integration/src services/integration/tests/unit/test_integration_async_execution.py` — passed.
- `python3` AST boundary check para `services/integration/src/creditos_integration/domain` — `offenders=[]`.
- `.venv/bin/python -m pytest services/integration/tests -q` — não executado: runtime da venv ausente.
- `.venv/bin/pyright services/integration/src services/integration/tests/unit/test_integration_async_execution.py` — não executado: binário depende do runtime ausente da venv.
- `PATH=/tmp/creditos-uv-shim:$PATH uv lock --check` — não executado: `uv` não encontrado no PATH local.
- `.venv/bin/python scripts/check_contracts.py` — não executado: runtime da venv ausente.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — passed.
- `.venv/bin/pytest services/integration/tests/unit/test_integration_async_execution.py` — não executado: shebang aponta para runtime ausente da venv.
- `PYTHONPATH=services/integration/src:packages/observability/src:packages/security/src python3 -m compileall -q services/integration/src/creditos_integration services/integration/tests/unit/test_integration_async_execution.py` — passed após revisão.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && PYTHONPATH=services/integration/src:packages/observability/src:packages/security/src python3 -m compileall -q services/integration/src/creditos_integration services/integration/tests/unit/test_integration_async_execution.py && git diff --check` — passed após patches de revisão.
- Smoke manual com stubs de OpenTelemetry — passed após patches para execução completa, reserva/reutilização idempotente com cenários padrão explícitos, conflito de idempotência e fan-in canônico.
- `git diff --check` — passed.

### Implementation Plan

- Criar modelo canônico de `IntegrationExecution` e `IntegrationExecutionJob` no domínio, sem dependências de infraestrutura.
- Criar portas hexagonais para dispatcher, store de idempotência e publisher futuro.
- Implementar store e dispatcher in-memory para fan-out/fan-in local, paralelizável e verificável sem NATS real.
- Conectar `start_integration_execution` no serviço de aplicação com tenant confiável, escopo próprio, preflight, idempotência e logs seguros.
- Cobrir fluxo com testes unitários focados e validações alternativas por limitação da venv local.

### Completion Notes List

- Story detalhada com base no Epic 3, AD-10, OQ-12, premissa de integrações assíncronas/paralelizáveis e Story 3.2.
- Escopo delimitado para fan-out/fan-in local/testável com portas compatíveis com NATS, sem broker real, retry, DLQ, replay, persistência real ou AsyncAPI final.
- Subtarefas Jira `CTOS-189` a `CTOS-197` criadas antes de codificar, conforme decisão de manter o quadro acompanhando o desenvolvimento.
- Implementadas entidades/value objects de execução e job assíncrono com status canônico, schema `1.0`, IDs técnicos, fingerprint de plano e dicionários log-safe.
- Criadas portas hexagonais para dispatcher, store de idempotência e publisher futuro de resultado de execução.
- Implementados store in-memory e dispatcher in-memory com `ThreadPoolExecutor`, limite efetivo de concorrência, preservação de ordem do plano e contagem de concorrência observada.
- Implementado `start_integration_execution` com escopo `integration_execution:start`, tenant confiável, validação de plano, preflight completo, idempotência atômica, reutilização segura, conflito por fingerprint e fan-in.
- Adicionados logs estruturados para início aceito, reutilização idempotente, job despachado, fan-in e rejeições, sempre com payload omitido e extras minimizados.
- Adicionados testes unitários para execução, preservação de metadados, concorrência, reutilização idempotente, conflito, preflight, fan-in, escopo, eventos internos e ausência de dados sensíveis.
- Documentado o escopo da Story 3.3 no README do `Integration Service`.
- Patches de revisão aplicados: reserva idempotente atômica, timeout/falhas canônicas, bloqueio de CPF/CNPJ formatado em `idempotency_key`, fingerprint normalizado, validação de contexto dos resultados, fan-in com fallback, envelope interno CloudEvents/NATS e log aceito de início.

### File List

- `_bmad-output/implementation-artifacts/3-3-execucao-assincrona-com-fan-out-fan-in.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/__init__.py`
- `services/integration/src/creditos_integration/adapters/events/__init__.py`
- `services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`
- `services/integration/src/creditos_integration/adapters/persistence/__init__.py`
- `services/integration/src/creditos_integration/adapters/persistence/in_memory_integration_execution_store.py`
- `services/integration/src/creditos_integration/application/__init__.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/application/ports/integration_execution.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/integration_execution.py`
- `services/integration/src/creditos_integration/domain/value_objects/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/execution.py`
- `services/integration/tests/unit/test_integration_async_execution.py`

### Change Log

- 2026-08-20 — Story 3.3 criada e marcada como `ready-for-dev`.
- 2026-08-20 — Implementação da Story 3.3 iniciada e marcada como `in-progress`.
- 2026-08-20 — Execução assíncrona com fan-out/fan-in implementada e marcada como `review`.
- 2026-08-20 — Achados do `bmad-code-review` aplicados e Story 3.3 marcada como `done` no artefato BMAD.
