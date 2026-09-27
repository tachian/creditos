from __future__ import annotations

# ruff: noqa: E501
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from creditos_security.masking import sanitize_log_text


class DashboardScope(StrEnum):
    INTERNAL = "internal"
    CUSTOMER_FACING = "customer-facing"


@dataclass(frozen=True, slots=True)
class DashboardVariable:
    name: str
    label: str
    kind: str
    query: str | tuple[str, ...]
    free_text: bool = False
    multi: bool = True
    include_all: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "query": self.query,
            "free_text": self.free_text,
            "multi": self.multi,
            "include_all": self.include_all,
        }


@dataclass(frozen=True, slots=True)
class DashboardTarget:
    query: str
    legend_format: str

    def to_dict(self) -> dict[str, str]:
        return {
            "query": self.query,
            "legend_format": self.legend_format,
        }


@dataclass(frozen=True, slots=True)
class DashboardPanel:
    title: str
    description: str
    query: str
    unit: str
    legend_format: str = "{{service}} {{operation}} {{status}}"
    extra_targets: tuple[DashboardTarget, ...] = ()
    data_source: str = "prometheus"
    visualization: str = "timeseries"
    placeholder: bool = False
    placeholder_reason: str | None = None
    uses_raw_logs: bool = False
    uses_raw_traces: bool = False

    def to_dict(self) -> dict[str, Any]:
        output = {
            "title": self.title,
            "description": self.description,
            "query": self.query,
            "unit": self.unit,
            "legend_format": self.legend_format,
            "extra_targets": tuple(target.to_dict() for target in self.extra_targets),
            "data_source": self.data_source,
            "visualization": self.visualization,
            "placeholder": self.placeholder,
            "placeholder_reason": self.placeholder_reason,
        }
        if self.uses_raw_logs:
            output["uses_raw_logs"] = self.uses_raw_logs
        if self.uses_raw_traces:
            output["uses_raw_traces"] = self.uses_raw_traces
        return output


@dataclass(frozen=True, slots=True)
class DashboardDefinition:
    uid: str
    slug: str
    title: str
    description: str
    scope: DashboardScope
    tags: tuple[str, ...]
    variables: tuple[DashboardVariable, ...]
    panels: tuple[DashboardPanel, ...]
    refresh: str = "30s"
    time_from: str = "now-6h"
    data_sources: frozenset[str] = frozenset({"prometheus"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "scope": self.scope.value,
            "tags": self.tags,
            "variables": tuple(variable.to_dict() for variable in self.variables),
            "panels": tuple(panel.to_dict() for panel in self.panels),
            "refresh": self.refresh,
            "time_from": self.time_from,
            "data_sources": tuple(sorted(self.data_sources)),
        }


_FORBIDDEN_DASHBOARD_TERMS = (
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
        "token",
        "secret",
    }
)
_ALLOWED_LABELS = frozenset(
    {
        "channel",
        "contract",
        "contract_version",
        "destination",
        "environment",
        "integration_class",
        "operation",
        "operation_type",
        "product_type",
        "release_ref",
        "service",
        "source",
        "status",
        "tenant_isolation_tier",
        "version",
    }
)
_SAFE_VARIABLE_NAMES = frozenset(
    {
        "channel",
        "contract",
        "contract_version",
        "destination",
        "environment",
        "integration_class",
        "operation",
        "operation_type",
        "product_type",
        "service",
        "source",
        "status",
        "tenant_isolation_tier",
        "version",
    }
)
_LABEL_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:=~|!~|=|!=)")
_GROUPING_PATTERN = re.compile(r"\b(?:by|without)\s*\(([^)]*)\)")
_LABEL_VALUES_PATTERN = re.compile(r"\blabel_values\s*\(([^)]*)\)")
_LABEL_REPLACE_PATTERN = re.compile(
    r'\blabel_replace\s*\([^,]+,\s*"([^"]+)"\s*,[^,]+,\s*"([^"]+)"',
)
_ALLOWED_REFRESHES = frozenset({"30s", "1m", "5m"})
_ALLOWED_TIME_RANGES = frozenset({"now-1h", "now-6h", "now-12h", "now-24h"})
_ALLOWED_VISUALIZATIONS = frozenset({"timeseries", "stat", "table"})


