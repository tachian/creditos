---
jira_issue: CTOS-46
branch: agent/story-4-8-gates-de-decisao-politica-e-explicabilidade
baseline_commit: d4b0946
created_at: 2026-09-04
---

# Story 4.8: Gates de Decisão, Política e Explicabilidade

Status: done

## Story

As a equipe de engenharia,
I want testes de domínio, contrato e regressão para políticas e decisões,
so that alterações não quebrem determinismo, explicabilidade, privacidade, multi-tenancy ou auditoria.

## Acceptance Criteria

1. **Cobertura transversal do ciclo de política e decisão**
   - **Given** a suíte de testes do `Decision Service`
   - **When** ela for executada
   - **Then** cobre criação de política, catálogo de reason codes, simulação, publicação, execução, inconclusão e explicabilidade
   - **And** valida que decisão final sempre aponta `policy_id`, `policy_version_id`, `policy_revision`, `reason_code_catalog_id`, `reason_code_catalog_version_id` e reason codes governados quando aplicável.

2. **Determinismo e reprodutibilidade mínima**
   - **Given** a mesma política publicada, catálogo publicado e entrada canônica minimizada
   - **When** a decisão for executada em testes controlados
   - **Then** o resultado de negócio, reason codes, fatores, lacunas, termos aprovados e fingerprint decisório permanecem estáveis
   - **And** nenhum timestamp, payload bruto ou dado sensível entra no cálculo de fingerprint.

3. **Governança contra decisor externo final**
   - **Given** uma tentativa de usar IA, integração externa, provider payload ou resultado proprietário como decisor final direto
   - **When** os testes de governança forem executados
   - **Then** a tentativa falha em domínio, aplicação ou contrato de teste
   - **And** preserva `CreditDecision`/`Decision Service` como fonte única transacional da decisão final no MVP.

4. **Explicabilidade obrigatória**
   - **Given** uma decisão final ou estado controlado
   - **When** a resposta explicável for criada, retornada ou consultada
   - **Then** decisões finais exigem reason code ativo, coerente com outcome e visível para audiência autorizada
   - **And** estados controlados exigem justificativa equivalente segura por `required_data_refs`, `validation_issues`, `fallback_action` ou reason code aplicável.

5. **Privacidade, mascaramento e ausência de payload bruto**
   - **Given** dados sensíveis em entradas sintéticas, textos, comandos, issues, mocks ou resultados de integração
   - **When** respostas, logs, auditoria ou fixtures de gate forem gerados
   - **Then** CPF, CNPJ, nome, e-mail, telefone, endereço, token, segredo, payload bruto, headers sensíveis e renda detalhada não aparecem
   - **And** testes usam apenas dados sintéticos e identificadores técnicos seguros.

6. **Tenant isolation e autorização**
   - **Given** contexto propagado confiável
   - **When** operações de criação, simulação, publicação, execução ou leitura explicável forem testadas
   - **Then** exigem scopes corretos, `tenant_isolation_tier=bridge` e tenant vindo do contexto confiável
   - **And** tentativa cross-tenant continua indistinguível de recurso inexistente.

7. **Auditoria e logs seguros**
   - **Given** operações aceitas ou rejeitadas no ciclo de decisão
   - **When** gates de regressão forem executados
   - **Then** verificam emissão de intents de auditoria antes de commit/persistência crítica quando aplicável
   - **And** logs estruturados registram metadados seguros, contagens e correlação sem payload bruto.

8. **Sem ampliação indevida de escopo**
   - **Given** que esta story encerra gates do Epic 4
   - **When** a implementação for feita
   - **Then** não cria endpoint público, contrato OpenAPI externo, gRPC real, NATS, banco real, IA real, serviço novo ou dependência nova
   - **And** qualquer lacuna estrutural encontrada deve virar item em `deferred-work.md` ou story futura, não overbuild local.

## Tasks / Subtasks

- [x] CTOS-274 — Criar regressões de domínio para política e catálogo (AC: 1, 4, 6)
  - [x] Consolidar gates de `CreditPolicy` para draft, publicação, imutabilidade, versionamento e proveniência de catálogo.
  - [x] Consolidar gates de `ReasonCodeCatalog` para status publicado, versionamento, audiência e compatibilidade de reason codes/fatores.
  - [x] Evitar helper duplicado se os testes atuais já cobrirem o cenário; preferir parametrização ou asserts adicionais.

