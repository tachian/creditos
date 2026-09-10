---
jira_issue: CTOS-49
branch: agent/story-5-3-validacao-saida-guardrails-classificacao
baseline_commit: d45e9e8
created_at: 2026-09-10
subtasks:
  - CTOS-294
  - CTOS-295
  - CTOS-296
  - CTOS-298
  - CTOS-297
  - CTOS-299
---

# Story 5.3: Validação de Saída, Guardrails e Classificação

Status: done

## Story

Como `Automated Review Service`,
quero tratar saídas de IA como não confiáveis,
para que apenas evidências consultivas válidas, seguras e classificadas sejam usadas pelo fluxo decisório.

## Acceptance Criteria

1. **Schema explícito de saída consultiva**
   - **Given** uma resposta do executor consultivo
   - **When** o serviço processa a saída
   - **Then** valida schema fechado, campos obrigatórios, tipos, limites de tamanho e listas permitidas
   - **And** rejeita campos desconhecidos, payload livre, texto bruto não governado e estruturas aninhadas arbitrárias.

2. **Classificação consultiva permitida**
   - **Given** uma resposta válida de IA
   - **When** a saída for aceita
   - **Then** classifica achados apenas como lacunas, inconsistências, fatores explicáveis ou limitações consultivas
   - **And** cada item aceito possui referência técnica, severidade/sinal permitido, confiança opcional em faixa governada e motivo seguro.

3. **Bloqueio de autonomia decisória**
   - **Given** uma saída tentando aprovar, reprovar, alterar termos, executar callback, chamar ferramenta, publicar decisão ou acionar integração
   - **When** os guardrails avaliam a resposta
   - **Then** a saída é bloqueada e convertida em fallback consultivo
   - **And** nenhuma decisão final, termo aprovado ou ação externa é persistida, logada como aceita ou exposta.

4. **Bloqueio de conteúdo sensível e prompt injection**
   - **Given** uma saída contendo CPF, CNPJ, e-mail, telefone, endereço, nome, documento, token, segredo, header sensível, prompt/instrução vazada, tentativa de jailbreak ou dado financeiro detalhado
   - **When** os guardrails avaliam a resposta
   - **Then** a saída é bloqueada ou reduzida a metadados seguros
   - **And** logs, auditoria e repositório não persistem o conteúdo sensível bruto.

5. **Fallback auditável para saída inválida**
   - **Given** erro de schema, guardrail bloqueante, confiança inválida, output malformado ou saída autônoma
   - **When** a validação falha
   - **Then** a execução retorna status `fallback`, registra `limitation_ref` técnica específica e evento auditável minimizado
   - **And** preserva tenant, produto, canal, propósito, config/version, prompt fingerprint, correlation ID e trace ID quando disponível.

6. **Sem ampliação indevida de escopo**
   - **Given** que esta story valida e classifica saída de IA
   - **When** o dev agent implementar
   - **Then** não adiciona provedor/modelo real, SDK de IA, endpoint público, gRPC real, NATS, banco real, dashboard, evidência oficial append-only ou vínculo final com proposta
   - **And** não altera a fonte de decisão final do `Decision Service`.

## Tasks / Subtasks

- [x] CTOS-294 — Modelar contrato de saída consultiva validável (AC: 1, 2, 6)
  - [x] Criar value objects de saída em `services/automated-review/src/creditos_automated_review/domain/value_objects` ou entidades de domínio quando houver invariante agregada.
  - [x] Definir catálogo fechado de tipos de item consultivo: lacuna, inconsistência, fator explicável e limitação.
  - [x] Definir validações de referência técnica, severidade/sinal permitido, confiança opcional e motivo seguro.
  - [x] Rejeitar campos livres, estruturas aninhadas arbitrárias, payload bruto e textos longos não governados.

- [x] CTOS-295 — Implementar guardrails de saída e bloqueio de autonomia (AC: 2, 3, 4)
  - [x] Bloquear qualquer semântica de decisão final: aprovação, reprovação, alteração de termos, callbacks, tool use, integrações externas e publicação de decisão.
  - [x] Bloquear prompt injection, jailbreak, vazamento de instruções, segredos e dados sensíveis usando os padrões já existentes de mascaramento/sensibilidade.
  - [x] Garantir que achados aceitos sejam sempre consultivos e nunca substituam reason codes determinísticos do `Decision Service`.
  - [x] Garantir mensagens de erro seguras, sem ecoar conteúdo inválido ou sensível.