def internal_dashboard_catalog() -> tuple[DashboardDefinition, ...]:
    return (
        _dashboard(
            uid="ctos-internal-platform-overview",
            slug="platform-overview",
            title="CreditOS — Platform Overview",
            description="Saúde técnica geral dos serviços internos da plataforma.",
            variables=(
                _query_variable("environment", "Ambiente", "label_values(environment)"),
                _query_variable("service", "Serviço", "label_values(service)"),
                _query_variable(
                    "tenant_isolation_tier",
                    "Tier de isolamento",
                    "label_values(tenant_isolation_tier)",
                ),
            ),
            panels=(
                _panel(
                    "Taxa de erro por serviço",
                    "Erros por serviço e status técnico.",
                    'sum by (service, status) (rate(creditos_requests_total{environment=~"$environment",service=~"$service",status=~"error|failed"}[5m]))',
                    "req/s",
                ),
                _panel(
                    "Latência p95/p99 por serviço",
                    "Percentis de duração por serviço usando histograma agregável.",
                    'histogram_quantile(0.95, sum by (service, le) (rate(creditos_request_duration_bucket{environment=~"$environment",service=~"$service"}[5m])))',
                    "ms",
                    legend_format="{{service}} p95",
                    extra_targets=(
                        DashboardTarget(
                            query='histogram_quantile(0.99, sum by (service, le) (rate(creditos_request_duration_bucket{environment=~"$environment",service=~"$service"}[5m])))',
                            legend_format="{{service}} p99",
                        ),
                    ),
                ),
                _panel(
                    "Throughput por serviço",
                    "Volume de operações por serviço.",
                    'sum by (service) (rate(creditos_requests_total{environment=~"$environment",service=~"$service"}[5m]))',
                    "req/s",
                ),
                _panel(
                    "CPU por serviço",
                    "Uso de CPU de runtime/processo por serviço quando o Collector publicar essas métricas.",
                    'sum by (service) (rate(process_cpu_time_seconds_total{environment=~"$environment",service=~"$service"}[5m]))',
                    "percent",
                    legend_format="{{service}} cpu",
                    placeholder=True,
                    placeholder_reason="Depende de métricas de processo/runtime publicadas pelo Collector.",
                ),
                _panel(
                    "Memória por serviço",
                    "Memória residente de runtime/processo por serviço quando o Collector publicar essas métricas.",
                    'max by (service) (process_resident_memory_bytes{environment=~"$environment",service=~"$service"})',
                    "bytes",
                    legend_format="{{service}} memory",
                    placeholder=True,
                    placeholder_reason="Depende de métricas de processo/runtime publicadas pelo Collector.",
                ),
                _panel(
                    "Saturação por serviço",
                    "Razão de saturação técnica agregada por serviço.",
                    'max by (service) (creditos_service_saturation_ratio{environment=~"$environment",service=~"$service"})',
                    "percent",
                    legend_format="{{service}} saturation",
                    placeholder=True,
                    placeholder_reason="Métrica será materializada quando limites operacionais por serviço forem definidos.",
                ),
                _panel(
                    "Health e readiness",
                    "Status agregado de health/readiness por serviço.",
                    'min by (service) (creditos_service_readiness{environment=~"$environment",service=~"$service"})',
                    "state",
                    placeholder=True,
                    placeholder_reason="Métrica será materializada quando endpoints reais forem expostos por serviço.",
                ),
                _panel(
                    "Versão e deploy atual",
                    "Versão operacional exposta por serviço.",
                    'max by (service, version) (creditos_service_version_info{environment=~"$environment",service=~"$service"})',
                    "short",
                    placeholder=True,
                    placeholder_reason="Release metadata real depende de eventos de deploy da pipeline.",
                ),
            ),
        ),
        _dashboard(
            uid="ctos-internal-public-api",
            slug="public-api",
            title="CreditOS — Public API",
            description="Operação das APIs públicas e contratos de borda.",
            variables=(
                _query_variable("environment", "Ambiente", "label_values(environment)"),
                _query_variable("service", "Serviço", "label_values(service)"),
                _query_variable("operation", "Operação", "label_values(operation)"),
                _query_variable("status", "Status", "label_values(status)"),
                _query_variable("channel", "Canal", "label_values(channel)"),
                _query_variable("product_type", "Produto", "label_values(product_type)"),
            ),
            panels=(
                _panel(
                    "Requisições por operação",
                    "Throughput HTTP por operação e status.",
                    'sum by (operation, status) (rate(creditos_requests_total{environment=~"$environment",service=~"$service",operation=~"$operation",status=~"$status",channel=~"$channel",product_type=~"$product_type"}[5m]))',
                    "req/s",
                ),
                _panel(
                    "Latência p50/p95/p99 por operação",
                    "Percentis de latência das operações públicas.",
                    'histogram_quantile(0.50, sum by (operation, le) (rate(creditos_request_duration_bucket{environment=~"$environment",service=~"$service",operation=~"$operation"}[5m])))',
                    "ms",
                    legend_format="{{operation}} p50",
                    extra_targets=(
                        DashboardTarget(
                            query='histogram_quantile(0.95, sum by (operation, le) (rate(creditos_request_duration_bucket{environment=~"$environment",service=~"$service",operation=~"$operation"}[5m])))',
                            legend_format="{{operation}} p95",
                        ),
                        DashboardTarget(
                            query='histogram_quantile(0.99, sum by (operation, le) (rate(creditos_request_duration_bucket{environment=~"$environment",service=~"$service",operation=~"$operation"}[5m])))',
                            legend_format="{{operation}} p99",
                        ),
                    ),
                ),
                _panel(
                    "Erros 4xx e 5xx",
                    "Erros categorizados por status técnico.",
                    'sum by (operation, status) (rate(creditos_requests_total{environment=~"$environment",operation_type="http",status=~"client_error|server_error"}[5m]))',
                    "req/s",
                ),
                _panel(
                    "Rate limiting e idempotência",
                    "Sinais futuros de proteção de borda e idempotência.",
                    'sum by (operation, status) (rate(creditos_api_guardrail_total{environment=~"$environment",operation=~"$operation"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Métrica será materializada em adapters HTTP reais.",
                ),
            ),
        ),
        _dashboard(
            uid="ctos-internal-grpc",
            slug="internal-grpc",
            title="CreditOS — Internal gRPC",
            description="Chamadas internas gRPC entre microsserviços.",
            variables=(
                _query_variable("environment", "Ambiente", "label_values(environment)"),
                _query_variable("service", "Serviço", "label_values(service)"),
                _query_variable("operation", "Método/operação", "label_values(operation)"),
                _query_variable("status", "Status", "label_values(status)"),
            ),
            panels=(
                _panel(
                    "Latência por método",
                    "Latência gRPC por operação interna.",
                    'histogram_quantile(0.95, sum by (operation, le) (rate(creditos_request_duration_bucket{environment=~"$environment",operation_type="grpc",operation=~"$operation"}[5m])))',
                    "ms",
                ),
                _panel(
                    "Erros por método",
                    "Falhas de chamadas internas gRPC.",
                    'sum by (service, operation, status) (rate(creditos_requests_total{environment=~"$environment",operation_type="grpc",operation=~"$operation",status=~"$status"}[5m]))',
                    "req/s",
                ),
                _panel(
                    "Deadlines e timeouts",
                    "Timeouts internos quando métricas dedicadas existirem.",
                    'sum by (service, operation) (rate(creditos_grpc_timeout_total{environment=~"$environment",operation=~"$operation"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Depende de interceptors gRPC reais e métricas de timeout.",
                ),
                _panel(
                    "Propagação de contexto",
                    "Falhas futuras de propagação de contexto interno.",
                    'sum by (service, operation) (rate(creditos_context_propagation_failure_total{environment=~"$environment",operation=~"$operation"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Métrica será adicionada quando interceptors reais validarem contexto.",
                ),
            ),
        ),
        _dashboard(
            uid="ctos-internal-nats-jetstream-dlq",
            slug="nats-jetstream-dlq",
            title="CreditOS — NATS JetStream and DLQ",
            description="Operação de eventos, consumers duráveis, retries e DLQs.",
            variables=(
                _query_variable("environment", "Ambiente", "label_values(environment)"),
                _query_variable("service", "Serviço", "label_values(service)"),
                _query_variable("source", "Origem", "label_values(source)"),
                _query_variable("destination", "Destino", "label_values(destination)"),
            ),
            panels=(
                _panel(
                    "Backlog por stream",
                    "Mensagens pendentes por stream lógico.",
                    'sum by (source, destination) (creditos_event_backlog{environment=~"$environment",source=~"$source",destination=~"$destination"})',
                    "messages",
                    legend_format="{{source}} → {{destination}} backlog",
                    placeholder=True,
                    placeholder_reason="Depende da integração real com NATS JetStream.",
                ),
                _panel(
                    "Lag por consumer",
                    "Atraso de consumidores duráveis.",
                    'max by (source, destination) (creditos_event_consumer_lag{environment=~"$environment",source=~"$source",destination=~"$destination"})',
                    "messages",
                    legend_format="{{source}} → {{destination}} lag",
                    placeholder=True,
                    placeholder_reason="Depende da integração real com NATS JetStream.",
                ),
                _panel(
                    "Retries e DLQ",
                    "Retries, falhas e mensagens enviadas para DLQ.",
                    'sum by (source, destination, status) (rate(creditos_event_delivery_total{environment=~"$environment",source=~"$source",destination=~"$destination",status=~"retry|dlq"}[5m]))',
                    "events/s",
                    legend_format="{{source}} → {{destination}} {{status}}",
                    placeholder=True,
                    placeholder_reason="Métrica será materializada nos publishers/consumers reais.",
                ),
                _panel(
                    "Idade de mensagens",
                    "Idade máxima de mensagem pendente.",
                    'max by (source, destination) (creditos_event_message_age_seconds{environment=~"$environment",source=~"$source",destination=~"$destination"})',
                    "s",
                    legend_format="{{source}} → {{destination}} age",
                    placeholder=True,
                    placeholder_reason="Depende de consumers reais.",
                ),
                _panel(
                    "Replay e reprocessamento",
                    "Volume de replay/reprocessamento controlado.",
                    'sum by (source, destination, status) (rate(creditos_event_reprocess_total{environment=~"$environment",source=~"$source",destination=~"$destination"}[5m]))',
                    "events/s",
                    legend_format="{{source}} → {{destination}} reprocess",
                    placeholder=True,
                    placeholder_reason="Depende de fluxo operacional real de reprocessamento.",
                ),
            ),
        ),
        _dashboard(
            uid="ctos-internal-external-integrations",
            slug="external-integrations",
            title="CreditOS — External Integrations",
            description="Falhas, latência, retries, fallback e custo técnico de integrações externas.",
            variables=(
                _query_variable("environment", "Ambiente", "label_values(environment)"),
                _query_variable("service", "Serviço", "label_values(service)"),
                _query_variable(
                    "integration_class",
                    "Classe de integração",
                    "label_values(integration_class)",
                ),
                _query_variable("destination", "Adapter/destino", "label_values(destination)"),
                _query_variable("product_type", "Produto", "label_values(product_type)"),
                _query_variable("status", "Status", "label_values(status)"),
            ),
            panels=(
                _panel(
                    "Falhas por classe",
                    "Falhas por classe técnica de integração.",
                    'sum by (service, integration_class, status) (rate(creditos_requests_total{environment=~"$environment",service=~"$service",operation_type="integration",destination=~"$destination",product_type=~"$product_type",status=~"failed|timeout|fallback"}[5m]))',
                    "events/s",
                ),
                _panel(
                    "Latência por adapter",
                    "Latência de adapters externos.",
                    'histogram_quantile(0.95, sum by (service, destination, le) (rate(creditos_request_duration_bucket{environment=~"$environment",service=~"$service",operation_type="integration",destination=~"$destination"}[5m])))',
                    "ms",
                ),
                _panel(
                    "Timeout, retry e fallback",
                    "Sinais operacionais de resiliência por destino.",
                    'sum by (service, destination, status) (rate(creditos_requests_total{environment=~"$environment",service=~"$service",operation_type="integration",destination=~"$destination",status=~"timeout|retry|fallback"}[5m]))',
                    "events/s",
                ),
                _panel(
                    "Custo estimado e real",
                    "Custo técnico agregado de integrações quando disponível.",
                    'sum by (service, destination, product_type) (rate(creditos_integration_cost_units_total{environment=~"$environment",service=~"$service",destination=~"$destination",product_type=~"$product_type"}[5m]))',
                    "cost_units/s",
                    placeholder=True,
                    placeholder_reason="Métrica de custo será consolidada quando providers reais forem configurados.",
                ),
            ),
        ),
        _dashboard(
            uid="ctos-internal-audit-security",
            slug="audit-security",
            title="CreditOS — Audit and Security",
            description="Falhas críticas de auditoria e sinais de segurança operacional.",
            variables=(
                _query_variable("environment", "Ambiente", "label_values(environment)"),
                _query_variable("service", "Serviço", "label_values(service)"),
                _query_variable("status", "Status", "label_values(status)"),
                _query_variable(
                    "tenant_isolation_tier",
                    "Tier de isolamento",
                    "label_values(tenant_isolation_tier)",
                ),
            ),
            panels=(
                _panel(
                    "Falha crítica de auditoria",
                    "Falhas técnicas de registro de auditoria crítica.",
                    'sum by (service, status) (rate(creditos_audit_critical_failure_total{environment=~"$environment",service=~"$service"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Auditoria oficial continua separada; painel é apenas sinal operacional.",
                ),
                _panel(
                    "Autorização negada",
                    "Negativas de autorização por serviço.",
                    'sum by (service, status) (rate(creditos_authorization_denied_total{environment=~"$environment",service=~"$service"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Depende de adapters reais de autorização.",
                ),
                _panel(
                    "Tentativas cross-tenant",
                    "Tentativas de violação de isolamento por tier, sem expor tenant específico.",
                    'sum by (service, tenant_isolation_tier) (rate(creditos_cross_tenant_attempt_total{environment=~"$environment",service=~"$service",tenant_isolation_tier=~"$tenant_isolation_tier"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Sinal agregado; não usa identificador de tenant livre.",
                ),
                _panel(
                    "Vazamento potencial detectado por gates",
                    "Falhas de gates de privacidade em validações técnicas.",
                    'sum by (service, status) (rate(creditos_privacy_gate_total{environment=~"$environment",service=~"$service",status=~"$status"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Métrica depende de integração futura dos gates ao pipeline.",
                ),
            ),
        ),
        _dashboard(
            uid="ctos-internal-deploy-release-health",
            slug="deploy-release-health",
            title="CreditOS — Deploy and Release Health",
            description="Saúde pós-deploy e comparação operacional de releases.",
            variables=(
                _query_variable("environment", "Ambiente", "label_values(environment)"),
                _query_variable("service", "Serviço", "label_values(service)"),
                _query_variable("version", "Versão", "label_values(version)"),
            ),
            panels=(
                _panel(
                    "Versão ativa por serviço",
                    "Versão atual reportada por serviço.",
                    'max by (service, version) (creditos_service_version_info{environment=~"$environment",service=~"$service",version=~"$version"})',
                    "short",
                    placeholder=True,
                    placeholder_reason="Release metadata real depende da pipeline.",
                ),
                _panel(
                    "Commit/digest publicado",
                    "Release metadata técnico por versão e digest/commit publicado pela pipeline.",
                    'max by (service, version, release_ref) (creditos_release_info{environment=~"$environment",service=~"$service",version=~"$version"})',
                    "short",
                    legend_format="{{service}} {{version}} {{release_ref}}",
                    placeholder=True,
                    placeholder_reason="Release metadata real depende da pipeline e deve usar release_ref controlado com baixa cardinalidade.",
                ),
                _panel(
                    "Erro pós-deploy",
                    "Taxa de erro por versão de serviço.",
                    'sum by (service, version, status) (rate(creditos_requests_total{environment=~"$environment",service=~"$service",version=~"$version",status=~"error|failed"}[5m]))',
                    "req/s",
                    placeholder=True,
                    placeholder_reason="A label version será populada quando release metadata estiver instrumentado.",
                ),
                _panel(
                    "Latência pós-deploy",
                    "p95 por versão operacional.",
                    'histogram_quantile(0.95, sum by (service, version, le) (rate(creditos_request_duration_bucket{environment=~"$environment",service=~"$service",version=~"$version"}[5m])))',
                    "ms",
                    placeholder=True,
                    placeholder_reason="A label version será populada quando release metadata estiver instrumentado.",
                ),
                _panel(
                    "Comparação antes/depois",
                    "Comparação operacional de erro e latência por versão.",
                    'sum by (service, version) (rate(creditos_release_regression_total{environment=~"$environment",service=~"$service",version=~"$version"}[5m]))',
                    "events/s",
                    placeholder=True,
                    placeholder_reason="Sinal depende de SLO watch e eventos de release futuros.",
                ),
            ),
        ),
    )


