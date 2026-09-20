## Deferred from: code review of 0-3-estrutura-base-de-contratos-versionados (2026-08-03)

- Definir estratégia de detecção de breaking changes reais em contratos versionados: opção metadata-only aprovada para a Story 0.3; diff semântico de OpenAPI, protobuf, AsyncAPI e JSON Schema exige ADR/tooling futuro. Jira: `CTOS-84`.

## Deferred from: code review of 1-5-gates-de-seguranca-e-isolamento-do-epic-1 (2026-08-12)

- Confirmar branch protection/required checks no GitHub como controle operacional fora do repositório. Descrição: a story valida comandos bloqueantes no CI versionado, mas a obrigatoriedade do check para merge depende de configuração do repositório/ambiente GitHub.
- Criar teste de bloqueio antes de caso de uso sensível real quando o primeiro fluxo de negócio consumir o gate do Epic 1. Descrição: nesta story o Identity & Tenant expõe o gate; a prova ponta a ponta deve ocorrer quando houver uma operação de negócio protegida além do próprio serviço de autorização.
## Deferred from: code review of 3-4-resiliencia-retry-dlq-e-reprocessamento-controlado (2026-08-21)

- Timeout com cancelamento/deadline real de adapter travado: o dispatcher in-memory mede timeout após retorno do adapter; implementação robusta exige worker com deadline cooperativo, cancelamento real ou isolamento de execução compatível com NATS/worker durável.

## Deferred from: code review of 3-5-registro-de-custo-e-resultado-de-integracao (2026-08-24)

- Durabilidade transacional de projeção/outbox para custo e resultado: a story prepara projeção minimizada local/testável, mas a garantia de entrega durável para Reporting depende de outbox/inbox, broker real ou persistência transacional futura, explicitamente fora do escopo desta story.

## Deferred from: code review of 4-4-publicacao-imutavel-de-politica-aprovada (2026-08-28)

- Verificação de fingerprint persistido em `CreditPolicy.restore`: o método recalcula o fingerprint a partir dos campos restaurados e não recebe/verifica um fingerprint previamente armazenado. É um endurecimento de persistência/auditoria para adapter real; no escopo atual in-memory não há serialização externa nem banco real.

## Deferred from: code review of 4-6-tratamento-de-propostas-inconclusivas-sem-fila-manual (2026-09-02)

- Fingerprint governado ainda usa serialização baseada em `repr`, criando risco futuro de reprodutibilidade entre refactors. É um endurecimento transversal e preexistente do modelo de política; a Story 4.6 apenas adicionou `fallback_action` ao fingerprint existente.

## Deferred from: code review of 4-7-resposta-explicavel-de-decisao (2026-09-04)

- Suíte completa depende de `uv` disponível no ambiente local: a regressão completa fora do sandbox passou em 528 testes e falhou apenas em `tests/test_local_harness.py:120` por `scripts/dev: line 47: uv: command not found`, condição ambiental preexistente ao código da Story 4.7.

## Deferred from: dev-story of 4-8-gates-de-decisao-politica-e-explicabilidade (2026-09-04)

- Suíte completa ainda depende de `uv` disponível no ambiente local: a regressão completa fora do sandbox passou em 539 testes e falhou apenas em `tests/test_local_harness.py:120` por `scripts/dev: line 47: uv: command not found`, condição ambiental preexistente e fora do escopo dos gates do `Decision Service`.

## Deferred from: dev-story of 5-1-configuracao-versionada-de-agente-de-revisao (2026-09-07)

- Suíte completa ainda depende de `uv` disponível no ambiente local: a regressão completa fora do sandbox passou em 546 testes e falhou apenas em `tests/test_local_harness.py:120` por `scripts/dev: line 47: uv: command not found`, condição ambiental preexistente e fora do escopo do `Automated Review Service`.

## Deferred from: code review of 5-5-fallback-seguro-de-revisao-automatizada (2026-09-11)

- Executor ausente não vira fallback e pode deixar reserva órfã em `execute_consultative_review`: a reserva antes de `_require_consultative_executor()` já existia antes da Story 5.5 e representa endurecimento futuro de configuração/bootstrapping do serviço, não falha de provedor/modelo tratada por fallback consultivo.

## Deferred from: dev-story of 6-1-trilha-oficial-append-only-de-auditoria (2026-09-14)

- Adapter SQLAlchemy/Alembic real e grants de banco para trilha append-only: a Story 6.1 criou a porta append-only, adapter in-memory testável e desenho de domínio/aplicação. O repositório ainda não possui padrão operacional de migrations por serviço nem banco real provisionado; a implementação física com `INSERT`-only, usuário sem `UPDATE`/`DELETE`, migrations Alembic e grants deve ser feita em história/ADR operacional de persistência real do `Audit & Evidence Service`, preservando a porta append-only já criada.

## Deferred from: dev-story of 6-3-auditoria-de-alteracoes-sensiveis (2026-09-17)

- Fluxos reais de permissões, manutenção e break-glass: a Story 6.3 definiu os escopos segregados futuros `governance:maintenance` e `governance:break_glass`, mas não criou CRUD de roles/scopes, IAM/cloud, bypass operacional ou endpoint administrativo novo. Quando esses fluxos forem materializados, devem emitir eventos oficiais no `Audit & Evidence` com resultado `accepted`, `blocked`, `rejected` ou `technical_failure`, sem depender de logs/traces.
- Exportação WORM/S3 Object Lock e acesso sensível real: não há fluxo operacional de exportação imutável nem consulta customer-facing de auditoria nesta etapa. Histórias futuras devem registrar `export_reference`, finalidade, retenção, legal hold quando aplicável e trilha oficial sem snapshots completos ou dados sensíveis.
- Transporte e durabilidade reais de auditoria de alterações sensíveis: os adapters oficiais permanecem in-process/testáveis. gRPC real, outbox transacional, persistência SQLAlchemy/Alembic, exportação WORM/S3 Object Lock e IaC continuam dependentes das próximas histórias/ADRs do Epic 6.

## Deferred from: dev-story of 6-4-integridade-verificavel-com-hash-encadeado-e-checkpoints (2026-09-19)

- Persistência real da cadeia e dos checkpoints: a Story 6.4 implementa domínio, portas, verificação e adapters in-memory. A materialização em banco relacional append-only, com migrations SQLAlchemy/Alembic, usuário/grants `INSERT`-only, índices por tenant/janela e rotina de reconciliação transacional permanece para história/ADR operacional de persistência real do `Audit & Evidence`.
- Assinatura com KMS/chave gerenciada: checkpoints usam porta de assinatura e adapter determinístico de teste. Produção deve substituir por AWS KMS/HSM/Secrets Manager ou equivalente, com referência de chave, rotação, segregação de função, auditoria, procedimento de recuperação e política de retenção de chave compatível com WORM.
- Exportação WORM/S3 Object Lock e jobs periódicos: a story não cria S3 Object Lock, exportação imutável, scheduler, worker, NATS/gRPC real ou IaC. Histórias futuras devem exportar prova minimizada, reconciliar checkpoints, detectar atraso/divergência e auditar falhas de verificação sem persistir payload sensível bruto.
