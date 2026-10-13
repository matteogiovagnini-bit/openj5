import asyncio, json, sys, aiohttp

TOKEN = sys.argv[1]
RAWFILE = sys.argv[2]
PIPEID = sys.argv[3] if len(sys.argv) > 3 else None
WS = "ws://127.0.0.1:8123/api/websocket"

async def main():
    with open(RAWFILE, "rb") as f:
        pcm = f.read()
    print("PCM input: %d byte (%.1f s @16k mono s16)" % (len(pcm), len(pcm) / 32000.0))

    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(WS) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": TOKEN})
            await ws.receive_json()

            payload = {
                "id": 1,
                "type": "assist_pipeline/run",
                "start_stage": "stt",
                "end_stage": "tts",
                "input": {"type": "audio", "sample_rate": 16000},
            }
            if PIPEID:
                payload["pipeline"] = PIPEID
            await ws.send_json(payload)

            handler_id = None
            sent = False
            transcript = None
            speech = None

            async def send_audio(hid):
                chunk_size = 4096
                for i in range(0, len(pcm), chunk_size):
                    await ws.send_bytes(bytes([hid]) + pcm[i:i + chunk_size])
                    await asyncio.sleep(0.005)
                # end of audio: empty payload with handler id
                await ws.send_bytes(bytes([hid]))
                print("[audio inviato, stream chiuso]")

            while True:
                msg = await ws.receive()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    continue
                if msg.type == aiohttp.WSMsgType.TEXT:
                    m = json.loads(msg.data)
                    if m.get("type") == "result":
                        continue
                    if m.get("type") != "event":
                        continue
                    ev = m["event"]; t = ev["type"]
                    print("event:", t)
                    if t == "run-start":
                        handler_id = ev["data"]["runner_data"]["stt_binary_handler_id"]
                        print("  handler_id:", handler_id)
                        if handler_id is not None and not sent:
                            sent = True
                            asyncio.create_task(send_audio(handler_id))
                    elif t == "stt-end":
                        transcript = ev["data"].get("stt_output", {}).get("text")
                        print("  TRASCRIZIONE:", repr(transcript))
                    elif t == "intent-end":
                        speech = ev["data"]["intent_output"]["response"]["speech"]["plain"]["speech"]
                        print("  RISPOSTA:", repr(speech))
                    elif t == "error":
                        print("  ERRORE:", json.dumps(ev["data"])[:300])
                    elif t == "run-end":
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    print("ws closed/error")
                    break

            print("---")
            print("TRASCRIZIONE FINALE:", transcript)
            print("RISPOSTA FINALE:", speech)

asyncio.run(main())
