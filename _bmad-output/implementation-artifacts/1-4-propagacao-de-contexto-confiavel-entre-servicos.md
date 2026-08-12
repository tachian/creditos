---
baseline_commit: 1e9672e
jira_issue: CTOS-26
branch: agent/story-1-4-propagacao-contexto-confiavel
---

# Story 1.4: Propagação de Contexto Confiável entre Serviços

Status: done

## Story

As a microsserviço CreditOS,
I want propagar tenant, sujeito, scopes, correlation ID e trace ID,
so that chamadas internas e eventos sejam rastreáveis e autorizáveis.

## Acceptance Criteria

1. **Metadata gRPC carrega contexto confiável**
   - **Given** um serviço CreditOS com contexto autenticado/autorizado e contexto de observabilidade
   - **When** ele prepara uma chamada interna gRPC
   - **Then** a metadata inclui `tenant_id`, `tenant_isolation_tier`, sujeito, cliente técnico quando aplicável, scopes, correlation ID, request ID e `traceparent`
   - **And** não inclui access token, `Authorization`, `token_id`, segredo, payload bruto ou dado pessoal/sensível.

2. **Receptor valida metadata antes do caso de uso**
   - **Given** uma chamada gRPC interna recebida
   - **When** a metadata está ausente, malformada, sem tenant, sem sujeito, sem scopes ou com tenant incompatível com o recurso
   - **Then** o adapter rejeita a chamada com erro seguro antes de invocar o caso de uso
   - **And** logs de rejeição não confiam em tenant não validado.

3. **Eventos carregam contexto mínimo em CloudEvents**
   - **Given** um evento publicado para fluxo assíncrono
   - **When** o evento é emitido
   - **Then** ele usa CloudEvents `specversion: "1.0"` com atributos/extensões válidos para tenant, correlação, trace context, schema version e referência do ator
   - **And** o contexto fica em atributos do evento, não duplicado em payload sensível bruto.

4. **Parsing de eventos é seguro e idempotente**
   - **Given** um consumidor de evento recebe atributos CloudEvents
   - **When** o contexto obrigatório está ausente, usa nomes inválidos, carrega scopes malformados ou tenta spoofing de tenant
   - **Then** o parsing falha com erro padronizado e o consumidor não executa caso de uso
   - **And** o evento mantém informações suficientes para inbox/idempotência, retry/DLQ e rastreabilidade.

5. **Contratos e testes protegem compatibilidade**
   - **Given** alterações em contratos protobuf, AsyncAPI ou helpers compartilhados
   - **When** os gates são executados
   - **Then** testes unitários, integração local, validação de contratos, lint, format e typecheck passam
   - **And** mudanças incompatíveis exigem nova versão ou justificativa explícita.

## Tasks / Subtasks

- [x] CTOS-128 — Modelar contexto propagável comum (AC: 1, 2, 3, 4)
  - [x] Criar modelo técnico compartilhável para contexto confiável propagado, sem compartilhar domínio entre bounded contexts.
  - [x] Reutilizar `AuthorizationSubject`, `ResolvedM2MTenantContext` e `ObservabilityContext` como fontes confiáveis, sem copiar `token_id`.
  - [x] Validar `tenant_id`, `tenant_isolation_tier`, sujeito, principal type, `client_id`, scopes e roles com regras equivalentes às Stories 1.2/1.3.

- [x] CTOS-129 — Criar helpers de metadata gRPC (AC: 1, 2)
  - [x] Serializar contexto para metadata gRPC como sequência de pares ASCII, com chaves lower-case e sem valores binários.
  - [x] Parsear metadata recebida para contexto validado antes de qualquer caso de uso.
  - [x] Preservar `traceparent` como forma canônica de trace distribuído; não inventar `x-trace-id` paralelo sem necessidade.

