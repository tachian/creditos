---
jira_issue: CTOS-34
branch: agent/story-3-2-adapter-mock-sandbox-integracoes-externas
baseline_commit: 6f81372
---

# Story 3.2: Adapter Mock/Sandbox para Integrações Externas

Status: done

## Story

Como equipe de engenharia,
quero adapters mock/sandbox para classes de integração MVP,
para que o fluxo possa ser testado sem depender de fornecedores reais.

## Acceptance Criteria

1. **Execução mock/sandbox em ambiente não produtivo**
   - **Given** um ambiente não produtivo e um plano de integração `ready`
   - **When** o plano solicita `kyc_kyb`, `credit_bureau`, `anti_fraud` ou `receivables`
   - **Then** o `Integration Service` usa apenas adapter mock/sandbox previamente registrado para a classe
   - **And** retorna resultado canônico versionado, sem chamada externa real.

2. **Resultados determinísticos com dados sintéticos**
   - **Given** dados de teste sintéticos e um cenário mock configurado
   - **When** o adapter processa a requisição
   - **Then** produz resposta determinística para a mesma entrada canônica
   - **And** permite cenários configuráveis de sucesso, falha controlada, ausência de dado e resultado parcial.

3. **Contrato canônico independente de fornecedor**
   - **Given** um resultado produzido por mock/sandbox
   - **When** o resultado é entregue à aplicação
   - **Then** contém somente campos canônicos versionados, status, reason codes seguros, classe, adapter, timestamps e referência de correlação
   - **And** não contém nomes, códigos, payloads, erros ou semântica proprietária de fornecedor real.

4. **Segurança, privacidade e dados sensíveis**
   - **Given** entrada sintética ou cenário configurável
   - **When** logs, eventos auditáveis ou resultados são inspecionados
   - **Then** não há CPF, CNPJ, e-mail completo, nome real, token, secret, credencial, payload bruto ou resposta externa bruta
   - **And** os testes usam somente dados sintéticos e identificadores técnicos.

5. **Governança por tenant, produto, classe e adapter**
   - **Given** configurações de tenants, produtos e classes distintos
   - **When** o mock/sandbox é executado
   - **Then** usa somente `tenant_id` confiável do `ObservabilityContext`
   - **And** rejeita plano/configuração de outro tenant, adapter não registrado, classe fora do MVP ou ambiente produtivo.

6. **Observabilidade operacional mínima**
   - **Given** execução aceita, falha controlada ou rejeição do adapter mock/sandbox
   - **When** logs estruturados são gerados
   - **Then** há rastreabilidade por operação, tenant, produto, classe, adapter, scenario, status, correlation ID, trace ID e duração
   - **And** labels ou campos extras não usam payload bruto nem identificadores livres de alta cardinalidade.

## Tasks / Subtasks

- [x] CTOS-34 — Detalhar e implementar adapter mock/sandbox para integrações externas (AC: 1, 2, 3, 4, 5, 6)
  - [x] CTOS-180 — Criar modelo canônico de resultado de integração no domínio, sem payload livre ou fornecedor nominal. (AC: 1, 3, 4)
  - [x] CTOS-181 — Criar value objects/enums para status de resultado, cenário mock, reason codes seguros e tipo de dado sintético. (AC: 2, 3, 4)
  - [x] CTOS-182 — Criar porta de execução de adapter mock/sandbox e registry específico para execução, sem substituir o `AdapterRegistry` do catálogo. (AC: 1, 5)
  - [x] CTOS-183 — Implementar adapters in-memory determinísticos para `kyc_kyb`, `credit_bureau`, `anti_fraud` e `receivables`. (AC: 1, 2)
  - [x] CTOS-184 — Implementar caso de uso de execução mock/sandbox a partir de `IntegrationPlan`, respeitando tenant confiável, produto, classe, adapter e ambiente. (AC: 1, 5, 6)
  - [x] CTOS-185 — Impedir execução em `prod`/ambiente produtivo e rejeitar adapter não registrado ou plano não `ready`. (AC: 1, 5)
  - [x] CTOS-186 — Adicionar logs estruturados minimizados para execução aceita, falha controlada e rejeição. (AC: 4, 6)
  - [x] CTOS-187 — Adicionar testes unitários para determinismo, cenários configuráveis, segurança de logs, cross-tenant, ambiente produtivo e não chamada externa. (AC: 1, 2, 4, 5, 6)
  - [x] CTOS-188 — Atualizar exports, README do serviço e story/sprint conforme avanço. (AC: 3, 6)

