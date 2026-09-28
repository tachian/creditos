from __future__ import annotations

# ruff: noqa: E501
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from creditos_security.masking import mask_text, sanitize_log_text


class AlertScope(StrEnum):
    INTERNAL = "internal"
    CUSTOMER_FACING = "customer-facing"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class AlertRule:
    alert: str
    expression: str
    for_duration: str
    severity: AlertSeverity
    service: str
    signal_class: str
    runbook: str
    labels: dict[str, str]
    annotations: dict[str, str]
    keep_firing_for: str = "5m"
    scope: AlertScope = AlertScope.INTERNAL
    uses_raw_logs: bool = False
    uses_raw_traces: bool = False

    def to_dict(self) -> dict[str, Any]:
        output = {
            "alert": self.alert,
            "expression": self.expression,
            "for_duration": self.for_duration,
            "keep_firing_for": self.keep_firing_for,
            "severity": self.severity.value,
            "service": self.service,
            "signal_class": self.signal_class,
            "runbook": self.runbook,
            "scope": self.scope.value,
            "labels": dict(sorted(self.labels.items())),
            "annotations": dict(sorted(self.annotations.items())),
        }
        if self.uses_raw_logs:
            output["uses_raw_logs"] = True
        if self.uses_raw_traces:
            output["uses_raw_traces"] = True
        return output


@dataclass(frozen=True, slots=True)
class PrometheusRuleGroup:
    name: str
    scope: AlertScope
    interval: str
    rules: tuple[AlertRule, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope.value,
            "interval": self.interval,
            "rules": tuple(rule.to_dict() for rule in self.rules),
        }


_FORBIDDEN_ALERT_TERMS = (
    "cpf",
    "cnpj",
    "email",
    "payload",
    "prompt",
    "output",
    "raw_log",
    "raw_trace",
    "raw_error",
    "logs_raw",
    "traces_raw",
    "error_message",
    "exception",
    "stacktrace",
    "stack_trace",
    "token",
    "secret",
    "password",
    "senha",
    "credential",
    "credentials",
    "api_key",
    "authorization",
    "bearer",
    "tenant_id",
    "proposal_id",
    "decision_id",
    "correlation_id",
    "request_id",
    "trace_id",
)
_FORBIDDEN_LABELS = frozenset(
    {
        "tenant_id",
        "proposal_id",
        "decision_id",
        "correlation_id",
        "request_id",
        "trace_id",
        "cpf",
        "cnpj",
        "email",
        "payload",
        "prompt",
        "output",
        "raw_error",
        "error_message",
        "exception",
        "stacktrace",
        "stack_trace",
        "token",
        "secret",
        "password",
        "senha",
        "credential",
        "credentials",
        "api_key",
        "authorization",
        "bearer",
        "receiver",
        "webhook",
        "user_id",
    }
)
_ALLOWED_PROMETHEUS_LABELS = frozenset(
    {
        "channel",
        "contract",
        "contract_version",
        "destination",
        "environment",
        "integration_class",
        "operation",
        "operation_type",
        "pool",
        "product_type",
        "release_ref",
        "service",
        "severity",
        "signal_class",
        "source",
        "status",
        "tenant_isolation_tier",
        "version",
    }
)
_ALLOWED_ALERT_LABELS = frozenset(
    {
        "environment",
        "release_ref",
        "service",
        "severity",
        "signal_class",
        "version",
    }
)
_REQUIRED_RULE_LABELS = frozenset({"environment", "service", "severity", "signal_class"})
_REQUIRED_ANNOTATIONS = frozenset({"summary", "description", "dashboard", "runbook"})
_GROUP_NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{1,80}")
_ALERT_NAME_PATTERN = re.compile(r"[A-Z][A-Za-z0-9]{2,80}")
_DURATION_PATTERN = re.compile(r"(?:[1-9][0-9]*)(?:s|m|h|d)")
_LABEL_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:=~|!~|=|!=)")
_GROUPING_PATTERN = re.compile(r"\b(?:by|without)\s*\(([^)]*)\)")
_VECTOR_MATCHING_PATTERN = re.compile(r"\b(?:on|ignoring)\s*\(([^)]*)\)")
_GROUP_SIDE_PATTERN = re.compile(r"\b(?:group_left|group_right)\s*(?:\(([^)]*)\))?")
_LABEL_VALUES_PATTERN = re.compile(r"\blabel_values\s*\(([^)]*)\)")
_LABEL_REPLACE_PATTERN = re.compile(
    r'\blabel_replace\s*\([^,]+,\s*"([^"]+)"\s*,[^,]+,\s*"([^"]+)"',
)
_LABEL_JOIN_PATTERN = re.compile(
    r'\blabel_join\s*\([^,]+,\s*"([^"]+)"\s*,[^,]+,\s*((?:"[^"]+"\s*,?\s*)+\))',
)
_COUNT_VALUES_PATTERN = re.compile(r'\bcount_values\s*\(\s*"([^"]+)"')
_ALLOWED_GROUP_INTERVALS = frozenset({"30s", "1m"})
_ALLOWED_SEVERITIES = frozenset(AlertSeverity)


