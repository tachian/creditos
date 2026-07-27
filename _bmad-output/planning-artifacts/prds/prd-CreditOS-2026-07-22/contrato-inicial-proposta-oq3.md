# Contrato inicial de proposta - OQ-3

Data: 2026-07-24
Status: decisão registrada para PRD e insumo de Architecture/API design

## Decisão

O contrato inicial de proposta do CreditOS será um contrato canônico, versionado e fechado por schema. Ele deve suportar CPF e CNPJ, os produtos MVP (`personal_credit`, `bnpl`, `business_credit`, `receivables`) e revisão automatizada consultiva por IA quando configurada.

O contrato não deve usar `selected_plan`, `plan_id` ou catálogo de planos da financeira. O cliente informa apenas os termos solicitados em `operation.requested_terms`. O CreditOS avalia esses termos e retorna decisão, aprovação com alterações, solicitação de dados adicionais, reprovação ou estado inconclusivo.

O MVP não terá fila operacional de análise manual, decisão manual ou override humano. Quando houver revisão por IA, ela será consultiva e auditável; a decisão final continuará dependente de política versionada, regras rastreáveis e códigos de motivo.

## Estrutura canônica

```json
{
  "schema_version": "1.0",
  "external_proposal_id": "prop-cliente-123",
  "idempotency_key": "idem-abc-123",
  "person_type": "PF",
  "product_type": "personal_credit",
  "channel": "api",
  "operation": {
    "requested_terms": {
      "amount": 5000,
      "currency": "BRL",
      "installments": 6,
      "down_payment": 500,
      "first_due_date": "2026-08-15"
    }
  },
  "borrower": {
    "document_type": "CPF",
    "document": "00000000000",
    "name": "Maria Silva",
    "birth_date": "1990-01-01"
  },
  "participants": [],
  "consents": [],
  "provided_data": {},
  "risk_context": {},
  "product_data": {
    "personal_credit": {}
  },
  "decision_options": {
    "execution_mode": "sync",
    "review_strategy": "ai_advisory",
    "fallback_action": "request_more_data",
    "max_wait_ms": 3000
  },
  "callback": {}
}
```

## Núcleo comum

| Campo | Obrigatoriedade | Regra |
| --- | --- | --- |
| `schema_version` | Obrigatório | Versão do schema público usado na submissão. |
| `external_proposal_id` | Obrigatório | Identificador da proposta no sistema do cliente; não deve conter CPF, CNPJ, e-mail ou dado sensível. |
| `idempotency_key` | Obrigatório | Chave usada para retry seguro e prevenção de duplicidade. |
| `person_type` | Obrigatório | `PF` ou `PJ`. |
| `product_type` | Obrigatório | `personal_credit`, `bnpl`, `business_credit` ou `receivables` no MVP. |
| `channel` | Obrigatório | Canal padronizado e habilitado para o tenant, como `api`, `batch`, `portal`, `partner`, `checkout` ou `backoffice`. |

`tenant_id` não deve ser tratado como fonte confiável no body. O tenant deve vir da autenticação, token, chave de API ou contexto da rota. Se uma referência de tenant for enviada por compatibilidade futura, ela deve ser validada contra o tenant autenticado.

## `operation.requested_terms`

`requested_terms` representa as condições solicitadas pelo cliente ou solicitante. Elas não são condições aprovadas.

| Campo | Obrigatoriedade | Regra |
| --- | --- | --- |
| `amount` | Obrigatório | Valor solicitado para crédito, compra, capital de giro ou antecipação. |
| `currency` | Obrigatório | `BRL` no MVP. |
| `installments` | Condicional | Obrigatório quando houver parcelamento. |
| `down_payment` | Opcional | Entrada ou pagamento inicial; deve ser maior ou igual a zero. |
| `first_due_date` | Condicional | Obrigatório quando houver agenda de vencimento. |

