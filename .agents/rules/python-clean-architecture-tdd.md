# Python Clean Architecture & TDD Rules

These rules enforce strict architectural boundaries and Test-Driven Development (TDD) best practices.

## Clean Architecture Rules
- **Dependency Rule**: Dependencies must always point inward: Infrastructure -> Adapters -> Application -> Domain.
- **Pure Domain**: The Domain Layer must remain pure Python with zero dependencies on external frameworks, databases, or `finos.cdm`.
- **Anti-Corruption Layer (ACL)**: External models (`finos.cdm`) must be mapped via adapter layers rather than leaking into core domain entities.
- **Interface Inversion**: Use `typing.Protocol` or abstract base classes to define outbound ports in the application layer.

## TDD Standards
- **Test-First**: Write unit tests before writing production code (Red -> Green -> Refactor).
- **Fast Domain Tests**: Domain unit tests must execute instantly without heavy I/O or CDM bundle loading.
- **Round-Trip Validation**: All data converters and adapters must have explicit JSON round-trip tests.
- **Verification**: Run `.venv\Scripts\python.exe -m pytest -v` before finalizing any code modification.
