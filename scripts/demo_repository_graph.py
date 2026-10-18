"""Reproducible offline graph demo using a disposable repository and database."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ai_dlc_mcp.store import MemoryStore


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-dlc-graph-demo-") as directory:
        root = Path(directory).resolve() / "repository"
        root.mkdir()
        subprocess.run(["git", "init", "--quiet", str(root)], check=True)
        (root / "tax.py").write_text("RATE = 0.1\n", encoding="utf-8")
        (root / "billing.py").write_text("import tax\n", encoding="utf-8")
        (root / "checkout.py").write_text("import billing\n", encoding="utf-8")
        with patch.dict(os.environ, {"AI_DLC_GRAPH_ROOTS": str(root)}):
            store = MemoryStore(Path(directory) / "memory.db", "demo")
            store.ensure_project("demo", "Disposable demo", str(root))
            indexed = store.index_repository_graph("demo")
            impact = store.query_repository_graph("demo", "tax.py")
            (root / "tax.py").write_text("RATE = 0.2\n", encoding="utf-8")
            stale = store.query_repository_graph("demo", "tax.py")
            assert stale["status"] == "stale" and stale["edges"] == []
            store.index_repository_graph("demo")
            refreshed = store.repository_graph_status("demo")
            assert refreshed["status"] == "current"
            print(json.dumps({"indexed_files": indexed["node_count"],
                              "dependents_of_tax": impact["edges"],
                              "after_edit": stale["status"],
                              "after_refresh": refreshed["status"]}, indent=2))
    print("Demo passed; temporary repository and database removed.")


if __name__ == "__main__":
    main()
