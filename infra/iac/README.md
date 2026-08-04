# Backlog Inicial de IaC

A pasta `infra/iac/` registra a trilha rastreável de infraestrutura como código
do CreditOS. Nesta Story 0.7, ela **não** cria infraestrutura real de produção.

O arquivo `backlog.toml` lista os workstreams mínimos que precisam existir antes
da entrada em produção com cliente real:

- ambientes;
- rede;
- EKS;
- bancos;
- NATS JetStream;
- observabilidade;
- storage imutável;
- KMS/secrets;
- políticas;
- automação de isolamento por tenant.

IaC completo de produção permanece como workstream posterior/pré-produção. Após
a fundação mínima estar verificável, a ausência de cluster real não deve bloquear
as histórias funcionais do MVP.
