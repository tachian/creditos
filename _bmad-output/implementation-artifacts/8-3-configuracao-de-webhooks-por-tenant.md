---
jira_issue: CTOS-68
branch: agent/story-8-3-tenant-webhook-configuration
baseline_commit: 1d869d007129fe6b451c9a6fc326fc2c2f1dbde7
---

# Story 8.3: Configuração de Webhooks por Tenant

Status: done

## Story

Como cliente técnico B2B,
quero configurar endpoints de webhook por tenant e evento,
para receber notificações versionadas de decisão ou mudança de status sem expor dados sensíveis.

## Acceptance Criteria

1. **Configuração governada por tenant e evento**
   - **Given** um cliente autorizado com tenant resolvido pelo contexto confiável
   - **When** configura webhook para eventos permitidos
   - **Then** registra endpoint, eventos, status, versão de contrato, dados de assinatura e política de retry
   - **And** a configuração é tenant-scoped, auditável e não usa `tenant_id` recebido em body/path como autoridade.

2. **Rejeição segura de endpoint, segredo e política inválidos**
   - **Given** endpoint inválido, inseguro ou fora de allowlist/política
   - **When** a configuração é salva
   - **Then** rejeita com erro padronizado, seguro e correlacionável
   - **And** não persiste segredo em claro, não loga segredo, não expõe query string sensível e não cria configuração parcial.

3. **Contrato público versionado**
   - **Given** consumidores externos integrando com a API pública de webhooks
   - **When** consultam ou submetem configuração
   - **Then** usam contrato público `v1` fechado, com enums versionados, erros padronizados e campos públicos minimizados
   - **And** qualquer breaking change após congelamento da v1 exige nova versão, plano de migração e janela de compatibilidade.

4. **Separação entre configuração e entrega**
   - **Given** uma configuração válida foi salva
   - **When** a Story 8.3 termina
   - **Then** não executa entrega assíncrona real, retry de entrega, DLQ de webhook ou chamada HTTP ao cliente
   - **And** deixa contrato/modelo preparados para a Story 8.4 implementar entrega assíncrona com retry e DLQ.

5. **Rastreabilidade sem vazamento**
   - **Given** criação, atualização, desativação ou rejeição de configuração
   - **When** logs e auditoria forem gerados
   - **Then** incluem contrato, versão, status, evento, tenant confiável, correlação, trace e motivo controlado
   - **And** não incluem CPF, CNPJ, nome, e-mail, endereço, telefone, segredo, token, headers, payload bruto, query string sensível ou endpoint completo quando contiver credencial.

## Tasks / Subtasks

- [x] CTOS-424 — Definir contrato público v1 de configuração de webhooks (AC: 1, 2, 3)
  - [x] Criar contrato OpenAPI público para configuração de webhooks em `packages/contracts/openapi/public/webhooks/v1/openapi.json`, salvo decisão justificada no Dev Agent Record.
  - [x] Registrar `webhook-configuration-public-api` em `packages/contracts/catalog/contracts.toml` com owner `Integration`, lifecycle MVP pré-produção e política de breaking change coerente com o Epic 8.
  - [x] Definir schemas fechados para request, response e erro público com `additionalProperties: false`.
  - [x] Definir enums públicos para evento, status, algoritmo de assinatura, estratégia de retry e `error_code`.
  - [x] Garantir que `tenant_id`, segredo em claro, headers privados e payload de entrega não façam parte do contrato público.

- [x] CTOS-425 — Modelar configuração de webhook no domínio de integração (AC: 1, 4)
  - [x] Criar entidade/value objects no `Integration Service`, preferencialmente em `services/integration/src/creditos_integration/domain/entities/` e `domain/value_objects/`.
  - [x] Representar `webhook_configuration_id`, endpoint normalizado, eventos permitidos, status, versão de contrato, retry policy, assinatura e timestamps.
  - [x] Persistir somente representação segura de assinatura, como referência/fingerprint/hash controlado; nunca persistir segredo em claro.
  - [x] Manter domínio sem dependência de OpenAPI, FastAPI, HTTP client, NATS, gRPC, banco ou SDK externo.

