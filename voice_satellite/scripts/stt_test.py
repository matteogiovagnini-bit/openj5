import asyncio, wave, sys
from wyoming.client import AsyncTcpClient
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.asr import Transcribe, Transcript

async def main(path, uri):
    with wave.open(path, "rb") as wav:
        rate = wav.getframerate()
        width = wav.getsampwidth()
        channels = wav.getnchannels()
        frames = wav.getnframes()
        dur = frames / rate
        client = AsyncTcpClient.from_uri(uri)
        await client.connect()
        try:
            await client.write_event(Transcribe(language="it").event())
            await client.write_event(AudioStart(rate=rate, width=width, channels=channels).event())
            total = 0
            while True:
                chunk = wav.readframes(2048)
                if not chunk:
                    break
                total += len(chunk)
                await client.write_event(AudioChunk(rate=rate, width=width, channels=channels, audio=chunk).event())
            await client.write_event(AudioStop().event())
            print(f"[audio inviato: {total} byte, {rate}Hz {width*8}bit {channels}ch, ~{dur:.1f}s]")
            while True:
                ev = await client.read_event()
                if ev is None:
                    print("[connessione chiusa senza transcript]")
                    break
                if Transcript.is_type(ev.type):
                    t = Transcript.from_event(ev)
                    print("TRASCRIZIONE:", repr(t.text))
                    break
        finally:
            await client.disconnect()

asyncio.run(main(sys.argv[1], sys.argv[2]))
