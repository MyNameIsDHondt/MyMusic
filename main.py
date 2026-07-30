"""
main.py
-------
Startpunt van de YouTube Downloader-applicatie.

Dit programma downloadt uitsluitend openbaar beschikbare video's/audio
via yt-dlp en houdt geen enkele functionaliteit in om
toegangsbeperkingen, DRM of auteursrechtelijke bescherming te omzeilen.
Gebruik dit programma alleen voor content waarvoor je toestemming hebt
of die vrij beschikbaar is, en houd je aan de gebruiksvoorwaarden van
YouTube en de toepasselijke wetgeving.

Gebruik:
    python main.py
"""

from __future__ import annotations

import sys

from gui import create_app


def main() -> int:
    """Start de GUI-applicatie. Geeft een exitcode terug."""
    try:
        app = create_app()
        app.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001 - vang álle opstartfouten af
        print(f"Onverwachte fout bij het starten van de applicatie: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
