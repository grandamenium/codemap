# Review: codemap

## Idea
- **Name**: codemap
- **Problem**: codebase map generator - scans a project directory and outputs structured markdown with file tree, module
  descriptions, entry points and dependency graph, designed for AI coding agents to quickly understand unfamiliar repos
- **Solution**: codebase map generator - scans a project directory and outputs structured markdown with file tree, module
  descriptions, entry points and dependency graph, designed for AI coding agents to quickly understand unfamiliar repos
- **Content Angle**: 
- **Source**: manual

## Build Result
- **Success**: True
- **Attempts**: 1/3
- **Cost**: $1.05
- **Duration**: 257.4s
- **Files created**: 8

### Files
.github/workflows/ci.yml
README.md
__pycache__/codemap.cpython-312.pyc
__pycache__/test_codemap.cpython-312-pytest-9.0.2.pyc
codemap.py
idea.json
requirements.txt
test_codemap.py

## Test Result
- **Overall**: PASS
- **Passed**: 6/7
- **Failed**: 0
- **Errors**: 0

### Test Cases
[PASS] syntax_check - All 2 Python files have valid syntax
[PASS] readme_exists - README.md exists (2696 chars)
[PASS] secret_scan - No hardcoded secrets detected in 2 file(s)
[PASS] import_check - Module 'codemap' imports successfully
[PASS] help_flag - --help exits 0 with usage information
[PASS] no_args_behavior - Tool handles no-args gracefully (exit code 0)
[ERROR] tool_own_pytest - pytest not installed in tool's venv, skipping

## Content
- **Video script**: Generated
- **Twitter thread**: Generated
- **Skool post**: Generated

## Action
To publish: `./run.sh --publish /Users/jamesgoldbach/clawd/projects/tool-factory/tools/2026-02-26-codemap`
