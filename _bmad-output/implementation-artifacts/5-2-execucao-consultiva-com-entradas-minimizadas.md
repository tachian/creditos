---
jira_issue: CTOS-48
branch: agent/story-5-2-execucao-consultiva-entradas-minimizadas
baseline_commit: a7c3f11
created_at: 2026-09-09
subtasks:
  - CTOS-287
  - CTOS-288
  - CTOS-289
  - CTOS-290
  - CTOS-291
  - CTOS-292
  - CTOS-293
---

# Story 5.2: Execução Consultiva com Entradas Minimizadas

Status: done

## Story

Como `Automated Review Service`,
quero executar revisão usando apenas entradas permitidas e minimizadas,
para que a IA ajude sem expor dados sensíveis além do necessário.

## Acceptance Criteria

1. **Entrada minimizada por configuração publicada**
   - **Given** uma solicitação de revisão por política configurada
   - **When** o serviço prepara a entrada para IA
   - **Then** aplica allowlist, minimização, mascaramento e referências técnicas
   - **And** não persiste prompt ou payload sensível bruto por padrão.

2. **Tratamento de campos sensíveis não permitidos**
   - **Given** campos sensíveis não permitidos
   - **When** a entrada é montada
   - **Then** os campos são omitidos, mascarados, tokenizados ou referenciados
   - **And** o evento registra a política de minimização aplicada.

3. **Execução estritamente consultiva**
   - **Given** uma execução de revisão automatizada
   - **When** a entrada minimizada for enviada ao executor consultivo
   - **Then** a saída não aprova, reprova, altera termos, chama integrações externas, executa callback ou publica decisão final
   - **And** qualquer resposta deve permanecer classificada como consultiva.

4. **Rastreabilidade segura**
   - **Given** uma execução aceita, rejeitada ou bloqueada por minimização
   - **When** logs, eventos ou intenções auditáveis forem emitidos
   - **Then** registram tenant, produto, canal, propósito, configuração publicada, correlation ID, trace ID quando disponível e política aplicada
   - **And** não registram prompt bruto, payload bruto, CPF, CNPJ, nome, e-mail, endereço, telefone, credenciais ou dados financeiros detalhados.

5. **Isolamento por tenant e contexto confiável**
   - **Given** uma requisição com contexto propagado
   - **When** o caso de uso executa
   - **Then** usa `tenant_id`, `tenant_isolation_tier`, ator e scopes vindos do `PropagatedContext`
   - **And** rejeita contexto divergente, cross-tenant ou tier diferente de `bridge` no MVP.

6. **Sem ampliação indevida de escopo**
   - **Given** que esta story implementa o núcleo da execução consultiva minimizada
   - **When** o dev agent trabalhar na implementação
   - **Then** não escolhe fornecedor/modelo real, não adiciona SDK de IA, não cria endpoint público, não implementa gRPC real, NATS, banco real, dashboard ou evidência oficial append-only
   - **And** lacunas estruturais devem ser registradas como trabalho futuro ou story posterior.

## Tasks / Subtasks

- [x] CTOS-287 — Modelar solicitação e plano de execução consultiva minimizada (AC: 1, 2, 5, 6)
  - [x] Criar objetos de domínio/aplicação para solicitação consultiva, plano de minimização e referência de execução.
  - [x] Exigir configuração `published` e rejeitar configuração `draft`, `archived` ou inexistente.
  - [x] Usar produto, canal e propósito compatíveis com `ReviewAgentScope`.
  - [x] Não aceitar payload livre como contrato de domínio; entradas devem passar por campos governados.

- [x] CTOS-288 — Implementar allowlist, minimização e classificação de campos (AC: 1, 2, 4)
  - [x] Reusar `ReviewAgentPrompt.input_allowlist` como fonte governada de campos permitidos.
  - [x] Classificar cada campo como `included`, `omitted`, `masked`, `tokenized` ou `referenced`.
  - [x] Omitir/bloquear campos sensíveis fora da allowlist e registrar apenas metadados seguros.
  - [x] Garantir que prompt bruto e payload bruto não sejam persistidos por padrão.

- [x] CTOS-289 — Implementar ports e adapter in-memory de execução consultiva (AC: 1, 3, 4, 6)
  - [x] Criar port para executor consultivo de IA sem dependência de SDK/provedor real.
  - [x] Criar port/repositório in-memory para rastreabilidade segura de execução quando necessário.
  - [x] Manter chamadas externas atrás de ports e retornar saída mockada/contratual no MVP.
  - [x] Preservar DDD/hexagonal: domínio sem FastAPI, banco, NATS, gRPC ou SDKs.

