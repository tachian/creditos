---
jira_issue: CTOS-47
branch: agent/story-5-1-configuracao-versionada-agente-revisao
baseline_commit: 6c6bf8b
created_at: 2026-09-07
---

# Story 5.1: Configuração Versionada de Agente de Revisão

Status: done

## Story

Como gestor autorizado,
quero configurar agente, modelo e prompt de revisão consultiva com versionamento,
para que revisões por IA sejam controladas, auditáveis e promovidas com segurança.

## Acceptance Criteria

1. **Configuração em draft**
   - **Given** um gestor autorizado com contexto confiável de tenant
   - **When** cria uma configuração de revisão automatizada
   - **Then** registra `review_agent_config_id`, `review_agent_config_version_id`, revisão, status `draft`, owner, produto, escopo de uso, versão do agente, prompt/configuração, provedor/modelo quando aplicável e changelog inicial
   - **And** a configuração em `draft` não pode ser usada em execução produtiva.

2. **Alteração rastreável sem mutar versão publicada**
   - **Given** uma configuração em status `draft`
   - **When** prompt, versão de agente, modelo/provedor, limites, escopo ou guardrails forem alterados
   - **Then** registra histórico mínimo com ator, timestamp, correlation ID, resumo log-safe, revisão anterior e revisão resultante
   - **And** não sobrescreve nenhuma configuração publicada.

3. **Publicação controlada**
   - **Given** uma configuração válida em `draft`
   - **When** um gestor com escopo autorizado solicita publicação
   - **Then** a versão é promovida para `published` com evidência auditável minimizada antes da exposição
   - **And** configurações sem aprovação/autorização, owner, escopo, agente, prompt ou guardrails mínimos são rejeitadas.

4. **Nova versão a partir de configuração publicada**
   - **Given** uma configuração `published`
   - **When** uma alteração é necessária
   - **Then** o sistema cria uma nova versão em `draft`
   - **And** preserva integralmente a versão usada em revisões passadas.

5. **Governança de IA consultiva**
   - **Given** qualquer configuração de agente/modelo/prompt
   - **When** o domínio valida suas permissões e capacidades
   - **Then** bloqueia aprovação, reprovação, alteração de termos, callback, integração externa, tool use autônomo ou publicação de decisão final pela IA
   - **And** deixa explícito que a configuração apenas habilita evidência consultiva para o `Decision`.

6. **Privacidade, tenant isolation e dados seguros**
   - **Given** valores de configuração, prompt e metadados
   - **When** são persistidos, logados ou auditados
   - **Then** não aceitam CPF, CNPJ, e-mail completo, nome, endereço, telefone, token, segredo, header sensível, payload bruto ou dado financeiro detalhado
   - **And** todas as mutações usam `tenant_id`/`tenant_isolation_tier=bridge` vindos do contexto confiável, nunca do body.

7. **Aplicação, portas e adapters mínimos**
   - **Given** o `Automated Review Service` como bounded context separado
   - **When** a configuração é criada, atualizada, publicada, versionada ou consultada
   - **Then** a camada de aplicação exige scopes adequados, usa portas hexagonais, emite logs estruturados minimizados e usa adapter in-memory transacional para testes
   - **And** consultas cross-tenant continuam indistinguíveis de recurso inexistente.

8. **Sem ampliação indevida de escopo**
   - **Given** que esta story inicia o Epic 5
   - **When** a implementação for feita
   - **Then** não executa modelo real, não chama provedor externo, não cria endpoint público, não implementa gRPC real, NATS, banco real, evidência oficial append-only, dashboard ou seleção final de fornecedor
   - **And** qualquer lacuna estrutural deve virar item em `deferred-work.md` ou story futura.

## Tasks / Subtasks

- [x] CTOS-280 — Criar base do `Automated Review Service` (AC: 1, 7, 8)
  - [x] Criar `services/automated-review` seguindo DDD + arquitetura hexagonal do template e padrões dos serviços existentes.
  - [x] Configurar `pyproject.toml`, exports e dependências somente para `creditos-observability` e `creditos-security`.
  - [x] Atualizar `pyproject.toml` raiz/`uv.lock` apenas se necessário pelo workspace.

- [x] CTOS-281 — Modelar configuração versionada de agente (AC: 1, 2, 4, 5, 6)
  - [x] Criar value objects/enums para status, produto, escopo de uso, versão de agente, prompt/configuração, provedor/modelo opcional, guardrails e changelog.
  - [x] Criar agregado imutável para configuração com criação em `draft`, atualização rastreável, publicação e nova versão a partir de `published`.
  - [x] Rejeitar capacidades autônomas de decisão final, tool use externo, callback ou alteração de termos.

