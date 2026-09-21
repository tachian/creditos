---
baseline_commit: 0be29e6e6a66a867ef8074a9d681fd7d94045234
---

# Story 6.5: Exportação Imutável para WORM

Status: done

## Story

As a responsável de compliance,
I want exportações/checkpoints protegidos por WORM,
so that evidências críticas tenham retenção imutável conforme política.

## Acceptance Criteria

1. **Exportação periódica minimizada:** dado checkpoint ou pacote mínimo de evidência de uma janela fechada, quando a exportação for executada, o `Audit & Evidence` cria um manifesto canônico versionado e grava o pacote em storage WORM via porta hexagonal, sem payload sensível bruto por padrão.
2. **Retenção e classe de WORM:** a exportação aplica classe de retenção explícita, modo WORM compatível com S3 Object Lock (`GOVERNANCE` ou `COMPLIANCE` em adapter real futuro), `retain_until` UTC e, quando aplicável, indicação de legal hold, sem permitir retenção vencida ou encurtamento silencioso.
3. **Rastreabilidade oficial:** toda exportação, falha de exportação e reconciliação gera evento oficial de auditoria minimizado, separado de logs operacionais, com tenant, janela, checkpoint, objeto, versão/digest, resultado, correlation ID e trace ID.
4. **Reconciliação verificável:** dado objeto exportado, quando o job de reconciliação roda, ele recomputa/verifica digest do manifesto, compatibilidade com checkpoint e metadados WORM retornados pelo storage; divergências retornam issues seguras e auditáveis sem expor payload bruto.
5. **Idempotência e isolamento por tenant:** reexecução da mesma exportação para o mesmo tenant/checkpoint/janela não cria pacote conflitante nem cruza dados entre tenants; divergência de manifesto/object key é conflito controlado.
6. **Sem dependência cloud real nesta story:** a implementação usa porta de storage WORM e adapter in-memory determinístico para testes; AWS SDK, S3 real, bucket real, KMS real, job scheduler real, NATS/gRPC real, SQLAlchemy/Alembic real e IaC ficam fora do escopo desta story.
7. **Privacidade e segurança:** manifesto e logs contêm apenas metadados minimizados, hashes/digests, IDs técnicos e contagens; não incluem CPF/CNPJ, nomes, e-mails, tokens, payloads de proposta, prompts/outputs de IA, documentos, headers, request/response bodies ou erro bruto.
8. **Gates locais:** testes unitários cobrem exportação, retenção, idempotência, reconciliação, divergência, falha de storage, auditoria oficial e não vazamento; Ruff, Pyright e testes focados passam sem adicionar dependências.

## Tasks / Subtasks

- [x] CTOS-353 — Modelar domínio de exportação WORM minimizada (AC: 1, 2, 5, 7)
  - [x] Criar entidade/value objects para `AuditWormExport`, manifesto, classe de retenção, modo WORM, object key, object version, digest e status.
  - [x] Validar datas UTC, retenção futura, tenant obrigatório, checkpoint obrigatório, object key técnico e ausência de payload bruto.
  - [x] Definir formato canônico do manifesto com versão explícita e `sha256`, reaproveitando padrões de canonicalização da Story 6.4.

- [x] CTOS-354 — Criar portas hexagonais para exportação e storage WORM (AC: 1, 2, 4, 6)
  - [x] Criar porta de repositório de exportações append-only/idempotente.
  - [x] Criar porta `AuditWormStorage` para `put_object`, `head_object`/metadados e leitura minimizada necessária para reconciliação.
  - [x] Modelar resultado de storage com object key, version ID, ETag/digest, retention mode, retain-until e legal hold sem acoplamento a boto3/S3.

- [x] CTOS-355 — Implementar adapters in-memory determinísticos (AC: 1, 2, 4, 5, 6)
  - [x] Implementar `InMemoryAuditWormExportRepository` com chaves por tenant/checkpoint/janela.
  - [x] Implementar `InMemoryAuditWormStorage` que simula WORM por versão e impede overwrite/delete lógico no escopo dos testes.
  - [x] Garantir que conflitos por mesmo checkpoint com manifesto divergente gerem `AuditEvidenceConflictError` seguro.

