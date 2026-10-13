import asyncio, json, sys, aiohttp

TOKEN = sys.argv[1]
WS = "ws://127.0.0.1:8123/api/websocket"

async def main():
    # Leggi i config entry per trovare gli unique_id dei motori wyoming
    with open("/config/.storage/core.config_entries") as f:
        ce = json.load(f)
    for e in ce["data"]["entries"]:
        if e["domain"] == "wyoming":
            print("wyoming entry ->", repr(e.get("title")), "unique_id=", repr(e.get("unique_id")))

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS) as ws:
            msg = await ws.receive_json()
            print("recv:", msg["type"])
            await ws.send_json({"type": "auth", "access_token": TOKEN})
            msg = await ws.receive_json()
            print("auth:", msg["type"])
            await ws.send_json({"id": 1, "type": "assist_pipeline/pipeline/list"})
            msg = await ws.receive_json()
            print("=== PIPELINES ===")
            print(json.dumps(msg.get("result"), indent=1, ensure_ascii=False)[:2000])
            # lista lingue supportate
            await ws.send_json({"id": 2, "type": "assist_pipeline/pipeline/list"})
            # prova a listare le lingue
            await ws.send_json({"id": 3, "type": "assist_pipeline/pipeline/list"})

asyncio.run(main())
