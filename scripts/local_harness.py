#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

DEFAULT_HOST = "127.0.0.1"
DEFAULT_SAMPLE_SERVICE_PORT = 18080
DEFAULT_MOCK_SERVICE_PORT = 18081
MAX_JSON_BODY_BYTES = 16 * 1024
LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}


class HarnessError(Exception):
    pass


class HarnessHttpError(HarnessError):
    def __init__(
        self,
        status: HTTPStatus,
        error: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message
        self.extra = extra or {}

    def to_payload(self) -> dict[str, Any]:
        return {
            "error": self.error,
            "message": self.message,
            **self.extra,
        }


@dataclass(frozen=True)
class RunningServer:
    name: str
    httpd: ThreadingHTTPServer
    thread: threading.Thread

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address[:2]
        if host in {"", "0.0.0.0", "::"}:
            host = DEFAULT_HOST
        return f"http://{host}:{port}"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


class JsonHandler(BaseHTTPRequestHandler):
    server_version = "CreditOSLocalHarness/0.1"
    sensitive_headers: ClassVar[set[str]] = {"authorization", "cookie", "set-cookie"}

    def log_message(self, format: str, *args: object) -> None:
        return

    def read_json_body(self) -> dict[str, Any]:
        raw_content_length = self.headers.get("content-length", "0")
        try:
            content_length = int(raw_content_length)
        except ValueError as error:
            raise HarnessHttpError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "Content-Length deve ser inteiro não negativo",
            ) from error

        if content_length < 0:
            raise HarnessHttpError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "Content-Length deve ser inteiro não negativo",
            )

        if content_length > MAX_JSON_BODY_BYTES:
            raise HarnessHttpError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "payload_too_large",
                f"Payload JSON limitado a {MAX_JSON_BODY_BYTES} bytes",
            )

        if content_length == 0:
            return {}

        try:
            raw_body = self.rfile.read(content_length).decode("utf-8")
        except UnicodeDecodeError as error:
            raise HarnessHttpError(
                HTTPStatus.BAD_REQUEST,
                "invalid_encoding",
                "Payload JSON deve usar UTF-8 válido",
            ) from error

        try:
            decoded_body = json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise HarnessHttpError(
                HTTPStatus.BAD_REQUEST,
                "invalid_json",
                "Payload deve ser JSON válido",
            ) from error

        if not isinstance(decoded_body, dict):
            raise HarnessHttpError(
                HTTPStatus.BAD_REQUEST,
                "invalid_json_object",
                "Payload JSON deve ser um objeto",
            )
        return decoded_body

    def write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_not_found(self) -> None:
        self.write_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "not_found",
                "message": "Rota não encontrada no harness local",
            },
        )

    def write_http_error(self, error: HarnessHttpError) -> None:
        self.write_json(error.status, error.to_payload())


class MockDependencyHandler(JsonHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self.write_json(
                HTTPStatus.OK,
                {
                    "service": "creditos-local-mocks",
                    "status": "ok",
                },
            )
            return

        if self.path == "/ready":
            self.write_json(
                HTTPStatus.OK,
                {
                    "dependencies": [],
                    "service": "creditos-local-mocks",
                    "status": "ready",
                },
            )
            return

        if self.path == "/mock/external-risk/v1/profile":
            self.write_json(
                HTTPStatus.OK,
                {
                    "classification": "mocked",
                    "contains_personal_data": False,
                    "provider": "external-risk-mock",
                    "status": "ok",
                    "subject_ref": "placeholder-subject",
                },
            )
            return

        self.write_not_found()

    def do_POST(self) -> None:
        if self.path != "/mock/async-broker/v1/publish":
            self.write_not_found()
            return

        try:
            payload = self.read_json_body()
        except HarnessHttpError as error:
            self.write_http_error(error)
            return

        required_fields = {"specversion", "type", "source", "id", "tenantid", "correlationid"}
        invalid_fields = sorted(
            field
            for field in required_fields
            if not isinstance(payload.get(field), str) or not payload[field].strip()
        )

        if invalid_fields:
            self.write_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "invalid_cloudevent",
                    "invalid_fields": invalid_fields,
                },
            )
            return

        if payload["specversion"] != "1.0":
            self.write_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "invalid_cloudevent",
                    "message": "CloudEvent mockado deve usar specversion 1.0",
                },
            )
            return

        self.write_json(
            HTTPStatus.ACCEPTED,
            {
                "broker": "async-broker-mock",
                "mode": "nats-jetstream-compatible-mock",
                "status": "accepted",
                "stream": "creditos.local.mock",
            },
        )


