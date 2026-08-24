## Deferred from: code review of 0-3-estrutura-base-de-contratos-versionados (2026-08-03)

- Definir estratégia de detecção de breaking changes reais em contratos versionados: opção metadata-only aprovada para a Story 0.3; diff semântico de OpenAPI, protobuf, AsyncAPI e JSON Schema exige ADR/tooling futuro. Jira: `CTOS-84`.

## Deferred from: code review of 1-5-gates-de-seguranca-e-isolamento-do-epic-1 (2026-08-12)

- Confirmar branch protection/required checks no GitHub como controle operacional fora do repositório. Descrição: a story valida comandos bloqueantes no CI versionado, mas a obrigatoriedade do check para merge depende de configuração do repositório/ambiente GitHub.
- Criar teste de bloqueio antes de caso de uso sensível real quando o primeiro fluxo de negócio consumir o gate do Epic 1. Descrição: nesta story o Identity & Tenant expõe o gate; a prova ponta a ponta deve ocorrer quando houver uma operação de negócio protegida além do próprio serviço de autorização.
## Deferred from: code review of 3-4-resiliencia-retry-dlq-e-reprocessamento-controlado (2026-08-21)

- Timeout com cancelamento/deadline real de adapter travado: o dispatcher in-memory mede timeout após retorno do adapter; implementação robusta exige worker com deadline cooperativo, cancelamento real ou isolamento de execução compatível com NATS/worker durável.

## Deferred from: code review of 3-5-registro-de-custo-e-resultado-de-integracao (2026-08-24)

- Durabilidade transacional de projeção/outbox para custo e resultado: a story prepara projeção minimizada local/testável, mas a garantia de entrega durável para Reporting depende de outbox/inbox, broker real ou persistência transacional futura, explicitamente fora do escopo desta story.
