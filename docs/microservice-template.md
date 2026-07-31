# Template de Microsserviço

O template em `services/service-template/` define a estrutura inicial para futuros
bounded contexts do CreditOS. Ele é intencionalmente mínimo: não cria domínio real,
não escolhe adapters concretos e não adiciona dependências de runtime.

## Como Usar

1. Copie `services/service-template/` para `services/<nome-do-servico>/`.
2. Renomeie o pacote Python de `creditos_service_template` para
   `creditos_<nome_do_servico>`.
3. Atualize o `name` no `pyproject.toml` do serviço.
4. Execute `uv lock` e `./scripts/dev all` a partir da raiz.

Cada serviço deve permanecer como pacote instalável do workspace `uv`, usando
`src/` layout e `build-system` configurado no próprio `pyproject.toml`. Os testes
locais em `services/<nome-do-servico>/tests/` são coletados pelo pytest padrão do
monorepo.

## Camadas Obrigatórias

- `domain`: domínio puro; não importa frameworks, banco, transporte ou provedores.
- `application`: casos de uso e portas; coordena o domínio.
- `adapters`: API, gRPC, eventos, persistência e integrações externas.
- `bootstrap`: composição da aplicação, configuração e wiring.

## Política de `packages/`

Pacotes compartilhados só podem conter contratos, observabilidade, segurança,
testes ou utilidades técnicas genéricas. O nome do pacote deve pertencer a uma
dessas categorias. Eles não podem conter entidades, value objects, policies,
repositories ou regras de negócio compartilhadas entre bounded contexts.

## Fora do Escopo

Esta story não cria os sete microsserviços reais do MVP, não implementa FastAPI,
gRPC, NATS, SQLAlchemy, OpenTelemetry, containers ou domínio funcional.
