import asyncio, json, sys, aiohttp

TOKEN = sys.argv[1]
WS = "ws://127.0.0.1:8123/api/websocket"

async def call(ws, i, typ, **kw):
    payload = {"id": i, "type": typ}
    payload.update(kw)
    await ws.send_json(payload)
    while True:
        msg = await ws.receive_json()
        if msg.get("id") == i:
            return msg

async def main():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": TOKEN})
            await ws.receive_json()

            r = await call(ws, 1, "config/entity_registry/list")
            print("=== entita' stt/tts ===")
            for e in r.get("result", []):
                eid = e["entity_id"]
                if eid.startswith("stt.") or eid.startswith("tts.") or e.get("platform") in ("stt", "tts"):
                    print(f"  {eid:40s} platform={e.get('platform')} unique_id={e.get('unique_id')}")

            print("=== entita' wake_word ===")
            for e in r.get("result", []):
                if e.get("platform") == "wake_word" or e["entity_id"].startswith("wake_word."):
                    print(f"  {e['entity_id']:40s} platform={e.get('platform')} unique_id={e.get('unique_id')}")

            print("=== tutti i domini di entita' presenti ===")
            doms = sorted(set(e["entity_id"].split(".")[0] for e in r.get("result", [])))
            print(" ", doms)

asyncio.run(main())
