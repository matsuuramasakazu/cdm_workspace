# AI Agent Operational Rules & Workspace Guide (`cdm-workspace`)

Welcome to `cdm-workspace`. This document defines the standard operational rules, environment constraints, and best practices for AI Agents (Antigravity, Cursor, Copilot, SWE-agent, etc.) working within this workspace.

---

## 1. ⚙️ Environment & Python Runtime

* **Operating System**: Windows (PowerShell / `pwsh` default).
* **Python Interpreter**: Always use the local virtual environment interpreter:
  * **Windows**: `.venv\Scripts\python.exe`
  * **Tests**: `.venv\Scripts\python.exe -m pytest`
  * ⚠️ *Do NOT invoke bare `python` or `poetry` directly, as they may resolve to global non-project environments.*

---

## 2. 🛡️ CDM Model & Runtime Compatibility Rules

1. **Mandatory Compatibility Layer Import**:
   * Whenever importing or utilizing `finos.cdm.*` models, you **MUST** import `cdm_compat` before any `finos.cdm` imports:
     ```python
     import cdm_compat  # REQUIRED FIRST: Patches Rune runtime & repairs Pydantic schemas
     from finos.cdm.event.common.Trade import Trade
     ```
   * *Rationale*: `finos-cdm` 7.1.0 and `rune-runtime` contain circular import issues in `finos._bundle` and schema loss in complex types. `cdm_compat` automatically resolves these on import.

2. **Top-Level Package Namespace**:
   * The package namespace is **`finos.cdm`**, NOT `cdm`.
   * Example: `from finos.cdm.event.common.TradeState import TradeState`

3. **Rosetta Generated Functions**:
   * Certain generated functions in `finos.cdm.*.functions` (such as `CalculateReset.py`) contain invalid Python 3.12+ syntax (`:=` in list comprehension iterables).
   * Prefer constructing and validating Pydantic models directly rather than calling broken Rosetta function files.

---

## 3. 🚀 Universal Agent Harness (Quick Reference)

This repository provides a dedicated **Agent Harness** (`cdm_workspace.harness`) to perform rapid diagnostics, code execution, inspection, and verification without boilerplate:

| Task | Command | Description |
| :--- | :--- | :--- |
| **Environment Check** | `.venv\Scripts\python.exe -m cdm_workspace.harness doctor` | Diagnoses venv, dependencies, and `cdm_compat` status in < 1s. |
| **Automated Verification** | `.venv\Scripts\python.exe -m cdm_workspace.harness verify` | Runs pytest suite and returns a structured health report. |
| **Safe Code Execution** | `.venv\Scripts\python.exe -m cdm_workspace.harness exec "<code>"` | Safely runs a Python snippet with `cdm_compat` pre-initialized. |
| **Model Inspection** | `.venv\Scripts\python.exe -m cdm_workspace.harness inspect <ModelName>` | Inspects fields, types, and schema of any CDM class instantly. |
| **Generate Sample IRS** | `.venv\Scripts\python.exe -m cdm_workspace.harness irs` | Builds Plain Vanilla IRS and validates JSON round-trip. |
| **List Business Events** | `.venv\Scripts\python.exe -m cdm_workspace.harness events` | Lists all IRS lifecycle business events and qualifiers. |

---

## 4. ⏱️ Command Execution & Latency Best Practices

* **Bundle Loading Overhead**:
  * Cold-loading `finos-cdm` and rebuilding its 180+ models takes approximately 4–7 seconds.
  * When invoking `run_command` in tool calls, **always set `WaitMsBeforeAsync: 10000`** (the maximum allowed) to prevent synchronous timeout and background task spawning.

---

## 5. 🧪 Testing & Validation Protocol

After making any code or documentation changes:
1. Run `.venv\Scripts\python.exe -m pytest -v` (or use `.venv\Scripts\python.exe -m cdm_workspace.harness verify`).
2. Ensure 100% test pass rate.
3. Verify JSON serialization round-trips with `exclude_none=True`.
