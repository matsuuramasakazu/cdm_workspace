# Financial Engineering & FINOS CDM Rules

These rules enforce mathematical accuracy, standard financial conventions, and FINOS CDM integrity across the workspace.

## Financial Calculations & Conventions
- **Precision**: Monetary amounts and rates must use `Decimal` or float with appropriate precision; never rely on implicit float rounding for financial settlement amounts.
- **Day Count Conventions**: Explicitly declare day count fractions (e.g. `ACT_365_FIXED` for JPY/GBP, `ACT_360` for USD/EUR, `30_360` for fixed legs).
- **Business Day Rolls**: Always define business day adjustments and specify business centers (e.g., `JPTO`, `USNY`, `GBLO`).

## FINOS CDM Usage
- **Mandatory Compatibility Import**: Any module importing `finos.cdm.*` must import `cdm_compat` first to prevent circular import failures.
- **Serialization**: Use Pydantic v2 `model_dump_json(indent=2, exclude_none=True)` for serializing CDM objects.
- **Deserialization**: Use `ModelClass.model_validate_json(json_str)` for validating JSON input against CDM schemas.
- **Avoid Rosetta Functions**: Prefer direct Pydantic model construction over calling `finos.cdm.*.functions` which contain Python 3.12+ syntax incompatibilities.
