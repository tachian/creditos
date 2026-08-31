---
jira_issue: CTOS-43
branch: agent/story-4-5-execucao-deterministica-de-decisao
baseline_commit: 032d75e
created_at: 2026-08-29
---

# Story 4.5: Execução Determinística de Decisão

Status: done

## Story

As a `Decision Service`,
I want executar política publicada sobre proposta canônica e resultados canônicos de integração,
so that o cliente receba uma decisão automática rastreável, reproduzível e explicável.

## Acceptance Criteria

1. **Execução com política publicada aplicável**
   - **Given** um `PropagatedContext` confiável, uma proposta já validada/normalizada, produto, canal, data efetiva UTC e uma política `published` aplicável ao tenant
   - **When** o `Decision Service` executa a decisão
   - **Then** gera uma decisão produtiva com `decision_id`, `tenant_id`, `proposal_id`, produto, canal, timestamp UTC, `policy_id`, `policy_version_id`, revisão da política, catálogo de reason codes, outcome e `correlation_id`
   - **And** a execução não depende diretamente de payload proprietário de fornecedor externo.

2. **Determinismo e reprodutibilidade**
   - **Given** os mesmos valores canônicos de entrada, a mesma política publicada, o mesmo catálogo publicado e os mesmos resultados canônicos de integração
   - **When** a avaliação é executada mais de uma vez
   - **Then** outcome, regras acionadas, reason codes, fatores explicáveis, termos aprovados e issues controladas são equivalentes
   - **And** o sistema registra um `decision_fingerprint` ou `evaluation_fingerprint` estável, calculado sem `decision_id`, timestamp ou campos sensíveis brutos.

3. **Resultados permitidos e default seguro**
   - **Given** entrada insuficiente, resultado parcial de integração, critério não satisfeito, limite violado ou regras conflitantes
   - **When** a política avalia a proposta
   - **Then** aplica apenas outcomes determinísticos já governados: `approve`, `reject`, `approve_with_changes`, `request_more_data` ou `unable_to_decide`
   - **And** ausência de dados, conflito entre outcomes ou falta de regra acionada nunca pode virar aprovação por default.

4. **Seleção e proteção de política produtiva**
   - **Given** políticas em `draft`, expiradas, fora da vigência, de outro tenant, de outro produto/canal ou com catálogo não produtivo
   - **When** a decisão é solicitada
   - **Then** a operação falha de forma controlada ou retorna ausência segura de política aplicável
   - **And** não revela existência de política, catálogo, simulação ou decisão de outro tenant.

5. **Explicabilidade mínima interna**
   - **Given** uma decisão final ou inconclusiva
   - **When** o resultado é persistido ou retornado pela camada de aplicação
   - **Then** inclui outcome, regras acionadas, reason code refs, factor refs, issues controladas, policy/catalog IDs e versões
   - **And** não inclui CPF, CNPJ, e-mail, nome, endereço, payload bruto, provider payload, headers, token, segredo ou stack trace.

6. **Auditoria crítica antes de visibilidade**
   - **Given** uma decisão produtiva calculada
   - **When** a aplicação vai persistir ou retornar a decisão final
   - **Then** publica intenção auditável minimizada antes de tornar a decisão visível
   - **And** falha crítica de auditoria impede persistência/retorno da decisão final e registra rejeição segura quando houver contexto confiável.

7. **Autorização, tenant e logs seguros**
   - **Given** chamada sem contexto confiável, tier diferente de `bridge`, tenant divergente ou scope insuficiente
   - **When** a decisão é executada
   - **Then** a operação é rejeitada antes de acessar política ou decisão
   - **And** logs estruturados registram operação, status, duração, IDs técnicos, tenant e correlation ID, mantendo payload como `[OMITIDO]`.