def internal_alert_catalog() -> tuple[PrometheusRuleGroup, ...]:
    return (
        _group(
            "creditos-internal-platform-slo",
            (
                _rule(
                    alert="HighErrorRate",
                    expression='sum by (service, environment) (rate(creditos_requests_total{environment=~".+",status=~"error|failed"}[5m])) / clamp_min(sum by (service, environment) (rate(creditos_requests_total{environment=~".+"}[5m])), 0.001) > 0.05',
                    for_duration="5m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="error-rate",
                    runbook="runbooks/observability/high-error-rate.md",
                    summary="Taxa de erro elevada por serviço",
                    description="Erro agregado acima do limite operacional em serviço interno.",
                    dashboard="dashboards/internal/platform-overview",
                ),
                _rule(
                    alert="HighLatencyP95",
                    expression='histogram_quantile(0.95, sum by (service, environment, le) (rate(creditos_request_duration_bucket{environment=~".+"}[5m]))) > 750',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="latency",
                    runbook="runbooks/observability/high-latency.md",
                    summary="Latência p95 elevada por serviço",
                    description="Percentil p95 sustentado acima do limite operacional.",
                    dashboard="dashboards/internal/platform-overview",
                ),
                _rule(
                    alert="HighLatencyP99",
                    expression='histogram_quantile(0.99, sum by (service, environment, le) (rate(creditos_request_duration_bucket{environment=~".+"}[5m]))) > 1500',
                    for_duration="10m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="latency",
                    runbook="runbooks/observability/high-latency.md",
                    summary="Latência p99 crítica por serviço",
                    description="Percentil p99 sustentado acima do limite crítico.",
                    dashboard="dashboards/internal/platform-overview",
                ),
                _rule(
                    alert="ServiceSaturation",
                    expression='max by (service, environment, operation) (creditos_service_resource_saturation_ratio{environment=~".+"}) > 0.85',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="saturation",
                    runbook="runbooks/observability/service-saturation.md",
                    summary="Saturação elevada por serviço",
                    description="Uso agregado de recurso técnico acima do limite operacional.",
                    dashboard="dashboards/internal/platform-overview",
                ),
                _rule(
                    alert="HealthReadinessDown",
                    expression='min by (service, environment, operation) (creditos_service_ready{environment=~".+"}) < 1',
                    for_duration="2m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="availability",
                    runbook="runbooks/observability/health-readiness-down.md",
                    summary="Health ou readiness indisponível",
                    description="Serviço reporta condição operacional indisponível.",
                    dashboard="dashboards/internal/platform-overview",
                ),
            ),
        ),
        _group(
            "creditos-internal-messaging-dlq",
            (
                _rule(
                    alert="NatsJetStreamBacklogHigh",
                    expression='sum by (service, environment, source) (creditos_nats_backlog_messages{environment=~".+"}) > 1000',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="messaging",
                    runbook="runbooks/observability/nats-backlog.md",
                    summary="Backlog elevado em mensageria",
                    description="Backlog agregado acima do limite operacional.",
                    dashboard="dashboards/internal/nats-jetstream-dlq",
                ),
                _rule(
                    alert="NatsConsumerLagHigh",
                    expression='max by (service, environment, destination) (creditos_nats_consumer_lag_messages{environment=~".+"}) > 500',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="messaging",
                    runbook="runbooks/observability/nats-consumer-lag.md",
                    summary="Lag elevado em consumer",
                    description="Lag agregado de consumo acima do limite operacional.",
                    dashboard="dashboards/internal/nats-jetstream-dlq",
                ),
                _rule(
                    alert="DeadLetterQueueGrowing",
                    expression='sum by (service, environment, destination) (increase(creditos_dlq_messages_total{environment=~".+"}[15m])) > 0',
                    for_duration="5m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="dlq",
                    runbook="runbooks/observability/dead-letter-queue.md",
                    summary="DLQ crescendo",
                    description="Fila de erro recebeu mensagens no intervalo monitorado.",
                    dashboard="dashboards/internal/nats-jetstream-dlq",
                ),
                _rule(
                    alert="ReplayOrReprocessStalled",
                    expression='max by (service, environment, operation) (creditos_reprocess_oldest_age_seconds{environment=~".+"}) > 1800',
                    for_duration="15m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="reprocess",
                    runbook="runbooks/observability/reprocess-stalled.md",
                    summary="Reprocessamento parado",
                    description="Idade agregada de reprocessamento acima do limite operacional.",
                    dashboard="dashboards/internal/nats-jetstream-dlq",
                ),
            ),
        ),
        _group(
            "creditos-internal-audit-security",
            (
                _rule(
                    alert="AuditCriticalFailure",
                    expression='sum by (service, environment, operation) (increase(creditos_audit_critical_failures_total{environment=~".+"}[5m])) > 0',
                    for_duration="1m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="audit",
                    runbook="runbooks/observability/audit-critical-failure.md",
                    summary="Falha crítica de auditoria",
                    description="Persistência de evidência crítica falhou e exige contenção operacional.",
                    dashboard="dashboards/internal/audit-security",
                ),
                _rule(
                    alert="CrossTenantAttemptDetected",
                    expression='sum by (service, environment, tenant_isolation_tier) (increase(creditos_cross_boundary_attempts_total{environment=~".+"}[5m])) > 0',
                    for_duration="1m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="security",
                    runbook="runbooks/observability/cross-boundary-attempt.md",
                    summary="Tentativa de acesso entre tenants detectada",
                    description="Sinal agregado de isolamento violado ou tentativa bloqueada.",
                    dashboard="dashboards/internal/audit-security",
                ),
                _rule(
                    alert="SensitiveDataLeakPotential",
                    expression='sum by (service, environment, operation) (increase(creditos_privacy_gate_failures_total{environment=~".+"}[5m])) > 0',
                    for_duration="1m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="privacy",
                    runbook="runbooks/observability/sensitive-data-leak-potential.md",
                    summary="Possível exposição de dado sensível",
                    description="Gate de privacidade detectou emissão operacional insegura.",
                    dashboard="dashboards/internal/audit-security",
                ),
            ),
        ),
        _group(
            "creditos-internal-integrations",
            (
                _rule(
                    alert="ExternalIntegrationFailureRateHigh",
                    expression='sum by (service, environment, integration_class, destination) (rate(creditos_integration_requests_total{environment=~".+",status=~"error|failed"}[5m])) / sum by (service, environment, integration_class, destination) (rate(creditos_integration_requests_total{environment=~".+"}[5m])) > 0.10',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="integration",
                    runbook="runbooks/observability/external-integration-failures.md",
                    summary="Falhas elevadas em integração externa",
                    description="Taxa agregada de falha de integração acima do limite operacional.",
                    dashboard="dashboards/internal/external-integrations",
                ),
                _rule(
                    alert="ExternalIntegrationTimeoutHigh",
                    expression='sum by (service, environment, integration_class, destination) (increase(creditos_integration_timeouts_total{environment=~".+"}[10m])) > 5',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="integration",
                    runbook="runbooks/observability/external-integration-timeouts.md",
                    summary="Timeout elevado em integração externa",
                    description="Volume agregado de timeout acima do limite operacional.",
                    dashboard="dashboards/internal/external-integrations",
                ),
                _rule(
                    alert="ExternalIntegrationFallbackHigh",
                    expression='sum by (service, environment, integration_class, destination) (increase(creditos_integration_fallbacks_total{environment=~".+"}[15m])) > 10',
                    for_duration="15m",
                    severity=AlertSeverity.INFO,
                    service="{{ $labels.service }}",
                    signal_class="integration",
                    runbook="runbooks/observability/external-integration-fallbacks.md",
                    summary="Fallback elevado em integração externa",
                    description="Uso agregado de fallback acima do comportamento esperado.",
                    dashboard="dashboards/internal/external-integrations",
                ),
            ),
        ),
        _group(
            "creditos-internal-database",
            (
                _rule(
                    alert="DatabaseLatencyHigh",
                    expression='histogram_quantile(0.95, sum by (service, environment, pool, le) (rate(creditos_database_operation_duration_bucket{environment=~".+"}[5m]))) > 500',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="database",
                    runbook="runbooks/observability/database-latency.md",
                    summary="Latência elevada de banco",
                    description="Percentil p95 de banco acima do limite operacional.",
                    dashboard="dashboards/internal/database-health",
                ),
                _rule(
                    alert="DatabaseErrorRateHigh",
                    expression='sum by (service, environment, pool) (rate(creditos_database_operation_total{environment=~".+",status=~"error|failed"}[5m])) / clamp_min(sum by (service, environment, pool) (rate(creditos_database_operation_total{environment=~".+"}[5m])), 0.001) > 0.05',
                    for_duration="10m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="database",
                    runbook="runbooks/observability/database-errors.md",
                    summary="Erros elevados de banco",
                    description="Falha técnica de banco acima do limite operacional.",
                    dashboard="dashboards/internal/database-health",
                ),
                _rule(
                    alert="DatabaseSaturationHigh",
                    expression='max by (service, environment, pool) (creditos_database_connection_pool_usage_ratio{environment=~".+"}) > 0.85',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="database",
                    runbook="runbooks/observability/database-saturation.md",
                    summary="Saturação elevada de banco",
                    description="Pool lógico de banco acima do limite operacional.",
                    dashboard="dashboards/internal/database-health",
                ),
            ),
        ),
        _group(
            "creditos-internal-deploy-slo-watch",
            (
                _rule(
                    alert="PostDeployErrorRegression",
                    expression='sum by (service, environment, version, release_ref) (rate(creditos_requests_total{environment=~".+",status=~"error|failed",version=~".+",release_ref=~".+"}[10m])) / clamp_min(sum by (service, environment, version, release_ref) (rate(creditos_requests_total{environment=~".+",version=~".+",release_ref=~".+"}[10m])), 0.001) > 0.05',
                    for_duration="10m",
                    severity=AlertSeverity.CRITICAL,
                    service="{{ $labels.service }}",
                    signal_class="deploy-slo",
                    runbook="runbooks/observability/post-deploy-error-regression.md",
                    summary="Regressão de erro pós-deploy",
                    description="Erro agregado após release acima do limite; avaliar rollback ou roll-forward.",
                    dashboard="dashboards/internal/deploy-release-health",
                    extra_labels={
                        "release_ref": "{{ $labels.release_ref }}",
                        "version": "{{ $labels.version }}",
                    },
                ),
                _rule(
                    alert="PostDeployLatencyRegression",
                    expression='histogram_quantile(0.95, sum by (service, environment, version, release_ref, le) (rate(creditos_request_duration_bucket{environment=~".+",version=~".+",release_ref=~".+"}[10m]))) > 1000',
                    for_duration="10m",
                    severity=AlertSeverity.WARNING,
                    service="{{ $labels.service }}",
                    signal_class="deploy-slo",
                    runbook="runbooks/observability/post-deploy-latency-regression.md",
                    summary="Regressão de latência pós-deploy",
                    description="Latência após release acima do limite; avaliar rollback ou roll-forward.",
                    dashboard="dashboards/internal/deploy-release-health",
                    extra_labels={
                        "release_ref": "{{ $labels.release_ref }}",
                        "version": "{{ $labels.version }}",
                    },
                ),
            ),
        ),
    )


