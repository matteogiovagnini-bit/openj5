#!/system/bin/sh
# Rimozione parallela (6 alla volta) delle app in /data/local/tmp/remove_apps.txt
LOG=/data/local/tmp/uninstall.log
: > "$LOG"
N=6
i=0
while read -r p; do
  [ -z "$p" ] && continue
  (
    if pm uninstall --user 0 "$p" >/dev/null 2>&1; then
      echo "OK   $p" >> "$LOG"
    else
      echo "FAIL $p" >> "$LOG"
    fi
  ) &
  i=$((i+1))
  if [ $((i % N)) -eq 0 ]; then wait; fi
done < /data/local/tmp/remove_apps.txt
wait
echo "DONE" >> "$LOG"
