---
baseline_commit: 774e1ed6e7ffe28a491fb936524292a3aaaca8f5
jira_issue: CTOS-20
branch: agent/story-0-5-observability-logs-security
---

# Story 0.5: Observabilidade, Logs e Segurança Base

Status: done

## Story

Como equipe de operação,
quero uma base transversal de logs, métricas, tracing, correlation ID e mascaramento,
para que novos serviços já nasçam rastreáveis e seguros por padrão.

## Acceptance Criteria

1. **Given** uma requisição HTTP, chamada gRPC ou mensagem assíncrona de exemplo, **when** ela é processada, **then** logs estruturados incluem tenant quando aplicável, correlation ID, trace ID, origem, destino, contrato, status e latência, **and** CPF, CNPJ, e-mail, tokens, secrets, documentos, payloads sensíveis e dados financeiros detalhados não aparecem completos.
2. **Given** um serviço instrumentado, **when** ele executa fluxo mínimo, **then** emite métricas e traces via OpenTelemetry, **and** health/readiness indicam estado operacional sem expor detalhes internos sensíveis.

## Tasks / Subtasks

- [x] CTOS-90 — Definir a base transversal de observabilidade e segurança (AC: 1, 2)
  - [x] Criar ou preparar pacote compartilhado permitido em `packages/observability`.
  - [x] Criar ou preparar pacote compartilhado permitido em `packages/security` quando a separação de mascaramento/hash justificar.
  - [x] Garantir que os pacotes compartilhados contenham apenas utilidades técnicas genéricas, sem entidades, regras ou repositories de domínio.
- [x] CTOS-91 — Implementar contexto de rastreabilidade e logs estruturados (AC: 1)
  - [x] Padronizar `correlation_id`, `trace_id`, `request_id`, `tenant_id` opcional, `tenant_isolation_tier` opcional, origem, destino, contrato, status e duração.
  - [x] Criar helpers/middleware/interceptors de exemplo para HTTP, gRPC e mensagens assíncronas sem acoplar domínio.
  - [x] Garantir que chamadas internas, externas e eventos possam propagar contexto confiável.
- [x] CTOS-92 — Implementar mascaramento obrigatório de dados sensíveis (AC: 1)
  - [x] Mascarar ou omitir CPF, CNPJ, e-mail, telefone, tokens, secrets, documentos, imagens, payloads sensíveis e dados financeiros detalhados.
  - [x] Evitar logs de payload bruto por padrão.
  - [x] Usar máscara forte como padrão para logs, traces, dashboards, telemetria e respostas operacionais.
- [x] CTOS-93 — Instrumentar métricas e traces mínimos via OpenTelemetry (AC: 2)
  - [x] Emitir métricas de contagem, duração e status para fluxo mínimo de exemplo.
  - [x] Emitir trace/span com atributos técnicos de baixa cardinalidade.
  - [x] Não incluir dados pessoais, payloads sensíveis ou identificadores completos em atributos de trace/métrica.
- [x] CTOS-94 — Padronizar health/readiness seguros (AC: 2)
  - [x] Expor exemplos ou helpers que retornem estado operacional sem credenciais, stack traces, payloads, nomes internos sensíveis ou detalhes excessivos.
  - [x] Diferenciar health de readiness conforme capacidade operacional mínima.
  - [x] Manter compatibilidade com o harness local da Story 0.4 quando aplicável.
- [x] CTOS-95 — Criar validações automatizadas e atualizar documentação (AC: 1, 2)
  - [x] Adicionar testes para logs estruturados, propagação de contexto e ausência de vazamento de dados sensíveis.
  - [x] Adicionar testes para mascaramento forte e casos comuns de CPF, CNPJ, e-mail, token/secret e payload sensível.
  - [x] Adicionar smoke tests para métricas/traces OpenTelemetry sem backend externo real.
  - [x] Atualizar documentação operacional com campos obrigatórios, exemplos seguros e anti-padrões.
  - [x] Executar `./scripts/dev all` ao final.
  - [x] Manter `CTOS-20` e subtasks sincronizados no Jira durante desenvolvimento, revisão e conclusão.

### Review Findings

