---
jira_issue: CTOS-69
branch: agent/story-8-4-webhook-delivery-retry-dlq
baseline_commit: 80417a8
---

# Story 8.4: Entrega Assíncrona de Webhooks com Retry e DLQ

Status: done

## Story

Como cliente técnico,
quero receber notificações assinadas e idempotentes,
para que meu sistema processe decisões sem polling constante.

## Acceptance Criteria

1. **Job assíncrono criado a partir de evento notificável**
   - **Given** uma decisão ou mudança de status notificável para um tenant com configuração ativa
   - **When** o evento é recebido pelo `Integration Service`
   - **Then** cria um job assíncrono de webhook por configuração ativa e evento habilitado
   - **And** não cria jobs duplicados para o mesmo par `event_id` + `webhook_configuration_id`.

2. **Payload público minimizado, versionado, assinado e idempotente**
   - **Given** um job de webhook elegível para entrega
   - **When** a entrega é preparada
   - **Then** envia envelope com versão de contrato, `event_id`, `event_type`, `proposal_id`, status/decisão aplicável, `correlation_id`, `trace_id`, `occurred_at` e `idempotency_key`
   - **And** assina o payload com chave resolvida por `signing_key_ref`
   - **And** não expõe CPF, CNPJ, nome, e-mail, endereço, payload bruto, segredo, token, stack trace ou detalhe interno.

3. **Entrega mockável sem rede externa obrigatória**
   - **Given** a etapa de implementação local e CI
   - **When** a entrega for executada em testes
   - **Then** usa porta/adaptador mockável ou in-memory para simular sucesso, falha temporária e falha permanente
   - **And** não exige endpoint externo real, NATS JetStream real, serviço HTTP real ou dependência nova sem justificativa registrada.

4. **Retry controlado com backoff e jitter testáveis**
   - **Given** uma falha temporária no endpoint do cliente
   - **When** a entrega falha antes do limite de tentativas
   - **Then** agenda nova tentativa com backoff e jitter determinísticos/testáveis, sem `sleep` real
   - **And** registra tentativa, causa normalizada, próximo horário, tenant e rastreabilidade mínima.

5. **DLQ e reprocessamento controlado**
   - **Given** uma falha permanente ou estouro do limite de tentativas
   - **When** o job não deve mais ser reenviado automaticamente
   - **Then** registra entrada de DLQ minimizada e log-safe
   - **And** permite reprocessamento controlado por escopo autorizado, tenant confiável e idempotência preservada.

6. **Rastreabilidade segura**
   - **Given** envio, sucesso, falha, retry, DLQ ou reprocessamento
   - **When** a operação é registrada
   - **Then** emite eventos/logs estruturados com `tenant_id`, IDs técnicos, `correlation_id`, `trace_id`, status e classe de falha
   - **And** não registra endpoint completo com query, segredo de assinatura, payload sensível ou body de resposta do cliente.

7. **Compatibilidade com arquitetura aprovada**
   - **Given** a arquitetura de mensageria assíncrona do CreditOS
   - **When** a story modela jobs, retry e DLQ
   - **Then** mantém mapeamento explícito para NATS JetStream, CloudEvents, DLQ e reprocessamento futuro
   - **And** preserva gRPC apenas para comunicação interna síncrona, sem expor gRPC publicamente.

## Tasks / Subtasks

- [x] CTOS-432 — Modelar evento e payload minimizado de entrega de webhook (AC: 1, 2, 7)
  - [x] Definir entidade/value object para evento/job de webhook no domínio de `Integration`.
  - [x] Incluir campos públicos permitidos: `contract_version`, `event_id`, `event_type`, `proposal_id`, status/decisão aplicável, `occurred_at`, `correlation_id`, `trace_id` e `idempotency_key`.
  - [x] Bloquear campos sensíveis: CPF, CNPJ, nome, e-mail, endereço, payload bruto, segredo, token e detalhe interno.

- [x] CTOS-433 — Criar portas e stores in-memory de entrega assíncrona (AC: 1, 3, 7)
  - [x] Criar porta de dispatcher/worker de webhook sem acoplar domínio a HTTP real ou NATS real.
  - [x] Criar store in-memory tenant-scoped para jobs, tentativas, estados e consulta por idempotência.
  - [x] Documentar mapeamento futuro para stream/consumer/DLQ JetStream sem implementar broker real.

- [x] CTOS-434 — Implementar criação de jobs para configurações ativas (AC: 1, 2)
  - [x] Reutilizar `WebhookConfiguration` e `WebhookConfigurationRepository` da Story 8.3.
  - [x] Filtrar por tenant, evento habilitado e status ativo.
  - [x] Garantir idempotência por `event_id` + `webhook_configuration_id`.

