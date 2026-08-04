---
baseline_commit: 2932179cbacd92b6ed8aaa9c96f2884ab42ade3b
jira_issue: CTOS-22
branch: agent/story-0-7-supply-chain-containers-iac
---

# Story 0.7: Trilha Inicial de Supply Chain, Containers e IaC

Status: done

## Story

Como equipe de plataforma,
quero registrar e iniciar a trilha técnica de containers, supply chain e IaC,
para que requisitos de produção não fiquem esquecidos após o desenvolvimento funcional começar.

## Acceptance Criteria

1. **Given** a base de build dos serviços, **when** uma imagem de exemplo é criada, **then** ela segue padrão de usuário não root, health/readiness, shutdown gracioso e tag/digest rastreável, **and** há plano documentado para ECR, SBOM, proveniência, assinatura, GitHub Artifact Attestations e SLSA Build L2.
2. **Given** a pasta `infra/`, **when** o backlog técnico é revisado, **then** existem tarefas rastreáveis para IaC de ambientes, rede, EKS, bancos, NATS JetStream, observabilidade, storage imutável, KMS/secrets, políticas e automação de isolamento por tenant, **and** fica explícito que IaC completo de produção permanece como workstream posterior/pré-produção, sem bloquear as histórias de produto após a fundação mínima.

## Tasks / Subtasks

- [x] CTOS-102 — Definir base inicial de containers (AC: 1)
  - [x] Criar uma imagem de exemplo para serviço implantável sem acoplar domínio real prematuramente.
  - [x] Garantir usuário não root, `WORKDIR` absoluto, porta explícita quando aplicável e ausência de `sudo`.
  - [x] Implementar health/readiness compatíveis com Kubernetes e documentar como o probe deve ser exposto pelo serviço.
  - [x] Garantir shutdown gracioso por tratamento de sinal/tempo limite, sem depender de finalização abrupta.
  - [x] Produzir tag rastreável por commit e registrar digest da imagem como artefato de build.
- [x] CTOS-103 — Registrar plano de supply chain de imagens (AC: 1)
  - [x] Documentar fluxo alvo de build de imagem no GitHub Actions com permissões mínimas e OIDC quando necessário.
  - [x] Registrar plano para publicação no Amazon ECR por digest imutável.
  - [x] Registrar geração e retenção de SBOM em formato SPDX ou CycloneDX.
  - [x] Registrar proveniência/attestation do build e verificação antes de promoção.
  - [x] Registrar assinatura keyless com Sigstore/Cosign e validação por identidade esperada.
  - [x] Registrar GitHub Artifact Attestations como alvo aplicável enquanto `tachian/creditos` permanecer público; se o repositório migrar para privado/interno, validar plano GitHub antes da implementação ou documentar fallback temporário por Cosign/in-toto.
  - [x] Manter SLSA Build L2 como alvo inicial e registrar caminho evolutivo para Build L3 sem tornar esta story dependente disso.
- [x] CTOS-104 — Registrar backlog rastreável de IaC (AC: 2)
  - [x] Criar ou atualizar backlog/documentação para ambientes `dev`, `sandbox`, `staging` e `prod`.
  - [x] Registrar tarefas futuras para rede privada, subnets multi-AZ, security groups, network policies e egress controlado.
  - [x] Registrar tarefas futuras para EKS, workloads privados, service accounts e EKS Pod Identity.
  - [x] Registrar tarefas futuras para RDS/Aurora PostgreSQL por serviço, criptografia KMS, backup e restore testado.
  - [x] Registrar tarefas futuras para NATS JetStream no EKS com persistência, HA, backup/restore e runbooks.
  - [x] Registrar tarefas futuras para observabilidade técnica/negócio, S3 Object Lock, KMS, Secrets Manager e políticas de admissão.
  - [x] Registrar automação futura de isolamento por tenant `bridge` e evolução controlada para `silo`.
- [x] CTOS-105 — Documentar limites da fundação mínima (AC: 1, 2)
  - [x] Explicitar que esta story cria trilha inicial e artefatos verificáveis, não IaC completo de produção.
  - [x] Explicitar que GitOps, Argo CD, Kyverno, ECR final, contas AWS e sizing detalhado continuam como workstream posterior/pré-produção.
  - [x] Explicitar que a implementação não deve bloquear histórias de produto após a fundação mínima estar verificável.
  - [x] Registrar decisões pendentes que exigem ADR, conta cloud real ou validação operacional.
- [x] CTOS-106 — Adicionar testes estruturais e validações da trilha (AC: 1, 2)
  - [x] Adicionar testes que verifiquem existência e guardrails mínimos da imagem de exemplo.
  - [x] Adicionar testes que verifiquem documentação/backlog de ECR, SBOM, proveniência, assinatura, Artifact Attestations e SLSA.
  - [x] Adicionar testes que verifiquem documentação/backlog de IaC para ambientes, rede, EKS, bancos, NATS, observabilidade, storage imutável, KMS/secrets, políticas e tenant isolation.
  - [x] Evitar testes frágeis por texto solto quando metadados estruturados forem mais adequados.
