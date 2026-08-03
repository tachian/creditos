---
baseline_commit: 23b9d597f15b751883206b357d26760cd0a3410e
jira_issue: CTOS-21
branch: agent/story-0-6-initial-ci-quality-gates
---

# Story 0.6: CI Inicial e Gates de Qualidade

Status: done

## Story

Como equipe de engenharia,
quero um pipeline inicial de pull request,
para que mudanças só avancem com qualidade mínima, contratos preservados e riscos básicos de segurança verificados.

## Acceptance Criteria

1. **Given** um pull request, **when** o CI é executado, **then** roda formatação/lint, testes, typecheck progressivo, validação de contratos e detecção de secrets, **and** falhas críticas impedem merge.
2. **Given** uma alteração em serviço, pacote ou contrato, **when** o pipeline identifica impacto, **then** executa os checks relevantes para a área alterada, **and** publica resultado rastreável no pull request.

## Tasks / Subtasks

- [x] CTOS-96 — Definir pipeline inicial de pull request (AC: 1, 2)
  - [x] Criar workflow de GitHub Actions para pull requests contra `main` e execução manual quando útil.
  - [x] Configurar permissões mínimas do workflow e `concurrency` para cancelar execuções obsoletas do mesmo PR.
  - [x] Não implementar deploy, build de imagem, assinatura, SBOM, ECR, GitOps ou IaC nesta story.
- [x] CTOS-97 — Configurar ambiente Python/uv reproduzível no CI (AC: 1)
  - [x] Usar Python 3.13 a partir de `.python-version`.
  - [x] Instalar `uv` de forma explícita e reprodutível.
  - [x] Usar `uv lock --check` e `uv sync --locked` para proteger o lock único.
- [x] CTOS-98 — Executar gates de qualidade locais no CI (AC: 1)
  - [x] Rodar Ruff lint.
  - [x] Rodar Ruff format check.
  - [x] Rodar Pyright em modo progressivo configurado no repositório.
  - [x] Rodar validação de contratos com `scripts/check_contracts.py`.
  - [x] Rodar harness local e pytest.
- [x] CTOS-99 — Implementar detecção de secrets no PR (AC: 1)
  - [x] Adicionar gate de secrets sem exigir credenciais externas.
  - [x] Falhar o pipeline quando secrets forem detectados.
  - [x] Redigir ou evitar exposição do segredo no log do CI.
- [x] CTOS-100 — Implementar identificação de impacto e resultado rastreável (AC: 2)
  - [x] Detectar alterações em `services/`, `packages/`, contratos, scripts, docs relevantes e workflow.
  - [x] Executar os checks relevantes para a área alterada ou justificar execução total quando o repositório ainda é pequeno.
  - [x] Publicar resumo rastreável no job summary do GitHub Actions.
- [x] CTOS-101 — Atualizar documentação e testes do pipeline (AC: 1, 2)
  - [x] Documentar comandos locais equivalentes ao CI em `docs/development.md` ou documento dedicado.
  - [x] Adicionar testes estruturais para workflow, permissões mínimas, eventos, gates e secrets scan.
  - [x] Executar `./scripts/dev all` ao final.
  - [x] Manter `CTOS-21` e subtasks sincronizados no Jira durante desenvolvimento, revisão e conclusão.

### Review Findings

- [x] [Review][Patch] Secret scan não cobre histórico do PR [.github/workflows/ci.yml:56]
- [x] [Review][Patch] Checkout mantém credenciais Git ao executar código do PR [.github/workflows/ci.yml:25]
- [x] [Review][Patch] Cálculo de impacto não é robusto para PRs, forks e execução manual [.github/workflows/ci.yml:45]
- [x] [Review][Patch] Resumo declara gates executados antes da execução real [scripts/ci_changed_areas.py:81]
- [x] [Review][Patch] Renames e deleções perdem semântica no resumo de impacto [.github/workflows/ci.yml:49]
- [x] [Review][Patch] Arquivos raiz críticos de tooling caem como `other` [scripts/ci_changed_areas.py:6]
- [x] [Review][Patch] Testes do workflow são frágeis por substring [tests/test_ci_workflow.py:17]
- [x] [Review][Patch] Comando local documentado usa `python` fora do padrão `uv` [docs/development.md:55]
- [x] [Review][Patch] `UV_VERSION` está duplicado e sujeito a drift [.github/workflows/ci.yml:15]

## Dev Notes

### Escopo da Story

- Esta story cria o CI inicial de pull request para validar qualidade antes de merge.
- O objetivo é materializar gates mínimos e rastreáveis, não uma esteira completa de produção.
- Story 0.7 continua responsável pela trilha de containers, supply chain, SBOM, proveniência, assinatura, ECR, Artifact Attestations, SLSA e IaC.
- O workflow deve refletir os comandos locais existentes para evitar drift entre ambiente local e CI.

### Requisitos Técnicos Obrigatórios