- [x] CTOS-435 — Assinar entregas e validar idempotência do consumidor (AC: 2, 3, 6)
  - [x] Criar assinatura HMAC com bibliotecas padrão (`hmac`, `hashlib`) e canonicalização JSON determinística.
  - [x] Resolver segredo por `signing_key_ref` via porta/adaptador testável, sem persistir ou logar segredo em claro.
  - [x] Incluir headers/envelope com assinatura, timestamp, event ID, idempotency key e correlation ID.

- [x] CTOS-436 — Implementar retry controlado com backoff e jitter testáveis (AC: 4, 6)
  - [x] Classificar resultado de entrega como sucesso, falha temporária ou falha final.
  - [x] Calcular próxima tentativa com política configurada em `WebhookConfiguration`.
  - [x] Evitar `sleep`, thread bloqueada ou dependência de relógio real não injetável.

- [x] CTOS-437 — Registrar DLQ de webhook e reprocessamento controlado (AC: 5, 6, 7)
  - [x] Criar registro de DLQ minimizado com tenant, job, evento, configuração, tentativa, classe de falha e rastreabilidade.
  - [x] Implementar comando/serviço de reprocessamento com escopo autorizado e tenant confiável.
  - [x] Preservar idempotência e impedir bypass de configuração desativada sem decisão explícita registrada.

- [x] CTOS-438 — Adicionar auditoria e logs seguros de entrega (AC: 4, 5, 6)
  - [x] Emitir eventos/logs para `webhook_delivery.created`, `sent`, `failed`, `retry_scheduled`, `dlq_recorded` e `reprocess_requested`, ou nomes equivalentes documentados.
  - [x] Usar payload log-safe e mascaramento já adotado no projeto.
  - [x] Não antecipar dashboards da Story 8.5; apenas produzir sinais seguros para consumo posterior.

