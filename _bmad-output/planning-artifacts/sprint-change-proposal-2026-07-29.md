# Sprint Change Proposal — CreditOS

**Data:** 2026-07-29  
**Workflow:** `bmad-correct-course`  
**Projeto:** CreditOS  
**Modo assumido:** Batch, sem implementação de código  
**Status:** Aprovada pelo usuário em 2026-07-30 para branch/commit/push/draft PR

## 1. Issue Summary

### Gatilho da mudança

O relatório `_bmad-output/planning-artifacts/implementation-readiness-report-2026-07-29.md` concluiu que o conjunto PRD + SPEC + Architecture + Epics/Stories está conceitualmente coerente, mas ainda estava com status **NEEDS WORK before Phase 4 implementation**.

### Problema central

O backlog possuía épicos fortes de produto e domínio, mas não possuía uma fundação técnica explícita antes da Story 1.1. Isso criava risco de iniciar a implementação de `Identity & Tenant` sem base comum de monorepo, DDD/hexagonal, contratos, execução local, observabilidade, CI, supply chain e trilha de IaC.

### Tipo de mudança

- **Categoria:** lacuna técnica descoberta em validação de readiness.
- **Não é:** pivot de produto, rollback, mudança de MVP funcional ou troca de stack.
- **Evidência:** findings `IR-MAJ-1` e `IR-MAJ-2` do readiness report.

## 2. Impact Analysis

### Impacto em épicos

- **Novo Epic 0 recomendado:** `Fundação Técnica e Bootstrap da Plataforma`.
- **Epic 1 permanece válido:** continua iniciando capacidades de identidade, tenant e autorização, mas deve depender da fundação técnica.
- **Epics 2 a 8 permanecem válidos:** não há alteração de escopo funcional, FRs ou sequencing de produto.
- **Cobertura de FRs permanece 26/26:** Epic 0 é habilitador técnico e não cobre novos FRs de negócio.

### Impacto em histórias

- Foram adicionadas 7 histórias técnicas antes da Story 1.1:
  - Story 0.1 — Bootstrap do Monorepo Python.
  - Story 0.2 — Template Base de Microsserviço DDD e Hexagonal.
  - Story 0.3 — Estrutura Base de Contratos Versionados.
  - Story 0.4 — Harness Local com Dependências Mockadas.
  - Story 0.5 — Observabilidade, Logs e Segurança Base.
  - Story 0.6 — CI Inicial e Gates de Qualidade.
  - Story 0.7 — Trilha Inicial de Supply Chain, Containers e IaC.

### Impacto no PRD

- O PRD não exige mudança imediata.
- O MVP funcional permanece o mesmo.
- A alteração apenas torna rastreável uma fundação técnica já exigida por requisitos não funcionais, arquitetura e SPEC.

### Impacto na Architecture

- A Architecture não exige alteração imediata.
- Epic 0 materializa decisões já adotadas, especialmente:
  - AD-13 — CI/CD, supply chain e promoção de ambientes.
  - AD-16 — Stack backend e starter/base do repositório.
  - AD-23 — CI/CD, GitOps, registry, assinatura e policy enforcement.
  - Parte operacional de AD-7 e AD-12.

### Impacto em UX

- Sem impacto direto.
- A recomendação anterior permanece: rodar `bmad-ux` antes de implementar dashboards customer-facing, superfícies administrativas e visualização final de evidências.

### Impacto em CI/CD, IaC e operação

- CI inicial passa a ser explicitamente planejado antes das stories de produto.
- Supply chain e containers passam a ter trilha rastreável desde o começo.
- IaC completo de produção permanece como workstream posterior/pré-produção, mas deixa de ficar invisível no backlog.

## 3. Recommended Approach

### Caminho escolhido

**Direct Adjustment** com adição de um Epic 0 técnico antes do Epic 1.

### Alternativas consideradas

- **Adicionar tarefas soltas dentro do Epic 1:** rejeitado porque misturaria fundação transversal com domínio de identidade/tenant.
- **Criar uma story única de bootstrap:** rejeitado porque ficaria grande demais e pouco verificável.
- **Reabrir PRD/Architecture:** não necessário, pois a mudança materializa decisões já existentes.
- **Rollback:** não aplicável, pois ainda não há implementação de código a reverter.

