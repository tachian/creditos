# Quality Constraints — CreditOS

Este companion consolida constraints verificáveis que downstream deve preservar ao criar epics, stories, testes e critérios de pronto.

## Segurança e Identidade

- Todo endpoint exige autenticação por padrão, exceto exceções explicitamente públicas.
- Operações sensíveis validam usuário, tenant, papel, permissão, recurso e contexto.
- `tenant_id` de payload não é fonte de verdade sem validação contra identidade autenticada.
- M2M usa OAuth 2.0 Client Credentials; usuários humanos usam OIDC Authorization Code + PKCE.
- gRPC interno propaga contexto confiável e roda com mTLS/autorização service-to-service em produção.

## Privacidade e LGPD

- Logs, traces, dashboards e respostas operacionais não exibem CPF/CNPJ completos, dados bancários, cartões, tokens, senhas, biometria, documentos, renda detalhada, credenciais ou payloads sensíveis completos.
- Dados pessoais/sensíveis persistidos têm `data_class`, finalidade, base legal, owner, retenção, descarte e política de exposição antes de produção.
- Dados de teste são sintéticos.
- Validação jurídica/contratual final é gate externo obrigatório antes de produção com cliente real.

## Multi-tenancy

- Toda entidade pertencente a cliente possui contexto de tenant.
- Isolamento entre tenants cobre dados, cache, eventos, filas, arquivos, logs, métricas, relatórios, jobs, notificações, secrets e integrações.
- MVP usa modelo `bridge`, com evolução para `silo` por risco, volume, contrato, região, performance ou compliance.
- Testes negativos cross-tenant são gate obrigatório.

## Resiliência, Performance e DR

- Operações com risco de duplicidade implementam idempotência ou justificativa aprovada.
- Fluxos assíncronos usam NATS JetStream no MVP com DLQ, replay, consumers duráveis, tenant, correlation ID e controle de duplicidade.
- SLOs internos iniciais seguem AD-22: API pública 99.9% mensal interno, submissão `p95 <= 500 ms`, decisão assíncrona `p95 <= 60 s` sob condições de timeout, auditoria crítica `p99 <= 300 ms` ou falha controlada.
- Produção inicial é single-region multi-AZ; active-active multi-região fica fora do MVP.

## Auditoria e Evidência

- Auditoria oficial é separada de logs operacionais.
- Auditoria principal é append-only, com hash encadeado, checkpoints assinados, verificação periódica e exportação imutável.
- S3 Object Lock é WORM de referência para exportações/checkpoints conforme AD-19.
- Decisão final não é publicada sem evidência/auditoria crítica.

## Contratos e Compatibilidade

- APIs públicas usam HTTP/JSON + OpenAPI versionado; gRPC não é público por padrão.
- Eventos usam CloudEvents e contratos assíncronos usam AsyncAPI.
- APIs, eventos, webhooks, schemas e integrações possuem testes de contrato quando alterados.
- Breaking changes exigem nova versão, período de compatibilidade, plano de migração e documentação.

## Backend e Operação

- Backend segue DDD + Hexagonal Architecture + Event-Driven Microservices.
- Cada microsserviço possui ownership lógico exclusivo dos seus dados.
- Joins, queries e transações diretas cross-service são proibidos.
- CI/CD e GitOps seguem AD-23: GitHub Actions, Argo CD, Amazon ECR, Sigstore/Cosign, GitHub Artifact Attestations, Kyverno e SLSA Build L2 inicial.
