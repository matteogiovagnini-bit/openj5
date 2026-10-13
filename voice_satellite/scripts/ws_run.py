import asyncio, json, sys, aiohttp, wave

TOKEN = sys.argv[1]
TEXT = sys.argv[2]
PIPEID = sys.argv[3] if len(sys.argv) > 3 else None
WS = "ws://127.0.0.1:8123/api/websocket"

async def main():
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(WS) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": TOKEN})
            await ws.receive_json()

            payload = {
                "id": 1,
                "type": "assist_pipeline/run",
                "start_stage": "intent",
                "end_stage": "tts",
                "input": {"text": TEXT},
            }
            if PIPEID:
                payload["pipeline"] = PIPEID
            await ws.send_json(payload)

            rate = width = channels = None
            audio = bytearray()
            speech = None
            while True:
                msg = await ws.receive()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    audio.extend(msg.data)
                    continue
                if msg.type == aiohttp.WSMsgType.TEXT:
                    raw = msg.data
                    print("RAW:", raw[:400])
                    m = json.loads(raw)
                    mt = m.get("type")
                    if mt == "event":
                        ev = m["event"]
                        t = ev["type"]
                        if t == "tts-start":
                            d = ev["data"]; rate = d.get("rate"); width = d.get("width"); channels = d.get("channels")
                        elif t == "intent-end":
                            io = ev["data"].get("intent_output", {})
                            sp = io.get("response", {}).get("speech", {})
                            speech = sp.get("plain", {}).get("speech") or speech
                        elif t == "run-end":
                            break
                    elif mt == "result":
                        # ack della subscription: NON terminare, gli eventi arrivano dopo
                        print("RESULT(ack):", json.dumps(m))
                        if not m.get("success"):
                            print("SUBSCRIBE ERROR:", m.get("error"))
                            break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    print("ws closed/error")
                    break

            print("SPEECH:", speech)
            print("audio: %d byte rate=%s width=%s ch=%s" % (len(audio), rate, width, channels))
            if audio and rate:
                with wave.open("/data/data/com.termux/files/home/run_out.wav", "wb") as w:
                    w.setnchannels(channels or 1); w.setsampwidth(width or 2); w.setframerate(rate or 22050)
                    w.writeframes(bytes(audio))
                print("scritto run_out.wav")

asyncio.run(main())
