"""
Universal AI Agent Harness Core.

Provides general-purpose environment diagnostics, safe execution,
and automated verification pipelines for AI agents and developers.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class HarnessContext:
    """Represents the workspace environment and runtime paths."""
    workspace_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3])
    python_executable: Path = field(default_factory=lambda: Path(sys.executable))
    python_version: str = field(default_factory=lambda: platform.python_version())
    os_platform: str = field(default_factory=lambda: platform.platform())
    is_venv: bool = field(default_factory=lambda: sys.prefix != sys.base_prefix)


def get_context() -> HarnessContext:
    """Returns the current runtime harness context."""
    return HarnessContext()


def doctor() -> Dict[str, Any]:
    """
    Performs comprehensive environment and dependency diagnostics.

    Returns:
        A dictionary containing diagnostic results, individual checks, and a formatted report.
    """
    ctx = get_context()
    checks: List[Dict[str, Any]] = []

    # 1. Python Environment Check
    in_venv = ctx.is_venv
    checks.append({
        "name": "Virtual Environment",
        "passed": in_venv,
        "detail": f"Path: {sys.prefix}" if in_venv else "Running outside a virtual environment!",
    })

    # 2. Python Version Check (>= 3.10)
    version_info = sys.version_info
    ver_ok = (version_info.major == 3 and version_info.minor >= 10)
    checks.append({
        "name": "Python Version (>= 3.10)",
        "passed": ver_ok,
        "detail": f"Python {ctx.python_version} ({ctx.os_platform})",
    })

    # 3. Critical Package Availability
    required_packages = ["pydantic", "finos", "rune", "pytest"]
    for pkg in required_packages:
        try:
            __import__(pkg)
            checks.append({
                "name": f"Package '{pkg}'",
                "passed": True,
                "detail": "Installed and importable",
            })
        except ImportError as e:
            checks.append({
                "name": f"Package '{pkg}'",
                "passed": False,
                "detail": f"Import failed: {e}",
            })

    # 4. cdm_compat Layer Health
    try:
        import cdm_compat
        patched = cdm_compat.is_patched()
        checks.append({
            "name": "cdm_compat Compatibility Layer",
            "passed": True,
            "detail": f"Active and initialized (is_patched={patched})",
        })
    except Exception as e:
        checks.append({
            "name": "cdm_compat Compatibility Layer",
            "passed": False,
            "detail": f"Failed to initialize: {e}",
        })

    all_passed = all(c["passed"] for c in checks)

    # Build human-readable formatted report
    lines = [
        "=" * 60,
        " AI AGENT HARNESS : ENVIRONMENT DOCTOR REPORT",
        "=" * 60,
        f"Workspace Root: {ctx.workspace_root}",
        f"Python Binary : {ctx.python_executable}",
        f"System OS     : {ctx.os_platform}",
        "-" * 60,
    ]
    for c in checks:
        status = "[ OK ]" if c["passed"] else "[FAIL]"
        lines.append(f"{status} {c['name']:<35} -> {c['detail']}")
    lines.append("-" * 60)
    lines.append(f"Overall Status: {'HEALTHY - All checks passed' if all_passed else 'WARNING - Some checks failed'}")
    lines.append("=" * 60)

    report_str = "\n".join(lines)

    return {
        "ok": all_passed,
        "checks": checks,
        "report": report_str,
        "context": ctx,
    }


def verify(
    tests_path: str = "tests",
    extra_args: Optional[List[str]] = None,
    cwd: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Runs the automated test & verification suite using pytest.

    Parameters:
        tests_path: Relative or absolute path to tests directory.
        extra_args: Additional arguments to pass to pytest.
        cwd: Working directory.

    Returns:
        A dictionary containing exit code, duration, stdout, and success boolean.
    """
    ctx = get_context()
    run_cwd = cwd or ctx.workspace_root
    args = [str(ctx.python_executable), "-m", "pytest", tests_path]
    if extra_args:
        args.extend(extra_args)

    start_time = time.time()
    result = subprocess.run(
        args,
        cwd=str(run_cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.time() - start_time
    passed = (result.returncode == 0)

    lines = [
        "=" * 60,
        " AI AGENT HARNESS : VERIFICATION REPORT",
        "=" * 60,
        f"Test Command : {' '.join(args)}",
        f"Elapsed Time : {elapsed:.2f}s",
        f"Exit Code    : {result.returncode}",
        f"Status       : {'PASSED [OK]' if passed else 'FAILED [ERROR]'}",
        "-" * 60,
        result.stdout.strip() if result.stdout else "(No stdout)",
    ]
    if result.stderr:
        lines.extend(["- STDERR -", result.stderr.strip()])
    lines.append("=" * 60)

    report_str = "\n".join(lines)

    return {
        "ok": passed,
        "exit_code": result.returncode,
        "elapsed_seconds": elapsed,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "report": report_str,
    }


def exec_code(code: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Safely executes a Python snippet in a subprocess with cdm_compat pre-imported.

    Parameters:
        code: Python code string to execute.
        timeout: Maximum execution time in seconds.

    Returns:
        A dictionary containing returncode, stdout, stderr, and elapsed time.
    """
    ctx = get_context()
    bootstrap_code = f"import cdm_compat\n{code}"

    env = os.environ.copy()
    src_dir = str(ctx.workspace_root / "src")
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pp}" if existing_pp else src_dir

    start_time = time.time()
    try:
        result = subprocess.run(
            [str(ctx.python_executable), "-c", bootstrap_code],
            cwd=str(ctx.workspace_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        elapsed = time.time() - start_time
        return {
            "ok": (result.returncode == 0),
            "exit_code": result.returncode,
            "elapsed_seconds": elapsed,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - start_time
        return {
            "ok": False,
            "exit_code": -1,
            "elapsed_seconds": elapsed,
            "stdout": e.stdout or "",
            "stderr": f"Execution timed out after {timeout} seconds.",
        }
