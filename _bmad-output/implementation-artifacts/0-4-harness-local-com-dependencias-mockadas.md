---
baseline_commit: 482625cb58c54ec7cfe15b3a09cd2278ebca1147
jira_issue: CTOS-19
branch: agent/story-0-4-local-mocked-harness
---

# Story 0.4: Harness Local com Dependências Mockadas

Status: done

## Story

Como desenvolvedor,
quero executar localmente um conjunto mínimo de serviços e dependências mockadas,
para que o fluxo técnico básico seja validado antes das histórias de produto.

## Acceptance Criteria

1. **Given** um ambiente local configurado, **when** a equipe executa o comando de subida local documentado, **then** dependências essenciais do desenvolvimento sobem de forma reproduzível, **and** serviços de exemplo expõem health check, readiness check e endpoint ou handler mínimo.
2. **Given** integrações externas ainda sem fornecedor real, **when** o harness local executa cenários de integração, **then** usa mocks/sandbox controlados, **and** não exige credenciais reais, dados pessoais reais ou acesso a provedores externos.

## Tasks / Subtasks

- [x] Definir o harness local mínimo (AC: 1)
  - [x] Criar estrutura em `infra/local/` para composição local reprodutível.
  - [x] Documentar comando único de subida, parada e validação local.
  - [x] Não exigir credenciais reais, provedores externos ou dados pessoais reais.
- [x] Materializar dependências mockadas essenciais (AC: 1, 2)
  - [x] Incluir mock/sandbox controlado para integrações externas ainda sem fornecedor definido.
  - [x] Representar dependência assíncrona local de forma compatível com a direção NATS JetStream quando aplicável.
  - [x] Evitar criar fornecedor nominal ou adapter real nesta story.
- [x] Expor serviço de exemplo mínimo (AC: 1)
  - [x] Reusar o `services/service-template` como referência estrutural, sem criar domínio de produto definitivo.
  - [x] Expor health check e readiness check sem vazar detalhes sensíveis.
  - [x] Expor endpoint ou handler mínimo para validar que o harness está operável.
- [x] Criar validações automatizadas (AC: 1, 2)
  - [x] Adicionar testes que validem comandos/documentação do harness e ausência de credenciais reais.
  - [x] Integrar a validação ao fluxo local existente quando fizer sentido.
  - [x] Executar `./scripts/dev all` ao final.
- [x] Atualizar documentação e rastreamento (AC: 1, 2)
  - [x] Atualizar `README.md` ou documentação específica com instruções locais.
  - [x] Atualizar `sprint-status.yaml` para `in-progress`, depois `review` ao concluir implementação.
  - [x] Manter `CTOS-19` sincronizado no Jira durante desenvolvimento, revisão e conclusão.

### Review Findings

- [x] [Review][Patch] Requisições POST malformadas ou grandes demais podem derrubar a conexão em vez de retornar erro estruturado [scripts/local_harness.py:50]
- [x] [Review][Patch] Falhas nas dependências mockadas podem derrubar readiness/endpoint mínimo em vez de retornar `503` seguro [scripts/local_harness.py:160]
- [x] [Review][Patch] Mock assíncrono aceita CloudEvents incompletos ou com campos obrigatórios vazios [scripts/local_harness.py:123]
- [x] [Review][Patch] `--host` aceita bind não-loopback e pode gerar URL cliente inválida para `0.0.0.0` [scripts/local_harness.py:321]
- [x] [Review][Patch] Portas inválidas via variáveis de ambiente falham antes do tratamento amigável de erro [scripts/local_harness.py:324]
- [x] [Review][Patch] Testes não exercitam o comando documentado `./scripts/dev harness-check` [tests/test_local_harness.py:50]

## Dev Notes

### Escopo da Story