def internal_incident_routing_placeholders() -> dict[str, Any]:
    return {
        "route_placeholders": [
            {
                "name": "critical-platform-operations",
                "purpose": "Alertas técnicos internos críticos para operação da plataforma.",
                "matchers": {"severity": "critical"},
                "contact_point_ref": "configure-with-iac-critical",
                "integration_ref": "future-incident-tooling",
                "enabled": "false",
            },
            {
                "name": "warning-platform-operations",
                "purpose": "Alertas técnicos internos de degradação sustentada.",
                "matchers": {"severity": "warning"},
                "contact_point_ref": "configure-with-iac-warning",
                "integration_ref": "future-incident-tooling",
                "enabled": "false",
            },
        ]
    }


def export_incident_routing_placeholders_yaml() -> str:
    placeholders = internal_incident_routing_placeholders()
    _validate_routing_placeholders(placeholders)
    return _to_yaml(placeholders)


def validate_alert_catalog(catalog: tuple[PrometheusRuleGroup, ...]) -> None:
    seen_groups: set[str] = set()
    seen_alerts: set[str] = set()
    for group in catalog:
        _validate_group(group, seen_groups=seen_groups, seen_alerts=seen_alerts)


def export_prometheus_alert_rules(catalog: tuple[PrometheusRuleGroup, ...]) -> dict[str, Any]:
    validate_alert_catalog(catalog)
    return {
        "groups": [
            {
                "name": group.name,
                "interval": group.interval,
                "rules": [
                    {
                        "alert": rule.alert,
                        "expr": rule.expression,
                        "for": rule.for_duration,
                        "keep_firing_for": rule.keep_firing_for,
                        "labels": dict(sorted(rule.labels.items())),
                        "annotations": dict(sorted(rule.annotations.items())),
                    }
                    for rule in group.rules
                ],
            }
            for group in catalog
        ]
    }