- [x] CTOS-290 — Criar testes RED e regressões da execução minimizada (AC: 1-6)
  - [x] Cobrir allowlist, omissão de campo proibido, mascaramento/tokenização/referência e ausência de persistência bruta.
  - [x] Cobrir contexto divergente, cross-tenant, configuração não publicada e escopo incompatível.
  - [x] Cobrir que IA não aprova, reprova, altera termos, chama integração externa ou publica decisão.
  - [x] Rodar testes focados de `services/automated-review` e gates Ruff/Pyright aplicáveis.

- [x] CTOS-291 — Criar application service de execução consultiva (AC: 1, 3, 4, 5)
  - [x] Resolver configuração publicada por tenant, produto, canal e propósito.
  - [x] Gerar plano de minimização antes de qualquer execução consultiva.
  - [x] Exigir scopes de execução, contexto confiável e `tenant_isolation_tier=bridge`.
  - [x] Retornar resultado consultivo com referências técnicas, nunca decisão final.

- [x] CTOS-292 — Garantir logs, auditoria e eventos minimizados (AC: 2, 4, 5)
  - [x] Emitir logs estruturados com operação, status, duração, tenant, config/version, correlation ID e contagens por classificação.
  - [x] Emitir intenção auditável/evento minimizado com política aplicada e referências técnicas.
  - [x] Garantir que erros não revelem payload, prompt, PII, credenciais ou existência cross-tenant.
  - [x] Validar que todo campo sensível é omitido, mascarado, tokenizado ou referenciado antes de registro.

- [x] CTOS-293 — Atualizar story, documentação e rastreabilidade BMAD/Jira (AC: 4, 6)
  - [x] Atualizar esta story com arquivos alterados, decisões locais e evidências de testes.
  - [x] Atualizar `services/automated-review/README.md` com o fluxo da Story 5.2.
  - [x] Manter subtarefas Jira em `Em andamento`, `Review QA` e `Concluído` conforme avanço.
  - [x] Registrar limitações conhecidas: execução mockada/consultiva e ausência de provedor real.

### Review Findings

- [x] [Review][Patch] Aplicar allowlist estrita para execução consultiva — Decisão aprovada: o executor recebe somente campos presentes em `ReviewAgentPrompt.input_allowlist`; campos `referenced`/`tokenized` fora da allowlist ficam apenas como metadados minimizados e não alimentam o executor.
- [x] [Review][Patch] Checar idempotência antes de chamar o executor consultivo [`services/automated-review/src/creditos_automated_review/application/service.py`:389]
- [x] [Review][Patch] Rejeitar `source_ref` e `token_ref` com PII, segredo ou credencial técnica [`services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py`:77]
- [x] [Review][Patch] Rejeitar `proposal_id` sensível antes de persistir ou auditar execução [`services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`:156]
- [x] [Review][Patch] Aplicar schema de tipo e faixa por campo permitido na entrada consultiva [`services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py`:236]
- [x] [Review][Patch] Converter falha do executor em resultado `failed` ou `fallback` auditável [`services/automated-review/src/creditos_automated_review/application/service.py`:390]
- [x] [Review][Patch] Derivar `event_type` e status de log a partir do status real da execução [`services/automated-review/src/creditos_automated_review/application/service.py`:411]
- [x] [Review][Patch] Propagar `trace_id` na intenção auditável de execução [`services/automated-review/src/creditos_automated_review/application/ports/review_execution_audit_publisher.py`:16]
- [x] [Review][Patch] Exigir contexto observável completo para logs de execução com tenant e tier [`services/automated-review/src/creditos_automated_review/application/service.py`:491]
- [x] [Review][Patch] Rejeitar resolução ambígua de configuração publicada quando versão/configuração não forem explícitas [`services/automated-review/src/creditos_automated_review/application/service.py`:471]
- [x] [Review][Patch] Alinhar validação de `policy_ref` ao contrato aceito por `prompt_version` [`services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py`:156]
- [x] [Review][Patch] Bloquear payload bruto por normalização e fragmentos, não apenas nomes exatos [`services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py`:54]
- [x] [Review][Patch] Não persistir valores de entrada minimizada como rastreabilidade da execução [`services/automated-review/src/creditos_automated_review/application/service.py`:402]
- [x] [Review][Patch] Remover fixtures com PII realista dos testes da Story 5.2 [`services/automated-review/tests/unit/test_consultative_review_execution.py`:62]

## Dev Notes

### Escopo desta story

