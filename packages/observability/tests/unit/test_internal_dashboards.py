from __future__ import annotations

import json
from pathlib import Path

import pytest
from creditos_observability import (
    DashboardScope,
    export_grafana_dashboard,
    internal_dashboard_catalog,
    validate_dashboard_catalog,
)
from creditos_observability.dashboards import (
    DashboardDefinition,
    DashboardPanel,
    DashboardVariable,
)

FORBIDDEN_DASHBOARD_TERMS = (
    "cpf",
    "cnpj",
    "email",
    "payload",
    "raw_log",
    "raw_trace",
    "logs_raw",
    "traces_raw",
    "token",
    "secret",
    "tenant_id",
    "proposal_id",
    "decision_id",
    "correlation_id",
    "request_id",
    "trace_id",
)


def test_internal_dashboard_catalog_covers_required_technical_views() -> None:
    catalog = internal_dashboard_catalog()
    dashboards = {dashboard.slug: dashboard for dashboard in catalog}

    assert set(dashboards) == {
        "platform-overview",
        "public-api",
        "internal-grpc",
        "nats-jetstream-dlq",
        "external-integrations",
        "audit-security",
        "deploy-release-health",
    }
    assert all(dashboard.scope is DashboardScope.INTERNAL for dashboard in dashboards.values())
    assert all("internal" in dashboard.tags for dashboard in dashboards.values())
    assert all(dashboard.uid.startswith("ctos-internal-") for dashboard in dashboards.values())

    platform_panel_titles = {panel.title for panel in dashboards["platform-overview"].panels}
    public_api_panel_titles = {panel.title for panel in dashboards["public-api"].panels}
    integration_variables = {
        variable.name for variable in dashboards["external-integrations"].variables
    }
    audit_variables = {variable.name for variable in dashboards["audit-security"].variables}
    deploy_panel_titles = {panel.title for panel in dashboards["deploy-release-health"].panels}
    nats_panel_titles = {panel.title for panel in dashboards["nats-jetstream-dlq"].panels}

    assert {
        "Taxa de erro por serviço",
        "Latência p95/p99 por serviço",
        "Throughput por serviço",
        "CPU por serviço",
        "Memória por serviço",
        "Saturação por serviço",
        "Health e readiness",
        "Versão e deploy atual",
    }.issubset(platform_panel_titles)
    assert "Latência p50/p95/p99 por operação" in public_api_panel_titles
    assert "service" in integration_variables
    assert "tenant_isolation_tier" in audit_variables
    assert "Commit/digest publicado" in deploy_panel_titles
    assert {
        "Backlog por stream",
        "Lag por consumer",
        "Retries e DLQ",
        "Idade de mensagens",
        "Replay e reprocessamento",
    }.issubset(nats_panel_titles)


def test_dashboard_catalog_validates_privacy_cardinality_and_external_runtime_free() -> None:
    catalog = internal_dashboard_catalog()

    validate_dashboard_catalog(catalog)

    serialized_catalog = json.dumps(
        [dashboard.to_dict() for dashboard in catalog],
        ensure_ascii=False,
        sort_keys=True,
    ).lower()
    for forbidden in FORBIDDEN_DASHBOARD_TERMS:
        assert forbidden not in serialized_catalog

    for dashboard in catalog:
        assert dashboard.data_sources <= {"prometheus"}
        for variable in dashboard.variables:
            assert variable.kind in {"query", "custom"}
            assert variable.name not in {"tenant_id", "correlation_id", "request_id"}
            assert not variable.free_text
        for panel in dashboard.panels:
            assert panel.query
            assert panel.data_source == "prometheus"
            assert not panel.uses_raw_logs
            assert not panel.uses_raw_traces
            assert panel.visualization in {"timeseries", "stat", "table"}
            assert isinstance(panel.legend_format, str)
            if panel.placeholder:
                assert panel.placeholder_reason


def test_dashboard_validation_rejects_sensitive_or_high_cardinality_queries() -> None:
    for query in (
        'sum(rate(creditos_requests_total{tenant_id="$tenant"}[5m]))',
        'sum by (tenant_id) (rate(creditos_requests_total{service=~"$service"}[5m]))',
        "label_values(tenant_id)",
    ):
        unsafe_dashboard = DashboardDefinition(
            uid="ctos-internal-unsafe",
            slug="unsafe",
            title="Unsafe",
            description="Unsafe dashboard",
            scope=DashboardScope.INTERNAL,
            tags=("creditos", "internal"),
            variables=(
                DashboardVariable(
                    name="service",
                    label="Serviço",
                    kind="query",
                    query=query,
                ),
            ),
            panels=(
                DashboardPanel(
                    title="Violação",
                    description="Não permitido",
                    query=query,
                    unit="req/s",
                ),
            ),
        )

        with pytest.raises(ValueError, match="tenant_id"):
            validate_dashboard_catalog((unsafe_dashboard,))


