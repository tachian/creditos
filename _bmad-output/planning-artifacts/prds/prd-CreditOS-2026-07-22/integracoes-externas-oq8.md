# Integrações externas prioritárias - OQ-8

## Decisão registrada

O CreditOS não escolherá fornecedores externos nominais no PRD. O MVP deve estar preparado para consultar classes prioritárias de serviços externos por meio de adapters substituíveis, mocks/sandbox, contratos versionados e modelo de custo por operação.

Fornecedores reais serão definidos posteriormente por caso comercial, parceiro, homologação, requisito regulatório ou necessidade operacional.

## Classes de integração prioritárias

| Prioridade | Classe | Uso principal no MVP |
| --- | --- | --- |
| 1 | Cadastro, validação documental, KYC e KYB | Validar PF/PJ, documentos, situação cadastral, representantes e sócios quando aplicável |
| 2 | Bureau de crédito, restritivos e indicadores financeiros | Enriquecer análise de crédito, risco e capacidade de pagamento quando permitido |
| 3 | Antifraude e contexto digital | Reduzir fraude em BNPL, crédito pessoal digital e onboarding remoto |
| 4 | Recebíveis, lastro e elegibilidade | Apoiar produtos de recebíveis, FIDC, sacados/pagadores e concentração |
| 5 | Open Finance ou fontes financeiras equivalentes | Usar dados autorizados por consentimento quando houver parceiro/instituição habilitada |
| 6 | Webhooks/callbacks e notificações | Notificar clientes sobre decisão, mudança de status e falhas recuperáveis |

## Relação por produto MVP

| Produto | Classes mínimas recomendadas | Observações |
| --- | --- | --- |
| Crédito pessoal | KYC, bureau e antifraude | Open Finance pode melhorar renda/capacidade, mas não deve bloquear o MVP |
| BNPL | Antifraude, KYC leve e bureau leve ou condicional | Latência e custo por chamada são críticos |
| Crédito PJ/capital de giro | KYB, bureau PJ e representantes/sócios | Pode exigir dados financeiros autorizados em evolução |
| Recebíveis/FIDC | KYB, recebíveis/lastro e sacados/pagadores | Bureau PJ complementa risco de cedente e pagador |

## Modelo de custo por operação

O custo real de fornecedores não precisa estar definido agora, mas o produto precisa controlar custo desde o MVP.

Requisitos para o modelo:

- Calcular custo estimado por proposta com base nas classes de integração planejadas.
- Registrar custo real quando um fornecedor estiver configurado.
- Registrar tenant, produto, proposta, classe de integração, adapter, fornecedor quando existir, quantidade de chamadas, tentativas, fallback e resultado.
- Permitir teto de custo por tenant, produto, proposta ou estratégia de decisão.
- Projetar custos para dashboards de negócio no `Reporting & Insights Service`.
- Manter rastreabilidade sem registrar dados sensíveis em claro.

## Critérios para escolha futura de fornecedores

- Cobertura PF/PJ e aderência aos produtos MVP.
- Latência, SLA, disponibilidade, limites de taxa e suporte a paralelização.
- Qualidade, atualidade, explicabilidade e rastreabilidade dos dados.
- Segurança, privacidade, LGPD, minimização, retenção e contrato de tratamento de dados.
- Sandbox, mocks, versionamento, idempotência e testes de contrato.
- Custo por chamada, pacote, volume, tenant e consulta enriquecida.
- Risco de lock-in, complexidade de homologação e maturidade operacional.

## Consequências para Architecture

- O `Integration Service` deve implementar anti-corruption layers para provedores externos.
- O domínio de decisão não deve depender de payloads, nomes, erros ou semântica proprietária de fornecedor.
- Integrações externas devem executar de forma assíncrona e paralelizável, com fan-out/fan-in, timeout, retry seguro, DLQ ou equivalente e resultados parciais.
- Políticas de decisão devem declarar quais classes de integração são obrigatórias, opcionais ou condicionais.
- Observabilidade deve separar falhas por tenant, produto, classe de integração, adapter e fornecedor.

## Consequências para ADRs

ADRs necessários:

- Estratégia de adapters e anti-corruption layer para provedores externos.
- Modelo de custo de integrações externas.
- Política de timeout, retry, fallback, DLQ e resultado parcial.
- Critérios de homologação e substituição de fornecedores.
- Uso futuro de Open Finance e tratamento de consentimento.

## Referências usadas

- OWASP API Security Top 10 2023: `https://owasp.org/API-Security/editions/2023/en/0x11-t10/`
- OWASP API10:2023 Unsafe Consumption of APIs: `https://owasp.org/API-Security/editions/2023/en/0xaa-unsafe-consumption-of-apis/`
- Banco Central do Brasil - Open Finance: `https://www.bcb.gov.br/estabilidadefinanceira/openfinance_participantes`
- Banco Central do Brasil - SCR: `https://www.bcb.gov.br/estabilidadefinanceira/scr`
