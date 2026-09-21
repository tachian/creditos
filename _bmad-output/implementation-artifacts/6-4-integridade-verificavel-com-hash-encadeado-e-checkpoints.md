---
jira_issue: CTOS-56
branch: agent/story-6-4-audit-integrity-hash-checkpoints
baseline_commit: ea42d91
created_at: 2026-09-17
subtasks:
  - CTOS-345
  - CTOS-346
  - CTOS-347
  - CTOS-348
  - CTOS-349
  - CTOS-350
  - CTOS-351
  - CTOS-352
---

# Story 6.4: Integridade Verificável com Hash Encadeado e Checkpoints

Status: done

## Story

Como auditor técnico,
quero verificar a integridade da trilha oficial de auditoria,
para que alterações, lacunas, reordenações ou adulterações sejam detectadas de forma confiável.

## Acceptance Criteria

1. **Eventos oficiais recebem integridade encadeada**
   - **Given** um novo evento crítico registrado pelo `Audit & Evidence`
   - **When** o evento for anexado à trilha oficial
   - **Then** o serviço calcula `previous_hash` e `current_hash` sobre payload canônico determinístico
   - **And** o encadeamento é feito por tenant em ordem oficial de append, isolando cadeias entre tenants.

2. **Payload canônico é determinístico e seguro**
   - **Given** o mesmo evento lógico com a mesma informação permitida
   - **When** o payload canônico for serializado
   - **Then** a serialização produz o mesmo digest independentemente da ordem de dicionários de entrada
   - **And** não inclui campos derivados de integridade, assinaturas, payload bruto, evidências operacionais completas, tokens, segredos, documentos completos ou PII sensível.

3. **Primeiro evento e eventos subsequentes são verificáveis**
   - **Given** o primeiro evento de um tenant
   - **When** a cadeia for calculada
   - **Then** usa um valor gênese versionado e explícito como `previous_hash`
   - **And** eventos seguintes usam o `current_hash` do evento anterior do mesmo tenant.

4. **Verificação detecta violações de cadeia**
   - **Given** uma janela de auditoria por tenant
   - **When** a verificação de integridade for executada
   - **Then** recomputa hashes e retorna resultado explícito para cadeia válida, hash divergente, predecessor ausente, tenant divergente, ordem inválida ou checkpoint incompatível
   - **And** o resultado não expõe payload bruto nem dados sensíveis.

5. **Checkpoints assinados cobrem janelas fechadas**
   - **Given** uma janela fechada de auditoria com eventos persistidos
   - **When** um checkpoint for gerado
   - **Then** calcula digest do lote usando os hashes encadeados, assina o digest por uma porta de assinatura determinística em testes
   - **And** registra versão de algoritmo, versão de canonicalização, referência de chave, período coberto, tenant, contagem de eventos, primeiro evento e último evento.

6. **Checkpoints são verificáveis**
   - **Given** um checkpoint existente para uma janela
   - **When** a janela for verificada novamente
   - **Then** a recomputação do digest e a validação da assinatura confirmam integridade ou apontam divergência segura
   - **And** uma janela vazia não gera checkpoint oficial por padrão.

7. **Escopo controlado**
   - **Given** que esta story implementa integridade lógica verificável
   - **When** a implementação for concluída
   - **Then** não cria KMS real, S3/WORM real, job agendado real, SQLAlchemy/Alembic real, gRPC real, NATS real, outbox real, IAM/cloud real ou dashboards
   - **And** documenta esses itens como evolução operacional das próximas stories/ADRs quando aplicável.

8. **Gates locais de qualidade e regressão**
   - **Given** a suíte local do repositório
   - **When** a Story 6.4 for concluída
   - **Then** testes focados do `Audit & Evidence` passam cobrindo canonicalização, hash chain, isolamento por tenant, checkpoint e verificação
   - **And** Ruff format/check, Pyright, `uv lock --check` e testes relevantes permanecem verdes ou qualquer limitação ambiental preexistente é registrada sem mascarar falha funcional.

## Tasks / Subtasks

- [x] CTOS-345 — Definir payload canônico e contrato de integridade (AC: 1, 2, 3, 4, 5)
  - [x] Definir versão de canonicalização, versão de algoritmo e valor gênese explícito.
  - [x] Definir exatamente quais campos do `AuditEvent` entram no payload canônico.
  - [x] Excluir `current_hash`, assinaturas, payload bruto, evidência operacional completa e campos sensíveis do material hasheado.
  - [x] Cobrir serialização estável por JSON ordenado, separadores compactos e normalização de datas/tuplas.

