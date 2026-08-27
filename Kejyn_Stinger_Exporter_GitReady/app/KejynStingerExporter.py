# -*- coding: utf-8 -*-
"""
Kejyn Stinger Exporter
----------------------
Petit outil Windows pour :
- sélectionner un HTML / CSS / JS de transition,
- sélectionner un son optionnel + son volume,
- lancer une prévisualisation dans Chromium,
- exporter un WebM VP9 avec alpha + audio Opus.

Convention d'export :
le JS de transition doit exposer :
    window.renderTransition(progress)
où progress va de 0 à 1.

Le JS actuel de la transition KejynDev le fait déjà.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Kejyn Stinger Exporter"
def app_data_dir() -> Path:
    """Dossier de config utilisateur, compatible installation Windows."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        target = base / "KejynStingerExporter"
    else:
        target = Path.home() / ".kejyn_stinger_exporter"
    target.mkdir(parents=True, exist_ok=True)
    return target


def runtime_base_dir() -> Path:
    """
    Dossier réel de l'application.
    - En mode PyInstaller onedir : dossier contenant l'EXE.
    - En développement : dossier du fichier Python.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_bundled_playwright() -> None:
    """
    L'installateur place Chromium dans {app}\\browsers.
    On dit à Playwright d'utiliser ce bundle local.
    """
    bundled = runtime_base_dir() / "browsers"
    if bundled.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)


configure_bundled_playwright()

SETTINGS_FILE = app_data_dir() / "settings.json"


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def local_file_to_data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def inject_sources(html_text: str, css_text: str, js_text: str, css_path: Path, js_path: Path, audio_path: Path | None) -> str:
    """
    Construit un HTML autonome :
    - le CSS choisi est injecté dans <style>,
    - le JS choisi est injecté dans <script>,
    - le son choisi est injecté en data URI dans #transition-sound.
    """

    html = html_text

    # Supprime uniquement le link stylesheet correspondant au CSS sélectionné.
    css_name = re.escape(css_path.name)
    html = re.sub(
        rf'<link\b(?=[^>]*\bhref\s*=\s*["\'][^"\']*{css_name}["\'])[^>]*>',
        "",
        html,
        flags=re.IGNORECASE,
    )

    # Supprime uniquement le script src correspondant au JS sélectionné.
    js_name = re.escape(js_path.name)
    html = re.sub(
        rf'<script\b(?=[^>]*\bsrc\s*=\s*["\'][^"\']*{js_name}["\'])[^>]*>\s*</script>',
        "",
        html,
        flags=re.IGNORECASE,
    )

    style_block = f"\n<style>\n{css_text}\n</style>\n"
    if re.search(r"</head\s*>", html, flags=re.IGNORECASE):
        html = re.sub(r"</head\s*>", style_block + "</head>", html, count=1, flags=re.IGNORECASE)
    else:
        html = style_block + html

    if audio_path:
        data_uri = local_file_to_data_uri(audio_path)
        audio_tag = (
            f'<audio id="transition-sound" preload="auto" '
            f'src="{data_uri}"></audio>'
        )

        # Remplace l'élément audio existant s'il existe.
        audio_pattern = re.compile(
            r'<audio\b(?=[^>]*\bid\s*=\s*["\']transition-sound["\'])[^>]*>.*?</audio>',
            flags=re.IGNORECASE | re.DOTALL,
        )

        if audio_pattern.search(html):
            html = audio_pattern.sub(audio_tag, html, count=1)
        else:
            if re.search(r"</body\s*>", html, flags=re.IGNORECASE):
                html = re.sub(
                    r"</body\s*>",
                    "\n" + audio_tag + "\n</body>",
                    html,
                    count=1,
                    flags=re.IGNORECASE,
                )
            else:
                html += "\n" + audio_tag
    else:
        # S'il n'y a pas de son choisi, on neutralise la source locale éventuelle,
        # mais on garde l'élément pour ne pas casser le JS.
        html = re.sub(
            r'(<audio\b(?=[^>]*\bid\s*=\s*["\']transition-sound["\'])[^>]*?)\s+src\s*=\s*["\'][^"\']*["\']',
            r"\1",
            html,
            flags=re.IGNORECASE,
        )
        html = re.sub(
            r'(<audio\b(?=[^>]*\bid\s*=\s*["\']transition-sound["\'])[^>]*>).*?(</audio>)',
            r"\1\2",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Injecte le JS juste avant </body>.
    # </script> est extrêmement rare dans un JS de transition ; on le neutralise au cas où.
    safe_js = js_text.replace("</script>", "<\\/script>")
    script_block = f"\n<script>\n{safe_js}\n</script>\n"

    if re.search(r"</body\s*>", html, flags=re.IGNORECASE):
        html = re.sub(
            r"</body\s*>",
            script_block + "</body>",
            html,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        html += script_block

    return html


class StingerExporterApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("900x705")
        self.minsize(820, 650)

        self.preview_running = False
        self.export_running = False

        self.html_var = tk.StringVar()
        self.css_var = tk.StringVar()
        self.js_var = tk.StringVar()
        self.audio_var = tk.StringVar()

        self.volume_var = tk.DoubleVar(value=65)
        self.width_var = tk.IntVar(value=1920)
        self.height_var = tk.IntVar(value=1080)
        self.fps_var = tk.IntVar(value=60)
        self.duration_var = tk.IntVar(value=1800)
        self.fade_var = tk.IntVar(value=250)
        self.crf_var = tk.IntVar(value=18)

        self.status_var = tk.StringVar(value="Prêt.")
        self.progress_var = tk.DoubleVar(value=0)

        self._build_ui()
        self._load_settings()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(
            outer,
            text="Kejyn Stinger Exporter",
            font=("Segoe UI", 17, "bold"),
        )
        title.pack(anchor="w")

        subtitle = ttk.Label(
            outer,
            text="Prévisualise ton HTML/CSS/JS puis exporte un WebM transparent prêt pour OBS.",
        )
        subtitle.pack(anchor="w", pady=(2, 14))

        files = ttk.LabelFrame(outer, text="Sources", padding=12)
        files.pack(fill="x")

        self._file_row(files, 0, "HTML", self.html_var, [("HTML", "*.html;*.htm"), ("Tous les fichiers", "*.*")])
        self._file_row(files, 1, "CSS", self.css_var, [("CSS", "*.css"), ("Tous les fichiers", "*.*")])
        self._file_row(files, 2, "JS", self.js_var, [("JavaScript", "*.js"), ("Tous les fichiers", "*.*")])
        self._file_row(
            files,
            3,
            "Son (optionnel)",
            self.audio_var,
            [
                ("Audio", "*.mp3;*.wav;*.ogg;*.m4a;*.aac;*.flac"),
                ("Tous les fichiers", "*.*"),
            ],
            allow_clear=True,
        )

        settings = ttk.LabelFrame(outer, text="Export", padding=12)
        settings.pack(fill="x", pady=(12, 0))

        for c in range(8):
            settings.columnconfigure(c, weight=1 if c % 2 else 0)

        ttk.Label(settings, text="Largeur").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(settings, from_=320, to=7680, textvariable=self.width_var, width=9).grid(row=0, column=1, sticky="ew", padx=(6, 18))

        ttk.Label(settings, text="Hauteur").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(settings, from_=240, to=4320, textvariable=self.height_var, width=9).grid(row=0, column=3, sticky="ew", padx=(6, 18))

        ttk.Label(settings, text="FPS").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(settings, from_=1, to=240, textvariable=self.fps_var, width=8).grid(row=0, column=5, sticky="ew", padx=(6, 18))

        ttk.Label(settings, text="Durée (ms)").grid(row=0, column=6, sticky="w")
        ttk.Spinbox(settings, from_=100, to=30000, increment=50, textvariable=self.duration_var, width=10).grid(row=0, column=7, sticky="ew", padx=(6, 0))

        ttk.Label(settings, text="Volume son (%)").grid(row=1, column=0, sticky="w", pady=(12, 0))
        volume_frame = ttk.Frame(settings)
        volume_frame.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 18), pady=(12, 0))
        volume_frame.columnconfigure(0, weight=1)
        ttk.Scale(volume_frame, from_=0, to=100, variable=self.volume_var).grid(row=0, column=0, sticky="ew")
        ttk.Label(volume_frame, textvariable=self.volume_var, width=5).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(settings, text="Fade audio fin (ms)").grid(row=1, column=4, sticky="w", pady=(12, 0))
        ttk.Spinbox(settings, from_=0, to=5000, increment=50, textvariable=self.fade_var, width=9).grid(row=1, column=5, sticky="ew", padx=(6, 18), pady=(12, 0))

        ttk.Label(settings, text="Qualité VP9 (CRF)").grid(row=1, column=6, sticky="w", pady=(12, 0))
        ttk.Spinbox(settings, from_=0, to=63, textvariable=self.crf_var, width=9).grid(row=1, column=7, sticky="ew", padx=(6, 0), pady=(12, 0))

        hint = ttk.Label(
            settings,
            text="CRF 18 = très propre. Plus bas = meilleure qualité / fichier plus lourd.",
            foreground="#666666",
        )
        hint.grid(row=2, column=0, columnspan=8, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(14, 0))

        self.preview_button = ttk.Button(
            buttons,
            text="▶  Jouer la prévisu",
            command=self.preview,
        )
        self.preview_button.pack(side="left")

        self.export_button = ttk.Button(
            buttons,
            text="⬇  Exporter en WebM",
            command=self.export_webm,
        )
        self.export_button.pack(side="left", padx=(10, 0))

        ttk.Button(
            buttons,
            text="Ouvrir le dossier source",
            command=self.open_source_folder,
        ).pack(side="right")

        progress = ttk.Progressbar(
            outer,
            maximum=100,
            variable=self.progress_var,
        )
        progress.pack(fill="x", pady=(16, 5))

        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w")

        log_frame = ttk.LabelFrame(outer, text="Journal", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.log_text = tk.Text(
            log_frame,
            height=10,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True)

    def _file_row(self, parent, row, label, variable, filetypes, allow_clear=False):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text=label, width=16).grid(row=row, column=0, sticky="w", pady=4)

        ttk.Entry(parent, textvariable=variable).grid(
            row=row,
            column=1,
            sticky="ew",
            padx=(8, 8),
            pady=4,
        )

        def browse():
            initial = self._initial_dir()
            path = filedialog.askopenfilename(
                title=f"Sélectionner {label}",
                initialdir=initial,
                filetypes=filetypes,
            )
            if path:
                variable.set(path)
                self._autofill_related_files(label, Path(path))
                self._save_settings()

        ttk.Button(parent, text="Parcourir…", command=browse).grid(row=row, column=2, pady=4)

        if allow_clear:
            ttk.Button(parent, text="✕", width=3, command=lambda: variable.set("")).grid(row=row, column=3, padx=(6, 0), pady=4)

    # ------------------------------------------------------------------
    # Paths/settings
    # ------------------------------------------------------------------

    def _initial_dir(self):
        for var in (self.html_var, self.css_var, self.js_var, self.audio_var):
            value = var.get().strip()
            if value and Path(value).exists():
                return str(Path(value).parent)
        return str(Path.home())

    def _autofill_related_files(self, label: str, selected: Path):
        # Petit confort : si l'utilisateur choisit transition.html,
        # on tente transition.css / transition.js dans le même dossier.
        if label == "HTML":
            css = selected.with_suffix(".css")
            js = selected.with_suffix(".js")

            if css.exists() and not self.css_var.get().strip():
                self.css_var.set(str(css))

            if js.exists() and not self.js_var.get().strip():
                self.js_var.set(str(js))

    def _load_settings(self):
        try:
            if not SETTINGS_FILE.exists():
                return

            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))

            self.html_var.set(data.get("html", ""))
            self.css_var.set(data.get("css", ""))
            self.js_var.set(data.get("js", ""))
            self.audio_var.set(data.get("audio", ""))

            self.volume_var.set(data.get("volume", 65))
            self.width_var.set(data.get("width", 1920))
            self.height_var.set(data.get("height", 1080))
            self.fps_var.set(data.get("fps", 60))
            self.duration_var.set(data.get("duration", 1800))
            self.fade_var.set(data.get("fade", 250))
            self.crf_var.set(data.get("crf", 18))

        except Exception:
            pass

    def _save_settings(self):
        try:
            data = {
                "html": self.html_var.get(),
                "css": self.css_var.get(),
                "js": self.js_var.get(),
                "audio": self.audio_var.get(),
                "volume": float(self.volume_var.get()),
                "width": int(self.width_var.get()),
                "height": int(self.height_var.get()),
                "fps": int(self.fps_var.get()),
                "duration": int(self.duration_var.get()),
                "fade": int(self.fade_var.get()),
                "crf": int(self.crf_var.get()),
            }
            SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def log(self, text):
        def write():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text.rstrip() + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.after(0, write)

    def set_status(self, text, progress=None):
        def update():
            self.status_var.set(text)
            if progress is not None:
                self.progress_var.set(progress)

        self.after(0, update)

    def _validate_inputs(self):
        html = Path(self.html_var.get().strip())
        css = Path(self.css_var.get().strip())
        js = Path(self.js_var.get().strip())
        audio_text = self.audio_var.get().strip()
        audio = Path(audio_text) if audio_text else None

        missing = []
        for name, path in (("HTML", html), ("CSS", css), ("JS", js)):
            if not path.is_file():
                missing.append(name)

        if missing:
            raise ValueError("Fichier(s) manquant(s) : " + ", ".join(missing))

        if audio and not audio.is_file():
            raise ValueError("Le fichier audio sélectionné n'existe pas.")

        width = int(self.width_var.get())
        height = int(self.height_var.get())
        fps = int(self.fps_var.get())
        duration_ms = int(self.duration_var.get())
        fade_ms = int(self.fade_var.get())
        crf = int(self.crf_var.get())
        volume = float(self.volume_var.get())

        if width <= 0 or height <= 0:
            raise ValueError("La résolution doit être positive.")
        if fps <= 0:
            raise ValueError("Les FPS doivent être supérieurs à 0.")
        if duration_ms <= 0:
            raise ValueError("La durée doit être supérieure à 0.")

        return {
            "html": html,
            "css": css,
            "js": js,
            "audio": audio,
            "width": width,
            "height": height,
            "fps": fps,
            "duration_ms": duration_ms,
            "fade_ms": max(0, fade_ms),
            "crf": int(clamp(crf, 0, 63)),
            "volume": clamp(volume, 0, 100) / 100.0,
        }

    def _build_standalone_html(self, config, destination: Path):
        html_text = config["html"].read_text(encoding="utf-8-sig")
        css_text = config["css"].read_text(encoding="utf-8-sig")
        js_text = config["js"].read_text(encoding="utf-8-sig")

        standalone = inject_sources(
            html_text,
            css_text,
            js_text,
            config["css"],
            config["js"],
            config["audio"],
        )

        destination.write_text(standalone, encoding="utf-8")

    def _on_close(self):
        self._save_settings()
        self.destroy()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview(self):
        if self.preview_running:
            messagebox.showinfo(APP_NAME, "Une prévisualisation est déjà ouverte.")
            return

        try:
            config = self._validate_inputs()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return

        self._save_settings()
        self.preview_running = True
        self.preview_button.configure(state="disabled")

        threading.Thread(
            target=self._preview_worker,
            args=(config,),
            daemon=True,
        ).start()

    def _preview_worker(self, config):
        temp_dir = Path(tempfile.mkdtemp(prefix="kejyn_stinger_preview_"))

        try:
            from playwright.sync_api import sync_playwright

            preview_html = temp_dir / "preview.html"
            self._build_standalone_html(config, preview_html)

            self.log("Prévisualisation : lancement de Chromium…")
            self.set_status("Prévisualisation ouverte.")

            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(
                        headless=False,
                        args=[
                            f'--window-size={config["width"]},{config["height"]}',
                            "--autoplay-policy=no-user-gesture-required",
                        ],
                    )
                except Exception as exc:
                    raise RuntimeError(
                        "Chromium Playwright n'est pas installé.\n"
                        "Lance install.bat une fois, puis réessaie."
                    ) from exc

                context = browser.new_context(
                    viewport={
                        "width": config["width"],
                        "height": config["height"],
                    },
                    device_scale_factor=1,
                )

                page = context.new_page()

                # On passe le volume au JS via l'élément audio lui-même.
                page.goto(preview_html.as_uri(), wait_until="load")
                page.evaluate(
                    """(v) => {
                        const a = document.getElementById('transition-sound');
                        if (a) a.volume = v;
                    }""",
                    config["volume"],
                )

                # Déclenche le replay prévu dans le HTML/JS actuel.
                # Avec l'argument Chromium ci-dessus, le son part également.
                page.mouse.click(
                    config["width"] // 2,
                    config["height"] // 2,
                )

                self.log("Prévisualisation lancée. Ferme la fenêtre Chromium quand tu as fini.")

                # Attend que l'utilisateur ferme Chromium.
                try:
                    page.wait_for_event("close", timeout=0)
                except Exception:
                    pass

                try:
                    browser.close()
                except Exception:
                    pass

        except Exception as exc:
            self.log(traceback.format_exc())
            self.after(
                0,
                lambda: messagebox.showerror(APP_NAME, str(exc)),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.preview_running = False
            self.after(0, lambda: self.preview_button.configure(state="normal"))
            self.set_status("Prêt.")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_webm(self):
        if self.export_running:
            return

        try:
            config = self._validate_inputs()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return

        default_name = config["html"].stem + "_stinger.webm"

        output = filedialog.asksaveasfilename(
            title="Exporter le Stinger WebM",
            defaultextension=".webm",
            initialdir=str(config["html"].parent),
            initialfile=default_name,
            filetypes=[("WebM", "*.webm")],
        )

        if not output:
            return

        config["output"] = Path(output)

        self._save_settings()
        self.export_running = True
        self.export_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.progress_var.set(0)

        threading.Thread(
            target=self._export_worker,
            args=(config,),
            daemon=True,
        ).start()

    def _export_worker(self, config):
        temp_dir = Path(tempfile.mkdtemp(prefix="kejyn_stinger_export_"))
        frames_dir = temp_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        try:
            from playwright.sync_api import sync_playwright
            import imageio_ffmpeg

            standalone_html = temp_dir / "render.html"
            self._build_standalone_html(config, standalone_html)

            fps = config["fps"]
            duration_s = config["duration_ms"] / 1000.0
            total_frames = max(2, round(duration_s * fps))

            self.log(
                f"Export : {config['width']}×{config['height']} / "
                f"{fps} FPS / {config['duration_ms']} ms / {total_frames} frames"
            )
            self.set_status("Rendu des frames…", 0)

            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True)
                except Exception as exc:
                    raise RuntimeError(
                        "Chromium Playwright n'est pas installé.\n"
                        "Lance install.bat une fois, puis réessaie."
                    ) from exc

                context = browser.new_context(
                    viewport={
                        "width": config["width"],
                        "height": config["height"],
                    },
                    device_scale_factor=1,
                )
                page = context.new_page()

                # frame/total force le mode statique du JS actuel et évite
                # qu'une animation requestAnimationFrame tourne en parallèle.
                uri = standalone_html.as_uri() + f"?frame=0&total={total_frames}"
                page.goto(uri, wait_until="load")

                try:
                    page.wait_for_function(
                        "() => window.__FRAME_READY__ === true || typeof window.renderTransition === 'function'",
                        timeout=5000,
                    )
                except Exception:
                    pass

                has_renderer = page.evaluate(
                    "() => typeof window.renderTransition === 'function'"
                )

                if not has_renderer:
                    raise RuntimeError(
                        "Le JS sélectionné n'expose pas window.renderTransition(progress).\n\n"
                        "La transition KejynDev actuelle le fait déjà. "
                        "Pour un autre projet, ajoute cette fonction d'export."
                    )

                # Laisse les polices finir de charger.
                try:
                    page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
                except Exception:
                    pass

                for i in range(total_frames):
                    progress = i / (total_frames - 1)

                    page.evaluate(
                        "(p) => window.renderTransition(p)",
                        progress,
                    )

                    frame_path = frames_dir / f"frame_{i:05d}.png"

                    page.screenshot(
                        path=str(frame_path),
                        omit_background=True,
                        animations="disabled",
                    )

                    pct = ((i + 1) / total_frames) * 82.0
                    if i == 0 or (i + 1) % max(1, total_frames // 20) == 0 or i == total_frames - 1:
                        self.set_status(
                            f"Rendu des frames… {i + 1}/{total_frames}",
                            pct,
                        )

                browser.close()

            self.set_status("Encodage WebM VP9 + alpha…", 86)
            self.log("Frames terminées. Encodage VP9…")

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

            output = config["output"]
            output.parent.mkdir(parents=True, exist_ok=True)

            cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(fps),
                "-i",
                str(frames_dir / "frame_%05d.png"),
            ]

            if config["audio"]:
                cmd += ["-i", str(config["audio"])]

            # Vidéo : VP9 avec canal alpha pour OBS.
            video_args = [
                "-map",
                "0:v:0",
                "-c:v",
                "libvpx-vp9",
                "-pix_fmt",
                "yuva420p",
                "-auto-alt-ref",
                "0",
                "-b:v",
                "0",
                "-crf",
                str(config["crf"]),
            ]

            if config["audio"]:
                volume = config["volume"]
                fade_s = min(config["fade_ms"] / 1000.0, duration_s)
                filters = [f"volume={volume:.6f}"]

                if fade_s > 0:
                    fade_start = max(0.0, duration_s - fade_s)
                    filters.append(
                        f"afade=t=out:st={fade_start:.6f}:d={fade_s:.6f}"
                    )

                audio_filter = ",".join(filters)

                cmd += [
                    "-filter_complex",
                    f"[1:a]{audio_filter}[aout]",
                ]

                cmd += video_args

                cmd += [
                    "-map",
                    "[aout]",
                    "-c:a",
                    "libopus",
                    "-b:a",
                    "160k",
                ]
            else:
                cmd += video_args
                cmd += ["-an"]

            # Force la durée exacte de la transition.
            cmd += [
                "-t",
                f"{duration_s:.6f}",
                str(output),
            ]

            self.log("Commande FFmpeg prête.")
            subprocess.run(
                cmd,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )

            self.set_status("Export terminé.", 100)
            self.log(f"OK : {output}")

            self.after(
                0,
                lambda: messagebox.showinfo(
                    APP_NAME,
                    f"WebM exporté avec succès :\n\n{output}",
                ),
            )

        except subprocess.CalledProcessError as exc:
            self.log(traceback.format_exc())
            self.after(
                0,
                lambda: messagebox.showerror(
                    APP_NAME,
                    "FFmpeg a échoué pendant l'encodage.\n"
                    "Regarde le journal de l'application.",
                ),
            )
            self.set_status("Erreur d'encodage.", 0)

        except Exception as exc:
            self.log(traceback.format_exc())
            self.after(
                0,
                lambda: messagebox.showerror(APP_NAME, str(exc)),
            )
            self.set_status("Erreur.", 0)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.export_running = False
            self.after(
                0,
                lambda: (
                    self.export_button.configure(state="normal"),
                    self.preview_button.configure(state="normal"),
                ),
            )

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def open_source_folder(self):
        value = self.html_var.get().strip()
        if not value:
            return

        path = Path(value)
        folder = path.parent if path.suffix else path

        try:
            if hasattr(__import__("os"), "startfile"):
                __import__("os").startfile(folder)
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))


if __name__ == "__main__":
    app = StingerExporterApp()
    app.mainloop()