- Esta story implementa a preparação e execução consultiva com entrada minimizada dentro do `Automated Review Service`.
- A execução deve usar configuração publicada criada na Story 5.1 e respeitar `ReviewAgentScope`, `ReviewAgentPrompt.input_allowlist`, `ReviewAgentGuardrails` e `ReviewAgentCapabilities`.
- O executor de IA deve ser uma abstração/port com implementação fake/in-memory para testes; não adicionar SDK, chamada HTTP externa, secrets, egress real ou seleção de fornecedor.
- O resultado desta story ainda não vira evidência consultiva final vinculada à proposta; esse vínculo pertence à Story 5.4.
- Validação profunda de output/guardrails de resposta pertence à Story 5.3; nesta story, impedir autonomia decisória e dados sensíveis na entrada/logs já é obrigatório.

### Fronteiras de domínio

- `Automated Review` é o único bounded context autorizado a falar com provedores/modelos de IA; `Integration` continua dono de provedores externos de dados/notificação.
- `Decision` continua sendo a única fonte da decisão final, termos aprovados e reason codes determinísticos.
- A IA pode sugerir lacunas, inconsistências, sinais relevantes e fatores explicáveis, mas nunca pode aprovar, reprovar, alterar termos, publicar decisão, chamar ferramenta, callback ou integração externa.
- `Audit & Evidence` permanece dono da trilha oficial append-only; esta story pode emitir intenção auditável minimizada, mas não implementa o banco append-only oficial.
- `Reporting & Insights` receberá métricas/agregados em story posterior; esta story deve produzir metadados seguros que permitam observabilidade futura.

### Modelo esperado

- Criar uma entrada governada de execução, por exemplo `AutomatedReviewExecutionRequest`, com IDs técnicos, `proposal_id`/referência técnica, `product_type`, `channel`, `review_purpose`, `requested_at` e campos candidatos governados.
- Criar plano de minimização, por exemplo `InputMinimizationPlan`, com:
  - campos incluídos por allowlist;
  - campos omitidos por sensibilidade ou ausência na allowlist;
  - campos mascarados/tokenizados/referenciados quando a regra permitir;
  - contadores por classificação;
  - versão/fingerprint da política aplicada.
- Criar resultado de execução consultiva, por exemplo `AutomatedReviewExecutionResult`, com status consultivo, referências técnicas, versão de config, versão de prompt, limitação/fallback quando aplicável e payload de saída mockado/validável.
- Usar apenas campos candidatos compatíveis com a allowlist atual da Story 5.1: `requested_amount_units`, `requested_installments`, `requested_term_days`, `monthly_income_units`, `declared_revenue_units`, `company_age_months`, `relationship_age_days`.
- Se a implementação precisar de novos campos permitidos, não inventar silenciosamente: propor alteração governada na allowlist e documentar consequência para configuração/prompt.

### Segurança, privacidade e minimização

- `tenant_id`, `tenant_isolation_tier`, ator e scopes vêm exclusivamente do `PropagatedContext`; dados do body não são fonte confiável de identidade ou tenant.
- `ObservabilityContext` deve ser compatível com o contexto confiável, seguindo o padrão já implementado em `AutomatedReviewApplicationService`.
- Logs e audit intents podem conter IDs técnicos, versões, status, contagens, fingerprints, correlation ID, trace ID quando disponível e nome da política de minimização aplicada.
- Logs e audit intents não podem conter prompt bruto, payload bruto, CPF, CNPJ, e-mail completo, nome, endereço, telefone, documento, token, segredo, header sensível ou dado financeiro detalhado.
- Erros de validação devem ser seguros e não revelar conteúdo sensível. Falhas cross-tenant devem continuar indistinguíveis de recurso inexistente quando consultarem configuração ou execução.
- Não persistir entrada bruta. Se for necessário persistir rastreabilidade, persistir somente snapshot minimizado, hashes/referências técnicas e metadados seguros.

### Multi-tenancy

- O MVP usa modelo `bridge`; esta story deve rejeitar `tenant_isolation_tier` diferente de `bridge` enquanto `silo` não for suportado.
- Repositórios/adapters in-memory devem ser chaveados por tenant e nunca retornar execução/configuração de outro tenant.
- Métricas/logs podem carregar `tenant_id` apenas com cuidado de cardinalidade; agregações customer-facing pertencem a story futura de observabilidade.

### Arquitetura e estrutura esperada

