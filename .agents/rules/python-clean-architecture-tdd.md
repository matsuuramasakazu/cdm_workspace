# Python Clean Architecture & TDD Rules

These rules enforce strict architectural boundaries, dependency isolation, and Test-Driven Development (TDD) standards.

## Clean Architecture Boundaries
- **Inward Dependency Rule**: Source code dependencies must only point inward: Infrastructure -> Adapters -> Application -> Domain.
- **Pure Domain Isolation**: The Domain layer must be pure Python with zero external imports (no `finos.cdm`, no frameworks, no database drivers).
- **Anti-Corruption Layer (ACL)**: All external models (including CDM Pydantic classes) must be translated into pure domain entities via bidirectional adapters.
- **Dependency Inversion**: Define abstract interfaces/ports in Application/Domain using `typing.Protocol`.

## Test-Driven Development (TDD)
- **Red-Green-Refactor**: Write a failing test first, make it pass with minimal code, then refactor.
- **Fast Domain Tests**: Domain unit tests must run in milliseconds without triggering heavy CDM bundle initialization.
- **Adapter Contract Tests**: Every ACL converter must include explicit round-trip serialization and schema validation tests.
- **Pre-Finalization Verification**: Always run `.venv\Scripts\python.exe -m pytest -v` before finalizing code changes.