### Justificativa

Epic 0 reduz risco de inconsistência técnica sem alterar valor de produto, domínios, microsserviços ou decisões arquiteturais. Ele cria uma ponte limpa entre planejamento e implementação: antes de pedir que um agente desenvolvedor implemente a Story 1.1, o repositório terá base mínima para serviços Python, DDD/hexagonal, contratos, execução local, observabilidade e CI.

### Esforço e risco

- **Esforço estimado:** médio.
- **Risco reduzido:** alto.
- **Risco introduzido:** baixo, desde que Epic 0 não vire uma plataforma completa antes do produto.
- **Guardrail:** Epic 0 deve entregar a menor fundação útil, não uma infraestrutura de produção completa.

## 4. Detailed Change Proposals

### Mudança no arquivo de épicos

**Arquivo:** `_bmad-output/planning-artifacts/epics.md`

**OLD:**

```md
## Lista de Épicos

### Epic 1: Acesso Seguro e Gestão de Tenants
```

**NEW:**

```md
## Lista de Épicos

### Epic 0: Fundação Técnica e Bootstrap da Plataforma
A equipe consegue iniciar a implementação em um repositório padronizado, com monorepo Python, base DDD/hexagonal, contratos, execução local, observabilidade mínima, CI inicial e trilha explícita para supply chain/IaC.
**FRs cobertos:** N/A — épico habilitador técnico para reduzir risco antes do Epic 1.

**Notas de implementação:** Deve ser executado antes da Story 1.1. Não altera o escopo funcional do MVP e não cria novo microsserviço de domínio. Materializa AD-16, AD-13, AD-23 e parte operacional de AD-7/AD-12 como fundação rastreável.

### Epic 1: Acesso Seguro e Gestão de Tenants
```

**Rationale:** o readiness report identificou risco real de iniciar implementação funcional sem fundação técnica comum.

### Novo Epic 0

**Epic:** Fundação Técnica e Bootstrap da Plataforma  
**Posição:** antes do Epic 1  
**Tipo:** habilitador técnico  
**Escopo:** monorepo, template de serviço, contratos, harness local, observabilidade/logging, CI inicial, supply chain/IaC inicial.

### Histórias adicionadas

#### Story 0.1 — Bootstrap do Monorepo Python

- Cria `services/`, `packages/`, `tests/`, `infra/`, `docs/` e `scripts/`.
- Define workspace `uv`, lock único, Ruff, Pyright progressivo e pytest.
- Garante comandos padronizados e dependências rastreáveis.

#### Story 0.2 — Template Base de Microsserviço DDD e Hexagonal

- Define `domain`, `application`, `adapters` e `bootstrap`.
- Bloqueia dependência de frameworks, bancos, gRPC, NATS, OpenTelemetry e Kubernetes no domínio.
- Restringe `packages/` a capacidades técnicas compartilháveis, sem domínio compartilhado.

#### Story 0.3 — Estrutura Base de Contratos Versionados

- Organiza OpenAPI, protobuf, AsyncAPI e schemas.
- Exige owner, versão, compatibilidade e política de breaking change.
- Prepara checks de contrato antes das features de produto.

#### Story 0.4 — Harness Local com Dependências Mockadas

- Permite execução local reproduzível.
- Usa mocks/sandbox sem credenciais reais.
- Expõe health/readiness em serviços de exemplo.

#### Story 0.5 — Observabilidade, Logs e Segurança Base

- Define logs estruturados, correlation ID, trace ID, métricas e traces.
- Exige mascaramento de CPF, CNPJ, e-mail, tokens, secrets e dados sensíveis.
- Garante health/readiness sem exposição de detalhes internos.

#### Story 0.6 — CI Inicial e Gates de Qualidade

- Roda lint/format, testes, typecheck progressivo, contratos e secret scanning.
- Bloqueia merge em falhas críticas.
- Publica resultado rastreável no PR.

#### Story 0.7 — Trilha Inicial de Supply Chain, Containers e IaC

