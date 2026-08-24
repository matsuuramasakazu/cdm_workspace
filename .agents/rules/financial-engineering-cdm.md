# Financial Engineering & FINOS CDM Rules

These rules enforce mathematical precision, ISDA financial conventions, and FINOS CDM structural integrity.

## Financial Calculations & Conventions
- **Precision**: Monetary amounts, accruals, and rates must use `Decimal` with explicit rounding rules (e.g., `ROUND_HALF_UP`); never rely on raw float arithmetic for financial settlements.
- **Day Count Fractions**: Explicitly specify day count conventions (e.g., `ACT_365_FIXED` for JPY/GBP, `ACT_360` for USD/EUR, `30_360` for fixed legs).
- **Business Day Adjustments**: Explicitly define business day roll conventions (e.g., `MODIFIED_FOLLOWING`, `FOLLOWING`) and business centers (e.g., `JPTO`, `USNY`, `GBLO`).

## FINOS CDM Model Integrity
- **Model Construction**: Prefer direct, explicit Pydantic model instantiations over generated `finos.cdm.*.functions` (which contain Python 3.12+ syntax issues).
- **Type Safety**: Distinguish clearly between metadata wrappers (`FieldWithMetaDate`, `ReferenceWithMeta...`), primitives, and Enum members.
- **ISDA Event Alignment**: Ensure event instructions (Execution, ClearedTrade, Reset, CashTransfer, Novation, Termination) correspond to standard ISDA / CCP workflows.

