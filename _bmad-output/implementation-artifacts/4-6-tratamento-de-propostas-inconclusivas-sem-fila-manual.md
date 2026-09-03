---
jira_issue: CTOS-44
branch: agent/story-4-6-tratamento-de-propostas-inconclusivas-sem-fila-manual
baseline_commit: fd537d1
created_at: 2026-08-31
---

# Story 4.6: Tratamento de Propostas Inconclusivas sem Fila Manual

Status: done

## Story

As a cliente técnico,
I want receber estado controlado quando a proposta não puder ser decidida,
so that meu fluxo saiba solicitar dados adicionais, aplicar contingência governada ou tratar o caso sem fila manual no CreditOS.

## Acceptance Criteria

1. **Fallback governado por política publicada**
   - **Given** uma política publicada, aplicável ao tenant/produto/canal e com configuração governada de `fallback_action`
   - **When** faltam dados críticos, há resultado parcial de integração, contingência técnica, ausência de regra acionável ou conflito de regras
   - **Then** o `Decision Service` retorna um outcome governado e determinístico entre `request_more_data`, `unable_to_decide`, `reject` por regra explícita ou `approve_with_changes` quando houver termos ajustados explícitos
   - **And** registra lacuna, razão, fallback aplicado, política/catálogo/versionamento, proposal ID, tenant, produto, canal, correlation ID e fingerprint decisório sem payload sensível.

2. **Compatibilidade semântica de solicitação de dados**
   - **Given** que o épico usa a expressão `request_additional_data`
   - **When** a implementação representar o resultado no contrato interno atual
   - **Then** deve usar o outcome governado existente `request_more_data`
   - **And** não deve criar um segundo outcome equivalente sem ADR ou migração explícita de contrato.

3. **Solicitação de dados adicionais sem decisão final**
   - **Given** que a política determine `fallback_action=request_more_data`
   - **When** campos necessários estiverem ausentes ou indisponíveis
   - **Then** a decisão fica controlada como `request_more_data`
   - **And** expõe somente referências seguras de campos/lacunas, reason codes/fatores aplicáveis e contexto técnico mínimo, sem CPF, CNPJ, nome, e-mail, endereço, payload bruto ou resposta de fornecedor.

4. **Inconclusão e contingência técnica controladas**
   - **Given** que a política determine `fallback_action=unable_to_decide` ou exista contingência sem fallback seguro
   - **When** o motor não puder decidir de forma reproduzível
   - **Then** a decisão fica controlada como `unable_to_decide`
   - **And** preserva rastreabilidade da lacuna/contingência, sem degradar falhas críticas de auditoria para uma decisão visível ao cliente.

5. **Reprovação explícita por política**
   - **Given** que a política determine reprovação por regra explícita como fallback
   - **When** a condição governada for satisfeita
   - **Then** o outcome deve ser `reject`, com regra acionada, reason code publicado e fingerprint reproduzível
   - **And** a reprovação não pode ser inferida implicitamente apenas por timeout, ausência de dado ou erro técnico sem regra governada.

6. **Aprovação com alterações somente com termos ajustados**
   - **Given** uma política que permita `approve_with_changes`
   - **When** a aprovação com alterações for produzida
   - **Then** `approved_terms` deve ser derivado explicitamente de limites/regras governadas e deve diferir dos `requested_terms`
   - **And** o sistema deve rejeitar `approve_with_changes` sem modelo explícito de termos ajustados, sem `plan_id` e sem plano comercial externo da financeira.

7. **Rejeição de revisão manual e override humano no MVP**
   - **Given** tentativa de configurar `manual_review`, fila manual, `human_override` ou comportamento equivalente
   - **When** a política ou opção de decisão for validada
   - **Then** o sistema rejeita a configuração com erro seguro e rastreável
   - **And** orienta uso de fallback automatizado ou IA consultiva, lembrando que IA não aprova nem reprova sozinha.

8. **Auditoria, logs e observabilidade de negócio**
   - **Given** uma decisão inconclusiva, solicitação de dados, aprovação com alterações ou reprovação por fallback
   - **When** o fluxo for executado
   - **Then** auditoria/logs devem registrar outcome, `fallback_action`, códigos de lacuna/razão, contagens seguras, tenant, produto, canal, policy/catalog refs, correlation ID e duração
   - **And** os dados devem permitir métricas futuras de funil por tenant/produto/canal/política/outcome sem expor dado sensível.