- [x] [Review][Patch] `tenant_id` pode ser aceito de carrier/header sem fronteira confiável [packages/observability/src/creditos_observability/context.py:35]
- [x] [Review][Patch] `traceparent` é gerado com span id inválido e validação fraca de trace ID [packages/observability/src/creditos_observability/context.py:61]
- [x] [Review][Patch] Métricas aceitam atributos arbitrários e de alta cardinalidade [packages/observability/src/creditos_observability/telemetry.py:98]
- [x] [Review][Patch] Spans podem registrar exceções com dados sensíveis automaticamente [packages/observability/src/creditos_observability/telemetry.py:55]
- [x] [Review][Patch] Campos canônicos de log podem ser sobrescritos por `extra` [packages/observability/src/creditos_observability/logging.py:49]
- [x] [Review][Patch] Detecção de chaves sensíveis é frágil para nomes parciais ou camelCase [packages/security/src/creditos_security/masking.py:68]
- [x] [Review][Patch] Valores binários podem passar sem omissão no mascaramento recursivo [packages/security/src/creditos_security/masking.py:86]
- [x] [Review][Patch] Readiness aceita truthiness e pode expor nomes internos de dependências [packages/observability/src/creditos_observability/health.py:25]
- [x] [Review][Patch] Faltam helpers ou exemplos testados para HTTP, gRPC e mensagens assíncronas [packages/observability/src/creditos_observability/logging.py:11]
- [x] [Review][Patch] Log estruturado não suporta `error_type` seguro quando aplicável [packages/observability/src/creditos_observability/logging.py:11]
- [x] [Review][Patch] Duração e status aceitam valores inválidos em logs/métricas [packages/observability/src/creditos_observability/logging.py:23]

## Dev Notes

### Escopo da Story

- Esta story cria a fundação transversal de observabilidade, logs e proteção de dados para os próximos microsserviços.
- O foco é biblioteca/padrão reutilizável e exemplos mínimos, não dashboards completos, SLOs finais, pipeline de produção, auditoria oficial append-only ou telemetria customer-facing.
- A observabilidade de negócio e dashboards para clientes continuam pertencendo ao `Reporting & Insights Service` por eventos/projeções, conforme Epic 7.
- Auditoria oficial, evidências imutáveis, hash encadeado e retenção regulatória detalhada ficam para Epic 6.

### Requisitos Técnicos Obrigatórios

- Runtime: Python 3.13.
- Gerenciador: `uv` workspace com `uv.lock` único.
- Qualidade local: `./scripts/dev all` continua sendo o gate principal.
- OpenTelemetry Python é o padrão obrigatório de instrumentação para métricas, traces e propagação de contexto.
- Logs estruturados devem ser emitidos antes de qualquer persistência ou envio para backend, já com dados sensíveis mascarados/omitidos.
- `tenant_id` deve aparecer em logs/traces/métricas somente quando aplicável e com controle de cardinalidade.
- Domínio permanece puro: `domain` não importa FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, Redis, OpenTelemetry, provedores externos ou Kubernetes.
- Bibliotecas compartilhadas em `packages/` continuam restritas a contratos, observabilidade, segurança, testes e utilidades técnicas genéricas.

### Arquitetura e Guardrails

- Seguir AD-5: `tenant_id` confiável vem de autenticação/contexto, nunca do payload de negócio sem validação.
- Seguir AD-6: contexto confiável propaga por gRPC metadata e CloudEvents; payload de negócio não é fonte de verdade de identidade ou tenant.
- Seguir AD-7: todos os componentes devem nascer com logs estruturados, métricas, traces, health checks, readiness checks, correlation ID e trace ID.
- Seguir AD-9: máscara forte é padrão para logs, traces, dashboards, telemetria e respostas operacionais; CPF/CNPJ/e-mail visíveis não podem ser dependência operacional.
- Seguir AD-16: OpenTelemetry fica em adapters, middleware, interceptors, bootstrap ou utilidades técnicas; nunca em regras de domínio.
- Não criar stack completa de Grafana/Prometheus/Loki/Tempo nesta story, salvo se for estritamente necessário para smoke local; essa materialização pertence a stories posteriores de observabilidade/infra.
- Não criar fornecedor nominal de observabilidade, APM ou SIEM sem justificativa, alternativa e consequência.

### Estrutura Esperada

```text
packages/
  observability/
    README.md
    pyproject.toml
    src/creditos_observability/
      __init__.py
      context.py
      logging.py
      metrics.py
      tracing.py
      health.py
  security/
    README.md
    pyproject.toml
    src/creditos_security/
      __init__.py
      masking.py
tests/
  test_observability_foundation.py
  test_sensitive_data_masking.py
docs/
  observability.md
```

A estrutura final pode variar se a implementação justificar opção mais simples, mas deve preservar a separação entre observabilidade técnica e segurança de mascaramento quando isso reduzir acoplamento.

### Padrão Mínimo de Log Estruturado

Campos mínimos esperados quando aplicáveis:

- `timestamp` em UTC.
- `service.name`, `service.version` e `deployment.environment`.
- `tenant_id` e `tenant_isolation_tier` quando houver contexto confiável.
- `correlation_id`, `trace_id` e `request_id`.
- `operation`, `source`, `destination`, `contract`, `contract_version`.
- `status`, `status_code`, `error_type` seguro e `duration_ms`.
- `idempotency_key` somente quando aplicável e, se puder ser sensível ou enumerável, mascarada ou hasheada.

