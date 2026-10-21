# Revisão do AD-25 — 2026-10-21

Escopo: delta de arquitetura aprovado no coaching. Revisão sequencial pelo próprio agente; não representa revisão independente por subagentes.

## Rubrica

- IDs anteriores preservados; AD-25 declara Binds, Prevents e Rule.
- Gate local precede gastos AWS; validações dependentes da cloud ocorrem após provisionamento.
- UX abrange o escopo demonstrável, sem expandir para portal completo fora do MVP.
- Piloto sintético não libera uso de dados reais; AD-24 continua vinculante.
- Conta existente permitida para demonstração; topologia produtiva é reavaliada antes do onboarding.

## Tecnologias e evidências

OpenTofu e AWS são escolhas aprovadas pelo usuário e pesquisadas durante o coaching. Referências oficiais utilizadas: https://opentofu.org/docs/language/settings/backends/s3/ e https://opentofu.org/docs/v1.11/language/state/encryption/ . Este delta não fixa versão nem declara uma região mais barata: versões e preços exigem verificação antes da implementação/provisionamento. Kubernetes/GitOps continuam vinculados às decisões anteriores.

## Fronteiras adversariais

- Bootstrap não pode depender de um backend ainda inexistente: exige procedimento reproduzível e migração de estado temporário.
- Conclusão local não certifica HA/DR AWS: há gates próprios pós-provisionamento.
- Conta compartilhada não autoriza alteração de outros projetos: permissões e recursos devem ter escopo CreditOS.
- Redução de custo não revoga topologia produtiva: exceções exigem registro explícito.
- Estado e planos podem conter dados sensíveis: proteção, locking e segregação são obrigatórios.

Resultado: sem bloqueador identificado neste delta pela revisão sequencial. Validação mecânica do spine passou sem achados. Revisão independente continua recomendada no PR.