- [x] CTOS-275 — Cobrir gates de simulação e publicação (AC: 1, 7)
  - [x] Garantir que `PolicySimulation` permanece não produtiva e não publica decisão final.
  - [x] Garantir que publicação exige simulação compatível, catálogo publicado, vigência válida e auditoria crítica antes da exposição da versão.
  - [x] Preservar atomicidade dos adapters in-memory já reforçada nas Stories 4.3 e 4.4.

- [x] CTOS-276 — Cobrir execução determinística de decisão (AC: 1, 2, 3, 7)
  - [x] Adicionar regressão explícita para mesma entrada governada produzir resultado/fingerprint estável.
  - [x] Validar que `CreditDecision` final sempre contém refs de política, catálogo, reason codes quando aplicável, `correlation_id` e `decision_fingerprint`.
  - [x] Provar que payload proprietário, provider result e valores brutos não são usados como decisão final direta.

- [x] CTOS-277 — Cobrir inconclusão e explicabilidade segura (AC: 4, 5, 6, 7)
  - [x] Testar `request_more_data`, `unable_to_decide`, `reject_by_policy` e `approve_with_changes` com justificativas seguras.
  - [x] Testar filtros de audiência da explicabilidade para cliente e interno autorizado.
  - [x] Testar ausência de dados sensíveis em resposta, logs, auditoria e mensagens de erro controladas.

- [x] CTOS-278 — Criar gates de governança contra decisor externo (AC: 3, 8)
  - [x] Criar testes que falham caso IA consultiva seja usada como outcome final sem passar pela política determinística.
  - [x] Criar testes que falham caso resultado de integração externa seja convertido diretamente em decisão final.
  - [x] Documentar que IA e integrações continuam evidências/entradas, não autoridade final de decisão.

- [x] CTOS-279 — Atualizar documentação e rastreabilidade BMAD (AC: 1-8)
  - [x] Atualizar `services/decision/README.md` com os gates protegidos pela Story 4.8.
  - [x] Registrar validações executadas no Dev Agent Record.
  - [x] Manter Jira e `sprint-status.yaml` sincronizados conforme avanço e revisão.

### Review Findings

- [x] [Review][Patch] Mensagem de erro não acompanha o código customer-safe [`services/decision/src/creditos_decision/domain/entities/credit_decision.py`:511]
- [x] [Review][Patch] Gate de privacidade faz assert sobre dados sensíveis que não entram no cenário [`services/decision/tests/unit/test_epic4_decision_governance_gates.py`:202]
- [x] [Review][Patch] Metadados BMAD da story ficaram desatualizados após execução [`_bmad-output/implementation-artifacts/4-8-gates-de-decisao-politica-e-explicabilidade.md`:238]

## Dev Notes

### Escopo

- Esta story deve fortalecer a malha de testes/gates do `Decision Service`; ela não deve alterar comportamento produtivo sem necessidade comprovada por regressão.
- O foco é impedir regressões nas histórias 4.1 a 4.7: política versionada, catálogo explicável, simulação, publicação imutável, execução determinística, inconclusão controlada e resposta explicável.
- A implementação deve começar pelos testes: identificar cobertura existente, adicionar RED tests onde houver lacuna e só então ajustar código se um gate revelar bug real.
- Nenhuma tecnologia nova deve ser adicionada. Usar Python 3.13, pytest, dataclasses, `Protocol`, Ruff e Pyright já definidos no monorepo.
- Não implementar API pública, gRPC, NATS, banco real, outbox real, IA real, Integration Service real, Audit & Evidence real ou Reporting nesta story.

### Decisões e ajustes em relação ao épico

- O épico fala em “testes de domínio, contrato e regressão”. Como ainda não há contrato público do `Decision Service` no Epic 4, “contrato” aqui significa contratos internos de aplicação/domínio e invariantes verificáveis por teste; contratos públicos ficam para o Epic 8.
- A governança contra IA/integração como decisor final deve ser comprovada por testes negativos e documentação, sem criar um AI Service fake ou adapter externo novo.
- “Decisão final sempre aponta reason codes” deve ser interpretado com a nuance já aprovada na Story 4.7: outcomes finais exigem reason code governado; estados controlados podem usar justificativa equivalente segura.
- Caso algum teste revele lacuna ampla que exija arquitetura nova, registrar em `_bmad-output/implementation-artifacts/deferred-work.md` em vez de expandir escopo.

### Estado atual que deve ser preservado

