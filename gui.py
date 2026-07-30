"""
gui.py
------
Grafische gebruikersinterface (CustomTkinter) voor de YouTube-
downloader. Deze module bevat uitsluitend UI-logica; het daadwerkelijke
downloaden gebeurt in downloader.py, en instellingen in settings.py.

Optioneel wordt sleep-en-neerzet-ondersteuning geboden via het pakket
`tkinterdnd2`. Als dit pakket niet geïnstalleerd is, werkt de applicatie
gewoon door (drag & drop is dan simpelweg niet beschikbaar en de
gebruiker gebruikt de knop "Bestand openen" of plakt de links).
"""

from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List, Optional

import customtkinter as ctk

from downloader import (
    DownloadManager,
    DownloadMode,
    DownloadStatus,
    DownloadTask,
    extract_urls_from_text,
)
from settings import AppSettings, load_settings, save_settings
from utils import ensure_directories, is_valid_youtube_url, setup_logger

# Sleep-en-neerzet is optioneel; de app werkt ook zonder dit pakket.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore

    _DND_AVAILABLE = True
except ImportError:  # pragma: no cover - optionele afhankelijkheid
    _DND_AVAILABLE = False


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SettingsWindow(ctk.CTkToplevel):
    """Apart venster waarin de gebruiker de applicatie-instellingen kan
    aanpassen: standaardmap, gelijktijdige downloads, bitrate,
    videokwaliteit en bestandsnaamformaat."""

    def __init__(self, master: "MainWindow", settings: AppSettings) -> None:
        super().__init__(master)
        self.title("Instellingen")
        self.geometry("480x420")
        self.resizable(False, False)
        self.master_app = master
        self.settings = settings

        self.grab_set()  # maak dit venster modaal

        padding = {"padx": 20, "pady": (10, 0)}

        # --- Standaard downloadmap ---
        ctk.CTkLabel(self, text="Standaard downloadmap:").pack(anchor="w", **padding)
        self.dir_var = ctk.StringVar(value=settings.default_download_dir)
        dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        dir_frame.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkEntry(dir_frame, textvariable=self.dir_var).pack(
            side="left", fill="x", expand=True
        )
        ctk.CTkButton(
            dir_frame, text="Bladeren", width=90, command=self._choose_dir
        ).pack(side="left", padx=(8, 0))

        # --- Gelijktijdige downloads ---
        ctk.CTkLabel(self, text="Aantal gelijktijdige downloads (max 3):").pack(
            anchor="w", **padding
        )
        self.concurrency_var = ctk.IntVar(value=settings.max_concurrent_downloads)
        ctk.CTkSlider(
            self, from_=1, to=3, number_of_steps=2, variable=self.concurrency_var
        ).pack(fill="x", padx=20, pady=(0, 10))

        # --- Audio bitrate ---
        ctk.CTkLabel(self, text="Audio bitrate (kbps):").pack(anchor="w", **padding)
        self.bitrate_var = ctk.StringVar(value=settings.audio_bitrate)
        ctk.CTkOptionMenu(
            self, values=["128", "192", "256", "320"], variable=self.bitrate_var
        ).pack(fill="x", padx=20, pady=(0, 10))

        # --- Videokwaliteit ---
        ctk.CTkLabel(self, text="Videokwaliteit:").pack(anchor="w", **padding)
        self.quality_var = ctk.StringVar(value=settings.video_quality)
        ctk.CTkOptionMenu(
            self,
            values=["best", "1080", "720", "480"],
            variable=self.quality_var,
        ).pack(fill="x", padx=20, pady=(0, 10))

        # --- Bestandsnaamformaat ---
        ctk.CTkLabel(self, text="Bestandsnaamformaat (yt-dlp-sjabloon):").pack(
            anchor="w", **padding
        )
        self.filename_var = ctk.StringVar(value=settings.filename_format)
        ctk.CTkEntry(self, textvariable=self.filename_var).pack(
            fill="x", padx=20, pady=(0, 10)
        )
        ctk.CTkLabel(
            self,
            text='Bijv. "%(title)s" of "%(uploader)s - %(title)s"',
            text_color="gray60",
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=20)

        # --- Opslaan / Annuleren ---
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=20)
        ctk.CTkButton(button_frame, text="Opslaan", command=self._save).pack(
            side="right"
        )
        ctk.CTkButton(
            button_frame,
            text="Annuleren",
            fg_color="gray40",
            command=self.destroy,
        ).pack(side="right", padx=(0, 8))

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Kies standaard downloadmap")
        if chosen:
            self.dir_var.set(chosen)

    def _save(self) -> None:
        self.settings.default_download_dir = self.dir_var.get()
        self.settings.max_concurrent_downloads = int(self.concurrency_var.get())
        self.settings.audio_bitrate = self.bitrate_var.get()
        self.settings.video_quality = self.quality_var.get()
        self.settings.filename_format = self.filename_var.get() or "%(title)s"
        save_settings(self.settings)
        self.master_app.apply_settings(self.settings)
        self.destroy()