def export_prometheus_alert_rules_yaml(catalog: tuple[PrometheusRuleGroup, ...]) -> str:
    return _to_yaml(export_prometheus_alert_rules(catalog))


def _group(name: str, rules: tuple[AlertRule, ...]) -> PrometheusRuleGroup:
    return PrometheusRuleGroup(
        name=name,
        scope=AlertScope.INTERNAL,
        interval="30s",
        rules=rules,
    )


def _rule(
    *,
    alert: str,
    expression: str,
    for_duration: str,
    severity: AlertSeverity,
    service: str,
    signal_class: str,
    runbook: str,
    summary: str,
    description: str,
    dashboard: str,
    extra_labels: dict[str, str] | None = None,
) -> AlertRule:
    labels = {
        "environment": "{{ $labels.environment }}",
        "service": service,
        "severity": severity.value,
        "signal_class": signal_class,
    }
    if extra_labels:
        labels.update(extra_labels)
    return AlertRule(
        alert=alert,
        expression=expression,
        for_duration=for_duration,
        severity=severity,
        service=service,
        signal_class=signal_class,
        runbook=runbook,
        labels=labels,
        annotations={
            "dashboard": dashboard,
            "description": description,
            "runbook": runbook,
            "summary": summary,
        },
    )


def _validate_group(
    group: PrometheusRuleGroup,
    *,
    seen_groups: set[str],
    seen_alerts: set[str],
) -> None:
    _validate_group_name(group.name)
    if group.name in seen_groups:
        raise ValueError(f"grupo de alertas duplicado: {group.name}")
    seen_groups.add(group.name)
    if group.scope is not AlertScope.INTERNAL:
        raise ValueError("alertas desta story devem ser internos")
    if group.interval not in _ALLOWED_GROUP_INTERVALS:
        raise ValueError(f"intervalo de grupo não permitido: {group.interval}")
    if not group.rules:
        raise ValueError(f"grupo sem regras: {group.name}")
    for rule in group.rules:
        _validate_rule(rule, seen_alerts=seen_alerts)


