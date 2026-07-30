# YouTube Downloader (yt-dlp + CustomTkinter)

Een desktopapplicatie met grafische gebruikersinterface waarmee audio (MP3)
of video (MP4) van YouTube gedownload kan worden, gebouwd op de open-source
bibliotheek [`yt-dlp`](https://github.com/yt-dlp/yt-dlp).

## ⚠️ Belangrijk: verantwoord gebruik

Dit programma is uitsluitend bedoeld voor het downloaden van video's of
audio **waarvoor je toestemming hebt, of die vrij/openbaar beschikbaar
zijn** (bijv. eigen content, Creative Commons-materiaal, of content waarvan
de rechthebbende downloaden toestaat). Het bevat geen enkele functionaliteit
om leeftijdscontroles, regio-blokkades, DRM, of andere toegangsbeperkingen
te omzeilen. Je bent zelf verantwoordelijk voor het naleven van de
[gebruiksvoorwaarden van YouTube](https://www.youtube.com/t/terms) en de
auteursrechtwetgeving die op jouw situatie van toepassing is.

## Functies

- Links invoeren via een tekstvak (één per regel), door een `.txt`-bestand
  te laden, of via slepen-en-neerzetten (optioneel, zie hieronder).
- Kiezen tussen **Audio (MP3, standaard 320 kbps)** of **Video (MP4, hoogste
  beschikbare kwaliteit)**.
- Automatische ID3-tags (titel, artiest, album, albumcover) bij audio.
- Automatisch samenvoegen van video- en audiostream tot MP4.
- Downloadmap kiezen; automatische submappen `Muziek/` en `Video/`.
- Parallelle downloads (maximaal 3 tegelijk, instelbaar).
- Voortgangsbalk, downloadlog (ook opgeslagen als logbestand) en tellers
  voor totaal/voltooid/mislukt.
- Validatie van links; ongeldige links worden overgeslagen met een
  duidelijke melding.
- Voorkomt dubbele downloads (bestaat het bestand al, dan wordt het
  overgeslagen).
- Instellingenvenster voor standaardmap, aantal gelijktijdige downloads,
  audio bitrate, videokwaliteit en bestandsnaamformaat.

## Projectstructuur

```
yt_downloader/
├── main.py          # Startpunt van de applicatie
├── gui.py           # CustomTkinter-interface
├── downloader.py    # Downloadlogica (yt-dlp, threading, callbacks)
├── settings.py       # Laden/opslaan van applicatie-instellingen
├── utils.py          # URL-validatie, bestandsnaam-sanering, logging
├── requirements.txt
└── README.md
```

## Installatie

### 1. Python

Zorg voor **Python 3.9 of hoger**.

### 2. FFmpeg (verplicht)

`yt-dlp` heeft FFmpeg nodig om audio naar MP3 te converteren en video/audio
samen te voegen tot MP4.

- **Windows**: download FFmpeg van [ffmpeg.org](https://ffmpeg.org/download.html)
  en voeg de `bin`-map toe aan je systeem-`PATH`, of installeer via
  [Chocolatey](https://chocolatey.org/): `choco install ffmpeg`.
- **macOS**: `brew install ffmpeg`
- **Linux (Debian/Ubuntu)**: `sudo apt install ffmpeg`

Controleer de installatie met:

```bash
ffmpeg -version
```

### 3. Python-afhankelijkheden

Maak bij voorkeur eerst een virtuele omgeving aan:

```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows
```

Installeer daarna de vereiste pakketten:

```bash
pip install -r requirements.txt
```

> `tkinterdnd2` (voor slepen-en-neerzetten) is optioneel. Als de installatie
> hiervan op jouw systeem niet lukt, kun je deze regel uit
> `requirements.txt` verwijderen — de rest van de applicatie blijft dan
> gewoon werken, alleen zonder drag & drop.

## Gebruik

Start de applicatie vanuit de projectmap:

```bash
python main.py
```

1. Plak of typ YouTube-links in het tekstvak (één per regel), of klik op
   **"Bestand openen"** om een `.txt`-bestand met links te laden.
2. Kies een downloadmap via **"Downloadmap kiezen"** (of gebruik de
   standaardmap uit de instellingen).
3. Kies de downloadmodus: **Audio (MP3)** of **Video (MP4)**.
4. Klik op **"▶ Start"**. Voortgang, log en tellers worden live
   bijgewerkt.
5. Klik op **"■ Stop"** om lopende en nog geplande downloads te
   annuleren.

Bestanden komen terecht in:

```
<downloadmap>/Muziek/   (voor audio)
<downloadmap>/Video/    (voor video)
```

Een logbestand (`download_log.txt`) wordt in de downloadmap bijgehouden.

## Instellingen aanpassen

Via de knop **"⚙ Instellingen"** kun je wijzigen:

- Standaard downloadmap
- Aantal gelijktijdige downloads (1–3)
- Audio bitrate (128/192/256/320 kbps)
- Videokwaliteit (beste beschikbare, of maximaal 1080/720/480p)
- Bestandsnaamformaat (yt-dlp-sjabloonsyntax, bijv. `%(title)s` of
  `%(uploader)s - %(title)s`)

Instellingen worden opgeslagen in `~/.yt_downloader/settings.json` en
blijven bewaard tussen sessies.

## Bekende beperkingen

- Alleen losse video's worden verwerkt (geen automatische
  playlist-uitbreiding), om te voorkomen dat één link per ongeluk
  honderden downloads start.
- De downloadmodus (audio/video) geldt per download-run voor alle
  ingevoerde links tegelijk, zoals gevraagd in de specificatie.

## Licentie van gebruikte bibliotheken

- `yt-dlp`: Unlicense (public domain-achtige licentie)
- `customtkinter`: MIT-licentie
- `tkinterdnd2`: MIT-licentie

Alle gebruikte pakketten zijn open-source.