def build_sample_service_handler(mock_base_url: str) -> type[JsonHandler]:
    class SampleServiceHandler(JsonHandler):
        def do_GET(self) -> None:
            if self.path == "/health":
                self.write_json(
                    HTTPStatus.OK,
                    {
                        "service": "sample-service",
                        "status": "ok",
                    },
                )
                return

            if self.path == "/ready":
                try:
                    mock_ready = get_json(f"{mock_base_url}/ready")
                except HarnessError:
                    self.write_json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {
                            "dependencies": {
                                "local-mocks": "unavailable",
                            },
                            "service": "sample-service",
                            "status": "not_ready",
                        },
                    )
                    return

                if mock_ready.get("status") != "ready":
                    self.write_json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {
                            "dependencies": {
                                "local-mocks": str(mock_ready.get("status", "not_ready")),
                            },
                            "service": "sample-service",
                            "status": "not_ready",
                        },
                    )
                    return

                self.write_json(
                    HTTPStatus.OK,
                    {
                        "dependencies": {
                            "local-mocks": mock_ready["status"],
                        },
                        "service": "sample-service",
                        "status": "ready",
                    },
                )
                return

            if self.path == "/v1/harness/ping":
                try:
                    profile = get_json(f"{mock_base_url}/mock/external-risk/v1/profile")
                    broker_result = post_json(
                        f"{mock_base_url}/mock/async-broker/v1/publish",
                        {
                            "correlationid": "local-harness-correlation",
                            "id": "local-harness-event",
                            "source": "creditos-local-harness",
                            "specversion": "1.0",
                            "tenantid": "tenant-placeholder",
                            "type": "creditos.local.harness.ping",
                        },
                    )
                except HarnessError:
                    self.write_json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {
                            "error": "mock_dependency_unavailable",
                            "service": "sample-service",
                            "status": "not_ready",
                        },
                    )
                    return

                self.write_json(
                    HTTPStatus.OK,
                    {
                        "async-broker-mock": broker_result["status"],
                        "contains_personal_data": False,
                        "external-risk-mock": profile["status"]
                        if "status" in profile
                        else profile["classification"],
                        "service": "sample-service",
                        "status": "ok",
                    },
                )
                return

            self.write_not_found()

    return SampleServiceHandler


def get_json(url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HarnessError(f"Falha ao consultar dependência mockada: {url}") from error

    if not isinstance(payload, dict):
        raise HarnessError(f"Resposta não é objeto JSON: {url}")
    return payload


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            decoded_payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HarnessError(f"Falha ao publicar em dependência mockada: {url}") from error

    if not isinstance(decoded_payload, dict):
        raise HarnessError(f"Resposta não é objeto JSON: {url}")
    return decoded_payload


def start_server(
    name: str,
    handler: type[BaseHTTPRequestHandler],
    host: str,
    port: int,
) -> RunningServer:
    httpd = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=httpd.serve_forever, name=name, daemon=True)
    thread.start()
    return RunningServer(name=name, httpd=httpd, thread=thread)


def start_harness(
    host: str,
    sample_service_port: int,
    mock_service_port: int,
) -> list[RunningServer]:
    if host not in LOOPBACK_HOSTS:
        raise HarnessError("Harness local só aceita bind loopback: use 127.0.0.1 ou localhost")

    mock_server = start_server(
        name="creditos-local-mocks",
        handler=MockDependencyHandler,
        host=host,
        port=mock_service_port,
    )
    sample_server = start_server(
        name="creditos-sample-service",
        handler=build_sample_service_handler(mock_server.base_url),
        host=host,
        port=sample_service_port,
    )
    return [mock_server, sample_server]


def stop_harness(servers: list[RunningServer]) -> None:
    for running_server in reversed(servers):
        running_server.stop()


def run_up(args: argparse.Namespace) -> int:
    servers = start_harness(
        host=args.host,
        sample_service_port=args.sample_service_port,
        mock_service_port=args.mock_service_port,
    )
    stop_event = threading.Event()

    def handle_signal(signum: int, frame: object) -> None:
        stop_event.set()

    previous_sigterm = signal.signal(signal.SIGTERM, handle_signal)
    previous_sigint = signal.signal(signal.SIGINT, handle_signal)

    try:
        print("CreditOS local harness running", flush=True)
        for running_server in servers:
            print(f"- {running_server.name}: {running_server.base_url}", flush=True)
        print("Pressione Ctrl+C para parar.", flush=True)
        stop_event.wait()
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)
        stop_harness(servers)

    return 0


def run_check(args: argparse.Namespace) -> int:
    servers = start_harness(host=args.host, sample_service_port=0, mock_service_port=0)
    sample_service = next(server for server in servers if server.name == "creditos-sample-service")

    try:
        health = get_json(f"{sample_service.base_url}/health")
        readiness = get_json(f"{sample_service.base_url}/ready")
        ping = get_json(f"{sample_service.base_url}/v1/harness/ping")
    finally:
        stop_harness(servers)

    if health["status"] != "ok" or readiness["status"] != "ready" or ping["status"] != "ok":
        raise HarnessError("Harness local não respondeu com estados esperados")

    print("local harness check passed")
    print("sample-service health=ok readiness=ready")
    print(f"external-risk-mock={ping['external-risk-mock']}")
    print(f"async-broker-mock={ping['async-broker-mock']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harness local mockado do CreditOS")
    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser("up", help="Sobe o harness local até Ctrl+C")
    up_parser.add_argument("--host", default=os.getenv("CREDITOS_HARNESS_HOST", DEFAULT_HOST))
    up_parser.add_argument(
        "--sample-service-port",
        default=env_port("CREDITOS_SAMPLE_SERVICE_PORT", DEFAULT_SAMPLE_SERVICE_PORT),
        type=int,
    )
    up_parser.add_argument(
        "--mock-service-port",
        default=env_port("CREDITOS_MOCK_SERVICE_PORT", DEFAULT_MOCK_SERVICE_PORT),
        type=int,
    )
    up_parser.set_defaults(func=run_up)

    check_parser = subparsers.add_parser("check", help="Valida o harness local com portas efêmeras")
    check_parser.add_argument("--host", default=os.getenv("CREDITOS_HARNESS_HOST", DEFAULT_HOST))
    check_parser.set_defaults(func=run_check)

    return parser


def env_port(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        port = int(raw_value)
    except ValueError as error:
        raise HarnessError(f"{name} deve ser uma porta numérica") from error

    if port < 1 or port > 65535:
        raise HarnessError(f"{name} deve estar entre 1 e 65535")

    return port


def main(argv: list[str] | None = None) -> int:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        return int(args.func(args))
    except (HarnessError, OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        print(f"local harness error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