- [x] CTOS-356 — Adicionar casos de uso de exportação e reconciliação (AC: 1, 3, 4, 5, 7)
  - [x] Criar comandos/resultados de aplicação para exportar checkpoint/janela e reconciliar exportação.
  - [x] Exigir escopo segregado sugerido `audit:worm:write` para exportação e `audit:read` ou `audit:worm:read` para reconciliação conforme padrão de segurança do serviço.
  - [x] Reutilizar checkpoint existente como fonte autoritativa; não recalcular cadeia de forma incompatível nem exportar janela sem checkpoint válido.
  - [x] Registrar evento oficial para exportação aceita/rejeitada e reconciliação válida/inválida.

- [x] CTOS-357 — Atualizar documentação e deferred work operacional (AC: 2, 6, 7)
  - [x] Atualizar `services/audit-evidence/README.md` com escopo da exportação WORM implementada e limites de adapter in-memory.
  - [x] Atualizar `_bmad-output/implementation-artifacts/deferred-work.md` para IaC/S3 Object Lock real, bucket policy, Object Lock habilitado na criação do bucket, KMS, lifecycle, scheduler e runbooks.
  - [x] Documentar que `COMPLIANCE` é decisão de produção/contrato e que `GOVERNANCE` pode ser usado para testes/ambientes não produtivos.

- [x] CTOS-358 — Criar testes e gates da Story 6.5 (AC: 1, 2, 3, 4, 5, 7, 8)
  - [x] Testar exportação feliz com checkpoint assinado existente e manifesto minimizado.
  - [x] Testar idempotência de replay e conflito de manifesto divergente.
  - [x] Testar rejeição de retenção vencida, janela sem checkpoint e escopo ausente.
  - [x] Testar reconciliação válida e divergência de digest/metadados WORM.
  - [x] Testar auditoria oficial de exportação/reconciliação e ausência de dados sensíveis em logs/resultados.

- [x] CTOS-359 — Sincronizar BMAD, Jira e branch da Story 6.5 (AC: 8)
  - [x] Atualizar `sprint-status.yaml` para `ready-for-dev` após criação da story.
  - [x] Criar branch `agent/story-6-5-exportacao-imutavel-worm` antes de desenvolvimento.
  - [x] Mover `CTOS-57` para `Em andamento` e criar/sincronizar subtarefas Jira antes da implementação.

### Review Findings