- [x] CTOS-130 — Criar helpers CloudEvents para contexto assíncrono (AC: 3, 4)
  - [x] Serializar contexto mínimo como atributos/extensões CloudEvents sem underscore: `tenantid`, `tenanttier`, `subjectid`, `clientid`, `principaltype`, `scopes`, `roles`, `correlationid`, `requestid`, `traceparent` e `schemaversion`.
  - [x] Parsear atributos CloudEvents recebidos com validação estrita e erro seguro.
  - [x] Garantir que dados sensíveis permaneçam fora de atributos e `data` por padrão.

- [x] CTOS-131 — Integrar o padrão ao `Identity & Tenant Service` (AC: 1, 2)
  - [x] Expor factory/adapters locais que derivem contexto propagável de `ResolvedM2MTenantContext` e `AuthorizationSubject`.
  - [x] Adicionar ponto de validação no caminho de adapter gRPC local/testável sem acoplar domínio a gRPC.
  - [x] Atualizar logs para registrar origem/destino/contrato, `tenant_id` apenas quando confiável e falhas sem payload sensível.

- [x] CTOS-132 — Atualizar contratos/documentação de contexto (AC: 3, 5)
  - [x] Atualizar `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` apenas de forma backward-compatible ou documentar por que metadata não altera o proto.
  - [x] Atualizar `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` se novos atributos mínimos forem promovidos a contrato.
  - [x] Atualizar README(s) com convenções de metadata gRPC e CloudEvents, incluindo exemplos seguros.

- [x] CTOS-133 — Cobrir regressões de segurança e isolamento (AC: 1, 2, 3, 4, 5)
  - [x] Testar round-trip gRPC metadata: saída segura, entrada válida, metadata ausente, scopes malformados, tenant ausente e `traceparent` inválido.
  - [x] Testar round-trip CloudEvents: atributos válidos, extensões com underscore rejeitadas, ausência de tenant/correlation/trace e payload sensível não propagado.
  - [x] Testar que `Authorization`, access token, `token_id`, CPF/CNPJ, e-mail completo, segredo e payload bruto não aparecem em logs/eventos.

- [x] CTOS-134 — Sincronizar BMAD/Jira e registrar evidências da Story 1.4 (AC: 5)
  - [x] Manter `CTOS-26` atualizado no Jira durante desenvolvimento, revisão e conclusão.
  - [x] Atualizar esta story com arquivos alterados, notas de conclusão, resultados de gates e achados de review.
  - [x] Atualizar `sprint-status.yaml` para `review` somente após implementação e gates verdes.

### Review Findings

- [x] [Review][Patch] Rejeitar metadata gRPC duplicada e itens de sequência malformados [packages/security/src/creditos_security/context.py:271]
- [x] [Review][Patch] Rejeitar chaves sensíveis desconhecidas em metadata gRPC e CloudEvents [packages/security/src/creditos_security/context.py:282]
- [x] [Review][Patch] Detectar CPF/CNPJ embutido em identificadores propagados, não apenas valor inteiro [packages/security/src/creditos_security/context.py:185]
- [x] [Review][Patch] Preservar e validar `idempotencykey` no parse de contexto de evento [packages/security/src/creditos_security/context.py:331]
- [x] [Review][Patch] Alinhar campos obrigatórios do AsyncAPI ao contexto mínimo que o parser exige [packages/contracts/asyncapi/events/proposal/v1/asyncapi.json:50]
- [x] [Review][Patch] Validar tenant esperado antes de reconstruir sujeito gRPC para uso de negócio [services/identity-tenant/src/creditos_identity_tenant/adapters/grpc/trusted_context.py:34]
- [x] [Review][Patch] Validar tenant esperado no consumidor CloudEvents para bloquear spoofing cross-tenant [services/identity-tenant/src/creditos_identity_tenant/adapters/events/trusted_context.py:35]
- [x] [Review][Patch] Validar envelope CloudEvents core antes de aceitar/publicar contexto de evento [packages/security/src/creditos_security/context.py:303]
- [x] [Review][Patch] Implementar logging seguro de rejeições de contexto sem confiar em tenant não validado [services/identity-tenant/src/creditos_identity_tenant/adapters/grpc/trusted_context.py:34]
- [x] [Review][Patch] Remover acoplamento adapter de eventos para adapter gRPC na factory comum [services/identity-tenant/src/creditos_identity_tenant/adapters/events/trusted_context.py:12]
- [x] [Review][Patch] Ler tenant confiável de `x-creditos-*` no `ObservabilityContext` [packages/observability/src/creditos_observability/context.py:54]

