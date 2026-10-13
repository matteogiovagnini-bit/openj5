import asyncio, json, sys, aiohttp

TOKEN = sys.argv[1]
PIPEID = sys.argv[2]
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

            r = await call(
                ws, 1, "assist_pipeline/pipeline/update",
                pipeline_id=PIPEID,
                name="Assistente Locale",
                language="it",
                conversation_engine="conversation.home_assistant",
                conversation_language="it",
                stt_engine="stt.faster_whisper",
                stt_language="it",
                tts_engine="tts.piper",
                tts_language="it_IT",
                tts_voice="it_IT-serena-medium",
                wake_word_entity=None,
                wake_word_id=None,
            )
            print("=== UPDATE ===")
            print(json.dumps(r, indent=1, ensure_ascii=False)[:1200])


asyncio.run(main())
