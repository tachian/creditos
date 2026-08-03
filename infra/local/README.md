# Harness Local CreditOS

Este harness sobe um serviço de exemplo e dependências mockadas em `localhost`
para validar o esqueleto técnico do repositório sem credenciais reais,
provedores externos, cloud, internet ou dados pessoais reais.

## Comandos

Subir o harness local:

```bash
./scripts/dev harness-up
```

Parar o harness:

```text
Ctrl+C
```

Validar o harness com portas efêmeras:

```bash
./scripts/dev harness-check
```

## Serviços locais

Com as portas padrão, o harness expõe:

- `http://127.0.0.1:18080/health`: health check do serviço de exemplo.
- `http://127.0.0.1:18080/ready`: readiness check do serviço de exemplo.
- `http://127.0.0.1:18080/v1/harness/ping`: endpoint mínimo que exercita os mocks.
- `http://127.0.0.1:18081/health`: health check das dependências mockadas.
- `http://127.0.0.1:18081/ready`: readiness check das dependências mockadas.
- `http://127.0.0.1:18081/mock/external-risk/v1/profile`: mock controlado de classe de integração externa.
- `http://127.0.0.1:18081/mock/async-broker/v1/publish`: mock compatível com o envelope assíncrono esperado para NATS JetStream/CloudEvents.

## Limites

- Não representa topologia final de produção.
- Não substitui NATS JetStream real, gRPC real, PostgreSQL real ou observabilidade real.
- Não escolhe fornecedor externo nominal.
- Não contém CPF, CNPJ, e-mail real, tokens, secrets ou payload sensível completo.
- Deve permanecer simples até que histórias futuras materializem serviços reais.

## Configuração

O arquivo `.env.example` documenta apenas valores locais e placeholders. Ele não
deve receber segredos reais. Se precisar alterar portas, exporte variáveis de
ambiente antes de executar `./scripts/dev harness-up`.
