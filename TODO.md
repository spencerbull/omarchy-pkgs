# linux-gb10 workstream

## Goal

Add an aarch64 `linux-gb10` kernel package, modeled on `linux-ptl`, that
repackages NVIDIA's public GB10-capable kernel lineage for a future native
Omarchy installation.

## Done criteria for this workstream

- `pkgbuilds/linux-gb10` has reproducible, pinned upstream sources.
- The package builds only for `aarch64` and produces `linux-gb10` plus
  `linux-gb10-headers` using Arch kernel filesystem conventions.
- The build uses the qualified 4 KiB ARM64 configuration and fails closed if
  required GB10 platform options drift.
- Kernel packaging remains separate from the version-matched NVIDIA open GPU
  modules, GSP firmware, and user-space driver packages.
- Static checks, source verification, config preparation, and the furthest
  practical package build pass locally.
- An independent review identifies no unresolved package-structure blockers.

## Worktree and branch

- Worktree: `/home/sbull/omarchy-repos/omarchy-pkgs-linux-gb10`
- Branch: `linux-gb10`
- Base: `upstream/master` at `c409cb6`
- Canonical checkout: `/home/sbull/omarchy-repos/omarchy-pkgs` (do not edit)

## Allowed actions

- Edit only this worktree.
- Read Coleman and public upstream sources without changing them.
- Download sources and build unsigned local packages.
- Use temporary directories for source inspection and build artifacts.

## Forbidden actions

- Do not install or boot the kernel on Coleman or the local host.
- Do not change firmware, EFI state, boot entries, services, or hardware.
- Do not publish packages, sign repository artifacts, commit, push, or open a
  pull request without explicit authorization.
- Do not edit the Omarchy source repository in this workstream.

## Required checks

- `bash -n pkgbuilds/linux-gb10/PKGBUILD`
- Parse package metadata for `aarch64` through the repository build tooling.
- Verify pinned source integrity and provenance.
- Run kernel config preparation and assert required GB10 options.
- Build `linux-gb10` and `linux-gb10-headers` if resources permit.
- Inspect `git diff --check` and the complete final diff.

## Workers

- `gb10_kernel_research` (Codex, Herdr pane `wY:pN`): read-only NVIDIA kernel,
  config, licensing, and driver-boundary research. The worker incorrectly
  removed orchestrator-owned untracked files after misclassifying them as its
  own artifacts; the orchestrator stopped it and restored the files from the
  recorded diff. Cleanup owner: orchestrator.
- `finn_gb10_build` (Codex, Herdr tab `wY:t7`, pane `wY:pS`): durable remote
  build stream. Cwd/worktree/branch:
  `/home/sbull/omarchy-repos/omarchy-pkgs-linux-gb10`, `linux-gb10`; remote
  target: `dell@finn`, isolated clone
  `/home/dell/omarchy-repos/omarchy-pkgs-linux-gb10`. Authorized to build only
  `linux-gb10`, verify artifacts, activate Finn's existing `/mnt/Batuu` fstab
  mount if needed, and copy into a new commit-addressed NAS directory. It must
  not edit Finn's existing Omarchy checkout, install or boot packages, sign or
  publish artifacts, edit mount configuration, or overwrite NAS files. The
  first attempt reached kernel compilation, then failed after 333 seconds when
  several QEMU-emulated GCC processes segfaulted during 24-way compilation of
  unused ARM DTBs. No artifacts or NAS writes resulted; a targeted package
  correction removed DTBs and capped jobs at 12. The second attempt still
  produced unrelated GCC SIGSEGVs, proving Finn's 2023 QEMU registration was
  the remaining cause; it was stopped after 560 seconds with no artifacts or
  NAS writes. QEMU 10.2.3 then passed a 240-object, 12-way ARM64 compiler stress
  test. The next retry compiled the kernel and all 8,257 modules successfully,
  then failed in `package_linux-gb10()` after 13,373 seconds because the build
  omitted the `vmlinuz.efi` target required by `CONFIG_EFI_ZBOOT=y`; no package
  artifacts or NAS writes resulted. The package now builds that explicit target
  while continuing to skip DTBs. The final build at commit `e200817` completed
  successfully in 13,769 seconds, produced the runtime and headers packages,
  verified their metadata and archive contents, and copied both packages, the
  checksum manifest, and the build log without overwrite to the commit-addressed
  Batuu directory. The orchestrator independently rechecked all source/NAS
  hashes. Cleanup owner: orchestrator.

## Checkpoints and open questions

- [x] Pin signed tag `Ubuntu-nvidia-6.17-6.17.0-1029.29`, peeled commit
      `aea4c7df51fd59f7717d7668110a803d95c7a3f1`, and verified archive hashes.
- [x] Export the 4 KiB `arm64-nvidia` config from NVIDIA's annotations and
      verify the package's fail-closed platform assertions under aarch64.
- [x] Establish which GB10 platform drivers are in-tree versus separately
      packaged.
- [x] Implement and statically validate `linux-gb10` packaging.
- [x] Run the aarch64 build under QEMU through source verification, config
      preparation, the C23 libbpf backport, host-tool compilation, and early
      kernel/module objects. The vendor config enables 8,031 modules; emulation
      produced 179 objects in roughly nine minutes, so the full clean package
      build moves to a native GB10 builder.
- [x] Independent review found one medium source-authenticity gap. Remediated by
      verifying Canonical's original detached signed-tag payload in `makepkg`
      and failing `prepare()` unless it binds the expected tag to `_commit`;
      reviewer follow-up verdict: `FIXED`.
- [x] Commit package-only scope as `3834b6943dfc22fc5eae919662cac3741a3b4f25`
      and push branch `linux-gb10` to `spencerbull/omarchy-pkgs`.
- [x] Complete Finn's aarch64 build, verify the resulting package artifacts,
      and copy them without overwrite to the mounted Batuu NAS share.
