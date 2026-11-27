"""Batch queue preview and dedicated progress dashboard for TextAnimator."""
from __future__ import annotations
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from .batch import TITLE_KEYS, TEXT_KEYS, resolve_resolution
from .config import COLOR_MODES
from .presets import PRESET_NAMES
from .renderer import RenderCancelled

def _value(row, keys, default=""):
    return next((str(row.get(k, "")).strip() for k in keys if row.get(k)), default)

def _number(row, key, default, cast):
    try:
        return cast(row.get(key)) if str(row.get(key, "")).strip() else default
    except (TypeError, ValueError):
        return default

def _boolean(row, key, default):
    v = str(row.get(key, "")).strip().lower()
    if v in {"1", "true", "yes", "on"}: return True
    if v in {"0", "false", "no", "off"}: return False
    return default

def _payload(app, row):
    base = app._gather_batch_params()
    preset = str(row.get("preset") or base["preset_name"]).strip().lower()
    if preset not in PRESET_NAMES: preset = base["preset_name"]
    color = str(row.get("color_mode") or base["color_mode"]).strip()
    if color not in COLOR_MODES: color = base["color_mode"]
    csv_path = Path(app.csv_entry.get().strip()).expanduser()
    bg = str(row.get("bg_image") or base["bg_image_path"] or "").strip() or None
    if bg and not Path(bg).expanduser().is_absolute(): bg = str((csv_path.resolve().parent / bg).resolve())
    if bg and not Path(bg).is_file(): bg = base["bg_image_path"]
    audio_value = str(row.get("audio") or "").strip()
    if audio_value.lower() in {"none", "silent", "off", "-"}: audio = None
    elif audio_value:
        audio_path = Path(audio_value).expanduser()
        if not audio_path.is_absolute(): audio_path = csv_path.resolve().parent / audio_path
        audio = str(audio_path.resolve())
    else: audio = app.batch_fixed_audio_var.get().strip() or None
    transition = str(row.get("transition") or base["transition"]).strip().lower()
    if transition not in {"fade", "cut", "zoom"}: transition = base["transition"]
    return {
        "preset_name": preset, "font_name_or_path": str(row.get("font") or base["font_name_or_path"]),
        "font_size": max(20, _number(row, "font_size", base["font_size"], int)), "color_mode": color,
        "word_duration": max(.2, _number(row, "word_duration", base["word_duration"], float)),
        "gap": max(0., _number(row, "gap", base["gap"], float)),
        "end_hold": max(0., _number(row, "end_hold", base["end_hold"], float)),
        "outline": _boolean(row, "outline", base["outline"]), "shadow": _boolean(row, "shadow", base["shadow"]),
        "outline_width": max(1, min(16, _number(row, "outline_width", base["outline_width"], int))),
        "shadow_offset": max(1, min(24, _number(row, "shadow_offset", base["shadow_offset"], int))),
        "auto_fit_font": _boolean(row, "auto_fit_font", base["auto_fit_font"]),
        "transition": transition,
        "transition_duration": max(0., min(1.5, _number(row, "transition_duration", base["transition_duration"], float))),
        "audio_path": audio,
        "audio_volume": max(0., min(1., _number(row, "audio_volume", base["audio_volume"], float))),
        "audio_fade_in": max(0., _number(row, "audio_fade_in", base["audio_fade_in"], float)),
        "audio_fade_out": max(0., _number(row, "audio_fade_out", base["audio_fade_out"], float)),
        "bg_image_path": bg, "hardware_backend": base["hardware_backend"],
        "size": resolve_resolution(str(row.get("resolution") or ""), base["size"]),
    }

def _selected(app):
    selection = app.tree.selection()
    if not selection: return None, None
    try:
        i = int(selection[0])
        return i, app._batch_rows[i - 1]
    except (ValueError, IndexError): return None, None

def _set_text(app, value):
    app.batch_preview_text.configure(state=tk.NORMAL)
    app.batch_preview_text.delete("1.0", tk.END)
    app.batch_preview_text.insert("1.0", value)
    app.batch_preview_text.configure(state=tk.DISABLED)