9. **Isolamento e autorização permanecem obrigatórios**
   - **Given** execução sem `PropagatedContext` confiável, sem scope `decision:execute`, com tenant incompatível ou com `tenant_isolation_tier` diferente de `bridge`
   - **When** a decisão for solicitada
   - **Then** o sistema falha antes de avaliar política ou persistir decisão
   - **And** respostas cross-tenant continuam indistinguíveis de recurso inexistente.

## Tasks / Subtasks

- [x] CTOS-260 — Modelar fallback governado da política (AC: 1, 2, 5, 7)
  - [x] Criar value object/enum para `fallback_action` com valores permitidos `request_more_data`, `unable_to_decide` e `reject_by_policy`.
  - [x] Adicionar fallback ao fingerprint governado da política para manter imutabilidade e publicação reproduzível.
  - [x] Rejeitar explicitamente `manual_review`, fila manual, `human_override` e aliases equivalentes.

- [x] CTOS-261 — Resolver lacunas e inconclusões no avaliador determinístico (AC: 1, 3, 4, 5)
  - [x] Mapear ausência de campos, violação de critérios/limites, ausência de regra, conflito de regras e contingência para fallback configurado.
  - [x] Preservar `PolicyEvaluationIssue` com códigos e caminhos seguros, sem valores sensíveis.
  - [x] Garantir que erro técnico, timeout ou dado ausente não vire `reject` sem regra explícita.

- [x] CTOS-262 — Implementar solicitação de dados adicionais (AC: 2, 3, 8)
  - [x] Usar `PolicyOutcome.REQUEST_MORE_DATA` como representação interna de solicitação de dados.
  - [x] Produzir referências seguras para campos ausentes ou indisponíveis.
  - [x] Preparar detalhes minimizados para auditoria e métricas futuras.

- [x] CTOS-263 — Implementar aprovação com alterações governada (AC: 6)
  - [x] Criar modelo explícito para termos ajustados derivados de limites/regras da política.
  - [x] Validar que `approved_terms` é completo, seguro e diferente dos termos solicitados.
  - [x] Manter bloqueio de `approve_with_changes` quando não houver termos ajustados explícitos.

- [x] CTOS-264 — Fortalecer auditoria, logs e observabilidade segura (AC: 1, 8, 9)
  - [x] Publicar intenção de auditoria minimizada para decisões de fallback sem payload bruto.
  - [x] Incluir outcome/fallback/lacunas em logs estruturados usando IDs técnicos e correlation ID.
  - [x] Manter campos suficientes para Reporting futuro distinguir approved/rejected/approve_with_changes/request_more_data/unable_to_decide.

- [x] CTOS-265 — Criar testes RED e regressões de domínio/aplicação (AC: 1-9)
  - [x] Testar fallback `request_more_data`, `unable_to_decide` e `reject_by_policy`.
  - [x] Testar rejeição de revisão manual/override humano.
  - [x] Testar `approve_with_changes` com termos ajustados explícitos e bloqueio sem ajuste.
  - [x] Testar que logs/auditoria não incluem CPF, CNPJ, nome, e-mail, endereço, payload bruto, token ou segredo.
  - [x] Testar isolamento por tenant, scope obrigatório e falha antes da avaliação quando contexto é inválido.

- [x] CTOS-266 — Atualizar documentação e rastreabilidade (AC: 1-9)
  - [x] Atualizar `services/decision/README.md` com comportamento da Story 4.6 e limites de escopo.
  - [x] Registrar no artefato da story qualquer decisão tomada durante implementação ou review.
  - [x] Manter `sprint-status.yaml` e Jira sincronizados conforme avanço.

### Review Findings

