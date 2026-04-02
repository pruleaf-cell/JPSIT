# JPSIT

## Repeatable import process

Use `scripts/mirror_jpsit.py` to run a three-stage import pipeline for redesign work:

1. **Mirror** content from `jpsit.com` into `import/raw/<run-id>/`.
2. **Transform** mirrored HTML and extract reusable data into `import/normalized/<run-id>/`.
3. **Wire** transformed output into the site source tree (`site/src/content/imported_content.json` by default).

### Requirements

- Python 3.10+
- `wget` available on `PATH`

### Quick start

```bash
python3 scripts/mirror_jpsit.py --run-id 2026-04-02
```

### Operator flags

```bash
python3 scripts/mirror_jpsit.py \
  --url https://jpsit.com \
  --run-id latest \
  --import-root import \
  --site-dir site/src/content \
  --delay 1.0 \
  --user-agent "JPSIT-Importer/1.0 (+internal redesign)" \
  --skip-mirror \
  --skip-wire \
  --dry-run
```

- `--url`: Base URL to mirror.
- `--run-id`: Namespaced run folder under `import/raw/` and `import/normalized/`.
- `--import-root`: Root for import artifacts.
- `--site-dir`: Destination folder used to wire normalized content into site source.
- `--delay`: Request delay (seconds) for polite crawling.
- `--user-agent`: Explicit crawler identity string.
- `--skip-mirror`: Reuse existing `import/raw/<run-id>/` without making network requests.
- `--skip-wire`: Stop after generating normalized output.
- `--dry-run`: Print mirror/wire actions without mutating files.

## Legal and robots constraints

Before any import run, operators must:

1. Verify terms of service and copyright permissions for `jpsit.com` content.
2. Respect `robots.txt`; this pipeline enforces robots handling via `wget --execute robots=on`.
3. Use conservative request pacing (`--delay`) and an identifiable `--user-agent`.
4. Use imported output only for internal redesign and content modeling unless explicit publication rights are granted.

## Output layout

- `import/raw/<run-id>/`: Unmodified mirrored pages/assets.
- `import/normalized/<run-id>/reusable_content.json`: Extracted structured content (logo candidates, copy blocks, navigation labels).
- `import/normalized/<run-id>/reusable_content.md`: Human-readable extract summary.
- `site/src/content/imported_content.json`: Wired content consumed by redesign source files.