- [x] CTOS-107 — Validar gates e sincronizar BMAD/Jira (AC: 1, 2)
  - [x] Executar validação focada dos testes criados para esta story.
  - [x] Executar `./scripts/dev all` ao final da implementação.
  - [x] Atualizar `sprint-status.yaml` conforme a evolução da story.
  - [x] Manter `CTOS-22` e subtasks sincronizados no Jira durante desenvolvimento, revisão e conclusão.

### Review Findings

- [x] [Review][Patch] Separar liveness de readiness para probes Kubernetes [services/service-template/src/creditos_service_template/bootstrap/container_runtime.py:38]
- [x] [Review][Patch] Produzir ou registrar digest da imagem como artefato verificável [services/service-template/README.md:42]
- [x] [Review][Patch] Fixar imagem base por digest para reduzir mutabilidade da supply chain [services/service-template/Dockerfile:2]
- [x] [Review][Patch] Falhar build quando metadados rastreáveis permanecerem `unknown` [services/service-template/Dockerfile:5]
- [x] [Review][Patch] Adicionar janela de drain antes do encerramento após `SIGTERM` [services/service-template/src/creditos_service_template/bootstrap/container_runtime.py:48]
- [x] [Review][Patch] Tratar falhas de escrita/remoção do arquivo de readiness [services/service-template/src/creditos_service_template/bootstrap/container_runtime.py:21]
- [x] [Review][Patch] Remover ou justificar `EXPOSE 8080` sem processo escutando porta [services/service-template/Dockerfile:33]
- [x] [Review][Patch] Fortalecer testes do Dockerfile para validar instruções efetivas [tests/test_supply_chain_containers_iac.py:29]
- [x] [Review][Patch] Validar consistência mínima entre TOML e Markdown de supply chain [tests/test_supply_chain_containers_iac.py:89]

## Dev Notes

### Escopo da Story

- Esta story inicia a trilha operacional de containers, supply chain e IaC sem implementar a infraestrutura completa de produção.
- O resultado esperado é uma fundação verificável: imagem de exemplo com guardrails mínimos, documentação operacional de supply chain e backlog rastreável para IaC.
- A story deve reduzir risco de esquecimento dos requisitos de AD-12, AD-13 e AD-23 antes das histórias funcionais.
- Não criar novo microsserviço de domínio nesta story; usar `services/service-template` ou artefato equivalente como base quando fizer sentido.
- Não criar recursos reais na AWS, não exigir credenciais cloud e não fazer deploy em cluster real nesta story.

### Requisitos Técnicos Obrigatórios

- Containers devem rodar como usuário não root por padrão.
- Containers devem expor mecanismo verificável de health/readiness compatível com Kubernetes.
- Containers devem suportar shutdown gracioso em resposta a sinais de parada.
- Imagens devem ter tag rastreável por commit e referência por digest para promoção.
- O plano de supply chain deve cobrir Amazon ECR, SBOM, proveniência, assinatura, GitHub Artifact Attestations, verificação e SLSA Build L2.
- IaC completo de produção deve permanecer como workstream posterior/pré-produção, mas com backlog rastreável desde agora.
- Qualquer novo fornecedor, action ou ferramenta não prevista em AD-23 precisa de justificativa, alternativa e consequência.

### Arquitetura e Guardrails

- Seguir AD-12: AWS/EKS como infraestrutura de referência do MVP de produção, workloads em subnets privadas, RDS/Aurora PostgreSQL, NATS JetStream no EKS, S3 Object Lock, KMS/Secrets Manager e IaC obrigatório para produção.
- Seguir AD-13: mudanças via PR, deploy por artefato imutável, promoção controlada, GitOps/pipeline protegido, sem rebuild no deploy e sem credenciais long-lived.
- Seguir AD-23: GitHub Actions, Amazon ECR, Sigstore/Cosign, GitHub Artifact Attestations, Argo CD, Kyverno e SLSA Build L2 inicial.
- Seguir Story 0.6: CI inicial já existe; esta story não deve enfraquecer `pull_request`, permissões mínimas, secret scan ou `./scripts/dev all`.
- Produção não deve receber `kubectl apply`, Helm manual ou apply direto do CI.
- Exceções de policy devem ser temporárias, auditadas, com owner, justificativa, escopo e expiração.

### Decisões Técnicas Recomendadas

