---
jira_issue: CTOS-36
branch: agent/story-3-4-resiliencia-retry-dlq-reprocessamento-controlado
baseline_commit: 5648bed
---

# Story 3.4: Resiliência, Retry, DLQ e Reprocessamento Controlado

Status: review

## Story

Como operador da plataforma,
quero que falhas de integração sejam tratadas com retry seguro, DLQ e reprocessamento controlado,
para que indisponibilidades externas não quebrem a jornada sem rastreabilidade.

## Acceptance Criteria

1. **Retry seguro para falha recuperável**
   - **Given** uma execução de integração com adapter que falha de forma recuperável
   - **When** o job for processado pelo dispatcher in-memory
   - **Then** aplica retry até `max_attempts`, com backoff e jitter determinísticos/testáveis
   - **And** preserva `execution_id`, `job_id`, `tenant_id`, `product_type`, `integration_class`, `adapter_id`, `correlation_id`, `trace_id`, `schema_version` e idempotência da execução.

2. **Classificação explícita de falha**
   - **Given** uma falha de adapter, timeout, resultado inválido ou erro de validação
   - **When** a falha for tratada
   - **Then** classifica a causa como recuperável ou final por código controlado
   - **And** não expõe exceção bruta, payload proprietário, stack trace, token, credencial, CPF, CNPJ, e-mail ou nome real.

3. **DLQ canônica sem broker real**
   - **Given** uma falha final ou uma falha recuperável que excedeu o limite de tentativas
   - **When** o job não puder ser concluído
   - **Then** registra uma entrada de DLQ canônica, minimizada e log-safe
   - **And** inclui somente `dlq_id`, `execution_id`, `job_id`, `tenant_id`, `product_type`, `integration_class`, `adapter_id`, `failure_code`, `attempt_count`, `correlation_id`, `trace_id`, `schema_version` e timestamps.

4. **Reprocessamento controlado**
   - **Given** uma entrada de DLQ elegível para reprocessamento
   - **When** um operador autorizado solicitar reprocessamento com escopo específico
   - **Then** cria uma nova tentativa controlada vinculada à entrada original
   - **And** não duplica resultado nem ignora conflito de idempotência, tenant, fingerprint ou contexto.

5. **Observabilidade segura de resiliência**
   - **Given** retry, falha final, envio para DLQ e reprocessamento
   - **When** logs estruturados forem inspecionados
   - **Then** existem eventos `integration_execution.retry_scheduled`, `integration_execution.dlq_recorded` e `integration_execution.reprocess_requested`
   - **And** os logs usam extras minimizados, mascarados e sem payload bruto.

6. **Compatibilidade futura com NATS JetStream**
   - **Given** que NATS JetStream é o backbone assíncrono de referência do MVP
   - **When** retry, DLQ e reprocessamento forem modelados nesta story
   - **Then** os conceitos devem mapear para `AckPolicy=explicit`, `AckWait`, `MaxDeliver`, backoff, advisory de máximo de entregas e subjects CloudEvents
   - **And** esta story não adiciona `nats-py`, broker real, stream real, consumer durável real, Docker Compose de NATS nem contrato AsyncAPI final.

## Tasks / Subtasks

