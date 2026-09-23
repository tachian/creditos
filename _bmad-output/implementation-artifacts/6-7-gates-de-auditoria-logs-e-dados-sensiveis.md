---
baseline_commit: e6cc84cc3d41ae7818b7f758fec1b09944029795
---

# Story 6.7: Gates de Auditoria, Logs e Dados Sensíveis

Status: done

## Story

Como equipe de engenharia e segurança,
quero gates automatizados que detectem ausência de auditoria crítica e vazamento em logs/traces/eventos,
para que rastreabilidade e privacidade sejam garantidas continuamente.

## Acceptance Criteria

1. **Gate de auditoria obrigatória para decisões:** dado um fluxo de decisão final, política, simulação ou catálogo de reason codes, quando os testes de governança rodam, então eles provam que eventos críticos de auditoria são emitidos com tenant, ator técnico/humano, recurso, resultado, correlation ID, trace ID e versões aplicáveis.
2. **Gate de auditoria obrigatória para alterações sensíveis:** dado alteração em política, catálogo, agente de IA, exportação WORM ou acesso/leitura de auditoria, quando a operação ocorre, então a suíte falha se a auditoria oficial for omitida ou se a operação prosseguir sem estado controlado em falha crítica.
3. **Gate transversal de vazamento em logs/traces/eventos:** dado logs, spans, eventos, safe details e respostas gerados por testes representativos, quando o scanner de dados sensíveis roda, então ele não encontra CPF/CNPJ completos, e-mail completo, telefone completo, token, segredo, documento/imagem, renda detalhada, payload bruto, prompt/output de IA ou headers de autorização.
4. **Preservação de rastreabilidade segura:** dado o mesmo scanner, quando ele valida artefatos minimizados, então correlation ID, request ID, trace ID, tenant confiável, operação, contrato, versão, status, duração e referências técnicas seguras continuam presentes quando aplicáveis.
5. **Integração com CI existente:** dado um pull request, quando o CI executa `uv run pytest`, então os novos gates rodam junto da suíte padrão, sem exigir serviço externo, licença externa, rede, Docker adicional ou baseline manual de DLP.
6. **Reuso de componentes existentes:** dado o pacote `creditos_security` e os testes já criados, quando a story é implementada, então ela reutiliza `mask_sensitive_data`, `mask_text`, `hmac_sha256_identifier`, `build_structured_log`, helpers de auditoria existentes e padrões de testes atuais, sem criar framework paralelo de logging/auditoria.
7. **Sem dados reais e sem falsos positivos ruidosos:** dado fixtures e asserts de segurança, quando os gates rodam, então usam apenas dados sintéticos claramente inválidos/seguros, redigem achados em mensagens de teste e evitam termos/documentação que disparem secret scanning sem necessidade.

## Tasks / Subtasks

- [x] CTOS-366 — Criar helper de gate para vazamento sensível em artefatos serializados (AC: 3, 4, 6, 7)
  - [x] Adicionar helper de teste reutilizável em `tests/` ou módulo de teste apropriado para serializar estruturas e verificar ausência de padrões sensíveis.
  - [x] Cobrir CPF/CNPJ com e sem pontuação, Unicode compatível, e-mail completo, telefone completo, bearer/API token, segredo/senha, headers de autorização, payload/body/provider raw, prompt/output de IA, documento/imagem e renda detalhada.
  - [x] Garantir mensagens de falha redigidas, sem imprimir o valor bruto encontrado.

- [x] CTOS-367 — Consolidar gate de auditoria crítica para Decision e Automated Review (AC: 1, 2, 6)
  - [x] Validar fluxos já existentes em `services/decision/tests/unit/` que publicam auditoria para decisão, política, simulação e catálogo.
  - [x] Validar fluxos em `services/automated-review/tests/unit/` para configuração de agente, execução consultiva, fallback e evidência consultiva.
  - [x] Adicionar regressões que falhem se publishers de auditoria forem omitidos, se evento crítico não possuir contexto mínimo ou se falha crítica permitir publicação insegura.

- [x] CTOS-368 — Consolidar gate de auditoria oficial e leitura/exportação no Audit & Evidence (AC: 1, 2, 4, 6)
  - [x] Validar `AuditEvent` mínimo, append-only, hash encadeado, leitura auditável, checkpoint e exportação WORM.
  - [x] Confirmar que logs operacionais continuam complementares e não substituem `AuditEvent`.
  - [x] Verificar que safe details e operational evidence refs não carregam payload bruto nem identificadores diretos completos.

