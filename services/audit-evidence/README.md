# Audit & Evidence Service

O `Audit & Evidence Service` é a trilha oficial de auditoria do CreditOS.
Ele é separado de logs operacionais, traces, métricas e eventos de mensageria.

## Responsabilidades

- Registrar eventos oficiais de auditoria em trilha append-only.
- Preservar tenant, agregado, recurso, ator, origem, resultado e rastreabilidade.
- Exigir contexto confiável para tenant e ator.
- Minimizar e mascarar dados em detalhes auditáveis.
- Permitir referências operacionais complementares sem substituir a auditoria oficial.

## Limites

- Logs, traces, métricas e mensagens não são a trilha oficial.
- Correções devem ser novos eventos compensatórios; eventos gravados não são alterados.
- Payload bruto, prompt/output de IA, documentos, imagens, biometria, tokens, segredos e dados financeiros detalhados não são persistidos por padrão.
- O adapter in-memory é a fundação testável desta story; SQLAlchemy/Alembic, grants `INSERT`-only e banco real append-only ficam registrados como trabalho posterior.
- Hash encadeado, checkpoints, WORM/S3 Object Lock, gRPC/NATS reais e IaC ficam para histórias futuras do Epic 6.

## Camadas

- `domain`: entidades, value objects e erros puros.
- `application`: comandos, resultados, portas e orquestração de casos de uso.
- `adapters`: persistência e bordas técnicas.
- `bootstrap`: composição e runtime mínimo de container.

## Validação local

```bash
.venv/bin/pytest services/audit-evidence/tests/unit -q
.venv/bin/ruff format --check services/audit-evidence
.venv/bin/ruff check services/audit-evidence
```
