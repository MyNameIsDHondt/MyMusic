"""
settings.py
-----------
Beheer van de applicatie-instellingen: standaard downloadmap, aantal
gelijktijdige downloads, audio bitrate, videokwaliteit en
bestandsnaamformaat. Instellingen worden persistent opgeslagen als JSON
in de gebruikersmap, zodat ze bewaard blijven tussen sessies.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict


def _default_download_dir() -> str:
    """Geef de standaard downloadmap (~/Downloads/YT-Downloader) terug."""
    return str(Path.home() / "Downloads" / "YT-Downloader")


def _config_path() -> Path:
    """Locatie van het instellingenbestand in de gebruikersmap."""
    config_dir = Path.home() / ".yt_downloader"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "settings.json"


@dataclass
class AppSettings:
    """Alle instelbare parameters van de applicatie."""

    # Map waarin downloads standaard worden opgeslagen
    default_download_dir: str = field(default_factory=_default_download_dir)

    # Maximaal aantal downloads dat gelijktijdig mag draaien (max 3, per eis)
    max_concurrent_downloads: int = 3

    # Audio bitrate in kbps voor MP3-conversie
    audio_bitrate: str = "320"

    # Gewenste videokwaliteit: "best" = hoogste beschikbare kwaliteit
    video_quality: str = "best"

    # Sjabloon voor bestandsnamen (yt-dlp outtmpl-syntax)
    filename_format: str = "%(title)s"

    def to_dict(self) -> Dict[str, Any]:
        """Zet de instellingen om naar een gewoon dict (voor JSON)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppSettings":
        """Bouw een AppSettings-object op basis van een dict, met fallback
        naar standaardwaarden voor ontbrekende sleutels."""
        defaults = cls()
        merged = {**defaults.to_dict(), **data}
        # Filter onbekende sleutels eruit zodat oude configbestanden geen
        # fouten veroorzaken na updates van de applicatie
        valid_keys = defaults.to_dict().keys()
        filtered = {k: v for k, v in merged.items() if k in valid_keys}
        return cls(**filtered)


def load_settings() -> AppSettings:
    """
    Laad de instellingen van schijf. Als er nog geen instellingenbestand
    bestaat (of het is corrupt), worden standaardinstellingen gebruikt.

    Returns:
        AppSettings-object.
    """
    path = _config_path()
    if not path.exists():
        return AppSettings()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppSettings.from_dict(data)
    except (json.JSONDecodeError, OSError):
        # Corrupt of onleesbaar bestand: val terug op standaardwaarden
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    """
    Sla de instellingen op naar schijf als JSON.

    Args:
        settings: Het AppSettings-object dat opgeslagen moet worden.
    """
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)
