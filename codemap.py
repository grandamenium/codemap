#!/usr/bin/env python3
"""
codemap.py - Codebase Map Generator

Scans a project directory and outputs structured markdown with file tree,
module descriptions, entry points, and dependency graph.

Designed for AI coding agents to quickly understand unfamiliar repos.
"""

import ast
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".env", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    "htmlcov", ".eggs", ".idea", ".vscode", "coverage",
    ".ruff_cache", ".DS_Store", "__pypackages__", "site-packages",
    "target", "vendor", ".nx",
}

SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".webp", ".bmp", ".tiff",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".pdf", ".docx", ".xlsx",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".db", ".sqlite", ".sqlite3",
    ".wasm",
}

ENTRY_POINT_NAMES = {
    "main.py", "__main__.py", "app.py", "run.py", "cli.py", "manage.py",
    "server.py", "wsgi.py", "asgi.py", "index.js", "index.ts",
    "app.js", "server.js", "main.js", "main.ts", "main.go", "main.rs",
    "Makefile", "Dockerfile",
}

LANG_COMMENT = {
    ".py": "#", ".js": "//", ".ts": "//", ".jsx": "//", ".tsx": "//",
    ".go": "//", ".rs": "//", ".java": "//", ".kt": "//",
    ".c": "//", ".cpp": "//", ".h": "//",
    ".sh": "#", ".bash": "#", ".zsh": "#",
    ".rb": "#", ".pl": "#", ".lua": "--", ".hs": "--",
    ".r": "#", ".R": "#",
}

# ── File tree ─────────────────────────────────────────────────────────────────

def _should_skip(name: str, path: Path) -> bool:
    if name in SKIP_DIRS and path.is_dir():
        return True
    if name.startswith(".") and path.is_dir() and name not in {".github"}:
        return True
    if path.is_file() and path.suffix in SKIP_EXTENSIONS:
        return True
    if path.is_file() and name.endswith((".min.js", ".min.css")):
        return True
    return False


def build_file_tree(
    root: Path,
    prefix: str = "",
    max_depth: int = 6,
    current_depth: int = 0,
    max_files: int = 300,
    _counter: Optional[list] = None,
) -> list[str]:
    """Return lines of an ASCII file tree."""
    if _counter is None:
        _counter = [0]

    if current_depth > max_depth:
        return [f"{prefix}... (max depth reached)"]

    lines: list[str] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return [f"{prefix}[permission denied]"]

    entries = [e for e in entries if not _should_skip(e.name, e)]
    dirs = [e for e in entries if e.is_dir()]
    files = [e for e in entries if e.is_file()]
    all_entries = dirs + files

    for i, entry in enumerate(all_entries):
        if _counter[0] >= max_files:
            lines.append(f"{prefix}... ({len(all_entries) - i} more items truncated)")
            break

        is_last = i == len(all_entries) - 1
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "

        lines.append(f"{prefix}{connector}{entry.name}")
        _counter[0] += 1

        if entry.is_dir():
            sub = build_file_tree(
                entry,
                prefix=prefix + extension,
                max_depth=max_depth,
                current_depth=current_depth + 1,
                max_files=max_files,
                _counter=_counter,
            )
            lines.extend(sub)

    return lines


# ── Module descriptions ───────────────────────────────────────────────────────

def _read_safe(path: Path, max_bytes: int = 8192) -> Optional[str]:
    """Read file text, return None on error or binary."""
    try:
        with open(path, "r", encoding="utf-8", errors="strict") as f:
            return f.read(max_bytes)
    except (UnicodeDecodeError, PermissionError, OSError):
        return None