def validate_dashboard_catalog(catalog: tuple[DashboardDefinition, ...]) -> None:
    seen_uids: set[str] = set()
    seen_slugs: set[str] = set()
    for dashboard in catalog:
        _validate_identifier(dashboard.uid, field_name="uid")
        _validate_identifier(dashboard.slug, field_name="slug")
        if dashboard.uid in seen_uids:
            raise ValueError(f"dashboard uid duplicado: {dashboard.uid}")
        if dashboard.slug in seen_slugs:
            raise ValueError(f"dashboard slug duplicado: {dashboard.slug}")
        seen_uids.add(dashboard.uid)
        seen_slugs.add(dashboard.slug)
        if dashboard.scope is not DashboardScope.INTERNAL:
            raise ValueError("dashboards desta story devem ser internos")
        if "internal" not in dashboard.tags:
            raise ValueError(f"dashboard {dashboard.slug} deve possuir tag internal")
        if dashboard.data_sources - {"prometheus"}:
            raise ValueError(f"dashboard {dashboard.slug} usa fonte de dados não permitida")
        if dashboard.refresh not in _ALLOWED_REFRESHES:
            raise ValueError(f"refresh de dashboard não permitido: {dashboard.refresh}")
        if dashboard.time_from not in _ALLOWED_TIME_RANGES:
            raise ValueError(f"janela temporal de dashboard não permitida: {dashboard.time_from}")
        _validate_safe_text(dashboard.title, field_name="title")
        _validate_safe_text(dashboard.description, field_name="description")
        for tag in dashboard.tags:
            _validate_safe_text(tag, field_name="tag")
        for variable in dashboard.variables:
            _validate_variable(variable)
        if not dashboard.panels:
            raise ValueError(f"dashboard {dashboard.slug} não possui painéis")
        for panel in dashboard.panels:
            _validate_panel(panel)


