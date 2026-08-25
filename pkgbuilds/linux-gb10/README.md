# linux-gb10

Arch-style packaging for NVIDIA's public GB10-capable kernel lineage. The
initial source is the maintained NVIDIA/Ubuntu kernel release currently
published in Ubuntu Noble for GB10-class systems:

- Ubuntu source release: `6.17.0-1029.29`
- NVIDIA tag: `Ubuntu-nvidia-6.17-6.17.0-1029.29`
- Signed tag object: `20db7150caa3a91b449cf61aced89e8a70cbbe75`
- Pinned source commit: `aea4c7df51fd59f7717d7668110a803d95c7a3f1`
- Upstream kernel base: `6.17.13`
- Page size: 4 KiB

The package exports NVIDIA's `arm64-nvidia` config directly from the pinned
source tree. This mechanism was first validated against the live Dell Pro Max
GB10 host on `6.17.0-1026.26`; the package advances to Ubuntu's maintained
`1029.29` release rather than freezing the older validation image. `prepare()`
removes Canonical certificate file references that do not exist in an Arch
build, backports NVIDIA's three-line C23 libbpf fix for Arch's current compiler,
runs `olddefconfig`, and fails closed if required GB10 platform options drift.

This package deliberately contains only the in-tree kernel and headers. The
matching NVIDIA open GPU modules, GSP firmware, user-space driver, CUDA, and
container runtime belong in separately version-locked packages. Ubuntu's
current `1029.29` GB10 track pairs the kernel modules, firmware, and user space
at NVIDIA `580.173.02`; the future Omarchy packages must preserve that exact
driver-stack version lock. Do not install or boot this kernel until those
packages and the rollback path are ready.

The package is excluded from unscoped repository builds because it is large
and hardware-specific. Build it explicitly on native aarch64 when possible:

```bash
bin/repo build --arch aarch64 --package linux-gb10
```

The build selects the raw arm64 `Image` and modules explicitly without building
every ARM device tree; GB10 uses ACPI and the package does not ship DTBs. The
raw image is intentional: `CONFIG_EFI_ZBOOT=y` changes the kernel's declared
`image_name` to the PE/COFF-wrapped `vmlinuz.efi`, but Omarchy's installed
system boots through Limine's aarch64 Linux protocol, which requires the native
arm64 Linux image header at offset zero. Parallel compilation is capped at 12
jobs so the same package can also complete under x86_64 QEMU emulation.

Required physical validation includes DRM KMS/Hyprland, CUDA, the in-tree
`r8127` 10 GbE driver, MediaTek Wi-Fi, ConnectX-7 PCIe hotplug and RDMA, warm
reboots, firmware capsules, and kernel rollback.
