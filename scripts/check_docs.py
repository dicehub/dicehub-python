"""Check Markdown frontmatter and relative file links without network access."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^```.*?^```[^\n]*$", re.MULTILINE | re.DOTALL)


def main() -> None:
    paths = sorted({*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md"), *ROOT.glob("examples/**/*.md")})
    errors: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        if path.is_relative_to(ROOT / "docs"):
            parts = text.split("---", 2)
            if len(parts) != 3 or parts[0].strip():
                errors.append(f"{relative}: missing YAML frontmatter")
            else:
                for field in ("title", "description", "read_when"):
                    if not re.search(rf"^{field}:\s*\S?", parts[1], re.MULTILINE):
                        errors.append(f"{relative}: missing {field} frontmatter")
        for link in LINK.findall(FENCE.sub("", text)):
            target = unquote(link.strip("<>").split("#", 1)[0])
            if not target or ":" in target:
                continue
            if not (path.parent / target).exists():
                errors.append(f"{relative}: missing link target {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked frontmatter and relative file links in {len(paths)} Markdown files.")


if __name__ == "__main__":
    main()