- `DecisionApplicationService.execute_credit_decision` seleciona política publicada, busca catálogo publicado, avalia caso, cria `CreditDecision`, monta explicação, audita antes do commit e salva via `CreditDecisionRepository`.
- `CreditDecisionApplicationResult` contém `decision`, `explanation` e `logs`; consumidores atuais usam `result.decision` e não devem quebrar.
- `CreditDecision.to_explainable_response` deriva resposta segura a partir de decisão persistida e catálogo versionado, com audiência controlada.
- `CreditDecisionRepository` já possui `get` e `get_by_proposal`; consultas cross-tenant devem continuar indistinguíveis de not found.
- `PolicySimulation.run` deve permanecer não produtiva, com issues/lacunas/fallback rastreáveis e sem evento de decisão final.
- `CreditPolicy.publish` e `create_new_version` já reforçam imutabilidade, vigência, simulação compatível, janela de publicação e auditoria crítica.
- `ReasonCodeCatalog` é a fonte governada de reason codes, fatores, audiência e descrições; não criar catálogo paralelo.

### Arquivos prováveis

- `services/decision/tests/unit/test_credit_policy_model.py`: regressões de política versionada, campos governados, imutabilidade e fallback sem manual review.
- `services/decision/tests/unit/test_credit_policy_publication_model.py`: publicação imutável, vigência e nova versão preservando snapshot original.
- `services/decision/tests/unit/test_credit_policy_publication_service.py`: auditoria antes de exposição, simulação compatível e conflito de janela.
- `services/decision/tests/unit/test_policy_simulation_model.py`: simulação não produtiva, paridade com avaliador determinístico, lacunas e conflitos.
- `services/decision/tests/unit/test_policy_simulation_service.py`: autorização, tenant isolation, auditoria e logs da simulação.
- `services/decision/tests/unit/test_reason_code_catalog_model.py`: versionamento, compatibilidade, audiência e mudança incompatível.
- `services/decision/tests/unit/test_reason_code_catalog_service.py`: autorização, auditoria e logs do catálogo.
- `services/decision/tests/unit/test_credit_decision_model.py`: determinismo, fingerprint, explicabilidade, privacidade e estados controlados.
- `services/decision/tests/unit/test_credit_decision_service.py`: execução/leitura, scopes, tenant isolation, auditoria antes do commit e logs seguros.
- `services/decision/README.md`: documentação dos gates do Epic 4.
- `_bmad-output/implementation-artifacts/deferred-work.md`: lacunas estruturais fora do escopo, se descobertas.

### Arquivos de código a alterar somente se teste provar necessidade

- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`
- `services/decision/src/creditos_decision/domain/entities/policy_simulation.py`
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py`
- `services/decision/src/creditos_decision/domain/services/policy_evaluator.py`
- `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy_evaluation.py`
- `services/decision/src/creditos_decision/domain/value_objects/reason_codes.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_decision_repository.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_policy_repository.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_policy_simulation_repository.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_reason_code_catalog_repository.py`

### Anti-patterns a evitar

- Não criar novo motor de regras, DSL, snapshot serializer genérico, framework de fixtures ou biblioteca de property-based testing sem ADR/aprovação.
- Não transformar esta story em refatoração ampla dos testes existentes; adicionar gates cirúrgicos e legíveis.
- Não criar contrato público só para satisfazer a palavra “contrato”; se necessário, tratar invariantes internas como contrato testável.
- Não usar dados reais em fixtures. CPF, CNPJ, e-mail, telefone, nome, endereço, tokens e renda detalhada devem estar ausentes ou omitidos.
- Não permitir que IA consultiva ou resultado de integração defina `outcome` final sem passar pela política determinística.
- Não enfraquecer a regra de `tenant_id` vindo de `PropagatedContext` confiável.
- Não usar logs operacionais como trilha oficial de auditoria; continuar validando intents minimizadas.
- Não alterar `uv.lock` se nenhuma dependência nova for adicionada.

### Testes esperados