- [x] CTOS-282 — Implementar validações de segurança e privacidade (AC: 5, 6)
  - [x] Validar texto log-safe para prompt/configuração e `change_summary`, bloqueando PII, tokens, segredos e payload bruto.
  - [x] Impedir campos livres como `metadata`, `raw_payload`, `provider_payload`, headers, credenciais e dados financeiros detalhados.
  - [x] Garantir que configuração não contém credencial ou segredo de provedor; credenciais ficam fora do domínio e serão tratadas por infraestrutura/secret manager futuro.

- [x] CTOS-283 — Criar portas e adapter in-memory (AC: 3, 4, 7)
  - [x] Criar porta de repositório scoped por tenant para salvar, consultar versão, listar publicadas por produto/escopo e criar nova versão.
  - [x] Criar porta de auditoria minimizada para eventos de criação, atualização, publicação, rejeição e nova versão.
  - [x] Implementar adapter in-memory com isolamento por tenant, imutabilidade de versões publicadas e rollback/atomicidade local quando auditoria crítica falhar.

- [x] CTOS-284 — Criar application service governado (AC: 1, 2, 3, 4, 7)
  - [x] Implementar comandos/casos de uso para criar draft, atualizar draft, publicar, criar nova versão e consultar configuração.
  - [x] Exigir contexto confiável, `tenant_isolation_tier=bridge`, owner/ator do contexto, scopes mínimos e deny-by-default.
  - [x] Emitir logs estruturados com payload omitido, correlação, contagens e status sem prompt sensível bruto.

- [x] CTOS-285 — Criar testes RED e regressões (AC: 1-8)
  - [x] Cobrir criação, update, publicação, nova versão, imutabilidade, versão histórica preservada e rejeições por autorização.
  - [x] Cobrir bloqueio de IA decisora final, tool use autônomo, callback, integração externa e alteração de termos.
  - [x] Cobrir tenant isolation, cross-tenant indistinguível de not found, logs/auditoria seguros e rejeição de PII/segredos.

- [x] CTOS-286 — Atualizar documentação e rastreabilidade (AC: 1, 5, 7, 8)
  - [x] Criar/atualizar `services/automated-review/README.md` com responsabilidades, limites, comandos e anti-patterns.
  - [x] Atualizar `sprint-status.yaml`, esta story e Jira conforme avanço.
  - [x] Registrar validações executadas no Dev Agent Record e lacunas reais em `deferred-work.md`.

### Review Findings

- [x] [Review][Patch] Publicação deve exigir `approval_reference` técnico e log-safe como evidência de aprovação explícita [services/automated-review/src/creditos_automated_review/application/service.py:65]
- [x] [Review][Patch] `owner_subject_id` vem do comando/body em vez do contexto confiável [services/automated-review/src/creditos_automated_review/application/service.py:41]
- [x] [Review][Patch] Criação, nova versão e mutações podem sobrescrever estado existente sem controle de existência/revisão [services/automated-review/src/creditos_automated_review/adapters/persistence/in_memory_review_agent_config_repository.py:13]
- [x] [Review][Patch] Logs/auditoria aceitam `ObservabilityContext` divergente do `PropagatedContext` confiável [services/automated-review/src/creditos_automated_review/application/service.py:338]
- [x] [Review][Patch] `ReviewAgentPrompt` aceita fingerprint fornecido sem validar contra o conteúdo real do prompt [services/automated-review/src/creditos_automated_review/domain/value_objects/review_agent_config.py:147]
- [x] [Review][Patch] Validação de textos/referências não cobre nomes, endereços e credenciais técnicas sem palavras bloqueadas; teste também usa PII bruta em fixture [services/automated-review/src/creditos_automated_review/domain/value_objects/review_agent_config.py:15]
- [x] [Review][Patch] `model_ref` opcional não pode ser removido em update porque `None` significa “não alterar” [services/automated-review/src/creditos_automated_review/domain/entities/review_agent_configuration.py:181]
- [x] [Review][Patch] Listagem de configurações publicadas filtra só por produto e ignora canal/propósito do escopo [services/automated-review/src/creditos_automated_review/application/ports/review_agent_config_repository.py:19]
- [x] [Review][Patch] Evento auditável não expõe campos mínimos do último changelog, como resumo seguro, timestamp e revisões anterior/resultante [services/automated-review/src/creditos_automated_review/application/ports/audit_publisher.py:7]
- [x] [Review][Patch] Agregado não valida consistência entre `product_type` e `scope.product_type` nem a sequência completa do changelog [services/automated-review/src/creditos_automated_review/domain/entities/review_agent_configuration.py:35]
- [x] [Review][Patch] Update sem mudança real cria nova revisão e evento auditável de alteração [services/automated-review/src/creditos_automated_review/domain/entities/review_agent_configuration.py:169]

