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

## Auditoria de Decisões

A Story 6.2 registra decisões do `Decision Service` como eventos oficiais:

- `credit_decision.completed` vira evento append-only com agregado e recurso `credit_decision`.
- `credit_decision.rejected` registra rejeições técnicas minimizadas quando a intent chega ao serviço.
- `safe_details` aceita somente chaves canônicas de decisão, como decisão, proposta, política, versão, catálogo, outcome, status, reason codes/regras como referências técnicas, contagens e fingerprint.
- `OperationalEvidenceReference` pode apontar para trace técnico complementar, sem persistir conteúdo de log, payload de provedor ou dado sensível.
- Falhas de validação ou append são críticas para decisões finais e devem impedir publicação/visibilidade da decisão no serviço de origem.

## Auditoria de Alterações Sensíveis

A Story 6.3 amplia a trilha oficial para alterações sensíveis já materializadas no MVP:

- políticas, catálogos de reason codes e simulações governadas do `Decision Service`;
- configurações versionadas de agente de IA consultivo do `Automated Review Service`;
- `safe_details` continua fechado, minimizado e composto apenas por IDs técnicos, versões, revisões, fingerprints, contagens, status e justificativas seguras;
- campos autoritativos de recurso não podem ser sobrescritos pelo payload seguro informado pelo serviço de origem;
- manutenção, bypass, permissões, exportações/WORM e acesso sensível real ficam registrados como lacunas controladas até existirem fluxos materializados.

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
