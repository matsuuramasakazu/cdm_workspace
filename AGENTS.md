# AI Agent Master Baseline (`cdm-workspace`)

This workspace uses Antigravity Customizations. Detailed domain instructions, rules, and runbooks are modularized in `.agents/`.

---

## 1. ⚙️ Environment Baseline

* **Interpreter**: `.venv\Scripts\python.exe` (⚠️ *Never invoke bare `python` or `poetry`*).
* **Test Suite**: `.venv\Scripts\python.exe -m pytest`
* **Shell Latency Guard**: Set `WaitMsBeforeAsync: 10000` when executing tool commands involving `finos-cdm`.

---

## 2. 🗂️ Customizations & Specialized Sub-Agents

* 👥 **Specialized Sub-Agents** ([`.agents/agents/`](.agents/agents/)):
  * [`finos-cdm-financial-analyst`](.agents/agents/finos-cdm-financial-analyst.md): Financial Engineering, ISDA Trade Lifecycle & FINOS CDM Schema Analysis.
  * [`python-clean-architecture-tdd`](.agents/agents/python-clean-architecture-tdd.md): Clean Architecture, TDD (Red-Green-Refactor) & Python 3.12+ Implementation.
* 📜 **Workspace Rules** ([`.agents/rules/`](.agents/rules/)):
  * [`cdm-workspace.md`](.agents/rules/cdm-workspace.md) / [`financial-engineering-cdm.md`](.agents/rules/financial-engineering-cdm.md) / [`python-clean-architecture-tdd.md`](.agents/rules/python-clean-architecture-tdd.md)
* 🛠️ **Operational Skills & Runbooks** ([`.agents/skills/`](.agents/skills/)):
  * [`cdm-workspace`](.agents/skills/cdm-workspace/SKILL.md): Harness CLI Diagnostics, Model Inspection & Troubleshooting.

---

## 3. 🛡️ Invariant Rules

1. **CDM Compatibility**: Always `import cdm_compat` before any `finos.cdm.*` import. Avoid calling `finos.cdm.*.functions` directly.
2. **Clean Architecture & TDD**: Pure domain with zero external dependencies. External CDM models must be mapped via adapters. Follow Red-Green-Refactor.
3. **Verification**: Always run `.venv\Scripts\python.exe -m pytest -v` before finalizing changes.
