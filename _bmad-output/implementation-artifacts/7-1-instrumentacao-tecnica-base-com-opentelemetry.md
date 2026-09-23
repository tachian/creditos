---
baseline_commit: b429fe1eddc2f1b6cd4222a88b77c376cc986700
---

# Story 7.1: Instrumentação Técnica Base com OpenTelemetry

Status: done

## Story

As a operador da plataforma,  
I want todos os serviços emitindo métricas, logs e traces padronizados,  
so that a saúde técnica seja observável ponta a ponta.

## Acceptance Criteria

1. **Envelope técnico mínimo:** dado um microsserviço do CreditOS, quando ele processa requisição HTTP, chamada gRPC, evento, job ou integração, então a telemetria emitida contém `service.name`, `service.version`, `deployment.environment`, `operation`, `status`, `duration_ms`, `correlation_id`, `request_id`, `trace_id` e `tenant_id`/`tenant_isolation_tier` quando vierem de contexto confiável.
2. **Traces correlacionáveis:** dado um fluxo síncrono ou assíncrono, quando contexto é recebido ou propagado, então spans preservam `trace_id`, propagam `traceparent` válido e permitem correlacionar API, gRPC, evento, job e integração sem confiar em tenant vindo de header HTTP externo.
3. **Métricas seguras de baixa cardinalidade:** dado uma operação instrumentada, quando métricas são registradas, então labels usam allowlist de baixa cardinalidade e excluem `tenant_id`, `correlation_id`, `request_id`, `proposal_id`, `decision_id`, CPF, CNPJ, e-mail, payload, prompt/output, erro bruto, token ou segredo.
4. **Logs continuam seguros:** dado uma operação instrumentada, quando logs estruturados são emitidos, então o helper central preserva campos mínimos, omite payload bruto, mascara dados sensíveis e não transforma logs operacionais em auditoria oficial.
5. **Helpers reutilizáveis:** dado adapters/middleware/interceptors/workers futuros, quando precisarem instrumentar uma operação, então reutilizam API transversal em `creditos_observability`, sem dependência de OpenTelemetry em `domain` e sem duplicar lógica por serviço.
6. **Sem backend externo obrigatório:** dado testes locais e CI, quando a suíte roda, então valida métricas/traces/logs com exporters/readers in-memory e não exige Collector, Prometheus, Loki, Tempo, Grafana, Docker, rede ou serviço externo.
7. **Documentação operacional atualizada:** dado o início do Epic 7, quando a story é concluída, então `docs/observability.md` e `packages/observability/README.md` documentam sinais permitidos, atributos proibidos, propagação, cardinalidade e limites entre observabilidade interna, auditoria oficial e dashboards customer-facing.

## Tasks / Subtasks

- [x] CTOS-372 — Definir taxonomia mínima de telemetria técnica (AC: 1, 3, 5)
  - [x] Classificar sinais como log, metric, trace/span ou projeção futura; não criar dashboard nesta story.
  - [x] Documentar atributos obrigatórios, atributos permitidos e atributos explicitamente proibidos.
  - [x] Manter `tenant_id` em spans/logs quando confiável, mas fora de labels métricas nesta story para evitar cardinalidade alta.
- [x] CTOS-373 — Evoluir `creditos_observability.telemetry` sem reinventar pacote (AC: 1, 2, 3, 5, 6)
  - [x] Reutilizar `ObservabilityContext`, `build_structured_log`, `mask_sensitive_data` e `InMemoryTelemetry`.
  - [x] Adicionar helpers/framework-agnostic para operações HTTP, gRPC, evento, job e integração, ou funções equivalentes testáveis.
  - [x] Garantir validação atômica antes de registrar medições para evitar telemetria parcial inválida.
- [x] CTOS-374 — Garantir propagação segura de contexto e traces (AC: 2, 5)
  - [x] Preservar W3C `traceparent` válido e rejeitar IDs zerados ou inválidos.
  - [x] Confirmar que `from_http_headers` não confia em tenant externo.
  - [x] Confirmar que `from_grpc_metadata` e `from_cloudevent_attributes` usam tenant apenas em fronteira interna confiável.