- [x] CTOS-296 — Integrar validação ao fluxo de execução consultiva (AC: 1, 3, 5)
  - [x] Estender `ConsultativeReviewOutput` ou criar saída validada separada sem quebrar a porta existente desnecessariamente.
  - [x] Validar a saída antes de construir `AutomatedReviewExecutionResult` aceito.
  - [x] Converter falhas de schema/guardrail em fallback auditável com `limitation_ref` específica.
  - [x] Preservar idempotência/reserva atômica de `execution_id` criada na Story 5.2.

- [x] CTOS-298 — Registrar logs e auditoria minimizados da validação (AC: 4, 5)
  - [x] Incluir contagens seguras de itens aceitos/bloqueados por classificação, sem conteúdo bruto.
  - [x] Garantir `event_type` coerente com status real (`completed`, `fallback`, `blocked` quando aplicável).
  - [x] Preservar `tenant_id`, `tenant_isolation_tier`, `correlation_id`, `request_id` e `trace_id` do contexto confiável/observável.
  - [x] Não persistir prompt, output bruto, payload bruto ou dados sensíveis em repositório, logs, audit intent ou string representation relevante.

- [x] CTOS-297 — Criar regressões RED/GREEN para validação de saída (AC: 1-6)
  - [x] Testar saída válida com itens consultivos aceitos e classificados.
  - [x] Testar rejeição de status/ação autônoma: `approved`, `rejected`, alteração de termos, tool/callback/integration.
  - [x] Testar bloqueio de prompt injection e vazamento sintético de dado sensível sem usar PII realista.
  - [x] Testar fallback para schema inválido, confiança fora de faixa, referência inválida e campo desconhecido.
  - [x] Testar que logs/auditoria/repositório não contêm conteúdo bruto inválido ou sensível.

- [x] CTOS-299 — Atualizar documentação e rastreabilidade BMAD/Jira (AC: 5, 6)
  - [x] Atualizar `services/automated-review/README.md` com o fluxo da Story 5.3.
  - [x] Atualizar esta story com evidências de testes, decisões locais e arquivos alterados.
  - [x] Sincronizar subtarefas Jira antes da implementação e mover cards conforme avanço.
  - [x] Registrar limitações conhecidas para Story 5.4/5.5 quando surgirem vínculos com proposta ou fallback operacional ampliado.

### Review Findings

- [x] [Review][Patch] `evidence_refs` rejeita arrays/listas JSON válidos e força fallback indevido [services/automated-review/src/creditos_automated_review/domain/value_objects/review_output.py:372]
- [x] [Review][Patch] Guardrails de `safe_summary` não cobrem frases comuns de chamada de ferramenta/ação externa [services/automated-review/src/creditos_automated_review/domain/value_objects/review_output.py:39]

## Dev Notes

### Escopo desta story

- Implementar validação profunda da saída do executor consultivo, guardrails de resposta e classificação dos achados consultivos dentro do `Automated Review Service`.
- O resultado aceito continua sendo consultivo. A decisão final, termos aprovados, reason codes determinísticos e publicação de decisão continuam pertencendo ao `Decision Service`.
- Esta story não transforma o resultado validado em evidência final vinculada à proposta; esse vínculo pertence à Story 5.4.
- Esta story não implementa política operacional completa de fallback de provedor/modelo; fallback operacional ampliado pertence à Story 5.5. Aqui, falha de saída/guardrail deve produzir fallback auditável mínimo.
- Não selecionar fornecedor/modelo, não adicionar SDK de IA e não criar endpoint ou protocolo real novo.

### Modelo esperado

- Reusar a base da Story 5.2:
  - `ConsultativeReviewOutput` em `application/ports/consultative_review_executor.py` é a saída atual do executor mockado.
  - `AutomatedReviewExecutionResult` em `domain/entities/automated_review_execution.py` já bloqueia decisão final, termos aprovados e ações externas.
  - `execute_consultative_review` em `application/service.py` já converte exceções e outputs inválidos em fallback auditável.
- A Story 5.3 deve adicionar um contrato explícito para conteúdo consultivo validado, por exemplo:
  - `ReviewOutputItem` ou nome equivalente, com `item_ref`, `item_type`, `severity`, `confidence`, `reason_ref`/`safe_summary_ref` e `evidence_refs` técnicos.
  - `ReviewOutputValidationResult` ou equivalente, com status validado, itens aceitos, itens bloqueados por contagem/motivo técnico e `limitation_refs`.