- [x] CTOS-369 — Criar gate transversal de logs, traces, eventos e safe details (AC: 3, 4, 5, 6, 7)
  - [x] Exercitar amostras representativas de `Proposal Intake`, `Decision`, `Integration`, `Automated Review`, `Audit & Evidence`, `creditos_observability` e `creditos_security`.
  - [x] Validar ausência de vazamento nos logs estruturados, spans/atributos allowlisted, eventos de auditoria, eventos de domínio e respostas minimizadas.
  - [x] Validar presença de rastreabilidade segura, incluindo `correlation_id`, `request_id`, `trace_id`, `tenant_id` confiável e `technical_result` quando aplicável.

- [x] CTOS-370 — Garantir execução pelos quality gates existentes (AC: 5, 7)
  - [x] Confirmar que os novos testes são descobertos por `uv run pytest` sem markers especiais obrigatórios.
  - [x] Atualizar testes estruturais do CI apenas se necessário; não adicionar novo serviço externo nem baseline de scanner.
  - [x] Rodar gates locais relevantes: testes focados, `pytest services packages -q`, `ruff format --check`, `ruff check`, `pyright` e Gitleaks quando Docker estiver disponível.

- [x] CTOS-371 — Sincronizar BMAD e Jira da Story 6.7 (AC: 5, 7)
  - [x] Atualizar `sprint-status.yaml` para `ready-for-dev`.
  - [x] Criar/sincronizar subtarefas Jira vinculadas a `CTOS-59`.
  - [x] Registrar branch planejada `agent/story-6-7-audit-logs-sensitive-data-gates` e manter Jira em `Tarefas pendentes` até o início do `bmad-dev-story`.

### Review Findings

- [x] [Review][Patch] Endurecer scanner para chaves sensíveis, Unicode, valores não-string e allowlist sob paths sensíveis [tests/test_epic6_audit_logs_sensitive_data_gates.py:55]
- [x] [Review][Patch] Validar versões aplicáveis e cardinalidade dos eventos oficiais de auditoria [tests/test_epic6_audit_logs_sensitive_data_gates.py:180]
- [x] [Review][Patch] Trocar fixtures de CPF/CNPJ/telefone por identificadores sintéticos claramente inválidos [tests/test_epic6_audit_logs_sensitive_data_gates.py:108]
- [x] [Review][Patch] Normalizar tipos anômalos antes da serialização do scanner [tests/test_epic6_audit_logs_sensitive_data_gates.py:208]

## Dev Notes

### Escopo desta story

- Esta story cria **gates automatizados** sobre auditoria, logs, traces, eventos e dados sensíveis. Ela não deve implementar SIEM, DLP externo, dashboards, retenção física, storage adicional, Collector OpenTelemetry, nova infraestrutura ou novo serviço.
- A implementação deve priorizar testes de regressão e helpers reutilizáveis para impedir que histórias futuras quebrem auditoria oficial ou vazem dados sensíveis.
- Os gates devem rodar no CI atual via `uv run pytest`; só alterar `.github/workflows/ci.yml` se houver lacuna estrutural real.
- Todos os dados de teste devem ser sintéticos; evitar exemplos que pareçam tokens reais ou chaves reais para não gerar ruído no Gitleaks.

### Contexto funcional consolidado

- Epic 6 exige trilha oficial append-only de auditoria, evidências críticas, alterações sensíveis auditadas, integridade verificável, exportação WORM, logs seguros e gates contínuos. [Fonte: `_bmad-output/planning-artifacts/epics.md#Epic 6`]
- Story 6.7 exige gates que detectem ausência de auditoria e vazamento em logs, traces e eventos. [Fonte: `_bmad-output/planning-artifacts/epics.md#Story 6.7`]
- OQ-11 define que auditoria é separada de logs operacionais, que eventos mínimos precisam de tenant, ator, origem, ação, recurso, resultado, correlation ID, trace ID, hashes e versões aplicáveis, e que falha de auditoria crítica bloqueia publicação de decisão final. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`]
- OQ-10 define máscara forte para logs, traces, dashboards e respostas operacionais; testes automatizados devem verificar vazamento de dados sensíveis em logs e respostas. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md`]
- A arquitetura define que `Audit & Evidence` é fonte de verdade para trilha oficial, enquanto logs/traces/métricas são operacionais e devem incluir tenant confiável sem payload sensível bruto. [Fonte: `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`]

