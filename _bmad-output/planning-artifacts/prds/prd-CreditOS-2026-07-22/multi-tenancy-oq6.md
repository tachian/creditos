# Estratégia de multi-tenancy - OQ-6

Data: 2026-07-24
Status: decisão registrada para PRD e insumo de Architecture/ADRs

## Decisão

O CreditOS adotará modelo `bridge` no MVP. Os serviços podem ser compartilhados, mas dados e recursos críticos devem ser isolados por tenant ou por grupo controlado de tenants. O modelo `silo` será a evolução para tenants que exigirem isolamento dedicado por risco, volume, contrato, região, performance ou compliance.

O modelo `pooled` puro não será o padrão inicial, porque o produto lida com crédito, risco, CPF/CNPJ, auditoria, revisão por IA e integrações externas.

## Definições

### `pooled`

Vários tenants compartilham aplicação, infraestrutura e dados, geralmente com segregação lógica por `tenant_id`.

Uso no CreditOS: não recomendado como padrão inicial. Pode existir apenas para recursos não sensíveis ou ambientes de baixo risco, se aprovado em ADR.

### `bridge`

Parte da infraestrutura é compartilhada, mas dados e recursos críticos são isolados por tenant ou grupo de tenants.

Uso no CreditOS: padrão do MVP.

### `silo`

Tenant recebe ambiente ou recursos dedicados, podendo incluir aplicação, banco, filas, secrets, storage, rede, observabilidade e deploy.

Uso no CreditOS: evolução para tenants premium, regulados, de alto volume ou com requisito contratual específico.

## Controles obrigatórios

- `tenant_isolation_tier` obrigatório no cadastro do tenant.
- `tenant_id` ou contexto equivalente obrigatório em entidades, eventos, logs, métricas, traces, filas, jobs, arquivos, integrações, callbacks e auditoria.
- `tenant_id` no payload não é fonte confiável sem validação contra identidade autenticada.
- Catálogo de tenant resolve tier, localização dos dados, credenciais, limites, região, configurações e recursos dedicados.
- Cache deve incluir chave de tenant.
- Filas, DLQs e jobs devem carregar contexto de tenant.
- Secrets e credenciais externas devem ser segregados por tenant.
- Exportações, relatórios e dashboards devem ser tenant-scoped.
- Testes cross-tenant são obrigatórios em todos os serviços.
- Alertas devem detectar tentativa de acesso cross-tenant e consumo anômalo por tenant.
- Rate limits, quotas e concorrência devem existir por tenant.
- Provisionamento de recursos dedicados deve ser automatizável.

## Estratégia por serviço

| Serviço | Estratégia `bridge` |
| --- | --- |
| Identity & Tenant | fonte do catálogo de tenant, tier de isolamento, capacidades e contexto confiável |
| Proposal Intake | resolve tenant autenticado, valida produto/canal habilitado e grava dados no particionamento do tenant |
| Decision | executa políticas no contexto do tenant e não acessa dados de outro tenant |
| Automated Review | aplica minimização, limites, modelo/configuração e guardrails por tenant |
| Integration | usa credenciais, provedores, limites, filas e resultados segregados por tenant |
| Audit & Evidence | isolamento reforçado por tenant, com retenção e proteção contra alteração |
| Reporting & Insights | projeções por tenant, agregações seguras e sem reidentificação indevida |

## Critérios para evoluir para `silo`

- Exigência regulatória ou contratual.
- Alto volume ou risco de noisy neighbor.
- SLO dedicado de performance.
- Residência de dados ou região dedicada.
- Backup/restore individual obrigatório.
- Chaves, secrets, rede, filas ou storage dedicados.
- Auditoria ou retenção específica.
- Sensibilidade elevada dos dados.

## Relação com OQ-5

A decisão da OQ-5 continua válida: cada microsserviço possui ownership lógico exclusivo dos seus dados. A OQ-6 define como os tenants são isolados dentro dessa estratégia.

No modelo `bridge`, o MVP pode usar cluster PostgreSQL compartilhado, mas deve possuir separação por serviço e estratégia de particionamento/isolamento por tenant. Para tenants que evoluírem para `silo`, dados e recursos podem migrar para infraestrutura dedicada.

## Fontes

- Azure, tenancy models: https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/tenancy-models
- Azure, approaches for multitenant solutions: https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/approaches/overview
- Azure SQL SaaS tenancy patterns: https://learn.microsoft.com/en-us/azure/azure-sql/database/saas-tenancy-app-design-patterns
- AWS SaaS tenant isolation: https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/core-isolation-concepts.html