- [x] CTOS-375 — Adicionar testes de métricas, traces, logs e cardinalidade (AC: 1, 2, 3, 4, 6)
  - [x] Criar ou ampliar testes em `packages/observability/tests/unit/` e `tests/test_observability_foundation.py`.
  - [x] Cobrir HTTP, gRPC, evento, job e integração com dados sintéticos inválidos, sem PII real.
  - [x] Validar ausência de payload bruto, headers, CPF/CNPJ/e-mail, token, segredo, prompt/output e IDs de alta cardinalidade em métricas.
- [x] CTOS-376 — Atualizar documentação e rastreabilidade BMAD/Jira (AC: 7)
  - [x] Atualizar `docs/observability.md` com taxonomia e limites desta story.
  - [x] Atualizar `packages/observability/README.md` com API esperada de instrumentação.
  - [x] Atualizar esta story com decisões locais, arquivos alterados, validações e achados de review.
- [x] CTOS-377 — Executar gates de qualidade focados (AC: 6, 7)
  - [x] Rodar testes focados de observabilidade, masking e gates do Epic 6.
  - [x] Rodar Ruff format/check e Pyright.
  - [x] Registrar limitação ambiental de `tests/test_local_harness.py` somente se aparecer novamente e sem mascarar falha funcional.

### Review Findings

- [x] [Review][Patch] Atributos livres podem injetar tenant não confiável ou sobrescrever tier confiável — resolvido bloqueando atributos de contexto vindos de `attributes`/`extra` e preservando tenant/tier exclusivamente a partir do `ObservabilityContext`. [packages/observability/src/creditos_observability/telemetry.py:228]
- [x] [Review][Patch] Métricas de operação usam allowlist ampla demais — resolvido separando atributos de span e métrica, com métricas filtradas somente por `_OPERATION_METRIC_ATTRIBUTES`. [packages/observability/src/creditos_observability/telemetry.py:444]
- [x] [Review][Patch] Valores de labels de baixa cardinalidade não são validados contra identificadores por requisição — resolvido com validação de valores técnicos estáveis, rejeitando rotas parametrizadas, IDs longos, UUIDs e hexadecimais livres. [packages/observability/src/creditos_observability/telemetry.py:468]
- [x] [Review][Patch] `extra` de log operacional aceita campos proibidos e permite sobrescrever `operation_type` — resolvido filtrando campos proibidos/reservados e gravando `operation_type` validado após o merge. [packages/observability/src/creditos_observability/telemetry.py:228]
- [x] [Review][Patch] Parent context fabricado quebra hierarquia de spans — resolvido preservando span corrente quando existe e usando `parent_span_id`/`trace_flags` reais extraídos de `traceparent` quando disponíveis. [packages/observability/src/creditos_observability/telemetry.py:456]
- [x] [Review][Patch] Validações de borda faltam para `trace_id` direto e `status_code` não inteiro — resolvido validando `ObservabilityContext` em `__post_init__` e exigindo `status_code` inteiro estrito. [packages/observability/src/creditos_observability/context.py:13]
- [x] [Review][Patch] Cobertura obrigatória de foundation e bordas críticas está incompleta — resolvido ampliando `tests/test_observability_foundation.py` e adicionando regressões para tenant/tier spoofing, labels fora da taxonomia, `raw_error`, `status_code`, `trace_id` inválido/zerado e hierarquia de spans. [packages/observability/tests/unit/test_telemetry_operations.py:139]

## Dev Notes

### Contexto do Epic 7

- Epic 7 cobre observabilidade e dashboards por tenant, com operadores e clientes autorizados acompanhando saúde técnica, funil de decisão, volumes, custos, integrações, incidentes e métricas curadas por tenant. [Source: `_bmad-output/planning-artifacts/epics.md#Epic 7`]
- Story 7.1 é a base técnica de instrumentação; dashboards internos, alertas, projeções de negócio e dashboards customer-facing ficam para Stories 7.2–7.6. [Source: `_bmad-output/planning-artifacts/epics.md#Story 7.1`]
- OQ-9 define OpenTelemetry como padrão obrigatório, com stack Grafana OSS como referência inicial: OpenTelemetry Collector, Prometheus, Grafana, Loki, Tempo e Alertmanager. Esta story não materializa essa stack. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]
- Observabilidade interna e customer-facing não são a mesma coisa: clientes só veem projeções curadas e isoladas por tenant, nunca logs crus, traces crus ou métricas brutas. [Source: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]

### Arquitetura e Guardrails

