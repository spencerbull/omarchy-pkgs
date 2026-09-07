#!/bin/bash
set -euo pipefail

die() {
  echo "Hermes: $*" >&2
  exit 1
}

HERMES_HOME=$(realpath -ms -- "${HERMES_HOME:-$HOME/.hermes}")
# A profile session shares its parent home's installation and launchers.
home_parent=${HERMES_HOME%/*}
if [[ ${home_parent##*/} == "profiles" ]]; then
  HERMES_HOME=${home_parent%/*}
fi
[[ $HERMES_HOME == /* && $HERMES_HOME != "/" ]] || die "Use a Hermes data directory other than /."
export HERMES_HOME
root="$HERMES_HOME/hermes-agent"
marker="$root/.omarchy-hermes-desktop"
installer=/usr/share/hermes-desktop/install.sh
seed=/usr/share/hermes-desktop/seed
cli=("$root/venv/bin/python" "$root/hermes")

desktop_executable() {
  local executable
  for executable in "$root/apps/desktop/release/linux-unpacked/"{Hermes,hermes}; do
    if [[ -f $executable && -x $executable ]]; then
      printf '%s\n' "$executable"
      return 0
    fi
  done
  return 1
}

native_wrapper() {
  local wrapper=$1 entry=$2 suffix=${3:-}
  [[ -f $wrapper && ! -L $wrapper ]] && cmp -s "$wrapper" <(
    printf '#!/usr/bin/env bash\nunset PYTHONPATH\nunset PYTHONHOME\nexec "%s/venv/bin/python" "%s/%s"%s "$@"\n' "$root" "$root" "$entry" "$suffix"
  )
}

runtime_ready() {
  [[ -f $root/.hermes-bootstrap-complete && -x ${cli[0]} ]] &&
    [[ -x $HOME/.local/bin/hermes ]] &&
    native_wrapper "$HOME/.local/bin/hermes" hermes &&
    desktop_executable >/dev/null &&
    timeout 15 env -u PYTHONPATH -u PYTHONHOME "${cli[@]}" --version >/dev/null 2>&1
}

ready() {
  if [[ -f $marker ]]; then
    grep -qxF ready "$marker" || return 1
  fi
  runtime_ready
}

restore_launchers() {
  local command wrapper entry
  for command in hermes hermes-agent hermes-acp; do
    [[ -f $install_backup/$command ]] || continue
    wrapper="$HOME/.local/bin/$command"
    entry=hermes
    [[ $command == "hermes-agent" ]] && entry=run_agent.py
    if [[ ! -e $wrapper && ! -L $wrapper ]] || native_wrapper "$wrapper" "$entry" ||
      { [[ -f $wrapper && ! -L $wrapper ]] && grep -qxF '# Written by omarchy-install-hermes-cli.' "$wrapper"; } ||
      { [[ $command == "hermes-acp" ]] && native_wrapper "$wrapper" hermes ' acp'; }; then
      cp -p "$install_backup/$command" "$wrapper"
    else
      echo "Keeping changed $wrapper; its original is in $install_backup." >&2
      return
    fi
  done
  rm -rf "$install_backup"
}

stage() {
  bash "$installer" --dir "${2:-$root}" --branch main --non-interactive --stage "$1"
}

install_desktop() {
  local graphical=${1:-false}
  (( EUID != 0 )) || die "Run this installer as your desktop user, without sudo."
  mkdir -p "$HERMES_HOME"
  exec 9>"$HERMES_HOME/.omarchy-hermes-desktop.lock"
  flock -n 9 || die "Another Hermes installation is already running."
  if ready; then
    exec 9>&-
    return
  fi

  # Upstream replaces these launchers. Admit its exact shims or Omarchy's
  # marked predecessor before starting work, never a user's custom command.
  local command wrapper entry
  for command in hermes hermes-agent hermes-acp; do
    wrapper="$HOME/.local/bin/$command"
    [[ -e $wrapper || -L $wrapper ]] || continue
    entry=hermes
    [[ $command == "hermes-agent" ]] && entry=run_agent.py
    if native_wrapper "$wrapper" "$entry"; then continue; fi
    if [[ $command == "hermes-acp" ]] && native_wrapper "$wrapper" hermes ' acp'; then continue; fi
    if [[ $command == "hermes" && -f $wrapper && ! -L $wrapper ]] &&
      grep -qxF '# Written by omarchy-install-hermes-cli.' "$wrapper"; then continue; fi
    die "Keeping the existing $wrapper. Move or update that installation before installing Hermes Desktop."
  done

  # The native prerequisite stage may install Node's three user symlinks.
  for command in node npm npx; do
    wrapper="$HOME/.local/bin/$command"
    if [[ -e $wrapper || -L $wrapper ]] &&
      [[ ! -L $wrapper || $(readlink "$wrapper") != "$HERMES_HOME/node/bin/$command" ]]; then
      die "Keeping the existing $wrapper. Move it before installing Hermes Desktop."
    fi
  done

  local legacy=false
  if [[ -e $root || -L $root ]]; then
    [[ -d $root/.git && ! -L $root && ! -L $root/.git ]] || die "Keeping $root; it is not a managed checkout."
    if [[ -f $marker ]] && grep -qxF updating "$marker"; then
      legacy=true
    elif [[ ! -f $marker ]]; then
      python -I - "$root/.hermes-bootstrap-complete" <<'PY' || die "Keeping the existing checkout; install its desktop with 'hermes desktop'."
import json, sys
try:
    stamp = json.load(open(sys.argv[1]))
    assert stamp.get('desktopVersion') and stamp.get('pinnedCommit') in {
        'e624e9fde561e1add9388384012b295fde669ade',
        '29112bef099274229cadff79cdff7bf7b99c4b77',
    }
except (OSError, ValueError, AssertionError, AttributeError):
    sys.exit(1)
PY
      legacy=true
    fi
    [[ -z $(git -C "$root" status --porcelain) ]] || die "Keeping local changes in $root. Save them before installing the desktop."
    case "$(git -C "$root" remote get-url origin)" in
      https://github.com/NousResearch/hermes-agent.git | git@github.com:NousResearch/hermes-agent.git) ;;
      *) die "Keeping the checkout's custom origin. Install its desktop with 'hermes desktop'." ;;
    esac
    # GUI bootstrap updates existing Git checkouts and can hard-reset a
    # divergent main. Admit only published history before giving it the root.
    if [[ $legacy == true || $graphical == true ]]; then
      case "$(git -C "$root" rev-parse HEAD)" in
        e624e9fde561e1add9388384012b295fde669ade | 29112bef099274229cadff79cdff7bf7b99c4b77) ;;
        *)
          if [[ $(git -C "$root" symbolic-ref --short -q HEAD) != "main" ]] ||
            ! git -C "$root" merge-base --is-ancestor HEAD refs/remotes/origin/main; then
            die "Keeping the checkout branch or unpublished commits. Run 'hermes desktop' from that installation."
          fi
          ;;
      esac
    fi
  fi

  install_backup=$(mktemp -d "$HERMES_HOME/.omarchy-hermes-launchers.XXXXXX")
  for command in hermes hermes-agent hermes-acp; do
    wrapper="$HOME/.local/bin/$command"
    if [[ -f $wrapper ]]; then cp -p "$wrapper" "$install_backup/$command"; fi
  done
  trap restore_launchers EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM

  local mise_predecessor=false
  if [[ -f $install_backup/hermes ]] && grep -qxF '# Written by omarchy-install-hermes-cli.' "$install_backup/hermes"; then
    mise_predecessor=true
  fi

  if [[ $legacy == true ]]; then
    if [[ $mise_predecessor == true ]]; then
      printf '%s\n' 'pipx:hermes-agent[extras=all]' >"$root/.git/omarchy-mise-predecessor"
    fi
    if ! grep -qxF '/.omarchy-hermes-desktop' "$root/.git/info/exclude"; then
      printf '/.omarchy-hermes-desktop\n' >>"$root/.git/info/exclude"
    fi
    printf 'updating\n' >"$marker"
    local refspec='+refs/heads/main:refs/remotes/origin/main'
    if ! git -C "$root" config --get-all remote.origin.fetch | grep -qxF "$refspec"; then
      git -C "$root" config --add remote.origin.fetch "$refspec"
    fi
    if [[ $graphical == false ]]; then
      git -C "$root" fetch origin "$refspec"
      env -u PYTHONPATH -u PYTHONHOME "${cli[@]}" update --yes --branch main
    fi
  elif [[ ! -e $root ]]; then
    if [[ $graphical == false ]]; then stage prerequisites; fi
    # Publish only a complete clone with its ownership marker. An interrupted
    # clone stays aside for inspection and cannot block the next installation.
    local repository_dir
    repository_dir=$(mktemp -d "$HERMES_HOME/.omarchy-hermes-repository.XXXXXX")
    echo "Preparing the Hermes checkout in $repository_dir"
    if [[ $graphical == true ]]; then
      cp -a --reflink=auto "$seed" "$repository_dir/hermes-agent"
      chmod -R u+w "$repository_dir/hermes-agent"
    else
      stage repository "$repository_dir/hermes-agent"
    fi
    printf '/.omarchy-hermes-desktop\n' >>"$repository_dir/hermes-agent/.git/info/exclude"
    printf 'pending\n' >"$repository_dir/hermes-agent/.omarchy-hermes-desktop"
    mv -T --no-clobber "$repository_dir/hermes-agent" "$root"
    [[ ! -e $repository_dir/hermes-agent ]] || die "Keeping the checkout that appeared at $root during installation."
    rmdir "$repository_dir"
  fi

  if [[ $mise_predecessor == true ]]; then
    printf '%s\n' 'pipx:hermes-agent[extras=all]' >"$root/.git/omarchy-mise-predecessor"
  fi

  if [[ $graphical == true ]]; then
    # Existing managed bootstraps may have a runtime but no writable desktop.
    # Seed only the absent app; never replace a newer executable or source.
    if ! desktop_executable >/dev/null; then
      [[ ! -e $root/apps/desktop/release/linux-unpacked ]] || die "Keeping the incomplete desktop at $root/apps/desktop/release/linux-unpacked."
      local desktop_dir
      desktop_dir=$(mktemp -d "$root/.git/omarchy-desktop.XXXXXX")
      cp -a --reflink=auto "$seed/apps/desktop/release/linux-unpacked" "$desktop_dir/"
      chmod -R u+w "$desktop_dir/linux-unpacked"
      mkdir -p "$root/apps/desktop/release"
      mv -T --no-clobber "$desktop_dir/linux-unpacked" "$root/apps/desktop/release/linux-unpacked"
      [[ ! -e $desktop_dir/linux-unpacked ]] || die "Keeping the desktop that appeared during setup."
      rmdir "$desktop_dir"
    fi
    # The GUI owns bootstrap and cancellation. Keep the old launchers as a
    # recovery copy until it succeeds; never race an installer with rollback.
    graphical_existing=false
    if [[ -f $root/.hermes-bootstrap-complete && -x ${cli[0]} ]] &&
      timeout 15 env -u PYTHONPATH -u PYTHONHOME "${cli[0]}" -c 'import yaml; import dotenv; import hermes_cli.config' >/dev/null 2>&1; then
      graphical_existing=true
    fi
    graphical_legacy=$graphical_existing
    graphical_marker=$(stat -c '%d:%i:%y' "$root/.hermes-bootstrap-complete" 2>/dev/null || true)
    printf 'pending\n' >"$marker"
    graphical_setup=true
    trap - EXIT INT TERM
    return
  fi

  if [[ $legacy == false ]]; then
    for command in venv python-deps node-deps config; do stage "$command"; done
  fi
  # The native builder also handles updates and supports the namespace
  # sandbox. The shell installer's desktop stage still requires a sudo chown.
  # The build registers a desktop entry, too. Keep it private until the new
  # CLI is published so a different hermes on PATH cannot become its target.
  env -u PYTHONPATH -u PYTHONHOME XDG_DATA_HOME="$install_backup/desktop" "${cli[@]}" desktop --build-only

  # Build first: a failed download leaves the old terminal CLI usable.
  stage complete
  stage path
  runtime_ready || die "The CLI or desktop is not ready. See the installer output above."
  env -u PYTHONPATH -u PYTHONHOME PATH="$HOME/.local/bin:$PATH" "${cli[@]}" desktop --skip-build --build-only
  if ! grep -qxF '/.omarchy-hermes-desktop' "$root/.git/info/exclude"; then
    printf '/.omarchy-hermes-desktop\n' >>"$root/.git/info/exclude"
  fi
  printf 'ready\n' >"$marker"
  trap - EXIT INT TERM
  rm -rf "$install_backup"
  exec 9>&-
  if [[ -f $root/.git/omarchy-mise-predecessor ]] && command -v omarchy-install-hermes-cli >/dev/null 2>&1; then
    omarchy-install-hermes-cli || echo 'Run omarchy-install-hermes-cli again to finish the old CLI cleanup.' >&2
  fi
  echo "Hermes is ready. Update it in the app or with 'hermes update'."
}

case "${1:-}" in
  --check) ready; exit ;;
  --install) install_desktop; exit ;;
  --setup) shift ;;
esac

graphical_setup=false
if ! ready; then
  install_desktop true
fi

# HERMES_HOME selects the native root. A developer source/Python override
# bypasses GUI bootstrap and falls back to system Python before the venv exists.
unset HERMES_DESKTOP_HERMES_ROOT HERMES_DESKTOP_PYTHON HERMES_DESKTOP_BOOTSTRAP HERMES_DESKTOP_BOOTSTRAP_SEED
export HERMES_DESKTOP_IGNORE_EXISTING=1
if [[ $graphical_setup == true && $graphical_existing == false ]]; then
  # A cancelled first install can already import the CLI, even though it has
  # never completed. The packaged app consumes this one-shot bootstrap request.
  export HERMES_DESKTOP_BOOTSTRAP=1
  seed_receipt="$root/.git/omarchy-desktop-seed"
  if [[ -f $seed_receipt && ! -L $seed_receipt ]] &&
    cmp -s "$seed_receipt" "$seed/.git/omarchy-desktop-seed"; then
    seed_commit=$(cat "$seed_receipt")
    if [[ $seed_commit =~ ^[0-9a-f]{40}$ && $(git -C "$root" rev-parse HEAD) == "$seed_commit" ]]; then
      export HERMES_DESKTOP_BOOTSTRAP_SEED=$seed_commit
    fi
  fi
fi
export HERMES_DESKTOP_PASSWORD_STORE="${HERMES_DESKTOP_PASSWORD_STORE:-gnome-libsecret}"
# Upstream desktop registration resolves its launcher through PATH.
export PATH="$HOME/.local/bin:$PATH"
unset ELECTRON_RUN_AS_NODE PYTHONPATH PYTHONHOME

flags=()
if [[ -n ${WAYLAND_DISPLAY:-} || ${XDG_SESSION_TYPE:-} == "wayland" ]]; then
  flags=(--ozone-platform=wayland)
  for flag in "$@"; do
    case "$flag" in --ozone-platform=* | --ozone-platform-hint=*) flags=() ;; esac
  done
fi

# Disable only the unusable setuid helper; Chromium keeps its namespace sandbox.
if unshare --user --map-root-user true 2>/dev/null; then
  flags+=(--disable-setuid-sandbox)
fi
if [[ $graphical_setup == false ]]; then
  exec "$(desktop_executable)" "${flags[@]}" "$@"
fi

# Keep the installation lock until the GUI's native bootstrap has finished.
# The app gets no lock descriptor: its updater must be able to outlive it.
"$(desktop_executable)" "${flags[@]}" "$@" 9>&- &
app_pid=$!
(
  while kill -0 "$app_pid" 2>/dev/null; do
    # An existing healthy legacy runtime skips GUI bootstrap. Register its
    # admitted CLI shims without reinstalling dependencies or building the app.
    if [[ $graphical_legacy == true ]] &&
      timeout 15 env -u PYTHONPATH -u PYTHONHOME "${cli[@]}" --version >/dev/null 2>&1; then
      stage path
      graphical_legacy=false
    fi
    # Electron adds desktopVersion after the final installer child exits.
    # The installer's earlier marker alone must not finalize a cold GUI setup.
    if { [[ $graphical_existing == true ]] || {
      [[ $(stat -c '%d:%i:%y' "$root/.hermes-bootstrap-complete" 2>/dev/null || true) != "$graphical_marker" ]] && python -I -c '
import json, sys
try:
    assert json.load(open(sys.argv[1])).get("desktopVersion")
except (OSError, ValueError, AssertionError, AttributeError):
    sys.exit(1)
' "$root/.hermes-bootstrap-complete"; }; } && runtime_ready; then
      # Keep the package desktop entry until a real native update builds and
      # stamps the app. A premature `hermes desktop` entry would build on launch.
      printf 'ready\n' >"$marker"
      rm -rf "$install_backup"
      exec 9>&-
      if [[ -f $root/.git/omarchy-mise-predecessor ]] && command -v omarchy-install-hermes-cli >/dev/null 2>&1; then
        omarchy-install-hermes-cli || echo 'Run omarchy-install-hermes-cli again to finish the old CLI cleanup.' >&2
      fi
      exit
    fi
    sleep 2
  done
  echo "Hermes setup did not finish. Previous CLI launchers are preserved in $install_backup." >&2
  echo "Retry in Hermes, or finish setup from a terminal with: hermes-desktop --install" >&2
) &
completion_pid=$!
exec 9>&-
status=0
wait "$app_pid" || status=$?
wait "$completion_pid" || true
exit "$status"