## Dev Notes

### Escopo desta story

- Implementar a base local/testável para propagar contexto confiável entre microsserviços por metadata gRPC e por atributos CloudEvents.
- Esta story não precisa criar servidor gRPC real em produção, service mesh, NATS real, outbox/inbox persistente, novos microsserviços nem autenticação real de workload.
- A entrega deve produzir primitives, adapters ou factories reutilizáveis por futuras bordas HTTP/gRPC/eventos, mantendo domínio livre de frameworks.
- O objetivo não é revalidar token OAuth em cada hop; é transportar contexto já autenticado/autorizado por bordas confiáveis e validar formato/tenant antes do caso de uso.

### Regras de arquitetura obrigatórias

- Backend segue DDD + arquitetura hexagonal: `domain` não importa gRPC, NATS, CloudEvents SDK, OpenTelemetry, FastAPI, Pydantic de borda ou banco.
- Comunicação síncrona interna usa gRPC; comunicação assíncrona usa NATS JetStream com CloudEvents/AsyncAPI.
- `Identity & Tenant` é dono de tenants, clientes técnicos, roles, scopes, claims e contexto confiável; outros serviços não inventam identidade própria.
- Payload de negócio nunca é fonte de verdade para `tenant_id`, sujeito, scopes ou autorização.
- Produção exigirá identidade de workload/mTLS via mesh conforme AD-17, mas esta story deve ficar substituível e testável sem Istio/EKS.
- Não adicionar nova tecnologia ou dependência se helpers puros com `Mapping[str, str]` e `Sequence[tuple[str, str]]` resolverem o MVP.

### Convenção proposta para gRPC metadata

- Usar somente chaves ASCII lower-case e valores string ASCII seguros.
- Campos de rastreabilidade já existentes:
  - `x-correlation-id`
  - `x-request-id`
  - `traceparent`
- Campos de contexto CreditOS:
  - `x-creditos-tenant-id`
  - `x-creditos-tenant-isolation-tier`
  - `x-creditos-subject-id`
  - `x-creditos-client-id` quando aplicável
  - `x-creditos-principal-type`
  - `x-creditos-scopes` com scopes separados por espaço
  - `x-creditos-roles` opcional, separado por espaço
- Não propagar `Authorization`, bearer token, `token_id`/`jti`, segredo, claims brutas, CPF/CNPJ, e-mail completo ou payload de proposta.
- `traceparent` é a forma canônica de trace distribuído; o `trace_id` pode ser extraído dele pelo `ObservabilityContext`.

### Convenção proposta para CloudEvents

- Manter core CloudEvents: `specversion`, `id`, `source`, `type`, `subject`, `time`, `datacontenttype`, `dataschema` quando houver e `data`.
- Usar extensões válidas, sem underscore e curtas:
  - `tenantid`
  - `tenanttier`
  - `subjectid`
  - `clientid`
  - `principaltype`
  - `scopes`
  - `roles`
  - `correlationid`
  - `requestid`
  - `traceparent`
  - `schemaversion`
  - `idempotencykey` quando aplicável
- `data` deve conter apenas dados mínimos de domínio já permitidos pelo contrato do evento; contexto de segurança/rastreabilidade fica em atributos.
- Consumidores devem tratar ausência ou formato inválido de contexto como falha controlada antes do caso de uso.

### Padrões herdados das Stories 1.2 e 1.3

