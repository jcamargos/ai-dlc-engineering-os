"""Exercise the built wheel through uvx, with isolated homes and tool/cache paths."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile


def main() -> None:
    wheel = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="aidlc-setup-") as temp:
        root = Path(temp)
        home = root / "home"
        if sys.platform == "win32":
            profile = home / "AppData/Roaming/Code/User"
        elif sys.platform == "darwin":
            profile = home / "Library/Application Support/Code/User"
        else:
            profile = home / ".config/Code/User"
        profile.mkdir(parents=True)
        env = dict(os.environ)
        env.update(UV_TOOL_DIR=str(root / "tools"), UV_TOOL_BIN_DIR=str(root / "bin"),
                   UV_CACHE_DIR=str(root / "cache"), AI_DLC_DATA_DIR=str(home / ".ai-dlc/memory"))
        env.pop("AI_DLC_DB_PATH", None)
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        uv = shutil.which("uv", path=env["PATH"])
        if not uv:
            raise RuntimeError("Install uv in the verification environment first")

        def run(*args: str) -> None:
            subprocess.run(list(args), env=env, check=True, timeout=300)

        run(uv, "tool", "run", "--python", sys.executable, "--from", str(wheel), "ai-dlc-engineering-os", "setup",
            "--editors", "codex,claude,vscode", "--yes", "--home", str(home))
        # Editor registrations must survive removal of the launcher's cached environment.
        run(uv, "cache", "clean", "ai-dlc-engineering-os")
        python = root / "tools/ai-dlc-engineering-os" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(str(python), "-m", "ai_dlc_mcp.installer", "doctor", "--home", str(home))
        print("PASS: installed wheel setup and persistent MCP work after uvx cache cleanup")


if __name__ == "__main__":
    main()
