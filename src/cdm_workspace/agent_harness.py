"""
AI Agent Harness entrypoint wrapper.

Redirects directly to cdm_workspace.harness.cli.main.
"""

from __future__ import annotations

import sys
from cdm_workspace.harness.cli import main

if __name__ == "__main__":
    sys.exit(main())
