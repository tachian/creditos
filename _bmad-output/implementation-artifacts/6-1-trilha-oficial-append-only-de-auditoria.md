---
jira_issue: CTOS-53
branch: agent/story-6-1-audit-append-only-create-story
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

Status: ready-for-dev

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

- [ ] CTOS-321 — Criar base do `Audit & Evidence Service` (AC: 1, 7, 8)
  - [ ] Criar `services/audit-evidence` seguindo o template DDD/hexagonal existente.
  - [ ] Criar pacote `creditos_audit_evidence` com `domain`, `application`, `adapters`, `bootstrap` e testes unitários.
  - [ ] Adicionar `pyproject.toml` do serviço com dependências compartilhadas `creditos-observability` e `creditos-security`.
  - [ ] Atualizar `pyproject.toml` raiz (`extraPaths`/`pythonpath`) somente se necessário para Pyright/pytest reconhecerem o novo serviço.

- [ ] CTOS-322 — Modelar evento oficial de auditoria no domínio (AC: 1, 3, 4, 5)
  - [ ] Criar entidade/agregado imutável `AuditEvent` ou nome equivalente.
  - [ ] Validar campos mínimos: `event_id`, `tenant_id`, `aggregate_type`, `aggregate_id`, `event_type`, `action`, `resource_type`, `resource_id`, `actor_subject_id`, `source_service`, `source_kind`, `result`, `occurred_at`, `correlation_id`, `trace_id` e `request_id` opcional.
  - [ ] Exigir `occurred_at` timezone-aware em UTC e normalizar serialização ISO 8601 com offset UTC.
  - [ ] Usar value objects/funções de validação locais ao bounded context; não importar entidades de `Decision`, `Integration` ou `Automated Review`.

- [ ] CTOS-323 — Implementar trilha append-only por porta hexagonal (AC: 1, 6, 7)
  - [ ] Criar `AuditEventRepository` com métodos somente de append/leitura (`append`, `get`, `list_by_aggregate` ou equivalente).
  - [ ] Não expor métodos `save`, `update`, `delete`, `remove`, `replace` ou mutação de registro existente na porta principal.
  - [ ] Implementar adapter in-memory determinístico e thread-safe para testes, com índice por `(tenant_id, event_id)` e por agregado.
  - [ ] Rejeitar duplicidade de `event_id` no mesmo tenant sem sobrescrever registro existente.

- [ ] CTOS-324 — Preparar persistência relacional append-only do MVP (AC: 1, 7, 8)
  - [ ] Criar modelo/migration mínima para tabela principal de auditoria, se compatível com o padrão atual do repositório e sem exigir infraestrutura produtiva.
  - [ ] Garantir que o desenho de persistência tenha operação normal apenas por `INSERT`; não criar fluxo operacional de `UPDATE`/`DELETE`.
  - [ ] Se o adapter SQLAlchemy/Alembic completo extrapolar a story, registrar explicitamente em `deferred-work.md` o gap de persistência real sem enfraquecer a porta append-only e os testes in-memory.
  - [ ] Não implementar hash encadeado ainda; reservar campos/interfaces apenas se isso não tornar o evento da Story 6.1 dependente da Story 6.4.

- [ ] CTOS-325 — Implementar caso de uso de registro oficial (AC: 1, 2, 3, 4, 5)
  - [ ] Criar command/result imutáveis para registrar evento oficial.
  - [ ] Exigir `ObservabilityContext` e `PropagatedContext` confiáveis; `tenant_id` e ator vêm do contexto, não do body.
  - [ ] Emitir log operacional via `build_structured_log` apenas como telemetria auxiliar, com `payload="[OMITIDO]"` e `extra` minimizado.
  - [ ] Falha de validação deve retornar erro de domínio/aplicação seguro, sem ecoar payload bruto.

- [ ] CTOS-326 — Separar evidência operacional complementar de auditoria oficial (AC: 2, 6)
  - [ ] Modelar `OperationalEvidenceReference` ou estrutura equivalente para refs de `log`, `trace`, `message` ou `metric`.
  - [ ] Permitir essas refs somente como complemento opcional do evento oficial, nunca como registro substituto.
  - [ ] Rejeitar comandos que tentem registrar apenas log/trace/message como se fosse evento oficial.
  - [ ] Documentar no README do serviço que logs/traces/eventos de mensageria não são a trilha oficial.

- [ ] CTOS-327 — Aplicar minimização, mascaramento e bloqueios de dados sensíveis (AC: 4, 5, 8)
  - [ ] Reusar `creditos_security.masking.mask_sensitive_data` e constantes existentes como defesa adicional.
  - [ ] Restringir `safe_details` a `dict[str, str]` com chaves permitidas/normalizadas, limite de cardinalidade e valores curtos.
  - [ ] Rejeitar ou omitir chaves de payload bruto, documento, imagem, biometria, segredo, token e dados financeiros detalhados.
  - [ ] Testar CPF, CNPJ, e-mail, telefone, token, segredo e payload em fixtures sintéticas.

- [ ] CTOS-328 — Criar testes de domínio, aplicação e persistência append-only (AC: 1-8)
  - [ ] Cobrir criação válida, UTC obrigatório, IDs inválidos, tenant ausente/divergente, ator ausente e contexto não confiável.
  - [ ] Cobrir idempotência/duplicidade de `event_id` sem sobrescrita.
  - [ ] Cobrir ausência de métodos de update/delete na porta principal e adapter in-memory.
  - [ ] Cobrir consulta por tenant/agregado sem vazamento cross-tenant.
  - [ ] Cobrir que logs/traces/mensagens são apenas `operational_evidence_refs` e não substituem evento oficial.

- [ ] CTOS-329 — Atualizar documentação e rastreabilidade BMAD/Jira (AC: 7, 8)
  - [ ] Criar/atualizar `services/audit-evidence/README.md` com responsabilidades, limites e fora de escopo.
  - [ ] Atualizar esta story com decisões locais, arquivos alterados, evidências de validação e achados de review.
  - [ ] Atualizar `sprint-status.yaml` conforme avanço da implementação.
  - [ ] Criar/sincronizar subtarefas Jira antes de codificar e mover cards conforme execução.

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
- `safe_details` deve ter limite de número de chaves, tamanho de chave/valor, tipos apenas string e nomes técnicos normalizados.
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

- [ ] Antes de codificar, mover `CTOS-53` e `CTOS-321` para `Em andamento`.
- [ ] Começar por testes RED de domínio/aplicação para append-only, contexto confiável, UTC e privacidade.
- [ ] Reusar o template de serviço e padrões de `Decision`/`Automated Review`; não reinventar estrutura.
- [ ] Manter domínio livre de infraestrutura.
- [ ] Não criar tecnologia nova sem ADR/aprovação.
- [ ] Não implementar Story 6.4/6.5/6.7 por antecipação.
- [ ] Atualizar README, story, `sprint-status.yaml` e Jira conforme avanço.
- [ ] Rodar `bmad-code-review` antes de `commit/push/draft PR`.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Story criada por `bmad-create-story` em 2026-09-14.
- Epic 6 marcado como `in-progress` no `sprint-status.yaml`.
- Story 6.1 marcada como `ready-for-dev` no `sprint-status.yaml`.

### File List

- `_bmad-output/implementation-artifacts/6-1-trilha-oficial-append-only-de-auditoria.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