- [x] CTOS-426 — Implementar serviço de aplicação e repositório de configuração (AC: 1, 2, 4)
  - [x] Criar comando/query para criar/atualizar/listar/desativar configuração conforme escopo mínimo aprovado.
  - [x] Criar porta de repositório tenant-scoped e adapter in-memory para testes/harness.
  - [x] Exigir tenant confiável com isolamento `bridge` e escopo autorizado, sugerido `webhook_configuration:write` para escrita e `webhook_configuration:read` para leitura.
  - [x] Garantir rollback lógico em falha crítica de auditoria antes de confirmar configuração.
  - [x] Não implementar entrega HTTP, assinatura de payload de entrega, retry real ou DLQ real nesta story.

- [x] CTOS-427 — Aplicar validações de endpoint, allowlist e proteção contra SSRF (AC: 2)
  - [x] Aceitar somente `https://` com host válido e sem `userinfo`.
  - [x] Rejeitar `localhost`, loopback, IP privado, link-local, multicast, reserved/unspecified e host vazio.
  - [x] Rejeitar query string com chaves sensíveis óbvias (`token`, `secret`, `key`, `authorization`, `password`) ou mascará-la antes de qualquer log/auditoria, conforme decisão de implementação.
  - [x] Aplicar allowlist/política por tenant quando fornecida; se ausente, manter bloqueios mínimos obrigatórios de SSRF.
  - [x] Produzir erro controlado, sem ecoar endpoint bruto inseguro ou segredo.

- [x] CTOS-428 — Proteger segredo de assinatura e mascarar dados sensíveis (AC: 1, 2, 5)
  - [x] Definir algoritmo público inicial, sugerido `hmac_sha256`, sem adicionar dependência externa.
  - [x] Criar representação segura de segredo para teste local, como `secret_fingerprint`/`secret_reference`, deixando KMS/secret manager real fora do escopo.
  - [x] Garantir que logs, auditoria, responses e fixtures não contenham segredo em claro.
  - [x] Testar que valores como token, segredo, CPF, CNPJ e e-mail não aparecem em artifacts gerados.

- [x] CTOS-429 — Registrar auditoria e logs seguros da configuração de webhook (AC: 1, 2, 5)
  - [x] Estender `IntegrationAuditEvent` ou criar evento específico de configuração de webhook com payload log-safe.
  - [x] Registrar eventos auditáveis para criação, atualização, desativação e rejeição controlada.
  - [x] Usar logs estruturados apenas como telemetria; auditoria oficial continua via porta auditável.
  - [x] Incluir correlação, trace, contrato, versão, evento, status e motivo controlado, sem payload bruto ou dados sensíveis.

- [x] CTOS-430 — Adicionar testes e gates de contrato/segurança para webhooks (AC: 1, 2, 3, 4, 5)
  - [x] Atualizar `tests/test_contracts_structure.py` e `scripts/check_contracts.py` para validar contrato público, catálogo, schemas fechados e campos proibidos.
  - [x] Criar testes unitários no `Integration Service` para configuração válida, endpoint inseguro, allowlist, tenant isolation, escopo, auditoria e logs seguros.
  - [x] Adicionar testes negativos de segredo em claro, query string sensível e endpoint interno.
  - [x] Confirmar que `uv.lock` não muda se nenhuma dependência for adicionada.

- [x] CTOS-431 — Atualizar documentação operacional e artefatos BMAD da Story 8.3 (AC: 1, 2, 3, 4, 5)
  - [x] Atualizar `packages/contracts/README.md`, `docs/contracts.md` e `services/integration/README.md` quando o contrato/modelo for implementado.
  - [x] Registrar limites explícitos: configuração sim, entrega/retry/DLQ de webhook somente na Story 8.4.
  - [x] Atualizar este story file, `sprint-status.yaml` e Dev Agent Record conforme avanço.
  - [x] Registrar comandos de validação e resultados antes de PR.

### Review Findings

