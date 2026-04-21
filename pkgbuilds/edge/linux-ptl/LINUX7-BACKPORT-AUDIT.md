# linux-ptl Linux 7 Backport Audit

Audit date: 2026-04-21

Scope:
- Current patch list in `pkgbuilds/edge/linux-ptl/PKGBUILD`
- Panther Lake enablement, display, camera, audio, and related backports
- Upstream comparison target: `torvalds/linux` `master` as the best public proxy for Linux 7

Current limitation:
- Arch Linux has not published a `v7.*-arch1` tag yet, so this branch records the prune plan but does not change the active `linux-ptl` package base.

## Summary

Drop on Linux 7:
- `0001 0002 0003 0004 0005 0007 0008 0010 0012 0013 0014 0018 0026 0027`

Drop `0020` verbatim:
- Most of its intent is already upstream in refactored form.
- If needed, respin only the remaining ALPM hunk after reproducing a Linux 7 regression.

Keep on Linux 7 for now:
- `0017 0019 0022 0028 0029`

Camera backports present in `linux-ptl`:
- None

## Audio

| Patch | Linux 7 verdict | Proof | Snippet |
|---|---|---|---|
| `0001` | Drop. Cleanup-only and upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_functions.c> | `u32 *delay_list __free(kfree) = kcalloc(...)` |
| `0002` | Drop. Jack hookup is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_class_function.c> | `return sdca_jack_set_jack(core->irq_info, jack);` |
| `0003` | Drop. Workqueue refactor is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_ump.c> | `queue_delayed_work(system_dfl_wq, work, ...)` |
| `0004` | Drop. IRQ helpers are upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_interrupts.c> | `sdca_irq_enable_early(...)`, `sdca_irq_enable(...)`, `sdca_irq_disable(...)` |
| `0005` | Drop. System suspend/resume support is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_class.c>, <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_class_function.c> | `SYSTEM_SLEEP_PM_OPS(class_suspend, class_resume)` |
| `0007` | Drop. Init serialization is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_class_function.c> | `guard(mutex)(&drv->core->init_lock);` |
| `0008` | Drop. Cleanup-only and upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_fdl.c>, <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_functions.c> | `sizeof(*fdl_state)`, `sizeof(*control->values)` |
| `0010` | Drop. PM flag is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_class_function.c> | `dev_pm_set_driver_flags(dev, DPM_FLAG_NO_DIRECT_COMPLETE);` |
| `0012` | Drop. Logging-only and upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_fdl.c> | `dev_info(dev, "loading SWF: %x-%x-%x\n", ...)` |
| `0013` | Drop. Reset-default handling is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/include/sound/sdca_function.h>, <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_regmap.c> | `bool has_reset;` |
| `0014` | Drop. Selected-mode guard is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_asoc.c> | `return -EBUSY;` / `return -EINVAL;` |
| `0017` | Keep. Still out-of-tree teardown/jack race fix. | Local patch: `0017-ASoC-SDCA-Fix-NULL-pointer-dereference-in-sdca_jack_.patch`; upstream: <https://github.com/torvalds/linux/blob/master/sound/soc/sdca/sdca_jack.c> | Local: `if (!card || !card->snd_card) return -ENODEV;` Upstream still dereferences `card->snd_card` directly. |

## Display

| Patch | Linux 7 verdict | Proof | Snippet |
|---|---|---|---|
| `0019` | Keep. PTL PSR2 Early Transport acceptance is still missing upstream. | Local patch: `0019-drm-i915-psr-accept-early-transport-for-psr2.patch`; upstream: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_psr.c#L697-L716> | Local: `(y_req || ... == DP_PSR2_WITH_Y_COORD_ET_SUPPORTED)`; upstream still requires `y_req && intel_alpm_aux_wake_supported(...)` |
| `0020` | Drop verbatim. Most logic is upstream/refactored; only one ALPM hunk remains as a real delta. | Upstream: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_psr.c#L1315-L1325>, <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_alpm.c> | Upstream now selects PR vs PSR2 granularity via `crtc_state->has_panel_replay ? connector->dp.panel_replay_caps... : connector->dp.psr_caps...` |
| `0022` | Keep. PSR2+VRR coexistence on PTL is still blocked upstream. | Local patch: `0022-drm-i915-psr-allow-psr-with-vrr-on-ptl.patch`; upstream: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_psr.c#L1718-L1722> | Upstream still has `if (crtc_state->vrr.enable) return false;` |
| `0026` | Drop. Panel Replay full-line SU handling is upstream. | Upstream: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_psr.c#L1315-L1325> | `== DP_PANEL_REPLAY_FULL_LINE_GRANULARITY ? crtc_hdisplay : ...` |
| `0027` | Drop. TRANS_PUSH PR cursor path is upstream/superseded. | Upstream: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_vrr_regs.h#L161-L168>, <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_vrr.c#L693-L709>, <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_crtc.c#L747-L753> | `LNL_TRANS_PUSH_PSR_PR_EN` |
| `0028` | Keep. XPS/LGD OLED Panel Replay ALPM workaround is still local. | Local patch: `0028-drm-i915-psr-exit-Panel-Replay-for-ALPM-lag.patch`; upstream: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/i915/display/intel_frontbuffer.c#L83-L101> | Local adds `intel_psr_panel_replay_exit(display);` before `intel_psr_flush(...)` |
| `0029` | Keep. DisplayID adaptive-sync monitor-range backfill is still missing upstream. | Local patch: `0029-drm-edid-populate-monitor-range-from-displayid-adaptive-sync.patch`; upstream: <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/drm_displayid_internal.h#L66-L71>, <https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/drm_edid.c#L6653-L6667> | Local adds `DATA_BLOCK_2_ADAPTIVE_SYNC` and fills `display_info.monitor_range` |

## Other Panther Lake Enablement

| Patch | Linux 7 verdict | Proof | Snippet |
|---|---|---|---|
| `0018` | Drop. Already upstream in mainline. | Commit: <https://github.com/torvalds/linux/commit/ddaa85feeb15783cf8b4a1a673303f8affb9b155> | `iwl_mld_set_wifi_gen(mld, vif, &cmd->wifi_gen);` |

## Camera

No camera-specific Panther Lake backport patches were found in `linux-ptl`.

Proof:
- `pkgbuilds/edge/linux-ptl/PKGBUILD` only lists ASoC SDCA, `iwlwifi`, and DRM/i915/EDID patches in `source=()`.
- Searching the patch set for `camera`, `ipu6`, `ivsc`, `media`, and `v4l` found no camera/media backport patches.

## Notes For The Actual Linux 7 Rebase

When Arch publishes a `v7.*-arch1` base:
- remove `0001 0002 0003 0004 0005 0007 0008 0010 0012 0013 0014 0018 0026 0027`
- remove `0020` unless the remaining ALPM hunk still reproduces a Linux 7 regression
- keep `0017 0019 0022 0028 0029` until verified upstream or no longer needed on hardware