- Trabalhar dentro de `services/automated-review/src/creditos_automated_review`.
- Preferir novos arquivos em:
  - `domain/entities` ou `domain/value_objects` para regras puras de solicitação, minimização e resultado consultivo;
  - `application/service.py` ou módulo de aplicação dedicado para comandos/casos de uso;
  - `application/ports` para executor consultivo e repositório/evento minimizado;
  - `adapters/persistence` para adapters in-memory;
  - `tests/unit` para testes de domínio/aplicação.
- Não mover código de `Decision`, `Integration` ou pacotes compartilhados para cumprir esta story.
- Reusar padrões existentes de `ReviewAgentConfiguration`, portas, adapter in-memory, logs minimizados e validação de contexto da Story 5.1.
- Se a story crescer demais para `application/service.py`, criar módulo dedicado e exportar de forma explícita, preservando compatibilidade com os testes existentes.

### Anti-patterns a evitar

- Não implementar provedor/modelo real de IA.
- Não adicionar dependência de OpenAI, Anthropic, Bedrock, Vertex, Ollama ou SDK similar.
- Não criar `metadata: dict[str, Any]` ou `payload: dict[str, Any]` livre como contrato principal de domínio.
- Não logar nem persistir prompt bruto, payload bruto, fixture com PII realista, headers, secrets ou tokens.
- Não permitir que saída de IA tenha semântica de decisão final.
- Não criar endpoint HTTP público, contrato gRPC real, NATS, outbox/inbox, migration ou dashboard nesta story.
- Não ampliar allowlist de entrada sem justificar a governança e o impacto em privacidade.

### Testes esperados

- Começar por testes RED em `services/automated-review/tests/unit`.
- Testar criação do plano de minimização com campos permitidos, omitidos, mascarados/tokenizados/referenciados e contadores.
- Testar que campos sensíveis não entram em prompt, logs, audit intents ou persistência.
- Testar que configuração `draft`, `archived`, inexistente, de outro tenant ou fora do escopo produto/canal/propósito é rejeitada.
- Testar que execução consultiva exige scope apropriado, contexto confiável e `bridge`.
- Testar que resultado consultivo não possui aprovação, reprovação, alteração de termos, callback, tool use ou publicação de decisão.
- Comandos recomendados:
  - `.venv/bin/pytest services/automated-review/tests/unit`
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`

### Previous Story Intelligence

- A Story 5.1 criou `ReviewAgentConfiguration`, `ReviewAgentPrompt`, `ReviewAgentGuardrails`, `ReviewAgentCapabilities`, `ReviewModelRef`, portas de repositório/auditoria, adapter in-memory e `AutomatedReviewApplicationService`.
- A configuração publicada é imutável e exige `approval_reference`; alterações em configuração publicada criam nova versão em `draft`.
- `owner_subject_id` vem do contexto confiável, não do body.
- Logs/auditoria já devem validar consistência entre `ObservabilityContext` e `PropagatedContext`.
- `ReviewAgentPrompt` calcula e valida fingerprint real do conteúdo do prompt.
- `list_published_by_scope` já filtra por tenant, produto, canal e propósito; reutilizar esse padrão para resolver configuração executável.
- Updates sem mudança real são rejeitados; evitar criar eventos/auditoria ruidosos.
- A suíte atual cobre tenant isolation, imutabilidade, logs minimizados e bloqueios de capacidades autônomas; não quebrar esses comportamentos.

### Git Intelligence

- Baseline da branch: `a7c3f11`, após merge da Story 5.1.
- Commits recentes de 5.1 corrigiram formatação Ruff, lookup de publicação, validação de `approval_reference`, fingerprint de prompt, auditoria antes de commit e remoção de chave indevida.
- Commits deste projeto devem usar `Andre Tachian <altachian@gmail.com>`.
- Fluxo acordado: branch no início da story, Jira acompanha subtarefas, `bmad-dev-story`, `bmad-code-review`, depois `commit/push/draft PR`.

### Latest Technical Information

- Nenhuma pesquisa web é necessária nesta story porque não há seleção de tecnologia nova, fornecedor/modelo real, SDK de IA ou API externa.
- Se surgir necessidade de escolher provedor/modelo, secret manager, SDK ou protocolo adicional, pausar e apresentar alternativas, justificativa e consequências antes de implementar.

### Project Structure Notes

- `services/automated-review` já existe; esta story deve estender o serviço criado na 5.1, não recriá-lo.
- O pacote permanece `creditos_automated_review`; evitar nomes como `ai_service`, `llm_service` ou acoplados a fornecedor.
- O Jira da história é `CTOS-48`; subtarefas `CTOS-287` a `CTOS-293` foram criadas/sincronizadas antes da implementação.
- Não foi encontrado `project-context.md` no workspace durante a ativação do workflow; usar PRD, Architecture, Epics, stories anteriores e README como fontes de verdade disponíveis.

### References

- `_bmad-output/planning-artifacts/epics.md` — Epic 5, Stories 5.1 a 5.6 e ACs da Story 5.2.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md` — padrões de logging, privacidade, observabilidade, DDD, IA e backlog de dados/modelos.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md` — regras de mascaramento, omissão e proibição de payload sensível bruto.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md` — telemetria técnica/negócio, tenant, correlation ID, trace ID e redaction.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-4, AD-5, AD-6, AD-7, AD-10, AD-11 e AD-16.
- `docs/microservice-template.md` — estrutura obrigatória de microsserviço DDD/hexagonal.
- `docs/development.md` — comandos locais, gates de qualidade e padrões de desenvolvimento.
- `_bmad-output/implementation-artifacts/5-1-configuracao-versionada-de-agente-de-revisao.md` — contexto anterior, achados de revisão e padrões estabelecidos.
- `services/automated-review/README.md` — responsabilidades, limites e comandos locais do serviço.
- `services/automated-review/src/creditos_automated_review/application/service.py` — application service existente, contexto confiável, scopes, logs e auditoria minimizada.
- `services/automated-review/src/creditos_automated_review/domain/entities/review_agent_configuration.py` — agregado de configuração versionada.
- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_agent_config.py` — allowlist, escopo, guardrails, capacidades e validações de dados sensíveis.
- `services/automated-review/src/creditos_automated_review/application/ports/review_agent_config_repository.py` — resolução de configuração publicada por escopo.
- `services/automated-review/tests/unit/test_review_agent_configuration.py` — regressões existentes que a Story 5.2 não deve quebrar.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- 2026-09-09 — `CTOS-287` movido para `Em andamento`; iniciada implementação com ciclo RED/GREEN/REFACTOR.
- 2026-09-09 — RED: `.venv/bin/pytest services/automated-review/tests/unit/test_consultative_review_execution.py` falhou por imports ausentes esperados.
- 2026-09-09 — GREEN: `.venv/bin/pytest services/automated-review/tests/unit` passou com 14 testes.
- 2026-09-09 — Qualidade: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .` e `.venv/bin/pyright` passaram.
- 2026-09-09 — Regressão completa: `.venv/bin/pytest` passou 552 testes e falhou 1 teste ambiental preexistente por `scripts/dev: line 47: uv: command not found`; primeira execução em sandbox também bloqueou sockets locais do harness, resolvido com execução elevada.