def extract_python_docstring(source: str) -> Optional[str]:
    """Extract module-level docstring from Python source.

    Uses AST for full parse; falls back to regex for truncated/partial files.
    """
    try:
        tree = ast.parse(source)
        return ast.get_docstring(tree)
    except SyntaxError:
        pass

    # Regex fallback: match triple-quoted string at start of file (skipping
    # shebang lines, encoding declarations, and blank lines)
    stripped = source.lstrip()
    # Skip shebang / encoding comment lines
    while stripped.startswith("#"):
        stripped = stripped[stripped.find("\n") + 1:].lstrip()

    m = re.match(r'"""(.*?)"""', stripped, re.DOTALL)
    if not m:
        m = re.match(r"'''(.*?)'''", stripped, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def extract_first_comment(source: str, comment_char: str) -> Optional[str]:
    """Return first meaningful comment line from source."""
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(comment_char):
            text = stripped.lstrip(comment_char).strip()
            if text and not text.startswith("!"):  # skip shebangs
                return text
    return None


def describe_file(path: Path) -> Optional[str]:
    """Return a one-line description for a source file."""
    suffix = path.suffix.lower()
    source = _read_safe(path)
    if source is None:
        return "[binary or unreadable]"

    # Python: prefer docstring
    if suffix == ".py":
        doc = extract_python_docstring(source)
        if doc:
            return doc.splitlines()[0].strip()

    # For known comment styles, look for first comment
    comment_char = LANG_COMMENT.get(suffix)
    if comment_char:
        comment = extract_first_comment(source, comment_char)
        if comment:
            return comment

    # JSON / TOML: extract name + description fields
    if path.name in {"package.json", "pyproject.toml", "Cargo.toml"}:
        try:
            if path.name == "package.json":
                data = json.loads(source)
                parts = []
                if "name" in data:
                    parts.append(data["name"])
                if "description" in data:
                    parts.append(data["description"])
                if parts:
                    return " - ".join(parts)
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def collect_module_descriptions(root: Path, max_files: int = 200) -> dict[str, str]:
    """Walk root and return {rel_path: description} for describable files."""
    descriptions: dict[str, str] = {}
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if not _should_skip(d, Path(dirpath) / d)
        ]
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if _should_skip(fname, fpath):
                continue
            if count >= max_files:
                break
            rel = str(fpath.relative_to(root))
            desc = describe_file(fpath)
            if desc:
                descriptions[rel] = desc
            count += 1

    return descriptions


# ── Entry points ──────────────────────────────────────────────────────────────

def _has_python_main_guard(source: str) -> bool:
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"
                ):
                    return True
    except SyntaxError:
        pass
    return False


def find_entry_points(root: Path) -> list[dict]:
    """Return list of {path, type, reason} for detected entry points."""
    entries: list[dict] = []
    seen: set[str] = set()

    def add(path: Path, kind: str, reason: str):
        rel = str(path.relative_to(root))
        if rel not in seen:
            seen.add(rel)
            entries.append({"path": rel, "type": kind, "reason": reason})

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not _should_skip(d, Path(dirpath) / d)
        ]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel = fpath.relative_to(root)

            # Named entry points
            if fname in ENTRY_POINT_NAMES:
                kind = _classify_entry(fname)
                add(fpath, kind, f"canonical entry-point filename `{fname}`")

            # Python main guard
            if fname.endswith(".py"):
                source = _read_safe(fpath)
                if source and _has_python_main_guard(source):
                    add(fpath, "python-script", "contains `if __name__ == '__main__'`")

            # package.json main field
            if fname == "package.json":
                source = _read_safe(fpath)
                if source:
                    try:
                        data = json.loads(source)
                        if "main" in data:
                            main_path = fpath.parent / data["main"]
                            if main_path.exists():
                                add(main_path, "node-main", f"referenced as `main` in {rel}")
                            else:
                                add(fpath, "node-config", f"`main` field: {data['main']}")
                        if "bin" in data and isinstance(data["bin"], dict):
                            for bin_name, bin_path in data["bin"].items():
                                bp = fpath.parent / bin_path
                                add(bp if bp.exists() else fpath, "cli-binary", f"npm bin `{bin_name}`")
                    except (json.JSONDecodeError, KeyError):
                        pass

    return sorted(entries, key=lambda e: (e["type"], e["path"]))


def _classify_entry(fname: str) -> str:
    name_lower = fname.lower()
    if name_lower in {"dockerfile", "docker-compose.yml", "docker-compose.yaml"}:
        return "docker"
    if name_lower == "makefile":
        return "build"
    if name_lower in {"setup.py", "pyproject.toml", "setup.cfg"}:
        return "package"
    if name_lower in {"wsgi.py", "asgi.py"}:
        return "web-server"
    if name_lower == "manage.py":
        return "django"
    return "python-main"


# ── Dependency graph ──────────────────────────────────────────────────────────

def _collect_python_imports(source: str) -> list[str]:
    """Return list of top-level module names imported in Python source."""
    modules: list[str] = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    modules.append(node.module.split(".")[0])
                elif node.level and node.level > 0:
                    modules.append("." * node.level + (node.module or ""))
    except SyntaxError:
        pass
    return modules


