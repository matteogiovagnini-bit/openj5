#!/system/bin/sh
# Rimuove le app elencate in /data/local/tmp/remove_apps.txt
LOG=/data/local/tmp/uninstall.log
OK=0
FAIL=0
: > "$LOG"
while read -r p; do
  [ -z "$p" ] && continue
  if pm uninstall --user 0 "$p" >/dev/null 2>&1; then
    echo "OK   $p" >> "$LOG"
    OK=$((OK+1))
  else
    echo "FAIL $p" >> "$LOG"
    FAIL=$((FAIL+1))
  fi
done < /data/local/tmp/remove_apps.txt
echo "RIEPILOGO: OK=$OK FAIL=$FAIL" >> "$LOG"
echo "DONE" >> "$LOG"
