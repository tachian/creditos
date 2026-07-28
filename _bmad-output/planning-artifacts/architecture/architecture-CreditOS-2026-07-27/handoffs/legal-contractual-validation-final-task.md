# Tarefa Final Obrigatória — Validação Jurídica e Contratual

Esta tarefa deve ser executada no final do projeto, antes de produção com cliente real ou onboarding de qualquer tenant que processe dados pessoais de solicitantes.

## Objetivo

Obter validação jurídica e contratual formal de que a operação do CreditOS está aderente à LGPD, aos contratos B2B, às obrigações de incidentes, às responsabilidades entre controlador/operador/suboperador e às políticas de retenção, descarte, auditoria e decisão automatizada.

## Quando Executar

- Após a consolidação de Architecture, PRD, ADRs, epics/stories, runbooks e contratos de API.
- Antes de habilitar produção para cliente real.
- Antes de integrar fornecedores externos que processem dados pessoais em nome de tenant.
- Antes de publicar SLA externo ou material comercial com promessa operacional/jurídica.
- Sempre que houver mudança relevante em finalidade, base legal, suboperador, país/região, IA/modelo, retenção, descarte, decisão automatizada ou produto de crédito/risco.

## Como Executar

1. Preparar um pacote de revisão com Architecture Spine, PRD, matriz de dados, contratos de API, runbooks de incidente, políticas de retenção/descarte, lista de suboperadores, fluxos de IA e dashboards customer-facing.
2. Contratar ou acionar assessoria jurídica com experiência em LGPD, contratos SaaS B2B, crédito/risco, tecnologia financeira, incidentes de segurança e decisão automatizada.
3. Validar o DPA/contrato de tratamento, confirmando papéis LGPD, instruções do controlador, responsabilidades do operador, suboperadores, auditoria, segurança, retenção, descarte e atendimento a titulares.
4. Validar a matriz RACI entre CreditOS, tenant/controlador, jurídico, compliance, segurança, suporte, engenharia e fornecedores para incidentes, direitos dos titulares, revisão de decisão automatizada, retenção/descarte, auditorias e comunicações.
5. Validar o catálogo jurídico de dados: finalidade, base legal, classe, owner, retenção, descarte, exposição, origem da instrução e suboperadores por dado/fluxo.
6. Elaborar ou revisar o RIPD para fluxos de alto risco: crédito, perfil, antifraude, decisão automatizada, Open Finance, IA com dados pessoais e integrações externas relevantes.
7. Validar processo de incidentes: classificação, timeline, evidências, comunicação rápida ao tenant/controlador, suporte à comunicação à ANPD/titular e retenção de registros.
8. Validar SLAs internos/externos: não publicar SLA público sem histórico operacional, aprovação comercial e validação jurídica; definir SLAs LGPD de suporte ao controlador.
9. Validar textos e materiais: termos contratuais, política de privacidade aplicável, anexos técnicos, comunicação de incidentes, comunicação ao titular quando aplicável e descrição de decisão automatizada/explicabilidade.
10. Registrar aprovação formal, ressalvas, responsáveis, versão dos documentos revisados, data, escopo, pendências e plano de remediação.

## Checklist de Aceite

- [ ] DPA/contrato revisado e aprovado por jurídico.
- [ ] Papéis LGPD confirmados por finalidade: controlador, operador, controlador independente e suboperador.
- [ ] Matriz RACI aprovada para incidentes, direitos dos titulares, auditoria, retenção/descarte e decisão automatizada.
- [ ] Catálogo jurídico de dados aprovado com finalidade, base legal, retenção, descarte, owner e exposição.
- [ ] RIPD elaborado/revisado para fluxos de alto risco antes de produção.
- [ ] Lista de suboperadores aprovada, com finalidade, região/país, dados tratados, contrato e processo de substituição/notificação.
- [ ] Processo de incidentes aprovado, incluindo SLA de comunicação ao tenant/controlador e suporte à ANPD/titular.
- [ ] Políticas de retenção, descarte, WORM, tombstone, bloqueio de exposição e prova de descarte aprovadas.
- [ ] Processo de direitos dos titulares validado: localizar, exportar, corrigir, bloquear, anonimizar, eliminar e revisar/contestar decisão automatizada.
- [ ] SLA externo aprovado ou explicitamente mantido fora do MVP.
- [ ] Textos contratuais, anexos técnicos e comunicações revisados.
- [ ] Evidência formal da aprovação anexada ao pacote de release/onboarding.

## Saídas Esperadas

- Parecer ou aprovação jurídica formal.
- DPA/contrato e anexos técnicos aprovados.
- Matriz RACI aprovada.
- Catálogo jurídico de dados aprovado.
- RIPD aprovado ou plano de remediação documentado.
- Lista de suboperadores aprovada.
- Runbook de incidente validado.
- Registro de pendências com owner e prazo.

## Fontes de Referência

- LGPD — Lei nº 13.709/2018: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm
- ANPD — RIPD: https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/relatorio-de-impacto-a-protecao-de-dados-pessoais-ripd
- ANPD — Comunicação de Incidente de Segurança: https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis
- ANPD — Guia de Agentes de Tratamento: https://www.gov.br/anpd/pt-br/assuntos/noticias/nova-versao-do-guia-dos-agentes-de-tratamento