8. **Persistência in-memory e duplicidade controlada**
   - **Given** uma decisão já persistida para o mesmo `tenant_id` e `proposal_id`
   - **When** a execução é repetida sem fluxo explícito de reprocessamento
   - **Then** o repositório in-memory rejeita duplicidade ou retorna comportamento idempotente documentado
   - **And** reprocessamento produtivo, outbox transacional e replay por NATS ficam fora do escopo desta story.

## Tasks / Subtasks

- [x] CTOS-253 — Modelar decisão produtiva no domínio (AC: 1, 2, 3, 5)
  - [x] Criar `CreditDecision` ou entidade equivalente com `decision_id`, `tenant_id`, `proposal_id`, produto, canal, timestamps UTC, policy/catalog refs, outcome, reason codes, fatores, issues e fingerprint estável.
  - [x] Criar value objects de entrada produtiva usando apenas campos canônicos permitidos pela política; não reutilizar `PolicySimulationInputCase` como contrato produtivo.
  - [x] Validar IDs técnicos, canal, produto, datas UTC, campos governados e ausência de tokens/PII/payload bruto em detalhes seguros.
- [x] CTOS-254 — Reutilizar avaliador determinístico comum (AC: 2, 3, 5)
  - [x] Extrair lógica neutra de avaliação hoje embutida em `PolicySimulation` para evitar duplicação entre simulação e decisão real.
  - [x] Manter `PolicySimulation` como não produtiva e restrita a política `draft`.
  - [x] Garantir que política publicada use a mesma semântica de critérios, limites, operadores, conflitos e reason/factor refs.
- [x] CTOS-257 — Criar porta e adapter de decisão (AC: 1, 6, 8)
  - [x] Criar `CreditDecisionRepository` com implementação in-memory tenant-aware.
  - [x] Impedir vazamento cross-tenant e duplicidade não controlada por `(tenant_id, proposal_id)` ou chave documentada.
  - [x] Suportar operação com callback `before_commit` para auditoria crítica antes da decisão ficar visível.
- [x] CTOS-255 — Estender `DecisionApplicationService` (AC: 1, 4, 6, 7, 8)
  - [x] Criar comando `ExecuteCreditDecisionCommand` ou nome equivalente com `proposal_id`, produto, canal, `effective_at`, valores canônicos e identificadores seguros de resultados de integração.
  - [x] Selecionar política publicada aplicável via repositório existente; não aceitar `policy_id` arbitrário vindo do payload do cliente como fonte final de verdade.
  - [x] Exigir `PropagatedContext`, tier `bridge` e scope explícito `decision:execute`.
  - [x] Retornar resultado de aplicação com decisão e logs estruturados seguros.
- [x] CTOS-256 — Ampliar auditoria minimizada (AC: 5, 6, 7)
  - [x] Criar `CreditDecisionAuditIntent` tipado ou extensão equivalente no publisher existente, sem `Any`.
  - [x] Registrar somente IDs, outcome, policy/catalog refs, contagens, fingerprint, correlation ID e status seguro.
  - [x] Testar falha de auditoria crítica sem decisão persistida nem retornada como final.
- [x] CTOS-258 — Criar testes RED e regressões (AC: 1, 2, 3, 4, 5, 6, 7, 8)
  - [x] Testar execução feliz com política publicada, catálogo publicado, scope `decision:execute`, canal aplicável e entrada canônica suficiente.
  - [x] Testar determinismo/fingerprint com mesmas entradas e variação apenas de timestamp/`decision_id`.
  - [x] Testar `reject`, `approve`, `approve_with_changes`, `request_more_data` e `unable_to_decide` quando suportados por regras.
  - [x] Testar faltas de campo, limites violados, regras conflitantes, política inexistente, política `draft`, janela expirada, canal/produto incorreto, tenant divergente e scope insuficiente.
  - [x] Testar logs/auditoria sem payload bruto, CPF, CNPJ, e-mail, nome, headers, tokens ou secrets.
