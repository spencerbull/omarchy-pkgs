#!/usr/bin/env python3
"""Exercise the packaged entry point with a disposable HOME and installer."""
import json
import os
import pty
import signal
import time
from pathlib import Path
import subprocess
import tempfile
import shutil
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'pkgbuilds/hermes-desktop/hermes-desktop.sh'
INSTALLER = r'''#!/bin/bash
set -eu
while (( $# )); do
  case $1 in --dir) root=$2; shift;; --stage) stage=$2; shift;; esac
  shift
done
printf '%s\n' "$stage" >> "$TEST_LOG"
[[ ${FAIL_STAGE:-} != "$stage" ]] || exit 42
case $stage in
repository)
  mkdir -p "$root/venv/bin"
  git init -q -b main "$root"
  [[ ${FAIL_PARTIAL_CLONE:-} != 1 ]] || exit 44
  git -C "$root" remote add origin https://github.com/NousResearch/hermes-agent.git
  touch "$root/hermes"
  cp "$TEST_PYTHON" "$root/venv/bin/python"
  printf '/venv/\n' >> "$root/.git/info/exclude"
  git -C "$root" add hermes
  git -C "$root" -c user.email=test@example.com -c user.name=Test commit -qm initial
  git -C "$root" update-ref refs/remotes/origin/main HEAD
  if [[ ${RACE_CLONE:-} == 1 ]]; then
    mkdir -p "$HOME/.hermes/hermes-agent"
    printf 'foreign checkout\n' > "$HOME/.hermes/hermes-agent/keep"
  fi
  ;;
complete) touch "$root/.hermes-bootstrap-complete";;
path)
  mkdir -p "$HOME/.local/bin"
  for command in hermes hermes-agent hermes-acp; do
    entry=hermes; suffix=''
    [[ $command != hermes-agent ]] || entry=run_agent.py
    [[ $command != hermes-acp ]] || suffix=' acp'
    printf '#!/usr/bin/env bash\nunset PYTHONPATH\nunset PYTHONHOME\nexec "%s/venv/bin/python" "%s/%s"%s "$@"\n' "$root" "$root" "$entry" "$suffix" > "$HOME/.local/bin/$command"
    chmod +x "$HOME/.local/bin/$command"
  done
  [[ ${FAIL_AFTER_PATH:-} != 1 ]] || exit 43
  ;;
esac
'''

