---
baseline_commit: fa323c8c848288066be901e0e99f35c42d884c73
---

# Story 6.6: Logs Estruturados e Mascaramento Obrigatório

Status: done

## Story

Como operador da plataforma,
quero logs estruturados em requisições e integrações,
para que problemas sejam rastreáveis sem expor dados sensíveis.

## Acceptance Criteria

1. **Envelope obrigatório de log operacional:** dado qualquer serviço do CreditOS, quando uma requisição, comando, job, evento, chamada gRPC ou chamada de integração gerar log operacional, então o evento deve conter `timestamp` UTC, `service.name`, `service.version`, `deployment.environment`, `correlation_id`, `request_id`, `trace_id`, `tenant_id` quando confiável, `operation`, `source`, `destination`, `contract`, `contract_version`, `status`, `duration_ms` e resultado técnico seguro.
2. **Logs de integrações internas e externas:** dada uma chamada interna ou externa, quando ela for registrada, então o log deve incluir origem, destino, contrato, versão, tenant, trace, status, tentativas, timeout, duração e resultado minimizado, sem registrar payload bruto de provedor, headers sensíveis, token, segredo ou body de request/response.
3. **Mascaramento obrigatório e centralizado:** dado qualquer valor passado para logs, `extra`, erro, contexto propagado ou metadata operacional, quando o log for construído, então CPF, CNPJ, e-mail, telefone, token, senha, secret, API key, documento/imagem, payload bruto e dado financeiro detalhado devem ser omitidos, mascarados ou substituídos por marcador seguro antes de sair do helper central.
4. **Prevenção de log injection e chaves perigosas:** dado texto ou metadado vindo de entrada externa, quando for serializado em log, então caracteres de controle, CR/LF, delimitadores perigosos e chaves sensíveis/ambíguas devem ser normalizados, omitidos ou rejeitados para evitar forjar linhas/campos de log.
5. **Separação entre logs e auditoria oficial:** dado um evento que exija auditoria oficial, quando a operação também gerar log operacional, então o log deve permanecer complementar e minimizado; ele não substitui `AuditEvent`, não deve conter payload de auditoria bruto e deve preservar `correlation_id`/`trace_id` para correlacionar com a trilha append-only.
6. **Compatibilidade com padrões atuais:** dado o pacote existente `creditos_observability`, quando a story for implementada, então a solução deve evoluir `build_structured_log` e utilidades de `creditos_security.masking` sem criar outro framework paralelo de logging nem adicionar dependências externas sem ADR/justificativa.
7. **Gates locais de privacidade:** dado a suíte de testes, quando logs e máscaras forem exercitados com dados sintéticos sensíveis, então nenhum log serializado deve conter CPF/CNPJ completos, e-mail completo, telefone completo, token, segredo, payload bruto, prompt/output de IA, documento, renda detalhada ou headers de autorização; `ruff`, `pyright` e testes focados devem passar.

## Tasks / Subtasks

- [x] CTOS-360 — Endurecer helper central de logs estruturados (AC: 1, 3, 4, 6)
  - [x] Revisar `packages/observability/src/creditos_observability/logging.py` para garantir envelope obrigatório e validações de campos técnicos.
  - [x] Adicionar sanitização de texto contra CR/LF/caracteres de controle e normalização segura de `error_type`, `status`, `operation`, `source`, `destination`, `contract` e `contract_version`.
  - [x] Garantir que `duration_ms` continue finito/não negativo e que `timestamp` seja UTC em formato ISO.

- [x] CTOS-361 — Ampliar mascaramento reutilizável de dados sensíveis (AC: 3, 4, 7)
  - [x] Evoluir `packages/security/src/creditos_security/masking.py` sem quebrar a API atual `mask_text`, `mask_sensitive_data` e `hmac_sha256_identifier`.
  - [x] Cobrir chaves e fragmentos para `headers`, `authorization`, `cookie`, `set_cookie`, `request_body`, `response_body`, `prompt`, `completion`, `embedding`, `provider_payload`, `document_image`, `cpf`, `cnpj`, `email`, `phone`, `income` e equivalentes em português.
  - [x] Manter hash HMAC para correlação como função explícita; não aplicar hash silencioso com chave ausente.

