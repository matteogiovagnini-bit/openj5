#!/system/bin/sh
# Tenta il ripristino delle app "keep" erroneamente rimosse
for p in \
  com.openai.chatgpt \
  com.google.android.apps.photos \
  com.google.android.contactkeys \
  com.google.android.safetycore \
  com.google.android.verifier \
  com.google.earth \
  com.sec.android.app.popupcalculator \
  com.sec.android.app.sbrowser \
  com.sec.android.app.voicenote \
  com.samsung.android.app.tips \
  com.snapchat.android \
  com.amazon.appmanager \
  com.amazon.avod.thirdpartyclient \
  com.gamepass.samsung \
  app.feelsy \
  com.remote.control.tv.universal.pro.sams \
  com.tools.edge.lighting.ledlight \
  com.galaxy.starmap \
  com.jmsys.earth3d ; do
  if pm install-existing --user 0 "$p" >/dev/null 2>&1; then
    echo "RIPRISTINATA $p"
  else
    echo "NON_RIPRISTINABILE $p"
  fi
done
