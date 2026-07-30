"""
downloader.py
-------------
Bevat de downloadlogica op basis van yt-dlp (een actief onderhouden,
open-source bibliotheek). Ondersteunt:

- Audio-downloads (conversie naar MP3 via FFmpeg, incl. ID3-tags en
  albumcover via yt-dlp's eigen postprocessors).
- Video-downloads (automatisch samenvoegen van de beste video- en
  audiostream tot MP4).
- Parallelle uitvoering met een instelbaar maximumaantal gelijktijdige
  downloads (standaard 3).
- Voortgangsrapportage en annulering via callbacks.
- Overslaan van bestanden die al bestaan (voorkomt dubbele downloads).

BELANGRIJK: dit programma downloadt uitsluitend content die via de
publieke yt-dlp/YouTube-extractor normaal opvraagbaar is. Er wordt geen
enkele vorm van DRM-omzeiling, cookie-diefstal, regio-spoofing t.b.v.
omzeiling van beperkingen, of scraping van privécontent toegepast. De
gebruiker is zelf verantwoordelijk voor het naleven van de
gebruiksvoorwaarden van YouTube en het auteursrecht.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional

import yt_dlp

from settings import AppSettings
from utils import file_already_exists, sanitize_filename


class DownloadMode(Enum):
    """Type download dat voor een link is gekozen."""

    AUDIO = "audio"
    VIDEO = "video"


class DownloadStatus(Enum):
    """Status van een individuele downloadtaak."""

    WACHTEND = "wachtend"
    BEZIG = "bezig"
    VOLTOOID = "voltooid"
    MISLUKT = "mislukt"
    OVERGESLAGEN = "overgeslagen"
    GEANNULEERD = "geannuleerd"


class DownloadCancelled(Exception):
    """Interne uitzondering om een download tussentijds te stoppen."""


@dataclass
class DownloadTask:
    """Representeert één downloadopdracht (één URL + gekozen modus)."""

    url: str
    mode: DownloadMode
    status: DownloadStatus = DownloadStatus.WACHTEND
    error_message: str = ""
    title: str = ""


# Type-aliassen voor de callback-signaturen die de GUI kan meegeven
ProgressCallback = Callable[[DownloadTask, float], None]  # taak, percentage 0-100
LogCallback = Callable[[str], None]
StatusCallback = Callable[[DownloadTask], None]
CountersCallback = Callable[[int, int, int], None]  # totaal, voltooid, mislukt


class DownloadManager:
    """
    Beheert het parallel downloaden van een lijst DownloadTask-objecten
    met yt-dlp, en communiceert voortgang/afronding via callbacks naar de
    GUI-laag (zodat downloader.py geen weet heeft van de GUI-toolkit).
    """

    def __init__(
        self,
        settings: AppSettings,
        output_dir: Path,
        on_progress: ProgressCallback,
        on_log: LogCallback,
        on_status_change: StatusCallback,
        on_counters_update: CountersCallback,
    ) -> None:
        self.settings = settings
        self.output_dir = output_dir
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_status_change = on_status_change
        self.on_counters_update = on_counters_update

        self._stop_event = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: List[Future] = []

        self._completed_count = 0
        self._failed_count = 0
        self._counters_lock = threading.Lock()

    def stop(self) -> None:
        """Vraag alle lopende en nog geplande downloads te stoppen."""
        self._stop_event.set()
        self.on_log("Bezig met stoppen... lopende downloads worden afgebroken.")

    def run(self, tasks: List[DownloadTask]) -> None:
        """
        Start het (parallel) verwerken van de opgegeven downloadtaken.
        Deze methode is blokkerend en moet daarom vanuit een aparte
        achtergrondthread door de GUI worden aangeroepen.

        Args:
            tasks: Lijst van uit te voeren DownloadTask-objecten.
        """
        self._stop_event.clear()
        self._completed_count = 0
        self._failed_count = 0
        total = len(tasks)
        self.on_counters_update(total, self._completed_count, self._failed_count)

        max_workers = max(1, min(self.settings.max_concurrent_downloads, 3))
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        self._futures = [
            self._executor.submit(self._process_task, task) for task in tasks
        ]

        # Wacht tot alles klaar is (of gestopt wordt)
        for future in self._futures:
            future.result()

        self._executor.shutdown(wait=True)
        if self._stop_event.is_set():
            self.on_log("Download-run gestopt door gebruiker.")
        else:
            self.on_log("Alle downloads zijn verwerkt.")

    # ------------------------------------------------------------------
    # Interne verwerking per taak
    # ------------------------------------------------------------------

    def _process_task(self, task: DownloadTask) -> None:
        """Verwerk één downloadtaak (draait in een workerthread)."""
        if self._stop_event.is_set():
            task.status = DownloadStatus.GEANNULEERD
            self.on_status_change(task)
            return

        task.status = DownloadStatus.BEZIG
        self.on_status_change(task)

        try:
            if task.mode == DownloadMode.AUDIO:
                self._download_audio(task)
            else:
                self._download_video(task)

            if task.status != DownloadStatus.OVERGESLAGEN:
                task.status = DownloadStatus.VOLTOOID
                self._bump_counters(success=True)
            self.on_status_change(task)

        except DownloadCancelled:
            task.status = DownloadStatus.GEANNULEERD
            self.on_status_change(task)

        except Exception as exc:  # noqa: BLE001 - we willen élke fout afvangen
            task.status = DownloadStatus.MISLUKT
            task.error_message = str(exc)
            self.on_log(f"FOUT bij {task.url}: {exc}")
            self._bump_counters(success=False)
            self.on_status_change(task)

    def _bump_counters(self, success: bool) -> None:
        """Werk de gedeelde tellers thread-safe bij en meld ze aan de GUI."""
        with self._counters_lock:
            if success:
                self._completed_count += 1
            else:
                self._failed_count += 1
            total = len(self._futures)
            self.on_counters_update(total, self._completed_count, self._failed_count)

    def _make_progress_hook(self, task: DownloadTask) -> Callable[[dict], None]:
        """Bouw een yt-dlp progress_hook die voortgang doorstuurt en
        annulering ondersteunt."""

        def hook(d: dict) -> None:
            if self._stop_event.is_set():
                # Dit onderbreekt de huidige yt-dlp-download direct
                raise DownloadCancelled("Download geannuleerd door gebruiker.")

            if d.get("status") == "downloading":
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total_bytes:
                    percent = downloaded / total_bytes * 100
                    self.on_progress(task, percent)
            elif d.get("status") == "finished":
                self.on_progress(task, 100.0)

        return hook

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    def _download_audio(self, task: DownloadTask) -> None:
        """Download de beste audiostream en converteer naar MP3 met
        ID3-tags (titel, artiest, album, albumcover indien beschikbaar)."""
        outtmpl = str(self.output_dir / f"{self.settings.filename_format}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._make_progress_hook(task)],
            "writethumbnail": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.settings.audio_bitrate,
                },
                {"key": "FFmpegMetadata"},  # zet titel/artiest/album als ID3-tags
                {"key": "EmbedThumbnail"},  # zet thumbnail als albumcover
            ],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(task.url, download=False)
            title = sanitize_filename(info.get("title", task.url))
            task.title = title

            if file_already_exists(self.output_dir, title, "mp3"):
                self.on_log(f"Overgeslagen (bestaat al): {title}.mp3")
                task.status = DownloadStatus.OVERGESLAGEN
                return

            self.on_log(f"Audio downloaden: {title}")
            ydl.download([task.url])
            self.on_log(f"Audio voltooid: {title}.mp3")

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------

    def _download_video(self, task: DownloadTask) -> None:
        """Download de hoogste beschikbare videokwaliteit en voeg video-
        en audiostream samen tot een MP4-bestand."""
        outtmpl = str(self.output_dir / f"{self.settings.filename_format}.%(ext)s")

        quality = self.settings.video_quality
        if quality == "best":
            format_selector = "bestvideo+bestaudio/best"
        else:
            # bijv. "1080" -> beperk tot maximaal die hoogte
            format_selector = (
                f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
            )

        ydl_opts = {
            "format": format_selector,
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            "progress_hooks": [self._make_progress_hook(task)],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(task.url, download=False)
            title = sanitize_filename(info.get("title", task.url))
            task.title = title

            if file_already_exists(self.output_dir, title, "mp4"):
                self.on_log(f"Overgeslagen (bestaat al): {title}.mp4")
                task.status = DownloadStatus.OVERGESLAGEN
                return

            self.on_log(f"Video downloaden: {title}")
            ydl.download([task.url])
            self.on_log(f"Video voltooid: {title}.mp4")


def extract_urls_from_text(text: str) -> List[str]:
    """
    Splits een blok tekst (bijv. de inhoud van het tekstvak of een
    ingeladen .txt-bestand) op in losse, niet-lege URL-regels.

    Args:
        text: Ruwe tekst met één link per regel.

    Returns:
        Lijst van niet-lege, getrimde regels.
    """
    return [line.strip() for line in text.splitlines() if line.strip()]
