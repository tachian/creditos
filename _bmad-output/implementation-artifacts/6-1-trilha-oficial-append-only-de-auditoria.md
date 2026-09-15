---
jira_issue: CTOS-53
branch: agent/story-6-1-audit-append-only
baseline_commit: f0a9f71
created_at: 2026-09-14
subtasks:
  - CTOS-321
  - CTOS-322
  - CTOS-323
  - CTOS-324
  - CTOS-325
  - CTOS-326
  - CTOS-327
  - CTOS-328
  - CTOS-329
---

# Story 6.1: Trilha Oficial Append-only de Auditoria

Status: done

## Story

Como time de compliance/auditoria,
quero uma trilha oficial de auditoria separada dos logs operacionais,
para que decisões e ações sensíveis possam ser provadas e reconstruídas.

## Acceptance Criteria

1. **Registro oficial append-only**
   - **Given** um evento auditável de decisão ou ação sensível
   - **When** o `Audit & Evidence` recebe o registro
   - **Then** persiste em trilha append-only com `event_id`, tenant, agregado, ação, recurso, ator, origem, resultado, UTC, correlation ID e trace ID
   - **And** operações normais não permitem update/delete na trilha principal.

2. **Separação explícita entre auditoria e observabilidade operacional**
   - **Given** logs, traces ou eventos de mensageria
   - **When** uma auditoria oficial é solicitada
   - **Then** eles não substituem a trilha oficial
   - **And** podem ser usados apenas como evidência operacional complementar.

3. **Isolamento e contexto confiável por tenant**
   - **Given** uma requisição interna para registrar auditoria oficial
   - **When** o serviço receber `tenant_id`, `tenant_isolation_tier`, ator e rastreabilidade
   - **Then** usa somente `PropagatedContext`/metadata confiável como autoridade de tenant e ator
   - **And** rejeita tenant ausente, tenant divergente, ator ausente ou tentativa de usar tenant vindo de payload de negócio.

4. **Evento mínimo canônico e seguro**
   - **Given** um evento oficial aceito
   - **When** o registro for materializado no domínio
   - **Then** valida IDs técnicos, `occurred_at` timezone-aware em UTC, `event_type`, `aggregate_type`, `aggregate_id`, `resource_type`, `resource_id`, `action`, `source_service`, `source_kind`, `result`, `correlation_id`, `request_id` opcional e `trace_id`
   - **And** detalhes adicionais ficam em `safe_details` minimizado, tipado e log-safe.

5. **Privacidade por padrão na trilha oficial**
   - **Given** detalhes, recurso, ator ou origem contendo CPF, CNPJ, e-mail, telefone, token, segredo, payload bruto, documento, imagem, biometria ou dado financeiro detalhado
   - **When** o evento for validado
   - **Then** o sistema mascara, omite ou rejeita conforme a classe do dado antes de persistir
   - **And** testes garantem que a trilha oficial não armazena payload sensível bruto por padrão.

6. **Consulta oficial não confundida com logs**
   - **Given** uma consulta por `event_id`, agregado ou janela temporal
   - **When** o consumidor autorizado solicitar eventos oficiais
   - **Then** retorna apenas registros da trilha oficial append-only filtrados por tenant
   - **And** referências a logs, traces ou mensagens aparecem somente como `operational_evidence_refs` complementares, nunca como substituto do evento oficial.

7. **Escopo controlado da fundação**
   - **Given** que esta é a primeira story do Epic 6
   - **When** o dev agent implementar
   - **Then** cria a fundação do `Audit & Evidence Service` sem implementar hash encadeado/checkpoints da Story 6.4, WORM/S3 Object Lock da Story 6.5, scanner de logs da Story 6.7, endpoints públicos finais, NATS real, gRPC real ou IaC
   - **And** deixa interfaces claras para essas capacidades futuras.

8. **Gates locais de qualidade e regressão**
   - **Given** a suíte local do repositório
   - **When** a Story 6.1 for concluída
   - **Then** testes focados de domínio/aplicação/persistência append-only passam
   - **And** Ruff format/check e Pyright permanecem verdes ou qualquer limitação ambiental preexistente é registrada sem mascarar falha funcional.

