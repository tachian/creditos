# Audit & Evidence Service

O `Audit & Evidence Service` é a trilha oficial de auditoria do CreditOS.
Ele é separado de logs operacionais, traces, métricas e eventos de mensageria.

## Responsabilidades

- Registrar eventos oficiais de auditoria em trilha append-only.
- Preservar tenant, agregado, recurso, ator, origem, resultado e rastreabilidade.
- Exigir contexto confiável para tenant e ator.
- Minimizar e mascarar dados em detalhes auditáveis.
- Permitir referências operacionais complementares sem substituir a auditoria oficial.
- Calcular `previous_hash` e `current_hash` por tenant sobre payload canônico determinístico.
- Gerar e verificar checkpoints assinados de janelas fechadas usando digest minimizado.
- Exportar checkpoints para manifesto WORM lógico por porta hexagonal e reconciliar metadados/digest de forma segura.

## Limites

- Logs, traces, métricas e mensagens não são a trilha oficial.
- Correções devem ser novos eventos compensatórios; eventos gravados não são alterados.
- Payload bruto, prompt/output de IA, documentos, imagens, biometria, tokens, segredos e dados financeiros detalhados não são persistidos por padrão.
- O adapter in-memory é a fundação testável desta story; SQLAlchemy/Alembic, grants `INSERT`-only e banco real append-only ficam registrados como trabalho posterior.
- KMS real, S3 Object Lock/bucket real, jobs periódicos, gRPC/NATS reais e IaC ficam para histórias futuras do Epic 6.

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

## Integridade Verificável

A Story 6.4 adiciona integridade lógica verificável à trilha oficial:

- a cadeia canônica do MVP é por `tenant_id`, em ordem oficial de append;
- o primeiro evento de cada tenant usa a gênese versionada `creditos-audit-chain-genesis:v1`;
- o `current_hash` é `sha256` sobre payload canônico estável e inclui o `previous_hash`;
- o payload canônico inclui somente campos oficiais, `safe_details` já normalizado e referências operacionais técnicas, nunca payload bruto, tokens, segredos, documentos completos ou evidência operacional completa;
- checkpoints cobrem janelas fechadas e não vazias, registrando tenant, período, contagem, primeiro/último evento, digest do lote, algoritmo, versão de canonicalização, assinatura e referência de chave;
- a assinatura atual é uma porta com adapter determinístico para testes; KMS/HSM/Secrets Manager reais permanecem fora do escopo desta story;
- a verificação retorna divergências seguras, como hash divergente, predecessor ausente, checkpoint ausente, digest incompatível ou assinatura inválida, sem expor payload bruto ou PII.

## Exportação WORM Lógica

A Story 6.5 adiciona o contrato testável de exportação imutável:

- a exportação parte de checkpoint assinado existente e gera manifesto canônico `audit-worm-manifest.v1` com `sha256`;
- o manifesto contém apenas metadados minimizados, hashes, IDs técnicos, assinatura do checkpoint, janela, contagens e política de retenção;
- a porta `AuditWormStorage` representa gravação/leitura/head de objeto WORM sem acoplamento a `boto3`, S3 real, KMS, bucket ou scheduler;
- o adapter in-memory simula versionamento e impede overwrite lógico divergente para provar idempotência e conflitos;
- `GOVERNANCE` e `COMPLIANCE` são modelados como modos compatíveis com S3 Object Lock, mas a escolha produtiva depende de contrato, IaC e governança operacional;
- toda exportação aceita/rejeitada e reconciliação válida/inválida gera evento oficial minimizado separado de logs operacionais;
- a reconciliação valida digest do manifesto, checkpoint, versão do objeto, modo de retenção, `retain_until` e legal hold sem expor payload bruto.

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