## Dev Notes

### Escopo desta story

- Esta story cria o núcleo de configuração versionada do `Automated Review Service`; ela não executa IA, não monta prompt produtivo, não valida output de modelo, não registra evidência consultiva final e não integra com `Decision` por gRPC real.
- O foco é garantir que agente/modelo/prompt/configuração sejam artefatos governados antes das Stories 5.2 a 5.6.
- Implementar primeiro testes RED de domínio/aplicação, depois o mínimo de código necessário.
- Não escolher fornecedor/modelo específico. Provedor/modelo nesta story são metadados opcionais e substituíveis, não adoção tecnológica.
- Não adicionar SDK de IA, dependência de LLM, cliente HTTP externo, banco, NATS, gRPC, dashboard ou secret manager real.

### Fronteiras de domínio

- `Automated Review` é o único bounded context autorizado a falar com provedores/modelos de IA no MVP, mas esta story ainda não realiza chamada externa.
- `Decision` continua dono da política determinística, decisão final, termos aprovados e reason codes. O `Automated Review` nunca aprova, reprova, altera termos ou publica decisão final.
- `Integration` continua dono de provedores externos de dados/notificação; `Automated Review` só possui provedores/modelos de IA.
- `Audit & Evidence` é dono da trilha oficial; esta story emite intenção auditável minimizada, sem implementar append-only oficial.
- `Reporting & Insights` receberá métricas/agregados em story posterior; esta story só prepara logs seguros e campos observáveis mínimos.

### Modelo esperado

- Identificadores técnicos log-safe: `review_agent_config_id`, `review_agent_config_version_id`, `tenant_id`, `owner_subject_id`, `correlation_id`.
- Status mínimos: `draft`, `published`, `archived`. Alterações só podem ocorrer em `draft`; `published` é imutável.
- Produtos MVP permitidos devem seguir o padrão dos serviços existentes: `personal_credit`, `bnpl`, `business_credit`, `receivables`.
- Escopo de uso deve ser fechado e governado, por exemplo produto/canal/outcome/contexto consultivo, sem JSON livre.
- Prompt/configuração deve ser tratado como artefato sensível: validar texto seguro, manter versão/fingerprint e não expor conteúdo bruto em logs/auditoria.
- Guardrails mínimos devem existir como configuração governada: schema obrigatório, minimização de entrada, bloqueio de PII, bloqueio de autonomia decisória e fallback controlado.
- Provider/model metadata deve ser opcional: `provider_ref`, `model_ref`, `model_version` ou equivalentes técnicos seguros. Não armazenar API key, endpoint secreto ou headers.

### Segurança, privacidade e auditoria

- Alteração de agente/modelo/prompt é ação sensível coberta por FR-20 e AD-8; criação, update, publicação, rejeição e nova versão devem emitir intenção auditável minimizada.
- Logs estruturados podem conter IDs técnicos, versão, status, produto, escopo, contagens, erro controlado e correlation ID; não podem conter prompt bruto, payload bruto, credencial ou PII.
- Falhas de autorização, validação, publicação ou cross-tenant devem ser seguras e não revelar recurso de outro tenant.
- Usar `creditos_security.PropagatedContext`/`TrustedContext` como padrão de contexto confiável, scopes e tenant.
- Usar `creditos_observability.build_structured_log` ou padrão equivalente já aplicado nos serviços existentes.

### Multi-tenancy

- O MVP usa modelo `bridge`; exigir `tenant_isolation_tier="bridge"` nos casos de uso desta story.
- `tenant_id` vem exclusivamente do contexto confiável, nunca do comando/body.
- Repositórios e consultas devem ser chaveados por tenant e versão, com testes negativos cross-tenant.
- `tenant_isolation_tier` diferente de `bridge` deve falhar de forma explícita enquanto não houver suporte `silo`.

### Estrutura esperada

- Criar `services/automated-review` com pacote Python `creditos_automated_review`.
- Manter camadas:
  - `domain`: entidades, value objects, erros de domínio e regras puras.
  - `application`: comandos, serviços, portas e autorização por caso de uso.
  - `adapters`: repositório/auditoria in-memory para testes.
  - `bootstrap`: apenas placeholders/runtime mínimo se necessário.
  - `tests/unit`: testes de domínio e aplicação.