- [x] CTOS-362 — Padronizar logs de integrações e chamadas internas (AC: 1, 2, 5, 6)
  - [x] Reutilizar o envelope em `services/integration/src/creditos_integration/application/service.py` e validar campos de `attempts`, `timeout_ms`, `integration_class`, provider/adapters mockados e resultado seguro.
  - [x] Confirmar que adapters gRPC/Event/CloudEvent existentes em `identity-tenant` mantêm contexto sem token, CPF/CNPJ, e-mail ou payload bruto.
  - [x] Não introduzir gRPC real, NATS real, OpenTelemetry Collector real, exporter externo ou storage de logs nesta story.

- [x] CTOS-363 — Documentar contrato operacional de logging seguro (AC: 1, 2, 3, 5, 6)
  - [x] Atualizar `packages/observability/README.md` com envelope mínimo, campos proibidos, exemplos seguros e limite entre log operacional e auditoria oficial.
  - [x] Atualizar `packages/security/README.md` com regras de máscara forte, omissão, correlação por HMAC e prevenção de log injection.
  - [x] Registrar explicitamente que dashboards/customer-facing do Epic 7 devem consumir dados agregados/curados, não logs brutos.

- [x] CTOS-364 — Criar testes focados de logging e mascaramento (AC: 1, 2, 3, 4, 7)
  - [x] Criar testes unitários para `creditos_observability.logging` cobrindo envelope obrigatório, payload omitido, `extra` mascarado, sanitização e integração com `ObservabilityContext`.
  - [x] Criar testes unitários para `creditos_security.masking` cobrindo CPF, CNPJ, e-mail, telefone, tokens, secrets, cookies, payloads, prompts/outputs, documentos e dados financeiros sintéticos.
  - [x] Adicionar teste de integração leve com logs de serviço existente para provar que campos obrigatórios aparecem e dados sensíveis não vazam.

- [x] CTOS-365 — Sincronizar BMAD e Jira da Story 6.6 (AC: 7)
  - [x] Atualizar `sprint-status.yaml` para `ready-for-dev` após criação da story.
  - [x] Criar/sincronizar subtarefas Jira vinculadas a `CTOS-58` antes da implementação.
  - [x] Na implementação, criar branch `agent/story-6-6-structured-logs-masking` antes de alterar código e mover `CTOS-58` para `Em andamento`.

### Review Findings

- [x] [Review][Patch] Canonicalização de chaves sensíveis ainda permite vazamento por chaves ofuscadas com controles/Unicode, chave vazia ou colisões após sanitização. [`packages/security/src/creditos_security/masking.py:162`]
- [x] [Review][Patch] Variantes comuns de outputs de IA e identificadores estruturados não são omitidas, como `model_output`, `ai_output`, `customer_email`, `customer_cpf` e `document_number`. [`packages/security/src/creditos_security/masking.py:72`]
- [x] [Review][Patch] Campos técnicos obrigatórios aceitam `None` e tipos não string porque `_safe_required_field` converte qualquer valor com `str(...)`. [`packages/observability/src/creditos_observability/logging.py:81`]
- [x] [Review][Patch] Referências técnicas marcadas como seguras aceitam valores aninhados em vez de restringirem fingerprints/digests a strings escalares seguras. [`packages/security/src/creditos_security/masking.py:144`]
- [x] [Review][Patch] Sanitização de texto não cobre separadores Unicode, controles bidi e delimitadores perigosos em campos técnicos, permitindo spoofing/ambiguidade de logs. [`packages/security/src/creditos_security/masking.py:137`]
- [x] [Review][Patch] Máscara de secrets em texto livre pode vazar sufixo quando o valor contém espaços ou aspas. [`packages/security/src/creditos_security/masking.py:19`]
- [x] [Review][Patch] Estruturas cíclicas ou profundamente aninhadas podem derrubar logging por recursão sem limite/detecção de ciclos. [`packages/security/src/creditos_security/masking.py:162`]
- [x] [Review][Patch] Envelope central não explicita um campo minimizado de resultado técnico seguro além de `status`/`status_code`. [`packages/observability/src/creditos_observability/logging.py:38`]

