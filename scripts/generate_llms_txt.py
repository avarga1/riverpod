#!/usr/bin/env python3
"""
Generate llms.txt — a single flat markdown file of all Riverpod docs,
optimised for LLM context windows.

Output: website/static/llms.txt
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DOCS_ROOT = REPO_ROOT / "website" / "docs"
OUTPUT = REPO_ROOT / "website" / "static" / "llms.txt"

# Ordered sections — controls the narrative flow in the output file.
# Each entry is a glob pattern relative to DOCS_ROOT.
SECTIONS = [
    ("Introduction", ["introduction/*.mdx"]),
    ("Core Concepts", ["concepts2/providers.mdx", "concepts2/refs.mdx",
                       "concepts2/consumers.mdx", "concepts2/auto_dispose.mdx",
                       "concepts2/family.mdx", "concepts2/overrides.mdx",
                       "concepts2/scoping.mdx", "concepts2/containers.mdx",
                       "concepts2/mutations.mdx", "concepts2/retry.mdx",
                       "concepts2/offline.mdx", "concepts2/observers.mdx"]),
    ("How-To Guides", ["how_to/*.mdx"]),
    ("Tutorials", ["tutorials/*.mdx"]),
    ("FAQ & Do's / Don'ts", ["root/faq.mdx", "root/do_dont.mdx"]),
    ("Concepts (legacy/supplemental)", ["concepts/*.mdx"]),
    ("Migration", ["3.0_migration.mdx", "migration/*.mdx"]),
    ("What's New", ["whats_new.mdx"]),
]


def extract_title(content: str, path: Path) -> str:
    m = re.search(r"^---\s*\ntitle:\s*(.+?)\s*\n", content, re.MULTILINE)
    if m:
        return m.group(1).strip('"\'')
    return path.stem.replace("_", " ").title()


def clean_mdx(content: str) -> str:
    # Strip YAML frontmatter
    content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)

    # Strip import/export statements (may span multiple lines with { ... })
    content = re.sub(r"^(import|export)\s+.*?;\s*\n", "", content, flags=re.MULTILINE | re.DOTALL)
    # Catch any remaining multi-line imports not caught above
    content = re.sub(r"^import\s*\{[^}]*\}\s*from\s*['\"][^'\"]*['\"];\s*\n", "", content, flags=re.MULTILINE | re.DOTALL)

    # Replace <AutoSnippet .../> and <AutoSnippet ...></AutoSnippet> with a note
    content = re.sub(
        r"<AutoSnippet[^>]*/>\s*", "_[code snippet]_\n", content
    )
    content = re.sub(
        r"<AutoSnippet[^>]*>.*?</AutoSnippet>\s*",
        "_[code snippet]_\n",
        content,
        flags=re.DOTALL,
    )

    # Replace <Link documentID="foo/bar" /> with the doc name
    content = re.sub(
        r'<Link\s+documentID=["\']([^"\']+)["\']\s*/?>',
        lambda m: m.group(1).split("/")[-1].replace("_", " ").title(),
        content,
    )

    # Strip remaining JSX block tags (opening + closing), keep inner text
    content = re.sub(r"<TabItem[^>]*>", "", content)
    content = re.sub(r"</TabItem>", "", content)
    content = re.sub(r"<Tabs[^>]*>", "", content)
    content = re.sub(r"</Tabs>", "", content)
    content = re.sub(r"<Legend[^>]*/?>", "", content)
    content = re.sub(r"</Legend>", "", content)
    content = re.sub(r"<iframe[^>]*/?>.*?</iframe>", "", content, flags=re.DOTALL)
    content = re.sub(r"<iframe[^>]*/?>", "", content)
    content = re.sub(r"<div[^>]*>", "", content)
    content = re.sub(r"</div>", "", content)

    # Strip leftover self-closing JSX tags: <Foo /> or <Foo/>
    content = re.sub(r"<[A-Z][A-Za-z]*[^>]*/>\s*", "", content)
    # Strip leftover block JSX open/close tags
    content = re.sub(r"</?[A-Z][A-Za-z]*[^>]*>\s*", "", content)

    # Collapse 3+ blank lines to 2
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


def resolve_paths(patterns: list[str]) -> list[Path]:
    paths = []
    for pattern in patterns:
        matched = sorted(DOCS_ROOT.glob(pattern))
        paths.extend(matched)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def build_llms_txt() -> str:
    lines = [
        "# Riverpod — LLM Documentation",
        "",
        "> Auto-generated from the Riverpod documentation source.",
        "> Use this file as context when asking an LLM about Riverpod.",
        "> Source: https://riverpod.dev | https://github.com/rrousselGit/riverpod",
        "",
        "---",
        "",
    ]

    for section_title, patterns in SECTIONS:
        paths = resolve_paths(patterns)
        if not paths:
            continue

        lines.append(f"# {section_title}")
        lines.append("")

        for path in paths:
            try:
                raw = path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"Warning: could not read {path}: {e}", file=sys.stderr)
                continue

            title = extract_title(raw, path)
            cleaned = clean_mdx(raw)

            if not cleaned.strip():
                continue

            lines.append(f"## {title}")
            lines.append("")
            lines.append(cleaned)
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = build_llms_txt()
    OUTPUT.write_text(result, encoding="utf-8")
    size_kb = OUTPUT.stat().st_size / 1024
    doc_count = result.count("\n## ")
    print(f"Generated {OUTPUT.relative_to(REPO_ROOT)}")
    print(f"  {doc_count} sections | {size_kb:.1f} KB")