- `AuthenticatedClientContext` e `ResolvedM2MTenantContext` já carregam `client_id`, `subject`, `scopes`, `tenant_id`, `tenant_isolation_tier`, `issuer`, `audience` e `token_id`; não propagar `token_id`.
- `AuthorizationSubject.from_resolved_tenant_context` já cria sujeito autorizável a partir de contexto confiável e valida principal/tier/scopes.
- `AuthorizationOperationRegistry` impede requisitos autodeclarados; futuras bordas devem chamar `AuthorizedOperationFacade` antes de operações sensíveis.
- Logs de autorização usam `source=authorization-context`; logs M2M usam `source=m2m-token-context`; esta story deve escolher fonte específica para propagação, por exemplo `source=trusted-context`.
- Falha de logging permanece best-effort e não altera resultado de autenticação/autorização.
- Em falhas de parsing/metadata, limpar `tenant_id` e `tenant_isolation_tier` recebidos de fonte ainda não validada.

### Arquivos prováveis

- Preferir criar ou alterar:
  - `packages/security/src/creditos_security/context.py` ou nome equivalente para modelo técnico de contexto propagável.
  - `packages/observability/src/creditos_observability/context.py` para integração com carriers existentes, se necessário.
  - `services/identity-tenant/src/creditos_identity_tenant/application/security.py` para factories de conversão, se a responsabilidade ficar no serviço.
  - `services/identity-tenant/src/creditos_identity_tenant/adapters/grpc/...` para adapter/facade local de metadata gRPC.
  - `services/identity-tenant/src/creditos_identity_tenant/adapters/events/...` para helpers CloudEvents locais.
  - `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` somente se houver mudança contratual additive.
  - `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` somente se novos atributos virarem contrato.
  - testes em `packages/*/tests` ou `services/identity-tenant/tests/unit|integration`.
- Não mover estruturas existentes nem criar domínio compartilhado em `packages/`.
- Não adicionar `grpcio`, CloudEvents SDK ou NATS client nesta story sem justificativa explícita; a base atual ainda não depende de `grpcio`.

### Contratos e compatibilidade