def test_dashboard_validation_rejects_unsafe_metadata_and_export_options() -> None:
    unsafe_boolean_dashboard = DashboardDefinition(
        uid="ctos-internal-unsafe",
        slug="unsafe",
        title="Unsafe",
        description="Unsafe dashboard",
        scope=DashboardScope.INTERNAL,
        tags=("creditos", "internal"),
        variables=(
            DashboardVariable(
                name="service",
                label="Serviço",
                kind="query",
                query="label_values(service)",
                include_all="false",  # type: ignore[arg-type]
            ),
        ),
        panels=(
            DashboardPanel(
                title="Seguro",
                description="Painel válido",
                query='sum by (service) (rate(creditos_requests_total{service=~"$service"}[5m]))',
                unit="req/s",
            ),
        ),
    )
    unsafe_refresh_dashboard = DashboardDefinition(
        uid="ctos-internal-unsafe",
        slug="unsafe",
        title="Unsafe",
        description="Unsafe dashboard",
        scope=DashboardScope.INTERNAL,
        tags=("creditos", "internal"),
        variables=(),
        panels=(
            DashboardPanel(
                title="Seguro",
                description="Painel válido",
                query="sum by (service) (creditos_requests_total)",
                unit="req/s",
            ),
        ),
        refresh="1ms",
    )
    unsafe_visualization_dashboard = DashboardDefinition(
        uid="ctos-internal-unsafe",
        slug="unsafe",
        title="Unsafe",
        description="Unsafe dashboard",
        scope=DashboardScope.INTERNAL,
        tags=("creditos", "internal"),
        variables=(),
        panels=(
            DashboardPanel(
                title="Logs",
                description="Não permitido",
                query="sum by (service) (creditos_requests_total)",
                unit="req/s",
                visualization="logs",
            ),
        ),
    )

    with pytest.raises(ValueError, match="include_all"):
        validate_dashboard_catalog((unsafe_boolean_dashboard,))
    with pytest.raises(ValueError, match="refresh"):
        validate_dashboard_catalog((unsafe_refresh_dashboard,))
    with pytest.raises(ValueError, match="visualização"):
        validate_dashboard_catalog((unsafe_visualization_dashboard,))


def test_grafana_export_is_deterministic_internal_and_safe() -> None:
    dashboard = internal_dashboard_catalog()[0]
    exported = export_grafana_dashboard(dashboard)
    exported_again = export_grafana_dashboard(dashboard)
    serialized = json.dumps(exported, ensure_ascii=False, sort_keys=True).lower()

    assert exported == exported_again
    assert exported["uid"] == dashboard.uid
    assert exported["id"] is None
    assert exported["editable"] is False
    assert exported["tags"] == list(dashboard.tags)
    assert exported["time"] == {"from": "now-6h", "to": "now"}
    assert exported["refresh"] == "30s"
    assert len(exported["panels"]) == len(dashboard.panels)
    assert "templating" in exported
    latency_panel = next(
        panel for panel in exported["panels"] if panel["title"] == "Latência p95/p99 por serviço"
    )
    placeholder_panel = next(
        panel for panel in exported["panels"] if panel["title"] == "CPU por serviço"
    )
    assert len(latency_panel["targets"]) == 2
    assert {target["legendFormat"] for target in latency_panel["targets"]} == {
        "{{service}} p95",
        "{{service}} p99",
    }
    assert "Placeholder:" in placeholder_panel["description"]
    for forbidden in FORBIDDEN_DASHBOARD_TERMS:
        assert forbidden not in serialized


def test_versioned_grafana_dashboard_files_match_catalog_exports() -> None:
    root = Path("ops/observability/grafana/dashboards/internal")
    provider = Path("ops/observability/grafana/provisioning/dashboards/internal.yaml")
    expected_files = {
        f"{dashboard.slug}.json": export_grafana_dashboard(dashboard)
        for dashboard in internal_dashboard_catalog()
    }

    assert root.is_dir()
    assert provider.is_file()
    provider_content = provider.read_text(encoding="utf-8")
    assert "ops/observability/grafana/dashboards/internal" in provider_content
    assert "datasources" not in provider_content
    assert "password" not in provider_content.lower()
    assert "token" not in provider_content.lower()
    assert {path.name for path in root.glob("*.json")} == set(expected_files)
    for filename, expected in expected_files.items():
        actual = json.loads((root / filename).read_text(encoding="utf-8"))
        assert actual == expected