- [x] CTOS-36 — Implementar resiliência, retry, DLQ e reprocessamento controlado (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-198 — Modelar value objects de retry, failure classification e DLQ. (AC: 1, 2, 3)
  - [x] CTOS-199 — Estender entidades de execução/job para registrar tentativas e estado resiliente sem quebrar fan-in. (AC: 1, 3, 4)
  - [x] CTOS-200 — Estender portas hexagonais para política de retry, store de DLQ e reprocessamento controlado. (AC: 3, 4, 6)
  - [x] CTOS-201 — Implementar adapter in-memory determinístico para retry/backoff/jitter e DLQ. (AC: 1, 3, 6)
  - [x] CTOS-202 — Adicionar caso de uso de reprocessamento com escopo e tenant confiável. (AC: 4, 5)
  - [x] CTOS-203 — Adicionar logs estruturados seguros para retry, DLQ e reprocessamento. (AC: 2, 5)
  - [x] CTOS-204 — Reforçar guardrails para idempotência, privacidade, DDD e fronteiras de infraestrutura. (AC: 2, 4, 6)
  - [x] CTOS-205 — Criar testes unitários e de aplicação para retry, jitter, DLQ, reprocessamento e não duplicidade. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-206 — Atualizar exports, README, sprint status, story file e Jira conforme avanço. (AC: 5, 6)

### Review Findings

- [x] [Review][Patch] Falha controlada por resultado bypassava retry/DLQ [`services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`]
- [x] [Review][Patch] Reprocessamento marcava sucesso sem criar nova tentativa controlada [`services/integration/src/creditos_integration/application/service.py`]
- [x] [Review][Patch] Falha final podia ficar sem DLQ por configuração ausente [`services/integration/src/creditos_integration/application/service.py`]
- [x] [Review][Patch] Idempotência de reprocessamento permitia reuso estreito por DLQ [`services/integration/src/creditos_integration/adapters/persistence/in_memory_integration_dlq_store.py`]
- [x] [Review][Patch] `save()` de DLQ podia sobrescrever metadados append-like [`services/integration/src/creditos_integration/adapters/persistence/in_memory_integration_dlq_store.py`]
- [x] [Review][Patch] Contador de retries não era thread-safe [`services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`]
- [x] [Review][Patch] Mapeamento NATS JetStream/CloudEvents estava apenas narrativo [`services/integration/src/creditos_integration/application/ports/integration_execution.py`]
- [x] [Review][Defer] Timeout não interrompe adapter travado [`services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`] — deferred, exige worker/deadline cooperativo ou isolamento real de execução fora do escopo in-memory desta story.

## Dev Notes

### Escopo desta story

- Implementar **resiliência local/testável** sobre a execução assíncrona da Story 3.3.
- Reutilizar `IntegrationExecution`, `IntegrationExecutionJob`, `IntegrationExecutionJobRequest`, `IntegrationExecutionDispatchResult`, `IntegrationExecutionStore` e `InMemoryIntegrationExecutionDispatcher`.
- Implementar retry/backoff/jitter e DLQ como domínio/aplicação/adapters in-memory, sem infraestrutura externa.
- Preparar mapeamento conceitual para NATS JetStream, mas sem acoplar o domínio a NATS.
- O resultado deve continuar verificável com testes unitários sem rede, sem broker, sem fornecedor real e sem segredo.

### Fora de escopo explícito

- Não instalar `nats-py`, não subir NATS, não criar stream/consumer real e não alterar infraestrutura.
- Não implementar transactional outbox/inbox real, banco real, migration, lock distribuído ou worker durável real.
- Não implementar contrato AsyncAPI final; isso pertence à Story 3.6.
- Não implementar custo real por fornecedor; isso pertence à Story 3.5.
- Não implementar circuit breaker/bulkhead/rate limit completo se não forem necessários para ACs; podem ficar como preparação ou tarefa futura.
- Não escolher fornecedor externo real nem introduzir SDK de fornecedor.

### Estado atual que deve ser preservado

- `start_integration_execution` faz validação de ambiente não produtivo, tenant confiável, escopo `integration_execution:start`, plano `ready`, cenário normalizado, fingerprint seguro, reserva idempotente atômica, preflight, fan-out/fan-in e logs seguros.
- `InMemoryIntegrationExecutionStore.reserve_or_get` já bloqueia concorrência para a mesma `idempotency_key` e evita dispatch duplicado.
- `InMemoryIntegrationExecutionDispatcher` já executa jobs em paralelo, respeita concorrência efetiva, converte exceção/timeout em resultado canônico e valida tenant/produto/classe/adapter/correlation/trace do resultado.
- `IntegrationExecution.create` já rejeita jobs não terminais, resultados órfãos/duplicados, cross-tenant, cross-product, cross-class, cross-adapter e cross-context.
- `validate_attempt_count` hoje limita tentativas entre `1` e `5`; Story 3.4 deve respeitar esse limite e não criar retry infinito.
- `.venv/bin/pytest` esteve bloqueado por runtime ausente; se persistir, registrar e usar validações alternativas já aceitas no projeto.

### Modelo de domínio sugerido

Criar/estender value objects em `services/integration/src/creditos_integration/domain/value_objects/execution.py`:

- `IntegrationFailureClass`: `recoverable`, `non_recoverable`, `timeout`, `invalid_result`.
- `IntegrationRetryDecision`: `retry`, `send_to_dlq`, `fail_fast`.
- `validate_backoff_ms(value)`: inteiro seguro, por exemplo `0 <= value <= 120_000`.
- `validate_jitter_ms(value)`: inteiro seguro, por exemplo `0 <= value <= backoff_ms`.
- `validate_dlq_id(value)`: prefixo sugerido `idlq_`.
- `validate_failure_code(value)`: tokens allowlist/regex; nunca exceção bruta.

Criar entidade/value object de DLQ em `services/integration/src/creditos_integration/domain/entities/integration_execution.py` ou arquivo dedicado se ficar mais claro:

- `IntegrationExecutionDlqRecord`
  - `dlq_id`
  - `execution_id`
  - `job_id`
  - `tenant_id`
  - `product_type`
  - `integration_class`
  - `adapter_id`
  - `failure_class`
  - `failure_code`
  - `attempt_count`
  - `schema_version`
  - `correlation_id`
  - `trace_id`
  - `created_at`
  - `reprocess_count`
  - `last_reprocess_at`

Não adicionar campos livres como `payload`, `raw_payload`, `metadata`, `provider_response`, `exception`, `stack_trace`, `request_body`, `response_body` ou `headers`.

### Política de retry sugerida

- Usar `max_attempts` de `IntegrationPlanItem`; nunca exceder `validate_attempt_count`.
- Tentativa inicial conta como `attempt_count=1`.
- Falha recuperável pode tentar novamente até `max_attempts`.
- Falha não recuperável deve ir para DLQ sem consumir tentativas extras.
- Timeout pode ser tratado como recuperável até `max_attempts`; após limite, DLQ.
- Backoff deve ser determinístico em teste:
  - base sugerida: `min(timeout_ms, 250 * 2 ** (attempt_count - 1))`;
  - jitter sugerido: derivado de hash estável de `execution_id|job_id|attempt_count`, limitado a uma janela segura;
  - não usar `random` global não determinístico.
- Não fazer `sleep` real em testes; retornar/registrar `scheduled_retry_at` ou `retry_delay_ms` calculado.

### Reprocessamento controlado sugerido

Criar comando de aplicação, por exemplo `ReprocessIntegrationDlqCommand`:

- `dlq_id`
- `idempotency_key`
- `scopes`, exigindo `integration_execution:reprocess`
- opcional `reason_code` controlado para auditoria operacional mínima

Regras:

- Usa `tenant_id` do `ObservabilityContext`; nunca aceita tenant do payload como autoridade.
- Reprocessa somente DLQ do mesmo tenant.
- Rejeita DLQ inexistente, DLQ já reprocessada com resultado terminal incompatível ou conflito de idempotência.
- Deve reaproveitar adapter mock/sandbox e contexto de execução minimizado.
- Não deve apagar DLQ original; marca vínculo/reprocessamento de forma append-like no store in-memory.
- Gera log `integration_execution.reprocess_requested` com `dlq_id`, `execution_id`, `job_id`, classe, adapter, tentativa e status, sem payload bruto.

### Portas e adapters sugeridos

Atualizar `services/integration/src/creditos_integration/application/ports/integration_execution.py`:

- `IntegrationRetryPolicy`: decide retry/DLQ a partir de job, erro controlado, tentativa e relógio.
- `IntegrationDlqStore`: salva/lista/busca DLQ e registra reprocessamento.
- `IntegrationReprocessDispatcher` ou método no dispatcher existente, somente se necessário; preferir extensão pequena para evitar duplicação.

Criar/atualizar adapters:

- `services/integration/src/creditos_integration/adapters/persistence/in_memory_integration_dlq_store.py`, se store separado simplificar.
- `services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py` para aplicar retry sem dormir de verdade.

### Convenções compatíveis com NATS/CloudEvents

Usar nomes internos compatíveis com a evolução:

- `creditos.integration.job.retry_scheduled.v1`
- `creditos.integration.job.dlq_recorded.v1`
- `creditos.integration.job.reprocess_requested.v1`
- `creditos.integration.job.reprocessed.v1`

Metadados mínimos:

- `specversion`, `id`, `type`, `source`, `subject`, `time`, `datacontenttype`, `tenant_id`, `correlation_id`, `trace_id`, `schema_version`, `data`.

Mapeamento futuro para NATS:

- `AckPolicy=explicit`: cada job precisa de ack/resultado terminal.
- `AckWait`: deadline técnico antes de redelivery; deve ser maior que o tempo normal de processamento ou o worker precisa emitir progresso.
- `MaxDeliver`: limite de entregas/tentativas; não deixar default ilimitado.
- `BackOff`: lista de atrasos para redelivery por timeout; não substitui delay de `nak` manual.
- Advisory de máximo de entregas: usar como gatilho operacional para DLQ real quando broker for implementado.

### Regras arquiteturais obrigatórias

- Todo backend segue DDD + arquitetura hexagonal; domínio não importa FastAPI, Pydantic, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, `requests` ou `httpx`.
- `Integration` continua sendo o único bounded context autorizado a falar com provedores externos.
- `Decision` nunca recebe payload proprietário, exceção de fornecedor ou detalhe de SDK; apenas resultado canônico versionado.
- DLQ não é lixeira de payload: deve conter causa controlada e contexto mínimo para reprocessamento.
- Logs operacionais não substituem auditoria oficial e não podem expor dados sensíveis.
- Multi-tenancy `bridge`: todo estado de retry/DLQ/reprocessamento carrega `tenant_id` confiável e impede cross-tenant.
- Idempotência continua obrigatória para execução e reprocessamento.

### Anti-padrões proibidos

- Não criar retry recursivo, loop infinito ou `sleep` real que deixe testes lentos/frágeis.
- Não usar `random.random()` sem seed estável para jitter testável.
- Não engolir falhas finais como `completed`.
- Não substituir `IntegrationExecutionStore.reserve_or_get` por busca não atômica.
- Não persistir/registrar exceção bruta, stack trace, payload de adapter, headers, tokens ou credenciais.
- Não misturar reprocessamento real de NATS com o adapter in-memory desta story.
- Não criar outro modelo paralelo de execução se puder estender o modelo da Story 3.3.

### Arquivos esperados

Prováveis arquivos a atualizar:

- `services/integration/src/creditos_integration/domain/value_objects/execution.py`
- `services/integration/src/creditos_integration/domain/entities/integration_execution.py`
- `services/integration/src/creditos_integration/application/ports/integration_execution.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`
- `services/integration/src/creditos_integration/adapters/persistence/__init__.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/__init__.py`
- `services/integration/README.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Esta story file.

Prováveis arquivos novos:

- `services/integration/src/creditos_integration/adapters/persistence/in_memory_integration_dlq_store.py`
- `services/integration/tests/unit/test_integration_resilience.py`

### Testes obrigatórios

Adicionar/atualizar testes para:

- Falha recuperável executa tentativa inicial + retries até sucesso sem criar DLQ.
- Falha recuperável excede `max_attempts` e cria DLQ canônica.
- Falha não recuperável cria DLQ sem retry extra.
- Timeout recuperável respeita limite de tentativas e termina em `timed_out`/DLQ quando excede.
- Backoff e jitter são determinísticos, limitados e sem `sleep` real.
- Reprocessamento exige escopo `integration_execution:reprocess`.
- Reprocessamento rejeita cross-tenant e DLQ inexistente.
- Reprocessamento não duplica resultado para mesma `idempotency_key`.
- DLQ/logs/eventos não contêm CPF, CNPJ, e-mail, nome real, token, secret, credencial, `raw_payload`, `provider_response`, `exception` ou stack trace.
- Domínio continua sem imports de infraestrutura.
- Regressão: testes da Story 3.3 continuam válidos.

Comandos de validação esperados:

- `.venv/bin/python -m pytest services/integration/tests -q`
- `.venv/bin/ruff check .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/pyright`
- `PATH=/tmp/creditos-uv-shim:$PATH uv lock --check`
- `.venv/bin/python scripts/check_contracts.py`
- Se a `.venv` local continuar quebrada, registrar limitação e executar ao menos `ruff`, `ruff format --check`, `compileall`, `git diff --check` e teste de fronteira DDD com `python3`.

### Previous Story Intelligence

Da Story 3.3:

- O fan-out/fan-in atual é local/testável, sem NATS real.
- A idempotência foi corrigida para reserva atômica antes do dispatch; não regredir para `get_by_idempotency_key`.
- Exceções de adapter e timeouts já viram resultado canônico de falha; Story 3.4 deve decidir se há retry antes da falha terminal.
- O fingerprint do plano já normaliza cenários padrão e ordena itens semanticamente.
- Resultados já validam `correlation_id` e `trace_id` contra o contexto; retry/reprocessamento deve preservar o mesmo padrão.
- O domínio já rejeita resultados órfãos/duplicados e cross-context.
- A terminologia de `replay` real foi evitada em runtime; usar “reprocessamento controlado” para DLQ local e deixar replay NATS real fora de escopo.
- Smoke manual com stubs de OpenTelemetry foi necessário por ausência local de `pytest`/OpenTelemetry.

### Latest Technical Information

- NATS JetStream pull consumers usam fetch/consume com ack explícito; para serviços long-running, o padrão `consume` mantém fluxo contínuo enquanto o worker processa e faz ack. Fonte oficial consultada em 2026-08-20: https://docs.nats.io/learn/jetstream/pull-consumers
- Em JetStream, `ack`, `nak`, `term` e `in-progress` são respostas distintas: `ack` conclui, `nak` pede redelivery, `term` para poison message e `in-progress` estende o timer de ack. Fonte oficial consultada em 2026-08-20: https://docs.nats.io/learn/jetstream/acknowledgment
- `AckWait` é o timer de redelivery e `MaxDeliver` limita tentativas; o default de `MaxDeliver=-1` permite redelivery indefinido, então o MVP deve sempre definir limite. Fonte oficial consultada em 2026-08-20: https://docs.nats.io/learn/jetstream/acknowledgment
- A documentação do NATS alerta que JetStream não possui DLQ automática embutida: ao atingir `MaxDeliver`, a mensagem sai do consumer e um advisory de máximo de entregas deve ser observado para acionar fluxo de DLQ. Fonte oficial consultada em 2026-08-20: https://docs.nats.io/learn/jetstream/acknowledgment
- CloudEvents exige atributos centrais como `id`, `source`, `specversion` e `type`; `datacontenttype`, `subject` e `time` são úteis para roteamento/contrato. Fonte oficial consultada em 2026-08-20: https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 3, Story 3.4.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-8, NFR-22, NFR-23, NFR-24 e OQ-12.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md` — decisão gRPC/NATS, DLQ, replay e streams candidatos.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-10 e AD-21.
- `_bmad-output/implementation-artifacts/3-3-execucao-assincrona-com-fan-out-fan-in.md` — base imediata e achados de revisão aplicados.
- `services/integration/README.md` — escopo atual do `Integration Service`.

### Git Intelligence

- Baseline: `5648bed`, merge do PR #34 da Story 3.3.
- Branch de desenvolvimento criada no início: `agent/story-3-4-resiliencia-retry-dlq-reprocessamento-controlado`.
- Autor local obrigatório: `Andre Tachian <altachian@gmail.com>`.
- Commits recentes mostram correções pós-review em `.gitleaks.toml`, dispatcher e typing; validar segredos e padrões log-safe antes de commit.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- 2026-08-20 — `CTOS-35` movida para `Concluído` após merge do PR #34.
- 2026-08-20 — Branch `agent/story-3-4-resiliencia-retry-dlq-reprocessamento-controlado` criada a partir de `main` em `5648bed`.
- 2026-08-20 — `CTOS-36` movida para `Em andamento` no Jira para início do fluxo.
- 2026-08-20 — `bmad-create-story` executado para detalhar a Story 3.4 antes da implementação.
- 2026-08-20 — Subtarefas Jira `CTOS-198` a `CTOS-206` criadas antes de codificar.
- 2026-08-21 — `bmad-dev-story` iniciado; `CTOS-198` movida para WIP no Jira.
- 2026-08-21 — Implementados value objects, entidade DLQ, portas, store in-memory, retry determinístico, DLQ, reprocessamento controlado e logs seguros.
- 2026-08-21 — Validações executadas: `compileall`, `ruff check`, `ruff format --check`, `git diff --check`, `scripts/check_contracts.py`, fronteira DDD e smoke manual de retry/DLQ/reprocessamento.
- 2026-08-21 — `.venv/bin/python`, `.venv/bin/pytest` e `.venv/bin/pyright` indisponíveis por runtime ausente; `python3` puro sem `pytest`/`opentelemetry`.
- 2026-08-21 — Subtarefas Jira `CTOS-198` a `CTOS-206` movidas para `Concluído`; `CTOS-36` movida para `Em análise`.
- 2026-08-21 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; seis patches corrigidos, um item deferido e um falso conflito de AC descartado.
- 2026-08-21 — Smoke manual pós-review validou retry → DLQ → reprocessamento com nova tentativa real usando stubs mínimos de OpenTelemetry.

### Completion Notes List

- Story 3.4 detalhada com base no Epic 3, PRD, OQ-12, AD-10, AD-21 e Story 3.3.
- Escopo delimitado para resiliência local/testável, sem broker real, sem `nats-py`, sem AsyncAPI final e sem persistência real.
- Incluídos guardrails para retry determinístico, DLQ minimizada, reprocessamento autorizado, idempotência e privacidade.
- Implementados enums/validadores para `IntegrationFailureClass`, `IntegrationRetryDecision`, backoff, jitter, `dlq_id` e `failure_code`.
- Implementada `IntegrationExecutionDlqRecord` com contexto mínimo, `to_log_safe_dict` e contador append-like de reprocessamento.
- Dispatcher in-memory passou a aplicar retry sem `sleep` real, registrar agendas determinísticas e enviar falhas finais para DLQ in-memory quando configurada.
- Adicionado `ReprocessIntegrationDlqCommand` com escopo `integration_execution:reprocess`, tenant confiável, idempotência e validação de adapter mock/sandbox.
- Adicionados logs `integration_execution.retry_scheduled`, `integration_execution.dlq_recorded` e `integration_execution.reprocess_requested` com extras minimizados.
- Testes de resiliência adicionados para retry até sucesso, retry excedido, falha não recuperável, timeout, resultado inválido, reprocessamento, cross-tenant, idempotência e privacidade.
- Quadro Jira sincronizado com subtarefas `CTOS-198` a `CTOS-206` concluídas e `CTOS-36` em análise.
- Review adversarial corrigiu: `FAILED` canônico agora passa por retry/DLQ; reprocessamento cria execução controlada real; DLQ store é obrigatório para execução; idempotência de reprocessamento impede reuso conflitante; DLQ `save()` preserva metadados; contador de retry usa lock; mapeamento JetStream/CloudEvents foi materializado em constantes.
- Deferido para story futura: timeout com cancelamento/deadline real de adapter travado, pois a execução in-memory atual só mede tempo após retorno do adapter.

### File List

- `_bmad-output/implementation-artifacts/3-4-resiliencia-retry-dlq-e-reprocessamento-controlado.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/__init__.py`
- `services/integration/src/creditos_integration/adapters/events/in_memory_integration_execution_dispatcher.py`
- `services/integration/src/creditos_integration/adapters/persistence/__init__.py`
- `services/integration/src/creditos_integration/adapters/persistence/in_memory_integration_dlq_store.py`
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
- `services/integration/tests/unit/test_integration_resilience.py`

### Change Log

- 2026-08-20 — Story 3.4 criada e marcada como `ready-for-dev`.
- 2026-08-21 — Implementação da Story 3.4 iniciada e marcada como `in-progress`.
- 2026-08-21 — Implementação da Story 3.4 concluída, Jira sincronizado e story marcada como `review`.
- 2026-08-21 — Achados do `bmad-code-review` aplicados e documentados; timeout hard-cancel deferido para etapa futura.