- Esta story cria um harness local técnico; não implementa fluxo real de análise de crédito.
- O harness deve permitir validar o esqueleto operacional antes dos serviços de produto.
- Mocks/sandboxes são obrigatórios para integrações externas sem fornecedor real.
- O resultado deve ser útil para desenvolvimento local e testes automatizados, não para produção.

### Requisitos Técnicos Obrigatórios

- Runtime: Python 3.13.
- Gerenciador: `uv` workspace com `uv.lock` único.
- Qualidade local: `./scripts/dev all` continua sendo o gate principal.
- Backend segue DDD + arquitetura hexagonal: `domain` não importa FastAPI, Pydantic de borda, SQLAlchemy, Alembic, gRPC, NATS, Redis, OpenTelemetry, provedores externos ou Kubernetes.
- Bibliotecas compartilhadas em `packages/` continuam restritas a contratos, observabilidade, segurança, testes e utilidades técnicas genéricas.
- APIs públicas futuras usam FastAPI/OpenAPI; chamadas internas síncronas usam gRPC/protobuf; fluxos assíncronos usam NATS JetStream/CloudEvents/AsyncAPI.
- Integrações externas críticas devem ser assíncronas internamente, com idempotência, timeout/deadline, retry seguro, DLQ ou equivalente, rastreabilidade e resultado canônico.
- Exemplos, fixtures e documentação não podem conter CPF, CNPJ, e-mail real, tokens, secrets, dados financeiros reais ou payload sensível completo.

### Arquitetura e Guardrails

- Não criar monólito, domínio compartilhado ou serviço de produto definitivo nesta story.
- Não selecionar fornecedor externo nominal; o MVP trabalha com classes de integração, adapters substituíveis e mocks/sandbox.
- Não adicionar tecnologia nova de orquestração, broker, banco ou observabilidade sem justificativa, alternativa e consequência.
- Se Docker Compose for usado como harness local, ele deve ficar isolado em `infra/local/` e não representar topologia final de produção.
- Se um mock HTTP for criado, ele deve ser explicitamente identificado como mock/sandbox e não deve simular contrato proprietário de fornecedor real.
- Se NATS local for incluído, ele deve ser dependência de desenvolvimento para validar integração assíncrona, não uma configuração de HA/DR de produção.
- Health/readiness devem indicar estado operacional mínimo sem expor configuração sensível, credenciais, stack trace ou dados internos.

### Estrutura Esperada

```text
infra/
  local/
    README.md
    docker-compose.yaml ou alternativa documentada
    .env.example
scripts/
  dev
services/
  service-template/
tests/
  ...
```

A estrutura final pode variar se a implementação justificar opção mais simples, mas deve preservar localização em `infra/local/` para harness e não misturar dependências locais com contratos ou domínio.

### Testing Requirements

- Validar que o harness local é documentado com comandos de subida, parada e verificação.
- Validar que arquivos de exemplo usam placeholders e não segredos reais.
- Validar que mocks/sandboxes não exigem acesso externo.
- Validar que health/readiness/endpoint ou handler mínimo existem ou são testáveis sem infraestrutura externa real.
- Executar `./scripts/dev all` ao final da implementação.

### Previous Story Intelligence

- Story 0.1 criou `uv`, Python 3.13, Ruff, Pyright, pytest, `scripts/dev` e guardrails de monorepo.
- Story 0.1 definiu `./scripts/dev all` como fluxo local completo: lock check, sync locked, lint, format check, typecheck e pytest.
- Story 0.2 criou `services/service-template` com `domain`, `application`, `adapters` e `bootstrap`, além de guardrails contra dependência indevida no domínio.
- Story 0.2 reforçou que `packages/` não pode compartilhar entidades, regras, policies ou repositories de domínio.
- Story 0.3 criou `packages/contracts`, catálogo versionado e checks de contrato; qualquer contrato público, interno ou assíncrono novo deve seguir essa estrutura.
- Story 0.3 manteve checks com Python stdlib quando possível, evitando dependências externas sem necessidade.

