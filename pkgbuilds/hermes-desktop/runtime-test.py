"""Check the release backport against the actual pinned upstream source."""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Optional
from unittest.mock import patch

source, patch_file = map(Path, sys.argv[1:])
with tempfile.TemporaryDirectory(prefix="hermes-runtime-check-") as temporary:
    root = Path(temporary)
    for filename in ("hermes_cli/main.py", "scripts/desktop-update/posix.sh"):
        destination = root / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / filename, destination)
    subprocess.run(["git", "apply", str(patch_file.resolve())], cwd=root, check=True)
    text = (root / "hermes_cli/main.py").read_text()
    functions = {node.name: node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)}
    names = [
        "_desktop_linux_userns_sandbox_available", "_sandbox_helper_lstat",
        "_sandbox_helper_is_setuid_root", "_desktop_linux_needs_disable_setuid_sandbox",
        "_desktop_linux_sandbox_fixup",
    ]
    scope = dict(Path=Path, Optional=Optional, os=os, sys=sys, shutil=shutil,
                 subprocess=subprocess, stat=__import__("stat"))
    for name in names:
        exec(compile(ast.Module(body=[functions[name]], type_ignores=[]), str(source), "exec"), scope)

    native = root / "apps/desktop/release/linux-unpacked"
    native.mkdir(parents=True)
    executable = native / "Hermes"
    sandbox = native / "chrome-sandbox"
    sandbox.write_text("fixture")
    sandbox.chmod(0o755)
    gui = ast.get_source_segment(text, functions["cmd_gui"])
    start = gui.index("    launch_command = [str(packaged_executable)]")
    end = gui.index("    launch_command.extend(config_electron_flags)", start)
    exec("def launch(packaged_executable):\n" + gui[start:end] + "    return launch_command\n", scope)
    scope["_desktop_linux_needs_no_sandbox"] = lambda: False
    with patch.object(shutil, "which", side_effect=lambda name: "/fixture/unshare" if name == "unshare" else None):
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            assert scope["launch"](executable) == [str(executable), "--disable-setuid-sandbox"]
            assert all(call.args[0][0] == "/fixture/unshare" for call in run.call_args_list)
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            assert not scope["_desktop_linux_sandbox_fixup"](executable)
        sandbox.unlink()
        sandbox.symlink_to(root / "unrelated")
        (root / "unrelated").write_text("keep")
        with patch.object(subprocess, "run") as run:
            assert not scope["_desktop_linux_sandbox_fixup"](executable)
            run.assert_not_called()
        sandbox.unlink()
        sandbox.write_text("fixture")

    mock_bin = root / "bin"
    mock_bin.mkdir()
    unshare = mock_bin / "unshare"
    unshare.write_text('#!/bin/bash\nexit "${TEST_NAMESPACE_RESULT:-0}"\n')
    unshare.chmod(0o755)
    env = {**os.environ, "PATH": f"{mock_bin}:/usr/bin:/bin"}
    env.pop("ELECTRON_DISABLE_SANDBOX", None)
    gate = ["bash", str(root / "scripts/desktop-update/posix.sh"), "--self-test-gate",
            "--install-root", str(root), "--relaunch-target", str(executable)]
    assert subprocess.check_output(gate, env=env, text=True).strip() == "relaunch"
    assert subprocess.check_output(gate, env={**env, "TEST_NAMESPACE_RESULT": "1"}, text=True).startswith("manual:")
    gate[-1] = "/opt/hermes-desktop/Hermes"
    assert subprocess.check_output(gate, env=env, text=True).startswith("skew:")
print("PASS: native launch and release update handoff retain the user-namespace sandbox")
