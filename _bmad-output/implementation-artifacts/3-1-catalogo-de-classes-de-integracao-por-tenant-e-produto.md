---
jira_issue: CTOS-33
branch: agent/story-3-1-catalogo-classes-integracao
baseline_commit: bf0e261
---

# Story 3.1: Catálogo de Classes de Integração por Tenant e Produto

Status: review

## Story

Como gestor autorizado,
quero configurar classes de integração permitidas por tenant, produto e política,
para que cada análise use apenas fontes autorizadas, governadas e rastreáveis.

## Acceptance Criteria

1. **Configuração governada de classe de integração**
   - **Given** um tenant confiável e um produto MVP
   - **When** uma classe de integração é configurada
   - **Then** a configuração registra classe, obrigatoriedade, adapter, limites, timeout e fallback
   - **And** a alteração gera evento auditável minimizado.

2. **Plano controlado para integração obrigatória ausente**
   - **Given** uma proposta exige integração obrigatória não configurada
   - **When** o fluxo tenta montar o plano de integração
   - **Then** retorna estado controlado de configuração ausente
   - **And** não executa fornecedor, adapter externo, mock ou sandbox indevido.

3. **Isolamento por tenant e produto**
   - **Given** configurações de dois tenants ou produtos distintos
   - **When** o catálogo é consultado ou atualizado
   - **Then** cada operação usa somente `tenant_id` confiável do contexto autenticado
   - **And** não aceita `tenant_id` vindo de payload de negócio como autoridade.

4. **Classes MVP e adapters substituíveis**
   - **Given** classes de integração MVP
   - **When** o catálogo valida uma configuração
   - **Then** aceita apenas classes governadas e adapters registrados
   - **And** não depende de nomes, payloads, códigos ou semântica proprietária de fornecedor real.

5. **Limites, timeout, fallback e custo planejável**
   - **Given** uma configuração ativa
   - **When** ela é usada para montar o plano
   - **Then** inclui limites mínimos, deadline/timeout, estratégia de fallback e metadados para custo estimado
   - **And** rejeita valores inseguros ou ilimitados.

6. **Observabilidade e segurança operacional**
   - **Given** criação, atualização, consulta e falha de plano
   - **When** logs estruturados forem inspecionados
   - **Then** há rastreabilidade por tenant, produto, classe, adapter, operação e correlação
   - **And** não há CPF, CNPJ, e-mail completo, payload bruto, token, secret, credencial ou resposta externa.

## Tasks / Subtasks

