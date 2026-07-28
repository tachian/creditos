# Review — Segurança e Compliance

Veredito: aprovado com ressalvas fortes; bom spine, mas ainda não pronto para produção regulada.

## Achados priorizados

1. Severidade alta — LGPD operacional ficou deferida: papéis controlador/operador, direitos dos titulares, RIPD/DPIA, incidentes e bases legais precisam virar invariantes. Recomendação: discutir.
2. Severidade alta — identidade interna/mTLS para gRPC e workloads está deferida, apesar de tráfego sensível entre serviços. Recomendação: autofix.
3. Severidade alta — multi-tenancy define propagação de `tenant_id`, mas falta enforcement verificável em banco, filas, cache, storage e testes negativos cross-tenant. Recomendação: autofix.
4. Severidade média — explicabilidade de crédito existe por códigos de motivo, mas falta obrigação explícita de justificativa compreensível, contestação/revisão e monitoramento de viés/drift. Recomendação: discutir.
5. Severidade média — imutabilidade/auditoria não resolve claramente conflito entre retenção, expurgo LGPD, backups e prova de descarte. Recomendação: discutir.

## Resumo

A arquitetura é sólida em separação de domínios, auditoria, minimização de dados e IA consultiva, porém deixa pontos regulatórios críticos como itens deferidos. Antes de produção, recomenda-se promover LGPD operacional, segurança service-to-service, enforcement de isolamento por tenant, explicabilidade/contestação de decisões e política de retenção/expurgo para invariantes arquiteturais adotadas.
