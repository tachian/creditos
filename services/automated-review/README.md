# Automated Review Service

Microsserviço responsável por revisão automatizada consultiva por IA no CreditOS.

## Responsabilidades

- Governar configurações versionadas de agente, prompt, modelo/provedor e guardrails.
- Publicar somente versões aprovadas e imutáveis de configuração consultiva.
- Criar nova versão em `draft` quando uma configuração publicada precisar mudar.
- Emitir intenções auditáveis minimizadas para criação, atualização, publicação e nova versão.
- Registrar logs estruturados com IDs técnicos, status, versão, contagens e `correlation_id`.

## Limites

- O serviço não decide crédito final.
- O serviço não aprova, reprova, altera termos, executa callback ou chama integração externa.
- Provedores/modelos de IA pertencem a este bounded context, mas esta etapa não executa modelo real.
- Provedores externos de dados/notificação continuam pertencendo ao `Integration Service`.
- A política determinística e a decisão final continuam pertencendo ao `Decision Service`.
- A trilha oficial append-only continua pertencendo ao `Audit & Evidence Service`.

## Story 5.1

A Story 5.1 cria o núcleo de configuração versionada de agente de revisão:

- `ReviewAgentConfiguration` com status `draft`, `published` e `archived`;
- `ReviewAgentPrompt` com versão, allowlist de entrada, schema de saída e fingerprint;
- `ReviewAgentGuardrails` com schema validation, minimização, bloqueio de PII, bloqueio de decisão final e bloqueio de tool use;
- `ReviewAgentCapabilities` estritamente consultivas;
- `ReviewModelRef` opcional e substituível, sem credenciais;
- `AutomatedReviewApplicationService` com contexto confiável, scopes, auditoria antes de exposição e logs minimizados;
- `InMemoryReviewAgentConfigRepository` com isolamento por tenant e versão.

## Story 5.2

A Story 5.2 cria o núcleo de execução consultiva com entradas minimizadas:

- `AutomatedReviewExecutionRequest` representa uma solicitação técnica governada, sem payload livre;
- `ReviewInputCandidate` aceita apenas valores escalares seguros e rejeita payload bruto;
- `InputMinimizationPlan` aplica `ReviewAgentPrompt.input_allowlist` e classifica campos como `included`, `masked`, `omitted`, `referenced` ou `tokenized`;
- `AutomatedReviewExecutionResult` registra somente resultado consultivo, sem decisão final, termos aprovados ou ações externas;
- `ConsultativeReviewExecutor` isola a execução consultiva atrás de uma porta, com adapter mockado no MVP;
- `InMemoryReviewExecutionRepository` persiste apenas snapshot minimizado e metadados seguros.

## Segurança e privacidade

- `tenant_id` e `tenant_isolation_tier` vêm do `PropagatedContext` confiável.
- O MVP aceita apenas `tenant_isolation_tier=bridge` neste serviço.
- Logs sempre omitem payload de comando com `payload="[OMITIDO]"`.
- Eventos auditáveis carregam somente detalhes seguros, como IDs técnicos, versão e fingerprint de prompt.
- Prompt, payload bruto, CPF, CNPJ, e-mail, telefone, endereço, token, segredo, header sensível e dado financeiro detalhado não devem aparecer em logs, auditoria ou erros.
- Execuções consultivas registram contagens por classificação de minimização, política aplicada e referências técnicas, sem entrada bruta.

## Comandos locais

```bash
.venv/bin/pytest services/automated-review/tests/unit
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/pyright
```

## Fora do escopo atual

- SDK de IA ou chamada real a provedor/modelo.
- Endpoint público HTTP, gRPC real ou NATS JetStream.
- Banco real, migration, outbox/inbox ou secret manager.
- Evidência consultiva final vinculada à proposta.
- Dashboard, métrica de negócio ou seleção nominal de fornecedor/modelo.
- Validação profunda de saída de IA e guardrails de resposta, que ficam para a Story 5.3.