- `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` é contrato gRPC estrutural existente e não deve sofrer breaking change.
- Metadata gRPC normalmente não exige alterar mensagens protobuf; se a implementação só padronizar metadata, documentar isso no README/story.
- Se campos forem adicionados ao proto, usar números novos, preservar campos existentes e manter `compatibility = "backward-compatible"` no catálogo.
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` já exige `tenantid`, `correlationid`, `idempotencykey`, `schemaversion` e `traceparent`; qualquer novo atributo obrigatório deve ser avaliado contra compatibilidade.
- `scripts/check_contracts.py` deve continuar passando com 4 contratos ou com catálogo atualizado de forma consistente.

### Observabilidade, privacidade e segurança

- Logs devem conter `correlation_id`, `request_id`, `trace_id`, serviço, versão, ambiente, operação, origem, destino, contrato, status, duração e tenant somente quando confiável.
- Métricas técnicas com `tenant_id` exigem controle de cardinalidade; métricas customer-facing futuras devem vir de projeções de negócio, não de telemetria bruta.
- Payload sensível bruto é proibido em metadata, CloudEvents, logs, traces e erros.
- Contexto propagado deve ser minimizado: transportar o necessário para autorização/rastreabilidade, não claims completas nem tokens.
- Rejeições devem usar erros seguros com `code`, `safe_message` e `grpc_status`/equivalente, preservando o padrão de `TenantDomainError`.

### Testes obrigatórios

- Unitários para modelo de contexto propagável: criação válida, campos ausentes, tipos inválidos, strings com whitespace/control chars, scopes/roles malformados e limites de tamanho.
- Unitários para gRPC metadata: serialização, parsing, case normalization, `traceparent`, ausência de tenant, ausência de scopes, valores não ASCII/binários e não vazamento de token.
- Unitários para CloudEvents: atributos válidos, extensões sem underscore, ausência de campos obrigatórios, `traceparent` inválido, `tenanttier` inválido e `data` sem payload sensível.
- Integração no `TenantApplicationService` ou adapter local: derivar contexto de M2M/autorização e validar antes de autorizar operação sensível.
- Regressão completa antes de review: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `scripts/check_contracts.py` e `uv lock --check`.

### Pesquisa técnica atualizada

- gRPC Python representa metadata como sequência de pares; chaves são `str` ASCII válidas para header HTTP, valores podem ser ASCII ou bytes, e valores bytes exigem chave com sufixo `-bin`. Nesta story, usar apenas strings ASCII.
- CloudEvents v1.0.2 restringe nomes de atributos a letras minúsculas ASCII e dígitos, recomenda nomes descritivos/curtos e não permite underscore; por isso usar `tenantid`, não `tenant_id`.
- OpenTelemetry Python recomenda propagação de contexto via W3C Trace Context; o projeto já usa `traceparent` em `ObservabilityContext.to_carrier`.
- W3C Trace Context define `traceparent` como cabeçalho/valor padrão para identificar requisições em sistemas distribuídos.

### Referências

- `_bmad-output/planning-artifacts/epics.md` — NFR-8, NFR-23, NFR-28 e Story 1.4.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-4, AD-5, AD-6, AD-7, AD-16 e AD-17.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/autenticacao-autorizacao-oq7.md` — propagação interna por metadata gRPC e eventos.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/eventos-mensageria-oq12.md` — CloudEvents, NATS JetStream, outbox/inbox e envelope mínimo.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md` — OpenTelemetry, dashboards e minimização.
- `_bmad-output/implementation-artifacts/1-2-autenticacao-m2m-com-resolucao-de-tenant.md` — contexto M2M e logs seguros.
- `_bmad-output/implementation-artifacts/1-3-autorizacao-por-rbac-scopes-e-claims-de-tenant.md` — autorização local, registry e fachada.
- `packages/observability/src/creditos_observability/context.py` — carriers atuais de observabilidade.
- `packages/observability/src/creditos_observability/logging.py` — logs estruturados e mascarados.
- `packages/security/src/creditos_security/masking.py` — mascaramento e HMAC.
- `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto` — contrato gRPC interno estrutural.
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json` — contrato AsyncAPI/CloudEvents estrutural.
- gRPC Python metadata docs: https://grpc.github.io/grpc/python/glossary.html
- CloudEvents v1.0.2 spec: https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md
- OpenTelemetry Python propagation: https://opentelemetry.io/docs/languages/python/propagation/
- W3C Trace Context: https://www.w3.org/TR/trace-context/

## Dev Agent Record

### Agent Model Used

Codex

### Debug Log References

- 2026-08-11 — `bmad-create-story` executado para detalhar Story 1.4 antes da implementação.
- 2026-08-11 — Branch `agent/story-1-4-propagacao-contexto-confiavel` criada no início da Story 1.4.
- 2026-08-11 — `CTOS-26` movida para WIP no Jira antes do detalhamento, conforme fluxo acordado.
- 2026-08-11 — Subtarefas `CTOS-128` a `CTOS-134` criadas no Jira para execução rastreável.
- 2026-08-11 — `CTOS-128`, `CTOS-129`, `CTOS-130`, `CTOS-131`, `CTOS-132` e `CTOS-133` movidas para concluído conforme avanço.
- 2026-08-11 — `uv` não estava disponível no PATH; validações foram executadas pela `.venv` e o teste do `scripts/dev harness-check` foi validado com shim temporário em `/tmp/creditos-uv-shim`.
- 2026-08-12 — `bmad-code-review` executado com Blind Hunter, Edge Case Hunter e Acceptance Auditor; 11 achados de patch e 1 dismissed registrados.
- 2026-08-12 — 11 achados de patch aplicados; `CTOS-26` movida para WIP durante correção e pronta para retorno a review.
- 2026-08-12 — `uv` seguia indisponível no PATH; suíte completa validada com shim temporário em `/tmp/creditos-uv-shim`, sem alterar o repositório.

### Completion Notes List

- 2026-08-11 — Story 1.4 criada como guia de implementação com status `ready-for-dev`.
- 2026-08-11 — Contexto de Epic 1, Stories 1.2/1.3, Architecture Spine, PRD OQ-7/OQ-9/OQ-12, contratos existentes e documentação técnica oficial analisados.
- 2026-08-11 — Registradas convenções propostas de metadata gRPC e extensões CloudEvents sem implementar código.
- 2026-08-11 — Jira sincronizado com `CTOS-26` em WIP e subtarefas `CTOS-128` a `CTOS-134` em TODO.
- 2026-08-11 — Implementado `TrustedContext`/`PropagatedContext` com validação estrita de tenant, tier, sujeito, principal, scopes, roles, correlação, request ID, `traceparent`, schema version e bloqueio de CPF/CNPJ em identificadores propagados.
- 2026-08-11 — Implementados helpers puros para serializar/parsear metadata gRPC e atributos CloudEvents, sem adicionar `grpcio`, SDK CloudEvents ou cliente NATS.
- 2026-08-11 — Integrados adapters locais do `Identity & Tenant Service` para derivar contexto propagável de `AuthorizationSubject` e `ResolvedM2MTenantContext`, sem propagar `token_id`.
- 2026-08-11 — Atualizados contratos/documentação: protobuf preservado com metadata gRPC documentada, AsyncAPI ampliado de forma aditiva e READMEs com convenções seguras.
- 2026-08-11 — Gates verdes: testes focados `48 passed`; suíte completa `121 passed`; `ruff check .`; `ruff format --check .`; `pyright`; `scripts/check_contracts.py`.
- 2026-08-12 — Review adversarial corrigido: metadata duplicada, chaves sensíveis desconhecidas, CPF/CNPJ embutido, `idempotencykey`, required AsyncAPI, tenant esperado, envelope CloudEvents, logging seguro, acoplamento adapter→adapter e carrier `x-creditos-*`.
- 2026-08-12 — Gates finais verdes: testes focados `75 passed`; suíte completa `124 passed`; `ruff check .`; `ruff format --check .`; `pyright`; `scripts/check_contracts.py`.

### Implementation Plan

- Primitivas técnicas compartilhadas ficam em `packages/security`, sem domínio de produto e sem dependências externas.
- Adapters do `Identity & Tenant Service` convertem fontes confiáveis existentes para carriers gRPC/CloudEvents e validam entrada antes de reconstruir sujeito autorizável.
- Contratos permanecem backward-compatible: metadata gRPC não altera mensagens protobuf e novos atributos AsyncAPI são opcionais.
- Segurança por minimização: tokens, `token_id`, `Authorization`, payload bruto, CPF/CNPJ e e-mail completo são rejeitados ou omitidos.

### File List

- `_bmad-output/implementation-artifacts/1-4-propagacao-de-contexto-confiavel-entre-servicos.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `packages/contracts/asyncapi/events/proposal/v1/asyncapi.json`
- `packages/contracts/protobuf/internal/identity-tenant/v1/tenant_context.proto`
- `packages/security/README.md`
- `packages/security/src/creditos_security/__init__.py`
- `packages/security/src/creditos_security/context.py`
- `packages/security/tests/unit/test_cloudevent_context.py`
- `packages/security/tests/unit/test_grpc_context_metadata.py`
- `packages/security/tests/unit/test_trusted_context.py`
- `packages/observability/src/creditos_observability/context.py`
- `tests/test_observability_foundation.py`
- `services/identity-tenant/README.md`
- `services/identity-tenant/src/creditos_identity_tenant/application/trusted_context.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/events/trusted_context.py`
- `services/identity-tenant/src/creditos_identity_tenant/adapters/grpc/trusted_context.py`
- `services/identity-tenant/tests/unit/test_trusted_context_adapters.py`

### Change Log

- 2026-08-11 — Story 1.4 implementada com contexto confiável propagável por gRPC metadata e CloudEvents, adapters do Identity & Tenant, contratos/documentação e regressões de segurança.
- 2026-08-12 — Achados do code review aplicados e Story 1.4 marcada como `done`.
