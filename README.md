# Kejyn Stinger Exporter

A lightweight Windows tool for previewing HTML/CSS/JavaScript stinger transitions and exporting them as transparent WebM files for OBS.

Supports optional audio, custom resolutions, frame rates and export settings.

## Features

- Preview HTML/CSS/JavaScript transitions directly in Chromium
- Export transparent WebM videos for OBS
- VP9 video with alpha transparency
- Optional audio with volume control and fade-out
- Custom resolution, frame rate and duration
- Deterministic frame-by-frame rendering
- Simple Windows interface
- Standalone Windows installer

## Installation

Download the latest Windows installer from the **Releases** section:

```text
KejynStingerExporter-Setup-x.x.x.exe
```

Run the installer, then launch **Kejyn Stinger Exporter** from the Start menu.

No separate Python, Chromium or FFmpeg installation is required.

## Usage

1. Select your HTML file.
2. Select the associated CSS and JavaScript files.
3. Optionally select an audio file.
4. Configure the resolution, FPS, duration and audio settings.
5. Click **Jouer la prévisu** to preview the transition.
6. Click **Exporter en WebM** to generate the final file.
7. Import the resulting `.webm` as a **Stinger Transition** in OBS.

## Transition format

For deterministic frame-by-frame export, the JavaScript transition must expose:

```js
window.renderTransition = renderTransition;
```

The renderer must accept a progress value between `0` and `1`:

```js
function renderTransition(progress) {
    // Render the transition at the requested progress.
}
```

This allows the exporter to render every frame independently instead of recording the animation in real time.

## Development

### Requirements

- Python 3.11+
- Inno Setup 6 — only required to build the Windows installer

### Run from source

```bat
scripts\run_dev.bat
```

### Build the Windows installer

```bat
scripts\build_windows_installer.bat
```

The generated installer will be available in:

```text
release/
```

## Releases

Windows builds are generated automatically through GitHub Actions when a version tag is pushed.

Example:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The resulting installer is automatically attached to the corresponding GitHub Release.

## License

This project is licensed under the **GNU General Public License v3.0**.

See the [LICENSE](LICENSE) file for details.

Copyright © 2026 Kejyn.