- [x] CTOS-259 — Atualizar documentação e rastreabilidade (AC: 1, 5, 6, 8)
  - [x] Atualizar `services/decision/README.md` com escopo da Story 4.5 e fronteiras com Stories 4.6 e 4.7.
  - [x] Atualizar este artefato BMAD, `sprint-status.yaml` e Jira conforme avanço real.
  - [x] Registrar decisões de escopo tomadas durante a implementação.

### Review Findings

- [x] [Review][Patch] Semântica conservadora para termos aprovados — Decisão tomada: permitir `approve` somente com termos completos e bloquear `approve_with_changes` produtivo até existir modelo explícito de termos ajustados.
- [x] [Review][Patch] `decision_fingerprint` não cobre valores canônicos avaliados [`services/decision/src/creditos_decision/domain/entities/credit_decision.py:179`]
- [x] [Review][Patch] Auditoria de decisão não registra refs de catálogo em campos/safe details [`services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py:42`]
- [x] [Review][Patch] `CreditDecision.create` não valida proveniência completa do catálogo contra a política [`services/decision/src/creditos_decision/domain/entities/credit_decision.py:144`]
- [x] [Review][Patch] `CreditDecision.create` não vincula `evaluation_id` ao `proposal_id` avaliado [`services/decision/src/creditos_decision/domain/entities/credit_decision.py:126`]
- [x] [Review][Patch] Construção direta de `CreditDecision` não valida refs técnicos internos [`services/decision/src/creditos_decision/domain/entities/credit_decision.py:105`]
- [x] [Review][Patch] Paths de issues do avaliador comum perdem identidade do caso/proposta [`services/decision/src/creditos_decision/domain/services/policy_evaluator.py:168`]
- [x] [Review][Patch] Códigos de erro de simulação regrediram para nomes genéricos do avaliador comum [`services/decision/src/creditos_decision/domain/entities/policy_simulation.py:110`]
- [x] [Review][Patch] Auditoria de rejeição pode usar `unknown_credit_decision` quando o ID foi gerado internamente [`services/decision/src/creditos_decision/application/service.py:815`]

## Dev Notes

### Escopo desta story

- Implementar a primeira decisão produtiva determinística dentro do `Decision Service`, ainda em camada de domínio/aplicação/adapters in-memory.
- Não implementar API HTTP, gRPC real, NATS JetStream, outbox, banco real, callback/webhook, Reporting, IA consultiva, chamada ao `Integration Service` ou execução de fornecedores externos nesta story.
- Comunicação interna futura continua sendo gRPC para chamadas síncronas e NATS JetStream para fluxos assíncronos, mas esta story deve preparar contratos internos Python sem acoplar infraestrutura real.
- A Story 4.6 tratará fallback/inconclusão com mais profundidade; esta story deve produzir outcomes controlados sem fila manual.
- A Story 4.7 tratará resposta explicável pública/consulta; esta story deve gerar explicabilidade mínima interna, persistível e segura.
- Não selecionar novas tecnologias. Usar Python 3.13, dataclasses, Protocols, DDD, arquitetura hexagonal, pytest, Ruff e Pyright já adotados no workspace.

### Decisões e guardrails obrigatórios

- `tenant_id` vem sempre do `PropagatedContext`; nunca do corpo do comando como autoridade.
- Scope recomendado para execução final: `decision:execute`, distinto de `policy:read`, `policy:write` e `policy:publish`.
- A política usada deve estar `published`, dentro da vigência UTC, compatível com produto/canal e com catálogo publicado correspondente.
- O input produtivo deve aceitar apenas valores canônicos governados e minimizados. Não aceitar `payload`, `provider_payload`, `provider_response`, `raw_payload`, `headers`, `metadata`, `custom`, CPF, CNPJ, nome, e-mail, endereço, token ou segredo.
- `requested_terms` continuam sendo a fonte de termos solicitados; não reintroduzir `plan_id` nem dependência de planos da financeira.
- `approve_with_changes` pode retornar termos aprovados minimizados, como `approved_amount_units`, `approved_installments` e `approved_term_days`, quando deriváveis por regra/limite; não inventar plano comercial externo.
- Ausência de dados e conflito de regras devem gerar `unable_to_decide` ou `request_more_data`, nunca aprovação implícita.
- IA não decide crédito nesta story. Qualquer IA futura é consultiva e rastreável.