- [x] [Review][Patch] Recalcular e validar manifesto WORM na reconciliação [`services/audit-evidence/src/creditos_audit_evidence/application/service.py:1345`] — AC4 exige recomputar/verificar digest do manifesto e metadados WORM. A implementação compara `storage_object.body_digest` com `export.manifest_digest`, mas não recalcula `sha256(storage_object.body)`, assume que `json.loads` retornou `dict` e valida só parte do manifesto. Corrigido para validar schema mínimo, digest do corpo, tenant, janela, `event_count`, checkpoint, `batch_digest`, retenção, legal hold, object key e object version.
- [x] [Review][Patch] Auditar falhas esperadas e técnicas de exportação/reconciliação [`services/audit-evidence/src/creditos_audit_evidence/application/service.py:705`] — AC3 exige evento oficial para falhas de exportação e reconciliação. Hoje falhas inesperadas de storage/repositório não viram `AuditEvent`, reconciliação de export inexistente lança sem auditoria e auditoria de rejeição pode falhar se `checkpoint_id` de entrada for inválido. Corrigido com evento minimizado `rejected`/`technical_failure` usando referência segura quando input não for validável.
- [x] [Review][Patch] Incluir janela da exportação nos eventos oficiais WORM [`services/audit-evidence/src/creditos_audit_evidence/application/service.py:958`] — AC3 exige tenant, janela, checkpoint, objeto, versão/digest, resultado, correlation ID e trace ID. O evento atual inclui checkpoint/objeto/digest, mas não inclui `window_started_at`/`window_ended_at` ou referência técnica equivalente. Corrigido com janela UTC em `safe_details`.
- [x] [Review][Patch] Exigir metadado técnico para legal hold [`services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_worm_export.py:35`] — Dev Notes definem que legal hold deve ser explícito e não um booleano implícito sem motivo. A implementação modela apenas `legal_hold: bool` no manifesto, exportação e storage. Corrigido com `legal_hold_reason` técnico minimizado obrigatório quando `legal_hold=True`.
- [x] [Review][Patch] Restringir object key ao tenant confiável e ao padrão técnico [`services/audit-evidence/src/creditos_audit_evidence/application/service.py:637`] — `object_key` customizado não precisa começar com `tenants/{tenant_id}/audit/`, permitindo path de outro tenant ou identificador humano em logs/auditoria. A validação também bloqueia qualquer sequência de 11–14 dígitos, podendo rejeitar chave técnica válida aleatoriamente. Corrigido com validação por prefixo confiável e padrão técnico `tenants/{tenant_id}/audit/year=YYYY/month=MM/checkpoint={checkpoint_id}/manifest.json`.
- [x] [Review][Patch] Validar metadados efetivos retornados pelo storage no export [`services/audit-evidence/src/creditos_audit_evidence/application/service.py:674`] — o resultado de `put_object` é aceito sem comparar `body_digest`, `retention_mode`, `retain_until` e `legal_hold` com o manifesto/request. Corrigido para rejeitar/auditar divergência segura antes de registrar exportação.
- [x] [Review][Patch] Verificar existência/metadados no replay idempotente [`services/audit-evidence/src/creditos_audit_evidence/application/service.py:656`] — replay idempotente retorna o registro existente sem `head_object`/reconciliação mínima. Corrigido para detectar objeto ausente/divergente antes de emitir resultado `accepted/idempotent`.

## Dev Notes

### Escopo desta story

- Esta story materializa a etapa lógica de exportação imutável do `Audit & Evidence`, usando domínio, portas e adapters in-memory para provar contrato e comportamento.
- O storage real S3 Object Lock fica representado por porta hexagonal; não adicionar `boto3`, credenciais, buckets, SDK AWS, IaC ou runtime cloud nesta story.
- A exportação deve partir de checkpoint assinado existente da Story 6.4. Não criar um segundo mecanismo de integridade paralelo.
- O pacote exportado deve ser uma prova minimizada: manifesto canônico + referências/digests + metadados de checkpoint/exportação. Não exportar payload bruto de evento, proposta, integração, IA, documento ou logs.

### Decisões e guardrails obrigatórios

- **Modo WORM local:** usar adapter in-memory determinístico para representar object key/version/digest/retention. Ele deve ser suficiente para testes de regra; não deve tentar simular toda a API S3.
- **Manifesto canônico:** incluir `manifest_version`, `tenant_id`, `checkpoint_id`, janela, `event_count`, primeiro/último evento e hash, `batch_digest`, assinatura do checkpoint, algoritmo, canonicalização, classe de retenção, `retention_mode`, `retain_until`, `created_at` e digest do manifesto.
- **Object key sugerida:** `tenants/{tenant_id}/audit/year={YYYY}/month={MM}/checkpoint={checkpoint_id}/manifest.json`, validada como identificador técnico sem dados pessoais.
- **Retenção:** `retain_until` deve ser UTC e futuro no momento da exportação. Não permitir reduzir retenção em replay. Legal hold deve ser metadado explícito, não booleano implícito sem motivo.
- **Idempotência:** repetir a mesma exportação para o mesmo checkpoint deve retornar o registro existente se o manifesto/digest for igual; se qualquer metadado governado divergir, retornar conflito seguro.
- **Auditoria oficial:** exportação e reconciliação são ações sensíveis; devem gerar `AuditEvent` oficial com `event_type` como `audit_worm_export.created`, `audit_worm_export.reconciled` ou equivalente técnico estável. Logs operacionais continuam apenas complementares.
- **Privacidade:** `safe_details` deve continuar usando allowlist fechada. Se novas chaves forem necessárias, adicionar apenas chaves técnicas minimizadas em `domain/value_objects/audit_event.py`; não flexibilizar validação para payload livre.

