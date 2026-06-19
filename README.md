<p align="center"><img src="https://raw.githubusercontent.com/ThatOneDipu/Evera/master/data/icons/hicolor/scalable/apps/io.github.jeffshee.Evera.svg" width="256"></p>

<p align="center">Video wallpaper for Linux. Written in Python.</p>

# Evera

A fork of [Hidamari](https://github.com/jeffshee/hidamari) with an improved dark theme, runtime fixes, and system-level packaging.

## Features 🔥

Evera offers video wallpaper functionality with the following features:

- [x] Autostart after login
- [x] Apply static wallpaper with blur effect <sup>1</sup>
- [x] Detect maximized window and fullscreen mode <sup>2</sup>
- [x] Volume control
- [x] Mute/Pause the playback anytime with just 2 clicks!
- [x] I'm feeling lucky <sup>3</sup>
- [x] Hardware accelerated video decoding! <sup>4</sup>
- [x] Gnome Wayland support!
- [x] Multi-monitor support!
- [x] Streaming URL support! <sup>5</sup>
- [x] Webpage as wallpaper! <sup>6</sup>
- [ ] You name it! =)

<sup>1</sup> Video frame can be applied as system wallpaper, look great in <i>GNOME</i> (currently GNOME exclusive)  
<sup>2</sup> Automatically pauses playback when maximized window or full screen mode is detected (currently X11 only...)  
<sup>3</sup> Randomly select and play a video  
<sup>4</sup> Use <i>vlc</i> as backend (currently HW acceleration doesn't work with Nvidia+Wayland combination...)  
<sup>5</sup> Use <i>yt-dlp</i> as backend, tested with YouTube videos  
<sup>6</sup> Theoretically it can be anything from a normal webpage to <i>Unity/Godot WebGL games</i>, be creative!

## What's different from Hidamari?

- **Renamed to Evera** — all user-facing strings, D-Bus interface, and system identifiers
- **Dark theme redesign** — true black background with electric blue accents, card surfaces, improved readability
- **AyatanaAppIndicator3 support** — works on systems with the newer indicator stack (e.g. Ubuntu 23.10+)
- **GnomeDesktop 3.0 compatibility** — lowered dependency version for broader distro support
- **Graceful ffprobe handling** — no crash when ffprobe is missing
- **Debian packaging** — installable as a system `.deb` package (no Flatpak required)

## Installation ⏬

### Debian/Ubuntu (.deb)

```bash
curl -sL https://github.com/ThatOneDipu/Evera/releases/latest/download/evera_3.6-1_all.deb -o /tmp/evera.deb && sudo dpkg -i /tmp/evera.deb && sudo apt install -f
```

Or download manually from the [releases page](https://github.com/ThatOneDipu/Evera/releases) and install:

```bash
sudo dpkg -i evera_*.deb
sudo apt install -f
```

### Flatpak 📦

```bash
flatpak install flathub io.github.jeffshee.Evera
```

### Build from source

See [docs/development.md](docs/development.md) for build instructions.

## Usage

```bash
evera
```

Or launch in background mode (wallpaper only, no GUI):

```bash
evera -b
```

## Screenshot 📸

![](https://raw.githubusercontent.com/ThatOneDipu/Evera/master/assets/screenshot-1.png)

## Requirements

- Python 3.8+
- VLC
- GTK 3.24+
- libayatana-appindicator (or libappindicator)

## Acknowledgements

- Original project: [Hidamari](https://github.com/jeffshee/hidamari) by [jeffshee](https://github.com/jeffshee)
- Icons made by [Freepik](http://www.freepik.com/) from [Flaticon](https://www.flaticon.com)

## Contributors ✨

<a href="https://github.com/ThatOneDipu/Evera/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=ThatOneDipu/Evera" />
</a>
