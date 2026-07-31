# Desenvolvimento Local

Este projeto usa `uv` como ponto único para sincronização, execução de comandos e geração do `uv.lock`.

## Fluxo Padrão

```bash
uv lock --check
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

## Política de Dependências

- Dependências de desenvolvimento ficam no grupo `dev` do `pyproject.toml`.
- O `uv.lock` é o único lockfile versionado.
- Dependências não devem ser instaladas fora do fluxo `uv`.
- Novos serviços e pacotes devem entrar no workspace com `pyproject.toml` próprio.

## Workspace

O workspace está preparado para:

- `services/*`
- `packages/*`

Os diretórios `services/` e `packages/` não devem conter projetos sem `pyproject.toml`. Placeholders ocultos, como `.gitkeep`, são permitidos apenas para versionar diretórios vazios.