def _validate_rule(rule: AlertRule, *, seen_alerts: set[str]) -> None:
    _validate_alert_name(rule.alert)
    if rule.alert in seen_alerts:
        raise ValueError(f"alerta duplicado: {rule.alert}")
    seen_alerts.add(rule.alert)
    if rule.scope is not AlertScope.INTERNAL:
        raise ValueError("alertas desta story devem ser internos")
    if rule.severity not in _ALLOWED_SEVERITIES:
        raise ValueError(f"severidade não permitida: {rule.severity}")
    _validate_duration(rule.for_duration, field_name="for")
    _validate_duration(rule.keep_firing_for, field_name="keep_firing_for")
    if rule.uses_raw_logs:
        raise ValueError(f"alerta {rule.alert} usa logs crus")
    if rule.uses_raw_traces:
        raise ValueError(f"alerta {rule.alert} usa traces crus")
    _validate_safe_text(rule.service, field_name="service")
    _validate_safe_text(rule.signal_class, field_name="signal_class")
    _validate_safe_text(rule.runbook, field_name="runbook")
    if not rule.runbook.startswith("runbooks/observability/"):
        raise ValueError(f"runbook fora do padrão operacional: {rule.runbook}")
    _validate_safe_query(rule.expression)
    _validate_labels(rule)
    _validate_annotations(rule)


