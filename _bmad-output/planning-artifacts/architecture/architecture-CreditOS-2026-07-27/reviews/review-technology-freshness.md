# Review — Atualidade Tecnológica

Veredito: aprovado com ressalvas; tecnologias estão majoritariamente atuais e bem escolhidas, mas há lacunas de contrato/segurança que não deveriam ficar implícitas.

## Achados priorizados

1. Severidade alta — CloudEvents usa atributos inválidos (`tenant_id`, `trace_id`, etc.) e omite `specversion`. Recomendação: autofix.
2. Severidade alta — gRPC/OAuth/OIDC deixam service identity/mTLS/sender-constrained tokens muito deferidos para chamadas internas sensíveis. Recomendação: discutir.
3. Severidade média — AsyncAPI, SBOM/SLSA/Cosign são citados sem versões/nível mínimo; SLSA atual é v1.2 e AsyncAPI está em 3.1.0. Recomendação: autofix.
4. Severidade média — S3 Object Lock/WORM não define Governance vs Compliance mode, retenção, legal hold e bypass. Recomendação: discutir.
5. Severidade média — NATS JetStream em EKS 3 nós é fit plausível, mas precisa ADR de HA/DR, réplicas por stream, backup/restore e operação. Recomendação: discutir.

## Resumo

A arquitetura usa escolhas atuais e coerentes para AWS/EKS, RDS/Aurora PostgreSQL, NATS JetStream, OpenTelemetry/Grafana, OAuth/OIDC, gRPC, CloudEvents, AsyncAPI e supply chain. Antes de congelar, corrigir o envelope CloudEvents para conformidade v1.0.2, pinçar versões/níveis mínimos para AsyncAPI/SLSA/SBOM/Cosign, e decidir hardening de identidade interna, WORM e operação NATS.

Fontes: https://github.com/cloudevents/spec, https://github.com/asyncapi/spec, https://www.rfc-editor.org/rfc/rfc9700.html, https://slsa.dev/spec/v1.2/, https://docs.sigstore.dev/cosign/, https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html.