- **Monorepo com imagem por serviço vs imagem única:** manter uma imagem por serviço implantável porque AD-16/AD-23 e os épicos planejam microsserviços com deploy independente. Imagem única simplificaria o início, mas criaria acoplamento operacional e dificultaria promoção por digest.
- **Dockerfile no template vs Dockerfile raiz:** preferir Dockerfile no serviço/template para preservar autonomia por serviço. Dockerfile raiz reduz duplicação inicial, mas tende a misturar ciclos de release de serviços diferentes.
- **GitHub Artifact Attestations vs somente Cosign:** manter ambos no plano porque AD-23 exige Artifact Attestations e Cosign. Como `tachian/creditos` está público nesta fase, GitHub Artifact Attestations é aplicável agora; se o repositório migrar para privado/interno, validar disponibilidade no plano GitHub antes de manter o mesmo workflow ou usar Cosign/in-toto como fallback temporário documentado, sem remover o alvo arquitetural.
- **Cosign keyless vs chave estática:** preferir Cosign keyless por OIDC para evitar secrets long-lived. Chave em KMS pode ser fallback futuro via ADR se exigido por política corporativa.
- **SBOM SPDX vs CycloneDX:** aceitar SPDX ou CycloneDX inicialmente, pois ambos são suportados no ecossistema de attestations; a decisão final deve considerar integração com scanner, auditoria e requisitos de cliente.
- **ECR signing gerenciado vs Sigstore/Cosign:** ECR suporta assinatura por AWS Signer/Notation, mas AD-23 já adotou Sigstore/Cosign. Registrar ECR signing gerenciado como alternativa futura, não como substituição automática nesta story.
- **IaC mínimo agora vs IaC completo:** criar backlog e estrutura mínima agora; IaC completo de produção depende de contas AWS, estratégia de ambientes, sizing, custos e ADRs específicas.

### Pesquisa Técnica Atual

- Docker recomenda usar `USER` para executar serviços sem privilégio quando possível, evitar `sudo` e usar `WORKDIR` absoluto para clareza e confiabilidade.
- A referência de Dockerfile define `HEALTHCHECK`, `STOPSIGNAL` e `USER`; healthcheck tem apenas uma instrução efetiva por Dockerfile e deve retornar status de sucesso/falha de forma objetiva.
- GitHub Artifact Attestations gera claims assinadas sobre proveniência, workflow, repositório, ambiente, commit SHA e evento; também pode associar SBOM.
- GitHub informa que Artifact Attestations precisam ser verificadas para gerar benefício real. Para o estado atual do projeto, o recurso é aplicável porque `tachian/creditos` está público; a limitação relevante aparece se o repositório migrar para privado/interno sem plano GitHub compatível.
- O `actions/attest` exige permissões como `id-token: write`, `contents: read` e `attestations: write`; container images também podem exigir permissão de publicação no registry.
- A especificação SLSA v1.2 define níveis progressivos para supply chain; o alvo arquitetural CreditOS é Build L2 inicial, com evolução posterior para L3.
- Cosign recomenda assinar imagens por digest, não por tag, para evitar assinar conteúdo diferente do esperado.
- AWS ECR documenta assinatura de imagens com AWS Signer/Notation como opção gerenciada, mas isso é uma alternativa/complemento a ser avaliado em ADR caso conflite com AD-23.

### Anti-Patterns a Evitar

- Rodar container como root sem justificativa explícita.
- Usar tag `latest` como referência de deploy ou assinatura.
- Assinar imagem por tag em vez de digest.
- Gerar SBOM/proveniência sem etapa de verificação antes de promoção.
- Adicionar `id-token: write`, `packages: write` ou permissões de escrita em workflow de PR sem necessidade nesta story.
- Criar credenciais AWS long-lived no CI.
- Implementar IaC completo de produção sem contas, ambientes, estado remoto, política de drift e ADRs necessárias.
- Confundir `infra/local/` com topologia final de produção.
- Bloquear histórias funcionais por ausência de EKS/ECR/Argo CD reais após a fundação mínima desta story.

## References

- `_bmad-output/planning-artifacts/epics.md` — Epic 0 e Story 0.7.
- `_bmad-output/planning-artifacts/architecture/architecture-CreditOS-2026-07-27/ARCHITECTURE-SPINE.md` — AD-12, AD-13, AD-16, AD-23 e Structural Seed.
- `_bmad-output/implementation-artifacts/0-6-ci-inicial-e-gates-de-qualidade.md` — CI inicial, limites de Story 0.6 e handoff para Story 0.7.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — rastreamento BMAD.
- Docker build best practices: https://docs.docker.com/build/building/best-practices/
- Dockerfile reference: https://docs.docker.com/reference/dockerfile/
- GitHub Artifact Attestations: https://docs.github.com/en/actions/concepts/security/artifact-attestations
- GitHub Artifact Attestations how-to: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- SLSA specification v1.2: https://slsa.dev/spec/v1.2/
- Sigstore/Cosign signing: https://github.com/sigstore/cosign/blob/main/doc/cosign_sign.md
- Amazon ECR image signing: https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-signing.html
- Amazon EKS Pod Identity: https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html