def _validate_labels(rule: AlertRule) -> None:
    labels = dict(rule.labels)
    missing = _REQUIRED_RULE_LABELS - labels.keys()
    if missing:
        raise ValueError(f"alerta {rule.alert} sem labels obrigatórias: {sorted(missing)}")
    if labels["severity"] != rule.severity.value:
        raise ValueError(f"severity label diverge da severidade do alerta: {rule.alert}")
    if labels["service"] != rule.service:
        raise ValueError(f"service label diverge do serviço do alerta: {rule.alert}")
    if labels["signal_class"] != rule.signal_class:
        raise ValueError(f"signal_class label diverge do alerta: {rule.alert}")
    if "release_ref" in labels and rule.signal_class != "deploy-slo":
        raise ValueError(f"release_ref permitido apenas em SLO watch de deploy: {rule.alert}")
    if "version" in labels and rule.signal_class != "deploy-slo":
        raise ValueError(f"version permitido apenas em SLO watch de deploy: {rule.alert}")
    for label, value in labels.items():
        _validate_alert_label(label)
        _validate_safe_text(value, field_name=f"label.{label}")


def _validate_annotations(rule: AlertRule) -> None:
    annotations = dict(rule.annotations)
    missing = _REQUIRED_ANNOTATIONS - annotations.keys()
    if missing:
        raise ValueError(f"alerta {rule.alert} sem annotations obrigatórias: {sorted(missing)}")
    if annotations["runbook"] != rule.runbook:
        raise ValueError(f"runbook annotation diverge do alerta: {rule.alert}")
    for key, value in annotations.items():
        _validate_annotation_key(key)
        _validate_safe_text(value, field_name=f"annotation.{key}")