### Pesquisa Técnica Atual

- A arquitetura aprovada define AWS/EKS para produção futura, NATS JetStream como backbone assíncrono do MVP, PostgreSQL gerenciado em produção e IaC em etapa posterior.
- Para esta story, a melhor opção é um harness local leve e reproduzível, com mocks e configuração local explícita, sem tentar reproduzir HA/DR de produção.
- Docker Compose é uma opção prática para desenvolvimento local quando houver dependências de processo; alternativa aceitável é script Python/test harness se não houver necessidade real de containers nesta etapa.
- Consequência de usar Docker Compose: melhora reprodutibilidade de dependências locais, mas exige Docker instalado e não deve virar contrato de produção.
- Consequência de usar apenas script Python: reduz dependências locais, mas valida menos o comportamento real de serviços/dependências persistentes.

### Anti-Patterns a Evitar

- Usar CPF, CNPJ, e-mail real, token real ou segredo em `.env.example`, fixtures, docs ou testes.
- Criar adapter real para bureau, KYC, antifraude, Open Finance ou fornecedor específico.
- Criar lógica de decisão, score ou análise de crédito nesta story.
- Colocar FastAPI, NATS, gRPC, SQLAlchemy ou OpenTelemetry dentro de `domain`.
- Alterar contrato de produto futuro sem necessidade.
- Exigir internet, credenciais externas ou conta cloud para validar o harness local.
- Tratar Docker Compose local como desenho final de produção.

## References

- `_bmad-output/planning-artifacts/epics.md` — Epic 0 e Story 0.4.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-4, AD-12, AD-16, AD-17, AD-20, AD-21 e AD-23.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/recomendacoes-decisoes-abertas.md` — OQ-8, OQ-9 e OQ-12.
- `_bmad-output/implementation-artifacts/0-1-bootstrap-do-monorepo-python.md` — tooling local e comandos `./scripts/dev`.
- `_bmad-output/implementation-artifacts/0-2-template-base-de-microsservico-ddd-e-hexagonal.md` — template de serviço e guardrails DDD/hexagonal.
- `_bmad-output/implementation-artifacts/0-3-estrutura-base-de-contratos-versionados.md` — contratos versionados e aprendizados de revisão.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — rastreamento BMAD.

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- `uv run pytest tests/test_local_harness.py` — primeiro ciclo vermelho confirmou ausência de harness local.
- `uv run pytest tests/test_local_harness.py` — validação específica verde com 3 testes.
- `./scripts/dev all` — gate completo verde com 21 testes.
- `uv run pytest tests/test_local_harness.py` — patches de revisão verdes com 7 testes.
- `./scripts/dev all` — gate completo pós-review verde com 25 testes.

### Completion Notes List

- Criado harness local em Python stdlib, sem dependências novas, com serviço de exemplo e mocks HTTP locais.
- Adicionados comandos `./scripts/dev harness-up` e `./scripts/dev harness-check`.
- Documentado uso local em `infra/local/README.md` e configuração segura em `infra/local/.env.example`.
- Adicionados testes para documentação, placeholders seguros e execução do harness mockado sem provedores externos.
- Validação completa executada com sucesso: lock check, sync locked, Ruff, Pyright, contratos, harness-check e pytest.
- Resolvidos os 6 achados de code review: erro estruturado para POST inválido/grande, readiness segura, validação CloudEvents, bind loopback, portas inválidas e cobertura do comando documentado.

### File List

- `_bmad-output/implementation-artifacts/0-4-harness-local-com-dependencias-mockadas.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `infra/local/.env.example`
- `infra/local/README.md`
- `scripts/dev`
- `scripts/local_harness.py`
- `tests/test_local_harness.py`

### Change Log

- 2026-08-03 — Implementado harness local mockado da Story 0.4 e marcado para revisão.
- 2026-08-03 — Resolvidos achados de code review e story marcada como concluída.
