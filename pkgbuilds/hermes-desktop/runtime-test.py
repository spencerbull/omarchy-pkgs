"""Check native launch and the release updater without running Hermes or sudo."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

source, patch_file, launcher = map(Path, sys.argv[1:])
with tempfile.TemporaryDirectory(prefix="hermes-runtime-check-") as temporary:
    root = Path(temporary)
    destination = root / "scripts/desktop-update/posix.sh"
    destination.parent.mkdir(parents=True)
    shutil.copyfile(source / "scripts/desktop-update/posix.sh", destination)
    subprocess.run(["git", "apply", str(patch_file.resolve())], cwd=root, check=True)

    home = root / "home with spaces"
    runtime = home / ".hermes/hermes-agent"
    native = runtime / "apps/desktop/release/linux-unpacked"
    native.mkdir(parents=True)
    executable = native / "Hermes"
    executable.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
Path(os.environ["TEST_OUTPUT"]).write_text(json.dumps({
    "args": sys.argv[1:], "home": os.environ["HERMES_HOME"],
    "store": os.environ["HERMES_DESKTOP_PASSWORD_STORE"],
    "gpu": os.environ.get("HERMES_DESKTOP_DISABLE_GPU"),
}))
''')
    executable.chmod(0o755)
    sandbox = native / "chrome-sandbox"
    sandbox.write_text("fixture")
    sandbox.chmod(0o755)

    mock_bin = root / "bin"
    mock_bin.mkdir()
    unshare = mock_bin / "unshare"
    unshare.write_text('#!/bin/bash\nexit "${TEST_NAMESPACE_RESULT:-0}"\n')
    unshare.chmod(0o755)
    forbidden = '#!/bin/bash\ntouch "$TEST_FORBIDDEN"\nexit 99\n'
    cli = runtime / "venv/bin/hermes"
    cli.parent.mkdir(parents=True)
    cli.write_text(forbidden)
    cli.chmod(0o755)
    for command in ("sudo", "omarchy-install-hermes-cli"):
        target = mock_bin / command
        target.write_text(forbidden if command == "sudo" else '#!/bin/bash\nexit 0\n')
        target.chmod(0o755)

    output = root / "launch.json"
    forbidden_output = root / "forbidden"
    env = {"HOME": str(home), "PATH": f"{mock_bin}:/usr/bin:/bin",
           "TEST_OUTPUT": str(output), "TEST_FORBIDDEN": str(forbidden_output)}
    launch = ["bash", str(launcher.resolve())]
    for args, overrides, expected_args, expected_store in (
        ([], {"WAYLAND_DISPLAY": "wayland-1"}, ["--ozone-platform=wayland"], "gnome-libsecret"),
        (["--ozone-platform=x11", "hermes://open?text=a%20b"],
         {"WAYLAND_DISPLAY": "wayland-1", "HERMES_DESKTOP_PASSWORD_STORE": "kwallet6"},
         ["--ozone-platform=x11", "hermes://open?text=a%20b"], "kwallet6"),
        ([], {"HERMES_HOME": str(home / ".hermes/profiles/work"), "HERMES_DESKTOP_DISABLE_GPU": "1"},
         [], "gnome-libsecret"),
    ):
        subprocess.run(launch + args, env={**env, **overrides}, check=True)
        result = json.loads(output.read_text())
        assert result["args"] == ["--disable-setuid-sandbox", *expected_args], result
        assert result["home"] == str(home / ".hermes"), result
        assert result["store"] == expected_store, result
        assert result["gpu"] == overrides.get("HERMES_DESKTOP_DISABLE_GPU"), result
        assert not forbidden_output.exists(), "launcher invoked CLI or sudo"
        output.unlink()
    for code in ("1", "127"):
        for args in ([], ["hermes://open"]):
            result = subprocess.run(launch + args, env={**env, "TEST_NAMESPACE_RESULT": code},
                                    capture_output=True, text=True)
            assert result.returncode != 0 and "user namespaces" in result.stderr, result
            assert not output.exists() and not forbidden_output.exists()

    gate = ["bash", str(destination), "--self-test-gate", "--install-root", str(runtime),
            "--relaunch-target", str(executable)]
    assert subprocess.check_output(gate, env=env, text=True).strip() == "relaunch"
    assert subprocess.check_output(gate, env={**env, "TEST_NAMESPACE_RESULT": "1"}, text=True).startswith("manual:")
    gate[-1] = "/opt/hermes-desktop/Hermes"
    assert subprocess.check_output(gate, env=env, text=True).startswith("skew:")
print("PASS: direct native launches fail closed; release updater accepts the namespace sandbox")