- Runtime: Python 3.13.
- Gerenciador: `uv` workspace com `uv.lock` único.
- Gate local principal já existente: `./scripts/dev all`.
- CI oficial do MVP: GitHub Actions.
- Qualidade mínima: `uv lock --check`, `uv sync --locked`, Ruff lint, Ruff format check, Pyright, validação de contratos, harness local e pytest.
- Detecção de secrets deve falhar PRs com risco crítico e não deve imprimir segredo bruto nos logs.
- Workflow deve usar permissões mínimas, começando com `contents: read`; permissões adicionais precisam de justificativa explícita.
- Não adicionar credenciais AWS, cloud, registry, deploy, `pull_request_target`, OIDC AWS, ECR, Argo CD ou permissões de escrita nesta story.

### Arquitetura e Guardrails

- Seguir AD-16: stack Python 3.13, `uv`, Ruff, Pyright, pytest e contratos versionados.
- Seguir AD-23: GitHub Actions é o CI oficial do MVP; controles avançados de supply chain ficam para Story 0.7.
- Seguir AD-9 e Story 0.5: secrets e dados sensíveis não podem aparecer em logs de CI, fixtures ou exemplos.
- Workflows de PR devem evitar `pull_request_target` para código não confiável; usar `pull_request` é mais seguro para o CI inicial.
- `GITHUB_TOKEN` deve permanecer com permissões mínimas; se uma action exigir escrita em PR para comentário, preferir job summary nesta story.
- Caches não podem conter tokens, credenciais, `.env` real ou dados sensíveis.

### Decisões Técnicas Recomendadas

- **GitHub Actions vs CI externo:** usar GitHub Actions porque AD-23 o define como CI oficial do MVP e integra nativamente com PR checks. Alternativas como CircleCI/GitLab CI adicionariam fornecedor e configuração paralela sem benefício nesta fase.
- **`astral-sh/setup-uv` vs instalação manual de `uv`:** preferir `astral-sh/setup-uv` com versão fixa ou referência pinada, porque é a integração oficial recomendada pela documentação do `uv` para GitHub Actions. Alternativa manual reduz dependência de action, mas aumenta script customizado e manutenção.
- **`actions/setup-python` vs `uv python install`:** preferir `actions/setup-python` com `python-version-file: .python-version`, porque GitHub mantém cache de versões Python nos runners e isso reduz tempo de CI. Alternativa `uv python install` é válida, mas pode aumentar tempo de setup.
- **Secret scanning:** usar Gitleaks como gate inicial de CI ou CLI/action equivalente, porque roda em PR sem depender de configuração paga do repositório. GitHub Secret Scanning/Push Protection deve ser habilitado no repositório quando disponível, mas não substitui um check de CI rastreável. TruffleHog é alternativa forte, porém pode ser mais ruidosa/lenta para gate inicial. `detect-secrets` é alternativa Python, mas exige gestão de baseline.
- **Checks por impacto:** como o repositório ainda é pequeno, é aceitável executar o gate completo enquanto se publica um resumo de impacto. O caminho evolutivo é separar jobs por área quando o tempo de CI justificar.

### Estrutura Esperada

```text
.github/
  workflows/
    ci.yml
docs/
  development.md
scripts/
  ci_changed_areas.py ou equivalente, se necessário
tests/
  test_ci_workflow.py
```

A estrutura final pode variar se a implementação optar por YAML simples sem script auxiliar, desde que o AC2 permaneça verificável por resumo rastreável e checks relevantes.

### Testing Requirements

- Testar que `.github/workflows/ci.yml` existe.
- Testar que o workflow roda em `pull_request` contra `main` e não usa `pull_request_target`.
- Testar que permissões mínimas estão declaradas.
- Testar que o workflow executa lock check, sync locked, Ruff, Pyright, contratos, harness local, pytest e secrets scan.
- Testar que há `concurrency` configurado para evitar runs obsoletos.
- Testar que há job summary ou saída rastreável de impacto/checks.
- Executar `./scripts/dev all` ao final da implementação.

### Previous Story Intelligence

- Story 0.1 criou Python 3.13, `uv`, Ruff, Pyright, pytest, `scripts/dev` e `./scripts/dev all`.
- Story 0.2 reforçou DDD/hexagonal e guardrails de estrutura, que não devem ser afetados por CI.
- Story 0.3 criou `scripts/check_contracts.py`; CI deve chamar o mesmo check para preservar contratos.
- Story 0.4 criou `scripts/local_harness.py` e `./scripts/dev harness-check`; no sandbox local o harness pode exigir execução fora de sandbox por usar socket loopback, mas em GitHub Actions deve rodar normalmente.
- Story 0.5 adicionou `packages/security`, `packages/observability` e OpenTelemetry; CI deve validar esses pacotes e não vazar dados sensíveis em logs.

### Pesquisa Técnica Atual