### Reuso obrigatório do que já existe

- `CreditPolicy` já controla status `draft`/`published`, versão, revisão, fingerprint governado e imutabilidade.
- `CreditPolicyRepository.get` e `list_published_by_product` já permitem localizar políticas por tenant/produto; preservar isolamento por tenant.
- `InMemoryCreditPolicyRepository.publish_if_no_window_conflict` já usa `before_commit` para auditoria antes de visibilidade; repetir esse padrão no repositório de decisões.
- `ReasonCodeCatalog` já valida refs e possui `is_referenceable_for_final_decisions`; decisão produtiva deve exigir catálogo publicado.
- `PolicySimulation` contém a semântica atual de critérios, limites, operadores, regras acionadas, conflitos, reason codes e fatores; extrair lógica comum em vez de copiar/colar avaliação.
- `_require_policy_context`, `_log_operation`, `build_structured_log` e audit publisher existentes devem ser reutilizados.

### Arquivos existentes que provavelmente serão alterados

- `services/decision/src/creditos_decision/domain/entities/policy_simulation.py`: extrair ou delegar a lógica `_evaluate_case`, `_criteria_are_satisfied`, `_limits_are_satisfied`, `_matches_operator`, `_limit_field_and_operator`, `_factor_refs_for_reason_codes` e `_unique` para avaliador comum, preservando simulação não produtiva.
- `services/decision/src/creditos_decision/domain/value_objects/policy_simulation.py`: não transformar `PolicySimulationInputCase` em input produtivo; preservar `simulation=True` e `non_production=True`.
- `services/decision/src/creditos_decision/domain/entities/credit_policy.py`: usar `is_executable_in_production`; evitar mudar fingerprint/imutabilidade de política publicada sem necessidade.
- `services/decision/src/creditos_decision/domain/value_objects/policy.py`: reutilizar enums `PolicyOutcome`, `PolicyOperator`, campos governados e validações anti-PII.
- `services/decision/src/creditos_decision/application/service.py`: adicionar comando/caso de uso de execução de decisão e manter padrões de contexto, log, auditoria e rejeição segura.
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`: adicionar intenção tipada para decisão, se necessário, mantendo união explícita e sem `Any`.
- `services/decision/src/creditos_decision/application/ports/credit_policy_repository.py`: não sobrecarregar repositório de política com persistência de decisão; criar porta própria.
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_policy_repository.py`: usar como referência de lock, tenant key e callback antes de commit; não misturar armazenamento de decisão nesse adapter.
- `services/decision/README.md`: documentar a Story 4.5, limitações e fronteiras.

### Possíveis novos arquivos

```text
services/decision/src/creditos_decision/domain/entities/credit_decision.py
services/decision/src/creditos_decision/domain/services/policy_evaluator.py
services/decision/src/creditos_decision/domain/value_objects/credit_decision.py
services/decision/src/creditos_decision/application/ports/credit_decision_repository.py
services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_decision_repository.py
services/decision/tests/unit/test_credit_decision_model.py
services/decision/tests/unit/test_credit_decision_service.py
```

### Contrato interno sugerido

- `ExecuteCreditDecisionCommand` deve conter no mínimo:
  - `proposal_id`
  - `product_type`
  - `channel`
  - `effective_at`
  - `field_values` ou estrutura equivalente com campos canônicos governados
  - `integration_result_refs` ou `integration_snapshot_refs` minimizados, quando usados
  - `actor_subject_id`, se aplicável
