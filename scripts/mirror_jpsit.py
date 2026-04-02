#!/usr/bin/env python3
"""Repeatable import pipeline for jpsit.com.

Steps:
1. Mirror pages/assets into import/raw/<run_id>/
2. Normalize reusable content into import/normalized/<run_id>/
3. Wire normalized content into the site source directory.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


DEFAULT_URL = "https://jpsit.com"
DEFAULT_SITE_DIR = Path("site/src/content")


class ReusableContentParser(HTMLParser):
    """Small HTML extractor for nav labels, copy blocks, and logo candidates."""

    def __init__(self) -> None:
        super().__init__()
        self._tag_stack: list[str] = []
        self._capture_chunks: list[str] = []
        self._capture_target: str | None = None

        self.nav_labels: list[str] = []
        self.copy_blocks: list[str] = []
        self.logos: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag_stack.append(tag)
        attrs_dict = {k: (v or "") for k, v in attrs}
        classes = attrs_dict.get("class", "").lower()
        identifier = attrs_dict.get("id", "").lower()

        if tag == "img":
            src = attrs_dict.get("src", "")
            alt = attrs_dict.get("alt", "")
            if "logo" in (src + " " + alt).lower():
                self.logos.append(src or alt)

        if tag in {"nav", "a", "p", "li", "h1", "h2", "h3"}:
            if tag == "nav" or "nav" in classes or "menu" in classes or "nav" in identifier:
                self._capture_target = "nav"
                self._capture_chunks = []
            elif tag in {"p", "li", "h1", "h2", "h3"}:
                self._capture_target = "copy"
                self._capture_chunks = []

    def handle_data(self, data: str) -> None:
        if self._capture_target:
            normalized = normalize_space(data)
            if normalized:
                self._capture_chunks.append(normalized)

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack:
            self._tag_stack.pop()

        if self._capture_target and tag in {"nav", "a", "p", "li", "h1", "h2", "h3"}:
            content = normalize_space(" ".join(self._capture_chunks))
            if content:
                if self._capture_target == "nav" and short_label(content):
                    self.nav_labels.append(content)
                elif self._capture_target == "copy" and long_enough(content):
                    self.copy_blocks.append(content)
            self._capture_target = None
            self._capture_chunks = []


@dataclass
class PipelinePaths:
    raw_dir: Path
    normalized_dir: Path
    site_dir: Path


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def short_label(text: str) -> bool:
    return 1 <= len(text.split()) <= 6 and len(text) <= 50


def long_enough(text: str) -> bool:
    return len(text.split()) >= 4 and len(text) <= 600


def run_mirror(base_url: str, raw_dir: Path, delay: float, user_agent: str, dry_run: bool) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "wget",
        "--mirror",
        "--page-requisites",
        "--convert-links",
        "--no-parent",
        f"--wait={delay}",
        "--execute",
        "robots=on",
        "--adjust-extension",
        f"--user-agent={user_agent}",
        "--directory-prefix",
        str(raw_dir),
        base_url,
    ]

    if dry_run:
        print("[dry-run] mirror command:", " ".join(cmd))
        return

    print("Running mirror step...")
    subprocess.run(cmd, check=True)


def iter_html_files(directory: Path) -> Iterable[Path]:
    for path in directory.rglob("*.html"):
        if path.is_file():
            yield path


def transform(raw_dir: Path, normalized_dir: Path) -> Path:
    normalized_dir.mkdir(parents=True, exist_ok=True)

    nav_labels: set[str] = set()
    copy_blocks: set[str] = set()
    logos: set[str] = set()
    processed_files: list[str] = []

    for html_file in iter_html_files(raw_dir):
        parser = ReusableContentParser()
        parser.feed(html_file.read_text(encoding="utf-8", errors="ignore"))
        nav_labels.update(parser.nav_labels)
        copy_blocks.update(parser.copy_blocks)
        logos.update(parser.logos)
        processed_files.append(str(html_file.relative_to(raw_dir)))

    payload = {
        "source": str(raw_dir),
        "processed_html_files": sorted(processed_files),
        "navigation_labels": sorted(nav_labels),
        "copy_blocks": sorted(copy_blocks),
        "logo_candidates": sorted(logos),
    }

    json_out = normalized_dir / "reusable_content.json"
    json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    markdown_out = normalized_dir / "reusable_content.md"
    markdown_lines = ["# Reusable Content Extract", "", "## Navigation Labels"]
    markdown_lines.extend(f"- {item}" for item in payload["navigation_labels"] or ["(none)"])
    markdown_lines.extend(["", "## Logo Candidates"])
    markdown_lines.extend(f"- {item}" for item in payload["logo_candidates"] or ["(none)"])
    markdown_lines.extend(["", "## Copy Blocks"])
    markdown_lines.extend(f"- {item}" for item in payload["copy_blocks"] or ["(none)"])
    markdown_out.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    return json_out


def wire_to_site(normalized_json: Path, site_dir: Path, dry_run: bool) -> Path:
    site_dir.mkdir(parents=True, exist_ok=True)
    target = site_dir / "imported_content.json"

    if dry_run:
        print(f"[dry-run] would copy {normalized_json} -> {target}")
        return target

    shutil.copy2(normalized_json, target)
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mirror and normalize jpsit.com content for redesign work")
    parser.add_argument("--url", default=DEFAULT_URL, help="Base URL to mirror (default: https://jpsit.com)")
    parser.add_argument("--run-id", default="latest", help="Subdirectory name under import/raw and import/normalized")
    parser.add_argument("--import-root", default="import", help="Root folder for raw and normalized artifacts")
    parser.add_argument("--site-dir", default=str(DEFAULT_SITE_DIR), help="Site content directory to wire transformed output")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds")
    parser.add_argument("--user-agent", default="JPSIT-Importer/1.0 (+internal redesign)", help="Custom user agent")
    parser.add_argument("--skip-mirror", action="store_true", help="Skip network mirror step and reuse existing raw files")
    parser.add_argument("--skip-wire", action="store_true", help="Skip wiring normalized JSON into site source")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without mutating files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import_root = Path(args.import_root)
    paths = PipelinePaths(
        raw_dir=import_root / "raw" / args.run_id,
        normalized_dir=import_root / "normalized" / args.run_id,
        site_dir=Path(args.site_dir),
    )

    if not args.skip_mirror:
        run_mirror(args.url, paths.raw_dir, args.delay, args.user_agent, args.dry_run)
    elif not paths.raw_dir.exists():
        raise FileNotFoundError(f"Raw directory does not exist for --skip-mirror: {paths.raw_dir}")

    normalized_json = transform(paths.raw_dir, paths.normalized_dir)
    print(f"Normalized content written to {normalized_json}")

    if not args.skip_wire:
        target = wire_to_site(normalized_json, paths.site_dir, args.dry_run)
        print(f"Wired content to {target}")


if __name__ == "__main__":
    main()