- A documentação atual do `uv` recomenda `astral-sh/setup-uv` para GitHub Actions e também mostra uso de `actions/setup-python` com `python-version-file: .python-version`.
- A documentação atual de `actions/setup-python` indica `actions/setup-python@v6` e recomenda definir explicitamente a versão Python ou arquivo de versão para evitar variação inesperada nos runners.
- A documentação atual de cache do GitHub Actions alerta que caches não devem armazenar tokens ou credenciais e que forks/PRs podem ter acesso a caches em certos cenários.
- A documentação atual de concurrency do GitHub Actions permite cancelar execuções obsoletas do mesmo workflow/job, útil para PRs com novos commits.
- A documentação atual de GitHub Secret Protection/Push Protection mostra que push protection pode bloquear secrets antes do push, mas disponibilidade/configuração varia por tipo de repositório/plano; por isso o CI deve ter gate próprio inicial.
- A documentação oficial do Gitleaks informa disponibilidade por GitHub Action e CLI; para repositórios de organização, a action v2 pode exigir licença, então a implementação deve validar esse risco e usar CLI pinado se necessário.

### Anti-Patterns a Evitar

- Usar `pull_request_target` para executar código vindo do PR.
- Dar `contents: write`, `pull-requests: write`, `id-token: write` ou permissões amplas sem necessidade nesta story.
- Adicionar secrets reais em `.github/workflows`, `.env`, fixtures, docs ou logs.
- Esconder falhas críticas com `continue-on-error`.
- Trocar o fluxo local por comandos divergentes no CI.
- Implementar deploy, containers, registry, AWS OIDC, SBOM, assinatura ou GitOps nesta story.
- Tornar o CI dependente de conta cloud, credenciais externas ou serviços pagos.
- Aceitar secrets scan apenas como documentação sem falhar o PR.

## References

- `_bmad-output/planning-artifacts/epics.md` — Epic 0 e Story 0.6.
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/addendum.md` — quality gates sugeridos e handoff para CI/CD.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-16 e AD-23.
- `_bmad-output/implementation-artifacts/0-1-bootstrap-do-monorepo-python.md` — tooling local e `./scripts/dev`.
- `_bmad-output/implementation-artifacts/0-3-estrutura-base-de-contratos-versionados.md` — governança de contratos.
- `_bmad-output/implementation-artifacts/0-4-harness-local-com-dependencias-mockadas.md` — harness local.
- `_bmad-output/implementation-artifacts/0-5-observabilidade-logs-e-seguranca-base.md` — segurança/observabilidade e aprendizados de review.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — rastreamento BMAD.
- GitHub Actions workflow syntax: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
- GitHub Actions dependency caching: https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching
- GitHub Actions concurrency: https://docs.github.com/en/actions/concepts/workflows-and-actions/concurrency
- `actions/setup-python`: https://github.com/actions/setup-python
- `uv` em GitHub Actions: https://docs.astral.sh/uv/guides/integration/github/
- GitHub Secret Scanning/Push Protection: https://docs.github.com/en/code-security/concepts/secret-security/push-protection
- Gitleaks: https://github.com/gitleaks/gitleaks

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- RED: `.venv/bin/python -m pytest tests/test_ci_workflow.py` falhou com 7 testes antes do workflow/script existirem.
- GREEN: `.venv/bin/python -m pytest tests/test_ci_workflow.py` passou com 7 testes após workflow, script de impacto e ajustes de versão literal do Gitleaks.
- Validação focada: `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/pyright`, `.venv/bin/python scripts/check_contracts.py`.
- Validação final: `PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` passou fora do sandbox por exigir sockets locais no harness.
- Revisão adversarial: Blind Hunter, Edge Case Hunter e Acceptance Auditor executados; 9 findings de patch aplicados.
- Validação pós-review: `PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` passou com 46 testes.

### Completion Notes List

- Criado workflow inicial de PR em GitHub Actions com `pull_request` para `main`, `workflow_dispatch`, permissões mínimas e `concurrency`.
- Configurado setup reproduzível com Python via `.python-version`, `astral-sh/setup-uv` pinado por SHA e `uv lock --check`/`uv sync --locked`.
- Adicionados gates de Ruff, Pyright, contratos, harness local, pytest e secret scan com Gitleaks CLI em modo redigido.
- Criado resumo rastreável de impacto por área no `GITHUB_STEP_SUMMARY`, mantendo execução completa enquanto o repositório é pequeno.
- Documentado o fluxo local equivalente, o resumo de impacto e a reprodução local do scan de secrets.
- Validação final executada com 43 testes passando.
- Patches de code review aplicados: secret scan passou a cobrir histórico do PR, checkout não persiste credenciais, impacto usa três-pontos/name-status/NUL, tooling raiz é classificado e testes foram reforçados.
- Validação final pós-review executada com 46 testes passando.

### File List

- `.github/workflows/ci.yml`
- `_bmad-output/implementation-artifacts/0-6-ci-inicial-e-gates-de-qualidade.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `docs/development.md`
- `scripts/ci_changed_areas.py`
- `tests/test_ci_workflow.py`

### Change Log

- 2026-08-03 — Story 0.6 iniciada, branch criada e card Jira movido para WIP.
- 2026-08-03 — CI inicial, gates de qualidade, secret scan, resumo de impacto, documentação e testes estruturais implementados.
- 2026-08-03 — Achados do code review aplicados e Story 0.6 marcada como done no BMAD.