- [x] CTOS-439 — Cobrir contratos internos e testes unitários de webhook delivery (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Criar testes unitários no `Integration Service` para sucesso, retry, DLQ, idempotência e reprocessamento.
  - [x] Validar que payloads/logs não contêm CPF, CNPJ, e-mail, segredo, token ou endpoint sensível.
  - [x] Atualizar catálogo/contratos somente se contrato público ou interno for alterado.

### Review Findings

- [x] [Review][Patch] Bloquear dados sensíveis também nos valores públicos do webhook [services/integration/src/creditos_integration/domain/entities/webhook_delivery.py:425]
- [x] [Review][Patch] Tornar a idempotência efetiva específica por configuração de webhook [services/integration/src/creditos_integration/application/service.py:1538]
- [x] [Review][Patch] Não executar retries agendados imediatamente no mesmo ciclo [services/integration/src/creditos_integration/adapters/events/in_memory_webhook_delivery_dispatcher.py:50]
- [x] [Review][Patch] Evitar reserva idempotente presa em `pending` após falha inesperada de dispatch [services/integration/src/creditos_integration/adapters/persistence/in_memory_webhook_delivery_store.py:14]
- [x] [Review][Patch] Alinhar contador de tentativas de webhook ao limite configurável de até 10 [services/integration/src/creditos_integration/domain/entities/webhook_delivery.py:171]
- [x] [Review][Patch] Validar que resultado `accepted` só represente status HTTP 2xx [services/integration/src/creditos_integration/application/ports/webhook_delivery.py:65]
- [x] [Review][Patch] Marcar DLQ como reprocessada somente quando o reprocessamento for enviado com sucesso [services/integration/src/creditos_integration/application/service.py:1748]
- [x] [Review][Patch] Adicionar mapeamento CloudEvents explícito para eventos de entrega de webhook [services/integration/src/creditos_integration/application/ports/webhook_delivery.py:23]
- [x] [Review][Patch] Tornar o resolver estático de assinatura tenant-scoped [services/integration/src/creditos_integration/application/ports/webhook_delivery.py:162]

## Dev Notes

### Escopo funcional

- Esta story implementa entrega assíncrona de webhooks no `Integration Service`; não cria novo microsserviço.
- O gatilho de entrada deve ser um evento/comando notificável já minimizado, e não uma consulta direta ao banco do `Decision Service`.
- A entrega real por HTTP externo pode ser representada por porta/adaptador testável; CI não deve depender de internet, endpoint do cliente ou broker real.
- A observabilidade de negócio e dashboards customer-facing ficam para a Story 8.5; esta story deve apenas emitir sinais seguros e úteis.
- Testes de contrato completos para consulta/webhooks ficam para a Story 8.6, mas alterações de contrato nesta story precisam de gates locais.

### Arquitetura e ownership

- `Integration` é o bounded context autorizado para webhooks/callbacks externos, jobs, retries, DLQ e reprocessamento.
- `Decision` não deve armazenar endpoint do cliente, segredo de webhook, retry policy de entrega, estado de entrega ou DLQ.
- gRPC continua reservado para chamadas internas síncronas; webhooks públicos são HTTP/JSON versionados.
- Fluxos assíncronos críticos devem manter compatibilidade com NATS JetStream, CloudEvents, transactional outbox/inbox e consumidores idempotentes.
- No MVP atual, implemente o núcleo determinístico/in-memory conforme padrões existentes; NATS JetStream real permanece infraestrutura futura até história específica.

### Reuso obrigatório

- Reutilizar `WebhookConfiguration`, validação de endpoint, eventos permitidos, status, assinatura e retry policy criados na Story 8.3.
- Reutilizar padrões da Story 3.4 para retry/DLQ/reprocessamento controlado, mas criar tipos próprios de webhook quando a semântica de entrega externa for diferente.
- Reutilizar logs estruturados, mascaramento e gates de dados sensíveis existentes; não criar sanitizador paralelo.
- Reutilizar convenções de DDD/hexagonal do `Integration Service`: domínio sem dependência de infra, application services orquestrando casos de uso, adapters in-memory para testes.

### Contrato de entrega sugerido

- Payload público mínimo:
  - `contract_version`
  - `event_id`
  - `event_type`
  - `occurred_at`
  - `tenant_ref` somente se já for identificador público/seguro; caso contrário, omitir
  - `proposal_id` ou identificador público equivalente da proposta
  - `proposal_status` ou `decision_status`, conforme evento
  - `decision_outcome` apenas quando já estiver autorizado no contrato público
  - `correlation_id`
  - `trace_id`
  - `idempotency_key`
- Headers/envelope sugeridos:
  - `X-CreditOS-Event-Id`
  - `X-CreditOS-Event-Type`
  - `X-CreditOS-Idempotency-Key`
  - `X-CreditOS-Correlation-Id`
  - `X-CreditOS-Timestamp`
  - `X-CreditOS-Signature`
  - `X-CreditOS-Signature-Algorithm`
- A canonicalização para assinatura deve ser determinística (`json.dumps(..., sort_keys=True, separators=(",", ":"))` ou equivalente) e coberta por testes.

### Retry, DLQ e reprocessamento

- Falhas 2xx são sucesso; 408, 409 transitório se justificável, 425, 429 e 5xx podem ser temporárias; 4xx de validação/autorização normalmente são finais.
- `no_retry` deve levar falha elegível diretamente à DLQ ou estado final controlado, conforme política da configuração.
- `standard_exponential_backoff` deve usar cálculo determinístico e relógio injetável; não usar `time.sleep` nos testes nem no domínio.
- DLQ deve guardar contexto mínimo para reprocessar: tenant, job, configuração, evento, tentativa, causa normalizada, timestamps e rastreabilidade.
- Reprocessamento deve exigir escopo específico, por exemplo `webhook_delivery:reprocess`, e tenant confiável com isolamento preservado.

### Segurança, privacidade e tenancy

- Nunca logar ou persistir segredo de assinatura, payload bruto, CPF, CNPJ, nome, e-mail, endereço, token, authorization header, query sensível ou body de resposta do cliente.
- Endpoint completo com query não deve aparecer em log/auditoria/DLQ; use host normalizado e identificadores técnicos.
- Todos os stores, jobs, DLQs, idempotency keys e eventos precisam carregar `tenant_id` e rejeitar acesso cross-tenant.
- Reprocessamento não pode enviar para configuração desativada sem regra explícita e auditável; default seguro é bloquear.

### Testes mínimos esperados

- Job é criado somente para configuração ativa e evento habilitado.
- Mesmo evento/configuração não gera duplicidade.
- Payload assinado contém campos obrigatórios e exclui dados sensíveis.
- Assinatura é determinística para payload equivalente e muda quando payload muda.
- Falha temporária agenda retry com próxima tentativa calculada.
- Estouro de tentativas ou falha final gera DLQ minimizada.
- Reprocessamento exige escopo e respeita tenant/idempotência.
- Logs/auditoria de entrega, retry, DLQ e reprocessamento são log-safe.

### Arquivos prováveis

- `services/integration/src/creditos_integration/domain/entities/webhook_delivery.py`
- `services/integration/src/creditos_integration/domain/value_objects/webhook.py`
- `services/integration/src/creditos_integration/application/ports/webhook_delivery.py`
- `services/integration/src/creditos_integration/adapters/events/in_memory_webhook_delivery_dispatcher.py`
- `services/integration/src/creditos_integration/adapters/persistence/in_memory_webhook_delivery_store.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/tests/unit/test_webhook_delivery.py`
- `packages/contracts/catalog/contracts.toml`, somente se houver novo contrato ou evento catalogado.

## Anti-Patterns

- Não adicionar `httpx`, `requests`, cliente NATS ou dependência nova sem decisão registrada.
- Não criar microsserviço novo de webhooks.
- Não chamar endpoints reais em testes.
- Não persistir segredo de assinatura em entidade, log, auditoria, DLQ ou fixture exposta.
- Não duplicar o mecanismo genérico de mascaramento/log seguro já existente.
- Não acoplar `Decision Service` a detalhes de endpoint, retry ou DLQ.
- Não usar status string livre quando já existir enum governado.

## Referências

- `_bmad-output/planning-artifacts/epics.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md`
- `_bmad-output/implementation-artifacts/8-3-configuracao-de-webhooks-por-tenant.md`
- `_bmad-output/implementation-artifacts/3-4-resiliencia-retry-dlq-e-reprocessamento-controlado.md`

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- `.venv/bin/python -m pytest services/integration/tests/unit/test_webhook_delivery.py -q` — RED confirmado inicialmente por import inexistente; depois `3 passed`.
- `.venv/bin/python -m pytest services/integration/tests/unit/test_webhook_delivery.py services/integration/tests/unit/test_webhook_configuration.py services/integration/tests/unit/test_integration_resilience.py -q` — `40 passed`.
- `.venv/bin/python -m ruff format --check services/integration/src/creditos_integration services/integration/tests/unit/test_webhook_delivery.py` — passou após formatação.
- `.venv/bin/python -m ruff check services/integration/src/creditos_integration services/integration/tests/unit/test_webhook_delivery.py` — passou.
- `.venv/bin/python -m pyright services/integration/src/creditos_integration services/integration/tests/unit/test_webhook_delivery.py` — `0 errors`.
- `.venv/bin/python -m pytest -q` — falhou no sandbox por `Operation not permitted` nos testes de harness local.
- `.venv/bin/python -m pytest -q` com permissão elevada — `818 passed`.
- `uv lock --check` — não executado localmente porque `uv` não está instalado/disponível neste ambiente.

### Implementation Plan

- Modelar entidades de entrega de webhook no domínio, mantendo payload público minimizado e validado.
- Adicionar portas/adapters in-memory para dispatcher, store, DLQ, adapter de entrega e resolver de chave de assinatura.
- Orquestrar no `IntegrationCatalogApplicationService` a criação idempotente de jobs, entrega assinada, retry, DLQ e reprocessamento.
- Cobrir sucesso, replay idempotente, retry, DLQ, reprocessamento autorizado e ausência de dados sensíveis em payload/logs.

### Completion Notes

- Implementado fluxo de entrega assíncrona de webhooks no `Integration Service` sem novo microsserviço, sem HTTP externo real e sem dependência nova.
- Payload público de entrega agora é versionado, minimizado, assinado via HMAC SHA-256 e idempotente por evento/configuração.
- Retry é determinístico/testável, sem `sleep`, com backoff e jitter; falhas finais ou limite de tentativas geram DLQ minimizada.
- Reprocessamento de DLQ exige escopo `webhook_delivery:reprocess`, tenant confiável e configuração ativa.
- Logs estruturados registram criação, envio, falha, retry, DLQ e reprocessamento sem expor segredo, token, endpoint com query ou payload sensível.

### File List

- `_bmad-output/implementation-artifacts/8-4-entrega-assincrona-de-webhooks-com-retry-e-dlq.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `services/integration/src/creditos_integration/adapters/events/__init__.py`
- `services/integration/src/creditos_integration/adapters/events/in_memory_webhook_delivery_dispatcher.py`
- `services/integration/src/creditos_integration/adapters/persistence/__init__.py`
- `services/integration/src/creditos_integration/adapters/persistence/in_memory_webhook_delivery_dlq_store.py`
- `services/integration/src/creditos_integration/adapters/persistence/in_memory_webhook_delivery_store.py`
- `services/integration/src/creditos_integration/application/ports/webhook_delivery.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/src/creditos_integration/domain/entities/__init__.py`
- `services/integration/src/creditos_integration/domain/entities/webhook_delivery.py`
- `services/integration/tests/unit/test_webhook_delivery.py`

## Change Log

- 2026-10-07: Story 8.4 detalhada com subtarefas Jira CTOS-432 a CTOS-439 e status `ready-for-dev`.
- 2026-10-07: Implementada entrega assíncrona de webhooks com assinatura, idempotência, retry determinístico, DLQ, reprocessamento controlado, logs seguros e testes.