def export_grafana_dashboard(dashboard: DashboardDefinition) -> dict[str, Any]:
    validate_dashboard_catalog((dashboard,))
    return {
        "annotations": {"list": []},
        "editable": False,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "panels": [
            _export_panel(panel, index=index)
            for index, panel in enumerate(dashboard.panels, start=1)
        ],
        "refresh": dashboard.refresh,
        "schemaVersion": 39,
        "tags": list(dashboard.tags),
        "templating": {
            "list": [_export_variable(variable) for variable in dashboard.variables],
        },
        "time": {"from": dashboard.time_from, "to": "now"},
        "timezone": "browser",
        "title": dashboard.title,
        "uid": dashboard.uid,
        "version": 1,
    }


def _dashboard(
    *,
    uid: str,
    slug: str,
    title: str,
    description: str,
    variables: tuple[DashboardVariable, ...],
    panels: tuple[DashboardPanel, ...],
) -> DashboardDefinition:
    return DashboardDefinition(
        uid=uid,
        slug=slug,
        title=title,
        description=description,
        scope=DashboardScope.INTERNAL,
        tags=("creditos", "internal", "technical", "mvp"),
        variables=variables,
        panels=panels,
    )


def _panel(
    title: str,
    description: str,
    query: str,
    unit: str,
    *,
    legend_format: str = "{{service}} {{operation}} {{status}}",
    extra_targets: tuple[DashboardTarget, ...] = (),
    placeholder: bool = False,
    placeholder_reason: str | None = None,
) -> DashboardPanel:
    return DashboardPanel(
        title=title,
        description=description,
        query=query,
        unit=unit,
        legend_format=legend_format,
        extra_targets=extra_targets,
        placeholder=placeholder,
        placeholder_reason=placeholder_reason,
    )