- [x] CTOS-346 — Estender modelo de auditoria com hashes encadeados (AC: 1, 2, 3, 4, 8)
  - [x] Adicionar metadados de integridade ao evento oficial de forma imutável e validada.
  - [x] Garantir que eventos legados/testes existentes sejam atualizados sem abrir campos livres.
  - [x] Manter o domínio independente de framework, banco, cloud, gRPC, NATS ou OpenTelemetry.

- [x] CTOS-347 — Encadear hashes no append do repositório (AC: 1, 3, 4, 8)
  - [x] Calcular `previous_hash` a partir do último evento oficial do mesmo tenant.
  - [x] Garantir isolamento de cadeia entre tenants e estabilidade da ordem de append.
  - [x] Preservar comportamento append-only e rejeição de duplicidade de evento.
  - [x] Testar primeiro evento, segundo evento, tenants independentes e tentativa de adulteração.

- [x] CTOS-348 — Modelar checkpoints assinados de janela (AC: 5, 6, 7)
  - [x] Criar entidade/valor de checkpoint com tenant, janela, contagem, primeiro/último evento, digest, assinatura, chave e versões.
  - [x] Criar porta de assinatura/verificação com implementação fake/determinística para testes.
  - [x] Criar porta de repositório de checkpoints sem persistência real fora do escopo.

- [x] CTOS-349 — Implementar geração de checkpoint in-memory (AC: 5, 6, 8)
  - [x] Gerar checkpoint apenas para janela fechada e não vazia.
  - [x] Calcular digest do lote a partir de eventos ordenados da cadeia oficial.
  - [x] Persistir checkpoint em adapter in-memory com validação de duplicidade segura.

- [x] CTOS-350 — Implementar verificação de cadeia e checkpoints (AC: 4, 6, 8)
  - [x] Criar caso de uso/serviço de verificação por tenant e janela.
  - [x] Reportar divergências sem expor payload bruto ou PII.
  - [x] Verificar compatibilidade de checkpoint, digest e assinatura.
  - [x] Cobrir cenários de hash divergente, predecessor ausente, tenant divergente, ordem inválida e checkpoint incompatível.

- [x] CTOS-351 — Atualizar documentação e deferred work operacional (AC: 7, 8)
  - [x] Atualizar `services/audit-evidence/README.md` removendo a limitação de hash/checkpoint como futuro quando implementado.
  - [x] Atualizar documentação/deferred work para KMS real, S3 Object Lock/WORM, job periódico, persistência real, gRPC/NATS e IaC.
  - [x] Registrar a decisão local de cadeia por tenant no arquivo da story.

- [x] CTOS-352 — Sincronizar BMAD, Jira e gates da Story 6.4 (AC: 8)
  - [x] Criar branch no início do `bmad-dev-story` e mover `CTOS-56`/primeira subtarefa para `Em andamento`.
  - [x] Atualizar subtarefas Jira conforme avanço da implementação.
  - [x] Atualizar `sprint-status.yaml` para `in-progress`, `review` e `done` nos momentos corretos.
  - [x] Registrar comandos de teste/lint/typecheck/lockfile executados e limitações ambientais reais.

### Review Findings

- [x] [Review][Patch] Exigir escopo segregado `audit:integrity:write` para geração de checkpoint [services/audit-evidence/src/creditos_audit_evidence/application/service.py:335]
- [x] [Review][Patch] Verificação de janela parcial assume gênese e rejeita cadeia válida [services/audit-evidence/src/creditos_audit_evidence/application/service.py:561]
- [x] [Review][Patch] Verificação de janela vazia retorna `valid=True` [services/audit-evidence/src/creditos_audit_evidence/application/service.py:407]
- [x] [Review][Patch] Verificação não emite códigos explícitos para tenant/cadeia divergente, predecessor ausente e ordem inválida [services/audit-evidence/src/creditos_audit_evidence/application/service.py:561]
- [x] [Review][Patch] Checkpoint pode ser gerado sobre cadeia já adulterada [services/audit-evidence/src/creditos_audit_evidence/application/service.py:351]
- [x] [Review][Patch] Checkpoint pode ser criado para janela aberta ou futura [services/audit-evidence/src/creditos_audit_evidence/application/service.py:336]
- [x] [Review][Patch] Verificação de checkpoint não compara metadados registrados da janela [services/audit-evidence/src/creditos_audit_evidence/application/service.py:590]
- [x] [Review][Patch] Repositório permite checkpoints conflitantes para a mesma janela [services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_integrity_checkpoint_repository.py:21]
- [x] [Review][Patch] Falha técnica do signer escapa em vez de virar divergência segura [services/audit-evidence/src/creditos_audit_evidence/application/service.py:621]
- [x] [Review][Patch] Corrupção do último evento do tenant reinicia a cadeia silenciosamente [services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_event_repository.py:97]
- [x] [Review][Patch] Listagem temporal regrediu para ordem de append [services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_event_repository.py:82]
- [x] [Review][Patch] Testes não cobrem divergências obrigatórias de integridade e checkpoint [services/audit-evidence/tests/unit/test_audit_integrity.py:96]