### Contexto funcional consolidado

- Epic 6 exige auditoria oficial separada de logs operacionais, append-only, hash encadeado, checkpoints assinados e exportação imutável. [Fonte: `_bmad-output/planning-artifacts/epics.md#Epic 6`]
- Story 6.5 exige exportar checkpoints/pacotes mínimos para WORM/S3 Object Lock conforme classe/retenção e reconciliar divergências entre trilha principal, checkpoint e objeto exportado. [Fonte: `_bmad-output/planning-artifacts/epics.md#Story 6.5`]
- OQ-11 decidiu MVP com banco append-only + hash encadeado + checkpoints assinados + exportação periódica imutável; ledger/database especializada ficam fora do MVP. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`]
- AD-8 define que checkpoints e exportações periódicas vão para S3 Object Lock conforme AD-19, usando prova minimizada e nunca payload sensível bruto por padrão. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`]

### Informação técnica atualizada sobre S3 Object Lock

- S3 Object Lock usa modelo WORM e ajuda a impedir exclusão ou sobrescrita por período fixo/variável ou indefinidamente. [Fonte: AWS S3 Object Lock — https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html]
- Object Lock funciona em buckets com versionamento habilitado e a retenção/legal hold protege versões específicas de objeto. [Fonte: AWS S3 Object Lock — https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html]
- Existem modos `GOVERNANCE` e `COMPLIANCE`: `COMPLIANCE` não permite encurtar/remover retenção nem pelo root durante o período; `GOVERNANCE` permite bypass apenas com permissão/header específicos. [Fonte: AWS S3 Object Lock — https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html]
- Para produção, a escolha `GOVERNANCE` versus `COMPLIANCE`, retenção padrão, bucket policy e permissões (`PutObjectRetention`, `PutObjectLegalHold`, `BypassGovernanceRetention`) pertencem à story/ADR/IaC operacional posterior; nesta story, apenas o contrato lógico é modelado.

### Arquivos existentes que devem ser lidos antes de alterar

- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
  - Estado atual: registra eventos oficiais, gera checkpoints assinados, verifica integridade e audita verificação.
  - O que mudar: adicionar comandos/resultados/casos de uso para exportar checkpoint e reconciliar exportação; registrar auditoria oficial minimizada.
  - Preservar: escopos existentes `audit:write`, `audit:read`, `audit:integrity:write`; logs com payload omitido; validação de contexto confiável.

- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_integrity_checkpoint.py`
  - Estado atual: checkpoint imutável com tenant, janela, contagem, primeiro/último evento, digest, assinatura, chave, algoritmo e versão.
  - O que mudar: não alterar se puder compor exportação em nova entidade; se alterar, preservar compatibilidade dos testes da Story 6.4.
  - Preservar: checkpoint é a fonte de prova da janela; WORM exporta/referencia checkpoint, não substitui checkpoint.

- `services/audit-evidence/src/creditos_audit_evidence/domain/services/audit_integrity.py`
  - Estado atual: canonicaliza eventos e calcula digest/checkpoint ID com JSON ordenado e `sha256`.
  - O que mudar: preferir adicionar funções separadas para manifesto WORM (`canonicalize_worm_export_manifest`, `calculate_worm_export_digest`) sem misturar com hash de evento.
  - Preservar: `current_hash` não participa do próprio cálculo; não alterar digest de checkpoint existente.

- `services/audit-evidence/src/creditos_audit_evidence/application/ports/`
  - Estado atual: possui portas para repositório de evento, checkpoint e signer.
  - O que mudar: adicionar porta de repositório de exportações e porta de storage WORM.
  - Preservar: domínio não depende de adapters nem AWS SDK.

- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/`
  - Estado atual: adapters in-memory append-only para eventos e checkpoints.
  - O que mudar: adicionar adapters in-memory para export repository e WORM storage, com `RLock` e conflito seguro.
  - Preservar: isolamento por tenant e determinismo dos testes.