def _query_variable(name: str, label: str, query: str) -> DashboardVariable:
    return DashboardVariable(name=name, label=label, kind="query", query=query)


def _validate_variable(variable: DashboardVariable) -> None:
    if variable.name not in _SAFE_VARIABLE_NAMES:
        raise ValueError(f"variável de dashboard não permitida: {variable.name}")
    if variable.kind not in {"query", "custom"}:
        raise ValueError(f"tipo de variável não permitido: {variable.kind}")
    if not isinstance(variable.multi, bool):
        raise ValueError(f"multi deve ser booleano: {variable.name}")
    if not isinstance(variable.include_all, bool):
        raise ValueError(f"include_all deve ser booleano: {variable.name}")
    if variable.free_text:
        raise ValueError(f"variável livre não permitida: {variable.name}")
    _validate_safe_text(variable.name, field_name="variable.name")
    _validate_safe_text(variable.label, field_name="variable.label")
    if isinstance(variable.query, str):
        _validate_safe_query(variable.query)
    else:
        for option in variable.query:
            _validate_safe_text(option, field_name="variable.option")


def _validate_panel(panel: DashboardPanel) -> None:
    if panel.data_source != "prometheus":
        raise ValueError(f"fonte de dados não permitida: {panel.data_source}")
    if panel.visualization not in _ALLOWED_VISUALIZATIONS:
        raise ValueError(f"visualização não permitida: {panel.visualization}")
    if panel.uses_raw_logs:
        raise ValueError(f"painel {panel.title} usa logs crus")
    if panel.uses_raw_traces:
        raise ValueError(f"painel {panel.title} usa traces crus")
    if panel.placeholder and not panel.placeholder_reason:
        raise ValueError(f"painel placeholder sem motivo: {panel.title}")
    _validate_safe_text(panel.title, field_name="panel.title")
    _validate_safe_text(panel.description, field_name="panel.description")
    _validate_safe_text(panel.unit, field_name="panel.unit")
    _validate_safe_text(panel.legend_format, field_name="panel.legend_format")
    _validate_safe_query(panel.query)
    for target in panel.extra_targets:
        _validate_safe_text(target.legend_format, field_name="target.legend_format")
        _validate_safe_query(target.query)
    if panel.placeholder_reason:
        _validate_safe_text(panel.placeholder_reason, field_name="panel.placeholder_reason")