## Dev Notes

### Escopo desta story

- Esta story adiciona integridade criptográfica lógica à trilha oficial do `Audit & Evidence`, usando hash encadeado por tenant e checkpoints assinados de janela.
- A implementação deve ficar dentro do bounded context `Audit & Evidence`; outros serviços continuam publicando eventos oficiais sem conhecer detalhes de hash/checkpoint.
- O objetivo é provar contrato, domínio, portas, adapter in-memory e testes. Persistência real, KMS real, WORM/S3 Object Lock e automação operacional ficam para próximas stories.

### Decisões locais para remover ambiguidades

- **Escopo da cadeia no MVP:** a cadeia canônica da Story 6.4 é por `tenant_id`, em ordem oficial de append. Consultas por agregado ou janela podem ser usadas para leitura/verificação, mas não criam uma segunda cadeia independente nesta story.
- **Valor gênese:** usar valor constante, versionado e documentado, por exemplo `creditos-audit-chain-genesis:v1`, como predecessor do primeiro evento do tenant.
- **Algoritmo inicial:** usar `sha256` da biblioteca padrão para `current_hash` e digest de lote, sem adicionar dependência externa.
- **Assinatura em testes:** usar uma porta de assinatura/verificação com adapter determinístico baseado em biblioteca padrão; não integrar AWS KMS, HSM ou secret manager nesta story.
- **Janela vazia:** não gera checkpoint oficial por padrão, evitando prova ambígua de ausência sem mecanismo operacional de fechamento de janela.

### Contexto funcional consolidado

- Epic 6 exige auditoria oficial, trilha append-only, mascaramento, rastreabilidade e integridade verificável para decisões, alterações sensíveis, requisições e integrações. [Fonte: `_bmad-output/planning-artifacts/epics.md#Epic 6`]
- Story 6.4 exige `previous_hash` e `current_hash` sobre payload canonicalizado, cadeia verificável por tenant/agregado/janela aplicável e checkpoints assinados com algoritmo, chave/referência e período coberto. [Fonte: `_bmad-output/planning-artifacts/epics.md#Story 6.4`]
- OQ-11 aprovou banco append-only + hash encadeado + checkpoints assinados + exportação periódica imutável como abordagem de MVP para auditoria, com WORM/exportação como evolução operacional. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/recomendacoes-decisoes-abertas.md#OQ-11`]
- NFR-9 proíbe CPF/CNPJ completos, dados bancários, cartões, tokens, senhas, documentos, renda detalhada, credenciais ou payloads sensíveis completos em logs, traces, dashboards e respostas operacionais. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md#NFR-9`]

### Padrões arquiteturais obrigatórios

- Backend segue DDD + arquitetura hexagonal; domínio não depende de frameworks, banco, gRPC, NATS, OpenTelemetry, provedores externos ou Kubernetes. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-16`]
- `Audit & Evidence` é dono da trilha oficial, evidências, cadeia de hash, checkpoints e exportação imutável futura; logs, traces, métricas e eventos de mensageria não substituem auditoria. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`]
- Dados sensíveis devem ser minimizados, mascarados, omitidos, tokenizados ou hasheados; payload sensível bruto não entra na auditoria por padrão. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-9`]
- Mudanças que adicionarem dependências externas, cloud real, mensageria real, gRPC real ou persistência real exigem justificativa técnica, alternativa e consequência; não adicionar tecnologia por conveniência.

### Arquivos existentes que devem ser lidos antes de alterar

- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
  - Estado atual: `AuditEvidenceApplicationService.register_event` valida `audit:write`, contexto propagado/observabilidade, cria `AuditEvent`, faz append e registra log operacional seguro.
  - O que mudar: inserir cálculo/uso de integridade sem permitir que payload externo sobrescreva hashes oficiais.
  - Preservar: auditoria de leitura, logs seguros e rejeição de contexto inválido.

- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_event.py`
  - Estado atual: `AuditEvent` é imutável e valida campos oficiais, tenant, agregado, ação, fonte, resultado, correlação e referências operacionais.
  - O que mudar: adicionar campos de integridade imutáveis ou factory dedicada para evento com integridade.
  - Preservar: evento não pode virar log operacional nem aceitar payload livre.

- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
  - Estado atual: `safe_details` usa allowlist fechada, limites de tamanho/cardinalidade, strings apenas e bloqueio de padrões sensíveis.
  - O que mudar: somente se o payload canônico precisar normalizar detalhes seguros já aceitos.
  - Preservar: nenhuma flexibilização de allowlist para facilitar hashing.

- `services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_event_repository.py`
  - Estado atual: porta append-only com `append`, `get`, `list_by_aggregate` e `list_by_time_window`.
  - O que mudar: adicionar capacidade mínima para recuperar último evento por tenant e listar janela por tenant em ordem oficial, ou criar porta separada se preservar contrato existente for mais limpo.
  - Preservar: append-only e compatibilidade dos testes existentes.

- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_event_repository.py`
  - Estado atual: adapter in-memory mantém eventos por ID e índice por agregado, com proteção contra duplicidade.
  - O que mudar: manter ordem oficial por tenant e suportar leitura ordenada para hash/checkpoint.
  - Preservar: deterministicidade dos testes e isolamento por tenant.

- `services/audit-evidence/README.md`
  - Estado atual: documenta que hash/checkpoints ainda são trabalho futuro.
  - O que mudar: atualizar responsabilidade implementada e deixar como futuro apenas persistência real, KMS real, WORM/exportação, job periódico e integrações reais.

### Contrato de canonicalização sugerido

- O payload canônico deve ser um objeto JSON com campos explicitamente nomeados e versionados.
- Campos recomendados:
  - `canonicalization_version`
  - `hash_algorithm`
  - `tenant_id`
  - `aggregate_type`
  - `aggregate_id`
  - `event_id`
  - `event_type`
  - `action`
  - `resource_type`
  - `resource_id`
  - `actor_id`
  - `actor_type`
  - `source_kind`
  - `source_name`
  - `result`
  - `occurred_at` em ISO 8601 normalizado
  - `correlation_id`
  - `trace_id`
  - `request_id`
  - `safe_details` após validação e ordenação
  - `operational_reference_ids` ou fingerprints seguros, nunca conteúdo bruto da evidência
  - `previous_hash`
- O cálculo de `current_hash` deve incluir `previous_hash`, mas não deve incluir o próprio `current_hash`.
- Usar JSON com `sort_keys=True`, separadores compactos e normalização recursiva de tuplas/listas/dicionários.

### Contrato de checkpoint sugerido

- Entidade ou value object de checkpoint deve conter, no mínimo:
  - `checkpoint_id`
  - `tenant_id`
  - `window_started_at`
  - `window_ended_at`
  - `event_count`
  - `first_event_id`
  - `last_event_id`
  - `first_event_hash`
  - `last_event_hash`
  - `batch_digest`
  - `signature`
  - `signature_key_ref`
  - `hash_algorithm`
  - `canonicalization_version`
  - `signature_algorithm`
  - `created_at`
- `checkpoint_id` pode ser derivado deterministicamente de tenant + janela + digest, desde que duplicidades sejam tratadas de forma explícita.
- A verificação deve recomputar o digest da janela e validar a assinatura por porta, sem expor material sensível em exceções/logs.

### Testes esperados

- `AuditEvent`/canonicalização:
  - Mesmo evento com `safe_details` em ordens diferentes gera o mesmo payload canônico e hash.
  - `current_hash` não participa do próprio cálculo.
  - Campo sensível sintético em `safe_details` continua rejeitado/omitido pelo contrato existente.

- Hash chain:
  - Primeiro evento do tenant usa gênese versionada.
  - Segundo evento usa `current_hash` do primeiro como `previous_hash`.
  - Tenants diferentes não compartilham predecessor.
  - Repositório rejeita duplicidade sem recalcular cadeia de forma inconsistente.

- Verificação:
  - Cadeia íntegra retorna status válido.
  - Alteração de campo canônico, predecessor incorreto, tenant divergente ou ordem inválida retorna divergência segura.
  - Resultado de verificação não contém payload bruto nem PII.

- Checkpoint:
  - Janela fechada e não vazia gera digest e assinatura determinísticos em teste.
  - Janela vazia não gera checkpoint oficial.
  - Checkpoint divergente é detectado por digest ou assinatura incompatível.

### Comandos de validação esperados

- `uv run pytest services/audit-evidence/tests/unit -q`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run pyright`
- `uv lock --check`

## Change Log