- [x] [Review][Patch] Resolução DNS de hostname não bloqueia destino interno/privado [services/integration/src/creditos_integration/domain/value_objects/webhook.py:111]
- [x] [Review][Patch] Allowlist de domínios pode ser controlada pela requisição pública [services/integration/src/creditos_integration/application/service.py:130]
- [x] [Review][Patch] Rejeições de configuração geram log, mas não evento de auditoria oficial [services/integration/src/creditos_integration/application/service.py:1119]
- [x] [Review][Patch] Contrato `PATCH` promete atualização de status mais ampla que a implementação [packages/contracts/openapi/public/webhooks/v1/openapi.json:191]
- [x] [Review][Patch] Status `rejected` é aceito na criação de configuração [services/integration/src/creditos_integration/domain/value_objects/webhook.py:68]
- [x] [Review][Patch] Detecção de query string sensível não cobre variações comuns [services/integration/src/creditos_integration/domain/value_objects/webhook.py:34]
- [x] [Review][Patch] Porta explícita fora da política não é rejeitada [services/integration/src/creditos_integration/domain/value_objects/webhook.py:118]
- [x] [Review][Patch] Identificador determinístico usa endpoint bruto antes da normalização [services/integration/src/creditos_integration/application/service.py:1060]
- [x] [Review][Patch] Gate de contrato não valida todos os schemas públicos novos [scripts/check_contracts.py:752]
- [x] [Review][Patch] `Idempotency-Key` é obrigatório no contrato, mas não chega ao comando de aplicação [services/integration/src/creditos_integration/application/service.py:130]
- [x] [Review][Defer] Rollback sem controle transacional/CAS pode sobrescrever escrita concorrente [services/integration/src/creditos_integration/application/service.py:1101] — deferred, pre-existing

## Dev Notes

### Contexto funcional

- A Story 8.3 inicia a parte de notificações do Epic 8 depois da consulta pública de decisão/status das Stories 8.1 e 8.2.
- O objetivo é configurar webhooks por tenant e evento; a entrega assíncrona com retry/DLQ fica para a Story 8.4.
- O cliente ainda não usa a plataforma em produção; a v1 pública pode continuar com lifecycle MVP pré-produção, mas deve registrar política de congelamento no primeiro cliente externo ativo.

### Fronteira de domínio e serviço responsável

- `Integration Service` é o bounded context responsável por integrações externas, incluindo configuração de webhooks/callbacks.
- `Decision Service` não deve armazenar endpoint de cliente, segredo de webhook, política de retry de entrega ou estado de entrega.
- Comunicação interna síncrona entre microsserviços continua gRPC; eventos assíncronos continuam preparados para NATS JetStream/CloudEvents, mas esta story não precisa criar broker real.
- Backend deve seguir DDD + arquitetura hexagonal: domínio não importa adapter, transporte, persistência, framework ou contrato OpenAPI.

### Contrato público recomendado

- Caminho sugerido para contrato: `packages/contracts/openapi/public/webhooks/v1/openapi.json`.
- ID sugerido no catálogo: `webhook-configuration-public-api`.
- Owner sugerido: `Integration`.
- Endpoints mínimos sugeridos:
  - `POST /v1/webhooks/configurations` para criar ou substituir configuração governada.
  - `GET /v1/webhooks/configurations` para listar configurações públicas do tenant.
  - `PATCH /v1/webhooks/configurations/{webhook_configuration_id}` ou endpoint equivalente para ativar/desativar, se necessário no MVP.
- Se a implementação optar por outro path ou granularidade, registrar justificativa, alternativa rejeitada e consequência no Dev Agent Record.

### Eventos e status públicos sugeridos

- Eventos iniciais permitidos: `decision.status_changed` e `decision.completed`.
- Status de configuração sugeridos: `active`, `disabled`, `pending_verification` e `rejected`.
- Estratégias de retry configuráveis sugeridas: `standard_exponential_backoff` e `no_retry`.
- Algoritmo de assinatura inicial sugerido: `hmac_sha256`.
- Não adicionar evento público novo sem gate de contrato e documentação.

### Checklist de segurança para webhooks

- Endpoint deve usar `https://`.
- Endpoint não pode conter `userinfo`.
- Endpoint não pode resolver diretamente para loopback, private, link-local, multicast, reserved ou unspecified.
- Host vazio, porta fora da política, esquema não HTTP(S) e URLs malformadas devem falhar fechado.
- Query string com termos sensíveis deve ser rejeitada ou removida de qualquer representação persistida/logada.
- Allowlist/política por tenant deve ser aplicada quando configurada.
- Segredo de assinatura nunca deve ser persistido, logado, auditado ou retornado em claro.
- Logs e auditoria devem usar representação minimizada/masked do endpoint.
- Erros não devem ecoar endpoint inseguro bruto nem segredo.
- Testes devem cobrir tentativas de SSRF, tenant ausente, cross-tenant, escopo insuficiente e vazamento de segredo.

