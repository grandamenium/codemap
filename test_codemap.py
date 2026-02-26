"""Tests for codemap.py - codebase map generator."""

import json
import subprocess
import sys
import textwrap
import tempfile
from pathlib import Path

import pytest

import codemap


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_project(tmp_path: Path, structure: dict) -> Path:
    """Create a mock project from a nested dict.

    Keys are file/dir names. Values are:
    - str: file content
    - dict: subdirectory
    """
    for name, content in structure.items():
        target = tmp_path / name
        if isinstance(content, dict):
            target.mkdir(parents=True, exist_ok=True)
            make_project(target, content)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    return tmp_path


# ── Smoke tests ───────────────────────────────────────────────────────────────

def test_import_no_crash():
    """Module imports cleanly."""
    assert hasattr(codemap, "generate_map")
    assert hasattr(codemap, "build_file_tree")
    assert hasattr(codemap, "find_entry_points")
    assert hasattr(codemap, "build_dep_graph")


def test_help_flag():
    result = subprocess.run(
        [sys.executable, "codemap.py", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert "directory" in result.stdout.lower()
    assert "entry" in result.stdout.lower() or "mermaid" in result.stdout.lower()


def test_no_args_uses_cwd():
    """Running with no args (uses '.') should not crash."""
    result = subprocess.run(
        [sys.executable, "codemap.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "# Codebase Map:" in result.stdout


# ── File tree tests ───────────────────────────────────────────────────────────

def test_file_tree_basic(tmp_path):
    make_project(tmp_path, {
        "main.py": "print('hello')",
        "utils.py": "# helpers",
        "sub": {
            "module.py": "x = 1",
        },
    })
    lines = codemap.build_file_tree(tmp_path)
    flat = "\n".join(lines)
    assert "main.py" in flat
    assert "utils.py" in flat
    assert "sub" in flat
    assert "module.py" in flat


def test_file_tree_skips_pycache(tmp_path):
    make_project(tmp_path, {
        "main.py": "pass",
        "__pycache__": {
            "main.cpython-311.pyc": "",
        },
    })
    lines = codemap.build_file_tree(tmp_path)
    flat = "\n".join(lines)
    assert "__pycache__" not in flat


def test_file_tree_skips_node_modules(tmp_path):
    make_project(tmp_path, {
        "index.js": "console.log(1)",
        "node_modules": {
            "lodash": {"index.js": "module.exports = {}"},
        },
    })
    lines = codemap.build_file_tree(tmp_path)
    flat = "\n".join(lines)
    assert "node_modules" not in flat


def test_file_tree_depth_limit(tmp_path):
    # Create 4 levels deep
    deep = tmp_path / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    (deep / "file.py").write_text("x = 1")

    lines = codemap.build_file_tree(tmp_path, max_depth=2)
    flat = "\n".join(lines)
    assert "file.py" not in flat
    assert "max depth" in flat.lower()


# ── Docstring / description tests ─────────────────────────────────────────────

def test_extract_python_docstring_clean():
    source = '"""My module docstring.\n\nMore details."""\nimport os\n'
    result = codemap.extract_python_docstring(source)
    assert result is not None
    assert "My module docstring" in result


def test_extract_python_docstring_regex_fallback():
    """Test regex fallback for truncated/broken source."""
    source = '"""My module.\n\nDoes things."""\n# truncated...'
    # Intentionally break by passing garbage after
    result = codemap.extract_python_docstring(source + "\ndef broken(")
    assert result is not None
    assert "My module" in result


def test_describe_file_python_docstring(tmp_path):
    f = tmp_path / "mymod.py"
    f.write_text('"""Handles user authentication."""\nimport os\n')
    desc = codemap.describe_file(f)
    assert desc == "Handles user authentication."


def test_describe_file_python_comment_fallback(tmp_path):
    f = tmp_path / "util.py"
    f.write_text("# Utility functions for string parsing\nimport re\n")
    desc = codemap.describe_file(f)
    assert desc == "Utility functions for string parsing"


def test_describe_file_js_comment(tmp_path):
    f = tmp_path / "app.js"
    f.write_text("// Express app entry point\nconst express = require('express');\n")
    desc = codemap.describe_file(f)
    assert desc == "Express app entry point"


def test_describe_file_package_json(tmp_path):
    f = tmp_path / "package.json"
    f.write_text(json.dumps({"name": "my-app", "description": "A cool app"}))
    desc = codemap.describe_file(f)
    assert "my-app" in desc
    assert "A cool app" in desc


def test_describe_file_binary(tmp_path):
    f = tmp_path / "image.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
    # PNG files are in SKIP_EXTENSIONS so describe_file won't see them normally
    # but if called directly, binary bytes cause UnicodeDecodeError
    desc = codemap.describe_file(f)
    assert desc == "[binary or unreadable]"


# ── Entry points tests ────────────────────────────────────────────────────────

def test_find_entry_points_main_py(tmp_path):
    make_project(tmp_path, {"main.py": "def main(): pass"})
    eps = codemap.find_entry_points(tmp_path)
    paths = [e["path"] for e in eps]
    assert "main.py" in paths


def test_find_entry_points_main_guard(tmp_path):
    make_project(tmp_path, {
        "tool.py": textwrap.dedent("""
            def run():
                pass

            if __name__ == "__main__":
                run()
        """),
    })
    eps = codemap.find_entry_points(tmp_path)
    paths = [e["path"] for e in eps]
    assert "tool.py" in paths


def test_find_entry_points_skips_skip_dirs(tmp_path):
    make_project(tmp_path, {
        "__pycache__": {"main.py": "pass"},
        "real_main.py": "if __name__ == '__main__': pass",
    })
    eps = codemap.find_entry_points(tmp_path)
    paths = [e["path"] for e in eps]
    assert "real_main.py" in paths
    assert not any("__pycache__" in p for p in paths)


def test_find_entry_points_package_json_bin(tmp_path):
    pkg = {"name": "my-cli", "bin": {"mycli": "./cli.js"}}
    make_project(tmp_path, {
        "package.json": json.dumps(pkg),
        "cli.js": "#!/usr/bin/env node\nconsole.log('hi');",
    })
    eps = codemap.find_entry_points(tmp_path)
    types = [e["type"] for e in eps]
    assert "cli-binary" in types or "node-config" in types


# ── Dependency graph tests ────────────────────────────────────────────────────

def test_build_dep_graph_python(tmp_path):
    make_project(tmp_path, {
        "app.py": "import os\nimport utils\nfrom models import User\n",
        "utils.py": "import re\n",
        "models.py": "from dataclasses import dataclass\n",
    })
    graph = codemap.build_dep_graph(tmp_path)
    assert "app.py" in graph
    # utils and models are local
    local = graph["app.py"]["local"]
    assert "utils" in local
    assert "models" in local
    # os is external
    external = graph["app.py"]["external"]
    assert "os" in external


def test_build_dep_graph_js(tmp_path):
    make_project(tmp_path, {
        "app.js": textwrap.dedent("""
            const express = require('express');
            import { helper } from './utils';
        """),
        "utils.js": "export function helper() {}",
    })
    graph = codemap.build_dep_graph(tmp_path)
    assert "app.js" in graph
    assert "./utils" in graph["app.js"]["local"]
    assert "express" in graph["app.js"]["external"]


def test_build_dep_graph_empty_dir(tmp_path):
    """Empty dir produces empty graph."""
    graph = codemap.build_dep_graph(tmp_path)
    assert graph == {}


# ── Full generate_map tests ───────────────────────────────────────────────────

def test_generate_map_produces_sections(tmp_path):
    make_project(tmp_path, {
        "main.py": '"""Entry point."""\nif __name__ == "__main__": pass\n',
        "utils.py": '"""Utility helpers."""\nimport os\n',
        "README.md": "# My Project\nDoes things.",
    })
    result = codemap.generate_map(str(tmp_path))
    assert "# Codebase Map:" in result
    assert "## File Tree" in result
    assert "## Entry Points" in result
    assert "## Module Descriptions" in result
    assert "## Dependency Graph" in result
    assert "main.py" in result
    assert "utils.py" in result


def test_generate_map_readme_excerpt(tmp_path):
    make_project(tmp_path, {
        "README.md": "# Cool Project\nThis does stuff.",
        "main.py": "pass",
    })
    result = codemap.generate_map(str(tmp_path))
    assert "README Excerpt" in result
    assert "Cool Project" in result


def test_generate_map_no_deps_flag(tmp_path):
    make_project(tmp_path, {"main.py": "import os\n"})
    result = codemap.generate_map(str(tmp_path), no_deps=True)
    assert "## Dependency Graph" not in result


def test_generate_map_writes_file(tmp_path):
    make_project(tmp_path, {"main.py": "pass"})
    out_file = tmp_path / "output.md"
    codemap.generate_map(str(tmp_path), output=str(out_file))
    assert out_file.exists()
    content = out_file.read_text()
    assert "# Codebase Map:" in content


def test_generate_map_mermaid(tmp_path):
    make_project(tmp_path, {
        "app.py": "import utils\n",
        "utils.py": "pass",
    })
    result = codemap.generate_map(str(tmp_path), mermaid=True)
    assert "mermaid" in result


# ── Error handling tests ──────────────────────────────────────────────────────

def test_missing_directory_raises():
    with pytest.raises(FileNotFoundError):
        codemap.generate_map("/nonexistent/path/xyz")


def test_file_not_directory_raises(tmp_path):
    f = tmp_path / "file.py"
    f.write_text("pass")
    with pytest.raises(NotADirectoryError):
        codemap.generate_map(str(f))


def test_cli_missing_dir():
    result = subprocess.run(
        [sys.executable, "codemap.py", "/nonexistent/path/xyz"],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error" in result.stderr
    assert "not found" in result.stderr.lower()


def test_cli_invalid_flag():
    result = subprocess.run(
        [sys.executable, "codemap.py", "--bad-flag"],
        capture_output=True, text=True
    )
    assert result.returncode != 0


def test_cli_max_depth_option(tmp_path):
    make_project(tmp_path, {
        "a": {"b": {"deep.py": "pass"}},
        "top.py": "pass",
    })
    result = subprocess.run(
        [sys.executable, "codemap.py", str(tmp_path), "--max-depth", "1"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "top.py" in result.stdout
    # deep.py should be cut off by depth limit
    assert "deep.py" not in result.stdout


def test_cli_output_file(tmp_path):
    out = tmp_path / "map.md"
    make_project(tmp_path, {"main.py": "pass"})
    result = subprocess.run(
        [sys.executable, "codemap.py", str(tmp_path), "--output", str(out)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert out.exists()
    assert "# Codebase Map:" in out.read_text()


# ── Stats tests ───────────────────────────────────────────────────────────────

def test_count_stats(tmp_path):
    make_project(tmp_path, {
        "a.py": "pass",
        "b.py": "pass",
        "c.js": "pass",
        "sub": {"d.py": "pass"},
    })
    stats = codemap._count_stats(tmp_path)
    assert stats["total_files"] == 4
    assert stats["total_dirs"] == 1
    ext_map = dict(stats["top_extensions"])
    assert ext_map.get(".py", 0) == 3
    assert ext_map.get(".js", 0) == 1
