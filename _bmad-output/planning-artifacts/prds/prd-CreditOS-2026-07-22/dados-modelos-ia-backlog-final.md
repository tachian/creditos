# Backlog final - dados, modelos próprios e IA

Data: 2026-07-24
Status: backlog futuro, fora do MVP operacional

## Objetivo

Criar, no final do projeto, um processo governado para capturar, curar e utilizar dados do CreditOS em modelos próprios e IA, sem incluir identificadores diretos sensíveis por padrão.

Essa capacidade não substitui a revisão automatizada consultiva do MVP. Ela é uma trilha futura para melhoria de modelos, avaliação de performance, simulação, aprendizado estatístico, monitoramento de viés e evolução de políticas.

## Decisão

O processo futuro deve trabalhar com datasets minimizados, anonimizados ou pseudonimizados. Identificadores diretos sensíveis não devem entrar em datasets analíticos por padrão.

Exemplos de dados que devem ser excluídos ou substituídos por referências seguras:

- CPF.
- CNPJ quando usado como identificador direto do cliente analisado.
- Nome.
- Rua e endereço completo.
- Telefone.
- E-mail.
- Documento bruto.
- Credenciais, tokens e secrets.
- Payload bruto de integrações externas.

## Dados candidatos permitidos

Dados candidatos devem passar por classificação e aprovação antes de uso:

- Features derivadas de renda, faturamento, endividamento, recebíveis e histórico.
- Faixas, buckets, scores internos, contagens e indicadores agregados.
- Produto, canal, prazo, valor solicitado, resultado, códigos de motivo e política aplicada.
- Dados temporais normalizados, como mês de submissão, idade aproximada da empresa ou faixa de atraso.
- Métricas de performance de decisão, funil, inconclusão e aprovação com alterações.

## Requisitos futuros

- Definir base legal, finalidade e limites de uso.
- Definir política de segregação por tenant.
- Definir critérios de anonimização e pseudonimização.
- Criar catálogo de features com owner, descrição, fonte, transformação e classificação de dados.
- Versionar datasets, features, modelos, avaliações e aprovações.
- Registrar lineage de dados do evento original até o dataset utilizado.
- Medir drift, performance, viés, explicabilidade e estabilidade.
- Bloquear uso de dados sem consentimento/base legal/finalidade compatível.
- Permitir descarte, retenção e reprocessamento conforme política.
- Garantir que dados usados para IA não permitam reidentificação indevida.

## Arquitetura futura sugerida

A Architecture deve decidir se essa capacidade será:

1. um domínio separado `Data & Model Governance`;
2. uma plataforma analítica isolada consumindo eventos minimizados;
3. uma extensão controlada de `Reporting & Insights`.

Minha recomendação inicial é tratar como domínio futuro separado quando houver uso real para treinamento, avaliação ou governança de modelos próprios.

## Fontes e cautelas regulatórias

- A LGPD prevê princípios como finalidade, adequação, necessidade, segurança, prevenção e responsabilização.
- A LGPD trata dados anonimizados de forma distinta, salvo quando a anonimização puder ser revertida.
- A ANPD possui materiais sobre segurança, agentes de tratamento e consulta pública sobre anonimização e pseudonimização.

Fontes consultadas:

- LGPD, Lei nº 13.709/2018: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
- ANPD, Guia de Segurança da Informação: https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-publica-guia-de-seguranca-para-agentes-de-tratamento-de-pequeno-porte
- ANPD, Guia de Agentes de Tratamento: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-para-definicoes-dos-agentes-de-tratamento-de-dados-pessoais-e-do-encarregado
- ANPD, Consulta sobre Anonimização e Pseudonimização: https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-abre-consulta-a-sociedade-sobre-o-guia-de-anonimizacao-e-pseudonimizacao