### Review Findings

- [x] [Review][Patch] Validar tenant e produto de cada item antes da execução mock [services/integration/src/creditos_integration/application/service.py:330]
- [x] [Review][Patch] Fazer preflight completo antes de qualquer `adapter.execute` [services/integration/src/creditos_integration/application/service.py:357]
- [x] [Review][Patch] Rejeitar `scenario_by_class` com classes desconhecidas ou fora do plano [services/integration/src/creditos_integration/application/service.py:355]
- [x] [Review][Patch] Validar `synthetic_subject_reference` como referência técnica sintética, sem CPF, CNPJ, e-mail, token ou secret [services/integration/src/creditos_integration/application/service.py:79]
- [x] [Review][Patch] Tornar bloqueio de produção mais seguro para aliases como `prd`, `prod-*` e `production-*` [services/integration/src/creditos_integration/application/service.py:597]
- [x] [Review][Patch] Incluir produto, classes, adapters e cenários nos logs de rejeição [services/integration/src/creditos_integration/application/service.py:409]
- [x] [Review][Patch] Validar resultado retornado pelo adapter contra tenant confiável, produto, classe, adapter, cenário e schema [services/integration/src/creditos_integration/application/service.py:377]
- [x] [Review][Patch] Fechar vocabulário de `reason_codes` e valores do `summary` para impedir semântica proprietária [services/integration/src/creditos_integration/domain/value_objects/result.py:117]
- [x] [Review][Patch] Medir `duration_ms` real por resultado em vez de fixar `0.0` [services/integration/src/creditos_integration/application/service.py:375]

## Dev Notes

### Escopo desta story

- Esta story materializa somente **adapters mock/sandbox locais e determinísticos** para permitir testes sem fornecedor real.
- Ela deve reutilizar o catálogo criado na Story 3.1: `IntegrationCatalogApplicationService`, `IntegrationPlan`, `IntegrationPlanItem`, classes MVP e `AdapterRegistry`.
- Ela **não** deve implementar NATS JetStream real, comando `integration.execute`, fan-out/fan-in real, retry, DLQ, replay, contrato AsyncAPI final, banco real, migration, gRPC real, custo real de fornecedor ou integração com API externa.
- Ela **não** deve escolher fornecedores reais nem modelar payload proprietário. O adapter mock é um anti-corruption layer de teste, não uma simulação de fornecedor nominal.
- A execução mock/sandbox deve ser uma base para as próximas stories:
  - 3.3: execução assíncrona com fan-out/fan-in.
  - 3.4: retry, DLQ e reprocessamento.
  - 3.5: custo e resultado de integração.
  - 3.6: contratos e gates de integração.

### Estado atual que deve ser preservado

- `services/integration/src/creditos_integration/application/service.py` já implementa configuração, listagem governada e montagem de plano.
- `IntegrationPlan` possui status `ready`, `missing_required_configuration`, `no_applicable_integrations` e `invalid_configuration`.
- `IntegrationPlanItem` já carrega `tenant_id`, `product_type`, `integration_class`, `adapter_id`, `requirement`, `timeout_ms`, `max_attempts`, `max_concurrency`, `estimated_cost_units`, `fallback_strategy` e `configuration_id`.
- `configure_integration_class` exige `tenant_id` confiável, `tenant_isolation_tier="bridge"` e escopo `integration_catalog:write`.
- O domínio do `Integration` já possui teste de fronteira impedindo imports de FastAPI, Pydantic, SQLAlchemy, Alembic, gRPC, NATS, OpenTelemetry, requests e httpx.
- O repositório in-memory ainda mantém `list_all()` apenas como helper concreto de teste; a porta de aplicação não expõe listagem global.

### Regras arquiteturais obrigatórias