Validações mínimas: `amount > 0`, `currency = BRL`, `installments > 0` quando informado, `down_payment >= 0`, datas em ISO 8601 e valores monetários sem ponto flutuante binário.

## `borrower`

O `borrower` identifica o tomador principal da análise. O bloco deve ser pequeno e não deve virar cadastro mestre.

### PF

| Campo | Obrigatoriedade | Regra |
| --- | --- | --- |
| `document_type` | Obrigatório | `CPF`. |
| `document` | Obrigatório | CPF com validação de formato e dígito verificador. |
| `name` | Obrigatório | Nome do tomador. |
| `birth_date` | Condicional | Exigido por política, produto ou integração. |

### PJ

| Campo | Obrigatoriedade | Regra |
| --- | --- | --- |
| `document_type` | Obrigatório | `CNPJ`. |
| `document` | Obrigatório | CNPJ com validação de formato e dígito verificador. |
| `legal_name` | Obrigatório | Razão social. |
| `trade_name` | Opcional | Nome fantasia. |
| `foundation_date` | Condicional | Exigido por política, produto ou integração. |

Dados como renda, faturamento, telefone, e-mail, endereço, score interno e histórico de relacionamento devem entrar em `provided_data`, não em `borrower`, salvo decisão futura de schema.

## `participants`

`participants` representa pessoas ou empresas relacionadas à proposta, mas que não são necessariamente o tomador principal.

Campos recomendados:

- `participant_ref`: obrigatório quando o participante precisar ser referenciado por consentimento, recebível ou regra.
- `role`: obrigatório; enum inicial inclui `legal_representative`, `shareholder`, `guarantor`, `co_borrower`, `merchant`, `seller`, `payer`, `assignor`, `employer` e `beneficial_owner`.
- `person_type`, `document_type`, `document` e nome/razão social: obrigatórios quando o participante for identificável.
- `relationship`, `ownership_percentage` e `signature_required`: condicionais por produto, política ou integração.

## `consents`

`consents` registra autorização, base legal, finalidade ou referência que justifica o uso de dados na análise.

Campos recomendados:

- `subject_ref`: obrigatório; usar `borrower` para o tomador principal ou `participant_ref` para participantes.
- `basis`: obrigatório quando aplicável; enum inicial inclui `consent`, `contract_execution`, `legal_obligation`, `legitimate_interest` e `credit_protection`.
- `purpose`: obrigatório; enum inicial inclui `credit_analysis`, `risk_analysis`, `fraud_prevention`, `identity_validation`, `open_finance_data_access` e `audit`.
- `source`: obrigatório; enum inicial inclui `customer`, `open_finance`, `bureau`, `partner` e `internal`.
- `granted_at`, `expires_at` e `reference_id`: condicionais por fonte, finalidade e integração.

O contrato deve usar `subject_ref`, não repetir CPF/CNPJ no consentimento quando o titular já estiver em `borrower` ou `participants`.

## `provided_data`

`provided_data` contém dados declarados ou fornecidos pelo cliente. O bloco é opcional no núcleo, mas pode ser obrigatório por política ou produto.

Categorias iniciais:

- `contact`: e-mail e telefone.
- `address`: endereço resumido ou completo conforme política.
- `financial`: renda, faturamento, dívidas declaradas, fluxo de caixa e capacidade declarada.
- `relationship`: tempo de relacionamento, score interno e histórico de atraso.
- `employment`: ocupação, empregador e vínculo.
- `banking`: dados bancários minimizados, nunca credenciais.
- `commerce`: dados comerciais ou de compra.
- `documents`: referências para arquivos controlados, não anexos brutos no JSON.

Não deve existir `extra_data` livre sem schema aprovado.

## `risk_context`

`risk_context` captura dados contextuais disponíveis. Ele não deve exigir que todos os clientes possuam sinais antifraude avançados.

Campos básicos opcionais:

- `ip_address`.
- `user_agent`.
- `device_id`.
- `session_id`.
- `geo`.
- `transaction`.
- `customer_provided_signals`.