class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hermes-package-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home with spaces'
        self.home.mkdir()
        self.root = self.home / '.hermes/hermes-agent'
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.log = self.base / 'stages'
        self.output = self.base / 'launch.json'
        self.env = dict(os.environ, HOME=str(self.home), HERMES_HOME=str(self.home / '.hermes'),
                        XDG_DATA_HOME=str(self.home / '.local/share'),
                        XDG_CONFIG_HOME=str(self.home / '.config'), XDG_CACHE_HOME=str(self.home / '.cache'),
                        PATH=f'{self.bin}:/usr/bin:/bin', TEST_LOG=str(self.log),
                        TEST_GUI=str(self.base / 'gui'), TEST_PYTHON=str(self.base / 'python'),
                        TEST_OUTPUT=str(self.output), GIT_CONFIG_NOSYSTEM='1',
                        GIT_CONFIG_GLOBAL='/dev/null')
        for k in ['FAIL_STAGE', 'FAIL_AFTER_PATH', 'PYTHONHOME', 'PYTHONPATH']:
            self.env.pop(k, None)
        self.write(self.base / 'installer', INSTALLER)
        self.write(self.base / 'python', '''#!/bin/bash
set -eu
if [[ ${2:-} == desktop ]]; then
  root=$(dirname "$1")
  if [[ ${3:-} == --skip-build ]]; then
    [[ ${4:-} == --build-only && -x $root/apps/desktop/release/linux-unpacked/Hermes ]]
    [[ ${FAIL_FINAL_REGISTER:-} != 1 ]] || exit 45
  else
    [[ ${3:-} == --build-only ]]
    printf 'desktop\\n' >> "$TEST_LOG"
    [[ ${FAIL_STAGE:-} != desktop ]] || exit 42
    mkdir -p "$root/apps/desktop/release/linux-unpacked"
    cp "$TEST_GUI" "$root/apps/desktop/release/linux-unpacked/Hermes"
    printf '/apps/\\n/.hermes-bootstrap-complete\\n' >> "$root/.git/info/exclude"
  fi
  entry_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$entry_dir"
  printf 'Exec=%s desktop\\n' "$(command -v hermes || printf '%s/venv/bin/python -m hermes_cli.main' "$root")" > "$entry_dir/hermes.desktop"
else
  [[ ${FAIL_READY:-} != 1 ]]
fi
''')
        self.write(self.base / 'gui', '''#!/usr/bin/env python3
import json,os,sys,time,subprocess,shutil
json.dump({'pid':os.getpid(),'args':sys.argv[1:],'root':os.path.join(os.environ['HERMES_HOME'],'hermes-agent'),'home':os.environ['HERMES_HOME'],'seed':os.environ.get('HERMES_DESKTOP_BOOTSTRAP_SEED'),'bootstrap':os.environ.get('HERMES_DESKTOP_BOOTSTRAP'),'override':os.environ.get('HERMES_DESKTOP_HERMES_ROOT'),'python_override':os.environ.get('HERMES_DESKTOP_PYTHON'),'node':os.environ.get('ELECTRON_RUN_AS_NODE'),'password':os.environ['HERMES_DESKTOP_PASSWORD_STORE']},open(os.environ['TEST_OUTPUT'],'w'))
if os.environ.get('TEST_BOOTSTRAP'):
    root=__import__('pathlib').Path(os.path.join(os.environ['HERMES_HOME'],'hermes-agent'))
    (root/'venv/bin').mkdir(parents=True,exist_ok=True)
    shutil.copy2(os.environ['TEST_PYTHON'],root/'venv/bin/python')
    for stage in ['path','complete']:
        subprocess.run(['bash',os.environ['TEST_INSTALLER'],'--dir',str(root),'--stage',stage],check=True)
        if stage=='path' and os.environ.get('TEST_BOOTSTRAP_FAIL_LATE'):
            time.sleep(3)
            sys.exit(21)
    (root/'.hermes-bootstrap-complete').write_text(json.dumps({'desktopVersion':'test'}))
if os.environ.get('TEST_BOOTSTRAP') or os.environ.get('TEST_WAIT_READY'):
    root=__import__('pathlib').Path(os.path.join(os.environ['HERMES_HOME'],'hermes-agent'))
    deadline=time.monotonic()+10
    while (root/'.omarchy-hermes-desktop').read_text()!='ready\\n' and time.monotonic()<deadline:
        time.sleep(.05)
if os.environ.get('TEST_GUI_WAIT'): time.sleep(30)
''')
        self.write(self.bin / 'unshare', '#!/bin/bash\nexit 0\n')
        self.write(self.bin / 'xdg-terminal-exec', '#!/bin/bash\nprintf "%s\\n" "$@" > "$TEST_OUTPUT"\n')
        self.seed = self.base / 'seed'
        self.write(self.seed / 'hermes', '')
        self.write(self.seed / '.gitignore', 'apps/desktop/release/\nvenv/\n.hermes-bootstrap-complete\n')
        self.write(self.seed / 'apps/desktop/release/linux-unpacked/Hermes', (self.base / 'gui').read_text())
        for args in [['init','-q','-b','main'],['add','hermes','.gitignore'],['-c','user.email=test@example.com','-c','user.name=Test','commit','-qm','seed'],['remote','add','origin','https://github.com/NousResearch/hermes-agent.git'],['update-ref','refs/remotes/origin/main','HEAD']]:
            subprocess.run(['git','-C',str(self.seed),*args],check=True,env=self.env)
        self.seed_commit=subprocess.check_output(['git','-C',str(self.seed),'rev-parse','HEAD'],env=self.env,text=True).strip()
        (self.seed/'.git/omarchy-desktop-seed').write_text(self.seed_commit+'\n')
        self.env['TEST_INSTALLER'] = str(self.base / 'installer')
        source = SOURCE.read_text().replace('/usr/share/hermes-desktop/install.sh', str(self.base / 'installer'))
        source = source.replace('/usr/share/hermes-desktop/seed', str(self.seed))
        source = source.replace('/usr/bin/hermes-desktop', str(self.base / 'launcher'))
        self.write(self.base / 'launcher', source)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)

    def run_launcher(self, *args, ok=True, **env):
        result = subprocess.run(['bash', str(self.base / 'launcher'), *args], env=self.env | env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(result.returncode == 0, ok, result.stdout)
        return result

    def install(self):
        self.run_launcher('--install')
        self.run_launcher('--check')

    def test_fresh_install_publishes_cli_after_desktop(self):
        self.install()
        stages = self.log.read_text().splitlines()
        self.assertLess(stages.index('desktop'), stages.index('path'))
        self.assertEqual((self.root / '.omarchy-hermes-desktop').read_text(), 'ready\n')
        self.assertEqual(subprocess.check_output(['git','-C',str(self.root),'status','--porcelain'],env=self.env),b'')

    def test_profile_setup_installs_in_machine_home(self):
        profile = self.home / '.hermes/profiles/coder'
        self.write(profile / 'config.yaml', 'profile data\n')
        self.env['HERMES_HOME'] = str(profile) + '/./'
        self.install()
        self.assertEqual((self.root / '.omarchy-hermes-desktop').read_text(), 'ready\n')
        self.assertEqual(list(profile.iterdir()), [profile / 'config.yaml'])
        self.assertEqual((profile / 'config.yaml').read_text(), 'profile data\n')

    def test_profile_warm_check_install_and_launch_share_machine_runtime(self):
        self.install()
        before = self.log.read_bytes()
        self.env['HERMES_HOME'] = str(self.home / '.hermes/profiles/coder')
        self.run_launcher('--check')
        self.run_launcher('--install')
        self.run_launcher('hermes://profile')
        observed = json.loads(self.output.read_text())
        self.assertEqual(observed['root'], str(self.root))
        self.assertEqual(observed['home'], str(self.root.parent))
        self.assertEqual(self.log.read_bytes(), before)

    def test_custom_home_profile_uses_its_own_parent_root(self):
        custom_home = self.base / 'custom data'
        self.root = custom_home / 'hermes-agent'
        self.env['HERMES_HOME'] = str(custom_home / 'profiles/coder')
        self.install()
        self.run_launcher()
        observed = json.loads(self.output.read_text())
        self.assertEqual(observed['root'], str(self.root))
        self.assertEqual(observed['home'], str(custom_home))
        self.assertFalse((self.home / '.hermes').exists())
        self.assertFalse((custom_home / 'profiles').exists())

    def test_custom_home_with_profiles_ancestor_is_preserved(self):
        custom_home = self.base / 'profiles/team/custom data'
        self.root = custom_home / 'hermes-agent'
        self.env['HERMES_HOME'] = str(custom_home)
        self.install()
        self.run_launcher()
        observed = json.loads(self.output.read_text())
        self.assertEqual(observed['root'], str(self.root))
        self.assertEqual(observed['home'], str(custom_home))

    def test_profile_resolution_preserves_symlink_home_spelling(self):
        target = self.base / 'physical data'
        target.mkdir()
        alias = self.base / 'data alias'
        alias.symlink_to(target, target_is_directory=True)
        self.root = alias / 'hermes-agent'
        self.env['HERMES_HOME'] = str(alias / 'profiles/coder')
        self.install()
        self.run_launcher()
        observed = json.loads(self.output.read_text())
        self.assertEqual(observed['root'], str(self.root))
        self.assertEqual(observed['home'], str(alias))
        self.assertTrue(alias.is_symlink())

    def test_filesystem_root_home_is_rejected_before_mutation(self):
        self.write(self.bin / 'mkdir', '#!/bin/bash\nprintf called >> "$TEST_LOG"\nexit 42\n')
        for home in ['/', '/profiles/coder', '/profiles/coder/./']:
            with self.subTest(home=home):
                result = self.run_launcher('--install', ok=False, HERMES_HOME=home)
                self.assertIn('Use a Hermes data directory other than /.', result.stdout)
                self.assertFalse(self.log.exists())

    def test_interrupted_clone_stays_aside_and_retry_succeeds(self):
        self.run_launcher('--install', ok=False, FAIL_PARTIAL_CLONE='1')
        self.assertFalse(self.root.exists())
        partials=list((self.home/'.hermes').glob('.omarchy-hermes-repository.*/hermes-agent/.git'))
        self.assertEqual(len(partials),1)
        self.install()
        self.assertTrue(partials[0].is_dir())

    def test_clone_publication_preserves_concurrent_checkout(self):
        self.run_launcher('--install', ok=False, RACE_CLONE='1')
        self.assertEqual((self.root/'keep').read_text(),'foreign checkout\n')
        self.assertFalse((self.root/'.omarchy-hermes-desktop').exists())
        self.assertFalse((self.home/'.local/bin/hermes').exists())

    def test_desktop_registration_uses_published_cli(self):
        self.write(self.bin/'hermes', '#!/bin/bash\necho foreign\n')
        self.install()
        entry=self.home/'.local/share/applications/hermes.desktop'
        self.assertEqual(entry.read_text(),f'Exec={self.home}/.local/bin/hermes desktop\n')

    def test_failed_registration_preserves_previous_launcher(self):
        wrapper=self.home/'.local/bin/hermes'
        self.write(wrapper,'#!/bin/bash\n# Written by omarchy-install-hermes-cli.\necho old\n')
        entry=self.home/'.local/share/applications/hermes.desktop'
        self.write(entry,'previous desktop entry\n')
        before=wrapper.read_bytes()
        self.run_launcher('--install',ok=False,FAIL_FINAL_REGISTER='1')
        self.assertEqual(wrapper.read_bytes(),before)
        self.assertEqual(entry.read_text(),'previous desktop entry\n')
        self.run_launcher('--check',ok=False)
        self.install()

    def test_warm_launch_and_package_reinstall_leave_runtime_untouched(self):
        self.install()
        before = self.log.read_bytes()
        self.run_launcher('--install')
        self.run_launcher('hermes://test?a=b', 'two words', WAYLAND_DISPLAY='wayland-1', ELECTRON_RUN_AS_NODE='1')
        observed = json.loads(self.output.read_text())
        self.assertEqual(observed['args'], ['--ozone-platform=wayland','--disable-setuid-sandbox','hermes://test?a=b','two words'])
        self.assertEqual(observed['root'],str(self.root))
        self.assertIsNone(observed['node'])
        self.assertEqual(observed['password'],'gnome-libsecret')
        self.assertEqual(before,self.log.read_bytes())

    def test_explicit_platform_and_password_are_preserved(self):
        self.install()
        self.run_launcher('--ozone-platform=x11', WAYLAND_DISPLAY='wayland-1', HERMES_DESKTOP_PASSWORD_STORE='kwallet6')
        result=json.loads(self.output.read_text())
        self.assertNotIn('--ozone-platform=wayland',result['args'])
        self.assertEqual(result['password'],'kwallet6')

    def test_foreign_command_and_symlink_are_preserved(self):
        wrapper=self.home/'.local/bin/hermes'
        self.write(wrapper,'#!/bin/bash\necho custom\n')
        before=wrapper.read_bytes()
        self.run_launcher('--install',ok=False)
        self.assertEqual(before,wrapper.read_bytes())
        self.assertFalse(self.log.exists())
        wrapper.unlink()
        wrapper.symlink_to(self.base/'missing')
        self.run_launcher('--install',ok=False)
        self.assertTrue(wrapper.is_symlink())

    def test_customized_native_wrapper_is_preserved(self):
        self.install()
        wrapper=self.home/'.local/bin/hermes'
        wrapper.write_text(wrapper.read_text().replace('unset PYTHONPATH','export CUSTOM=yes\nunset PYTHONPATH'))
        before=wrapper.read_bytes()
        self.run_launcher('--install',ok=False)
        self.assertEqual(wrapper.read_bytes(),before)

    def test_failed_build_preserves_old_cli_and_retry_succeeds(self):
        wrapper=self.home/'.local/bin/hermes'
        self.write(wrapper,'#!/bin/bash\n# Written by omarchy-install-hermes-cli.\necho old\n')
        before=wrapper.read_bytes()
        self.run_launcher('--install',ok=False,FAIL_STAGE='desktop')
        self.assertEqual(wrapper.read_bytes(),before)
        self.run_launcher('--check',ok=False)
        self.install()
        self.assertNotEqual(wrapper.read_bytes(),before)

    def test_late_path_failure_restores_old_cli(self):
        wrapper=self.home/'.local/bin/hermes'
        self.write(wrapper,'#!/bin/bash\n# Written by omarchy-install-hermes-cli.\necho old\n')
        before=wrapper.read_bytes()
        self.run_launcher('--install',ok=False,FAIL_AFTER_PATH='1')
        self.assertEqual(wrapper.read_bytes(),before)
        self.run_launcher('--check',ok=False)
        self.install()

    def test_dirty_pending_checkout_is_preserved(self):
        self.run_launcher('--install',ok=False,FAIL_STAGE='desktop')
        (self.root/'hermes').write_text('user changes')
        before=self.log.read_bytes()
        self.run_launcher('--install',ok=False)
        self.assertEqual((self.root/'hermes').read_text(),'user changes')
        self.assertEqual(self.log.read_bytes(),before)

    def test_cold_graphical_launch_opens_app_before_runtime_install(self):
        self.run_launcher('hermes://open',HERMES_DESKTOP_HERMES_ROOT='/foreign/source',HERMES_DESKTOP_PYTHON='/foreign/python')
        observed=json.loads(self.output.read_text())
        self.assertIn('hermes://open',observed['args'])
        self.assertEqual(observed['root'],str(self.root))
        self.assertEqual(observed['bootstrap'],'1')
        self.assertEqual(observed['seed'],self.seed_commit)
        self.assertIsNone(observed['override'])
        self.assertIsNone(observed['python_override'])
        self.assertFalse(self.log.exists())
        self.assertFalse((self.root/'venv').exists())
        self.assertEqual((self.root/'.omarchy-hermes-desktop').read_text(),'pending\n')
        self.assertEqual(subprocess.check_output(['git','-C',str(self.root),'status','--porcelain'],env=self.env),b'')
        self.run_launcher('--check',ok=False)

    def test_gui_bootstrap_publishes_readiness_without_replacing_package_entry(self):
        self.run_launcher(TEST_BOOTSTRAP='1')
        self.run_launcher('--check')
        self.assertEqual(self.log.read_text().splitlines(),['path','complete'])
        entry=self.home/'.local/share/applications/hermes.desktop'
        self.assertFalse(entry.exists())
        lock=self.home/'.hermes/.omarchy-hermes-desktop.lock'
        self.assertEqual(subprocess.run(['flock','--nonblock',str(lock),'true']).returncode,0)

    def test_early_gui_cancellation_preserves_predecessor_and_can_retry(self):
        wrapper=self.home/'.local/bin/hermes'
        self.write(wrapper,'#!/bin/bash\n# Written by omarchy-install-hermes-cli.\necho old\n')
        before=wrapper.read_bytes()
        self.run_launcher()
        self.assertEqual(wrapper.read_bytes(),before)
        self.assertEqual((self.root/'.git/omarchy-mise-predecessor').read_text(),'pipx:hermes-agent[extras=all]\n')
        self.run_launcher('--check',ok=False)
        self.run_launcher(TEST_BOOTSTRAP='1')
        self.run_launcher('--check')

    def test_existing_healthy_runtime_gets_prebuilt_app_without_update_or_build(self):
        self.install()
        head=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],env=self.env)
        shutil.rmtree(self.root/'apps/desktop/release/linux-unpacked')
        before=self.log.read_text().splitlines()
        self.run_launcher(TEST_WAIT_READY='1')
        self.run_launcher('--check')
        self.assertEqual(subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],env=self.env),head)
        self.assertNotIn('desktop',self.log.read_text().splitlines()[len(before):])
        self.assertNotIn('repository',self.log.read_text().splitlines()[len(before):])

    def test_a_newer_runtime_does_not_request_seed_repository_skip(self):
        self.run_launcher()
        (self.root/'hermes').write_text('newer upstream source\n')
        for args in [['add','hermes'],['-c','user.email=test@example.com','-c','user.name=Test','commit','-qm','new upstream'],['update-ref','refs/remotes/origin/main','HEAD']]:
            subprocess.run(['git','-C',str(self.root),*args],check=True,env=self.env)
        self.run_launcher(TEST_BOOTSTRAP='1',HERMES_DESKTOP_BOOTSTRAP_SEED=self.seed_commit)
        observed=json.loads(self.output.read_text())
        self.assertIsNone(observed['seed'])
        self.run_launcher('--check')

    def test_incomplete_usable_runtime_requests_graphical_bootstrap_on_retry(self):
        self.run_launcher()
        self.write(self.root/'venv/bin/python',(self.base/'python').read_text())
        self.run_launcher(TEST_BOOTSTRAP='1')
        observed=json.loads(self.output.read_text())
        self.assertEqual(observed['bootstrap'],'1')
        self.run_launcher('--check')

    def test_graphical_repair_preserves_unpublished_committed_source(self):
        self.install()
        (self.root/'hermes').write_text('local committed source\n')
        for args in [['add','hermes'],['-c','user.email=test@example.com','-c','user.name=Test','commit','-qm','local work']]:
            subprocess.run(['git','-C',str(self.root),*args],check=True,env=self.env)
        self.write(self.root/'venv/bin/python','#!/bin/bash\nexit 1\n')
        before=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],env=self.env)
        result=self.run_launcher(ok=False)
        self.assertIn('unpublished commits',result.stdout)
        self.assertFalse(self.output.exists())
        self.assertEqual(subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],env=self.env),before)

    def test_damaged_runtime_does_not_reuse_stale_gui_completion(self):
        self.install()
        (self.root/'.hermes-bootstrap-complete').write_text(json.dumps({'desktopVersion':'old'}))
        self.write(self.root/'venv/bin/python','#!/bin/bash\nexit 1\n')
        self.run_launcher(TEST_BOOTSTRAP='1',TEST_BOOTSTRAP_FAIL_LATE='1',ok=False)
        self.assertEqual((self.root/'.omarchy-hermes-desktop').read_text(),'pending\n')
        self.run_launcher('--check',ok=False)
        self.assertTrue(list((self.home/'.hermes').glob('.omarchy-hermes-launchers.*')))

    def test_graphical_launch_preserves_foreign_wrapper_and_checkout(self):
        wrapper=self.home/'.local/bin/hermes'
        self.write(wrapper,'#!/bin/bash\necho custom\n')
        self.run_launcher(ok=False)
        self.assertFalse(self.root.exists())
        self.assertFalse(self.output.exists())
        self.assertEqual(wrapper.read_text(),'#!/bin/bash\necho custom\n')

    def test_unexecutable_native_cli_is_repaired(self):
        self.install()
        wrapper=self.home/'.local/bin/hermes'
        wrapper.chmod(0o644)
        self.run_launcher('--check',ok=False)
        self.install()
        self.assertTrue(os.access(wrapper,os.X_OK))

    def test_old_cli_ownership_survives_package_only_setup(self):
        wrapper=self.home/'.local/bin/hermes'
        self.write(wrapper,'#!/bin/bash\n# Written by omarchy-install-hermes-cli.\necho old\n')
        self.install()
        receipt=self.root/'.git/omarchy-mise-predecessor'
        self.assertEqual(receipt.read_text(),'pipx:hermes-agent[extras=all]\n')

    def test_cold_launch_from_terminal_still_bootstraps_inside_app(self):
        master,slave=pty.openpty()
        process=subprocess.Popen(['bash',str(self.base/'launcher')],stdin=slave,stdout=slave,stderr=slave,env=self.env | {'TEST_BOOTSTRAP':'1'})
        os.close(slave)
        try:
            self.assertEqual(process.wait(timeout=15),0)
            self.run_launcher('--check')
            self.assertEqual(self.log.read_text().splitlines(),['path','complete'])
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            os.close(master)

    def test_pending_marker_overrides_old_completion(self):
        self.install()
        (self.root/'.omarchy-hermes-desktop').write_text('pending\n')
        self.run_launcher('--check',ok=False)

if __name__=='__main__':
    unittest.main()