def _validate_safe_query(query: str) -> None:
    _validate_safe_text(query, field_name="query")
    lower_query = query.lower()
    if any(term in lower_query for term in ("loki", "tempo", "traceql", "logql")):
        raise ValueError("dashboards internos não devem consultar logs/traces crus")
    for label in _LABEL_PATTERN.findall(query):
        _validate_prometheus_label(label)
    for labels in _GROUPING_PATTERN.findall(query):
        for label in _split_label_list(labels):
            _validate_prometheus_label(label)
    for label in _extract_label_values_labels(query):
        _validate_prometheus_label(label)
        if label not in _SAFE_VARIABLE_NAMES:
            raise ValueError(f"label_values usa label fora da allowlist de variáveis: {label}")
    for destination_label, source_label in _LABEL_REPLACE_PATTERN.findall(query):
        _validate_prometheus_label(destination_label)
        _validate_prometheus_label(source_label)


def _validate_prometheus_label(label: str) -> None:
    if label in _FORBIDDEN_LABELS:
        raise ValueError(f"label proibida em query de dashboard: {label}")
    if label not in _ALLOWED_LABELS and label != "le":
        raise ValueError(f"label fora da allowlist de dashboard: {label}")


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


def _validate_identifier(value: str, *, field_name: str) -> None:
    _validate_safe_text(value, field_name=field_name)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,80}", value):
        raise ValueError(f"{field_name} deve ser identificador técnico estável")


