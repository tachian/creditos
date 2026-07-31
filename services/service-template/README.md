# Template de Microsserviço CreditOS

Este diretório é um template estrutural para futuros bounded contexts do CreditOS.
Ele não representa um microsserviço real do MVP e não contém regras de negócio.

## Camadas

- `domain`: entidades, value objects, eventos, policies e serviços de domínio puros.
- `application`: casos de uso e portas que coordenam o domínio.
- `adapters`: implementações de borda, transporte, eventos, persistência e integrações.
- `bootstrap`: composição da aplicação, configuração e wiring de adapters.

## Regra de Dependência

`domain` não pode importar FastAPI, Pydantic de borda, SQLAlchemy, Alembic,
gRPC, NATS, Redis, OpenTelemetry, provedores externos ou Kubernetes.

Dependências de infraestrutura devem ficar em `adapters` ou `bootstrap`.

## Testes e Empacotamento

O serviço usa `src/` layout, `build-system` no `pyproject.toml` e deve permanecer
instalável como membro do workspace `uv`. Testes locais devem ficar em
`tests/unit`, `tests/integration` e `tests/contract`; a suíte padrão do monorepo
coleta esses diretórios.
