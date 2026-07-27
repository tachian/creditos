# Retenção, mascaramento e descarte - OQ-10

## Decisão registrada

O CreditOS adotará uma política de proteção de dados por classe de dado e contexto de uso.

Máscara forte será o padrão para logs, traces, dashboards, telemetria, relatórios agregados e respostas operacionais. Máscara moderada será permitida apenas em telas autorizadas quando houver necessidade legítima de reconhecimento visual. Dados completos só poderão ser descriptografados ou exibidos com permissão elevada, justificativa e auditoria.

O sistema não deve depender de CPF, CNPJ ou e-mail visível para identificar uma proposta, pessoa ou empresa. A identificação operacional deve usar `proposal_id`, `customer_reference`, correlation ID, trace ID, hash seguro ou busca exata autorizada.

## Princípios

- Minimizar coleta, persistência, transmissão, logs e respostas.
- Não persistir payload sensível bruto por padrão.
- Separar reconhecimento visual de correlação técnica.
- Usar máscara forte por padrão e liberar máscara moderada somente por contexto autorizado.
- Criptografar ou tokenizar dados completos quando a persistência for indispensável.
- Auditar todo acesso a dado completo ou busca por dado original.
- Usar dados sintéticos em testes.

## Máscaras por contexto

| Dado | Logs, traces e dashboards | Tela autorizada | Correlação técnica |
| --- | --- | --- | --- |
| CPF | `***.***.***-09` ou omissão | `123.***.***-09` | hash com salt/pepper |
| CNPJ | `**.***.***/****-90` ou omissão | `12.***.***/0001-90` | hash com salt/pepper |
| E-mail | `j***@dominio.com` ou omissão | `jo***@dominio.com` | hash normalizado |
| Telefone | `(**) *****-4321` ou omissão | `(11) *****-4321` | hash normalizado |
| Nome | `J*** S***` ou omissão | `João S***` quando indispensável | evitar correlação por nome |
| Endereço | omissão | cidade/UF ou endereço mascarado | evitar correlação por endereço |
| Conta bancária | `****5-6` ou omissão | `****5-6` | hash ou token |
| Agência | `**34` ou omissão | `**34` | hash ou token |
| Cartão | nunca logar | últimos 4 dígitos quando aplicável | token PCI ou equivalente |
| Documento/imagem | nunca logar | referência segura | hash do arquivo e storage protegido |
| Token, senha, secret, API key | nunca logar | nunca exibir | não aplicável |
| Renda ou dado financeiro | faixa, bucket ou omissão | faixa ou valor criptografado sob permissão | bucket/agregação |
| Payload externo sensível | omissão | snapshot minimizado quando indispensável | hash/referência |

## Política por contexto de uso

| Contexto | Regra |
| --- | --- |
| Logs técnicos | Máscara forte ou omissão; nunca payload bruto ou segredo |
| Traces | Sem dados pessoais; usar identificadores técnicos e atributos de baixa cardinalidade |
| Dashboards internos | Agregados, métricas, status e custos; sem identificadores diretos completos |
| Dashboards customer-facing | Apenas projeções curadas do próprio tenant; sem telemetria bruta |
| Tela operacional autorizada | Máscara moderada permitida para reconhecimento visual |
| Auditoria | Evidência mínima suficiente; referências, hashes e dados criptografados quando indispensáveis |
| Banco transacional | Criptografia/tokenização para dados completos necessários |
| IA e modelos | Dados minimizados, anonimizados ou pseudonimizados; sem identificadores diretos por padrão |
| Testes | Dados sintéticos obrigatórios |

## Regras de identificação e suporte

- Identificação primária deve usar `proposal_id`, `customer_reference`, correlation ID ou trace ID.
- Correlação por CPF, CNPJ, e-mail ou telefone deve usar hash seguro normalizado.
- Busca exata por dado original pode existir, mas deve exigir permissão elevada, justificativa e auditoria.
- Resultado de busca por dado original não deve exibir o valor completo por padrão.
- Operadores não devem pedir CPF, CNPJ ou e-mail completo quando outro identificador seguro estiver disponível.

## Política inicial de retenção

| Classe | Retenção inicial |
| --- | --- |
| Logs operacionais mascarados | 90 dias hot, com arquivo conforme contrato |
| Traces técnicos | 15 a 30 dias |
| Métricas técnicas agregadas | 13 meses |
| Proposta canônica minimizada | prazo contratual/regulatório aplicável |
| Evidência decisória minimizada | 5 anos ou prazo maior aplicável |
| Auditoria | 5 anos ou prazo maior aplicável |
| Payload sensível bruto | não persistir por padrão; transitório apenas quando indispensável |
| Dados para IA/modelos | definir em backlog específico com minimização, anonimização ou pseudonimização |

Os prazos acima são baseline de produto e devem ser validados antes de produção por jurídico/compliance conforme produto, tenant, jurisdição, contrato, tipo de instituição e obrigação regulatória aplicável.

## Requisitos verificáveis

- Nenhum log crítico contém CPF, CNPJ, e-mail, telefone, token, segredo, documento, renda detalhada ou payload sensível completo.
- Campos persistidos possuem `data_class`, finalidade, base legal, owner, retenção, regra de descarte e regra de mascaramento.
- Telas autorizadas diferenciam máscara forte e máscara moderada por permissão.
- Acesso a dado completo exige permissão elevada, justificativa e evento de auditoria.
- Busca por dado original é auditada e não exibe valor completo por padrão.
- Testes automatizados verificam vazamento de dados sensíveis em logs e respostas.

## Consequências para Architecture

- Definir serviço, biblioteca ou componente central para mascaramento, hash e classificação de dados.
- Definir estratégia de salt/pepper e rotação para hashes de correlação.
- Definir onde dados completos serão criptografados, tokenizados ou omitidos.
- Definir política de exclusão, expurgo, retenção legal e exceções por tenant.
- Definir padrões para logs, traces, eventos, snapshots de integração externa e evidências decisórias.

## ADRs necessários

- Classificação de dados e política de retenção.
- Mascaramento contextual e níveis de exposição.
- Hash seguro para correlação de identificadores.
- Criptografia/tokenização de dados sensíveis persistidos.
- Busca exata autorizada e auditoria de acesso a dado completo.
- Descarte, expurgo e retenção legal.

## Referências usadas

- LGPD, Lei nº 13.709/2018: `https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm`
- ANPD, materiais orientativos: `https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes`
- OWASP Logging Cheat Sheet: `https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html`
- NIST SP 800-92, Guide to Computer Security Log Management: `https://csrc.nist.gov/pubs/sp/800/92/final`
