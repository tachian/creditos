---
id: SPEC-CreditOS
companions:
  - capability-map.md
  - quality-constraints.md
  - ../../planning-artifacts/prds/prd-CreditOS-2026-07-22/prd.md
  - ../../planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md
  - ../../planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/architecture/architecture-CreditOS-2026-07-27/handoffs/legal-contractual-validation-final-task.md
sources:
  - ../../planning-artifacts/prds/prd-CreditOS-2026-07-22/revisao-consolidacao-prd-2026-07-27.md
---

> **Contrato canônico.** Este SPEC e os arquivos em `companions:` são o contrato preservado para o que construir, testar e validar. Os documentos fonte em `sources:` ficam para rastreabilidade.

# SPEC — CreditOS

## Why

CreditOS existe para realizar a visão de uma plataforma SaaS B2B governável, auditável, explicável, multi-tenant e observável para análise de crédito, análise de risco e automação de decisões. O MVP deve atender instituições API-first que operam crédito/risco para CPF e CNPJ, reduzindo tempo de decisão e inconsistência operacional sem comprometer segurança, privacidade, segregação por tenant ou capacidade de provar como cada decisão foi tomada.

## Capabilities

- **CAP-1 — Identity & Tenant**
  - **intent:** Clientes técnicos e usuários autorizados podem autenticar, autorizar, gerenciar tenants e propagar contexto confiável para operações sensíveis.
  - **success:** Chamadas sem autenticação, permissão, scope ou tenant compatível são rejeitadas e testes demonstram bloqueio de acesso cross-tenant.
- **CAP-2 — Proposal Intake**
  - **intent:** Clientes técnicos podem submeter propostas CPF/CNPJ por contratos versionados para produtos MVP.
  - **success:** Propostas válidas são aceitas, normalizadas, idempotidas e enfileiradas; propostas inválidas retornam erro padronizado sem aceitar payload arbitrário.
- **CAP-3 — Integration Orchestration**
  - **intent:** A plataforma pode configurar e executar integrações externas substituíveis, assíncronas, paralelizáveis e resilientes por tenant/produto.
  - **success:** Adapters, mocks/sandbox, limites, retries, DLQ, custos e resultados canônicos funcionam sem acoplar `Decision` a fornecedor nominal.
- **CAP-4 — Policy Governance**
  - **intent:** Gestores autorizados podem criar, versionar, simular, aprovar e publicar políticas de crédito/risco.
  - **success:** Políticas publicadas são rastreáveis, simuladas antes da publicação, imutáveis após publicação e corrigidas por nova versão.
- **CAP-5 — Decision & Explainability**
  - **intent:** A plataforma executa decisão automática determinística, trata inconclusivos sem fila manual e expõe explicabilidade auditável.
  - **success:** Cada decisão registra política, versão, tenant, proposta, resultado, termos, reason codes, fatores relevantes e correlation ID.
- **CAP-6 — Automated Review AI**
  - **intent:** A plataforma executa revisão automatizada consultiva por IA em serviço separado quando configurada por política.
  - **success:** A IA identifica lacunas, inconsistências e fatores consultivos, mas não aprova, reprova, altera termos ou publica decisão final.
- **CAP-7 — Audit & Evidence**
  - **intent:** A plataforma registra auditoria oficial, evidências decisórias, alterações sensíveis, integridade verificável e exportação imutável.
  - **success:** Decisão final não é publicada quando evidência crítica ou escrita de auditoria falha; cadeia, checkpoints e WORM são verificáveis.
- **CAP-8 — Observability & Reporting**
  - **intent:** Operadores e clientes autorizados acompanham saúde técnica, funil, volumes, decisões, integrações, custos e indicadores curados por tenant.
  - **success:** Dashboards internos e customer-facing exibem métricas úteis sem expor telemetria bruta, infraestrutura interna, payloads sensíveis ou dados de outro tenant.
- **CAP-9 — Decision Access & Callbacks**
  - **intent:** Clientes podem consultar decisões por proposta e receber callbacks/webhooks assinados, idempotentes e resilientes.
  - **success:** Consultas e callbacks respeitam contrato versionado, tenant, permissões, retry, DLQ e correlação ponta a ponta.
- **CAP-10 — Platform Readiness**
  - **intent:** A plataforma opera com arquitetura DDD/microsserviços, segurança, privacidade, tenancy, CI/CD, SLO/DR e compliance pré-produção.
  - **success:** Gates técnicos passam, `Architecture Spine` permanece vinculante e produção com cliente real fica bloqueada até validação jurídica/contratual formal.

## Constraints

- O MVP é B2B API-first para instituições que analisam crédito/risco de CPF e CNPJ em crédito pessoal, BNPL, crédito PJ/capital de giro e recebíveis.
- Contratos são versionados e aprovados; payload arbitrário, `selected_plan` e `plan_id` de financeira ficam fora do MVP.
- Segurança, privacidade, multi-tenancy, auditabilidade e explicabilidade são preocupações centrais e não opcionais.
- Backend segue DDD + Hexagonal Architecture + Event-Driven Microservices; gRPC é o padrão síncrono interno e NATS JetStream é o backbone assíncrono.
- `Decision` é o único dono da decisão final; IA generativa é apenas consultiva no MVP.
- Auditoria oficial não é substituída por logs, traces, métricas ou eventos de mensageria.
- Dados pessoais e sensíveis seguem minimização, mascaramento, classificação, retenção, descarte e LGPD operacional.
- Produção real com cliente fica bloqueada até a validação jurídica/contratual final descrita no companion obrigatório.

## Non-goals

- Atender consumidores finais solicitando crédito diretamente ao CreditOS.
- Ser core bancário, sistema contábil, antifraude completo, bureau de crédito ou ferramenta BI genérica.
- Escolher fornecedores externos nominais no PRD/spec do MVP.
- Criar revisão/fila manual ou override humano no MVP.
- Permitir que IA generativa aprove, reprove, altere termos ou publique decisão final.
- Treinar modelos próprios com dados pessoais identificáveis no MVP operacional.
- Entregar multi-região active-active ou SLA público contratual no MVP.

## Success signal

Uma instituição B2B consegue integrar por API, submeter uma proposta CPF ou CNPJ de produto MVP, obter decisão automática ou inconclusiva explicável, receber callback/consulta, visualizar métricas curadas por tenant e reconstruir a decisão com evidências auditáveis, sem vazamento cross-tenant ou exposição de dados sensíveis.

## Open Questions

- Nenhuma questão de produto/arquitetura bloqueante conhecida para epics/stories; a validação jurídica/contratual é gate externo pré-produção, não bloqueio de decomposição.