- Executar testes focados do `Decision Service` afetados pela story.
- Executar pelo menos:
  - `.venv/bin/pytest services/decision/tests/unit/test_credit_policy_model.py services/decision/tests/unit/test_credit_policy_publication_model.py services/decision/tests/unit/test_credit_policy_publication_service.py services/decision/tests/unit/test_policy_simulation_model.py services/decision/tests/unit/test_policy_simulation_service.py services/decision/tests/unit/test_reason_code_catalog_model.py services/decision/tests/unit/test_reason_code_catalog_service.py services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py`
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Se possível antes do PR, executar `.venv/bin/pytest`; se a falha ambiental local por `uv` continuar, registrar exatamente o resultado em `deferred-work.md`/Dev Agent Record sem mascarar.
- Gates de privacidade devem fazer asserts negativos explícitos para strings sensíveis sintéticas em resposta/log/auditoria.
- Gates de determinismo devem controlar relógio/IDs quando necessário para evitar falso negativo por timestamp ou UUID.

### Project Structure Notes

- A story permanece dentro de `services/decision`, respeitando DDD e arquitetura hexagonal: domínio puro, aplicação coordenando casos de uso e adapters in-memory apenas para testes.
- Testes unitários específicos ficam em `services/decision/tests/unit`; testes transversais só devem ser criados em `tests/contract` ou `tests/integration` se houver contrato real do monorepo a validar, o que não é esperado nesta story.
- Pacotes compartilhados (`packages/*`) não devem receber regra de negócio de decisão.
- O Jira deve refletir o avanço: `CTOS-46` está em `Em análise`; subtarefas `CTOS-274` a `CTOS-279` devem ser movidas conforme execução.

### Previous Story Intelligence

- Story 4.1 reforçou que política usa contexto confiável, `tenant_isolation_tier=bridge`, campos governados e auditoria antes de commit.
- Story 4.2 reforçou proveniência entre política e catálogo, fingerprint governado do catálogo e versionamento incompatível.
- Story 4.3 consolidou simulação não produtiva, avaliação comum, lacunas acionáveis e auditoria segura.
- Story 4.4 reforçou publicação imutável, simulação compatível, conflitos de vigência e auditoria crítica antes de exposição.
- Story 4.5 consolidou `CreditDecision` como entidade transacional, fingerprint decisório, proveniência completa e paridade com avaliador.
- Story 4.6 consolidou fallback automatizado sem fila manual, lacunas seguras, `reject_by_policy` explícito e `approve_with_changes` governado.
- Story 4.7 consolidou resposta explicável customer-safe, audiência interna com escopo explícito, leitura por decisão/proposta e validação antes de persistência.

### Git Intelligence

- O baseline da branch é `d4b0946`, merge do PR #44.
- Commits recentes mostram padrão de uma branch por story, implementação cirúrgica, correções pós-review no mesmo PR e atualização de artefatos BMAD/Jira.
- Não usar conta/chave `Avalia-Tachian`; commits deste projeto devem manter `Andre Tachian <altachian@gmail.com>`.

### Latest Technical Information

- Não há seleção tecnológica nova nesta story.
- Pesquisa web não é necessária porque os gates usam dependências já fixadas no repositório: Python 3.13, pytest, Ruff, Pyright e utilitários internos `creditos-security`/`creditos-observability`.
- Se surgir necessidade de ferramenta nova de testes/contratos, pausar e justificar alternativas, consequências e ADR antes de adicionar dependência.

### References

- `_bmad-output/planning-artifacts/epics.md` — Epic 4 / Story 4.8.
- `docs/input/project-technical-premises.md` — premissas de segurança, privacidade, DDD, testes, decisão de crédito, IA e auditoria.
- `docs/development.md` — fluxo local, CI e gates obrigatórios.
- `docs/contracts.md` — política de contratos versionados e limitação atual de diff semântico.
- `docs/microservice-template.md` — camadas obrigatórias e limites de `packages`.
- `docs/observability.md` — logs estruturados, mascaramento, métricas e anti-padrões.
- `_bmad-output/implementation-artifacts/4-1-modelo-versionado-de-politica-de-credito.md` — política versionada e guardrails iniciais.
- `_bmad-output/implementation-artifacts/4-2-catalogo-de-reason-codes-e-fatores-explicaveis.md` — catálogo e fatores explicáveis.
- `_bmad-output/implementation-artifacts/4-3-simulacao-e-validacao-de-politica.md` — simulação não produtiva e validação.
- `_bmad-output/implementation-artifacts/4-4-publicacao-imutavel-de-politica-aprovada.md` — publicação imutável.
- `_bmad-output/implementation-artifacts/4-5-execucao-deterministica-de-decisao.md` — decisão determinística.
- `_bmad-output/implementation-artifacts/4-6-tratamento-de-propostas-inconclusivas-sem-fila-manual.md` — fallback automatizado e inconclusão.
- `_bmad-output/implementation-artifacts/4-7-resposta-explicavel-de-decisao.md` — resposta explicável, privacidade e leitura governada.
- `services/decision/src/creditos_decision/application/service.py` — casos de uso do `Decision Service`.
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py` — entidade decisória e resposta explicável.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py` — política versionada e publicação.
- `services/decision/src/creditos_decision/domain/entities/policy_simulation.py` — simulação.
- `services/decision/src/creditos_decision/domain/entities/reason_code_catalog.py` — catálogo de reason codes.
- `services/decision/src/creditos_decision/domain/services/policy_evaluator.py` — avaliador determinístico comum.
- `services/decision/tests/unit/*` — suítes existentes a fortalecer.