- `services/audit-evidence/tests/unit/test_audit_integrity.py`
  - Estado atual: cobre canonicalização, hash chain, checkpoints, verificação, divergências e auditoria da verificação.
  - O que mudar: pode criar novo `test_audit_worm_export.py` para evitar arquivo excessivo; reutilizar fixtures/padrões existentes.
  - Preservar: todos os testes de integridade existentes devem continuar passando.

- `services/audit-evidence/README.md`
  - Estado atual: documenta WORM/S3 Object Lock como trabalho futuro.
  - O que mudar: após implementação, documentar exportação WORM lógica/in-memory e manter apenas S3 real/IaC/KMS/scheduler como futuro.

### Padrões arquiteturais obrigatórios

- Backend segue DDD + arquitetura hexagonal; domínio não depende de FastAPI, SQLAlchemy, gRPC, NATS, OpenTelemetry, Kubernetes ou AWS SDK.
- `Audit & Evidence` é dono exclusivo de auditoria oficial, evidências, hash, checkpoint e exportação imutável.
- Nenhuma consulta direta cross-service, join cross-service ou dependência com `Reporting & Insights` nesta story.
- Não introduzir novo microsserviço, worker real, scheduler real ou infraestrutura real.
- Não adicionar dependência sem justificativa; usar biblioteca padrão (`hashlib`, `json`, `datetime`, `dataclasses`) sempre que suficiente.

### Testes esperados

- Exportação:
  - Checkpoint existente exporta manifesto com digest determinístico e metadados WORM.
  - Janela sem checkpoint ou checkpoint divergente não exporta.
  - Retenção vencida, modo inválido ou object key inválida são rejeitados.
  - Replay idempotente retorna exportação existente; replay divergente gera conflito seguro.

- Reconciliação:
  - Objeto exportado íntegro reconcilia como válido.
  - Digest do manifesto, version ID, retention mode ou retain-until divergente gera issue segura.
  - Falha de storage vira resultado técnico controlado e evento oficial, sem traceback/payload bruto.

- Segurança/privacidade:
  - Resultado, logs e auditoria não contêm payload bruto, CPF/CNPJ, e-mail, token, prompt/output, documento ou body de provider.
  - Tenant A não consegue reconciliar/exportar checkpoint de Tenant B.
  - Escopo ausente é negado por `AuditEvidenceTenantContextError`.

### Comandos de validação esperados

