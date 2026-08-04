# Padrão Inicial de Containers e Supply Chain

Este documento materializa a trilha inicial da Story 0.7. Ele não substitui os
ADRs de produção, mas torna verificáveis os requisitos de container, registry,
SBOM, proveniência, assinatura, attestations e SLSA antes do início das histórias
funcionais.

## Container de Serviço

- Cada serviço implantável deve possuir sua própria imagem OCI.
- A imagem deve rodar como usuário não root.
- A imagem deve evitar `latest` para promoção e deve ser promovida por digest.
- A imagem base do template deve ser fixada por digest.
- O build deve receber `COMMIT_SHA`, `SERVICE_VERSION` e data de criação como
  metadados rastreáveis; builds com `COMMIT_SHA` ou data `unknown` devem falhar.
- O serviço deve expor health/readiness compatíveis com Kubernetes.
- O serviço deve responder a `SIGTERM` com shutdown gracioso, removendo readiness
  antes de encerrar e aguardando uma janela curta de drain.
- O template atual usa probe por `exec`; serviços reais podem expor `/health` e
  `/ready`, desde que preservem a separação entre liveness e readiness.
- O template atual não declara porta porque não há processo HTTP escutando; portas
  devem ser declaradas apenas quando houver listener real.

## Fluxo Alvo de Supply Chain

1. Pull request roda CI inicial sem permissões de escrita amplas.
2. Build de release gera imagem imutável por digest e registra o digest em
   artefato JSON com `scripts/container_release_metadata.py`.
3. A imagem é publicada no Amazon ECR.
4. O pipeline gera SBOM em SPDX ou CycloneDX.
5. O pipeline gera proveniência e attestation do build.
6. A imagem é assinada com Sigstore/Cosign keyless por identidade OIDC.
7. GitHub Artifact Attestations é usado enquanto `tachian/creditos` permanecer
   público.
8. Se o repositório migrar para privado/interno, a disponibilidade do recurso deve
   ser validada no plano GitHub antes de manter o mesmo workflow. Sem suporte, o
   fallback temporário é Cosign/in-toto, preservando o alvo arquitetural.
9. Promoção para ambiente ocorre por digest já assinado/verificado, nunca por
   rebuild no deploy.
10. Argo CD reconcilia manifests/charts; produção não recebe `kubectl apply`,
    Helm manual ou apply direto do CI.

## Permissões de Workflow

- Workflows de pull request não devem usar `id-token: write`,
  `attestations: write`, `packages: write` ou permissões AWS.
- Workflows protegidos de release podem usar `id-token: write` e
  `attestations: write` quando estiverem gerando assinatura/proveniência.
- Credenciais AWS long-lived são proibidas; acesso AWS deve usar OIDC/identidade
  federada quando a conta AWS existir.

## SLSA

O alvo inicial do CreditOS é SLSA Build L2. A evolução para Build L3 deve ocorrer
somente após estabilização da esteira, usando reusable workflows, hardening de
runners/builders e verificação explícita de proveniência.

## Decisões Pendentes

- Conta/região AWS alvo e layout de ECR por ambiente.
- Ferramenta final de geração de SBOM.
- Scanner de imagem e política de severidade.
- Formato final de charts/manifests para Argo CD.
- Política Kyverno inicial em modo `audit` vs `enforce` por ambiente.
- ADR de fallback caso o repositório migre para privado/interno sem suporte a
  GitHub Artifact Attestations.