- AD-7 adota OpenTelemetry como padrão de instrumentação e Grafana OSS como referência de observabilidade; usar OpenTelemetry como contrato de emissão, sem acoplar domínio a SDK. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-7`]
- AD-16 define Python 3.13, `uv` workspace, pytest, Ruff, Pyright e OpenTelemetry Python; instrumentação deve ficar em adapters/middleware/interceptors, nunca no domínio. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- AD-5 exige propagação de `tenant_id` e `tenant_isolation_tier` em logs, métricas, traces, jobs, filas e dashboards, com mascaramento e controle de cardinalidade. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-5`]
- AD-20 exige modelo `bridge` no MVP e reporting/dashboards filtrados por tenant e autorização. Não criar `pooled` puro para dados sensíveis nem expor dados cross-tenant. [Source: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-20`]
- Auditoria oficial continua separada de logs/traces/métricas. Não registrar evento de auditoria oficial nesta story, salvo se algum fluxo existente exigir preservação; a base de auditoria foi entregue no Epic 6. [Source: `_bmad-output/implementation-artifacts/epic-6-retro-2026-09-23.md`]

### Estado Atual do Código

- `packages/observability/src/creditos_observability/context.py` já possui `ObservabilityContext` com criação, extração de HTTP/gRPC/CloudEvents e injeção de carrier com `traceparent`.
- `packages/observability/src/creditos_observability/logging.py` já possui `build_structured_log`, validação de duração/status e omissão de payload.
- `packages/observability/src/creditos_observability/telemetry.py` já possui `InMemoryTelemetry` com `TracerProvider`, `MeterProvider`, spans, `record_request` e `record_ai_usage`.
- `docs/observability.md` já documenta campos mínimos, fronteiras de confiança, mascaramento, limites de OpenTelemetry, health/readiness e anti-padrões.
- `tests/test_observability_foundation.py` já cobre contexto confiável, `traceparent`, logs seguros, health/readiness e telemetria in-memory segura.
- `packages/observability/tests/unit/test_logging.py` cobre envelope de log seguro.

### O Que Esta Story Deve Alterar

- Preferir evolução de `packages/observability/src/creditos_observability/telemetry.py` e documentação correspondente.
- Se criar novo módulo, manter dentro de `packages/observability/src/creditos_observability/`, por exemplo `instrumentation.py` ou `operations.py`, com API framework-agnostic e testável.
- Se houver necessidade comprovada de dependência nova, justificar no story file e atualizar `pyproject.toml`/`uv.lock`; não adicionar stack Grafana, Collector, Prometheus, Loki, Tempo, Alertmanager, Docker ou NATS nesta story.
- Não criar serviço `Reporting & Insights`, dashboards, alertas ou UI nesta story.

### Padrões Reutilizáveis

- Use allowlists de atributos como em `_METRIC_ATTRIBUTE_ALLOWLIST` e `_SPAN_ATTRIBUTE_ALLOWLIST`.
- Rejeite valores não escalares em atributos OTel; não serializar objetos arbitrários para labels/spans.
- Valide todos os valores antes de registrar qualquer métrica para evitar medições parciais.
- Para métricas, evite `tenant_id` nesta story; use `tenant_isolation_tier`, `service`, `operation`, `status`, `channel`, `contract`, `contract_version`, `source`, `destination`, `integration_class`, `product_type` apenas se allowlisted e de baixa cardinalidade.
- Para spans/logs, `tenant_id` pode aparecer quando vier de contexto confiável e passar por sanitização/mascaramento.

### Aprendizados do Epic 6

- Gates de auditoria/logs/dados sensíveis devem ser baseline para Epic 7; qualquer helper novo precisa ser coberto por scanner de vazamento. [Source: `_bmad-output/implementation-artifacts/6-7-gates-de-auditoria-logs-e-dados-sensiveis.md`]
- Unicode, controles, valores bytes e chaves sensíveis precisam ser tratados tanto em valores quanto em paths/mensagens de erro.
- Mensagens de teste não devem ecoar o valor sensível encontrado.
- Logging seguro centralizado funciona melhor que helpers por serviço; não duplicar lógica em cada bounded context. [Source: `_bmad-output/implementation-artifacts/6-6-logs-estruturados-e-mascaramento-obrigatorio.md`]

### Informação Técnica Atualizada

- A documentação oficial de OpenTelemetry Python indica traces e métricas Python como estáveis, enquanto logs permanecem em desenvolvimento. Consequência: manter o contrato de logs estruturados do CreditOS como fonte operacional segura e usar OTel principalmente para traces/métricas nesta story. [Source: `https://opentelemetry.io/status/`, consultado em 2026-09-23]
- A documentação oficial de OpenTelemetry Python recomenda instrumentação manual via API/SDK para traces, métricas e logs; a base atual já usa `opentelemetry-api`/`opentelemetry-sdk`. [Source: `https://opentelemetry.io/docs/languages/python/instrumentation/`, consultado em 2026-09-23]
- Instrumentações contrib oficiais existem para FastAPI e gRPC, mas não devem ser adicionadas automaticamente nesta story se helpers framework-agnostic atenderem aos ACs. Alternativa A: helpers próprios testáveis agora, menor dependência e mais controle de privacidade. Alternativa B: adicionar `opentelemetry-instrumentation-fastapi`/`opentelemetry-instrumentation-grpc`, maior cobertura automática, mas mais dependências e necessidade de lockfile/compatibilidade. Sugestão: começar pela Alternativa A; registrar a Alternativa B como evolução quando adapters HTTP/gRPC reais forem materializados. [Source: `https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html`, `https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/grpc/grpc.html`, consultados em 2026-09-23]

### File Structure Requirements

- `packages/observability/src/creditos_observability/telemetry.py` — provável UPDATE para novos helpers/atributos/métricas.
- `packages/observability/src/creditos_observability/context.py` — UPDATE somente se precisar ampliar carrier/propagação preservando regras de confiança.
- `packages/observability/src/creditos_observability/logging.py` — UPDATE somente se helper de operação precisar integrar log estruturado sem duplicar envelope.
- `packages/observability/src/creditos_observability/__init__.py` — UPDATE para exportar API pública, se nova API for criada.
- `packages/observability/tests/unit/` — adicionar testes unitários focados da API nova.
- `tests/test_observability_foundation.py` — ampliar testes de fundação se o comportamento for transversal.
- `tests/test_epic6_audit_logs_sensitive_data_gates.py` — rodar como regressão; alterar apenas se novo formato seguro exigir cobertura adicional.
- `docs/observability.md` e `packages/observability/README.md` — atualizar documentação operacional.

### Testing Requirements

- Testes focados esperados:
  - `.venv/bin/pytest packages/observability/tests/unit tests/test_observability_foundation.py -q`
  - `.venv/bin/pytest tests/test_epic6_audit_logs_sensitive_data_gates.py tests/test_sensitive_data_masking.py packages/security/tests/unit/test_masking.py -q`
- Gates antes de PR:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
  - teste amplo coerente com arquivos alterados, preferencialmente `services packages tests/test_observability_foundation.py tests/test_epic6_audit_logs_sensitive_data_gates.py`.
- Se `uv lock --check` falhar localmente por `uv` ausente e nenhuma dependência for adicionada, registrar limitação ambiental sem editar lockfile.
- Se dependência nova for adicionada, `uv.lock` deve ser atualizado; não alterar manualmente o lock sem necessidade comprovada.

### Anti-padrões Bloqueados

- Não colocar OpenTelemetry SDK/API dentro de qualquer `domain`.
- Não adicionar payload, headers completos, exception message bruta, CPF/CNPJ/e-mail, `proposal_id`, `decision_id`, `correlation_id`, `request_id` ou `tenant_id` como labels de métrica.
- Não criar dashboards customer-facing lendo Prometheus, Loki, Tempo, logs crus ou traces crus.
- Não tratar logs/traces/métricas como auditoria oficial.
- Não usar dados reais em exemplos, fixtures, docs ou mensagens de teste.
- Não selecionar Datadog, New Relic, CloudWatch/Application Signals, OpenSearch ou Jaeger nesta story; essas alternativas já foram avaliadas em OQ-9 e não substituem a stack aprovada.

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-09-23 — Branch inicial criada: `agent/story-7-1-opentelemetry-technical-instrumentation`.
- 2026-09-23 — Jira `CTOS-15` e `CTOS-60` movidos para `Em andamento` antes do detalhamento.
- 2026-09-23 — Subtarefas Jira `CTOS-372` a `CTOS-377` criadas e sincronizadas antes da implementação.
- 2026-09-23 — `bmad-dev-story` iniciado com baseline `b429fe1eddc2f1b6cd4222a88b77c376cc986700`; `CTOS-372` movida para `Em andamento`.
- 2026-09-23 — Teste RED criado em `packages/observability/tests/unit/test_telemetry_operations.py`; falhou por API `TelemetryOperationType` ausente, como esperado.
- 2026-09-23 — `CTOS-372` concluída e `CTOS-373` movida para `Em andamento`.
- 2026-09-23 — `CTOS-373` concluída e `CTOS-374` movida para `Em andamento`; testes focados de operação/fundação passaram.
- 2026-09-23 — RED adicional confirmou que spans não herdavam `trace_id`; corrigido com parent context OpenTelemetry derivado do `ObservabilityContext`.
- 2026-09-23 — `CTOS-374` concluída e `CTOS-375` movida para `Em andamento`.
- 2026-09-23 — Regressões de observabilidade e mascaramento passaram; `CTOS-375` concluída e `CTOS-376` movida para `Em andamento`.
- 2026-09-23 — `CTOS-376` concluída e `CTOS-377` movida para `Em andamento`.
- 2026-09-23 — Gates finais executados: Ruff format/check, Pyright, regressões focadas e suíte ampla `services packages tests/test_observability_foundation.py tests/test_epic6_audit_logs_sensitive_data_gates.py`.
- 2026-09-23 — `uv lock --check` não executou localmente porque o binário `uv` não está instalado no ambiente; nenhuma dependência foi adicionada e `uv.lock` não foi alterado.
- 2026-09-23 — `bmad-code-review` Step 02 executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; sete findings de patch aplicados e revalidados.

### Completion Notes List

- Story criada após merge do PR #61 de fechamento do Epic 6.
- Taxonomia técnica mínima definida para logs, métricas, traces/spans e projeções futuras, com métricas restritas a labels de baixa cardinalidade e sem `tenant_id`.
- `InMemoryTelemetry.record_operation` implementado como helper framework-agnostic para HTTP, gRPC, evento, job e integração, com validação antes de emissão de span/métrica/log.
- Spans agora preservam o `trace_id` do `ObservabilityContext` no contexto OpenTelemetry real e também nos atributos sanitizados permitidos.
- Testes cobrem taxonomia, HTTP/gRPC/evento/job/integração, ausência de payload bruto e exclusão de IDs de alta cardinalidade em métricas.
- Documentação operacional atualizada com taxonomia, API de instrumentação, atributos permitidos/proibidos e limites entre observabilidade, auditoria e dashboards customer-facing.
- Gates executados com sucesso: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright`, testes focados de observabilidade/mascaramento e suíte ampla com 701 testes.
- Não houve limitação de `tests/test_local_harness.py`; a única limitação ambiental foi ausência local do binário `uv` para `uv lock --check`.
- Review adversarial corrigiu bloqueio de tenant/tier via atributos livres, separou labels de métricas e spans, validou cardinalidade, filtrou `extra`, preservou hierarquia de spans e ampliou testes foundation/borda.
- Gates pós-review executados com sucesso: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright`, regressões de mascaramento/Epic 6 e suíte ampla com 706 testes.

### File List

- `_bmad-output/implementation-artifacts/7-1-instrumentacao-tecnica-base-com-opentelemetry.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/observability.md`
- `packages/observability/README.md`
- `packages/observability/src/creditos_observability/__init__.py`
- `packages/observability/src/creditos_observability/context.py`
- `packages/observability/src/creditos_observability/logging.py`
- `packages/observability/src/creditos_observability/telemetry.py`
- `packages/observability/tests/unit/test_telemetry_operations.py`
- `tests/test_observability_foundation.py`

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-09-23 | 0.1 | Story criada via `bmad-create-story`; contexto do Epic 7, OQ-9, AD-5/AD-7/AD-16/AD-20, Epic 6 e base atual de observabilidade consolidado. | Codex |
| 2026-09-23 | 0.2 | Taxonomia técnica mínima e API transversal inicial de operação observável adicionadas. | Codex |
| 2026-09-23 | 1.0 | Story implementada e movida para review após gates focados e suíte ampla passarem. | Codex |
| 2026-09-23 | 1.1 | Achados do code review adversarial corrigidos; story marcada como done. | Codex |