- Seguir padrões de `services/decision` e `services/integration`; não copiar lógica de decisão, apenas padrões de estrutura, contexto, logs, auditoria e in-memory adapters.
- Atualizar `pyproject.toml` raiz `extraPaths`/`pythonpath` somente se os testes exigirem import do novo pacote fora do workspace.

### Anti-patterns a evitar

- Não criar um “agent runner” real nesta story.
- Não chamar OpenAI, Anthropic, Bedrock, Vertex, Ollama, HTTP externo ou qualquer SDK de IA.
- Não armazenar prompt/payload sensível bruto em log, evento auditável, erro, fixture ou README.
- Não criar `metadata: dict[str, Any]` livre para configuração governada.
- Não permitir `can_approve`, `can_reject`, `can_change_terms`, `can_call_tools`, `can_call_external_services`, `can_publish_decision` ou equivalentes verdadeiros.
- Não transformar configuração de IA em política de crédito; política final continua em `Decision`.
- Não criar endpoint público ou contrato cross-service nesta story; contratos gRPC/eventos entram quando a integração com `Decision` for materializada.

### Testes esperados

- Executar testes focados do novo serviço:
  - `.venv/bin/pytest services/automated-review/tests/unit`
  - `.venv/bin/ruff format --check .`
  - `.venv/bin/ruff check .`
  - `.venv/bin/pyright`
- Se possível antes do PR, executar `.venv/bin/pytest`; se houver falha ambiental preexistente, registrar exatamente em `deferred-work.md`/Dev Agent Record.
- Testes devem provar imutabilidade de versão publicada, criação de nova versão, rejeição de capacidades autônomas, tenant isolation, auditoria antes de persistência crítica e logs sem prompt/payload sensível.

### Project Structure Notes

- O serviço `services/automated-review` ainda não existe; esta story deve criá-lo a partir do padrão de microsserviço DDD/hexagonal já usado no monorepo.
- O nome do pacote deve ser `creditos_automated_review`; evitar `ai_service`, `llm_service` ou nomes acoplados a tecnologia.
- Não mover código de `Decision`, `Integration` ou pacotes compartilhados para satisfazer esta story.
- O Jira deve refletir o avanço: `CTOS-47` está em `Em andamento`; subtarefas devem ser criadas antes da implementação e movidas conforme execução.

### Previous Story Intelligence

- Story 4.8 fechou gates de que IA, integração externa, provider payload ou resultado proprietário não podem ser decisores finais diretos.
- Story 4.7 reforçou resposta explicável customer-safe e audiência controlada; usar a mesma disciplina para prompts/configurações.
- Story 4.1 a 4.6 estabeleceram padrão de entidades imutáveis, versionamento, publicação controlada, auditoria antes de exposição, fallback sem fila manual e testes negativos cross-tenant.
- Stories 3.x estabeleceram que provedores externos de dados pertencem ao `Integration`; não misturar essa fronteira com provedores/modelos de IA.
- Falha ambiental recorrente: suíte completa pode falhar se `uv` não estiver no PATH em `scripts/dev`; registrar sem mascarar se reaparecer.

### Git Intelligence

- Baseline da branch: `6c6bf8b`, merge do PR #45.
- Commits recentes mantêm padrão de branch por story, story file BMAD, implementação cirúrgica, revisão adversarial antes de commit/push/draft PR e correções no mesmo PR quando houver review do GitHub.
- Commits deste projeto devem usar `Andre Tachian <altachian@gmail.com>`.

### Latest Technical Information

- Nenhuma pesquisa web é necessária nesta story porque não há seleção de fornecedor, modelo, SDK ou biblioteca nova.
- Se surgir necessidade de escolher provedor/modelo, SDK de IA, formato de prompt externo ou secret manager, pausar e propor alternativas, justificativa e consequências antes de implementar.

### References

- `_bmad-output/planning-artifacts/epics.md` — Epic 5 / Story 5.1 e FR-16/FR-17/FR-18.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — revisão automatizada consultiva, exclusões de marketplace/treinamento e riscos de IA fora de governança.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md` — `Automated Review Service` no MVP, IA consultiva e dados/modelos próprios como backlog final.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/multi-tenancy-oq6.md` — modelo `bridge` e isolamento por tenant.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-3, AD-5, AD-7, AD-8, AD-10 e AD-11.
- `docs/input/project-technical-premises.md` — uso de agentes de IA, rastreabilidade, segurança, privacidade e restrições para agentes.
- `docs/development.md` — fluxo local, CI e gates obrigatórios.
- `docs/microservice-template.md` — camadas obrigatórias e limites dos serviços.
- `services/service-template` — estrutura base de microsserviço.
- `services/decision` — padrões recentes de versionamento, publicação, auditoria, logs seguros, tenant isolation e testes.
- `services/integration` — padrões de serviço separado, adapters in-memory, portas e isolamento.