### Segurança, privacidade e tenancy

- Tenant deve vir de `ObservabilityContext` confiável; não aceitar `tenant_id` público como autoridade.
- Configuração deve ser tenant-scoped no repositório e em todos os casos de uso.
- Escopos sugeridos: `webhook_configuration:write` e `webhook_configuration:read`, salvo alinhamento com padrão final da implementação.
- Rejeições por escopo, tenant inválido e endpoint inseguro devem ser controladas e logadas sem dados sensíveis.
- Logs estruturados devem seguir o padrão de mascaramento obrigatório do Epic 6.

### Auditoria e observabilidade

- Configuração aceita, atualizada, desativada e rejeitada deve gerar evento auditável via porta, não apenas log.
- Logs técnicos devem incluir operação, status, contrato, versão, duração, correlação e motivo controlado.
- Observabilidade de entrega, latência externa, retry e DLQ de webhook pertence principalmente às Stories 8.4 e 8.5.

### Arquivos provavelmente afetados

- `packages/contracts/openapi/public/webhooks/v1/openapi.json`
- `packages/contracts/catalog/contracts.toml`
- `packages/contracts/README.md`
- `docs/contracts.md`
- `scripts/check_contracts.py`
- `tests/test_contracts_structure.py`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/application/ports/`
- `services/integration/src/creditos_integration/adapters/persistence/`
- `services/integration/src/creditos_integration/domain/entities/`
- `services/integration/src/creditos_integration/domain/value_objects/`
- `services/integration/tests/unit/`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Regras técnicas obrigatórias

- Não escolher SDK, gateway, provedor externo, KMS real, Secret Manager real ou HTTP client produtivo nesta story sem justificativa, alternativas e consequências.
- Não implementar microsserviço novo para webhooks; usar o `Integration Service` existente.
- Não implementar entrega assíncrona, retry de entrega, DLQ ou NATS real nesta story.
- Não reusar logs como auditoria oficial.
- Não armazenar segredo em claro.
- Não adicionar dependência se a validação puder ser feita com biblioteca padrão.

### Testing Requirements

- Testes focados recomendados:
  - `uv run pytest tests/test_contracts_structure.py -q`
  - `uv run pytest services/integration/tests/unit -q`
  - `uv run python scripts/check_contracts.py`
- Validações finais usuais:
  - `uv run ruff format --check .`
  - `uv run ruff check .`
  - `uv run pyright`
  - `uv lock --check`
- Se `uv` não estiver disponível localmente, usar `.venv/bin/python` conforme padrão operacional já adotado no repositório.

### Project Structure Notes

- Nenhum `project-context.md` foi encontrado no repositório durante a criação desta story; foram usadas Architecture, PRD/epics, stories anteriores, contratos e código existente.
- Não há UX formal aplicável; a interface desta story é API/contrato público e documentação técnica para cliente B2B.
- Não foi necessária pesquisa externa nesta etapa porque a story não seleciona nova tecnologia, biblioteca, cloud, provedor, protocolo ou fornecedor; ela aplica padrões internos já aprovados.

### References

- `_bmad-output/planning-artifacts/epics.md#Story 8.3: Configuração de Webhooks por Tenant`
- `_bmad-output/implementation-artifacts/8-1-consulta-de-decisao-por-proposta.md`
- `_bmad-output/implementation-artifacts/8-2-contrato-publico-de-status-e-decisao.md`
- `_bmad-output/implementation-artifacts/3-6-contratos-e-gates-de-integracao.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `packages/contracts/catalog/contracts.toml`
- `packages/contracts/openapi/public/decision/v1/openapi.json`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/domain/entities/integration_configuration.py`
- `services/integration/src/creditos_integration/application/ports/audit_event_publisher.py`
- `services/integration/tests/unit/test_integration_catalog.py`
- `services/integration/tests/unit/test_integration_resilience.py`
- `services/integration/README.md`

## Create Story Checklist

