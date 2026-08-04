from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def load_build_metadata(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"não foi possível ler o metadata file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"metadata file não é JSON válido: {path}") from exc


def digest_from_metadata(metadata: dict[str, Any]) -> str | None:
    for key in ("containerimage.digest", "containerimage.config.digest"):
        value = metadata.get(key)
        if isinstance(value, str) and DIGEST_PATTERN.fullmatch(value):
            return value

    return None


def validate_digest(digest: str | None) -> str:
    if digest is None or not DIGEST_PATTERN.fullmatch(digest):
        raise ValueError("image digest deve estar no formato sha256:<64 hex>")

    return digest


def build_release_metadata(
    *,
    service: str,
    image_ref: str,
    commit_sha: str,
    image_digest: str,
) -> dict[str, str]:
    if not commit_sha or commit_sha == "unknown":
        raise ValueError("commit_sha é obrigatório e não pode ser unknown")

    return {
        "service": service,
        "image_ref": image_ref,
        "image_digest": validate_digest(image_digest),
        "commit_sha": commit_sha,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "schema": "creditos.container-release-metadata.v1",
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera artefato de release com digest de imagem OCI."
    )
    parser.add_argument("--service", required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image-digest")
    parser.add_argument("--build-metadata-file", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    image_digest = args.image_digest

    if image_digest is None and args.build_metadata_file is not None:
        image_digest = digest_from_metadata(load_build_metadata(args.build_metadata_file))

    try:
        metadata = build_release_metadata(
            service=args.service,
            image_ref=args.image_ref,
            commit_sha=args.commit_sha,
            image_digest=validate_digest(image_digest),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
