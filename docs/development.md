# Desenvolvimento Local

Este projeto usa `uv` como ponto único para sincronização, execução de comandos e geração do `uv.lock`.

## Fluxo Padrão

```bash
uv lock --check
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/check_contracts.py
uv run python scripts/local_harness.py check
uv run pytest
```

O comando local agregado continua sendo:

```bash
./scripts/dev all
```

## Política de Dependências

- Dependências de desenvolvimento ficam no grupo `dev` do `pyproject.toml`.
- O `uv.lock` é o único lockfile versionado.
- Dependências não devem ser instaladas fora do fluxo `uv`.
- Novos serviços e pacotes devem entrar no workspace com `pyproject.toml` próprio.

## CI Inicial de Pull Request

O workflow `.github/workflows/ci.yml` é o gate inicial oficial de pull request para `main`.

Ele executa:

- setup de Python via `.python-version`;
- instalação explícita de `uv`;
- resumo rastreável de áreas alteradas no `GITHUB_STEP_SUMMARY`;
- scan de secrets com Gitleaks CLI em modo redigido;
- `uv lock --check`;
- `uv sync --locked`;
- Ruff lint;
- Ruff format check;
- Pyright;
- validação de contratos versionados;
- harness local com dependências mockadas;
- pytest.

Enquanto o repositório ainda é pequeno, o CI executa todos os gates mesmo quando o resumo identifica uma área específica de impacto. Essa decisão evita falsos negativos e mantém o pipeline simples. A separação por jobs/áreas deve ser avaliada quando o tempo de execução justificar.

Para gerar localmente o mesmo resumo de impacto usado no CI:

```bash
git diff --name-status -M -z main...HEAD | uv run python scripts/ci_changed_areas.py
```

### Scan de Secrets

O CI usa a imagem oficial `ghcr.io/gitleaks/gitleaks:v8.30.1` e executa `gitleaks git` no intervalo de commits do pull request com `--redact=100`, evitando imprimir o segredo bruto nos logs.

Para reproduzir localmente com Docker:

```bash
docker run --rm \
  -v "$PWD:/repo:ro" \
  ghcr.io/gitleaks/gitleaks:v8.30.1 \
  git /repo \
  --log-opts="main..HEAD" \
  --redact=100 \
  --no-banner \
  --exit-code 1 \
  --verbose
```

Não adicione secrets reais em `.github/workflows`, `.env`, fixtures, exemplos ou documentação. Caso um segredo seja detectado, ele deve ser rotacionado antes de qualquer novo push.

## Workspace

O workspace está preparado para:

- `services/*`
- `packages/*`

Os diretórios `services/` e `packages/` não devem conter projetos sem `pyproject.toml`. Placeholders ocultos, como `.gitkeep`, são permitidos apenas para versionar diretórios vazios.