## Tasks / Subtasks

- [x] CTOS-321 — Criar base do `Audit & Evidence Service` (AC: 1, 7, 8)
  - [x] Criar `services/audit-evidence` seguindo o template DDD/hexagonal existente.
  - [x] Criar pacote `creditos_audit_evidence` com `domain`, `application`, `adapters`, `bootstrap` e testes unitários.
  - [x] Adicionar `pyproject.toml` do serviço com dependências compartilhadas `creditos-observability` e `creditos-security`.
  - [x] Atualizar `pyproject.toml` raiz (`extraPaths`/`pythonpath`) somente se necessário para Pyright/pytest reconhecerem o novo serviço.

- [x] CTOS-322 — Modelar evento oficial de auditoria no domínio (AC: 1, 3, 4, 5)
  - [x] Criar entidade/agregado imutável `AuditEvent` ou nome equivalente.
  - [x] Validar campos mínimos: `event_id`, `tenant_id`, `aggregate_type`, `aggregate_id`, `event_type`, `action`, `resource_type`, `resource_id`, `actor_subject_id`, `source_service`, `source_kind`, `result`, `occurred_at`, `correlation_id`, `trace_id` e `request_id` opcional.
  - [x] Exigir `occurred_at` timezone-aware em UTC e normalizar serialização ISO 8601 com offset UTC.
  - [x] Usar value objects/funções de validação locais ao bounded context; não importar entidades de `Decision`, `Integration` ou `Automated Review`.

- [x] CTOS-323 — Implementar trilha append-only por porta hexagonal (AC: 1, 6, 7)
  - [x] Criar `AuditEventRepository` com métodos somente de append/leitura (`append`, `get`, `list_by_aggregate` ou equivalente).
  - [x] Não expor métodos `save`, `update`, `delete`, `remove`, `replace` ou mutação de registro existente na porta principal.
  - [x] Implementar adapter in-memory determinístico e thread-safe para testes, com índice por `(tenant_id, event_id)` e por agregado.
  - [x] Rejeitar duplicidade de `event_id` no mesmo tenant sem sobrescrever registro existente.

- [x] CTOS-324 — Preparar desenho append-only e registrar gap de persistência relacional do MVP (AC: 1, 7, 8)
  - [x] Confirmar que o repositório ainda não possui padrão operacional de migrations por serviço nem banco real provisionado para o `Audit & Evidence Service`.
  - [x] Garantir que a porta e o adapter in-memory tenham operação normal apenas por `append`/leitura; não criar fluxo operacional de `UPDATE`/`DELETE`.
  - [x] Registrar explicitamente em `deferred-work.md` o gap de SQLAlchemy/Alembic, grants `INSERT`-only e banco real sem enfraquecer a porta append-only e os testes in-memory.
  - [x] Não implementar hash encadeado ainda; reservar campos/interfaces apenas se isso não tornar o evento da Story 6.1 dependente da Story 6.4.

- [x] CTOS-325 — Implementar caso de uso de registro oficial (AC: 1, 2, 3, 4, 5)
  - [x] Criar command/result imutáveis para registrar evento oficial.
  - [x] Exigir `ObservabilityContext` e `PropagatedContext` confiáveis; `tenant_id` e ator vêm do contexto, não do body.
  - [x] Emitir log operacional via `build_structured_log` apenas como telemetria auxiliar, com `payload="[OMITIDO]"` e `extra` minimizado.
  - [x] Falha de validação deve retornar erro de domínio/aplicação seguro, sem ecoar payload bruto.

- [x] CTOS-326 — Separar evidência operacional complementar de auditoria oficial (AC: 2, 6)
  - [x] Modelar `OperationalEvidenceReference` ou estrutura equivalente para refs de `log`, `trace`, `message` ou `metric`.
  - [x] Permitir essas refs somente como complemento opcional do evento oficial, nunca como registro substituto.
  - [x] Rejeitar comandos que tentem registrar apenas log/trace/message como se fosse evento oficial.
  - [x] Documentar no README do serviço que logs/traces/eventos de mensageria não são a trilha oficial.

