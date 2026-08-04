# Kubernetes e GitOps

Esta pasta reserva o espaço para manifests, charts ou referências GitOps futuras.

Na Story 0.7, nenhuma implantação real é criada. O alvo arquitetural permanece:

- Amazon EKS privado multi-AZ;
- imagens publicadas no Amazon ECR;
- promoção por digest imutável;
- Argo CD como reconciliador GitOps;
- Kyverno para policy enforcement;
- exceções temporárias, auditadas e com expiração.

Produção não deve receber `kubectl apply`, Helm manual ou apply direto do CI.
