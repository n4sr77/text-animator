"""Embedded video preview popup for batch-render samples.

Uses the FFmpeg executable already bundled by imageio-ffmpeg and Pillow, so
no separate codec installation or additional runtime dependency is required.
"""
from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import imageio_ffmpeg
from PIL import Image, ImageTk


class BatchVideoPreviewWindow:
    """Small in-app MP4 player using TextAnimator's bundled FFmpeg binary."""

    FRAME_WIDTH = 900
    FRAME_HEIGHT = 506

    def __init__(self, app, path):
        self.app = app
        self.path = str(Path(path).resolve())
        self.window = tk.Toplevel(app)
        self.window.title("TextAnimator · Batch Video Preview")
        self.window.geometry("1000x700")
        self.window.minsize(760, 560)
        self.window.configure(background="#111827")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self._closed = False
        self._playing = True
        self._fps = 24.0
        self._duration = 0.0
        self._position = 0.0
        self._seek_origin = 0.0
        self._next_frame_at = time.perf_counter()
        self._photo = None
        self._stop_event = None
        self._frame_queue = queue.Queue(maxsize=4)
        self._meta_queue = queue.Queue(maxsize=1)
        self._decoder_done = threading.Event()
        self._decoder_error = None
        self._decoder_generation = 0

        outer = ttk.Frame(self.window, padding=14)
        outer.pack(fill=tk.BOTH, expand=True)
        header = ttk.Frame(outer)
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="BATCH VIDEO PREVIEW",
                  font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text=Path(self.path).name,
                  foreground="#8b95a7").pack(side=tk.RIGHT)

        self.video_surface = tk.Label(
            outer, text="Preparing video…", bg="#05070b", fg="#e5e7eb",
            anchor=tk.CENTER, compound=tk.CENTER,
        )
        self.video_surface.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(outer)
        controls.pack(fill=tk.X, pady=(12, 0))
        self.position_var = tk.DoubleVar(value=0.0)
        self.seek_scale = ttk.Scale(
            controls, from_=0, to=1, variable=self.position_var,
            command=self._on_seek_drag,
        )
        self.seek_scale.pack(fill=tk.X, expand=True)
        self.seek_scale.bind("<ButtonRelease-1>", self._on_seek_release)

        toolbar = ttk.Frame(controls)
        toolbar.pack(fill=tk.X, pady=(8, 0))
        self.play_button = ttk.Button(toolbar, text="Ⅱ  Pause", command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT)
        ttk.Button(toolbar, text="↺  Restart",
                   command=lambda: self.seek_to(0)).pack(side=tk.LEFT, padx=(6, 0))
        self.time_label = ttk.Label(toolbar, text="00:00 / 00:00", width=18)
        self.time_label.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(
            toolbar, text="In-app preview is muted",
            foreground="#8b95a7",
        ).pack(side=tk.RIGHT)

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(
            footer, text="Open in default player (with audio)",
            command=self.open_external,
        ).pack(side=tk.LEFT)
        ttk.Button(footer, text="Close", command=self.close).pack(side=tk.RIGHT)

        self.window.bind("<space>", lambda _event: self.toggle_play())
        self.window.bind("<Escape>", lambda _event: self.close())
        self.window.focus_set()
        self._start_decoder(0.0)
        self._tick()

    @staticmethod
    def _format_time(seconds):
        seconds = max(0, int(seconds or 0))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def _start_decoder(self, start_seconds):
        if self._stop_event is not None:
            self._stop_event.set()

        self._decoder_generation += 1
        generation = self._decoder_generation
        stop_event = threading.Event()
        self._stop_event = stop_event
        self._frame_queue = queue.Queue(maxsize=4)
        self._meta_queue = queue.Queue(maxsize=1)
        self._decoder_done = threading.Event()
        self._decoder_error = None
        self._seek_origin = max(0.0, float(start_seconds))
        self._position = self._seek_origin
        self._next_frame_at = time.perf_counter()

        def decode():
            reader = None
            try:
                input_params = ["-ss", f"{self._seek_origin:.3f}"] if self._seek_origin > 0 else []
                vf = (
                    f"scale={self.FRAME_WIDTH}:{self.FRAME_HEIGHT}:force_original_aspect_ratio=decrease,"
                    f"pad={self.FRAME_WIDTH}:{self.FRAME_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
                )
                reader = imageio_ffmpeg.read_frames(
                    self.path,
                    pix_fmt="rgb24",
                    input_params=input_params,
                    output_params=["-vf", vf, "-threads", "1"],
                )
                metadata = next(reader)
                while not stop_event.is_set() and generation == self._decoder_generation:
                    try:
                        self._meta_queue.put((metadata, generation), timeout=0.1)
                        break
                    except queue.Full:
                        continue

                for frame in reader:
                    if stop_event.is_set() or generation != self._decoder_generation:
                        break
                    while not stop_event.is_set() and generation == self._decoder_generation:
                        try:
                            self._frame_queue.put(frame, timeout=0.1)
                            break
                        except queue.Full:
                            continue
            except Exception as exc:
                if not stop_event.is_set() and generation == self._decoder_generation:
                    self._decoder_error = str(exc)
            finally:
                if reader is not None:
                    try:
                        reader.close()
                    except Exception:
                        pass
                self._decoder_done.set()

        threading.Thread(target=decode, name="BatchPreviewDecoder", daemon=True).start()

    def _apply_metadata(self, metadata, generation):
        if self._closed or generation != self._decoder_generation:
            return
        self._fps = max(1.0, float(metadata.get("fps") or 24.0))
        self._duration = max(0.0, float(metadata.get("duration") or 0.0))
        self.seek_scale.configure(from_=0, to=max(0.1, self._duration))
        self.position_var.set(self._seek_origin)
        self._update_time_label()

    def _update_time_label(self):
        self.time_label.configure(
            text=f"{self._format_time(self._position)} / {self._format_time(self._duration)}"
        )

    def _on_seek_drag(self, value):
        if self._closed:
            return
        try:
            self.time_label.configure(
                text=f"{self._format_time(float(value))} / {self._format_time(self._duration)}"
            )
        except (TypeError, ValueError, tk.TclError):
            pass

    def _on_seek_release(self, _event=None):
        try:
            self.seek_to(float(self.position_var.get()))
        except (TypeError, ValueError, tk.TclError):
            pass

    def seek_to(self, seconds):
        if self._closed:
            return
        target = max(0.0, min(float(seconds), self._duration or float(seconds)))
        self._start_decoder(target)
        self._update_time_label()

    def toggle_play(self):
        if self._closed:
            return
        if self._playing:
            self._playing = False
            self.play_button.configure(text="▶  Play")
            return

        if self._decoder_done.is_set() and self._frame_queue.empty():
            target = 0.0 if self._duration and self._position >= self._duration else self._position
            self._start_decoder(target)
        self._playing = True
        self.play_button.configure(text="Ⅱ  Pause")

    def _tick(self):
        if self._closed:
            return

        try:
            metadata, generation = self._meta_queue.get_nowait()
            self._apply_metadata(metadata, generation)
        except queue.Empty:
            pass

        if self._playing and time.perf_counter() >= self._next_frame_at:
            try:
                frame = self._frame_queue.get_nowait()
            except queue.Empty:
                frame = None

            if frame is not None:
                try:
                    image = Image.frombytes("RGB", (self.FRAME_WIDTH, self.FRAME_HEIGHT), frame)
                    self._photo = ImageTk.PhotoImage(image)
                    self.video_surface.configure(image=self._photo, text="")
                    self._position += 1.0 / self._fps
                    if self._duration:
                        self._position = min(self._duration, self._position)
                    self.position_var.set(self._position)
                    self._update_time_label()
                except (ValueError, tk.TclError):
                    pass
                self._next_frame_at = time.perf_counter() + (1.0 / self._fps)
            elif self._decoder_done.is_set():
                if self._decoder_error:
                    self.video_surface.configure(
                        text=f"Unable to play this preview:\n{self._decoder_error}",
                        image="",
                    )
                self._playing = False
                self.play_button.configure(text="▶  Replay")

        try:
            self.window.after(15, self._tick)
        except tk.TclError:
            pass

    def open_external(self):
        try:
            self.app._open_file(self.path)
        except Exception as exc:
            messagebox.showerror("Open preview", str(exc), parent=self.window)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._stop_event is not None:
            self._stop_event.set()
        try:
            self.window.destroy()
        except tk.TclError:
            pass


def show_video_preview(app, path):
    """Open a single reusable in-app preview popup for the selected batch row."""
    existing = getattr(app, "_batch_video_preview_window", None)
    if existing is not None:
        try:
            existing.close()
        except Exception:
            pass
    app._batch_video_preview_window = BatchVideoPreviewWindow(app, path)