| Data | Versão | Descrição | Autor |
| --- | --- | --- | --- |
| 2026-09-17 | 0.1 | Story criada via `bmad-create-story`; Jira `CTOS-56` sincronizado com subtarefas `CTOS-345`–`CTOS-352`. | Codex |
| 2026-09-19 | 1.0 | Implementação concluída com hash encadeado por tenant, checkpoints assinados, verificação segura, documentação e gates locais. | Codex |
| 2026-09-20 | 1.1 | Achados do `bmad-code-review` corrigidos; verificação de integridade, checkpoint e testes adversariais endurecidos. | Codex |

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

- `CTOS-55` atualizado para `Concluído`.
- `main` sincronizada com `origin/main` em `ea42d91`.
- `CTOS-56` consultado para confirmar subtarefas `CTOS-345`–`CTOS-352`.
- Branch `agent/story-6-4-audit-integrity-hash-checkpoints` criada no início do desenvolvimento; `CTOS-56` e `CTOS-345` movidos para `Em andamento`.
- Teste vermelho inicial: `.venv/bin/pytest services/audit-evidence/tests/unit/test_audit_integrity.py -q` falhou por imports ainda não implementados.
- Gates focados: `.venv/bin/pytest services/audit-evidence/tests/unit -q` passou com 45 testes.
- Gates de qualidade: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .` e `.venv/bin/pyright` passaram.
- Regressão completa no sandbox: `.venv/bin/pytest -q` falhou em 3 testes do harness local por bloqueio de socket e `uv` ausente.
- Regressão completa fora do sandbox: `.venv/bin/pytest -q` passou em 673 testes e falhou apenas em `tests/test_local_harness.py::test_dev_script_harness_check_uses_documented_command` por `scripts/dev: line 47: uv: command not found`, limitação ambiental preexistente.
- `uv lock --check` não pôde ser executado porque `uv` e `.venv/bin/uv` não existem neste ambiente; nenhuma dependência foi adicionada e `uv.lock` não foi alterado.
- `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 12 findings de patch corrigidos.
- Gates pós-review: `.venv/bin/pytest services/audit-evidence/tests/unit -q` passou com 56 testes.
- Gates pós-review: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .` e `.venv/bin/pyright` passaram.
- Regressão completa pós-review fora do sandbox: `.venv/bin/pytest -q` passou em 684 testes e falhou apenas em `tests/test_local_harness.py::test_dev_script_harness_check_uses_documented_command` por `scripts/dev: line 47: uv: command not found`, limitação ambiental preexistente.

### Implementation Plan

- Implementar canonicalização determinística e cálculo `sha256` no domínio, sem dependências externas.
- Estender `AuditEvent` com metadados de integridade validados e imutáveis.
- Encadear hashes no adapter append-only in-memory em ordem oficial por tenant.
- Modelar checkpoint, signer e repositório via portas hexagonais e adapters testáveis.
- Adicionar casos de uso para geração/verificação de checkpoints e divergências seguras.
- Atualizar documentação/deferred work preservando KMS, WORM, jobs, gRPC/NATS, persistência real e IaC fora do escopo.

### Completion Notes List

- Story 6.4 detalhada e pronta para desenvolvimento.
- Escopo fechado para hash encadeado por tenant, checkpoints assinados in-memory e verificação segura.
- Persistência real, KMS real, WORM/S3 Object Lock, jobs, gRPC/NATS, IAM/cloud e dashboards permanecem fora de escopo desta story.
- Implementado payload canônico v1 com JSON ordenado, datas normalizadas, `safe_details` validado e exclusão de `current_hash`/payload bruto.
- Implementado hash chain por tenant com gênese `creditos-audit-chain-genesis:v1` e cálculo oficial no append do repositório.
- Implementados checkpoints assinados de janelas fechadas e verificação segura de cadeia/checkpoint.
- Atualizados testes unitários do `Audit & Evidence`, README e deferred work operacional.
- Corrigidos achados do review: verificação de janela parcial, janela vazia, tenant/cadeia divergente, predecessor ausente, ordem inválida, checkpoint sobre cadeia adulterada, janela aberta, metadados de checkpoint, conflito de janela, falha técnica do signer, reinício silencioso da cadeia e ordenação temporal.

### File List

- `_bmad-output/implementation-artifacts/6-4-integridade-verificavel-com-hash-encadeado-e-checkpoints.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/audit-evidence/README.md`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/external/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/external/deterministic_checkpoint_signer.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_event_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_integrity_checkpoint_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_checkpoint_signer.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_event_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_integrity_checkpoint_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_event.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_integrity_checkpoint.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/services/audit_integrity.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_integrity.py`
- `services/audit-evidence/tests/unit/test_audit_application_service.py`
- `services/audit-evidence/tests/unit/test_audit_integrity.py`