### Regras de Mascaramento

- CPF em logs/traces/dashboards: `***.***.***-09` ou omissão.
- CNPJ em logs/traces/dashboards: `**.***.***/****-90` ou omissão.
- E-mail em logs/traces/dashboards: `j***@dominio.com` ou omissão.
- Token, senha, secret, API key: nunca logar.
- Documento/imagem: nunca logar conteúdo; usar referência segura ou hash permitido.
- Renda/dado financeiro detalhado: usar bucket/faixa ou omissão.
- Payload externo sensível: omitir por padrão; snapshots minimizados só em contexto autorizado futuro.
- Hash simples/sem chave para CPF, CNPJ e e-mail é proibido por risco de enumeração.

### Pesquisa Técnica Atual

- A documentação oficial atual de OpenTelemetry Python informa suporte a Python 3.10+ e geração/coleta de métricas, logs e traces.
- Em OpenTelemetry Python, traces e métricas estão estáveis; logs ainda aparecem com status de desenvolvimento, então a implementação deve usar logs estruturados seguros como contrato próprio e tratar integração de logs via OTel/Collector como evolução cautelosa.
- A versão mais recente publicada do `opentelemetry-sdk` observada em 2026-08-03 é `1.44.0`, publicada em 2026-07-16 no PyPI.
- Decisão recomendada para implementação: usar `opentelemetry-api`/`opentelemetry-sdk` para métricas/traces e manter logs estruturados com biblioteca padrão Python ou helper próprio; isso reduz risco de depender de API de logs ainda em evolução.
- Alternativa: usar apenas logs/contadores próprios sem OpenTelemetry nesta story; consequência: violaria AD-7/NFR-28 e deixaria tracing distribuído para depois.
- Alternativa: adicionar stack completa Collector/Prometheus/Loki/Tempo agora; consequência: aumenta escopo e fragilidade antes de CI/infra, portanto deve ficar fora desta story.

### Testing Requirements

- Testar que logs de exemplo possuem campos obrigatórios e formato estruturado.
- Testar que correlation ID e trace ID são gerados/propagados quando ausentes ou presentes.
- Testar mascaramento/omissão para CPF, CNPJ, e-mail, telefone, tokens, secrets, documentos e dados financeiros detalhados.
- Testar que payload bruto não aparece em log gerado por fluxo mínimo.
- Testar smoke de métricas e traces OpenTelemetry sem exigir Collector, Prometheus, Loki, Tempo ou rede externa.
- Testar health/readiness seguros, sem vazamento de configuração, credenciais, stack traces ou detalhes internos sensíveis.
- Executar `./scripts/dev all` ao final da implementação.

### Previous Story Intelligence

- Story 0.1 criou `uv`, Python 3.13, Ruff, Pyright, pytest, `scripts/dev` e `./scripts/dev all`.
- Story 0.2 criou `services/service-template` com `domain`, `application`, `adapters` e `bootstrap`, além de guardrails contra dependência indevida no domínio.
- Story 0.3 criou `packages/contracts`, catálogo versionado e checks de contrato; novos contratos devem preservar versão, owner, compatibilidade e política de breaking change.
- Story 0.4 criou harness local em Python stdlib, comandos `./scripts/dev harness-up` e `./scripts/dev harness-check`, health/readiness seguros e mocks sem credenciais externas.
- Story 0.4 demonstrou que validações com Python stdlib são preferíveis quando atendem ao objetivo, mas esta story pode exigir dependências OpenTelemetry por decisão arquitetural aprovada.

### Anti-Patterns a Evitar

- Registrar payload bruto, CPF/CNPJ/e-mail completos, tokens, secrets, renda detalhada, documentos ou imagens em logs, traces, métricas, erros ou docs.
- Colocar instrumentação OpenTelemetry dentro de `domain`.
- Criar métricas com cardinalidade explosiva, especialmente por CPF, e-mail, proposal_id livre, payload, erro bruto ou tenant sem controle.
- Criar dashboards customer-facing lendo diretamente Prometheus, Loki, Tempo, logs crus ou traces crus.
- Usar dados reais em testes, fixtures, exemplos ou documentação.
- Tratar logs operacionais como auditoria oficial append-only.
- Expandir escopo para service mesh, dashboards completos, IaC ou CI final.

## References

