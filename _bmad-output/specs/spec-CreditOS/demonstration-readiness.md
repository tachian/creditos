# Prontidão da Demonstração — CreditOS

Companion derivado do memlog da SPEC e do AD-25. Detalhes de arquitetura continuam sob autoridade do Architecture Spine adotado.

## Sequência Obrigatória

| Estágio | Critérios verificáveis |
| --- | --- |
| Conclusão local | Funcionalidades e todas as telas previstas para demonstração implementadas e integradas; jornadas, erros, autorização e isolamento validados; fluxo E2E verde |
| Preparação IaC | OpenTofu revisado e validado estaticamente, versões/providers fixados e bootstrap/backend documentados, sem apply nem criação antecipada de recursos |
| Primeiro provisionamento | Conclusão local comprovada, região escolhida por menor custo total estimado dos serviços compatíveis usando preços oficiais vigentes, orçamento e plano explicitamente aprovados |
| Piloto AWS | Runtime dos sete serviços, HTTP autenticado, gRPC, NATS e PostgreSQL reais; observabilidade, auditoria, webhooks, recuperação e runbooks mínimos validados na cloud |
| Produção | Gates das AD-12 a AD-24, persistência/isolamento, IaC/GitOps, supply chain, SLOs, backup/restore/DR, WORM/retenção, suporte e aprovação jurídica; separação de contas reavaliada antes do onboarding |

## Escopo e Limites

- O piloto usa exclusivamente dados sintéticos e adapters mock/sandbox internos. Dados reais mascarados não atendem ao critério de dados sintéticos.
- O fluxo local cobre submissão, enriquecimento mockado, decisão explicável, auditoria oficial, projeções, consulta e webhook.
- UX deve definir as jornadas humanas da demonstração, sem expandir implicitamente para portal completo fora do MVP.
- A conta AWS existente hospeda um ambiente não produtivo; recursos/permissões do CreditOS devem estar segregados dos demais projetos. Organizations e novas contas não são pré-requisitos.
- Uma topologia reduzida de piloto não comprova HA ou SLO produtivo; redução em relação às decisões produtivas exige registro explícito.
- Uso de fornecedores reais e dados pessoais reais depende de homologação e gates específicos antes do uso.

## Infraestrutura e Pendências

- OpenTofu é a ferramenta de IaC desde o piloto; Argo CD permanece responsável por workloads conforme AD-23.
- Estado remoto protegido e versionado, locking e segregação por ambiente/componente são obrigatórios. Bootstrap deve ser reproduzível e documentar migração de eventual estado local temporário; estado/planos sensíveis não são versionados no repositório.
- Apply usa identidade federada, menor privilégio e escopo CreditOS. Aprovação documental não autoriza criar recursos AWS.
- Região, orçamento, backend concreto de estado, versões e parâmetros de infraestrutura permanecem pendentes até a implementação e comparação de custos.
- Testes locais não substituem testes específicos AWS: estes ocorrem após o provisionamento autorizado.