- [x] [Review][Patch] `reject_by_policy` pode rejeitar sem regra explícita acionada — `services/decision/src/creditos_decision/domain/services/policy_evaluator.py:56`
- [x] [Review][Patch] `approve_with_changes` pode ser avaliado com termos solicitados incompletos — `services/decision/src/creditos_decision/domain/services/policy_evaluator.py:115`
- [x] [Review][Patch] Ajuste de termos pode aumentar valores solicitados ou depender da ordem de limites contraditórios — `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py:165`
- [x] [Review][Patch] Critério `EXISTS=true` ausente vira falha de critério em vez de lacuna solicitável — `services/decision/src/creditos_decision/domain/services/policy_evaluator.py:241`
- [x] [Review][Patch] Simulação perde `fallback_action` e `required_data_refs`, quebrando paridade de rastreabilidade com decisão — `services/decision/src/creditos_decision/domain/entities/policy_simulation.py:177`
- [x] [Review][Patch] Auditoria/log aceito não registram códigos seguros de lacuna/razão, canal e contexto suficiente exigido pelos ACs — `services/decision/src/creditos_decision/application/service.py:818`
- [x] [Review][Patch] `reason_code_refs` são aceitos em fallbacks que não usam reason codes — `services/decision/src/creditos_decision/domain/value_objects/policy.py:454`
- [x] [Review][Patch] `fallback_action` restaurado em avaliação/decisão aceita identificador técnico arbitrário em vez do enum governado — `services/decision/src/creditos_decision/domain/value_objects/policy_evaluation.py:106`
- [x] [Review][Patch] Erro de fallback manual não orienta alternativa automatizada/IA consultiva conforme AC7 — `services/decision/src/creditos_decision/domain/value_objects/policy.py:596`
- [x] [Review][Defer] Fingerprint governado ainda usa serialização baseada em `repr`, criando risco futuro de reprodutibilidade entre refactors — `services/decision/src/creditos_decision/domain/entities/credit_policy.py:547` — deferred, pre-existing

## Dev Notes

### Escopo

- Implementar o tratamento de propostas inconclusivas no `Decision Service`, em domínio/aplicação/adapters in-memory, seguindo DDD e arquitetura hexagonal.
- Não implementar API pública, gRPC real, NATS JetStream, banco real, outbox, callbacks, dashboards, Reporting Service, Automated Review Service ou integrações externas reais nesta story.
- IA consultiva pode ser mencionada como rota futura/adjacente, mas não deve ser usada como decisor final nesta story.
- Nenhuma tecnologia nova deve ser adicionada. Usar Python 3.13, dataclasses, `Protocol`, pytest, Ruff, Pyright e os padrões já adotados.

### Decisões e ajustes em relação ao épico

- O épico usa `request_additional_data`, mas o PRD detalhado e o código já governam o outcome como `request_more_data`. Esta story mantém `request_more_data` para evitar duplicidade semântica.
- `approve_with_changes` estava bloqueado na Story 4.5 até existir modelo explícito de termos ajustados. Esta story pode desbloquear esse outcome somente se implementar esse modelo com derivação determinística e testes.
- `reject_by_policy` é uma ação de fallback/configuração, não um novo outcome público; o outcome persistido deve continuar sendo `reject` quando houver regra explícita.
- Revisão manual, fila manual e override humano permanecem fora do MVP.

### Regras de domínio

- Toda decisão final ou controlada exige política publicada, catálogo publicado e compatível, `policy_version_id`, `reason_code_catalog_version_id`, proposal ID, tenant, produto, canal, timestamp UTC, correlation ID e fingerprint estável.
- `fallback_action` deve fazer parte da parte governada da política; política publicada não pode mudar fallback sem nova versão/revisão.
- Dados ausentes, integração parcial, timeout ou contingência técnica devem gerar `request_more_data` ou `unable_to_decide`, exceto quando existir regra explícita de reprovação governada.
- `approve_with_changes` deve produzir `approved_terms` completo e diferente dos termos solicitados, sem `plan_id` e sem dependência de planos da financeira.
- Falha crítica de auditoria continua bloqueando visibilidade da decisão conforme a Story 4.5; esta story não deve transformar falha de auditoria em sucesso inconclusivo.

### Segurança, privacidade e multi-tenancy

