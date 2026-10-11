#!/usr/bin/env bash
set -e
mkdir -p assets/fonts
curl -sL "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf" -o assets/fonts/SpaceGrotesk.ttf
curl -sL "https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf" -o assets/fonts/ArchivoBlack.ttf
curl -sL "https://github.com/google/fonts/raw/main/ofl/syne/Syne%5Bwght%5D.ttf" -o assets/fonts/Syne.ttf
curl -sL "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf" -o assets/fonts/JetBrainsMono.ttf
curl -sL "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf" -o assets/fonts/Inter.ttf
curl -sL "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf" -o assets/fonts/Anton.ttf
echo "Fonts downloaded to assets/fonts/"
