from __future__ import annotations

import json
from pathlib import Path

import pytest
from creditos_observability import (
    AlertScope,
    AlertSeverity,
    export_incident_routing_placeholders_yaml,
    export_prometheus_alert_rules,
    internal_alert_catalog,
    internal_incident_routing_placeholders,
    validate_alert_catalog,
)
from creditos_observability.alerts import AlertRule, PrometheusRuleGroup

FORBIDDEN_ALERT_TERMS = (
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
    "credential",
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


REQUIRED_ALERTS = {
    "HighErrorRate",
    "HighLatencyP95",
    "HighLatencyP99",
    "ServiceSaturation",
    "HealthReadinessDown",
    "NatsJetStreamBacklogHigh",
    "NatsConsumerLagHigh",
    "DeadLetterQueueGrowing",
    "ReplayOrReprocessStalled",
    "AuditCriticalFailure",
    "CrossTenantAttemptDetected",
    "SensitiveDataLeakPotential",
    "ExternalIntegrationFailureRateHigh",
    "ExternalIntegrationTimeoutHigh",
    "ExternalIntegrationFallbackHigh",
    "DatabaseLatencyHigh",
    "DatabaseErrorRateHigh",
    "DatabaseSaturationHigh",
    "PostDeployErrorRegression",
    "PostDeployLatencyRegression",
}


def test_internal_alert_catalog_covers_required_alerts_and_metadata() -> None:
    catalog = internal_alert_catalog()
    alerts = {rule.alert for group in catalog for rule in group.rules}

    assert REQUIRED_ALERTS.issubset(alerts)
    assert all(group.scope is AlertScope.INTERNAL for group in catalog)
    assert all(group.name.startswith("creditos-internal-") for group in catalog)

    for group in catalog:
        assert group.rules
        for rule in group.rules:
            assert rule.scope is AlertScope.INTERNAL
            assert rule.severity in {
                AlertSeverity.INFO,
                AlertSeverity.WARNING,
                AlertSeverity.CRITICAL,
            }
            assert rule.for_duration
            assert rule.runbook.startswith("runbooks/observability/")
            assert rule.labels["severity"] == rule.severity.value
            assert rule.labels["service"]
            assert rule.labels["environment"] == "{{ $labels.environment }}"
            assert rule.labels["signal_class"]
            assert rule.annotations["runbook"] == rule.runbook
            assert "dashboard" in rule.annotations
            assert "summary" in rule.annotations
            if rule.signal_class == "deploy-slo":
                assert set(rule.labels) >= {"release_ref", "version"}
                assert "release_ref" in rule.expression
                assert "version" in rule.expression


def test_alert_catalog_validates_privacy_cardinality_and_external_runtime_free() -> None:
    catalog = internal_alert_catalog()

    validate_alert_catalog(catalog)

    serialized_catalog = json.dumps(
        [group.to_dict() for group in catalog],
        ensure_ascii=False,
        sort_keys=True,
    ).lower()
    for forbidden in FORBIDDEN_ALERT_TERMS:
        assert forbidden not in serialized_catalog

    for group in catalog:
        for rule in group.rules:
            assert not rule.uses_raw_logs
            assert not rule.uses_raw_traces
            assert rule.scope is AlertScope.INTERNAL
            assert set(rule.labels) >= {"severity", "service", "environment", "signal_class"}
            assert "receiver" not in rule.labels
            assert "webhook" not in serialized_catalog
            assert "password" not in serialized_catalog


def test_alert_validation_rejects_sensitive_or_high_cardinality_queries() -> None:
    for expression in (
        'sum(rate(creditos_requests_total{tenant_id="tenant-a"}[5m]))',
        'sum by (tenant_id) (rate(creditos_requests_total{service=~".+"}[5m]))',
        "label_values(tenant_id)",
        "sum(foo) + on(user_id) sum(bar)",
        "sum(foo) + ignoring(user_id) sum(bar)",
        "sum(foo) + on(service) group_left(user_id) sum(bar)",
        "sum(foo) + ignoring(service) group_right(tenant_id) sum(bar)",
        'label_replace(sum by (service, environment) (foo), "tenant_id", "$1", "service", "(.+)")',
        'label_join(sum by (service, environment) (foo), "user_id", "-", "service", "status")',
        'label_join(foo, "user_id", "-", "service", "status")',
        'count_values("user_id", foo)',
    ):
        unsafe_catalog = (
            PrometheusRuleGroup(
                name="creditos-internal-unsafe",
                scope=AlertScope.INTERNAL,
                interval="30s",
                rules=(
                    AlertRule(
                        alert="UnsafeAlert",
                        expression=expression,
                        for_duration="5m",
                        severity=AlertSeverity.WARNING,
                        service="platform",
                        signal_class="unsafe",
                        runbook="runbooks/observability/unsafe.md",
                        labels={"service": "platform"},
                        annotations={
                            "summary": "Unsafe",
                            "description": "Unsafe alert",
                            "dashboard": "dashboards/internal/platform-overview",
                        },
                    ),
                ),
            ),
        )

        with pytest.raises(ValueError, match="tenant_id|user_id"):
            validate_alert_catalog(unsafe_catalog)


def test_alert_validation_rejects_unsafe_metadata_receivers_and_templates() -> None:
    unsafe_pii = _single_rule_catalog(
        annotations={
            "summary": "Contato alice@example.com",
            "description": "Não permitido",
            "dashboard": "dashboards/internal/platform-overview",
            "runbook": "runbooks/observability/safe-alert.md",
        }
    )
    unsafe_scope = (
        PrometheusRuleGroup(
            name="creditos-internal-unsafe",
            scope=AlertScope.CUSTOMER_FACING,
            interval="30s",
            rules=_single_rule_catalog()[0].rules,
        ),
    )
    unsafe_receiver = _single_rule_catalog(labels={"receiver": "pager"})
    unsafe_raw_logs = _single_rule_catalog(uses_raw_logs=True)
    unsafe_raw_error = _single_rule_catalog(
        annotations={
            "summary": "error_message",
            "description": "exception stacktrace",
            "dashboard": "dashboards/internal/platform-overview",
            "runbook": "runbooks/observability/safe-alert.md",
        }
    )
    unsafe_credential = _single_rule_catalog(
        annotations={
            "summary": "authorization bearer",
            "description": "api_key credential",
            "dashboard": "dashboards/internal/platform-overview",
            "runbook": "runbooks/observability/safe-alert.md",
        }
    )
    unsafe_syntax = _single_rule_catalog(
        expression='sum by (service) (rate(creditos_requests_total{service=~".+"}[5m]) > 1'
    )

    with pytest.raises(ValueError, match="sensível identificável"):
        validate_alert_catalog(unsafe_pii)
    with pytest.raises(ValueError, match="internos"):
        validate_alert_catalog(unsafe_scope)
    with pytest.raises(ValueError, match="receiver"):
        validate_alert_catalog(unsafe_receiver)
    with pytest.raises(ValueError, match="logs crus"):
        validate_alert_catalog(unsafe_raw_logs)
    with pytest.raises(ValueError, match="error_message|exception|stacktrace"):
        validate_alert_catalog(unsafe_raw_error)
    with pytest.raises(ValueError, match="authorization|api_key|credential"):
        validate_alert_catalog(unsafe_credential)
    with pytest.raises(ValueError, match="delimitadores"):
        validate_alert_catalog(unsafe_syntax)


def test_prometheus_alert_export_is_deterministic_internal_and_safe() -> None:
    catalog = internal_alert_catalog()
    exported = export_prometheus_alert_rules(catalog)
    exported_again = export_prometheus_alert_rules(catalog)
    serialized = json.dumps(exported, ensure_ascii=False, sort_keys=True).lower()

    assert exported == exported_again
    assert list(exported) == ["groups"]
    assert len(exported["groups"]) == len(catalog)
    assert exported["groups"][0]["name"] == catalog[0].name
    assert exported["groups"][0]["interval"] == catalog[0].interval
    first_rule = exported["groups"][0]["rules"][0]
    assert set(first_rule) == {"alert", "expr", "for", "keep_firing_for", "labels", "annotations"}
    assert first_rule["labels"]["severity"] in {"info", "warning", "critical"}
    assert "runbook" in first_rule["annotations"]
    for forbidden in FORBIDDEN_ALERT_TERMS:
        assert forbidden not in serialized


def test_versioned_prometheus_alert_files_match_catalog_export() -> None:
    root = Path("ops/observability/prometheus/rules/internal")
    rules_file = root / "technical-alerts.yaml"
    exported = export_prometheus_alert_rules(internal_alert_catalog())

    assert root.is_dir()
    assert rules_file.is_file()
    content = rules_file.read_text(encoding="utf-8")
    assert "webhook" not in content.lower()
    assert "token" not in content.lower()
    assert "secret" not in content.lower()
    assert content == _to_yaml(exported)


def test_incident_routing_placeholders_are_versioned_safe_and_explicit() -> None:
    root = Path("ops/observability/alertmanager/routing")
    routing_file = root / "internal-placeholders.yaml"
    placeholders = internal_incident_routing_placeholders()
    exported = export_incident_routing_placeholders_yaml()

    assert routing_file.is_file()
    assert routing_file.read_text(encoding="utf-8") == exported
    assert placeholders["route_placeholders"]
    assert "configure-with-iac-critical" in exported
    forbidden_terms = (
        "webhook",
        "token",
        "secret",
        "password",
        "api_key",
        "authorization",
        "bearer",
    )
    for forbidden in forbidden_terms:
        assert forbidden not in exported.lower()


def _single_rule_catalog(
    *,
    labels: dict[str, str] | None = None,
    annotations: dict[str, str] | None = None,
    uses_raw_logs: bool = False,
    expression: str | None = None,
) -> tuple[PrometheusRuleGroup, ...]:
    default_labels = {
        "environment": "{{ $labels.environment }}",
        "service": "platform",
        "severity": AlertSeverity.WARNING.value,
        "signal_class": "traffic",
    }
    if labels:
        default_labels.update(labels)
    return (
        PrometheusRuleGroup(
            name="creditos-internal-safe",
            scope=AlertScope.INTERNAL,
            interval="30s",
            rules=(
                AlertRule(
                    alert="SafeAlert",
                    expression=expression
                    or ('sum by (service) (rate(creditos_requests_total{service=~".+"}[5m])) > 1'),
                    for_duration="5m",
                    severity=AlertSeverity.WARNING,
                    service="platform",
                    signal_class="traffic",
                    runbook="runbooks/observability/safe-alert.md",
                    labels=default_labels,
                    annotations=annotations
                    or {
                        "summary": "Safe",
                        "description": "Safe alert",
                        "dashboard": "dashboards/internal/platform-overview",
                    },
                    uses_raw_logs=uses_raw_logs,
                ),
            ),
        ),
    )


def _to_yaml(value: object, *, indent: int = 0) -> str:
    if not isinstance(value, dict):
        raise TypeError("fixture root must be dict")
    return _format_mapping(value, indent=indent)


def _format_mapping(value: dict[str, object], *, indent: int) -> str:
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


def _format_list(value: list[object], *, indent: int) -> str:
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


def _format_scalar(value: object) -> str:
    if not isinstance(value, str):
        return str(value)
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'
