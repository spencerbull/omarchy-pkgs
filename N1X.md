# Omarchy N1X bring-up

This branch publishes the experimental September 2026 N1X implementation. The three matching branches are:

- [Kernel and package recipes](https://github.com/spencerbull/omarchy-pkgs/tree/n1x-bringup)
- [Omarchy installer](https://github.com/spencerbull/omarchy/tree/n1x-bringup)
- [AArch64 ISO builder](https://github.com/spencerbull/omarchy-iso/tree/n1x-bringup)

Each fork also has an `n1x-base` branch at the last commit before its N1X snapshot. The pull request from `n1x-bringup` to `n1x-base` shows the N1X changes on top of the earlier GB10/AArch64 foundation; it is not a proposal to merge into upstream or the fork's default branch.

## Recorded hardware status

On September 3, the Dell XPS 16 DX16263 booted the installed system with the panel console and LUKS prompt visible. Kernel `7.0.14-2-n1x` restored the internal keyboard and touchpad after the MediaTek I2C ACPI and GPIO debounce patches. A software-rendered Hyprland desktop ran on SimpleDRM with the NVIDIA stack disabled.

NVIDIA 610.57.04 bound GPU `10de:2e06` but failed to initialize GSP. GPU acceleration, the FF-A embedded-controller interface (battery/lid/thermal/UCSI), invisible hyprlock under software rendering, and automatic rescue-UKI refresh after kernel upgrades remain open in this snapshot. Hardware results are historical; this publication does not claim a new kernel/ISO build or physical retest. The historical `TODO.md` and `N1X_HANDOFF.md` contain earlier entries superseded by their later dated results.

## Kernel recipe

See [`pkgbuilds/linux-n1x`](pkgbuilds/linux-n1x). It builds `linux-n1x` and `linux-n1x-headers` version `7.0.14.nvidia1018-2`, with kernel release `7.0.14-2-n1x`, from NVIDIA source commit `d76db97d0a41dba9bdacca29ff22a0bb511854a9` and signed tag `Ubuntu-nvidia-7.0-7.0.0-1018.18_24.04.1`.

The recipe applies NVIDIA commits `1e2a75fb7d0f925eab94fd32e62fe6147d954ea1` (MediaTek MT8901 I2C / ACPI `NVDA0200`, firmware-managed clocks) and `c8ca6b82aeb7c0bd94f1b76e9c1880255114faed` (warn-only GPIO debounce). It exports the vendor's 4 KiB ARM64 configuration, checks required platform options, and packages the raw ARM64 Image plus modules and DKMS headers.

The signed tag payload **and detached signature** are tracked on this branch. The older snapshot omitted the signature because the repository ignores package `.sig` files; this branch adds a narrow exception for that required input.

Build explicitly from this repository root, preferably on native AArch64, using the repository's documented build environment:

```bash
bin/repo build --arch aarch64 --package linux-n1x
```

The package is excluded from unscoped builds. This is a development kernel; the packaged kernel does not by itself fix the NVIDIA GPU or embedded-controller issues above.
