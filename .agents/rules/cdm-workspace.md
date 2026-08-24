# CDM Workspace Standards & Coding Rules

These rules apply across `cdm_workspace` and guide code quality and data model serialization.

## Coding and Serialization Standards
- **Compatibility**: Every module or script interacting with CDM must place `import cdm_compat` before any `finos.cdm.*` imports.
- **Serialization**: Use Pydantic v2 `model.model_dump_json(indent=2, exclude_none=True)` when serializing CDM models to JSON.
- **Validation & Deserialization**: Use `ModelClass.model_validate_json(json_str)` when parsing JSON into CDM objects.
- **Compatibility Isolation**: Never edit vendor files in `.venv/` directly. Place monkey-patches and runtime adjustments in `src/cdm_compat/`.

## Diagnostics and Verification
- Use `.venv\Scripts\python.exe -m cdm_workspace.harness doctor` for quick environment health checks.
- Run `.venv\Scripts\python.exe -m pytest -v` or `.venv\Scripts\python.exe -m cdm_workspace.harness verify` after modifying production code or adapters.