- Todo backend segue DDD + arquitetura hexagonal; domínio não importa frameworks, transporte, banco, observabilidade, SDK externo ou NATS.
- O domínio deve conter tipos canônicos e invariantes do resultado; execução técnica do mock/sandbox deve ficar em `application` + `adapters/external` ou `adapters/persistence` conforme responsabilidade.
- `Integration` é o único bounded context autorizado a encapsular integrações externas; `Decision` não deve conhecer payloads de fornecedor.
- Mocks/sandboxes são obrigatórios para homologação futura de adapters, mas nesta story são locais e sem credenciais.
- Ambientes produtivos devem rejeitar execução de mock/sandbox por padrão com erro seguro e log minimizado.
- O modelo MVP usa multi-tenancy `bridge`; toda execução deve usar `tenant_id` confiável do contexto e nunca aceitar tenant vindo do payload de negócio.
- Logs estruturados devem usar `creditos-observability` e omitir payload bruto por padrão.
- Testes devem usar dados sintéticos e não devem introduzir CPF, CNPJ, e-mail, nome, endereço, token, secret, credencial ou resposta externa real.

### Classes MVP cobertas nesta story

Implementar adapters mock/sandbox para:

- `kyc_kyb`: resultado canônico de validação cadastral/documental sintética.
- `credit_bureau`: resultado canônico de bureau sintético, sem score real proprietário.
- `anti_fraud`: resultado canônico de antifraude sintético, sem fingerprint real.
- `receivables`: resultado canônico de recebíveis/lastro sintético.

Não implementar nesta story:

- `open_finance`: depende de consentimento/parceiro e permanece fora do mock obrigatório inicial.
- `webhook_callback`: pertence à jornada de callbacks/webhooks e deve ficar para histórias específicas.

### Resultado canônico sugerido

Criar uma entidade/value object de domínio, por exemplo `IntegrationResult`, com campos explícitos:

- `result_id`: identificador técnico determinístico ou gerado por factory, prefixo seguro como `ires_`.
- `tenant_id`: vindo do contexto confiável.
- `product_type`: produto MVP validado.
- `integration_class`: classe MVP validada.
- `adapter_id`: adapter governado e registrado.
- `status`: enum controlado, por exemplo `completed`, `partial`, `not_found`, `failed`.
- `scenario`: enum controlado, por exemplo `synthetic_success`, `synthetic_partial`, `synthetic_not_found`, `synthetic_failure`.
- `schema_version`: começar com `1.0`.
- `reason_codes`: tupla de códigos seguros, não proprietários, como `synthetic_identity_match`, `synthetic_bureau_clear`, `synthetic_fraud_signal_low`.
- `summary`: estrutura canônica minimizada com buckets/flags seguros; não criar `raw_payload`, `payload`, `metadata`, `attributes`, `custom` ou campos livres equivalentes.
- `correlation_id`, `trace_id`.
- `started_at`, `completed_at`, `duration_ms`.

O `summary` deve ser tipado com chaves allowlist por classe. Exemplo de chaves seguras:

- `kyc_kyb`: `document_status`, `registration_status`, `pep_flag`, `sanctions_flag`.
- `credit_bureau`: `bureau_status`, `risk_band`, `restriction_flag`, `income_evidence_band`.
- `anti_fraud`: `fraud_status`, `device_risk_band`, `velocity_risk_band`, `email_reputation_band`.
- `receivables`: `receivables_status`, `eligibility_band`, `concentration_band`, `payer_risk_band`.

### Comandos/casos de uso sugeridos

Criar casos de uso na aplicação, por exemplo:

- `ExecuteMockIntegrationCommand`
  - `plan`: `IntegrationPlan`.
  - `scenario_by_class`: mapeamento opcional de classe para cenário controlado.
  - `synthetic_subject_reference`: referência técnica sintética opcional, nunca CPF/CNPJ/e-mail.
  - `scopes`: deve exigir escopo de execução, por exemplo `integration_mock:execute`.
- `execute_mock_integration_plan(command, context=...)`
  - Rejeita se `environment` for `prod`, `production` ou equivalente.
  - Rejeita se `plan.status != "ready"`.
  - Rejeita se `plan.tenant_id` divergir do tenant confiável do contexto.
  - Executa apenas itens do plano com classes cobertas por esta story.
  - Retorna coleção imutável de `IntegrationResult`.
  - Loga execução aceita/rejeitada sem payload bruto.

Não acoplar esse caso de uso a NATS, worker ou fila. A 3.3 deve usar esta base para execução assíncrona.