- `.venv/bin/pytest services/audit-evidence/tests/unit -q`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/pyright`
- `uv lock --check` quando `uv` estiver disponível no ambiente; se indisponível, registrar limitação ambiental sem alterar lockfile quando nenhuma dependência for adicionada.

## Project Structure Notes

- Criar novos arquivos dentro de `services/audit-evidence/src/creditos_audit_evidence/domain`, `application/ports` e `adapters/persistence` conforme padrão atual.
- Atualizar `__init__.py` apenas para exports necessários e estáveis.
- Evitar arquivos em `packages/` salvo se houver utilidade transversal comprovada; esta story é específica do bounded context `Audit & Evidence`.
- Preferir novo teste `services/audit-evidence/tests/unit/test_audit_worm_export.py` para manter a Story 6.5 isolada.

## References

- `_bmad-output/planning-artifacts/epics.md#Story 6.5`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/recomendacoes-decisoes-abertas.md#OQ-11`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md#AD-8`
- `_bmad-output/implementation-artifacts/6-4-integridade-verificavel-com-hash-encadeado-e-checkpoints.md`
- `services/audit-evidence/README.md`
- AWS S3 Object Lock: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html`

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

- Story criada a partir do `bmad-create-story` em 2026-09-21.
- Fonte principal: Epic 6 / Story 6.5 em `_bmad-output/planning-artifacts/epics.md`.
- Contexto anterior: Story 6.4 mergeada no PR #57 e `main` sincronizada em `0be29e6`.
- Jira principal identificado: `CTOS-57`; subtarefas criadas: `CTOS-353` a `CTOS-359`.
- Implementação executada na branch `agent/story-6-5-exportacao-imutavel-worm`.
- Validação focada: `.venv/bin/pytest services/audit-evidence/tests/unit -q` — 67 passed.
- Gates locais: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .` e `.venv/bin/pyright` — passaram.
- Regressão completa fora do sandbox após patches de review: `.venv/bin/pytest -q` — 699 passed, 1 failed por `scripts/dev: line 47: uv: command not found`, limitação ambiental preexistente.
- `uv lock --check` não foi executado localmente porque `uv` não está disponível no PATH do ambiente.
- Code review BMAD executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 7 achados de patch aplicados.
- Validação pós-review: `.venv/bin/pytest services/audit-evidence/tests/unit -q` — 71 passed.
- Gates pós-review: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .` e `.venv/bin/pyright` — passaram.

### Completion Notes List

- Story 6.5 detalhada e pronta para desenvolvimento.
- Escopo fechado para contrato/domínio/portas/adapters in-memory de exportação WORM e reconciliação.
- AWS S3 Object Lock real, IaC, KMS, bucket policy, scheduler e runbooks permanecem fora de escopo da implementação desta story.
- Entidades, value objects e manifesto WORM canônico implementados com `sha256`, retenção futura UTC, modo `GOVERNANCE`/`COMPLIANCE`, object key técnico e ausência de payload bruto.
- Portas hexagonais e adapters in-memory determinísticos criados para repositório de exportação e storage WORM.
- Casos de uso adicionados para exportar checkpoint assinado existente e reconciliar objeto WORM, com escopos segregados, idempotência por tenant/checkpoint/janela e conflitos seguros.
- Auditoria oficial minimizada registrada para exportação aceita/rejeitada e reconciliação válida/inválida, separada de logs operacionais.
- README e deferred work atualizados para deixar S3 Object Lock real, IaC, KMS, scheduler, runbooks e validação jurídica/contratual como trabalho futuro.
- Patches de code review aplicados: reconciliação recompõe digest do corpo, valida manifesto/metadata governada, audita falhas esperadas/técnicas, inclui janela em evento oficial, exige `legal_hold_reason`, restringe object key por tenant/checkpoint e valida replay idempotente contra storage.

### File List

- `_bmad-output/implementation-artifacts/6-5-exportacao-imutavel-para-worm.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/audit-evidence/README.md`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_worm_export_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/adapters/persistence/in_memory_audit_worm_storage.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_worm_export_repository.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/ports/audit_worm_storage.py`
- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/__init__.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/entities/audit_worm_export.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/services/audit_integrity.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_event.py`
- `services/audit-evidence/src/creditos_audit_evidence/domain/value_objects/audit_worm_export.py`
- `services/audit-evidence/tests/unit/test_audit_worm_export.py`

## Change Log

| Data | Versão | Descrição | Autor |
| --- | --- | --- | --- |
| 2026-09-21 | 0.1 | Story criada via `bmad-create-story`; contexto do Epic 6, Story 6.4, AD-8, OQ-11 e S3 Object Lock consolidado. | Codex |
| 2026-09-21 | 1.0 | Exportação WORM lógica implementada com domínio, portas, adapters in-memory, casos de uso, auditoria oficial, documentação e testes. | Codex |
| 2026-09-21 | 1.1 | Achados de `bmad-code-review` corrigidos e story marcada como `done`. | Codex |
