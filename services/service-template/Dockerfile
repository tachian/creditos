# syntax=docker/dockerfile:1.7
FROM python:3.13.14-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91 AS runtime

ARG SERVICE_VERSION=0.1.0
ARG COMMIT_SHA
ARG BUILD_CREATED

RUN test -n "${COMMIT_SHA}" \
    && test "${COMMIT_SHA}" != "unknown" \
    && test -n "${BUILD_CREATED}" \
    && test "${BUILD_CREATED}" != "unknown"

LABEL org.opencontainers.image.title="creditos-service-template" \
      org.opencontainers.image.description="Imagem de exemplo para microsserviços CreditOS" \
      org.opencontainers.image.version="${SERVICE_VERSION}" \
      org.opencontainers.image.revision="${COMMIT_SHA}" \
      org.opencontainers.image.created="${BUILD_CREATED}" \
      org.opencontainers.image.source="https://github.com/tachian/creditos"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    SERVICE_NAME=creditos-service-template \
    SERVICE_VERSION="${SERVICE_VERSION}" \
    CREDITOS_COMMIT_SHA="${COMMIT_SHA}" \
    CREDITOS_READINESS_FILE=/tmp/creditos-service-template.ready

WORKDIR /app

RUN groupadd --system --gid 10001 creditos \
    && useradd --system --uid 10001 --gid creditos --home-dir /app --shell /usr/sbin/nologin creditos \
    && chown creditos:creditos /app

COPY --chown=creditos:creditos src/ /app/src/

USER 10001:10001

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-m", "creditos_service_template.bootstrap.container_runtime", "healthcheck"]

ENTRYPOINT ["python", "-m", "creditos_service_template.bootstrap.container_runtime"]
CMD ["serve"]
