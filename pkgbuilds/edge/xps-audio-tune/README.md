# xps-audio-tune

EasyEffects speaker tuning for Dell XPS SoundWire speakers.

The package installs the canonical tuning files into `/usr/share/xps-audio-tune` and provides `xps-audio-tune-apply` to copy them into a user's EasyEffects database at `~/.config/easyeffects/db`.

When installed with `sudo pacman`, the install script applies the config for `$SUDO_USER` automatically. If that is not available, run:

```bash
xps-audio-tune-apply
```

On Omarchy/Hyprland, the apply helper also adds this autostart line when `~/.config/hypr/autostart.conf` exists:

```conf
exec-once = uwsm-app -- easyeffects --service-mode
```

To compare tuned and raw playback:

```bash
easyeffects -b 1  # bypass effects
easyeffects -b 2  # enable effects
```
