"""
utils.py
--------
Algemene hulpfuncties die door meerdere modules worden gebruikt:
- URL-validatie
- Bestandsnaam-sanering
- Logging-configuratie
- Mapbeheer (aanmaken van Downloads/Muziek en Downloads/Video)

Bevat uitsluitend generieke, legale hulpmiddelen. Er wordt op geen enkele
manier geprobeerd toegangsbeperkingen (DRM, leeftijdscontrole, regio-locks,
private/unlisted-only content, etc.) te omzeilen.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

# Regex die de meest voorkomende publieke YouTube-URL-vormen herkent.
_YOUTUBE_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)"
    r"[A-Za-z0-9_\-]{6,}"
    r"(\S*)?$",
    re.IGNORECASE,
)


def is_valid_youtube_url(url: str) -> bool:
    """
    Controleer of een string een geldig ogende, publieke YouTube-URL is.

    Dit is uitsluitend een *syntactische* controle (regex). Het programma
    doet geen poging om private/unlisted video's, leeftijdsbeperkte content
    achter een login, of anderszins beveiligde content te benaderen; als
    yt-dlp bij het daadwerkelijke ophalen een fout geeft (bijv. "video
    unavailable" of "private video"), wordt dat afgehandeld als een normale
    downloadfout.

    Args:
        url: De te controleren string.

    Returns:
        True als de URL aan het verwachte YouTube-patroon voldoet.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url:
        return False
    return bool(_YOUTUBE_URL_PATTERN.match(url))


def sanitize_filename(name: str, max_length: int = 150) -> str:
    """
    Verwijder tekens uit een string die niet toegestaan zijn in
    bestandsnamen op Windows/macOS/Linux.

    Args:
        name: De oorspronkelijke (bestands)naam.
        max_length: Maximale lengte van de resulterende naam.

    Returns:
        Een veilige bestandsnaam.
    """
    # Verboden tekens op Windows: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name)
    # Overtollige spaties opschonen
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Voorkom lege bestandsnamen
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_length]


def ensure_directories(base_dir: Path) -> tuple[Path, Path]:
    """
    Zorg dat de mappen Downloads/Muziek en Downloads/Video onder de
    opgegeven basismap bestaan en geef hun paden terug.

    Args:
        base_dir: De door de gebruiker gekozen basis-downloadmap.

    Returns:
        Tuple (muziek_map, video_map).
    """
    music_dir = base_dir / "Muziek"
    video_dir = base_dir / "Video"
    music_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)
    return music_dir, video_dir


def setup_logger(log_file: Optional[Path] = None) -> logging.Logger:
    """
    Configureer en retourneer de applicatie-logger. Schrijft zowel naar
    een logbestand als (optioneel) naar de console.

    Args:
        log_file: Pad naar het logbestand. Indien None wordt alleen naar
            de console gelogd.

    Returns:
        Geconfigureerde Logger-instantie.
    """
    logger = logging.getLogger("yt_downloader")
    logger.setLevel(logging.INFO)

    # Voorkom dubbele handlers bij herhaaldelijk aanroepen
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def file_already_exists(directory: Path, expected_stem: str, extension: str) -> bool:
    """
    Controleer of een bestand met (ongeveer) deze naam al bestaat in de
    doelmap, om dubbele downloads te voorkomen.

    Args:
        directory: Map waarin gezocht wordt.
        expected_stem: Verwachte bestandsnaam zonder extensie.
        extension: Bestandsextensie zonder punt, bijv. "mp3" of "mp4".

    Returns:
        True als een overeenkomend bestand al bestaat.
    """
    candidate = directory / f"{expected_stem}.{extension}"
    return candidate.exists()