def _validate_safe_query(query: str) -> None:
    _validate_safe_text(query, field_name="expr")
    _validate_balanced_delimiters(query)
    lower_query = query.lower()
    if any(term in lower_query for term in ("loki", "tempo", "traceql", "logql")):
        raise ValueError("alertas internos não devem consultar logs/traces crus")
    for label in _LABEL_PATTERN.findall(query):
        _validate_prometheus_label(label)
    for labels in _GROUPING_PATTERN.findall(query):
        for label in _split_label_list(labels):
            _validate_prometheus_label(label)
    for labels in _VECTOR_MATCHING_PATTERN.findall(query):
        for label in _split_label_list(labels):
            _validate_prometheus_label(label)
    for labels in _GROUP_SIDE_PATTERN.findall(query):
        for label in _split_label_list(labels):
            _validate_prometheus_label(label)
    for label in _extract_label_values_labels(query):
        _validate_prometheus_label(label)
    for function_name in ("label_replace", "label_join"):
        for call in _extract_function_calls(query, function_name):
            _validate_no_forbidden_label_references(call, function_name=function_name)
    for destination_label, source_label in _LABEL_REPLACE_PATTERN.findall(query):
        _validate_prometheus_label(destination_label)
        _validate_prometheus_label(source_label)
    for destination_label, source_labels in _LABEL_JOIN_PATTERN.findall(query):
        _validate_prometheus_label(destination_label)
        for source_label in _extract_quoted_labels(source_labels):
            _validate_prometheus_label(source_label)
    for label in _COUNT_VALUES_PATTERN.findall(query):
        _validate_prometheus_label(label)


def _validate_prometheus_label(label: str) -> None:
    if label in _FORBIDDEN_LABELS:
        raise ValueError(f"label proibida em query de alerta: {label}")
    if label not in _ALLOWED_PROMETHEUS_LABELS and label != "le":
        raise ValueError(f"label fora da allowlist de alerta: {label}")


def _validate_alert_label(label: str) -> None:
    _validate_prometheus_label(label)
    if label not in _ALLOWED_ALERT_LABELS:
        raise ValueError(f"label de alerta não permitida: {label}")


def _validate_annotation_key(key: str) -> None:
    if key in _FORBIDDEN_LABELS:
        raise ValueError(f"annotation proibida: {key}")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", key):
        raise ValueError(f"annotation inválida: {key}")


def _validate_group_name(value: str) -> None:
    _validate_safe_text(value, field_name="group.name")
    if not _GROUP_NAME_PATTERN.fullmatch(value):
        raise ValueError(f"group.name deve ser identificador técnico estável: {value}")


def _validate_alert_name(value: str) -> None:
    _validate_safe_text(value, field_name="alert")
    if not _ALERT_NAME_PATTERN.fullmatch(value):
        raise ValueError(f"alert deve estar em PascalCase técnico: {value}")


def _validate_duration(value: str, *, field_name: str) -> None:
    if not _DURATION_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} deve ser duração simples: {value}")


def _validate_routing_placeholders(placeholders: dict[str, Any]) -> None:
    routes = placeholders.get("route_placeholders")
    if not isinstance(routes, list) or not routes:
        raise ValueError("placeholders de roteamento ausentes")
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("placeholder de roteamento inválido")
        for key, value in route.items():
            _validate_annotation_key(key)
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    _validate_alert_label(nested_key)
                    _validate_safe_text(str(nested_value), field_name=f"route.{key}.{nested_key}")
            else:
                _validate_safe_text(str(value), field_name=f"route.{key}")


def _validate_balanced_delimiters(query: str) -> None:
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    in_quote = False
    escaped = False
    for character in query:
        if escaped:
            escaped = False
            continue
        if character == "\\" and in_quote:
            escaped = True
            continue
        if character == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if character in pairs:
            stack.append(pairs[character])
            continue
        if character in pairs.values() and (not stack or stack.pop() != character):
            raise ValueError("expr contém delimitadores desbalanceados")
    if stack or in_quote:
        raise ValueError("expr contém delimitadores desbalanceados")