- `tenant_id` vem sempre do `PropagatedContext`; nunca do payload do comando.
- `tenant_isolation_tier` esperado no MVP é `bridge`.
- Escopo mínimo esperado para execução permanece `decision:execute`.
- Logs, auditoria, errors e detalhes de fallback não podem conter CPF, CNPJ, nome, e-mail, endereço, payload bruto, resposta bruta de fornecedor, token, segredo, headers sensíveis ou body de requisição.
- Erros cross-tenant devem continuar indistinguíveis de recurso inexistente.

### Observabilidade

- Esta story deve preparar campos seguros para métricas de negócio futuras: volume por tenant/produto/canal, outcome, `fallback_action`, tipo de lacuna, política, versão e duração.
- Dashboards não entram no escopo, mas os eventos/logs devem permitir funil futuro: recebida, validada, enriquecida, decidida, aprovada, recusada, inconclusiva, aprovada com alterações e solicitação de dados.

### Arquivos prováveis

- `services/decision/src/creditos_decision/domain/value_objects/policy.py`: outcome, fallback action, validação de política e fingerprint governado.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`: inclusão de fallback na política governada e imutabilidade.
- `services/decision/src/creditos_decision/domain/services/policy_evaluator.py`: aplicação determinística de fallback em lacunas/conflitos/ausência de regra.
- `services/decision/src/creditos_decision/domain/value_objects/policy_evaluation.py`: contexto seguro adicional, se necessário, para lacunas/fallback.
- `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py`: modelo de termos ajustados, se `approve_with_changes` for habilitado.
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`: validação da decisão, fingerprint e bloqueios de outcomes.
- `services/decision/src/creditos_decision/application/service.py`: orquestração, auditoria/logs seguros e autorização.
- `services/decision/tests/unit/test_credit_decision_model.py`: regressões de domínio.
- `services/decision/tests/unit/test_credit_decision_service.py`: regressões de aplicação/autorização/auditoria/logs.
- `services/decision/tests/unit/test_policy_simulation_model.py`: compatibilidade com simulação se fallback entrar no modelo de política.
- `services/decision/README.md`: documentação de comportamento e fronteiras da Story 4.6.

### Testes esperados

- Executar testes específicos do Decision Service afetados pela mudança.
- Executar `uv run ruff format --check .`, `uv run ruff check .` e `uv run pyright` antes de commit/push da implementação.
- Preferir testes RED primeiro para fallback, termos ajustados e rejeição de revisão manual.

### Project Structure Notes

- A story permanece dentro do microserviço `services/decision`, respeitando DDD: entidades/value objects/serviços de domínio sem dependências de infraestrutura, aplicação orquestrando casos de uso e adapters in-memory para testes.
- Não há necessidade de criar novo microsserviço, endpoint ou contrato público nesta story.
- O Jira deve refletir o avanço: `CTOS-44` em `Em andamento`, subtarefas movidas conforme execução e story concluída após merge do PR.

### References

- `_bmad-output/planning-artifacts/epics.md` — Epic 4 / Story 4.6.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-14, FR-15 e requisitos de métricas.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/contrato-inicial-proposta-oq3.md` — `decision_options`, `fallback_action` e resposta esperada.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md` — ausência de `selected_plan`/`plan_id`, sem revisão manual e IA consultiva.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — DDD, microserviços, gRPC, NATS, bridge tenancy, auditoria e observabilidade.
- `_bmad-output/implementation-artifacts/4-5-execucao-deterministica-de-decisao.md` — decisão determinística, bloqueios atuais e fronteiras para Story 4.6.
- `services/decision/src/creditos_decision/domain/value_objects/policy.py` — `PolicyOutcome` existente e validações seguras.
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py` — criação/fingerprint de decisão e bloqueio atual de `approve_with_changes`.
- `services/decision/src/creditos_decision/domain/services/policy_evaluator.py` — avaliação atual de regras, lacunas e `unable_to_decide`.

## Dev Agent Record

### Agent Model Used

TBD

### Debug Log References

- `.venv/bin/pytest services/decision/tests/unit/test_credit_policy_model.py`
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_policy_model.py`
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_service.py`
- `.venv/bin/pytest services/decision/tests/unit/test_credit_policy_service.py services/decision/tests/unit/test_policy_simulation_model.py services/decision/tests/unit/test_policy_simulation_service.py services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py`
- `.venv/bin/pytest services/decision/tests/unit tests/test_sensitive_data_masking.py tests/test_observability_foundation.py`
- `.venv/bin/ruff format .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/pyright`
- `.venv/bin/pytest` — executado também fora do sandbox; resultado: 509 passed, 1 failed por `uv: command not found` em `tests/test_local_harness.py::test_dev_script_harness_check_uses_documented_command`.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_policy_model.py services/decision/tests/unit/test_credit_policy_service.py services/decision/tests/unit/test_policy_simulation_model.py services/decision/tests/unit/test_policy_simulation_service.py` — 73 passed após patches de review.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/pyright` — passou após patches de review.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_credit_policy_model.py services/decision/tests/unit/test_credit_policy_service.py services/decision/tests/unit/test_policy_simulation_model.py services/decision/tests/unit/test_policy_simulation_service.py` — 77 passed após correções do review GitHub do PR #43.
- `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/pyright` — passou após correções do review GitHub do PR #43.