- [x] CTOS-33 — Detalhar e implementar catálogo de classes de integração por tenant e produto (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-171 — Criar o microsserviço `integration` a partir do padrão DDD/hexagonal existente. (AC: 1, 3, 4)
  - [x] CTOS-172 — Modelar entidades/value objects do catálogo: classe, adapter, produto, obrigatoriedade, limites, timeout, fallback e custo planejado. (AC: 1, 4, 5)
  - [x] CTOS-173 — Criar portas de aplicação para repositório do catálogo, registro de adapters e emissão de evento auditável. (AC: 1, 2, 4)
  - [x] CTOS-174 — Implementar adapter in-memory transacional para testes, sem banco real/migration nesta story. (AC: 1, 2, 3)
  - [x] CTOS-175 — Implementar casos de uso para criar/atualizar configuração e montar plano de integração. (AC: 1, 2, 5)
  - [x] CTOS-176 — Garantir isolamento por tenant confiável e rejeição de tenant/payload arbitrário. (AC: 3, 6)
  - [x] CTOS-177 — Adicionar logs estruturados minimizados e eventos auditáveis de configuração. (AC: 1, 6)
  - [x] CTOS-178 — Criar testes unitários e de aplicação para sucesso, ausências, limites inválidos, cross-tenant e não execução de adapter. (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-179 — Atualizar `pyproject.toml`, documentação do serviço e sprint/Jira conforme avanço. (AC: 6)

### Review Follow-ups (AI)

- [x] Garantir rollback da configuração quando a publicação auditável falhar antes da aceitação. (AC: 1, 6)
- [x] Tornar a configuração única por tenant, produto e classe, preservando `created_at` em atualização. (AC: 1, 3)
- [x] Rejeitar plano obrigatório quando a configuração ativa for opcional ou usar `skip_optional`. (AC: 2, 5)
- [x] Tornar `invalid_configuration` alcançável quando adapter previamente configurado deixar de ser governado. (AC: 2, 4, 5)
- [x] Rejeitar limites numéricos com tipos inseguros, incluindo `bool`, `str` e `float`. (AC: 5)
- [x] Reforçar tenant confiável com padrão seguro e tier `bridge` explícito nesta story. (AC: 3, 6)
- [x] Exigir escopo `integration_catalog:write` para configuração por gestor autorizado. (AC: 1, 3)
- [x] Remover `list_all` da porta de aplicação e manter listagem governada por tenant/produto. (AC: 3, 6)
- [x] Incluir `creditos-integration` no `uv.lock` para manter o workspace reproduzível. (AC: 6)

## Dev Notes

### Escopo desta story

- Esta story inaugura o `Integration Service` e entrega o catálogo governado de classes/adapters por tenant e produto.
- Ela **não** deve implementar chamada real a fornecedor externo, NATS JetStream real, fan-out/fan-in real, retry/DLQ real, adapter mock completo, banco real, migration, gRPC real ou custo real por fornecedor.
- O resultado esperado é uma base de domínio/aplicação testável para as próximas stories: 3.2 (`Adapter Mock/Sandbox`), 3.3 (`Fan-out/Fan-in`), 3.4 (`Retry/DLQ`), 3.5 (`Custo/Resultado`) e 3.6 (`Contratos/Gates`).

### Regras arquiteturais obrigatórias

- Todo backend segue DDD + arquitetura hexagonal; domínio não importa FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry ou SDK externo.
- `Integration` é o único bounded context autorizado a falar com provedores externos de dados, webhooks/callbacks e APIs de terceiros usadas como integração ou notificação.
- Provedores/modelos de IA pertencem ao `Automated Review`, não ao `Integration`.
- O MVP define **classes de integração e adapters substituíveis**, não fornecedores nominais.
- `Decision` e demais domínios não podem depender de payloads, erros, nomes, códigos ou semântica proprietária de fornecedor.
- Integrações externas futuras executam de forma assíncrona via NATS JetStream; nesta story, apenas preparar o modelo e os contratos internos necessários para isso.
- Chamadas síncronas internas futuras usam gRPC; nesta story, não criar interface gRPC se não for necessária para cumprir os ACs.

### Classes MVP permitidas

Usar enum/constantes explícitas para as classes MVP, evitando string livre:

- `kyc_kyb`: cadastro, validação documental, KYC e KYB.
- `credit_bureau`: bureau de crédito, restritivos e indicadores financeiros.
- `anti_fraud`: antifraude e contexto digital.
- `receivables`: recebíveis, lastro e elegibilidade.
- `open_finance`: Open Finance ou fonte financeira autorizada equivalente.
- `webhook_callback`: webhooks/callbacks e notificações.

### Produtos MVP

O catálogo deve aceitar somente os produtos já definidos no contrato canônico de proposta:

- `personal_credit`
- `bnpl`
- `business_credit`
- `receivables`

### Campos mínimos da configuração

Cada configuração ativa deve conter, no mínimo:

- `tenant_id` confiável vindo de `ObservabilityContext` ou contexto autenticado equivalente.
- `product_type`.
- `integration_class`.
- `adapter_id` governado, sem fornecedor nominal obrigatório.
- `requirement`: `required`, `optional` ou `conditional`.
- `timeout_ms` positivo e limitado.
- `max_attempts` positivo e limitado, mesmo que retry real fique para Story 3.4.
- `max_concurrency` positivo e limitado, mesmo que fan-out real fique para Story 3.3.
- `estimated_cost_units` ou campo equivalente para custo planejável, sem moeda/fornecedor real obrigatório.
- `fallback_strategy`: `fail_closed`, `allow_partial`, `skip_optional` ou equivalente explícito.
- `enabled`, `schema_version`, `created_at`, `updated_at` e identificador técnico da configuração.

### Estados controlados de plano

Ao montar plano de integração, o caso de uso deve retornar estados explícitos, por exemplo:

- `ready`: todas as integrações obrigatórias aplicáveis estão configuradas.
- `missing_required_configuration`: há integração obrigatória sem configuração ativa.
- `no_applicable_integrations`: não há integração aplicável ao produto/política informada.
- `invalid_configuration`: a configuração existe, mas possui valor inseguro, inválido ou incompatível.

O estado `missing_required_configuration` não pode disparar adapter, mock, sandbox ou chamada externa.

### Auditoria e logs

- A alteração de configuração deve gerar evento auditável minimizado via porta de aplicação, sem implementar o `Audit & Evidence Service`.
- O evento auditável deve conter `tenant_id`, operação, classe, produto, adapter, resultado, correlation ID, trace ID, versão e timestamp UTC.
- Logs estruturados devem usar `creditos-observability` e não podem conter payload bruto, token, secret, credencial, CPF, CNPJ, e-mail completo ou resposta externa.
- `tenant_id` em métrica técnica deve ser evitado como label livre; observabilidade por tenant pertence preferencialmente a projeções de negócio.

### Estrutura esperada de arquivos

Criar seguindo o padrão dos serviços existentes:

- `services/integration/pyproject.toml`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/domain/...`
- `services/integration/src/creditos_integration/application/...`
- `services/integration/src/creditos_integration/application/ports/...`
- `services/integration/src/creditos_integration/adapters/persistence/...`
- `services/integration/src/creditos_integration/adapters/logging/...` se necessário
- `services/integration/bootstrap/...` somente se houver padrão mínimo útil
- `services/integration/tests/unit/...`
- `services/integration/tests/integration/...` somente se necessário para ACs

Não colocar regras de domínio em `packages/`. Pacotes compartilhados continuam limitados a contratos, observabilidade, segurança, testes ou utilidades técnicas genéricas.

### Padrões existentes para reutilizar

- `services/service-template` define a estrutura base de microsserviço DDD/hexagonal.
- `services/identity-tenant` mostra uso de repositórios in-memory, casos de uso, contexto confiável e logs de operação.
- `services/proposal-intake` mostra idempotência, isolamento por tenant, outbox in-memory, erros seguros e testes negativos.
- `packages/security` fornece propagação segura de contexto gRPC/CloudEvents e rejeição de atributos sensíveis.
- `packages/observability` fornece `ObservabilityContext`, logs estruturados, health/readiness e helpers de telemetria.

### Anti-padrões proibidos

- Não escolher fornecedor real nesta story.
- Não criar payload livre como `raw_payload`, `payload`, `metadata`, `attributes`, `custom` ou equivalente para configuração.
- Não aceitar `tenant_id` vindo do body como autoridade.
- Não persistir resposta externa ou credencial em fixture, log ou evento.
- Não criar integração direta do `Decision` com fornecedor externo.
- Não implementar fan-out/fan-in, retry/DLQ ou mock completo antes das stories específicas.
- Não adicionar dependência externa sem justificativa, alternativa e consequência.

### Latest Technical Information

- NATS JetStream consumers são stateful, rastreiam entregas/acks e suportam garantia at-least-once; `MaxAckPending`, `MaxDeliver` e `BackOff` são relevantes para as stories 3.3/3.4, mas esta story deve apenas preparar limites configuráveis. Fonte: https://docs.nats.io/nats-concepts/jetstream/consumers
- NATS documenta comportamento de ack/redelivery e advisory de máximo de entregas para cenários tipo DLQ; manter isso como contexto futuro, sem implementar DLQ nesta story. Fonte: https://docs.nats.io/using-nats/developer/develop_jetstream/consumers
- AsyncAPI 3.1.0 é a baseline atual do projeto para contratos assíncronos; documentos descrevem operações, channels, messages e componentes em formato JSON/YAML. Fonte: https://www.asyncapi.com/docs/reference/specification/v3.1.0
- CloudEvents mantém release estável v1.0.2 para core e NATS binding; eventos futuros devem continuar com `specversion: "1.0"`. Fonte: https://github.com/cloudevents/spec
- OWASP API10:2023 reforça que APIs externas/terceiros não devem ser confiados sem validação de transporte, autenticação/autorização, sanitização e contrato. Fonte: https://owasp.org/API-Security/editions/2023/en/0xaa-unsafe-consumption-of-apis/

### Testing Requirements

- Testes focados do novo serviço: `.venv/bin/python -m pytest services/integration/tests -q`.
- Regressão de fronteira DDD: domínio do `Integration` não deve importar frameworks/adapters externos.
- Qualidade: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright`.
- Suíte antes de PR: `.venv/bin/python -m pytest -q`; se o harness local falhar por sandbox/`uv`, repetir fora do sandbox com `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q`.

### Checklist de criação da story

- [x] Epic 3 e Story 3.1 analisados.
- [x] PRD de integrações externas, eventos/mensageria, multi-tenancy e observabilidade consultados.
- [x] Architecture Spine AD-4, AD-5, AD-6, AD-7 e AD-10 incorporados.
- [x] Padrões dos serviços `identity-tenant`, `proposal-intake` e `service-template` considerados.
- [x] Limites de escopo definidos para não antecipar Stories 3.2 a 3.6.
- [x] Pesquisa técnica atual registrada com fontes oficiais/primárias.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 3, Story 3.1 e sequência das Stories 3.2 a 3.6.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-4, AD-5, AD-6, AD-7 e AD-10.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/integracoes-externas-oq8.md` — classes prioritárias, custos e critérios futuros de fornecedor.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md` — gRPC/NATS, CloudEvents, AsyncAPI, outbox/inbox e DLQ futura.
- `docs/observability.md` — logs estruturados, mascaramento e OpenTelemetry.
- `docs/contracts.md` — localização e política dos contratos versionados.
- `services/service-template` — estrutura base de microsserviço.
- `services/identity-tenant` — padrões de contexto confiável, autorização e repositório in-memory.
- `services/proposal-intake` — padrões de validação, idempotência, outbox e testes negativos.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- 2026-08-17 — `bmad-dev-story` iniciado para a Story 3.1.
- `.venv/bin/python -m pytest services/integration/tests -q` — primeiro ciclo vermelho por módulo `creditos_integration` inexistente.
- `.venv/bin/python -m pytest services/integration/tests -q` — 17 passed após implementação.
- `PATH=/tmp/creditos-uv-shim:$PATH uv lock --check` — passed.
- `.venv/bin/python scripts/check_contracts.py` — `contracts check passed: 4 contracts`.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — passed após formatar arquivos do novo serviço.
- `.venv/bin/pyright` — 0 errors.
- `.venv/bin/python -m pytest -q` — falhou no sandbox apenas por `tests/test_local_harness.py` exigir socket local e `uv` no PATH.
- `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q` fora do sandbox — 303 passed.
- 2026-08-17 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor.
- `.venv/bin/python -m pytest services/integration/tests -q` — 39 passed após correções de revisão.
- `PATH=/tmp/creditos-uv-shim:$PATH uv lock --check` — passed após incluir `creditos-integration`.
- `.venv/bin/python scripts/check_contracts.py` — `contracts check passed: 4 contracts`.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — `171 files already formatted`.
- `.venv/bin/pyright` — 0 errors.
- `.venv/bin/python -m pytest -q` — falhou no sandbox apenas por `tests/test_local_harness.py` exigir socket local e `uv` no PATH.
- `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q` fora do sandbox — 325 passed.

### Implementation Plan

- Inaugurar `services/integration` reutilizando o template DDD/hexagonal e padrões de serviços anteriores.
- Concentrar regras de classe/produto/limites/fallback em value objects do domínio, sem payload livre.
- Expor casos de uso de configuração e montagem de plano por application service, com tenant confiável vindo do contexto.
- Usar portas para repositório, registry de adapters e auditoria, mantendo adapters in-memory somente para testes.
- Cobrir segurança, logs minimizados, isolamento cross-tenant e não execução de adapter quando configuração obrigatória estiver ausente.

### Completion Notes List

- Story criada por `bmad-create-story` para preparar implementação da primeira story do Epic 3.
- Jira `CTOS-11` e `CTOS-33` movidos para `Em andamento` antes da implementação.
- A sincronização de `origin/main` local precisa ser refeita antes do PR porque o sandbox bloqueou `git fetch origin main`.
- Story movida para `in-progress` no início do `bmad-dev-story`.
- Criado o `Integration Service` com domínio, application service, portas e adapters in-memory.
- Implementado catálogo por tenant/produto com classes MVP, adapter registry, limites, timeout, fallback e custo planejável.
- Implementada montagem de plano com estados `ready`, `missing_required_configuration` e `no_applicable_integrations`, sem executar adapter nesta story.
- Adicionados logs estruturados minimizados e evento auditável de configuração via porta.
- Adicionados testes de sucesso, configuração obrigatória ausente, cross-tenant, tenant confiável ausente, limites inválidos, logs seguros e fronteira DDD.
- Correções de revisão aplicadas: rollback auditável, unicidade por tenant/produto/classe, atualização com preservação de `created_at`, estado `invalid_configuration`, autorização por escopo, validação forte de tipos e consulta governada.
- `uv.lock` atualizado manualmente porque o shim local de `uv` não suporta geração de lock, apenas validação.

### Change Log

- 2026-08-17 — Story 3.1 implementada; `Integration Service` criado e status movido para `review`.
- 2026-08-17 — Achados de revisão adversarial aplicados; suíte do serviço ampliada para 39 testes e regressão completa validada com 325 testes.

### File List

- `_bmad-output/implementation-artifacts/3-1-catalogo-de-classes-de-integracao-por-tenant-e-produto.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `pyproject.toml`
- `uv.lock`
- `services/integration/README.md`
- `services/integration/pyproject.toml`
- `services/integration/src/creditos_integration/__init__.py`
- `services/integration/src/creditos_integration/adapters/__init__.py`
- `services/integration/src/creditos_integration/adapters/api/__init__.py`
- `services/integration/src/creditos_integration/adapters/events/__init__.py`
- `services/integration/src/creditos_integration/adapters/external/__init__.py`
- `services/integration/src/creditos_integration/adapters/grpc/__init__.py`
- `services/integration/src/creditos_integration/adapters/logging/__init__.py`
- `services/integration/src/creditos_integration/adapters/persistence/__init__.py`
- `services/integration/src/creditos_integration/adapters/persistence/in_memory_integration_catalog_repository.py`
- `services/integration/src/creditos_integration/application/__init__.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/application/ports/adapter_registry.py`
- `services/integration/src/creditos_integration/application/ports/audit_event_publisher.py`
- `services/integration/src/creditos_integration/application/ports/catalog_repository.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/application/use_cases/__init__.py`
- `services/integration/src/creditos_integration/bootstrap/__init__.py`
- `services/integration/src/creditos_integration/domain/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/integration_configuration.py`
- `services/integration/src/creditos_integration/domain/entities/integration_plan.py`
- `services/integration/src/creditos_integration/domain/errors.py`
- `services/integration/src/creditos_integration/domain/events/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/catalog.py`
- `services/integration/tests/unit/test_integration_catalog.py`
- `services/integration/tests/unit/test_integration_domain_boundaries.py`
