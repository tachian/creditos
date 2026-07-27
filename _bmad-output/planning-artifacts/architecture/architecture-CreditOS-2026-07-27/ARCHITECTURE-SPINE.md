---
name: 'CreditOS'
type: architecture-spine
purpose: build-substrate
altitude: initiative
paradigm: 'DDD + Hexagonal Architecture + Event-Driven Microservices'
scope: 'Arquitetura técnica consolidada da plataforma SaaS CreditOS'
status: draft
created: '2026-07-27'
updated: '2026-07-27'
binds:
  - 'PRD CreditOS'
sources:
  - '../prds/prd-CreditOS-2026-07-22/prd.md'
  - '../prds/prd-CreditOS-2026-07-22/addendum.md'
companions:
  - '../prds/prd-CreditOS-2026-07-22/revisao-consolidacao-prd-2026-07-27.md'
---

# Architecture Spine — CreditOS

## Design Paradigm

CreditOS usa **DDD + Hexagonal Architecture + Event-Driven Microservices**.

- Cada microsserviço representa um bounded context ou capacidade de domínio com linguagem e ownership próprios.
- O domínio fica isolado de frameworks, banco de dados, transporte, provedores externos e formatos de payload de terceiros.
- Entradas externas e internas chegam por adapters; casos de uso vivem na camada de aplicação; regras e invariantes vivem no domínio.
- Comunicação síncrona interna usa gRPC.
- Fluxos assíncronos usam NATS JetStream como backbone de referência.

## Invariants & Rules

### AD-1 — Paradigma arquitetural [ADOPTED]

- **Binds:** todos os serviços backend, contratos internos, integrações externas e persistência.
- **Prevents:** serviços acoplados por infraestrutura, domínio dependente de framework, microsserviços por camada técnica e divergência entre padrões síncronos/assíncronos.
- **Rule:** todo backend deve seguir DDD + Hexagonal Architecture + Event-Driven Microservices; domínio não depende de infraestrutura; gRPC cobre chamadas síncronas internas; NATS JetStream cobre fluxos assíncronos duráveis.

### AD-2 — Mapa de serviços e ownership de domínio/dados [ADOPTED]

- **Binds:** decomposição do primeiro deploy, ownership de dados, limites de comunicação e responsabilidades por serviço.
- **Prevents:** duplicidade de responsabilidade entre serviços, acesso direto a dados de outro domínio, serviço técnico sem fronteira de domínio e divergência na alocação de capacidades.
- **Rule:** o primeiro deploy possui exatamente sete microsserviços de domínio: `Identity & Tenant`, `Proposal Intake`, `Decision`, `Automated Review`, `Integration`, `Audit & Evidence` e `Reporting & Insights`. Cada serviço possui dados próprios e fronteiras explícitas. Comunicação cross-service só ocorre por gRPC, eventos NATS JetStream ou projeções autorizadas.

```mermaid
flowchart LR
  Client[Cliente B2B / API] --> Intake[Proposal Intake]
  Intake -->|gRPC| Identity[Identity & Tenant]
  Intake -->|evento| Decision[Decision]
  Decision -->|comando assíncrono| Integration[Integration]
  Decision -->|gRPC/evento| Review[Automated Review]
  Decision -->|evento/evidência| Audit[Audit & Evidence]
  Integration -->|evento| Decision
  Intake -->|evento| Reporting[Reporting & Insights]
  Decision -->|evento| Reporting
  Integration -->|evento| Reporting
  Audit -->|projeção autorizada| Reporting
```