def _refresh(app, _event=None):
    i, row = _selected(app)
    if row is None: return
    title, text = _value(row, TITLE_KEYS, f"Row {i}"), _value(row, TEXT_KEYS)
    try:
        p = _payload(app, row)
        w, h = p["size"]
        app.batch_preview_title_var.set(f"ROW {i:02d}  ·  {title}")
        app.batch_preview_meta_var.set(f"{p['preset_name']}  ·  {w} × {h}  ·  {p['font_size']} px")
        app.batch_preview_settings_var.set(
            f"Word: {p['word_duration']:.2f}s   Gap: {p['gap']:.2f}s\n"
            f"Transition: {p['transition']}   ·   Outline: {'On' if p['outline'] else 'Off'}"
            f"   ·   Shadow: {'On' if p['shadow'] else 'Off'}\n"
            f"Audio: {'Selected track' if p['audio_path'] else 'No preview track'}"
        )
    except Exception as exc:
        app.batch_preview_title_var.set(f"ROW {i:02d}  ·  {title}")
        app.batch_preview_meta_var.set(f"Unable to resolve row settings: {exc}")
        app.batch_preview_settings_var.set("Batch defaults will be used where available.")
    _set_text(app, text)

def _render_preview(app):
    if app.is_busy: return
    i, row = _selected(app)
    if row is None:
        messagebox.showinfo("Select a row", "Select a row in the batch queue first."); return
    text = _value(row, TEXT_KEYS)
    if not text:
        messagebox.showwarning("Empty row", "This row has no text to preview."); return
    try: p = _payload(app, row)
    except Exception as exc:
        messagebox.showerror("Preview settings", str(exc)); return
    app._set_busy(True)
    app._set_status(f"Building low-resolution preview for batch row {i}…")
    def worker():
        try:
            path = app.preview_engine.generate(
                text, preset_name=p["preset_name"], font_name_or_path=p["font_name_or_path"],
                font_size=p["font_size"], color_mode=p["color_mode"], word_duration=p["word_duration"],
                gap=p["gap"], end_hold=p["end_hold"], outline=p["outline"], shadow=p["shadow"],
                outline_width=p["outline_width"], shadow_offset=p["shadow_offset"],
                auto_fit_font=p["auto_fit_font"], transition=p["transition"],
                transition_duration=p["transition_duration"], audio_path=p["audio_path"],
                audio_volume=p["audio_volume"], audio_fade_in=p["audio_fade_in"],
                audio_fade_out=p["audio_fade_out"], bg_image_path=p["bg_image_path"],
                hardware_backend=p["hardware_backend"], progress_callback=app._progress_cb)
            app.after(0, lambda path=path: app._open_file(path))
            app.after(0, lambda: app._set_status(f"Preview ready · Batch row {i}"))
        except RenderCancelled:
            app.after(0, lambda: app._set_status("Batch row preview cancelled"))
        except Exception as exc:
            msg = str(exc)
            app.after(0, lambda m=msg: messagebox.showerror("Batch preview error", m))
            app.after(0, lambda m=msg: app._set_status(f"Batch preview error: {m}"))
        finally: app.after(0, lambda: app._set_busy(False))
    threading.Thread(target=worker, daemon=True).start()

def _progress(app, current, total, message):
    def update():
        total = max(0, int(total or 0))
        current = max(0, min(int(current or 0), total)) if total else 0
        pct = int(100 * current / total) if total else 0
        app.batch_progress_bar.configure(value=pct)
        results = app.batch_renderer.last_results
        done = sum(x.get("status") == "done" for x in results)
        skipped = sum(x.get("status") == "skipped" for x in results)
        failed = sum(x.get("status") == "error" for x in results)
        app.batch_counts_var.set(f"{done} rendered  ·  {skipped} skipped  ·  {failed} failed")
        app.batch_progress_text_var.set(f"{pct}%  ·  {current}/{total} items  ·  {message[:85]}")
    app.after(0, update)

