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

## Container de Exemplo

O `Dockerfile` deste template é uma referência inicial para serviços implantáveis,
não uma imagem final de domínio. Ele usa imagem base fixada por digest, exige
metadados rastreáveis no build, define usuário não root, metadados OCI,
`HEALTHCHECK` de liveness e `STOPSIGNAL SIGTERM`.

O runtime mínimo em `bootstrap/container_runtime.py` expõe comandos separados
para probes por `exec`:

- `healthcheck`: liveness, não depende de readiness.
- `readiness`: readiness, baseada em arquivo efêmero gravado em `/tmp`.

Serviços reais podem substituir esse mecanismo por endpoints HTTP `/health` e
`/ready`, desde que preservem readiness separada de liveness, shutdown gracioso,
janela de drain após `SIGTERM` e ausência de dados sensíveis nas respostas.

Este template não expõe porta porque o runtime mínimo não escuta HTTP. Serviços
com adapter HTTP/gRPC devem declarar a porta explicitamente no Dockerfile e nos
manifests quando o listener existir.

Exemplo de build local rastreável:

```bash
docker build \
  --build-arg COMMIT_SHA="$(git rev-parse HEAD)" \
  --build-arg BUILD_CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --build-arg SERVICE_VERSION="0.1.0" \
  -t "creditos-service-template:$(git rev-parse --short HEAD)" \
  services/service-template
```

Exemplo de registro de digest como artefato de build:

```bash
docker buildx build \
  --metadata-file /tmp/creditos-service-template.build-metadata.json \
  --build-arg COMMIT_SHA="$(git rev-parse HEAD)" \
  --build-arg BUILD_CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --build-arg SERVICE_VERSION="0.1.0" \
  -t "creditos-service-template:$(git rev-parse --short HEAD)" \
  services/service-template

uv run python scripts/container_release_metadata.py \
  --service creditos-service-template \
  --image-ref "creditos-service-template:$(git rev-parse --short HEAD)" \
  --commit-sha "$(git rev-parse HEAD)" \
  --build-metadata-file /tmp/creditos-service-template.build-metadata.json \
  --output /tmp/creditos-service-template.release.json
```

Em pipelines protegidos, o arquivo `.release.json` deve ser publicado como
artefato junto de SBOM, proveniência e assinatura.