- O contrato deve evitar texto livre extenso. Quando resumo for necessário, usar identificadores técnicos, motivos catalogados ou texto curto validado e não sensível.
- Se o executor mockado precisar simular achados, ele deve retornar estruturas governadas e sintéticas, nunca payload bruto nem PII realista.

### Classificações permitidas

- Tipos consultivos permitidos nesta story:
  - `missing_data`: lacuna de informação ou dado necessário ausente.
  - `inconsistency`: inconsistência entre sinais/entradas minimizadas.
  - `explainability_factor`: fator explicável sugerido para investigação/explicação.
  - `limitation`: limitação, fallback ou ausência de revisão confiável.
- Severidade/sinal deve ser catálogo fechado, por exemplo `info`, `low`, `medium`, `high`, sem semântica de aprovação/reprovação.
- Confiança, quando presente, deve estar em faixa governada, preferencialmente inteiro de 0 a 100 ou decimal fechado de 0 a 1, mas a escolha deve ser consistente e testada.
- Não criar reason codes de decisão final nesta story; reason codes determinísticos pertencem ao Epic 4/Decision.

### Segurança, privacidade e guardrails

- Saídas de IA são sempre não confiáveis. Validar antes de persistir, logar ou auditar como aceitas.
- Bloquear ou converter para fallback qualquer saída que contenha:
  - CPF, CNPJ, e-mail completo, nome, endereço, telefone, documento, token, segredo, credential, header sensível ou dado financeiro detalhado.
  - Prompt injection, jailbreak, instrução vazada, tentativa de ignorar regras, tool call, callback, comando externo ou integração.
  - Termos como aprovação/reprovação/alteração de termos quando usados como decisão final ou ação autônoma.
- Erros devem reportar códigos técnicos e `field_path`, sem ecoar o conteúdo inválido.
- Logs e audit intents podem carregar status, contagens, IDs técnicos, prompt fingerprint, config/version, correlation ID e trace ID. Não podem carregar output bruto, prompt bruto, payload bruto ou dado sensível.

### Multi-tenancy e contexto confiável

- `tenant_id`, `tenant_isolation_tier`, ator e scopes continuam vindo exclusivamente do `PropagatedContext`.
- `ObservabilityContext` deve permanecer completo e compatível com contexto confiável para execução consultiva.
- Repositórios/adapters in-memory devem continuar chaveados por tenant quando armazenarem execução ou validação.
- Não ler tenant, roles, scopes ou identificação sensível de payload/output de IA.

### Arquitetura e estrutura esperada

- Trabalhar dentro de `services/automated-review/src/creditos_automated_review`.
- Preferir:
  - `domain/value_objects/review_output.py` ou extensão criteriosa de `review_execution.py` para contrato/validações puras de saída.
  - `domain/entities/automated_review_execution.py` apenas se o resultado persistido precisar carregar metadados adicionais de validação sem conteúdo bruto.
  - `application/service.py` para orquestrar validação no caso de uso existente, mantendo alterações pequenas e coesas.
  - `application/ports/consultative_review_executor.py` se a saída do executor precisar de campos governados adicionais.
  - `tests/unit/test_consultative_review_execution.py` ou novo teste unitário adjacente para regressões de output/guardrails.
- Domínio não deve importar FastAPI, Pydantic de borda, SQLAlchemy, gRPC, NATS, OpenTelemetry, SDK de IA ou adapters externos.
- Não mover código de `Decision`, `Integration`, `Audit & Evidence` ou pacotes compartilhados para cumprir esta story.

### Arquivos existentes a preservar

- `services/automated-review/src/creditos_automated_review/application/service.py`
  - Já valida scopes, tenant bridge, contexto observável completo, resolução de configuração publicada, reserva de `execution_id`, execução do mock e fallback auditável.
  - Preservar idempotência: `execution_repository.reserve(...)` deve ocorrer antes do executor e não pode voltar a ser `get()` não atômico.
  - Preservar fallback para exceção (`limitation_executor_failure`) e output inválido (`limitation_invalid_executor_output`).

- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
  - Já valida `execution_id` e `proposal_id` como referências técnicas não sensíveis.
  - Já força `classification="consultative"` e rejeita `final_decision`, `approved_terms` e `external_actions`.
  - Persiste `input_fields` sem `safe_value`; não reintroduzir valores de entrada.

- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py`
  - Já bloqueia payload bruto, refs sensíveis e valores governados inválidos.
  - `input_for_execution` segue allowlist estrita: apenas campos `included` alimentam o executor.
  - Reusar validadores existentes quando possível, sem duplicar lógica de PII/segredo.

- `services/automated-review/tests/unit/test_consultative_review_execution.py`
  - Já cobre minimização, idempotência, fallback, contexto confiável, refs sensíveis e ausência de PII realista.
  - Novos testes devem manter fixtures sintéticas e não usar CPF/CNPJ/e-mail realistas.

### Anti-patterns a evitar

- Não usar `dict[str, Any]`, `metadata`, `payload`, `raw_output`, `model_response` ou equivalente como contrato principal persistido.
- Não persistir output bruto “para debug”. Se houver necessidade futura, deve ser ADR/backlog com criptografia, retenção, base legal e auditoria.
- Não ampliar `ReviewAgentCapabilities` para aprovar/reprovar/chamar ferramenta; isso deve continuar bloqueado.
- Não usar confidence como decisão, cutoff ou aprovação automática.
- Não tratar fallback como sucesso de negócio; fallback é resultado técnico consultivo limitado.
- Não criar dependência circular entre `Automated Review` e `Decision`.

### Testes esperados

- Começar por testes RED em `services/automated-review/tests/unit`.
- Cobrir pelo menos:
  - saída válida com itens `missing_data`, `inconsistency`, `explainability_factor` e `limitation` quando aplicável;
  - rejeição/fallback de campo desconhecido, tipo inválido, confiança fora de faixa, referência inválida e texto sensível;
  - bloqueio de autonomia decisória (`approved`, `rejected`, `change_terms`, `callback`, `tool_use`, `external_action`);
  - prompt injection/jailbreak sintético, sem conteúdo realista;
  - logs/auditoria/repositório sem output bruto ou dado sensível;
  - preservação dos testes existentes da Story 5.2.
- Comandos recomendados:
  - `.venv/bin/pytest services/automated-review/tests/unit`
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`

### Previous Story Intelligence

- Story 5.2 implementou execução consultiva minimizada e recebeu correções de review importantes:
  - allowlist estrita: refs/tokenizações fora da allowlist são metadados, não input do executor;
  - `execution_id` e `proposal_id` rejeitam referências sensíveis;
  - reserva atômica de `execution_id` ocorre antes do executor;
  - output inválido do executor já vira fallback auditável;
  - persistência de execução não guarda `safe_value` dos campos de entrada;
  - fixtures de teste não devem usar PII realista.
- Qualquer alteração na saída deve manter essas correções. Elas são requisitos de regressão, não detalhes opcionais.
- O PR #47 foi mergeado antes desta story; baseline local é `d45e9e8`.

### Git Intelligence

- Commits recentes relevantes:
  - `c865d9b` — corrigiu achados de review da execução: `execution_id` sensível, reserva atômica e fallback para output inválido.
  - `470b1ae` — refinou validação de `execution_id` no `__post_init__`.
  - `0284d28` — refatorou tratamento de resultado/fallback no service.
  - `8fb05c5` — implementou execução consultiva minimizada.
- Commits deste projeto devem usar `Andre Tachian <altachian@gmail.com>`.
- Fluxo acordado: branch no início da story, Jira acompanha subtarefas, `bmad-dev-story`, `bmad-code-review`, depois `commit/push/draft PR`.

### Latest Technical Information

- Nenhuma pesquisa web é necessária nesta story: não há seleção de tecnologia nova, SDK de IA, provedor/modelo real, API externa ou protocolo novo.
- Se surgir necessidade de selecionar framework de schema adicional, fornecedor/modelo, secret manager ou protocolo, pausar e apresentar alternativas, justificativa e consequências antes de implementar.

### Project Structure Notes

- `services/automated-review` já existe e deve ser estendido; não recriar serviço nem renomear pacote.
- O pacote permanece `creditos_automated_review`; evitar nomes acoplados a fornecedor como `openai`, `anthropic`, `bedrock` ou `llm_provider` em domínio.
- O Jira da história é `CTOS-49`; subtarefas devem ser criadas/sincronizadas antes da implementação.
- Não foi encontrado `project-context.md` no workspace durante a ativação do workflow; usar PRD, Architecture, Epics, stories anteriores e README como fontes de verdade disponíveis.

### References