- [x] CTOS-327 — Aplicar minimização, mascaramento e bloqueios de dados sensíveis (AC: 4, 5, 8)
  - [x] Reusar `creditos_security.masking.mask_sensitive_data` e constantes existentes como defesa adicional.
  - [x] Restringir `safe_details` a `dict[str, str]` com chaves permitidas/normalizadas, limite de cardinalidade e valores curtos.
  - [x] Rejeitar ou omitir chaves de payload bruto, documento, imagem, biometria, segredo, token e dados financeiros detalhados.
  - [x] Testar CPF, CNPJ, e-mail, telefone, token, segredo e payload em fixtures sintéticas.

- [x] CTOS-328 — Criar testes de domínio, aplicação e persistência append-only (AC: 1-8)
  - [x] Cobrir criação válida, UTC obrigatório, IDs inválidos, tenant ausente/divergente, ator ausente e contexto não confiável.
  - [x] Cobrir idempotência/duplicidade de `event_id` sem sobrescrita.
  - [x] Cobrir ausência de métodos de update/delete na porta principal e adapter in-memory.
  - [x] Cobrir consulta por tenant/agregado sem vazamento cross-tenant.
  - [x] Cobrir que logs/traces/mensagens são apenas `operational_evidence_refs` e não substituem evento oficial.

- [x] CTOS-329 — Atualizar documentação e rastreabilidade BMAD/Jira (AC: 7, 8)
  - [x] Criar/atualizar `services/audit-evidence/README.md` com responsabilidades, limites e fora de escopo.
  - [x] Atualizar esta story com decisões locais, arquivos alterados, evidências de validação e achados de review.
  - [x] Atualizar `sprint-status.yaml` conforme avanço da implementação.
  - [x] Criar/sincronizar subtarefas Jira antes de codificar e mover cards conforme execução.

## Dev Notes

### Escopo desta story

- Esta story inicia o Epic 6 e cria a fundação do `Audit & Evidence Service` como trilha oficial de auditoria, separada de logs operacionais, traces, métricas e eventos de mensageria.
- O foco é o contrato canônico do evento auditável oficial, invariantes append-only, isolamento por tenant, minimização de dados e consultas oficiais básicas.
- Hash encadeado, checkpoints assinados, verificação periódica e exportação WORM são requisitos do Epic 6, mas pertencem principalmente às Stories 6.4 e 6.5.
- Logs estruturados obrigatórios e scanner/gates de vazamento ficam principalmente nas Stories 6.6 e 6.7; nesta story só registrar log operacional auxiliar seguro do próprio caso de uso.

### Contexto funcional consolidado

- Epic 6 exige que decisões, alterações sensíveis, requisições e integrações sejam rastreáveis por auditoria oficial, logs estruturados, mascaramento e integridade verificável. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Epic 6]
- Story 6.1 define a trilha oficial append-only de auditoria e afirma que logs, traces e eventos de mensageria não substituem auditoria oficial. [Fonte: `_bmad-output/planning-artifacts/epics.md`, Story 6.1]
- FR-19 exige auditoria de decisões com tenant, proposta, solicitante, horário, referências/dados usados, fontes, política, modelo, regras, resultado, justificativas e correlation ID. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-19`]
- FR-20 exige auditoria de alterações sensíveis e impede omissão silenciosa de eventos obrigatórios. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#FR-20`]
- NFR-25 e NFR-26 exigem auditoria separada de logs operacionais e trilha principal append-only no MVP. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#5.6-Auditabilidade`]
- OQ-11 decidiu banco relacional append-only como trilha principal do MVP, com `INSERT` normal, sem `UPDATE`/`DELETE`, e evolução para hash/checkpoints/WORM em stories posteriores. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`]

### Padrões arquiteturais obrigatórios

- Backend segue DDD + Hexagonal Architecture; domínio não depende de FastAPI, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry ou banco. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- `Audit & Evidence` é um dos sete microsserviços do MVP e é dono exclusivo da trilha oficial de auditoria, evidências, hash, checkpoints, exportações e consultas auditáveis. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-2`]
- Cada serviço possui ownership exclusivo de dados; comunicação cross-service ocorre por gRPC, eventos NATS JetStream ou projeções autorizadas, sem joins/transações diretas cross-service. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-3`]
- Contexto confiável propaga tenant, sujeito, scopes, correlation ID, trace ID e request ID por gRPC metadata ou CloudEvents; payload de negócio não é autoridade de tenant/identidade. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-6`]
- AD-8 proíbe usar logs como auditoria oficial e exige trilha append-only, minimização e falha controlada para auditoria crítica. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`]
- AD-9 exige minimização, máscara forte por padrão e proíbe dependência operacional em CPF/CNPJ/e-mail visível. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-9`]