### Completion Notes List

- Implementado `PolicyFallbackAction` governado com valores `request_more_data`, `unable_to_decide` e `reject_by_policy`, incluindo rejeição de aliases manuais e inclusão no fingerprint da política.
- Ajustado o avaliador determinístico para aplicar fallback em lacunas, ausência de regra, conflito de regras e violações governadas sem aprovar implicitamente.
- Mantido `request_more_data` como representação interna para solicitação de dados adicionais, registrando `fallback_action` e `required_data_refs` seguros na avaliação/decisão.
- Habilitado `approve_with_changes` somente com `approved_terms` ajustados por limites de política e diferentes dos termos solicitados.
- Fortalecidos auditoria/logs com fallback, contagem/referências seguras de dados requeridos, policy/catalog refs e fingerprint sem payload bruto.
- Corrigidos achados de code review: `reject_by_policy` agora exige regra de reprovação acionada e reason code compatível, `approve_with_changes` exige termos completos, ajustes nunca aumentam termos solicitados, `EXISTS=true` ausente vira lacuna, simulação preserva fallback/lacunas e restauração valida enum governado.
- Corrigidos achados do review GitHub do PR #43: `fallback_action` vazio removido de logs, reason codes de fallback reportam `field_path` correto, mensagem de IA consultiva foi clarificada, `approve_with_changes` rebaixa quando não há ajuste seguro, regras de rejeição explícitas são avaliadas antes de fallback, lacunas de dados são agregadas, duração do log inclui persistência e métricas contam apenas fallback efetivamente aplicado.
- Atualizado `services/decision/README.md` com comportamento, decisões e limites da Story 4.6.
- Validações de Story 4.6 passaram no escopo afetado; suíte completa tem falha ambiental local por ausência de `uv` global no `scripts/dev`.

### File List

- `_bmad-output/implementation-artifacts/4-6-tratamento-de-propostas-inconclusivas-sem-fila-manual.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`
- `services/decision/src/creditos_decision/domain/entities/policy_simulation.py`
- `services/decision/src/creditos_decision/domain/services/policy_evaluator.py`
- `services/decision/src/creditos_decision/domain/value_objects/__init__.py`
- `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy_evaluation.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy_simulation.py`
- `services/decision/tests/unit/test_credit_decision_model.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `services/decision/tests/unit/test_credit_policy_model.py`
- `services/decision/tests/unit/test_credit_policy_service.py`
- `services/decision/tests/unit/test_policy_simulation_model.py`
- `services/decision/tests/unit/test_policy_simulation_service.py`

## Change Log

- 2026-09-02 — Implementada Story 4.6 com fallback governado, tratamento de lacunas/inconclusão, `approve_with_changes` ajustado, auditoria/logs seguros, testes e documentação.
- 2026-09-03 — Aplicados patches do `bmad-code-review` para corrigir rejeição por fallback sem regra explícita, paridade de simulação, auditoria/logs seguros e validação estrita de fallback.
- 2026-09-03 — Corrigidos achados Codex/Copilot do PR #43 com regressões de execução determinística, fallback seguro, logs e simulação.