def _extract_function_calls(query: str, function_name: str) -> tuple[str, ...]:
    calls: list[str] = []
    search_from = 0
    prefix = f"{function_name}("
    while True:
        start = query.find(prefix, search_from)
        if start == -1:
            return tuple(calls)
        position = start + len(prefix)
        depth = 1
        in_quote = False
        escaped = False
        while position < len(query):
            character = query[position]
            if escaped:
                escaped = False
            elif character == "\\" and in_quote:
                escaped = True
            elif character == '"':
                in_quote = not in_quote
            elif not in_quote and character == "(":
                depth += 1
            elif not in_quote and character == ")":
                depth -= 1
                if depth == 0:
                    calls.append(query[start : position + 1])
                    break
            position += 1
        search_from = position + 1


def _validate_no_forbidden_label_references(call: str, *, function_name: str) -> None:
    for forbidden_label in sorted(_FORBIDDEN_LABELS):
        if re.search(rf"\b{re.escape(forbidden_label)}\b", call):
            raise ValueError(f"{function_name} referencia label proibida: {forbidden_label}")


def _split_label_list(labels: str) -> tuple[str, ...]:
    return tuple(label.strip() for label in labels.split(",") if label.strip())


def _extract_label_values_labels(query: str) -> tuple[str, ...]:
    extracted: list[str] = []
    for arguments in _LABEL_VALUES_PATTERN.findall(query):
        parts = [part.strip() for part in arguments.split(",")]
        label = parts[-1] if parts else ""
        if not label:
            continue
        if label.startswith('"') and label.endswith('"'):
            label = label[1:-1]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label):
            extracted.append(label)
    return tuple(extracted)


def _extract_quoted_labels(value: str) -> tuple[str, ...]:
    return tuple(
        label
        for label in re.findall(r'"([^"]+)"', value)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label)
    )


def _validate_safe_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} deve ser string")
    sanitized = sanitize_log_text(value)
    if sanitized != value or not value:
        raise ValueError(f"{field_name} contém texto inseguro")
    masked = mask_text(value)
    if masked != value:
        raise ValueError(f"{field_name} contém dado sensível identificável")
    lower_value = value.lower()
    for forbidden in _FORBIDDEN_ALERT_TERMS:
        if forbidden in lower_value:
            raise ValueError(f"{field_name} contém termo proibido: {forbidden}")


def _to_yaml(value: dict[str, Any]) -> str:
    return _format_mapping(value, indent=0)


def _format_mapping(value: dict[str, Any], *, indent: int) -> str:
    lines: list[str] = []
    for key, item in value.items():
        prefix = " " * indent
        if isinstance(item, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_mapping(item, indent=indent + 2).rstrip("\n"))
        elif isinstance(item, list):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_list(item, indent=indent + 2).rstrip("\n"))
        else:
            lines.append(f"{prefix}{key}: {_format_scalar(item)}")
    return "\n".join(lines) + "\n"


def _format_list(value: list[Any], *, indent: int) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for item in value:
        if isinstance(item, dict):
            first = True
            for key, nested in item.items():
                marker = "- " if first else "  "
                if isinstance(nested, dict):
                    lines.append(f"{prefix}{marker}{key}:")
                    lines.append(_format_mapping(nested, indent=indent + 4).rstrip("\n"))
                elif isinstance(nested, list):
                    lines.append(f"{prefix}{marker}{key}:")
                    lines.append(_format_list(nested, indent=indent + 4).rstrip("\n"))
                else:
                    lines.append(f"{prefix}{marker}{key}: {_format_scalar(nested)}")
                first = False
        else:
            lines.append(f"{prefix}- {_format_scalar(item)}")
    return "\n".join(lines) + "\n"


def _format_scalar(value: Any) -> str:
    if not isinstance(value, str):
        return str(value)
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'
