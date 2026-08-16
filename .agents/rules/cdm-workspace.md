# CDM Workspace Agent Rules

These rules apply across `cdm_workspace` and are discovered automatically by the Antigravity Agent framework.

## Execution Rules
- Always use the `.venv` Python executable located at `.venv\Scripts\python.exe`.
- Always set `WaitMsBeforeAsync: 10000` when executing CDM commands via shell tools.

## Coding and Serialization Standards
- Every CDM script must include `import cdm_compat` before any `finos.cdm.*` imports.
- Serializing CDM models: Use `model.model_dump_json(indent=2, exclude_none=True)`.
- Validating CDM models: Use `ModelClass.model_validate_json(json_str)`.
- Never edit files in `.venv/` directly. Put compatibility logic in `src/cdm_compat/`.

## Verification
- Before finishing any task modifying code, run `pytest` via `.venv\Scripts\python.exe -m pytest -v` or `.venv\Scripts\python.exe -m cdm_workspace.harness verify`.