### Arquitetura e padrões obrigatórios

- Backend segue DDD + arquitetura hexagonal; gates devem testar comportamento via portas/adapters existentes, não acessar internals para simular sucesso falso.
- Cada serviço mantém ownership de dados. Não criar query cross-service nem acoplar testes a banco compartilhado.
- Auditoria oficial pertence a `services/audit-evidence`; logs operacionais usam `packages/observability`; mascaramento e HMAC usam `packages/security`.
- CI atual já roda secret scan com Gitleaks, `uv lock --check`, `uv sync --locked`, Ruff, Pyright, contratos, harness local e pytest. Novos gates devem entrar na suíte pytest padrão. [Fonte: `.github/workflows/ci.yml`]
- Não adicionar dependências externas sem ADR/justificativa. Para esta story, biblioteca padrão + pytest + pacotes locais são suficientes.

### Arquivos existentes que devem ser lidos antes de alterar

- `tests/test_sensitive_data_masking.py`
  - Estado atual: cobre mascaramento de texto, estruturas recursivas e HMAC.
  - O que mudar: pode receber novos asserts transversais se forem úteis, mas evitar duplicar testes unitários já existentes em `packages/security/tests/unit/test_masking.py`.
  - Preservar: dados sintéticos e ausência de valores que pareçam credenciais reais.

- `packages/security/src/creditos_security/masking.py`
  - Estado atual: mascara CPF/CNPJ/e-mail/telefone, omite chaves perigosas, normaliza Unicode antes das regexes, limita profundidade/ciclos, valida fingerprints/digests 64-hex e preserva `prompt_version` técnico.
  - O que mudar: evitar alterações salvo bug encontrado durante gates; a story deve preferir reutilizar o helper.
  - Preservar: API pública `mask_text`, `mask_sensitive_data`, `hmac_sha256_identifier`, `OMITTED` e `FINANCIAL_OMITTED`.

- `packages/observability/src/creditos_observability/logging.py`
  - Estado atual: `build_structured_log` cria envelope com campos obrigatórios, sanitiza campos técnicos, omite payload, mascara `extra` e inclui `technical_result`.
  - O que mudar: evitar alterações salvo lacuna real; gates devem provar o contrato.
  - Preservar: assinatura pública e comportamento esperado por serviços existentes.

- `services/decision/tests/unit/test_epic4_decision_governance_gates.py`
  - Estado atual: cobre determinismo, política/catálogo publicados, explainability segura, autoridade final não-IA/provedor e ordem de auditoria.
  - O que mudar: pode ser estendido ou referenciado por novo gate consolidado para garantir eventos obrigatórios e safe output.
  - Preservar: foco em domínio Decision, sem acoplar a infraestrutura real.

- `services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py`
  - Estado atual: valida integração do publisher de auditoria do Decision com Audit & Evidence.
  - O que mudar: adicionar regressões para ausência de auditoria crítica ou safe details minimizados, se necessário.
  - Preservar: adapter in-memory e falhas controladas.

- `services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py`
  - Estado atual: valida auditoria oficial para Automated Review.
  - O que mudar: reforçar gate de alteração sensível de agente/modelo/prompt e execução consultiva, se lacuna existir.
  - Preservar: prompts minimizados e fingerprints técnicos.

- `services/audit-evidence/tests/unit/test_audit_application_service.py`
  - Estado atual: cobre registro append-only, escopos, tenant confiável, leitura auditável e logs seguros.
  - O que mudar: adicionar gate consolidado de evento mínimo e vazamento em safe details, se necessário.
  - Preservar: sem update/delete, sem payload bruto.

- `services/audit-evidence/tests/unit/test_audit_event_model.py`
  - Estado atual: valida modelo `AuditEvent`, detalhes seguros e rejeições de eventos inválidos.
  - O que mudar: reforçar ausência de payload/log/trace como substituto da auditoria oficial, se necessário.
  - Preservar: invariantes de evento oficial.

- `.github/workflows/ci.yml` e `tests/test_ci_workflow.py`
  - Estado atual: CI já executa pytest completo e secret scan.
  - O que mudar: apenas se os novos gates exigirem ajuste estrutural; preferir não alterar workflow.
  - Preservar: `pull_request`, permissões mínimas, checkout sem credenciais persistidas e Gitleaks com `--redact=100`.

