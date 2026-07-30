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

import os
import sys


def _configure_ssl_certificates() -> None:
    """
    Zorg dat Python/yt-dlp een geldige CA-certificatenbundel kan vinden.

    Sommige Python-installaties (met name de python.org-installer op
    macOS, maar soms ook Linux/Windows met een verouderd of ontbrekend
    systeemcertificaat) geven bij HTTPS-verzoeken de fout
    "CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate".

    In plaats van certificaatverificatie uit te schakelen (onveilig),
    wijzen we Python expliciet naar de betrouwbare, actueel gehouden
    certificatenbundel uit het `certifi`-pakket. Dit is de aanbevolen,
    veilige oplossing.
    """
    try:
        import certifi

        cert_path = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", cert_path)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cert_path)
        os.environ.setdefault("CURL_CA_BUNDLE", cert_path)
    except ImportError:
        # certifi is niet geïnstalleerd; installeer het met:
        #   pip install certifi
        # De applicatie werkt dan verder met de systeemcertificaten.
        pass


# Dit moet gebeuren VOORDAT yt-dlp/urllib/requests worden geïmporteerd
# of gebruikt, dus vóór de import van gui/downloader.
_configure_ssl_certificates()

from gui import create_app  # noqa: E402  (bewust ná _configure_ssl_certificates)


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