## Dev Agent Record

### Agent Model Used

GPT-5.1 Codex

### Debug Log References

- `.venv/bin/pytest services/decision/tests/unit/test_epic4_decision_governance_gates.py` — RED inicial: 5 passed, 1 failed por expectativa de erro customer-safe específico.
- `.venv/bin/pytest services/decision/tests/unit/test_epic4_decision_governance_gates.py services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py` — 51 passed após correção mínima do código de erro.
- `.venv/bin/pytest services/decision/tests/unit/test_credit_policy_model.py services/decision/tests/unit/test_credit_policy_publication_model.py services/decision/tests/unit/test_credit_policy_publication_service.py services/decision/tests/unit/test_policy_simulation_model.py services/decision/tests/unit/test_policy_simulation_service.py services/decision/tests/unit/test_reason_code_catalog_model.py services/decision/tests/unit/test_reason_code_catalog_service.py services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py services/decision/tests/unit/test_epic4_decision_governance_gates.py` — 117 passed.
- `.venv/bin/ruff format .` — 1 arquivo reformatado.
- `.venv/bin/ruff format --check .` — 228 arquivos formatados.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/pyright` — 0 errors.
- `.venv/bin/pytest` no sandbox — 537 passed, 3 failed por socket local bloqueado e `uv` ausente no PATH.
- `.venv/bin/pytest` fora do sandbox — 539 passed, 1 failed por condição ambiental preexistente: `scripts/dev: line 47: uv: command not found`.
- `.venv/bin/pytest services/decision/tests/unit/test_epic4_decision_governance_gates.py services/decision/tests/unit/test_credit_decision_model.py services/decision/tests/unit/test_credit_decision_service.py` — 51 passed após patches da revisão adversarial.
- `.venv/bin/ruff format --check .` — 228 arquivos formatados após patches da revisão adversarial.
- `.venv/bin/ruff check .` — passed após patches da revisão adversarial.
- `.venv/bin/pyright` — 0 errors após patches da revisão adversarial.

### Completion Notes List

- Implementado arquivo consolidado de gates do Epic 4 cobrindo política, catálogo, simulação, publicação, execução, explicabilidade, privacidade, autorização, tenant isolation e governança contra decisor externo.
- Adicionada regressão de determinismo comprovando fingerprint estável para mesma entrada governada sem depender de `decision_id`, timestamp ou `correlation_id`.
- Adicionadas regressões negativas para impedir IA/provider payload/resultado proprietário como autoridade final da decisão.
- Corrigido código de erro para decisão final sem reason code visível ao cliente, preservando diagnóstico específico em vez de cair no erro genérico de justificativa governada.
- Aplicados patches da revisão adversarial: mensagem de erro mais específica, serialização fiel de dataclasses no gate de privacidade e cenário negativo com PII real bloqueada na origem explicável.
- Atualizado `services/decision/README.md` com os gates e limites da Story 4.8.
- Registrada falha ambiental preexistente de `uv` ausente no PATH em `_bmad-output/implementation-artifacts/deferred-work.md`.

### File List

- `_bmad-output/implementation-artifacts/4-8-gates-de-decisao-politica-e-explicabilidade.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`
- `services/decision/tests/unit/test_epic4_decision_governance_gates.py`

## Change Log

- 2026-09-04 — Story 4.8 detalhada com branch inicial, subtarefas Jira, contexto das Stories 4.1–4.7 e guardrails para gates de decisão, política e explicabilidade.
- 2026-09-04 — Implementados gates consolidados do Epic 4, documentação do Decision Service e correção mínima do código de erro de explicabilidade customer-safe; story marcada para review.
- 2026-09-04 — Patches da revisão adversarial aplicados e story marcada como done.