### Completion Notes List

- Implementado núcleo de execução consultiva minimizada no `Automated Review Service`, sem provedor real, SDK externo, endpoint público, gRPC, NATS ou banco real.
- Criados objetos de domínio para solicitação de execução, candidatos de entrada, plano de minimização e resultado consultivo, com bloqueio de payload bruto.
- Reutilizada a configuração publicada da Story 5.1 por tenant, produto, canal e propósito; configurações não publicadas ou fora de escopo não executam.
- Implementados ports/adapters para executor consultivo mockado, repositório in-memory de execução e intenção auditável minimizada.
- Logs e auditoria registram apenas metadados seguros, contagens por ação de minimização e referências técnicas; prompt/payload bruto não são persistidos.
- Limitação ambiental local: `uv` não está instalado/disponível no PATH deste ambiente, afetando apenas o teste do comando documentado `scripts/dev harness-check`.

### Change Log

- 2026-09-09 — Adicionada execução consultiva minimizada, ports/adapters mockados, testes unitários e documentação da Story 5.2.

### File List

- `_bmad-output/implementation-artifacts/5-2-execucao-consultiva-com-entradas-minimizadas.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/automated-review/README.md`
- `services/automated-review/src/creditos_automated_review/adapters/model/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/model/mock_consultative_review_executor.py`
- `services/automated-review/src/creditos_automated_review/adapters/persistence/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/persistence/in_memory_review_execution_repository.py`
- `services/automated-review/src/creditos_automated_review/application/__init__.py`
- `services/automated-review/src/creditos_automated_review/application/ports/__init__.py`
- `services/automated-review/src/creditos_automated_review/application/ports/consultative_review_executor.py`
- `services/automated-review/src/creditos_automated_review/application/ports/review_execution_audit_publisher.py`
- `services/automated-review/src/creditos_automated_review/application/ports/review_execution_repository.py`
- `services/automated-review/src/creditos_automated_review/application/service.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/automated_review_execution.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_execution.py`
- `services/automated-review/tests/unit/test_consultative_review_execution.py`