## Dev Agent Record

### Agent Model Used

GPT-5.1 Codex

### Debug Log References

- `.venv/bin/pytest services/automated-review/tests/unit/test_review_agent_configuration.py` — RED inicial falhou com `ModuleNotFoundError` antes da implementação.
- `.venv/bin/pytest services/automated-review/tests/unit/test_review_agent_configuration.py` — `7 passed`.
- `.venv/bin/pytest services/automated-review/tests/unit` — `7 passed`.
- `.venv/bin/ruff format --check .` — `246 files already formatted`.
- `.venv/bin/ruff check .` — `All checks passed!`.
- `.venv/bin/pyright` — `0 errors`.
- `.venv/bin/pytest` no sandbox — `544 passed, 3 failed` por restrição ambiental de socket e `uv` ausente.
- `timeout 120s .venv/bin/pytest` fora do sandbox — `546 passed, 1 failed`; falha única por `scripts/dev: line 47: uv: command not found`, registrada em `deferred-work.md`.
- `bmad-code-review` Step 02 — Blind Hunter, Edge Case Hunter e Acceptance Auditor executados; 1 decision-needed resolvido como `approval_reference`, 11 patches aplicados.
- `.venv/bin/pytest services/automated-review/tests/unit` após patches de revisão — `9 passed`.
- `.venv/bin/ruff format --check .` após patches de revisão — `246 files already formatted`.
- `.venv/bin/ruff check .` após patches de revisão — `All checks passed!`.
- `.venv/bin/pyright` após patches de revisão — `0 errors`.

### Completion Notes List

- Criado o `Automated Review Service` como bounded context separado, seguindo DDD e arquitetura hexagonal.
- Implementado agregado `ReviewAgentConfiguration` com draft, update rastreável, publicação controlada, imutabilidade de versão publicada e nova versão a partir de published.
- Implementados value objects governados para escopo, prompt, referência de modelo, guardrails e capacidades consultivas, bloqueando autonomia decisória e uso de ferramentas/integrações.
- Implementado application service com autorização por scopes, contexto confiável `bridge`, auditoria minimizada antes da persistência e logs estruturados sem payload/prompt sensível.
- Implementados ports e adapter in-memory com isolamento por tenant, rollback local em falha crítica de auditoria e consultas cross-tenant indistinguíveis de not found.
- Documentadas responsabilidades, limites e comandos locais em `services/automated-review/README.md`.
- Patches de code review aplicados: publicação exige `approval_reference`, owner vem do contexto confiável, conflitos de versão/revisão são bloqueados, contexto observável é validado contra o contexto confiável, fingerprint é verificado contra conteúdo, filtros por escopo foram adicionados e validações de privacidade foram endurecidas.

### File List

- `_bmad-output/implementation-artifacts/5-1-configuracao-versionada-de-agente-de-revisao.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `pyproject.toml`
- `uv.lock`
- `services/automated-review/README.md`
- `services/automated-review/pyproject.toml`
- `services/automated-review/src/creditos_automated_review/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/persistence/__init__.py`
- `services/automated-review/src/creditos_automated_review/adapters/persistence/in_memory_review_agent_config_repository.py`
- `services/automated-review/src/creditos_automated_review/application/__init__.py`
- `services/automated-review/src/creditos_automated_review/application/ports/__init__.py`
- `services/automated-review/src/creditos_automated_review/application/ports/audit_publisher.py`
- `services/automated-review/src/creditos_automated_review/application/ports/review_agent_config_repository.py`
- `services/automated-review/src/creditos_automated_review/application/service.py`
- `services/automated-review/src/creditos_automated_review/bootstrap/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/entities/review_agent_configuration.py`
- `services/automated-review/src/creditos_automated_review/domain/errors.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/__init__.py`
- `services/automated-review/src/creditos_automated_review/domain/value_objects/review_agent_config.py`
- `services/automated-review/tests/unit/test_review_agent_configuration.py`

## Change Log

- 2026-09-07 — Story 5.1 detalhada com branch inicial, contexto do Epic 5, fronteiras do `Automated Review Service` e guardrails de IA consultiva.
- 2026-09-07 — `bmad-dev-story` iniciado; `CTOS-280` movida para `Em andamento`.
- 2026-09-07 — Implementação concluída; subtarefas `CTOS-280` a `CTOS-286` concluídas e story movida para revisão.
- 2026-09-08 — `bmad-code-review` concluído; decisão por `approval_reference` aplicada e 11 patches de revisão resolvidos.