def _collect_js_imports(source: str) -> list[str]:
    """Return list of import/require paths from JS/TS source."""
    modules: list[str] = []
    patterns = [
        r'import\s+.*?\s+from\s+["\']([^"\']+)["\']',
        r'require\s*\(\s*["\']([^"\']+)["\']\s*\)',
        r'import\s*\(\s*["\']([^"\']+)["\']\s*\)',
    ]
    for pat in patterns:
        for m in re.finditer(pat, source):
            modules.append(m.group(1))
    return modules


def build_dep_graph(root: Path) -> dict[str, dict]:
    """
    Build dependency info for Python and JS/TS files.
    Returns {rel_path: {"local": [...], "external": [...]}}.
    """
    # Collect all local Python module names (for resolving local vs external)
    local_py_modules: set[str] = set()
    for fpath in root.rglob("*.py"):
        rel = fpath.relative_to(root)
        parts = rel.parts
        # Module name is the stem of top-level or package name
        if len(parts) == 1:
            local_py_modules.add(fpath.stem)
        elif len(parts) > 1:
            local_py_modules.add(parts[0])

    graph: dict[str, dict] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not _should_skip(d, Path(dirpath) / d)
        ]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            suffix = fpath.suffix.lower()
            rel = str(fpath.relative_to(root))
            source = _read_safe(fpath)
            if source is None:
                continue

            if suffix == ".py":
                imports = _collect_python_imports(source)
                local = []
                external = []
                for imp in set(imports):
                    if imp.startswith(".") or imp in local_py_modules:
                        local.append(imp)
                    else:
                        external.append(imp)
                if local or external:
                    graph[rel] = {
                        "local": sorted(local),
                        "external": sorted(external),
                    }

            elif suffix in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}:
                imports = _collect_js_imports(source)
                local = sorted({i for i in imports if i.startswith(".")})
                external = sorted({i for i in imports if not i.startswith(".")})
                if local or external:
                    graph[rel] = {"local": local, "external": external}

    return graph


def _build_mermaid_graph(graph: dict[str, dict]) -> list[str]:
    """Generate Mermaid flowchart lines from dep graph (Python only, local deps)."""
    lines = ["```mermaid", "graph TD"]
    node_ids: dict[str, str] = {}

    def node_id(path: str) -> str:
        if path not in node_ids:
            node_ids[path] = f"N{len(node_ids)}"
        return node_ids[path]

    edges: set[tuple[str, str]] = set()
    for src, deps in graph.items():
        for local in deps.get("local", []):
            edges.add((src, local))

    if not edges:
        return []

    for src, tgt in sorted(edges):
        src_id = node_id(src)
        tgt_id = node_id(tgt)
        src_label = Path(src).stem
        tgt_label = tgt.lstrip(".") or tgt
        lines.append(f'    {src_id}["{src_label}"] --> {tgt_id}["{tgt_label}"]')

    lines.append("```")
    return lines


# ── Markdown output ───────────────────────────────────────────────────────────

def _count_stats(root: Path) -> dict:
    counts: dict[str, int] = defaultdict(int)
    total_files = 0
    total_dirs = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not _should_skip(d, Path(dirpath) / d)
        ]
        total_dirs += len(dirnames)
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if not _should_skip(fname, fpath):
                counts[fpath.suffix.lower() or "(no ext)"] += 1
                total_files += 1

    top_exts = sorted(counts.items(), key=lambda x: -x[1])[:8]
    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "top_extensions": top_exts,
    }


