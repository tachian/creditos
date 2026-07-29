# Capability Map — CreditOS

Este companion preserva o vínculo entre capacidades do SPEC, funcionalidades do PRD, bounded contexts da arquitetura e critérios de aceite de alto nível.

| CAP | Capacidade | PRD | Bounded context principal | Critério de aceite resumido |
| --- | --- | --- | --- | --- |
| CAP-1 | Identity & Tenant | FR-1, FR-2, FR-3; NFR-1 a NFR-8; NFR-12 a NFR-18 | `Identity & Tenant` | Autenticação, autorização, contexto confiável e isolamento de tenant passam em testes negativos cross-tenant. |
| CAP-2 | Proposal Intake | FR-4, FR-5, FR-6; NFR-32 a NFR-34 | `Proposal Intake` | Propostas CPF/CNPJ dos produtos MVP seguem contrato versionado, idempotência, validação, normalização e erros padronizados. |
| CAP-3 | Integration Orchestration | FR-7, FR-8, FR-9; NFR-23, NFR-24 | `Integration` | Integrações externas rodam por adapters substituíveis, assíncronos, paralelizáveis, com sandbox/mock, DLQ, retry e custo rastreável. |
| CAP-4 | Policy Governance | FR-10, FR-11, FR-12 | `Decision` | Políticas são versionadas, simuláveis, aprováveis, publicáveis e não são alteradas retroativamente após publicação. |
| CAP-5 | Decision & Explainability | FR-13, FR-14, FR-15 | `Decision` | Decisão determinística registra política, versão, resultado, termos, reason codes, fatores relevantes e inconclusivos sem fila manual. |
| CAP-6 | Automated Review AI | FR-16, FR-17, FR-18 | `Automated Review` | IA consultiva registra evidências, versões e guardrails sem tomar decisão final nem executar ações externas. |
| CAP-7 | Audit & Evidence | FR-19, FR-20; NFR-25 a NFR-27 | `Audit & Evidence` | Auditoria oficial é append-only, verificável, segregada de logs e bloqueia decisão final quando evidência crítica falha. |
| CAP-8 | Observability & Reporting | FR-21, FR-22, FR-23, FR-24; NFR-28 a NFR-31 | `Reporting & Insights` + todos os serviços produtores | Logs, métricas, traces, dashboards internos e dashboards customer-facing respeitam mascaramento, cardinalidade e isolamento por tenant. |
| CAP-9 | Decision Access & Callbacks | FR-25, FR-26 | `Proposal Intake`, `Decision`, `Integration` | Consultas e webhooks expõem decisão/status por contrato versionado, com assinatura, retry, idempotência e correlação. |
| CAP-10 | Platform Readiness | NFR-35 a NFR-42 + AD-12, AD-13, AD-16 a AD-24 | Todos | Backend, infraestrutura, CI/CD, SLO/DR, compliance e gate jurídico estão prontos para decomposição em epics/stories. |

## Produtos MVP

- Crédito pessoal para PF/CPF.
- BNPL para PF/CPF.
- Crédito PJ/capital de giro para PJ/CNPJ.
- Recebíveis para PJ/CNPJ.

## Serviços do primeiro deploy

- `Identity & Tenant`
- `Proposal Intake`
- `Decision`
- `Automated Review`
- `Integration`
- `Audit & Evidence`
- `Reporting & Insights`