- [x] Objetivo, valor e escopo da story estão claros.
- [x] Acceptance Criteria cobrem caminho feliz, rejeições, contrato, segurança, privacidade e limite de escopo.
- [x] Tasks estão rastreadas para subtarefas Jira e ACs.
- [x] Dev Notes incluem arquivos, padrões existentes, restrições arquiteturais e testing requirements.
- [x] Dependências e anti-padrões estão explícitos.
- [x] Nenhuma tecnologia nova foi escolhida sem justificativa.
- [x] Checklist de segurança de webhooks foi registrado antes das Stories 8.3 e 8.4.

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- `.venv/bin/python -m pytest tests/test_contracts_structure.py::test_webhook_public_openapi_defines_governed_configuration_contract services/integration/tests/unit/test_webhook_configuration.py -q` — RED confirmado inicialmente com import/contrato ausentes.
- `.venv/bin/python -m pytest tests/test_contracts_structure.py::test_webhook_public_openapi_defines_governed_configuration_contract tests/test_contracts_structure.py::test_webhook_public_api_catalog_marks_v1_as_pre_production_experimental tests/test_contracts_structure.py::test_contract_governance_check_rejects_webhook_event_enum_drift tests/test_contracts_structure.py::test_contract_governance_check_rejects_webhook_sensitive_public_fields services/integration/tests/unit/test_webhook_configuration.py -q` — 10 passed.
- `.venv/bin/python scripts/check_contracts.py && .venv/bin/python -m pytest tests/test_contracts_structure.py services/integration/tests/unit -q` — contracts check passed; 176 passed.
- `.venv/bin/python -m ruff format --check . && .venv/bin/python -m ruff check . && .venv/bin/pyright && .venv/bin/python -m pytest -q` — após formatação, ruff/pyright OK; 805 passed.
- `.venv/bin/python scripts/check_contracts.py` — contracts check passed: 11 contracts.
- `git diff --exit-code -- uv.lock` — sem alterações em `uv.lock`.

### Completion Notes List

- Implementado contrato público `webhook-configuration-public-api` em OpenAPI v1 com cadastro, listagem e alteração de status de configurações de webhook.
- Registrado contrato no catálogo como `experimental`/`mvp-pre-production`, com freeze no primeiro cliente externo integrado.
- Modelado `WebhookConfiguration` no domínio do `Integration Service`, com validação de endpoint HTTPS, eventos, status, assinatura e retry policy.
- Implementados casos de uso para configurar, listar e desativar webhooks por tenant, com repositório in-memory tenant-scoped.
- Adicionadas proteções contra endpoints inseguros, query string sensível, segredo em claro, campos públicos sensíveis e logs/auditoria com dados minimizados.
- Atualizados docs de contratos e README operacional do `Integration Service`; entrega assíncrona/retry/DLQ permanecem fora da Story 8.3 e preparados para Story 8.4.
- Validações locais completas passaram com `.venv`: ruff format/check, pyright, contratos e 805 testes.

### File List

- `_bmad-output/implementation-artifacts/8-3-configuracao-de-webhooks-por-tenant.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/contracts.md`
- `packages/contracts/README.md`
- `packages/contracts/catalog/contracts.toml`
- `packages/contracts/openapi/public/webhooks/v1/openapi.json`
- `scripts/check_contracts.py`
- `services/integration/README.md`
- `services/integration/src/creditos_integration/adapters/persistence/__init__.py`
- `services/integration/src/creditos_integration/adapters/persistence/in_memory_webhook_configuration_repository.py`
- `services/integration/src/creditos_integration/application/ports/__init__.py`
- `services/integration/src/creditos_integration/application/ports/audit_event_publisher.py`
- `services/integration/src/creditos_integration/application/ports/webhook_configuration_repository.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/webhook_configuration.py`
- `services/integration/src/creditos_integration/domain/value_objects/webhook.py`
- `services/integration/tests/unit/test_webhook_configuration.py`
- `tests/test_contracts_structure.py`

### Change Log

- 2026-10-06: Story 8.3 detalhada com subtarefas Jira CTOS-424 a CTOS-431, checklist de segurança para webhooks e status `ready-for-dev`.
- 2026-10-06: Implementada configuração pública de webhooks por tenant no `Integration Service`, contrato OpenAPI v1, gates de contrato, testes, documentação e status `review`.