## Dev Notes

### Escopo desta story

- Esta story endurece a base transversal de logs estruturados e mascaramento já existente nos pacotes `creditos_observability` e `creditos_security`.
- A implementação deve priorizar helpers reutilizáveis e testes de contrato local, não backends reais de coleta, dashboards, alertas, SIEM, OpenTelemetry Collector, Loki/Elastic/Grafana ou infraestrutura.
- Logs operacionais são complementares à auditoria oficial. Eventos críticos continuam pertencendo ao `Audit & Evidence`; logs não podem virar trilha oficial nem carregar payload bruto para compensar auditoria.
- O objetivo é deixar impossível que serviços e integrações emitam logs úteis para rastreabilidade, mas perigosos para privacidade.

### Contexto funcional consolidado

- Epic 6 exige que decisões, alterações sensíveis, requisições e integrações sejam rastreáveis com auditoria oficial, logs estruturados, mascaramento e integridade verificável. [Fonte: `_bmad-output/planning-artifacts/epics.md#Epic 6`]
- Story 6.6 exige logs de requisições com timestamp UTC, service name, version, environment, correlation ID, trace ID, tenant, operação, status e duração; integrações devem registrar origem/destino/contrato/versão/tentativas/timeout/resultado sem payload bruto. [Fonte: `_bmad-output/planning-artifacts/epics.md#Story 6.6`]
- OQ-10 define máscara forte como padrão para logs, traces e dashboards; dados completos só podem ser exibidos com permissão elevada, justificativa e auditoria. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md`]
- OQ-11 define que auditoria é separada de logs operacionais e que logs/traces podem ser evidência complementar, mas não substituem a trilha oficial append-only. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`]
- OQ-9 exige observabilidade técnica e de negócio, mas dashboards customer-facing devem expor visões curadas por tenant, não telemetria bruta. [Fonte: `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`]

### Arquitetura e padrões obrigatórios

- Backend segue DDD + arquitetura hexagonal. Pacotes transversais (`packages/observability`, `packages/security`) não podem depender de domínio de produto nem de serviços específicos.
- `packages/observability/src/creditos_observability/logging.py` já fornece `build_structured_log` com envelope base, `payload` omitido, `extra` mascarado e retorno final via `mask_sensitive_data`; a story deve evoluir esse helper em vez de criar logger paralelo.
- `packages/security/src/creditos_security/masking.py` já fornece `mask_text`, `mask_sensitive_data`, `hmac_sha256_identifier`, `OMITTED` e `FINANCIAL_OMITTED`; a story deve preservar compatibilidade de API.
- `ObservabilityContext` já carrega `correlation_id`, `request_id`, `trace_id`, `tenant_id` e `tenant_isolation_tier`; a story deve usá-lo como fonte de rastreabilidade.
- `creditos_security.context` já valida metadata gRPC e CloudEvents sem token, segredo, CPF/CNPJ, e-mail ou payload bruto; não duplicar esse contrato.
- Não adicionar dependências de logging estruturado externas nesta story. A biblioteca padrão e os pacotes locais são suficientes para o MVP.

### Informação técnica atualizada