- `_bmad-output/planning-artifacts/epics.md` — Epic 0 e Story 0.5.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md` — FR-21, NFR-9, NFR-21, NFR-28, NFR-29 e NFR-30.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md` — decisão OQ-9, dashboards e requisitos verificáveis.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md` — política de máscaras, retenção e descarte.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-5, AD-6, AD-7, AD-9 e AD-16.
- `_bmad-output/implementation-artifacts/0-1-bootstrap-do-monorepo-python.md` — tooling local e comandos `./scripts/dev`.
- `_bmad-output/implementation-artifacts/0-2-template-base-de-microsservico-ddd-e-hexagonal.md` — template de serviço e guardrails DDD/hexagonal.
- `_bmad-output/implementation-artifacts/0-3-estrutura-base-de-contratos-versionados.md` — contratos versionados.
- `_bmad-output/implementation-artifacts/0-4-harness-local-com-dependencias-mockadas.md` — harness local, health/readiness e mocks seguros.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — rastreamento BMAD.
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
- OpenTelemetry Python Instrumentation: https://opentelemetry.io/docs/languages/python/instrumentation/
- PyPI `opentelemetry-sdk`: https://pypi.org/project/opentelemetry-sdk/

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- `UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv run pytest tests/test_sensitive_data_masking.py tests/test_observability_foundation.py` — ciclo vermelho inicial falhou por ausência dos pacotes `creditos_security` e `creditos_observability`.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv lock` — lock atualizado com `creditos-observability`, `creditos-security`, `opentelemetry-api`, `opentelemetry-sdk` e `opentelemetry-semantic-conventions`.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv sync --locked` — workspace sincronizado com dependências da Story 0.5.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv run pytest tests/test_sensitive_data_masking.py tests/test_observability_foundation.py` — validação específica verde com 7 testes.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` — primeira execução em sandbox confirmou lint, format, Pyright e contratos verdes, mas harness local falhou por bloqueio de socket do sandbox.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` — execução final fora do sandbox verde com 32 testes.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` — repetição pós-atualização BMAD verde com 32 testes.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv run pytest tests/test_sensitive_data_masking.py tests/test_observability_foundation.py` — patches de review verdes com 11 testes focados.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv run ruff check . --fix && UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv run ruff format . && UV_CACHE_DIR=/tmp/creditos-uv-cache /tmp/creditos-tools/local/bin/uv run pyright` — lint, format e Pyright verdes após patches.
- `UV_CACHE_DIR=/tmp/creditos-uv-cache PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` — gate completo pós-code-review verde com 36 testes.

### Completion Notes List

- Criado `creditos-security` com mascaramento forte recursivo, omissão de payloads/secrets/documentos e HMAC-SHA256 com chave para identificadores enumeráveis.
- Criado `creditos-observability` com contexto de rastreabilidade, logs estruturados seguros, health/readiness seguros e telemetria em memória via OpenTelemetry SDK.
- Adicionados testes para ausência de vazamento de CPF, CNPJ, e-mail, telefone, tokens, secrets, payloads e dados financeiros detalhados.
- Adicionados smoke tests de métricas e traces OpenTelemetry sem depender de Collector, Prometheus, Loki, Tempo ou rede externa.
- Atualizada documentação operacional em `docs/observability.md`.
- Gate completo `./scripts/dev all` executado com sucesso: lock, sync, Ruff, format, Pyright, contratos, harness local e pytest.
- Resolvidos 11 achados do code review: fronteira confiável de tenant, traceparent válido, allowlist de métricas, exceções em spans sem gravação automática, extras de log isolados, chaves sensíveis parciais/camelCase, binários omitidos, readiness estrito/seguro, helpers HTTP/gRPC/CloudEvents, `error_type` seguro e validação de duração/status.

### File List

- `_bmad-output/implementation-artifacts/0-5-observabilidade-logs-e-seguranca-base.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/observability.md`
- `packages/observability/README.md`
- `packages/observability/pyproject.toml`
- `packages/observability/src/creditos_observability/__init__.py`
- `packages/observability/src/creditos_observability/context.py`
- `packages/observability/src/creditos_observability/health.py`
- `packages/observability/src/creditos_observability/logging.py`
- `packages/observability/src/creditos_observability/telemetry.py`
- `packages/security/README.md`
- `packages/security/pyproject.toml`
- `packages/security/src/creditos_security/__init__.py`
- `packages/security/src/creditos_security/masking.py`
- `pyproject.toml`
- `tests/test_contracts_structure.py`
- `tests/test_observability_foundation.py`
- `tests/test_sensitive_data_masking.py`
- `uv.lock`

### Change Log

- 2026-08-03 — Story 0.5 iniciada, branch criada e card Jira movido para WIP.
- 2026-08-03 — Implementada base transversal de observabilidade, logs estruturados, mascaramento, health/readiness e OpenTelemetry; story marcada para revisão.
- 2026-08-03 — Resolvidos achados do code review e story marcada como concluída.