### Padrões de implementação esperados

- Preferir um helper de teste puro, pequeno e local à suíte, por exemplo em `tests/test_epic6_audit_logs_sensitive_data_gates.py`, para serializar objetos e procurar padrões proibidos.
- O helper deve reportar apenas o tipo de padrão e o caminho do artefato, sem imprimir o valor sensível completo.
- O scanner de teste deve usar padrões sintéticos explícitos, incluindo Unicode compatível, mas evitar strings que Gitleaks trate como credenciais reais.
- Para auditoria obrigatória, testar efeitos observáveis: eventos publicados, repositórios in-memory, safe details, logs emitidos e exceções controladas.
- Não criar “auditoria fake” só para satisfazer teste. Se um fluxo crítico não audita, corrigir o fluxo ou adapter existente.
- Não usar snapshots brutos grandes; montar amostras mínimas e determinísticas.
- Não ampliar escopo para observabilidade de produção ou dashboards; isso pertence ao Epic 7.

### Testes esperados

- Novo gate ou extensões que validem ausência de vazamento em:
  - logs estruturados (`build_structured_log` e logs dos serviços);
  - spans/atributos allowlisted de `creditos_observability.telemetry`;
  - eventos oficiais de auditoria e `safe_details`;
  - eventos/resultados minimizados de Decision, Automated Review, Integration, Proposal Intake e Audit & Evidence.
- Regressões para garantir que:
  - auditoria crítica de decisões e alterações sensíveis é emitida;
  - falha de auditoria crítica não permite publicação final insegura;
  - correlation ID, request ID, trace ID e tenant confiável continuam presentes;
  - `prompt_version` e fingerprints/digests válidos permanecem disponíveis como referências técnicas seguras.
- Comandos mínimos de validação:
  - `.venv/bin/pytest tests/test_sensitive_data_masking.py packages/security/tests/unit/test_masking.py packages/observability/tests/unit/test_logging.py -q`
  - `.venv/bin/pytest services/decision/tests/unit services/automated-review/tests/unit services/audit-evidence/tests/unit -q`
  - `.venv/bin/pytest services packages -q`
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
  - `docker run ... gitleaks ... --log-opts="origin/main..HEAD"` quando Docker estiver disponível.

### Aprendizados da Story 6.6

- Code review externo encontrou riscos reais em Unicode, referências seguras permissivas e `prompt_version`; Story 6.7 deve proteger esses aprendizados com gates para evitar regressão.
- Gitleaks pode acusar falso positivo em texto de documentação; preferir “credenciais”, “segredos” ou termos descritivos em português quando possível e validar localmente quando a story alterar docs.
- `uv lock --check` pode não rodar localmente se `uv` não estiver no PATH; se nenhuma dependência for adicionada, registrar como limitação ambiental, não alterar `uv.lock` sem necessidade.
- A suíte completa local pode falhar em `tests/test_local_harness.py` por restrição de socket e `uv` ausente; não mascarar falhas reais dos testes focados.

## Project Structure Notes

- Novos testes transversais devem ficar em `tests/` quando cruzarem múltiplos serviços/pacotes.
- Testes específicos de serviço devem permanecer dentro de `services/<service>/tests/unit/`.
- Helpers que são apenas de teste não devem entrar em `packages/security` ou `packages/observability` como API pública.
- Não criar novo diretório de “compliance scanner” nem script de CI se pytest já cobre o gate.

## References

- `_bmad-output/planning-artifacts/epics.md#Story 6.7`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `_bmad-output/implementation-artifacts/6-6-logs-estruturados-e-mascaramento-obrigatorio.md`
- `.github/workflows/ci.yml`
- `tests/test_ci_workflow.py`
- `tests/test_sensitive_data_masking.py`
- `packages/security/src/creditos_security/masking.py`
- `packages/observability/src/creditos_observability/logging.py`
- `services/decision/tests/unit/test_epic4_decision_governance_gates.py`
- `services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py`
- `services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py`
- `services/audit-evidence/tests/unit/test_audit_application_service.py`
- `services/audit-evidence/tests/unit/test_audit_event_model.py`

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

