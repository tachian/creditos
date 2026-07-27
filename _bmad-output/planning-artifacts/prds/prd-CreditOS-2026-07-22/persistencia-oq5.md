# Persistência por microsserviço - OQ-5

Data: 2026-07-24
Status: decisão registrada para PRD e insumo de Architecture/ADRs

## Decisão

Cada microsserviço do CreditOS terá ownership lógico exclusivo dos seus dados desde o início. No MVP, é permitido usar um cluster PostgreSQL compartilhado como infraestrutura, desde que cada serviço tenha database, schema e usuário próprios, com permissões que impeçam acesso direto a dados de outro serviço.

O objetivo é evitar um banco monolítico disfarçado de microsserviços, preservando DDD, bounded contexts e independência evolutiva sem elevar demais o custo operacional inicial.

## Regras obrigatórias

- Cada serviço possui credencial própria.
- Cada serviço executa suas próprias migrations.
- Cada serviço acessa somente suas tabelas, schemas, views e objetos.
- Joins cross-service são proibidos.
- Transações distribuídas não são o caminho padrão.
- Consultas entre domínios devem usar API/gRPC, eventos, projeções, composição autorizada ou read models.
- Dados de reporting devem ser derivados de eventos/projeções, não de leitura direta nos bancos transacionais.
- Dados de auditoria devem ter isolamento reforçado e proteção contra alteração.

## Mapa inicial

| Serviço | Persistência inicial | Observações |
| --- | --- | --- |
| Identity & Tenant Service | PostgreSQL lógico isolado | tenants, usuários, clientes técnicos, roles, permissões, capacidades |
| Proposal Intake Service | PostgreSQL lógico isolado | propostas recebidas, schemas, idempotência, status inicial |
| Decision Service | PostgreSQL lógico isolado | políticas, versões, decisões, códigos de motivo, termos aprovados |
| Automated Review Service | PostgreSQL lógico isolado | revisões consultivas, versões de agente/modelo, guardrails, resultados |
| Integration Service | PostgreSQL lógico isolado | jobs, adapters, retries, DLQ, snapshots ou referências externas |
| Audit & Evidence Service | PostgreSQL/storage com isolamento reforçado | append-only, hash encadeado, exportação imutável/WORM quando possível |
| Reporting & Insights Service | Banco de leitura/projeções | alimentado por eventos; otimizado para consultas e dashboards |

## Evolução para isolamento físico

Um serviço deve migrar para banco físico dedicado quando houver:

- exigência regulatória ou contratual;
- necessidade de isolamento forte por risco;
- volume ou performance que afete outros serviços;
- padrão de acesso muito diferente;
- necessidade de storage especializado;
- requisitos de backup, retenção ou criptografia distintos;
- sensibilidade maior, como auditoria e evidências.

## Consistência entre serviços

O CreditOS deve aceitar consistência eventual onde o domínio permitir. Para fluxos que atravessam múltiplos serviços, a Architecture deve definir quando usar:

- eventos de domínio;
- outbox/inbox;
- idempotência;
- materialized views;
- API composition;
- Saga/orquestração;
- compensações.

## Consequências

### Benefícios

- Preserva DDD e bounded contexts.
- Reduz acoplamento entre microsserviços.
- Permite evolução física progressiva.
- Evita queries diretas e dependências invisíveis.
- Facilita governança de dados, auditoria e testes de contrato.

### Custos

- Exige disciplina de migrations por serviço.
- Exige eventos/projeções para consultas cruzadas.
- Introduz consistência eventual em reporting e integrações.
- Pode exigir maior maturidade operacional para backup, observabilidade e troubleshooting.

## Fontes

- AWS, persistência em microsserviços: https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-data-persistence/introduction.html
- AWS, Saga orchestration: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html
- Azure, CQRS: https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs
- Azure, Event Sourcing: https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing
- Microservices.io, Database per service: https://microservices.io/patterns/data/database-per-service.html
