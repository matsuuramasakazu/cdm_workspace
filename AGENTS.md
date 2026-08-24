# AI Agent Master Baseline (`cdm-workspace`)

This workspace uses Antigravity Customizations. Detailed domain instructions, rules, and runbooks are modularized in `.agents/`.

---

## 1. ⚙️ Command Execution Baseline

* **Interpreter**: `.venv\Scripts\python.exe` (⚠️ *Never invoke bare `python` or `poetry`*).
* **Shell Latency Guard**: Always set `WaitMsBeforeAsync: 10000` when executing tool commands involving `finos-cdm` / `cdm_compat`.

---

## 2. 👥 Sub-Agent Roles & Orchestration

| Sub-Agent | Role & Primary Focus | Key Inputs & Deliverables |
| :--- | :--- | :--- |
| [`finos-cdm-financial-analyst`](.agents/agents/finos-cdm-financial-analyst.md) | **What / Why**: Financial Engineering, ISDA Trade Lifecycle, and dynamic CDM schema inspection. | **In**: Financial requirements / business events<br/>**Out**: Financial Spec (Economic terms, CDM model paths, types, JSON specs) |
| [`python-clean-architecture-tdd`](.agents/agents/python-clean-architecture-tdd.md) | **How**: Clean Architecture 4-layer design, Anti-Corruption Layer (ACL), TDD, and Python 3.12+ implementation. | **In**: Financial Spec from Analyst<br/>**Out**: Pure domain models, ACL adapters, and verified pytest suite |

### Standard Handoff Flow:
```text
[User / Main Agent Request]
         │
         ▼
1. Financial Analyst: Inspects CDM schema & outputs Financial Spec DTO / JSON
         │
         ▼
2. Software Architect: Designs Clean Architecture layers, writes pytest (Red),
                       implements pure domain & ACL adapter (Green), and refactors.
```

---

## 3. 🗂️ Customizations Catalogue

* 📜 **Workspace Rules** ([`.agents/rules/`](.agents/rules/)):
  * [`cdm-workspace.md`](.agents/rules/cdm-workspace.md): General workspace coding and serialization standards.
  * [`financial-engineering-cdm.md`](.agents/rules/financial-engineering-cdm.md): Precision, Day Count, Business Day conventions.
  * [`python-clean-architecture-tdd.md`](.agents/rules/python-clean-architecture-tdd.md): Layer boundaries, pure domain isolation, TDD rules.
* 🛠️ **Operational Skills & Runbooks** ([`.agents/skills/`](.agents/skills/)):
  * [`cdm-workspace`](.agents/skills/cdm-workspace/SKILL.md): Harness CLI Diagnostics, Model Inspection (`inspect`), and Troubleshooting.

---

## 4. 🛡️ System Invariant

1. **CDM Runtime Compatibility**: Always `import cdm_compat` before any `finos.cdm.*` import. Avoid calling `finos.cdm.*.functions` directly due to Python 3.12+ syntax incompatibilities.