- Não incluir `tenant_id`, documento do solicitante, nome, e-mail, endereço, payload bruto ou configuração proprietária de fornecedor.
- Se `decision_id` vier do comando para testes/idempotência local, validar como ID técnico; caso contrário, gerar internamente de forma segura.
- `decision_fingerprint` deve ser calculado sobre entradas canônicas, IDs/versões de política e catálogo, outcome e refs explicáveis; excluir timestamp, `decision_id`, logs e dados sensíveis.

### Persistência e auditoria

- Criar `CreditDecisionRepository` separado para preservar bounded context de decisões sem contaminar repositório de política.
- Para MVP in-memory, uma decisão persistida deve ser visível somente após sucesso da auditoria crítica.
- Se auditoria falhar, propagar erro controlado e manter repositório sem decisão final visível.
- Rejeições podem emitir intenção auditável segura quando houver contexto confiável; falha ao auditar rejeição não deve mascarar o erro original.
- Auditoria oficial append-only continua sendo responsabilidade futura do `Audit & Evidence`; aqui publicar apenas intenção minimizada pela porta existente.

### Segurança, privacidade e multi-tenancy

- Nenhum log, erro, audit intent, fingerprint ou resultado de aplicação deve carregar payload bruto, CPF, CNPJ, e-mail, nome, endereço, token, segredo ou headers.
- Erros cross-tenant devem ser indistinguíveis de não encontrado para o chamador.
- `tenant_isolation_tier` esperado no MVP é `bridge`; tier ausente ou incompatível deve falhar antes de consultar dados.
- Métricas de negócio são futuras em `Reporting`; esta story deve manter campos seguros suficientes para contagem por tenant/produto/outcome sem expor PII.

### Testes obrigatórios

- Rodar testes focados em `services/decision/tests/unit` antes de qualquer commit.
- Rodar gates de qualidade do repo antes do PR:
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run pyright`
  - `uv run pytest services/decision/tests/unit -q`
- Adicionar testes antes da implementação principal sempre que possível, seguindo o fluxo RED/GREEN já usado no Epic 4.
- Não corrigir bugs fora do escopo da Story 4.5; se aparecerem, registrar como finding ou débito separado.

### Latest Technical Information

- Nenhuma pesquisa externa foi necessária para esta story porque ela não introduz tecnologia, biblioteca, serviço externo ou API pública nova.
- Versões locais confirmadas no workspace:
  - Python `>=3.13`
  - Ruff `>=0.12.5`
  - Pytest `>=8.4.1`
  - Pyright `>=1.1.403`
- Se a implementação tentar adicionar dependência, framework, gRPC/NATS real ou banco real, deve parar e justificar alternativa, consequência e motivo arquitetural antes de prosseguir.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 4 / Story 4.5.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-13, FR-14 e FR-15.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/contrato-inicial-proposta-oq3.md` — contrato canônico e `requested_terms`.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md` — minimização e mascaramento.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md` — trilha append-only e proteção contra alteração.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — DDD, microserviços, gRPC, NATS, bridge tenancy, auditoria, SLOs e segurança.
- `_bmad-output/implementation-artifacts/4-4-publicacao-imutavel-de-politica-aprovada.md` — padrões de publicação, auditoria antes de visibilidade e rollback.

## Project Structure Notes

