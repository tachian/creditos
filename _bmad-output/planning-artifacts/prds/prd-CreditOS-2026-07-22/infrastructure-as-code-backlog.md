# Infrastructure as Code - backlog final

## Decisão registrada

Toda infraestrutura de produção do CreditOS deve ser provisionada e modificada por Infrastructure as Code.

O desenvolvimento dos módulos IaC não entra como funcionalidade de produto do MVP, mas deve ser incluído no backlog final do projeto e concluído antes da preparação de produção.

## Escopo mínimo

IaC deve cobrir:

- Rede, VPC/VNet, subnets privadas, rotas, NAT, endpoints privados e regras de firewall.
- Kubernetes gerenciado ou cluster equivalente.
- Bancos PostgreSQL, schemas/databases por serviço, usuários e políticas de backup.
- NATS JetStream ou broker definido pela Architecture.
- Observabilidade: OpenTelemetry Collector, Prometheus, Grafana, Loki, Tempo e Alertmanager ou serviços managed equivalentes.
- Storage imutável/WORM para auditoria.
- KMS, secrets, certificados e rotação.
- IAM/RBAC, service accounts e políticas de menor privilégio.
- Registries de imagem e políticas de supply chain.
- Ambientes separados: desenvolvimento, staging, produção e sandbox quando aplicável.
- Automação de isolamento por tenant e evolução de `bridge` para `silo`.

## Requisitos de qualidade

- Todo plano de mudança deve passar por revisão em pull request.
- Estado remoto deve ser protegido, versionado, criptografado e com controle de acesso.
- Secrets não podem ser versionados no repositório.
- Mudanças devem ter validação, lint, security scan e plano aplicável antes do deploy.
- Drift detection deve ser previsto para detectar divergência entre código e ambiente real.
- Módulos devem ser reutilizáveis e parametrizados por ambiente, tenant e tier de isolamento.
- Runbooks operacionais devem explicar provisionamento, rollback, restore e rotação de secrets/chaves.

## Ferramentas candidatas

A ferramenta será definida pela Architecture. Opções a avaliar:

- Terraform ou OpenTofu para infraestrutura cloud.
- Helm/Kustomize para componentes Kubernetes.
- GitOps com Argo CD ou Flux para workloads e configuração de cluster.
- Terragrunt ou alternativa equivalente se a composição multiambiente exigir mais governança.

## Consequências para Architecture

- Definir cloud alvo e modelo de contas/projetos/subscriptions.
- Definir estrutura de módulos IaC.
- Definir backend de estado remoto.
- Definir estratégia de GitOps ou pipeline CI/CD para infraestrutura.
- Definir política de promoção entre ambientes.
- Definir como tenants com isolamento `silo` serão provisionados.

## ADRs necessários

- Ferramenta principal de IaC.
- Estratégia de estado remoto.
- GitOps vs pipeline imperativo.
- Modelo de contas/projetos/subscriptions por ambiente e tenant.
- Automação de evolução multi-tenancy `bridge` para `silo`.