- OWASP Logging Cheat Sheet recomenda sanitizar dados de eventos para prevenir log injection, incluindo CR/LF e delimitadores, e evitar registro de dados que exponham segredos ou informações sensíveis. [Fonte: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html]
- OpenTelemetry recomenda definir explicitamente `service.name` e usar atributos semânticos para recursos como serviço e ambiente; o projeto já usa `service.name`, `service.version` e `deployment.environment`. [Fonte: https://opentelemetry.io/docs/specs/otel/semantic-conventions/]
- NIST SP 800-92 é a referência de gestão de logs citada no PRD; para esta story, usar apenas como diretriz de segurança/gestão, sem implementar SIEM/retenção física. [Fonte: https://csrc.nist.gov/pubs/sp/800/92/final]

### Arquivos existentes que devem ser lidos antes de alterar

- `packages/observability/src/creditos_observability/logging.py`
  - Estado atual: cria logs estruturados com campos técnicos, valida `duration_ms`/`status_code`, omite `payload` e mascara `extra`.
  - O que mudar: endurecer validação/sanitização e garantir envelope mínimo explícito para requisições e integrações.
  - Preservar: assinatura pública quando possível, retorno `dict[str, Any]`, uso de `ObservabilityContext` e chamada final a `mask_sensitive_data`.

- `packages/security/src/creditos_security/masking.py`
  - Estado atual: mascara CPF/CNPJ/e-mail/telefone em texto, omite secrets/payloads por chave, omite bytes e dados financeiros por chave.
  - O que mudar: ampliar cobertura de chaves sensíveis e sanitizar caracteres de controle sem perder marcadores seguros.
  - Preservar: comportamento atual testado em serviços existentes, HMAC com `secret_key` obrigatório e dados sintéticos nos testes.

- `packages/observability/src/creditos_observability/context.py`
  - Estado atual: cria/propaga correlation ID, request ID, trace ID e tenant quando confiável.
  - O que mudar: evitar alterações se não forem necessárias; se mexer, manter compatibilidade com headers HTTP, metadata gRPC e CloudEvents existentes.
  - Preservar: HTTP não confia tenant do header externo por padrão; gRPC/CloudEvent usam contexto confiável.

- `services/integration/src/creditos_integration/application/service.py`
  - Estado atual: já usa `_log_operation` e `build_structured_log` para catálogo, execução assíncrona, retry/DLQ e custo/resultado.
  - O que mudar: adicionar testes ou ajustes mínimos se faltarem campos de integração (`attempts`, `timeout_ms`, `source`, `destination`, `contract`, `contract_version`) em logs relevantes.
  - Preservar: resultados minimizados, isolamento por tenant e ausência de payload bruto de provider.

- `services/proposal-intake/src/creditos_proposal_intake/application/service.py`
  - Estado atual: usa `_log_operation` com `build_structured_log`; já possui testes que impedem vazamento de CPF/CNPJ, e-mail, token e valores financeiros.
  - O que mudar: apenas se necessário para compatibilizar com helper central.
  - Preservar: idempotência, fingerprint HMAC e validações de proposta.

- `services/audit-evidence/src/creditos_audit_evidence/application/service.py`
  - Estado atual: usa logs estruturados complementares à auditoria oficial; Story 6.5 adicionou WORM e correções de review.
  - O que mudar: evitar alteração salvo ajuste de compatibilidade do helper central.
  - Preservar: `AuditEvent` oficial, hash encadeado, checkpoints, WORM e safe details allowlist.

### Padrões de implementação esperados

- Preferir funções puras pequenas em `masking.py` e `logging.py`, com testes diretos e sem estado global mutável.
- Validar campos técnicos como string segura sem CR/LF, sem bytes e com tamanho limitado quando aplicável.
- Omitir payloads por chave antes de percorrer estruturas profundas; não tentar mascarar body bruto linha a linha.
- Preservar `tenant_id` apenas quando vier de contexto confiável; não registrar tenant vindo de headers HTTP externos não validados.
- Usar `extra` apenas para metadados técnicos de baixa cardinalidade; valores enumeráveis sensíveis devem virar HMAC explícito em fluxo próprio, não ser logados completos.
- Não registrar exceção bruta, stack trace completo, headers completos, request body, response body, token, prompt/output de IA ou payload de provider.

### Testes esperados

- `packages/observability/tests/unit/test_logging.py`
  - Verifica envelope obrigatório com `service.name`, `service.version`, `deployment.environment`, ids de correlação, tenant confiável, operação, origem/destino, contrato, status e duração.
  - Verifica `payload == "[OMITIDO]"` quando payload é informado.
  - Verifica `extra` mascarado para documento, e-mail, telefone, token, secret, headers e dados financeiros.
  - Verifica sanitização contra `\r`, `\n`, caracteres de controle e `error_type` malicioso.

- `packages/security/tests/unit/test_masking.py`
  - Cobre texto livre, dicionários aninhados, listas, bytes, chaves sensíveis, payloads, prompt/output, CPF/CNPJ/e-mail/telefone sintéticos e dados financeiros.
  - Garante que `hmac_sha256_identifier` exige `secret_key` e normaliza identificadores enumeráveis.

- Testes existentes que devem continuar verdes:
  - `services/proposal-intake/tests/unit/test_validate_and_normalize_proposal.py`
  - `services/proposal-intake/tests/unit/test_idempotent_submission.py`
  - `services/integration/tests/unit/test_integration_async_execution.py`
  - `services/audit-evidence/tests/unit/test_audit_worm_export.py`

### Comandos de validação esperados

- `.venv/bin/pytest packages/observability packages/security -q`
- `.venv/bin/pytest services/integration/tests/unit services/proposal-intake/tests/unit services/audit-evidence/tests/unit -q`
- `.venv/bin/ruff format --check .`
- `.venv/bin/ruff check .`
- `.venv/bin/pyright`
- `uv lock --check` quando `uv` estiver disponível; se indisponível e nenhuma dependência for adicionada, registrar limitação ambiental sem alterar `uv.lock`.

### Aprendizados da Story 6.5

- Correções de review exigiram validação explícita antes de gravar evidência imutável; para logs, aplicar a mesma postura: sanitizar/mascarar no helper central antes de armazenar ou retornar o evento.
- A auditoria oficial deve continuar minimizada e separada de logs operacionais; não duplicar `safe_details` nem abrir payload livre.
- Review externo apontou caminhos não auditados por exceções de escopo; nesta story, testes devem cobrir também falhas/rejeições para garantir que logs de erro continuem seguros.
- A suíte completa local pode falhar por `uv` ausente em `scripts/dev`; registrar como limitação ambiental se aparecer, sem mascarar falhas reais dos testes focados.

## Project Structure Notes

- Novos testes devem ficar em `packages/observability/tests/unit/` e `packages/security/tests/unit/`.
- Evitar alterações amplas nos serviços; quando possível, corrigir o helper central para beneficiar todos os serviços.
- Se ajustes em serviços forem necessários, limitar aos métodos `_log_operation` existentes e testes correspondentes.
- Não criar módulo de logging dentro de um serviço específico para resolver problema transversal.

## References

- `_bmad-output/planning-artifacts/epics.md#Story 6.6`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/retencao-mascaramento-descarte-oq10.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/protecao-auditoria-oq11.md`
- `_bmad-output/planning-artifacts/prds/prd-CreditOS-2026-07-22/observabilidade-oq9.md`
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md`
- `_bmad-output/implementation-artifacts/6-5-exportacao-imutavel-para-worm.md`
- `packages/observability/src/creditos_observability/logging.py`
- `packages/security/src/creditos_security/masking.py`
- `packages/security/src/creditos_security/context.py`
- OWASP Logging Cheat Sheet: `https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html`
- OpenTelemetry Semantic Conventions: `https://opentelemetry.io/docs/specs/otel/semantic-conventions/`
- NIST SP 800-92: `https://csrc.nist.gov/pubs/sp/800/92/final`

## Dev Agent Record

### Agent Model Used

Codex GPT-5.1

### Debug Log References

- Story criada a partir do `bmad-create-story` em 2026-09-21.
- Fonte principal: Epic 6 / Story 6.6 em `_bmad-output/planning-artifacts/epics.md`.
- Contexto anterior: Story 6.5 mergeada no PR #58 e `main` sincronizada em `fa323c8`.
- Jira principal identificado: `CTOS-58`; subtarefas criadas: `CTOS-360` a `CTOS-365`.
- Branch criada no início do desenvolvimento: `agent/story-6-6-structured-logs-masking`.
- Jira `CTOS-58` e `CTOS-360` movidos para `Em andamento` no início do `bmad-dev-story`.
- Testes vermelhos criados para logging estruturado, mascaramento e log de integração antes da implementação.
- Validação focada inicial: `.venv/bin/pytest packages/observability/tests/unit/test_logging.py packages/security/tests/unit/test_masking.py -q` — 4 failed, 1 passed.
- Validação pós-implementação focada: `.venv/bin/pytest packages/observability/tests/unit/test_logging.py packages/security/tests/unit/test_masking.py services/integration/tests/unit/test_integration_async_execution.py::test_integration_execution_logs_calls_with_safe_traceability_attempts_and_timeout -q` — 6 passed.
- Validação transversal: `.venv/bin/pytest packages/observability packages/security -q` — 65 passed.
- Validação de serviços-alvo: `.venv/bin/pytest services/integration/tests/unit services/proposal-intake/tests/unit services/audit-evidence/tests/unit -q` — 259 passed.
- Validação ampla de serviços e pacotes: `.venv/bin/pytest services packages -q` — 679 passed.
- Gates: `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .` e `.venv/bin/pyright` — passaram.
- Code review BMAD corrigiu 8 findings de patch: canonicalização de chaves, variantes de output/identificadores, campos obrigatórios não string, referências seguras escalares, Unicode/delimitadores, credenciais com múltiplas palavras, ciclos/profundidade e `technical_result`.
- `uv lock --check` não executou localmente porque `uv` não está disponível no PATH.
- Suíte completa local: `.venv/bin/pytest -q` — 701 passed, 3 failed por limitação ambiental preexistente de socket (`Operation not permitted`) e `uv` ausente nos testes de `tests/test_local_harness.py`.

### Implementation Plan

- Endurecer `build_structured_log` no helper central para sanitizar campos técnicos obrigatórios, rejeitar campo obrigatório vazio e preservar envelope atual.
- Evoluir `mask_sensitive_data` e `mask_text` para omitir containers perigosos, identificadores diretos estruturados, prompts/outputs e headers, mantendo fingerprints/digests técnicos seguros.
- Validar logs de integração com metadados de tentativas e timeout sem payload bruto.
- Documentar contrato operacional em `packages/observability` e `packages/security`.

### Completion Notes List

- Story 6.6 implementada e pronta para `bmad-code-review`.
- Findings do `bmad-code-review` aplicados e story aprovada localmente para commit/push/draft PR.
- `build_structured_log` agora sanitiza campos técnicos contra caracteres de controle/log injection e rejeita campo obrigatório vazio.
- `mask_sensitive_data` agora omite headers, bodies, payloads de provider, prompts, completions, embeddings e identificadores diretos estruturados, preservando referências técnicas seguras como `prompt_fingerprint`.
- `mask_text` agora normaliza caracteres de controle após aplicar máscaras e omissões.
- Logs de dispatch de integração passaram a incluir `attempt_count` minimizado junto de `timeout_ms` e `max_attempts`.
- READMEs de observabilidade e segurança documentam envelope mínimo, campos proibidos, HMAC para correlação e separação entre logs e auditoria oficial.
- Backends reais de logs, SIEM, dashboards, alertas, Collector OpenTelemetry, Loki/Elastic/Grafana e infraestrutura permaneceram fora de escopo.

### File List

- `_bmad-output/implementation-artifacts/6-6-logs-estruturados-e-mascaramento-obrigatorio.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `packages/observability/README.md`
- `packages/observability/src/creditos_observability/logging.py`
- `packages/observability/tests/unit/test_logging.py`
- `packages/security/README.md`
- `packages/security/src/creditos_security/masking.py`
- `packages/security/tests/unit/test_masking.py`
- `services/integration/src/creditos_integration/application/service.py`
- `services/integration/tests/unit/test_integration_async_execution.py`

## Change Log

| Data | Versão | Descrição | Autor |
| --- | --- | --- | --- |
| 2026-09-21 | 0.1 | Story criada via `bmad-create-story`; contexto do Epic 6, OQ-10, OQ-11, OQ-9, pacotes transversais e Story 6.5 consolidado. | Codex |
| 2026-09-21 | 1.0 | Logs estruturados e mascaramento obrigatório implementados com testes, documentação e gates locais. | Codex |
