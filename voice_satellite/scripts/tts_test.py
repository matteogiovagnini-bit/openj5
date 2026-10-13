import asyncio, wave, sys
from wyoming.client import AsyncTcpClient
from wyoming.tts import Synthesize
from wyoming.audio import AudioChunk, AudioStart, AudioStop

async def main(text, out, uri):
    client = AsyncTcpClient.from_uri(uri)
    await client.connect()
    rate = width = channels = None
    audio = bytearray()
    try:
        await client.write_event(Synthesize(text=text).event())
        while True:
            ev = await client.read_event()
            if ev is None:
                break
            if AudioStart.is_type(ev.type):
                a = AudioStart.from_event(ev)
                rate, width, channels = a.rate, a.width, a.channels
            elif AudioChunk.is_type(ev.type):
                c = AudioChunk.from_event(ev)
                audio.extend(c.audio)
            elif AudioStop.is_type(ev.type):
                break
    finally:
        await client.disconnect()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels or 1)
        w.setsampwidth(width or 2)
        w.setframerate(rate or 22050)
        w.writeframes(bytes(audio))
    print(f"[TTS ok: {len(audio)} byte, {rate}Hz {(width or 2)*8}bit {channels or 1}ch]")

asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