- Define padrão inicial de imagem por serviço.
- Registra plano para ECR, SBOM, proveniência, assinatura, Artifact Attestations e SLSA Build L2.
- Cria tarefas rastreáveis para IaC completo posterior/pré-produção.

## 5. Checklist de Change Navigation

### 1. Understand the Trigger and Context

- `[x] 1.1` Trigger identificado: readiness report pós PRD/Architecture/SPEC/Epics.
- `[x] 1.2` Problema definido: fundação técnica ausente no backlog.
- `[x] 1.3` Evidência coletada: `IR-MAJ-1`, `IR-MAJ-2` e recomendações do readiness.

### 2. Epic Impact Assessment

- `[x] 2.1` Epic 1 continua viável, com dependência explícita do Epic 0.
- `[x] 2.2` Mudança necessária: adicionar Epic 0.
- `[x] 2.3` Epics 2 a 8 não exigem alteração.
- `[x] 2.4` Nenhum épico existente fica obsoleto.
- `[x] 2.5` Sequenciamento muda apenas para executar Epic 0 antes do Epic 1.

### 3. Artifact Conflict and Impact Analysis

- `[x] 3.1` PRD sem conflito; MVP funcional preservado.
- `[x] 3.2` Architecture sem conflito; Epic 0 materializa decisões já adotadas.
- `[N/A] 3.3` UX sem impacto imediato.
- `[x] 3.4` CI/CD, supply chain e IaC agora têm trilha rastreável.

### 4. Path Forward Evaluation

- `[x] 4.1` Direct Adjustment viável, esforço médio, risco baixo.
- `[N/A] 4.2` Rollback não aplicável.
- `[x] 4.3` PRD MVP Review não exige redução de escopo.
- `[x] 4.4` Caminho selecionado: Direct Adjustment com Epic 0.

### 5. Sprint Change Proposal Components

- `[x] 5.1` Issue summary criado.
- `[x] 5.2` Impacto em épicos e artefatos documentado.
- `[x] 5.3` Caminho recomendado e alternativas documentados.
- `[x] 5.4` MVP preservado; ação principal é backlog técnico inicial.
- `[x] 5.5` Handoff definido para Product Owner/Developer antes da implementação.

### 6. Final Review and Handoff

- `[x] 6.1` Checklist aplicável concluído.
- `[x] 6.2` Proposta conferida contra readiness, PRD, Architecture e epics.
- `[x] 6.3` Aprovação final do usuário recebida em 2026-07-30 para commit/PR.
- `[N/A] 6.4` `sprint-status.yaml` ainda não existe; deve ser criado no `bmad-sprint-planning`.
- `[x] 6.5` Próximo handoff recomendado: revisar/aprovar Epic 0 e depois revalidar readiness.

## 6. Implementation Handoff

### Classificação da mudança

**Moderate** — reorganização de backlog antes da implementação, sem mudança estratégica de produto.

### Responsáveis sugeridos

- **Product Owner / PM:** aprovar Epic 0 e garantir que ele entre antes do Epic 1 no Jira/Sprint Planning.
- **Developer agent:** transformar as stories 0.x em story files implementáveis quando o projeto entrar em desenvolvimento.
- **Architect:** validar que o Epic 0 não extrapola a arquitetura aprovada nem antecipa produção completa.

### Critérios de sucesso

- Epic 0 aparece antes do Epic 1 no backlog.
- Stories 0.x são pequenas, verificáveis e orientadas à fundação mínima.
- Readiness deixa de apontar ausência de bootstrap como major issue.
- Sprint planning consegue iniciar por fundação técnica sem bloquear o fluxo E2E mockado do MVP.

## 7. Próximas Ações Recomendadas

1. Usuário revisa e aprova esta Sprint Change Proposal.
2. Após aprovação, criar branch/commit/PR do ciclo `bmad-correct-course`.
3. Rodar novamente `bmad-check-implementation-readiness` ou validar incrementalmente a seção alterada.
4. Rodar `bmad-sprint-planning` para criar `sprint-status.yaml` e preparar sincronização com Jira `SCRUM`.
5. Depois do sprint planning, criar story files começando pelas histórias do Epic 0.