class MainWindow(ctk.CTk):
    """Hoofdvenster van de applicatie."""

    def __init__(self) -> None:
        super().__init__()

        self.settings: AppSettings = load_settings()
        self.download_dir = Path(self.settings.default_download_dir)
        self.logger = setup_logger(self.download_dir / "download_log.txt")

        self.tasks: List[DownloadTask] = []
        self.manager: Optional[DownloadManager] = None
        self.download_thread: Optional[threading.Thread] = None

        self.title("YouTube Downloader")
        self.geometry("900x720")
        self.minsize(760, 600)

        self._build_widgets()
        self._setup_drag_and_drop()

    # ------------------------------------------------------------------
    # UI-opbouw
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        """Bouw alle widgets van het hoofdvenster op."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # --- Bovenste balk: titel + instellingenknop ---
        top_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_bar.pack(fill="x")
        ctk.CTkLabel(
            top_bar, text="YouTube Downloader", font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left")
        ctk.CTkButton(
            top_bar, text="⚙ Instellingen", width=120, command=self._open_settings
        ).pack(side="right")

        # --- Tekstvak voor links ---
        ctk.CTkLabel(main_frame, text="YouTube-links (één per regel):").pack(
            anchor="w", pady=(12, 4)
        )
        self.link_textbox = ctk.CTkTextbox(main_frame, height=160)
        self.link_textbox.pack(fill="x")

        # --- Knoppenrij: bestand openen / downloadmap kiezen ---
        button_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_row.pack(fill="x", pady=8)
        ctk.CTkButton(
            button_row, text="📄 Bestand openen", command=self._open_file
        ).pack(side="left")
        ctk.CTkButton(
            button_row, text="📁 Downloadmap kiezen", command=self._choose_folder
        ).pack(side="left", padx=(8, 0))

        self.folder_label = ctk.CTkLabel(
            button_row, text=f"Map: {self.download_dir}", text_color="gray60"
        )
        self.folder_label.pack(side="left", padx=12)

        # --- Modus: audio of video (globaal voor alle links) ---
        mode_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(mode_frame, text="Downloadmodus:").pack(side="left")
        self.mode_var = ctk.StringVar(value=DownloadMode.AUDIO.value)
        ctk.CTkRadioButton(
            mode_frame, text="Audio (MP3)", variable=self.mode_var, value=DownloadMode.AUDIO.value
        ).pack(side="left", padx=(12, 8))
        ctk.CTkRadioButton(
            mode_frame, text="Video (MP4)", variable=self.mode_var, value=DownloadMode.VIDEO.value
        ).pack(side="left")

        # --- Start / Stop knoppen + tellers ---
        control_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        control_frame.pack(fill="x", pady=(0, 8))
        self.start_button = ctk.CTkButton(
            control_frame, text="▶ Start", fg_color="#2e7d32",
            hover_color="#1b5e20", command=self._start_downloads,
        )
        self.start_button.pack(side="left")
        self.stop_button = ctk.CTkButton(
            control_frame, text="■ Stop", fg_color="#c62828",
            hover_color="#8e0000", command=self._stop_downloads, state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        self.counters_label = ctk.CTkLabel(
            control_frame, text="Totaal: 0   Voltooid: 0   Mislukt: 0"
        )
        self.counters_label.pack(side="right")

        # --- Voortgangsbalk ---
        self.progress_bar = ctk.CTkProgressBar(main_frame)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        # --- Downloadlog ---
        ctk.CTkLabel(main_frame, text="Downloadlog:").pack(anchor="w")
        self.log_textbox = ctk.CTkTextbox(main_frame, height=180, state="disabled")
        self.log_textbox.pack(fill="both", expand=True, pady=(4, 0))

    def _setup_drag_and_drop(self) -> None:
        """Registreer sleep-en-neerzet voor .txt-bestanden, indien
        tkinterdnd2 beschikbaar is."""
        if not _DND_AVAILABLE:
            return
        try:
            self.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
            self.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensief, niet kritiek
            pass

    def _on_drop(self, event) -> None:  # type: ignore[no-untyped-def]
        """Verwerk een gesleept .txt-bestand door de inhoud in het
        tekstvak te plakken."""
        path_str = event.data.strip("{}")
        path = Path(path_str)
        if path.suffix.lower() == ".txt" and path.exists():
            content = path.read_text(encoding="utf-8", errors="ignore")
            self.link_textbox.insert("end", content)
            self._log(f"Links geladen via slepen-en-neerzetten: {path.name}")

    # ------------------------------------------------------------------
    # Knop-acties
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        """Open een .txt-bestand met links en voeg de inhoud toe aan het
        tekstvak."""
        file_path = filedialog.askopenfilename(
            title="Kies een tekstbestand met links",
            filetypes=[("Tekstbestanden", "*.txt"), ("Alle bestanden", "*.*")],
        )
        if not file_path:
            return
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            self.link_textbox.insert("end", content)
            self._log(f"Links geladen uit bestand: {file_path}")
        except OSError as exc:
            messagebox.showerror("Fout bij laden", f"Kon bestand niet lezen:\n{exc}")

    def _choose_folder(self) -> None:
        """Laat de gebruiker de downloadmap kiezen."""
        chosen = filedialog.askdirectory(title="Kies downloadmap")
        if chosen:
            self.download_dir = Path(chosen)
            self.folder_label.configure(text=f"Map: {self.download_dir}")
            self.logger = setup_logger(self.download_dir / "download_log.txt")

    def _open_settings(self) -> None:
        SettingsWindow(self, self.settings)

    def apply_settings(self, settings: AppSettings) -> None:
        """Callback vanuit SettingsWindow: pas nieuwe instellingen toe."""
        self.settings = settings
        self.download_dir = Path(settings.default_download_dir)
        self.folder_label.configure(text=f"Map: {self.download_dir}")
        self._log("Instellingen bijgewerkt.")

    # ------------------------------------------------------------------
    # Downloadlogica (aansturing van downloader.py)
    # ------------------------------------------------------------------

    def _start_downloads(self) -> None:
        """Valideer invoer en start het downloadproces in een aparte
        achtergrondthread, zodat de GUI responsief blijft."""
        raw_text = self.link_textbox.get("1.0", "end")
        urls = extract_urls_from_text(raw_text)

        if not urls:
            messagebox.showwarning("Geen links", "Voer minstens één YouTube-link in.")
            return

        valid_urls: List[str] = []
        skipped = 0
        for url in urls:
            if is_valid_youtube_url(url):
                valid_urls.append(url)
            else:
                skipped += 1
                self._log(f"Ongeldige link overgeslagen: {url}")

        if skipped:
            self._log(f"{skipped} ongeldige link(s) overgeslagen.")

        if not valid_urls:
            messagebox.showerror("Geen geldige links", "Geen enkele link is geldig.")
            return

        mode = DownloadMode(self.mode_var.get())
        self.tasks = [DownloadTask(url=u, mode=mode) for u in valid_urls]

        music_dir, video_dir = ensure_directories(self.download_dir)
        target_dir = music_dir if mode == DownloadMode.AUDIO else video_dir

        self.manager = DownloadManager(
            settings=self.settings,
            output_dir=target_dir,
            on_progress=self._on_progress,
            on_log=self._log,
            on_status_change=self._on_status_change,
            on_counters_update=self._on_counters_update,
        )

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress_bar.set(0)

        self.download_thread = threading.Thread(
            target=self._run_manager, args=(self.tasks,), daemon=True
        )
        self.download_thread.start()

    def _run_manager(self, tasks: List[DownloadTask]) -> None:
        """Draait in een achtergrondthread; roept de blokkerende
        DownloadManager.run() aan en herstelt daarna de knoppenstatus."""
        assert self.manager is not None
        try:
            self.manager.run(tasks)
        finally:
            # UI-aanpassingen moeten via `after` op de hoofdthread gebeuren
            self.after(0, self._on_downloads_finished)

    def _stop_downloads(self) -> None:
        if self.manager is not None:
            self.manager.stop()
        self.stop_button.configure(state="disabled")

    def _on_downloads_finished(self) -> None:
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    # ------------------------------------------------------------------
    # Callbacks vanuit DownloadManager (thread-safe via `after`)
    # ------------------------------------------------------------------

    def _on_progress(self, task: DownloadTask, percent: float) -> None:
        def update() -> None:
            # Toon het gemiddelde voortgangspercentage over alle taken
            # als een eenvoudige, begrijpelijke totale voortgangsbalk.
            self.progress_bar.set(percent / 100)

        self.after(0, update)

    def _on_status_change(self, task: DownloadTask) -> None:
        def update() -> None:
            if task.status == DownloadStatus.MISLUKT:
                self._log(f"Mislukt: {task.url} ({task.error_message})")
            elif task.status == DownloadStatus.GEANNULEERD:
                self._log(f"Geannuleerd: {task.url}")

        self.after(0, update)

    def _on_counters_update(self, total: int, completed: int, failed: int) -> None:
        def update() -> None:
            self.counters_label.configure(
                text=f"Totaal: {total}   Voltooid: {completed}   Mislukt: {failed}"
            )

        self.after(0, update)

    def _log(self, message: str) -> None:
        """Schrijf een regel naar zowel de GUI-log als het logbestand."""
        self.logger.info(message)

        def update() -> None:
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")

        self.after(0, update)


def create_app() -> MainWindow:
    """Fabrieksfunctie die het hoofdvenster aanmaakt (gebruikt door
    main.py)."""
    return MainWindow()