Sinais como idade de e-mail, reputação de dispositivo, velocidade de tentativas ou compatibilidade de endereços podem existir, mas devem ser opcionais, versionados e identificados como fornecidos pelo cliente ou calculados pelo CreditOS.

## `product_data`

`product_data` é obrigatório e deve conter exatamente um sub-bloco compatível com `product_type`.

### `personal_credit`

Campos iniciais:

- `employment_type`.
- `occupation`.
- `declared_monthly_income`.
- `declared_monthly_debt`.
- `income_source`.

### `bnpl`

Campos iniciais:

- `merchant_reference`.
- `order_reference`.
- `purchase_amount`, quando diferente de `requested_terms.amount`.
- `cart_items_count`.
- `delivery_method`.
- `shipping_address_ref`.

### `business_credit`

Campos iniciais:

- `business_activity_code`.
- `declared_monthly_revenue`.
- `declared_monthly_debt`.
- `company_age_months`.
- `requested_collateral`.

### `receivables`

Campos iniciais:

- `receivables`: lista obrigatória de recebíveis.
- `external_receivable_id`.
- `payer_ref`.
- `face_value`.
- `due_date`.
- `document_number`, com cuidado para não expor dado sensível.

## `decision_options`

`decision_options` define comportamento de execução e contingência.

| Campo | Obrigatoriedade | Regra |
| --- | --- | --- |
| `execution_mode` | Obrigatório | `sync` ou `async`. |
| `review_strategy` | Obrigatório | `policy_only` ou `ai_advisory`; não há `manual_review` no MVP. |
| `fallback_action` | Obrigatório | `request_more_data`, `unable_to_decide` ou `reject_by_policy`. |
| `max_wait_ms` | Opcional | Tempo máximo aceito pelo cliente em execução síncrona. |

`ai_advisory` permite revisão automatizada consultiva por IA. A saída da IA não pode aprovar ou reprovar sozinha; ela deve alimentar explicabilidade, detecção de lacunas, inconsistências ou sinais para política versionada.

## `callback`

`callback` define notificações quando a decisão não for imediata ou quando o tenant desejar eventos por webhook.

Campos recomendados:

- `url`: obrigatório para `execution_mode = async`, salvo webhook pré-configurado por tenant.
- `events`: opcional; se ausente, usar eventos padrão.
- `secret_reference`: referência a segredo cadastrado, nunca segredo bruto.
- `headers_ref`: referência a configuração de headers cadastrada.

Callbacks devem ser assinados, versionados, idempotentes, rastreados e livres de payload sensível desnecessário.

## Resposta esperada de decisão

A resposta da análise deve diferenciar termos solicitados de termos aprovados.

Resultados iniciais:

- `approved`.
- `approved_with_changes`.
- `rejected`.
- `request_more_data`.
- `unable_to_decide`.
- `controlled_error`.

Quando houver alteração, a resposta deve incluir `approved_terms`. Quando houver solicitação de dados, deve incluir `required_data`. Toda resposta deve incluir correlation ID, versão de contrato, política aplicada, códigos de motivo e referência de auditoria.

## Fontes e cautelas regulatórias

- A LGPD prevê direitos relacionados a decisões tomadas unicamente com base em tratamento automatizado de dados pessoais, incluindo decisões ligadas a perfil de crédito.
- A ANPD destaca transparência, explicação dos critérios e revisão de decisões automatizadas como temas relevantes.
- O CreditOS deve preservar evidências, critérios, versões e explicabilidade para que a instituição cliente consiga atender solicitações de titulares e obrigações regulatórias aplicáveis.

Fontes consultadas:

- LGPD, Lei nº 13.709/2018: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
- ANPD, Direitos dos Titulares: https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares
- ANPD, IA e decisões automatizadas: https://www.gov.br/anpd/pt-br/assuntos/projetos-acoes-iniciativas/sandbox/por-que-inteligencia-artificial