| Serviço | Ownership |
| --- | --- |
| `Identity & Tenant` | tenants, clientes técnicos, usuários, roles, permissões, claims, catálogo de tenant e tier de isolamento |
| `Proposal Intake` | submissão, schema, validação, normalização, idempotência, proposta recebida e status inicial |
| `Decision` | políticas, versões, execução determinística, decisão, códigos de motivo, inconclusivos e termos aprovados |
| `Automated Review` | revisão consultiva por IA, lacunas, inconsistências, guardrails e versões de agente/modelo |
| `Integration` | adapters externos, jobs assíncronos, fan-out/fan-in, retries, DLQ, fallback, resultados e custos de integração |
| `Audit & Evidence` | auditoria oficial, evidências, hash encadeado, checkpoints, exportação imutável e consultas auditáveis |
| `Reporting & Insights` | projeções, funil, dashboards, métricas de negócio, custos agregados e visão customer-facing curada |

### AD-3 — Ownership de dados e persistência cross-service [ADOPTED]

- **Binds:** persistência, migrations, repositories, integrações internas, reporting, auditoria e fluxo de decisão.
- **Prevents:** banco compartilhado como contrato implícito, queries diretas entre domínios, transações distribuídas, duplicidade de dono de entidade e acoplamento silencioso entre equipes.
- **Rule:** cada microsserviço é dono exclusivo do seu modelo persistido e das suas mutações. No MVP, PostgreSQL pode ser compartilhado apenas como infraestrutura física, desde que cada serviço tenha database/schema/usuário separados. Joins, queries e transações diretas cross-service são proibidos. Estado entre serviços circula somente por gRPC, eventos NATS JetStream, outbox/inbox ou projeções autorizadas.

```mermaid
flowchart TB
  Identity[Identity & Tenant] --> IdentityDb[(identity_tenant_db/schema)]
  Intake[Proposal Intake] --> IntakeDb[(proposal_intake_db/schema)]
  Decision[Decision] --> DecisionDb[(decision_db/schema)]
  Review[Automated Review] --> ReviewDb[(automated_review_db/schema)]
  Integration[Integration] --> IntegrationDb[(integration_db/schema)]
  Audit[Audit & Evidence] --> AuditDb[(audit_evidence_db/storage)]
  Reporting[Reporting & Insights] --> ReportingDb[(reporting_read_db/projections)]
  Identity -. gRPC/eventos .-> Intake
  Intake -. eventos .-> Decision
  Decision -. eventos .-> Reporting
  Integration -. eventos .-> Reporting
  Audit -. projeções autorizadas .-> Reporting
```

| Serviço | Persistência própria | Regra de acesso |
| --- | --- | --- |
| `Identity & Tenant` | tenants, usuários, clientes técnicos, roles, permissões, claims, catálogo de tenant | fonte confiável de identidade/tenant; demais serviços consultam por gRPC ou contexto autenticado |
| `Proposal Intake` | propostas recebidas, schemas, idempotência, status inicial | não expõe banco; publica eventos de submissão/status |
| `Decision` | políticas, versões, decisões, códigos de motivo, termos aprovados | mutação de decisão pertence ao serviço; evidências vão para `Audit & Evidence` |
| `Automated Review` | revisões consultivas, versões de agente/modelo, guardrails, resultados | não decide crédito final; retorna recomendação consultiva por contrato |
| `Integration` | jobs, adapters, retries, DLQ, snapshots/referências, custos de integração | não vaza payload bruto; normaliza via anti-corruption layer |
| `Audit & Evidence` | eventos append-only, evidências, hashes, checkpoints, exportações | trilha oficial; acesso reforçado e auditado |
| `Reporting & Insights` | projeções e agregações de leitura | não consulta bancos transacionais diretamente |

## Structural Seed

```text
creditos/
  services/
    identity-tenant/
    proposal-intake/
    decision/
    automated-review/
    integration/
    audit-evidence/
    reporting-insights/
  packages/
    contracts/
    observability/
    security/
    testing/
  infra/
    iac/
    kubernetes/
```

## Deferred

- Stack de linguagem/framework backend.
- Topologia final AWS/EKS e sizing dos componentes.
- Detalhe físico de migrations, naming de schemas/databases e política de migração por serviço.
- Convenção final de pacotes, namespaces e estrutura de código.
- Lista completa de ADRs e ordem de execução.