def install_batch_ui(app_class):
    """Add batch preview and progress without changing rendering behavior."""
    from . import gui
    old_build, old_load = app_class._build_batch_tab, app_class._load_csv_preview
    old_progress, old_busy, old_run = app_class._progress_cb, app_class._set_busy, app_class._run_batch

    def build(self, notebook):
        old_build(self, notebook)
        host = self.tree.master
        host.columnconfigure(0, weight=3); host.columnconfigure(2, weight=2); host.rowconfigure(0, weight=1)
        panel = gui.ttk.LabelFrame(host, text="  Selected Row Preview  ", padding=10)
        panel.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(10, 0))
        self.batch_preview_title_var = tk.StringVar(value="Select a CSV row")
        gui.ttk.Label(panel, textvariable=self.batch_preview_title_var, font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        self.batch_preview_meta_var = tk.StringVar(value="Choose a row to inspect its content and overrides.")
        gui.ttk.Label(panel, textvariable=self.batch_preview_meta_var, foreground=self._colors["fg_dim"],
                      wraplength=330).pack(anchor=tk.W, pady=(4, 8))
        gui.ttk.Label(panel, text="TEXT CONTENT", font=("Segoe UI", 8, "bold"),
                      foreground=self._colors["fg_dim"]).pack(anchor=tk.W)
        frame = gui.ttk.Frame(panel); frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self.batch_preview_text = tk.Text(frame, height=8, wrap=tk.WORD, relief=tk.FLAT, padx=10, pady=10,
            background=self._colors["bg_input"], foreground=self._colors["fg_primary"],
            insertbackground=self._colors["fg_primary"], font=("Segoe UI", 11))
        scroll = gui.ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.batch_preview_text.yview)
        self.batch_preview_text.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
        self.batch_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.batch_preview_settings_var = tk.StringVar(value="Effective row settings appear here.")
        gui.ttk.Label(panel, textvariable=self.batch_preview_settings_var, foreground=self._colors["fg_secondary"],
                      wraplength=330, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 8))
        self.btn_batch_preview = gui.ttk.Button(panel, text="▶  Render Preview",
            command=lambda: _render_preview(self),
            **({"bootstyle": "info"} if gui._HAS_TTKBOOTSTRAP else {}))
        self.btn_batch_preview.pack(anchor=tk.W)
        self.tree.bind("<<TreeviewSelect>>", lambda event: _refresh(self, event), add="+")

        progress = gui.ttk.LabelFrame(host.master, text="  Batch Progress  ", padding=8)
        progress.pack(fill=tk.X, before=host, pady=(0, 6))
        top = gui.ttk.Frame(progress); top.pack(fill=tk.X)
        self.batch_progress_text_var = tk.StringVar(value="Ready · 0 of 0 items")
        gui.ttk.Label(top, textvariable=self.batch_progress_text_var, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.batch_counts_var = tk.StringVar(value="0 rendered  ·  0 skipped  ·  0 failed")
        gui.ttk.Label(top, textvariable=self.batch_counts_var, foreground=self._colors["fg_dim"]).pack(side=tk.RIGHT)
        self.batch_progress_bar = gui.ttk.Progressbar(progress, orient=tk.HORIZONTAL, mode="determinate",
                                                       maximum=100, value=0)
        self.batch_progress_bar.pack(fill=tk.X, pady=(7, 2))

    def load(self):
        old_load(self)
        rows = getattr(self, "_batch_rows", [])
        children = self.tree.get_children()
        if rows and children:
            self.tree.selection_set(children[0]); self.tree.focus(children[0]); _refresh(self)
        else:
            self.batch_preview_title_var.set("No rows to preview")
            self.batch_preview_meta_var.set("The CSV contains no data rows.")
            self.batch_preview_settings_var.set(""); _set_text(self, "")
        self.batch_progress_bar.configure(value=0)
        self.batch_progress_text_var.set(f"Ready · {len(rows)} rows loaded")
        self.batch_counts_var.set("0 rendered  ·  0 skipped  ·  0 failed")

    def progress(self, current, total, message):
        old_progress(self, current, total, message)
        if getattr(self, "_batch_ui_active", False): _progress(self, current, total, message)

    def busy(self, value):
        old_busy(self, value)
        if not value: self._batch_ui_active = False
        if hasattr(self, "btn_batch_preview"):
            self.btn_batch_preview.configure(state=tk.DISABLED if value else tk.NORMAL)

    def run_batch(self):
        self._batch_ui_active = True
        total = len(getattr(self, "_batch_rows", [])) * max(1, int(self.batch_variants_var.get()))
        if hasattr(self, "batch_progress_bar"):
            self.batch_progress_bar.configure(value=0)
            self.batch_progress_text_var.set(f"0%  ·  0/{total} items")
            self.batch_counts_var.set("0 rendered  ·  0 skipped  ·  0 failed")
        old_run(self)
        if not getattr(self, "is_busy", False): self._batch_ui_active = False

    app_class._build_batch_tab = build
    app_class._load_csv_preview = load
    app_class._progress_cb = progress
    app_class._set_busy = busy
    app_class._run_batch = run_batch
