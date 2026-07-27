# Proteção da auditoria - OQ-11

## Decisão registrada

O CreditOS usará banco relacional append-only como trilha principal de auditoria no MVP, reforçado por hash encadeado, checkpoints assinados, verificação periódica e exportação imutável.

Ledger ou database especializada ficam fora do MVP e só devem ser avaliados se cliente, contrato, auditoria externa ou regulação exigirem imutabilidade mais forte.

## Desenho do MVP

| Camada | Decisão |
| --- | --- |
| Storage principal | Banco relacional append-only do `Audit & Evidence Service` |
| Escrita normal | Apenas `INSERT`; sem `UPDATE` ou `DELETE` na trilha principal |
| Integridade | `previous_hash` e `current_hash` por evento |
| Eventos críticos | HMAC ou assinatura com chave gerenciada quando aplicável |
| Checkpoints | Digest assinado por lote, tenant ou janela temporal |
| Cópia imutável | Exportação periódica para storage WORM/imutável ou equivalente |
| Verificação | Job periódico valida cadeia, checkpoints e exportações |
| Evolução | Ledger/database especializada apenas se houver exigência real |

## Evento mínimo de auditoria

Cada evento deve registrar, no mínimo:

- `event_id`.
- `tenant_id`.
- `aggregate_type` e `aggregate_id`.
- `event_type`.
- `occurred_at` em UTC.
- Ator humano ou técnico.
- Origem da operação.
- Ação executada.
- Recurso afetado.
- Resultado.
- Motivo ou código de decisão quando aplicável.
- `correlation_id` e `trace_id`.
- Versão do contrato, política, modelo ou agente quando aplicável.
- `previous_hash`.
- `current_hash`.

## Controles obrigatórios

- Auditoria é separada de logs operacionais.
- Serviços comuns não podem alterar ou apagar eventos de auditoria.
- Roles de escrita operacional têm apenas permissão de inserção.
- Acesso administrativo à trilha é segregado e monitorado.
- Leitura, exportação, tentativa de alteração, falha de escrita e falha de verificação também geram auditoria.
- Falha em auditoria crítica bloqueia publicação de decisão final de crédito.
- Exportações imutáveis respeitam retenção definida no OQ-10.
- Backups e restaurações devem preservar verificabilidade da cadeia de hashes.

## Estados em caso de falha

Se a decisão foi calculada, mas a evidência ou auditoria crítica falhou, o sistema não deve retornar decisão final. Estados possíveis:

- `pending_evidence`: decisão calculada, mas evidência crítica ainda não foi persistida.
- `audit_write_failed`: falha controlada ao registrar evento de auditoria obrigatório.
- `technical_failure`: falha técnica impede publicação segura da decisão.

A nomenclatura final dos estados pertence ao contrato de API e deve ser validada com Product/Architecture.

## Verificações e alertas

- Quebra de cadeia de hashes.
- Divergência entre banco e checkpoint assinado.
- Divergência entre checkpoint e exportação imutável.
- Ausência de evento obrigatório esperado.
- Atraso de exportação imutável.
- Tentativa de `UPDATE` ou `DELETE`.
- Leitura anômala ou exportação incomum de auditoria.
- Falha recorrente de auditoria crítica.

## Alternativas consideradas

| Alternativa | Vantagem | Consequência |
| --- | --- | --- |
| Banco append-only simples | Rápido, barato e fácil de consultar | Fraco contra alteração administrativa sem controles adicionais |
| Banco append-only + hash + exportação imutável | Bom equilíbrio para MVP | Exige operação de verificação, checkpoints e exportação |
| Ledger/database especializada | Forte para imutabilidade e trilha verificável | Maior custo, lock-in e complexidade antes de exigência real |
| Blockchain | Forte apelo narrativo | Desnecessário, caro e complexo para o problema atual |

## Consequências para Architecture

- Definir schema de eventos de auditoria e evidência.
- Definir algoritmo de hash, canonicalização do payload e estratégia de rotação.
- Definir KMS/chaves para HMAC ou assinatura dos checkpoints.
- Definir periodicidade de checkpoints e exportação imutável.
- Definir storage WORM/imutável ou equivalente conforme cloud escolhida.
- Definir fluxo de recuperação e verificação após restore.
- Definir SLO para escrita de auditoria crítica.

## ADRs necessários

- Banco append-only como trilha principal de auditoria.
- Hash encadeado e canonicalização de evento.
- Checkpoints assinados e gestão de chaves.
- Exportação imutável/WORM.
- Política de falha de auditoria crítica.
- Evolução futura para ledger/database especializada.

## Referências usadas

- OWASP Logging Cheat Sheet: `https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html`
- NIST SP 800-92, Guide to Computer Security Log Management: `https://csrc.nist.gov/pubs/sp/800/92/final`
- AWS S3 Object Lock: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html`
