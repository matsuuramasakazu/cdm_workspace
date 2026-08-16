---
name: cdm-workspace
description: >-
  Operational workflows, harness commands, and domain guidance for developing,
  testing, inspecting, and executing FINOS CDM models and Plain Vanilla Interest
  Rate Swaps (IRS) in cdm_workspace.
---

# CDM Workspace AI Agent Runbook & Skill

This skill provides step-by-step procedures, runbooks, and harness commands for AI agents operating in the `cdm-workspace` repository.

---

## 1. Quick Reference: Agent Harness Commands

Always use the local virtual environment (`.venv\Scripts\python.exe`):

```bash
# 1. Environment & Dependency Health Check (< 1s)
.venv\Scripts\python.exe -m cdm_workspace.harness doctor

# 2. Automated Test & Verification Pipeline
.venv\Scripts\python.exe -m cdm_workspace.harness verify

# 3. Model Inspection (fields, types, required flags without circular imports)
.venv\Scripts\python.exe -m cdm_workspace.harness inspect Trade
.venv\Scripts\python.exe -m cdm_workspace.harness inspect TradeState
.venv\Scripts\python.exe -m cdm_workspace.harness inspect InterestRatePayout

# 4. List IRS Business Events & Qualifiers
.venv\Scripts\python.exe -m cdm_workspace.harness events

# 5. Generate & Validate IRS JSON
.venv\Scripts\python.exe -m cdm_workspace.harness irs

# 6. Safe Python Execution (with cdm_compat auto-bootstrapped)
.venv\Scripts\python.exe -m cdm_workspace.harness exec "from finos.cdm.event.common.Trade import Trade; print(Trade)"
```

---

## 2. Mandatory Rules for Agent Code Generation

1. **Always import `cdm_compat` first**:
   ```python
   import cdm_compat  # REQUIRED BEFORE ANY finos.cdm.* IMPORTS
   from finos.cdm.event.common.Trade import Trade
   ```
2. **Package Namespace**:
   * Use `finos.cdm.*`, NOT `cdm.*`.
3. **Pydantic v2 Serialization**:
   * Dumps: `model.model_dump_json(indent=2, exclude_none=True)`
   * Loads: `ModelClass.model_validate_json(json_str)`
4. **Command Execution Latency**:
   * When invoking shell tools (`run_command`), set `WaitMsBeforeAsync: 10000` to prevent unnecessary background task hand-offs.

---

## 3. Common Troubleshooting & Workarounds

| Issue | Symptom | Immediate Fix |
| :--- | :--- | :--- |
| **Circular Import Error** | `ImportError: cannot import name 'IdentifiedList' from partially initialized module ...` | Ensure `import cdm_compat` is placed at the very top before any `from finos.cdm.*` line. |
| **Missing Field / Schema Error** | `ValidationError` on inherited fields | `cdm_compat.rebuild_models.rebuild_cdm_model(cls)` fixes inherited fields on Pydantic v2. |
| **Rosetta Syntax Error** | `SyntaxError: assignment expression cannot be used in a comprehension iterable expression` | Do not call `finos.cdm.*.functions.Calculate*` directly; build model objects (`Reset`, `Transfer`, etc.) explicitly. |
| **Pydantic Serializer Warning** | `UserWarning: PydanticSerializationUnexpectedValue` for lists | Handled by `cdm_compat` at runtime. Safe to ignore in test assertions. |