- `_bmad-output/planning-artifacts/epics.md` — Epic 5 e Story 5.3, linhas 850-866.
- `_bmad-output/planning-artifacts/epics.md` — NFRs e requisitos adicionais de arquitetura, linhas 90-118.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — NFR-9, NFR-28, NFR-30, NFR-32, riscos R-4/R-8 e governança de IA.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md` — `Automated Review Service` no MVP, IA consultiva e dados/modelos próprios fora do fluxo do MVP.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-4, AD-5, AD-7, AD-10, AD-11 e baseline Python/DDD.
- `_bmad-output/implementation-artifacts/5-1-configuracao-versionada-de-agente-de-revisao.md` — configuração versionada, guardrails e capacidades consultivas.
- `_bmad-output/implementation-artifacts/5-2-execucao-consultiva-com-entradas-minimizadas.md` — execução consultiva minimizada e review findings aplicados.
- `services/automated-review/README.md` — responsabilidades, limites e fora de escopo atual.
- `services/automated-review/src/creditos_automated_review/application/service.py` — execução consultiva, logs, auditoria e fallback atual.
- `services/automated-review/src/creditos_automated_review/application/ports/consultative_review_executor.py` — contrato atual do executor consultivo.
- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py` — resultado consultivo persistido e bloqueios de autonomia.
- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py` — minimização, validação de entrada e refs seguras.
- `services/automated-review/tests/unit/test_consultative_review_execution.py` — regressões existentes de execução consultiva.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- `.venv/bin/pytest services/automated-review/tests/unit/test_review_output_validation.py` — RED inicial falhou por tipos ainda não exportados; GREEN final passou.
- `.venv/bin/pytest services/automated-review/tests/unit/test_consultative_review_execution.py -k 'governed_output or autonomous_output or unknown_output or executes_consultative'` — RED/GREEN de integração de saída consultiva.
- `.venv/bin/pytest services/automated-review/tests/unit` — 32 testes passaram após patches de code review.
- `.venv/bin/ruff format --check .` — 257 arquivos formatados corretamente.
- `.venv/bin/ruff check .` — sem violações.
- `.venv/bin/pyright` — 0 erros.
- `.venv/bin/pytest` — 570 passaram com permissão elevada; 1 falhou por `uv: command not found` em `scripts/dev harness-check`, limitação ambiental local não introduzida pela story.

### Completion Notes List

- Implementado contrato fechado `ReviewOutputItem`/`ReviewOutputValidationResult` para classificar saídas consultivas e rejeitar campos livres, payloads arbitrários, refs sensíveis e texto não governado.
- Integrado `ConsultativeReviewOutput.output_items` ao fluxo de execução; saídas inválidas agora viram fallback auditável com `limitation_invalid_executor_output`.
- Adicionadas contagens seguras de saída aceita/bloqueada em logs/auditoria, sempre com `raw_output_persisted=false` e sem persistir output bruto.
- Atualizado mock executor para emitir itens governados e preservadas as regressões de minimização/idempotência da Story 5.2.
- Limitação registrada: a suíte completa local ainda depende do binário `uv` disponível no PATH para `scripts/dev harness-check`; validações da story e gates de qualidade passaram.
- Code review patches aplicados: `evidence_refs` agora aceita array/list JSON e `safe_summary` bloqueia frases comuns de tool call, function call, webhook e chamada a provedor externo.

### Change Log

- 2026-09-10 — Story 5.3 detalhada com contexto do Epic 5, branch inicial, guardrails de saída, preservação dos achados da Story 5.2 e Jira `CTOS-49` em andamento.
- 2026-09-10 — Implementada validação de saída consultiva, guardrails, fallback auditável, logs/auditoria minimizados, testes e documentação da Story 5.3.
- 2026-09-10 — Patches do code review aplicados para arrays JSON em `evidence_refs` e cobertura ampliada de tool/action guardrails em `safe_summary`.

### File List

- `_bmad-output/implementation-artifacts/5-3-validacao-de-saida-guardrails-e-classificacao.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/automated-review/README.md`
- `services/automated-review/src/creditos_automated_review/adapters/model/mock_consultative_review_executor.py`
- `services/automated-review/src/creditos_automated_review/application/ports/consultative_review_executor.py`
- `services/automated-review/src/creditos_automated_review/application/service.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_output.py`
- `services/automated-review/tests/unit/test_consultative_review_execution.py`
- `services/automated-review/tests/unit/test_review_output_validation.py`