## Dev Agent Record

### Agent Model Used

Codex CLI

### Debug Log References

- Story iniciada com branch `agent/story-0-7-supply-chain-containers-iac`.
- Jira `CTOS-22` movido para WIP no início, conforme acordo operacional do projeto.
- RED: `.venv/bin/python -m pytest tests/test_supply_chain_containers_iac.py` falhou com 4 testes antes dos artefatos de container, supply chain e IaC existirem.
- GREEN: `.venv/bin/python -m pytest tests/test_supply_chain_containers_iac.py` passou com 4 testes após implementação.
- Validação focada: `.venv/bin/ruff check tests/test_supply_chain_containers_iac.py services/service-template/src/creditos_service_template/bootstrap/container_runtime.py` passou.
- Validação focada: `.venv/bin/ruff format --check tests/test_supply_chain_containers_iac.py services/service-template/src/creditos_service_template/bootstrap/container_runtime.py` passou.
- Validação focada: `.venv/bin/pyright` passou com 0 erros.
- Validação final: `env UV_CACHE_DIR=/tmp/creditos-uv-cache PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` passou fora do sandbox por o harness local exigir socket local.
- Revisão adversarial: Blind Hunter, Edge Case Hunter e Acceptance Auditor executados; 9 findings de patch aplicados.
- Validação pós-review focada: `.venv/bin/python -m pytest tests/test_supply_chain_containers_iac.py` passou com 7 testes.
- Validação pós-review focada: `.venv/bin/ruff check tests/test_supply_chain_containers_iac.py scripts/container_release_metadata.py services/service-template/src/creditos_service_template/bootstrap/container_runtime.py` passou.
- Validação pós-review focada: `.venv/bin/ruff format --check tests/test_supply_chain_containers_iac.py scripts/container_release_metadata.py services/service-template/src/creditos_service_template/bootstrap/container_runtime.py` passou.
- Validação pós-review focada: `.venv/bin/pyright` passou com 0 erros.
- Validação final pós-review: `env UV_CACHE_DIR=/tmp/creditos-uv-cache PATH=/tmp/creditos-tools/local/bin:$PATH ./scripts/dev all` passou fora do sandbox com 53 testes.

### Completion Notes List

- Criado Dockerfile de exemplo no template de serviço com usuário não root, metadados OCI, `HEALTHCHECK`, `STOPSIGNAL SIGTERM`, porta explícita e build args rastreáveis.
- Criado runtime mínimo de container para health/readiness por `exec` e shutdown gracioso sem acoplamento de domínio.
- Documentado padrão inicial de containers e supply chain com Amazon ECR, SBOM SPDX/CycloneDX, proveniência, Sigstore/Cosign keyless, GitHub Artifact Attestations e SLSA Build L2.
- Registrada nuance de GitHub Artifact Attestations: aplicável enquanto `tachian/creditos` permanecer público; fallback temporário Cosign/in-toto só se migrar para privado/interno sem plano compatível.
- Criado backlog IaC estruturado para ambientes, rede, EKS, bancos, NATS JetStream, observabilidade, storage imutável, KMS/secrets, políticas e tenant isolation `bridge` → `silo`.
- Adicionados testes estruturais para evitar que a trilha de containers, supply chain e IaC fique apenas documental.
- Validação final inicial executada com 50 testes passando.
- Patches de code review aplicados: liveness/readiness separados, digest artifact script criado, base image pinada por digest, build args rastreáveis obrigatórios, drain configurável, readiness file robusto, `EXPOSE` removido do template mínimo e testes fortalecidos.
- Validação final pós-review executada com 53 testes passando.

### File List

- `docs/standards/container-supply-chain.md`
- `docs/standards/container-supply-chain.toml`
- `infra/iac/README.md`
- `infra/iac/backlog.toml`
- `infra/kubernetes/README.md`
- `services/service-template/.dockerignore`
- `services/service-template/Dockerfile`
- `services/service-template/README.md`
- `services/service-template/src/creditos_service_template/bootstrap/container_runtime.py`
- `scripts/container_release_metadata.py`
- `tests/test_supply_chain_containers_iac.py`
- `_bmad-output/implementation-artifacts/0-7-trilha-inicial-de-supply-chain-containers-e-iac.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

### Change Log

- 2026-08-04 — Story 0.7 iniciada, branch criada e card Jira movido para WIP.
- 2026-08-04 — Implementada trilha inicial de containers, supply chain e backlog IaC, com testes estruturais e validação completa.
- 2026-08-04 — Aplicados 9 patches de code review e Story 0.7 marcada como done.