### Portas e adapters sugeridos

Criar portas em `services/integration/src/creditos_integration/application/ports/`:

- `MockIntegrationAdapter`: protocolo para executar uma classe/adapter mock.
- `MockIntegrationAdapterRegistry`: protocolo para resolver adapter por classe e `adapter_id`.

Criar implementação em `services/integration/src/creditos_integration/adapters/external/`, por exemplo:

- `in_memory_mock_integration_adapter.py`
- `mock_integration_registry.py`

O adapter deve ser determinístico:

- mesma entrada canônica + mesma classe + mesmo adapter + mesmo cenário → mesmo status, reason codes e summary;
- timestamps podem vir de clock injetado para testes;
- não usar `random`, rede, arquivo externo, secrets, relógio global sem injeção quando afetar teste determinístico.

### Anti-padrões proibidos

- Não usar `requests`, `httpx`, SDK de fornecedor, rede, arquivo externo ou segredo.
- Não criar payload livre: `raw_payload`, `payload`, `metadata`, `attributes`, `custom`, `provider_response`, `external_response`.
- Não logar ou persistir resposta externa bruta, mesmo sintética.
- Não aceitar `tenant_id` no comando/payload como autoridade.
- Não executar mock/sandbox se o plano estiver ausente, inválido, sem item ou com status diferente de `ready`.
- Não executar `open_finance` ou `webhook_callback` nesta story.
- Não alterar contratos públicos de proposta.
- Não criar nova dependência externa sem justificativa, alternativas e consequência.
- Não implementar fan-out/fan-in, retry, DLQ, NATS real ou AsyncAPI final nesta story.

### Arquivos esperados

Prováveis arquivos novos:

- `services/integration/src/creditos_integration/domain/entities/integration_result.py`
- `services/integration/src/creditos_integration/domain/value_objects/result.py`
- `services/integration/src/creditos_integration/application/ports/mock_integration_adapter.py`
- `services/integration/src/creditos_integration/adapters/external/in_memory_mock_integration_adapter.py`
- `services/integration/tests/unit/test_mock_integration_adapters.py`

Prováveis arquivos a atualizar:

- `services/integration/src/creditos_integration/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/__init__.py`
- `services/integration/src/creditos_integration/application/__init__.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/adapters/external/__init__.py`
- `services/integration/README.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Esta story file.

Evitar mudanças em `packages/contracts` nesta story, salvo se a implementação comprovar necessidade mínima de schema interno experimental. Contratos AsyncAPI finais pertencem à Story 3.6.

### Testes obrigatórios

Adicionar/atualizar testes para:

- Execução mock/sandbox retorna resultados canônicos versionados para `kyc_kyb`, `credit_bureau`, `anti_fraud` e `receivables`.
- Mesma entrada sintética e mesmo cenário retornam resultado determinístico.
- Cenários `synthetic_success`, `synthetic_partial`, `synthetic_not_found` e `synthetic_failure` produzem status controlados.
- Ambiente produtivo rejeita execução mock/sandbox e não gera resultado aceito.
- Plano `missing_required_configuration`, `invalid_configuration` ou sem itens não executa adapter.
- Cross-tenant entre `plan.tenant_id` e contexto confiável é rejeitado.
- Adapter não registrado ou classe não coberta é rejeitado com erro seguro.
- Logs e resultados não contêm CPF, CNPJ, e-mail completo, nome real, token, secret, credencial, `raw_payload`, `payload_bruto`, `provider_response` ou resposta externa.
- Domínio continua sem imports de infraestrutura; manter e ampliar teste `test_integration_domain_has_no_infrastructure_imports` se necessário.

Comandos de validação esperados:

- `.venv/bin/python -m pytest services/integration/tests -q`
- `PATH=/tmp/creditos-uv-shim:$PATH uv lock --check`
- `.venv/bin/python scripts/check_contracts.py`
- `.venv/bin/ruff check .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/pyright`
- Antes do PR: `PATH=/tmp/creditos-uv-shim:$PATH .venv/bin/python -m pytest -q` fora do sandbox se o harness local exigir socket/`uv`.

### Previous Story Intelligence

Da Story 3.1:

- O catálogo já impõe unicidade por tenant/produto/classe; trocar adapter para mesma classe atualiza configuração e preserva `created_at`.
- A auditoria de configuração possui rollback se a publicação auditável falhar.
- O estado `invalid_configuration` já cobre adapter removido do registry e configuração incompatível com classe obrigatória.
- O uso de `list_all()` deve continuar restrito a testes concretos, nunca à porta de aplicação.
- O `Integration Service` usa `build_structured_log`; payloads são omitidos por padrão.
- A suíte focada do serviço passou com 39 testes após revisão adversarial; a regressão completa passou com 325 testes fora do sandbox.
- Houve achados adversariais sobre segurança e determinismo; nesta story, escrever testes negativos antes de marcar tarefas como concluídas.

### Git Intelligence

- Branch base: `6f81372`, merge do PR #32 da Story 3.1.
- Commits recentes da 3.1 incluem correções de revisão em sequência antes do merge; trate guardrails de revisão como requisitos de primeira classe, não como ajustes opcionais.
- O projeto usa commit/PR por story implementada; esta story já possui branch inicial publicada: `agent/story-3-2-adapter-mock-sandbox-integracoes-externas`.
- Autor local obrigatório: `Andre Tachian <altachian@gmail.com>`.

### Latest Technical Information

- CloudEvents permanece com release estável v1.0.2; eventos futuros devem continuar usando `specversion: "1.0"` e extensões compatíveis, mas esta story não deve publicar eventos reais. Fonte oficial: https://github.com/cloudevents/spec
- AsyncAPI 3.1.0 é a baseline arquitetural atual; contratos assíncronos finais pertencem à Story 3.6, não à 3.2. Fonte oficial: https://www.asyncapi.com/docs/reference/specification/v3.1.0
- NATS JetStream consumers controlam entrega/ack, `MaxAckPending`, `MaxDeliver` e `BackOff`; isso informa as Stories 3.3/3.4, mas a 3.2 não deve implementar broker real. Fonte oficial: https://docs.nats.io/nats-concepts/jetstream/consumers
- OWASP API10:2023 reforça que integrações externas/terceiros são não confiáveis e exigem validação, sanitização, autenticação/autorização e contrato; mesmo mocks devem manter fronteira anti-corruption e não normalizar padrões inseguros. Fonte oficial: https://owasp.org/API-Security/editions/2023/en/0xaa-unsafe-consumption-of-apis/

### Referências

- `_bmad-output/planning-artifacts/epics.md` — Epic 3, Story 3.2 e dependências 3.3–3.6.
- `_bmad-output/implementation-artifacts/3-1-catalogo-de-classes-de-integracao-por-tenant-e-produto.md` — base do catálogo e aprendizados da story anterior.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-1, AD-2, AD-4, AD-5, AD-6, AD-7, AD-9, AD-10 e AD-21.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/integracoes-externas-oq8.md` — classes prioritárias, mocks/sandbox, critérios futuros de fornecedores e custo.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md` — NATS/CloudEvents/AsyncAPI como contexto futuro.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md` — logs, dashboards e métricas de integrações.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md` — dados sintéticos, máscaras e não persistência de payload sensível bruto.
- `docs/observability.md` — helpers de observabilidade, logs seguros e anti-padrões.
- `docs/contracts.md` — contratos versionados e limitação metadata-only atual.
- `services/integration/src/creditos_integration/application/service.py` — application service existente que deve ser estendido, não refeito.
- `services/integration/tests/unit/test_integration_catalog.py` — padrões de testes e helpers existentes.

## Dev Agent Record

### Agent Model Used

Codex CLI.

### Debug Log References

- 2026-08-20 — bmad-dev-story iniciado na branch `agent/story-3-2-adapter-mock-sandbox-integracoes-externas`; baseline `6f81372`; Story movida para `in-progress`.
- `.venv/bin/python -m pytest services/integration/tests -q` — não executado: `.venv/bin/python` aponta para runtime ausente em `/tmp/creditos-uv-python`.
- `python3 -m pytest services/integration/tests -q` — não executado: Python 3.12 local sem `pytest`.
- `.venv/bin/ruff check services/integration/src services/integration/tests/unit/test_mock_integration_adapters.py` — passed.
- `.venv/bin/ruff format --check services/integration/src services/integration/tests/unit/test_mock_integration_adapters.py` — `30 files already formatted`.
- `PYTHONPATH=services/integration/src:packages/observability/src python3 -m compileall -q services/integration/src/creditos_integration services/integration/tests/unit/test_mock_integration_adapters.py` — passed.
- `python3` AST boundary check para `services/integration/src/creditos_integration/domain` — `offenders=[]`.
- `.venv/bin/pyright services/integration/src services/integration/tests/unit/test_mock_integration_adapters.py` — não executado: binário da venv depende de arquivo ausente.
- Jira — sincronização inicialmente falhou porque o `cloudId` não havia sido recuperado antes das chamadas; corrigido em seguida com `cloudId=84f362df-e059-4b3c-9f26-f6ea66180b7a`.
- Jira — subtarefas `CTOS-180` a `CTOS-188` criadas e movidas para `Concluído`; `CTOS-34` movida para `Em análise`.
- 2026-08-20 — `bmad-code-review` Step 02 executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 9 patches identificados.
- `.venv/bin/ruff check services/integration/src services/integration/tests/unit/test_mock_integration_adapters.py` — passed após patches de revisão.
- `.venv/bin/ruff format --check services/integration/src services/integration/tests/unit/test_mock_integration_adapters.py` — `30 files already formatted` após patches de revisão.
- `PYTHONPATH=services/integration/src:packages/observability/src python3 -m compileall -q services/integration/src/creditos_integration services/integration/tests/unit/test_mock_integration_adapters.py` — passed após patches de revisão.
- `git diff --check` — passed.

- 2026-08-18 — `bmad-create-story` executado para detalhar a Story 3.2.

### Completion Notes List

- Story detalhada com contexto de Epic 3, PRD, Architecture Spine, Story 3.1, código atual do `Integration Service` e pesquisa técnica oficial.
- Escopo delimitado para mocks/sandbox locais, determinísticos e sem fornecedor real.
- Guardrails explícitos adicionados para não antecipar NATS, fan-out/fan-in, retry, DLQ, gRPC, banco real ou contratos AsyncAPI finais.
- Implementado `IntegrationResult` canônico versionado e value objects de status, cenário, reason codes, classes cobertas e summary allowlist.
- Implementada porta hexagonal de adapter mock/sandbox e registry de execução separado do `AdapterRegistry` de catálogo.
- Implementados adapters in-memory determinísticos para quatro classes MVP, com cenários sintéticos configuráveis.
- Implementado `execute_mock_integration_plan` com tenant confiável, escopo `integration_mock:execute`, bloqueio de produção, rejeição de plano não `ready`, cross-tenant, classe não coberta e adapter não registrado.
- Adicionados testes unitários para fluxo feliz, determinismo, cenários, produção, plano não pronto, cross-tenant, adapter ausente, classe não coberta e logs/resultados seguros.
- Atualizados exports públicos e README do `Integration Service`.
- Validação completa de pytest/pyright ficou pendente por limitação ambiental da venv nesta sessão; `ruff`, `format --check`, compilação e fronteira DDD passaram.
- Patches de revisão aplicados: preflight completo sem execução parcial, validação por item, rejeição de cenários fora do plano, validação de referência sintética, bloqueio robusto de produção, logs de rejeição rastreáveis, validação pós-adapter, vocabulário fechado e duração por resultado medida.

### File List

- `_bmad-output/implementation-artifacts/3-2-adapter-mock-sandbox-para-integracoes-externas.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/__init__.py`
- `services/integration/src/creditos_integration/adapters/external/__init__.py`
- `services/integration/src/creditos_integration/adapters/external/in_memory_mock_integration_adapter.py`
- `services/integration/src/creditos_integration/application/__init__.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/application/ports/mock_integration_adapter.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/integration_result.py`
- `services/integration/src/creditos_integration/domain/value_objects/__init__.py`
- `services/integration/src/creditos_integration/domain/value_objects/result.py`
- `services/integration/tests/unit/test_mock_integration_adapters.py`

### Change Log

- 2026-08-18 — Story 3.2 criada e marcada como `ready-for-dev`.
- 2026-08-20 — Story 3.2 implementada e marcada como `review`.
- 2026-08-20 — Achados de revisão adversarial aplicados; Story 3.2 marcada como `done`.