def generate_map(
    directory: str,
    output: Optional[str] = None,
    max_depth: int = 6,
    max_files: int = 300,
    mermaid: bool = False,
    no_deps: bool = False,
) -> str:
    """Generate the full codebase map and return as markdown string."""
    root = Path(directory).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    project_name = root.name
    lines: list[str] = []

    # Header
    lines.append(f"# Codebase Map: `{project_name}`")
    lines.append("")
    lines.append(f"> Generated by codemap.py | Path: `{root}`")
    lines.append("")

    # Overview / stats
    lines.append("## Overview")
    lines.append("")
    stats = _count_stats(root)
    lines.append(f"- **Files**: {stats['total_files']}")
    lines.append(f"- **Directories**: {stats['total_dirs']}")
    if stats["top_extensions"]:
        ext_str = ", ".join(f"`{e}` ({n})" for e, n in stats["top_extensions"])
        lines.append(f"- **Top file types**: {ext_str}")
    lines.append("")

    # README snippet
    readme_path = None
    for name in ("README.md", "README.rst", "README.txt", "README"):
        candidate = root / name
        if candidate.exists():
            readme_path = candidate
            break

    if readme_path:
        lines.append("### README Excerpt")
        lines.append("")
        content = _read_safe(readme_path, max_bytes=1200) or ""
        excerpt = "\n".join(content.splitlines()[:20])
        lines.append("```")
        lines.append(excerpt.strip())
        lines.append("```")
        lines.append("")

    # File tree
    lines.append("## File Tree")
    lines.append("")
    lines.append(f"```")
    lines.append(project_name + "/")
    tree_lines = build_file_tree(root, max_depth=max_depth, max_files=max_files)
    lines.extend(tree_lines)
    lines.append("```")
    lines.append("")

    # Entry points
    lines.append("## Entry Points")
    lines.append("")
    entry_points = find_entry_points(root)
    if entry_points:
        for ep in entry_points:
            lines.append(f"- **`{ep['path']}`** `[{ep['type']}]` - {ep['reason']}")
    else:
        lines.append("_No entry points detected._")
    lines.append("")

    # Module descriptions
    lines.append("## Module Descriptions")
    lines.append("")
    descriptions = collect_module_descriptions(root, max_files=max_files)
    if descriptions:
        # Group by directory
        by_dir: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for rel, desc in sorted(descriptions.items()):
            parent = str(Path(rel).parent)
            by_dir[parent].append((rel, desc))

        for parent in sorted(by_dir.keys()):
            dir_label = parent if parent != "." else project_name + "/"
            lines.append(f"### `{dir_label}`")
            lines.append("")
            for rel, desc in by_dir[parent]:
                fname = Path(rel).name
                lines.append(f"- **`{fname}`** - {desc}")
            lines.append("")
    else:
        lines.append("_No module descriptions found._")
        lines.append("")

    # Dependency graph
    if not no_deps:
        lines.append("## Dependency Graph")
        lines.append("")
        graph = build_dep_graph(root)
        if graph:
            # External dependencies summary
            all_external: dict[str, int] = defaultdict(int)
            for deps in graph.values():
                for ext in deps.get("external", []):
                    all_external[ext] += 1

            if all_external:
                lines.append("### External Dependencies")
                lines.append("")
                top = sorted(all_external.items(), key=lambda x: -x[1])[:20]
                for pkg, count in top:
                    lines.append(f"- `{pkg}` (imported in {count} file{'s' if count > 1 else ''})")
                lines.append("")

            # Local dependency map
            lines.append("### Local Module Dependencies")
            lines.append("")
            has_local = False
            for rel in sorted(graph.keys()):
                local = graph[rel].get("local", [])
                if local:
                    has_local = True
                    deps_str = ", ".join(f"`{d}`" for d in local)
                    lines.append(f"- **`{rel}`** imports: {deps_str}")
            if not has_local:
                lines.append("_No local dependencies detected._")
            lines.append("")

            # Mermaid diagram (optional)
            if mermaid:
                mermaid_lines = _build_mermaid_graph(graph)
                if mermaid_lines:
                    lines.append("### Dependency Diagram (Mermaid)")
                    lines.append("")
                    lines.extend(mermaid_lines)
                    lines.append("")
        else:
            lines.append("_No dependency information extracted._")
            lines.append("")

    result = "\n".join(lines)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result, encoding="utf-8")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="codemap",
        description=(
            "Generate a structured markdown map of a codebase for AI coding agents.\n"
            "Outputs file tree, module descriptions, entry points, and dependency graph."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python codemap.py .
  python codemap.py /path/to/project --output CODEBASE_MAP.md
  python codemap.py . --max-depth 4 --mermaid
  python codemap.py . --no-deps --output map.md
        """,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Project directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write output to FILE instead of stdout",
    )
    parser.add_argument(
        "--max-depth", "-d",
        type=int,
        default=6,
        metavar="N",
        help="Maximum directory depth for file tree (default: 6)",
    )
    parser.add_argument(
        "--max-files", "-n",
        type=int,
        default=300,
        metavar="N",
        help="Maximum files to include in tree and descriptions (default: 300)",
    )
    parser.add_argument(
        "--mermaid",
        action="store_true",
        help="Include Mermaid diagram in dependency graph section",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="Skip dependency graph analysis",
    )

    args = parser.parse_args()

    try:
        result = generate_map(
            directory=args.directory,
            output=args.output,
            max_depth=args.max_depth,
            max_files=args.max_files,
            mermaid=args.mermaid,
            no_deps=args.no_deps,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except NotADirectoryError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"Error: permission denied - {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)

    if args.output:
        print(f"Map written to: {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