- Story criada após merge do PR #59 da Story 6.6.
- `main` sincronizada em `e6cc84cc3d41ae7818b7f758fec1b09944029795`.
- Jira principal identificado: `CTOS-59`.
- Próxima branch planejada: `agent/story-6-7-audit-logs-sensitive-data-gates`.
- Branch de desenvolvimento criada: `agent/story-6-7-audit-logs-sensitive-data-gates`.
- Teste focado executado: `.venv/bin/pytest tests/test_epic6_audit_logs_sensitive_data_gates.py -q` — 4 passed.
- Testes focados de auditoria executados: `.venv/bin/pytest tests/test_epic6_audit_logs_sensitive_data_gates.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py services/audit-evidence/tests/unit/test_audit_application_service.py services/audit-evidence/tests/unit/test_audit_event_model.py -q` — 60 passed.
- Quality gates executados: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright` — passed.
- Suíte ampla executada: `.venv/bin/pytest services packages tests/test_epic6_audit_logs_sensitive_data_gates.py -q` — 684 passed.
- Testes raiz relacionados executados: `.venv/bin/pytest tests/test_sensitive_data_masking.py tests/test_observability_foundation.py tests/test_ci_workflow.py -q` — 22 passed.
- `uv run pytest tests/test_epic6_audit_logs_sensitive_data_gates.py -q` não executou localmente porque `uv` não está instalado no PATH desta sessão.
- Gitleaks via Docker nos arquivos alterados — no leaks found.
- Regressão completa executada: `.venv/bin/pytest -q` — 705 passed, 3 failed em `tests/test_local_harness.py` por limitações ambientais conhecidas (`uv` ausente no PATH e criação de socket bloqueada).
- Code review executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 4 patches resolvidos.
- Validação pós-review executada: `.venv/bin/pytest tests/test_epic6_audit_logs_sensitive_data_gates.py tests/test_sensitive_data_masking.py packages/security/tests/unit/test_masking.py packages/observability/tests/unit/test_logging.py services/decision/tests/unit/test_credit_decision_audit_evidence_adapter.py services/automated-review/tests/unit/test_automated_review_audit_evidence_adapter.py services/audit-evidence/tests/unit/test_audit_application_service.py services/audit-evidence/tests/unit/test_audit_event_model.py -q` — 70 passed.
- Quality gates pós-review executados: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/pyright` — passed.
- Suíte ampla pós-review executada: `.venv/bin/pytest services packages tests/test_epic6_audit_logs_sensitive_data_gates.py -q` — 685 passed.
- Gitleaks pós-review nos arquivos alterados — no leaks found.

### Completion Notes List

- Story 6.7 criada com contexto de auditoria, logs, dados sensíveis, CI e aprendizados da Story 6.6.
- Subtarefas Jira devem ser sincronizadas antes do início do `bmad-dev-story`.
- Criado gate transversal em pytest para detectar vazamento sensível sem ecoar valores brutos nas falhas.
- Consolidada validação de auditoria oficial mínima para Decision, Automated Review e Audit & Evidence usando adapters e entidades existentes.
- Nenhuma alteração no workflow de CI foi necessária; os novos gates ficam na suíte pytest padrão.
- Story marcada como `review`; única pendência local é ambiental e restrita ao harness local, sem relação com os arquivos alterados.
- Achados do code review resolvidos: scanner endurecido para chaves sensíveis, Unicode, tipos não-string e tipos anômalos; auditoria oficial agora valida cardinalidade e versões aplicáveis; fixtures sensíveis foram trocadas por valores sintéticos inválidos.
- Corrigido mascaramento de `raw_output` em `creditos_security.masking` para impedir vazamento em `build_structured_log(extra=...)`.
- Story marcada como `done` após resolução dos achados de review.

### File List

- `_bmad-output/implementation-artifacts/6-7-gates-de-auditoria-logs-e-dados-sensiveis.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `packages/security/src/creditos_security/masking.py`
- `tests/test_epic6_audit_logs_sensitive_data_gates.py`

## Change Log

| Data | Versão | Descrição | Autor |
| --- | --- | --- | --- |
| 2026-09-22 | 0.1 | Story criada via `bmad-create-story`; contexto do Epic 6, OQ-10, OQ-11, CI, Story 6.6 e gates existentes consolidado. | Codex |
| 2026-09-22 | 0.2 | Implementados gates pytest de auditoria, logs, traces, safe details e dados sensíveis; story enviada para review. | Codex |
| 2026-09-22 | 0.3 | Achados do code review resolvidos; scanner endurecido e mascaramento de `raw_output` corrigido. | Codex |
