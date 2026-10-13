#!/bin/sh
# Patch: PyAV 19 ha rimosso il parametro metadata_errors usato da faster-whisper
F=/opt/whisper/lib/python3.14/site-packages/faster_whisper/audio.py
cp "$F" "$F.bak"
sed -i 's/, metadata_errors="ignore"//' "$F"
echo "--- riga av.open dopo patch ---"
grep -n 'av.open' "$F"