### Arquivos e padrões existentes a reutilizar

- `services/service-template/` fornece a estrutura base de microsserviço DDD/hexagonal para novos bounded contexts.
- `services/decision/src/creditos_decision/application/service.py` mostra padrão de `ApplicationService`, commands/results dataclass frozen, `ObservabilityContext`, `PropagatedContext`, `build_structured_log`, `before_commit` para auditoria/persistência e logs retornados no result.
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_decision_repository.py` mostra adapter in-memory thread-safe com `RLock`, índice por tenant e rejeição de duplicidade.
- `services/automated-review/src/creditos_automated_review/application/ports/audit_publisher.py` e `review_execution_audit_publisher.py` já produzem intenções auditáveis minimizadas que serão mapeadas ao envelope oficial em stories do Epic 6.
- `packages/observability/src/creditos_observability/context.py` deve ser reutilizado para `correlation_id`, `request_id`, `trace_id`, `tenant_id` e `tenant_isolation_tier`.
- `packages/observability/src/creditos_observability/logging.py` deve ser usado para log operacional auxiliar, sempre com payload omitido.
- `packages/security/src/creditos_security/masking.py` deve ser usado como defesa adicional contra CPF, CNPJ, e-mail, telefone, token, segredo, payload e dado financeiro em detalhes/logs.

### Modelo canônico sugerido para o evento oficial

- Campos obrigatórios iniciais:
  - `event_id`: ID técnico único por tenant.
  - `tenant_id`: vindo do contexto confiável.
  - `aggregate_type` e `aggregate_id`: agregado de negócio auditado, por exemplo `credit_decision`, `review_agent_configuration`, `integration_execution`.
  - `event_type`: nome canônico versionável, por exemplo `credit_decision.created` ou `automated_review.execution.fallback_recorded`.
  - `action`: verbo de negócio técnico, por exemplo `create`, `publish`, `execute`, `access`, `export`, `verify`.
  - `resource_type` e `resource_id`: recurso afetado; pode ser igual ao agregado quando não houver recurso mais específico.
  - `actor_subject_id`: usuário/cliente técnico/workload confiável.
  - `source_service`: serviço emissor (`decision`, `automated-review`, `integration`, etc.).
  - `source_kind`: `api`, `worker`, `job`, `grpc`, `event_consumer`, `system` ou equivalente fechado.
  - `result`: `accepted`, `rejected`, `blocked`, `failed`, `technical_failure` ou enum fechado equivalente.
  - `occurred_at`: `datetime` UTC timezone-aware.
  - `correlation_id`, `trace_id` e `request_id` opcional.
  - `safe_details`: metadados minimizados e seguros.
  - `operational_evidence_refs`: refs opcionais para logs/traces/mensagens/métricas complementares.
- Não incluir `previous_hash`/`current_hash` como requisito obrigatório desta story se isso acoplar a implementação à Story 6.4; se os campos forem preparados, devem permanecer opcionais/semântica reservada.

### Regras de append-only

- A porta principal deve representar semanticamente append-only; evitar nome `save` porque pode sugerir upsert. Preferir `append`.
- Repositório in-memory não deve sobrescrever registro existente e deve retornar entidades imutáveis ou cópias imutáveis.
- API de aplicação não deve ter comando de correção por update. Correções futuras devem ser novo evento compensatório, não mutação do evento original.
- Modelo/migration de banco, se criado nesta story, deve ser somente fundação. Controle operacional de grants, usuário de banco e bloqueio físico de update/delete em produção depende de IaC/DB real posterior.

### Segurança e privacidade

- Não persistir payload bruto de proposta, payload de fornecedor, prompt/output de IA, documento, imagem, biometria, token, segredo ou dado financeiro detalhado.
- `safe_details` deve ter allowlist fechada de chaves, limite de número de chaves, tamanho de chave/valor, tipos apenas string e nomes técnicos normalizados.
- Refs operacionais devem ser IDs técnicos (`log_ref`, `trace_id`, `message_id`, `stream_subject`, `metric_ref`) e não conteúdo bruto.
- Testes devem usar dados sintéticos; se usarem CPF/CNPJ/e-mail para teste negativo, devem ser fictícios e nunca reais.
- Erros de validação não devem ecoar valores sensíveis recebidos.

### Previous Epic Intelligence

- Epic 5 entregou o `Automated Review Service` como IA consultiva, sem autonomia para decisão final, com entradas minimizadas, saída validada, fallback seguro e telemetria/custo seguros.
- A retro do Epic 5 definiu que o Epic 6 deve mapear intenções auditáveis do `Automated Review` para o envelope oficial do `Audit & Evidence`.
- Risco explicitado: misturar logs/telemetria com auditoria oficial, tratar evidência consultiva como decisão ou perder atomicidade entre operação sensível e registro auditável.
- Action item aberto: definir comportamento técnico para falhas de auditoria crítica no `Automated Review`; a Story 6.1 deve criar a base, mas não precisa resolver todos os bloqueios de decisão das Stories 6.2/6.3.
- Pendência recorrente: suíte completa local pode depender de `uv` disponível no PATH; não confundir limitação ambiental com falha funcional da story.

### Git Intelligence

- Baseline desta story: `f0a9f71`, merge do PR #52 de fechamento do Epic 5.
- Commits recentes mantêm padrão de PR por story, correções pós-review no mesmo PR, testes focados e atualização de Jira/BMAD.
- Histórias recentes criaram subtarefas Jira antes de codificar e moveram subtarefas conforme execução; manter o mesmo padrão.

### Pesquisa técnica recente

- Nenhuma tecnologia nova deve ser selecionada nesta story.
- A stack já aprovada define Python 3.13, uv workspace, pytest, Ruff, Pyright, SQLAlchemy 2.x/Alembic para persistência e OpenTelemetry via pacote compartilhado. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- Como a story não introduz biblioteca/framework novo nem muda versões, não há pesquisa externa necessária neste ciclo de `bmad-create-story`.

### Testes e validações esperadas

- Testes focados esperados:
  - `.venv/bin/pytest services/audit-evidence/tests/unit -q`
  - `.venv/bin/pytest services/audit-evidence/tests -q`
- Gates esperados:
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Se tocar pacotes compartilhados, rodar também testes relevantes de `packages/security` e `packages/observability`.
- Se a suíte completa falhar por `uv: command not found`, registrar como limitação ambiental preexistente somente após validar testes focados e gates da story.

### Fora do escopo explícito

- Hash encadeado, canonicalização final de hash, checkpoints assinados e verificação periódica completa.
- Exportação WORM/S3 Object Lock, bucket, KMS, retenção, legal hold ou IaC.
- gRPC real, NATS real, outbox/inbox real, worker real, endpoint público final ou autenticação HTTP pública.
- Consulta customer-facing de evidências, dashboards, reporting de negócio ou projeções curadas.
- Integração completa dos publishers de `Decision`, `Integration` e `Automated Review`; esta story define a fundação e fixtures/contratos para stories seguintes.
- Ledger/database especializada ou blockchain.

### Checklist de implementação para o dev agent

- [x] Antes de codificar, mover `CTOS-53` e `CTOS-321` para `Em andamento`.
- [x] Começar por testes RED de domínio/aplicação para append-only, contexto confiável, UTC e privacidade.
- [x] Reusar o template de serviço e padrões de `Decision`/`Automated Review`; não reinventar estrutura.
- [x] Manter domínio livre de infraestrutura.
- [x] Não criar tecnologia nova sem ADR/aprovação.
- [x] Não implementar Story 6.4/6.5/6.7 por antecipação.
- [x] Atualizar README, story, `sprint-status.yaml` e Jira conforme avanço.
- [x] Rodar `bmad-code-review` antes de `commit/push/draft PR`.

### Review Findings

- [x] [Review][Patch] Aplicar allowlist fechada para `safe_details` — Decisão: opção 1, aceitar somente chaves explicitamente permitidas para auditoria oficial e rejeitar chaves não reconhecidas.
- [x] [Review][Patch] Ajustar checklist/documentação da persistência relacional — Decisão: opção 2, manter adapter in-memory nesta story e deixar SQLAlchemy/Alembic/grants como trabalho posterior registrado.
- [x] [Review][Patch] Congelar `safe_details` e proteger retornos append-only contra mutação pós-append [`services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_event.py:66`]
- [x] [Review][Patch] Corrigir detecção de CPF/CNPJ em identificadores técnicos [`services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py:15`]
- [x] [Review][Patch] Rejeitar `occurred_at` com timezone diferente de UTC em vez de normalizar silenciosamente [`services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py:81`]
- [x] [Review][Patch] Implementar consulta oficial por janela temporal prevista no AC6 [`services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_event_repository.py:17`]
- [x] [Review][Patch] Revalidar duplicidade após `before_commit` para evitar overwrite/reindexação reentrante [`services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_event_repository.py:24`]
- [x] [Review][Patch] Rejeitar colisão de chaves normalizadas em `safe_details` [`services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py:122`]
- [x] [Review][Patch] Fortalecer bloqueio de aliases operacionais que tentem substituir auditoria oficial [`services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_event.py:185`]
- [x] [Review][Patch] Corrigir runtime/healthcheck para refletir prontidão real e manter `serve` vivo até shutdown [`services/audit-evidence/src/creditos_audit_evidence/bootstrap/container_runtime.py:15`]

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Implementation Plan

- Criar primeiro testes RED para domínio e aplicação do `Audit & Evidence Service`.
- Materializar um novo bounded context em `services/audit-evidence` seguindo o template DDD/hexagonal.
- Implementar entidade `AuditEvent`, `OperationalEvidenceReference`, validações de IDs/UTC/contexto e mascaramento de `safe_details`.
- Implementar porta append-only e adapter in-memory sem métodos de update/delete.
- Implementar `AuditEvidenceApplicationService` usando `ObservabilityContext`, `PropagatedContext` e log operacional seguro.
- Registrar gap de persistência SQLAlchemy/Alembic real em `deferred-work.md`, sem enfraquecer a porta append-only nem afirmar que o banco real foi entregue nesta story.

### Debug Log References

- `.venv/bin/pytest services/audit-evidence/tests/unit -q` — RED inicial: falha por pacote `creditos_audit_evidence` inexistente.
- `.venv/bin/pytest services/audit-evidence/tests/unit -q` — 20 passed.
- `.venv/bin/ruff format services/audit-evidence` — 27 files left unchanged após correções.
- `.venv/bin/ruff check services/audit-evidence` — All checks passed.
- `.venv/bin/pyright` — 0 errors, 0 warnings, 0 informations.
- `.venv/bin/pytest services/audit-evidence/tests -q` — 20 passed.
- `.venv/bin/ruff format services/audit-evidence _bmad-output/implementation-artifacts/6-1-trilha-oficial-append-only-de-auditoria.md` — 2 files reformatted, 27 files left unchanged.
- `.venv/bin/ruff check services/audit-evidence --fix` — All checks passed.
- `.venv/bin/pytest services/audit-evidence/tests/unit -q` — 31 passed após patches do code review.
- `.venv/bin/ruff format --check .` — 288 files already formatted.
- `.venv/bin/ruff check .` — All checks passed.
- `.venv/bin/pyright` — 0 errors, 0 warnings, 0 informations.
- `.venv/bin/pytest services/audit-evidence/tests -q` — 31 passed.
- `.venv/bin/pytest -q --ignore=tests/test_local_harness.py` — 631 passed.
- `.venv/bin/ruff format --check .` — 287 files already formatted.
- `.venv/bin/ruff check .` — All checks passed.
- `.venv/bin/pyright` — 0 errors, 0 warnings, 0 informations.
- `.venv/bin/pytest -q` — 624 passed, 3 failed em `tests/test_local_harness.py` por limitação ambiental preexistente (`Operation not permitted` para socket e `uv: command not found`).
- `.venv/bin/pytest -q --ignore=tests/test_local_harness.py` — 620 passed.

### Completion Notes List

- Story criada por `bmad-create-story` em 2026-09-14.
- Epic 6 marcado como `in-progress` no `sprint-status.yaml`.
- Story 6.1 marcada como `ready-for-dev` no `sprint-status.yaml`.
- `Audit & Evidence Service` criado em `services/audit-evidence` com estrutura DDD/hexagonal, pacote instalável e runtime mínimo de container.
- Entidade `AuditEvent` e `OperationalEvidenceReference` implementadas com validação de evento oficial, UTC, IDs técnicos, tenant, ator, origem, resultado, rastreabilidade e evidências operacionais complementares.
- Porta `AuditEventRepository` e adapter `InMemoryAuditEventRepository` implementados com semântica append-only, rejeição de duplicidade e sem API de update/delete.
- `AuditEvidenceApplicationService` implementado usando contexto confiável para tenant/ator/rastreabilidade e logs operacionais seguros via `build_structured_log`.
- `safe_details` normaliza strings, aplica mascaramento/omissão para PII, payload, token, segredo e dado financeiro, e limita cardinalidade/tamanho.
- Code review aplicado: `safe_details` agora usa allowlist fechada e mapping imutável, `occurred_at` rejeita timezone não UTC, CPF/CNPJ formatados são detectados, consulta por janela temporal foi adicionada, append reentrante revalida duplicidade e runtime de container mantém `serve` vivo até shutdown.
- Persistência SQLAlchemy/Alembic real foi registrada em `deferred-work.md` como trabalho futuro, pois o repositório ainda não possui padrão operacional de migrations por serviço.
- Jira sincronizado: `CTOS-53` e `CTOS-321` movidos para `Em andamento` no início; subtarefas `CTOS-321` a `CTOS-329` concluídas após validação.

### File List

- `_bmad-output/implementation-artifacts/6-1-trilha-oficial-append-only-de-auditoria.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `pyproject.toml`
- `services/audit-evidence/.dockerignore`
- `services/audit-evidence/Dockerfile`
- `services/audit-evidence/README.md`
- `services/audit-evidence/pyproject.toml`
- `services/audit-evidence/src/creditos_audit_evidence/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/api/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/events/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/external/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/grpc/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_event_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_event_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/use_cases/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/bootstrap/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/bootstrap/container_runtime.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_event.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/errors.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/events/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/policies/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/services/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
- `services/audit-evidence/tests/unit/test_audit_application_service.py`
- `services/audit-evidence/tests/unit/test_container_runtime.py`
- `services/audit-evidence/tests/unit/test_audit_event_model.py`

### Change Log

- 2026-09-14 — Implementada fundação do `Audit & Evidence Service` com domínio, aplicação, adapter append-only in-memory, testes e documentação inicial.
- 2026-09-14 — Registrado trabalho futuro para persistência SQLAlchemy/Alembic real e grants de banco append-only.
- 2026-09-14 — Aplicados patches do `bmad-code-review` para allowlist de `safe_details`, imutabilidade, UTC estrito, consulta por janela temporal, revalidação append-only e runtime de container.