- O serviço segue arquitetura DDD/hexagonal: domínio sem frameworks, aplicação orquestrando casos de uso, portas por `Protocol`, adapters in-memory e testes unitários por serviço.
- O nome do pacote permanece `creditos_decision`.
- A implementação deve manter acentuação correta em documentação e mensagens de negócio em português.
- Não há `project-context.md` encontrado no repositório durante este workflow; usar os artefatos BMAD e padrões já implementados como fonte principal.

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- 2026-08-29 — Branch `agent/story-4-5-execucao-deterministica-de-decisao` já criada antes do detalhamento, seguindo decisão operacional do projeto de criar branch no início do desenvolvimento.
- 2026-08-29 — Jira `CTOS-43` já movido para `Em andamento` antes do `bmad-create-story`.
- 2026-08-29 — `bmad-create-story` executado com desvio controlado: status BMAD foi ajustado para `ready-for-dev` embora o card Jira permaneça em andamento por causa do fluxo branch-first aprovado.
- 2026-08-30 — `bmad-dev-story` iniciado; `CTOS-253` movido para `Em andamento`.
- 2026-08-30 — Testes RED criados para modelo e aplicação de decisão produtiva.
- 2026-08-30 — Implementados domínio, avaliador comum, repositório in-memory, auditoria e caso de uso de execução.
- 2026-08-30 — Validações executadas: Ruff format/check, Pyright, testes unitários do Decision e regressão completa.
- 2026-08-31 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 9 patches aplicados e validados.

### Completion Notes List

- Story detalhada com foco em decisão produtiva determinística, reuso do avaliador de política, auditoria crítica antes de visibilidade, isolamento por tenant e ausência de payload sensível.
- Escopo limitado a domínio/aplicação/adapters in-memory; gRPC, NATS, banco real, outbox, IA, Reporting e resposta pública completa ficam para stories futuras.
- Implementada `CreditDecision` produtiva com fingerprint estável, termos aprovados minimizados e validações anti-PII.
- Extraído avaliador comum para preservar a mesma semântica entre simulação e decisão real.
- Implementado `ExecuteCreditDecisionCommand` com scope `decision:execute`, seleção de política publicada aplicável, logs seguros e auditoria crítica antes de visibilidade.
- Criado repositório in-memory de decisões com isolamento por tenant e controle de duplicidade por proposta.
- Atualizado README do `Decision Service` com escopo e fronteiras da Story 4.5.
- Pós-review: fingerprint passou a incluir hash da entrada canônica, auditoria registra refs de catálogo, `approve` exige termos completos e `approve_with_changes` produtivo fica bloqueado até modelo explícito de ajuste.
- Pós-review: avaliador comum preserva identidade do caso/proposta em issues, simulação remapeia erros para códigos específicos e rejeições usam ID gerado internamente quando aplicável.

### File List

- `_bmad-output/implementation-artifacts/4-5-execucao-deterministica-de-decisao.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/decision/README.md`
- `services/decision/src/creditos_decision/adapters/persistence/__init__.py`
- `services/decision/src/creditos_decision/adapters/persistence/in_memory_credit_decision_repository.py`
- `services/decision/src/creditos_decision/application/ports/__init__.py`
- `services/decision/src/creditos_decision/application/ports/credit_decision_repository.py`
- `services/decision/src/creditos_decision/application/ports/credit_policy_audit_publisher.py`
- `services/decision/src/creditos_decision/application/service.py`
- `services/decision/src/creditos_decision/domain/entities/__init__.py`
- `services/decision/src/creditos_decision/domain/entities/credit_decision.py`
- `services/decision/src/creditos_decision/domain/entities/policy_simulation.py`
- `services/decision/src/creditos_decision/domain/services/__init__.py`
- `services/decision/src/creditos_decision/domain/services/policy_evaluator.py`
- `services/decision/src/creditos_decision/domain/value_objects/__init__.py`
- `services/decision/src/creditos_decision/domain/value_objects/credit_decision.py`
- `services/decision/src/creditos_decision/domain/value_objects/policy_evaluation.py`
- `services/decision/tests/unit/test_credit_decision_model.py`
- `services/decision/tests/unit/test_credit_decision_service.py`
- `services/decision/tests/unit/test_policy_simulation_model.py`
- `services/decision/tests/unit/test_policy_simulation_service.py`

## Change Log

- 2026-08-30 — Implementada execução determinística produtiva de decisão com domínio, aplicação, auditoria, persistência in-memory, documentação e testes.
- 2026-08-31 — Aplicadas correções do `bmad-code-review` da Story 4.5 e status BMAD atualizado para `done`.