def _validate_safe_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} deve ser string")
    sanitized = sanitize_log_text(value)
    if sanitized != value or not value:
        raise ValueError(f"{field_name} contém texto inseguro")
    lower_value = value.lower()
    for forbidden in _FORBIDDEN_DASHBOARD_TERMS:
        if forbidden in lower_value:
            raise ValueError(f"{field_name} contém termo proibido: {forbidden}")


def _export_variable(variable: DashboardVariable) -> dict[str, Any]:
    query = variable.query
    if isinstance(query, tuple):
        query = ",".join(query)
    return {
        "allValue": ".*" if variable.include_all else None,
        "current": {"selected": False, "text": "All", "value": "$__all"},
        "datasource": {"type": "prometheus", "uid": "prometheus"},
        "definition": query,
        "hide": 0,
        "includeAll": variable.include_all,
        "label": variable.label,
        "multi": variable.multi,
        "name": variable.name,
        "options": [],
        "query": query,
        "refresh": 1,
        "skipUrlSync": True,
        "type": variable.kind,
    }


def _export_panel(panel: DashboardPanel, *, index: int) -> dict[str, Any]:
    width = 12
    height = 8
    zero_based_index = index - 1
    description = panel.description
    if panel.placeholder_reason:
        description = f"{description}\n\nPlaceholder: {panel.placeholder_reason}"
    return {
        "datasource": {"type": "prometheus", "uid": "prometheus"},
        "description": description,
        "fieldConfig": {
            "defaults": {"unit": panel.unit},
            "overrides": [],
        },
        "gridPos": {
            "h": height,
            "w": width,
            "x": 0 if zero_based_index % 2 == 0 else width,
            "y": (zero_based_index // 2) * height,
        },
        "id": index,
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "none"},
        },
        "targets": _export_targets(panel),
        "title": panel.title,
        "type": panel.visualization,
    }


def _export_targets(panel: DashboardPanel) -> list[dict[str, Any]]:
    targets = (
        DashboardTarget(query=panel.query, legend_format=panel.legend_format),
        *panel.extra_targets,
    )
    ref_ids = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [
        {
            "datasource": {"type": "prometheus", "uid": "prometheus"},
            "expr": target.query,
            "legendFormat": target.legend_format,
            "refId": ref_ids[index],
        }
        for index, target in enumerate(targets)
    ]
