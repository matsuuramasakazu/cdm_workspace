---
name: cdm-workspace
description: >-
  Operational runbooks, diagnostic procedures, and harness commands for executing,
  inspecting, and verifying FINOS CDM models and IRS trades in cdm_workspace.
---

# 🛠️ CDM Workspace AI Agent Operational Runbook

This skill provides on-demand executable procedures and runbooks for AI agents operating within `cdm-workspace`.

---

## 📖 Runbook 1: Environment & Compatibility Health Check

Run this procedure whenever entering a new session or encountering import/environment anomalies:

```bash
# Diagnoses virtualenv, Python dependencies, and cdm_compat health (< 1s)
.venv\Scripts\python.exe -m cdm_workspace.harness doctor
```

**Success Criteria**:
- `Virtualenv`: Active (`.venv\Scripts\python.exe`)
- `finos-cdm`: Version 7.1.0 or higher detected
- `cdm_compat`: Active and patching `rune-runtime`

---

## 📖 Runbook 2: CDM Schema & Model Inspection Procedure

Use this procedure (typically invoked by [`finos-cdm-financial-analyst`](../../agents/finos-cdm-financial-analyst.md)) to inspect fields, required types, and schema hierarchies without circular import overhead:

```bash
# Inspect any CDM model class
.venv\Scripts\python.exe -m cdm_workspace.harness inspect <ModelName>

# Examples:
.venv\Scripts\python.exe -m cdm_workspace.harness inspect Trade
.venv\Scripts\python.exe -m cdm_workspace.harness inspect TradeState
.venv\Scripts\python.exe -m cdm_workspace.harness inspect InterestRatePayout
.venv\Scripts\python.exe -m cdm_workspace.harness inspect CalculationPeriodDates
```

**Interpretation**:
- Check for `[Required]` vs `[Optional]` flags.
- Note whether fields are wrapped in `FieldWithMeta...` or primitive types.

---

## 📖 Runbook 3: Trade Generation & Verification Procedure

Use this procedure to verify end-to-end Plain Vanilla IRS creation, Pydantic v2 validation, and JSON serialization:

```bash
# 1. Generate IRS Trade JSON and test round-trip
.venv\Scripts\python.exe -m cdm_workspace.harness irs

# 2. List all IRS lifecycle business events and qualifiers
.venv\Scripts\python.exe -m cdm_workspace.harness events

# 3. Run full automated test suite
.venv\Scripts\python.exe -m cdm_workspace.harness verify
```

---

## 📖 Runbook 4: Safe Snippet Execution

Run Python snippets with `cdm_compat` pre-initialized to test model instantiation on the fly:

```bash
.venv\Scripts\python.exe -m cdm_workspace.harness exec "from finos.cdm.event.common.Trade import Trade; print(Trade.__name__)"
```

---

## 📖 Runbook 5: Troubleshooting & Incident Resolution

| Symptom / Error | Root Cause | Actionable Fix |
| :--- | :--- | :--- |
| `ImportError: cannot import name 'IdentifiedList'` | Circular import in `rune-runtime` / `finos._bundle` | Place `import cdm_compat` at line 1 before any `from finos.cdm.*` import. |
| `ValidationError` on inherited fields | Pydantic v2 schema rebuild omitted on subclass | Invoke `cdm_compat.rebuild_models.rebuild_cdm_model(cls)`. |
| `SyntaxError: assignment expression cannot be used...` | Rosetta DSL generated function incompatibility in Python 3.12+ | Do not call `finos.cdm.*.functions.Calculate*`. Construct Pydantic model objects directly. |
| Command hangs or turns into background task | Bundle loading latency (4–7s) exceeds default timeout | Always specify `WaitMsBeforeAsync: 10000` in shell tool calls. |
