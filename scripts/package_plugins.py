#!/usr/bin/env python3
"""Gera um ZIP por plataforma, pronto para a release.

Uso:
    python3 scripts/package_plugins.py [--out dist]

Saída, para cada plugin de harnesses.json:
    <out>/<plugin>-<pacote>-<versão>.zip  e  <out>/<plugin>-<pacote>.zip

O pacote é o nome do harness (claude, codex, dsh), menos o de layout "gpt",
que vira "gpts". A cópia sem versão serve ao link estável
releases/latest/download/<plugin>-<pacote>.zip do README e do site. O conteúdo
da pasta do pacote vai na raiz do ZIP (manifesto, skills/, LICENSE, NOTICE e
COMMERCIAL.md). __pycache__, *.pyc e .DS_Store ficam de fora.

Também escreve, no formato de output do GitHub Actions, as tags de release
esperadas (<plugin>-v<versão>), para o workflow decidir o que publicar.
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {".DS_Store"}
SKIP_SUFFIXES = {".pyc"}
# Data fixa para o ZIP sair igual a partir do mesmo conteúdo.
FIXED_DATE = (2020, 1, 1, 0, 0, 0)


def package_name(harness: str, target: dict) -> str:
    return "gpts" if target.get("layout") == "gpt" else harness


def zip_dir(src: Path, dest: Path) -> int:
    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            rel = path.relative_to(src)
            if (
                path.is_dir()
                or path.name in SKIP_FILES
                or path.suffix in SKIP_SUFFIXES
                or SKIP_DIRS & set(rel.parts)
            ):
                continue
            info = zipfile.ZipInfo(rel.as_posix(), FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (path.stat().st_mode & 0o777) << 16
            zf.writestr(info, path.read_bytes())
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="dist", help="pasta de saída (padrão: dist)")
    args = parser.parse_args()

    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "harnesses.json").read_text(encoding="utf-8"))
    tags: list[str] = []

    for plugin, spec in config["plugins"].items():
        version = json.loads((ROOT / spec["core"] / "plugin.core.json").read_text(encoding="utf-8"))["version"]
        tags.append(f"{plugin}-v{version}")
        for harness, target in spec["harnesses"].items():
            src = ROOT / target["path"]
            if not src.is_dir():
                print(f"{src.relative_to(ROOT)} não existe. Rode antes: python3 scripts/sync_plugins.py")
                return 1
            name = f"{plugin}-{package_name(harness, target)}"
            dest = out / f"{name}-{version}.zip"
            n = zip_dir(src, dest)
            alias = out / f"{name}.zip"
            alias.write_bytes(dest.read_bytes())
            print(f"{dest.name} e {alias.name}: {n} arquivos")

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"tags={' '.join(tags)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
