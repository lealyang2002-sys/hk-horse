"""
Volcano Engine (豆包) Realtime Dialogue API — binary WebSocket client.
Input : raw PCM  16 kHz · 16-bit · mono · little-endian
Output: raw audio bytes (OGG/Opus) from the TTS stream
"""

import asyncio
import json
import struct
import uuid

import websockets

_WS_URL = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"

# ── Binary frame constants ──────────────────────────────────────────────────
_HDR0 = 0x11            # protocol_version=1, header_size=1

_MT_FULL_CLIENT  = 0b0001
_MT_AUDIO_CLIENT = 0b0010
_MT_FULL_SERVER  = 0b1001
_MT_AUDIO_SERVER = 0b1011
_MT_ERROR        = 0b1111

_FLAG_HAS_EVENT = 0b0100

_SER_RAW  = 0b0000
_SER_JSON = 0b0001
_COMP_NONE = 0b0000

# ── Event IDs ───────────────────────────────────────────────────────────────
_EV_START_CONN     = 1
_EV_FINISH_CONN    = 2
_EV_START_SESSION  = 100
_EV_FINISH_SESSION = 102
_EV_TASK_REQUEST   = 200
_EV_END_ASR        = 400
_EV_TTS_RESPONSE   = 352
_EV_TTS_ENDED      = 359
_EV_NO_CONTENT     = 459  # server detected no speech in the audio

_EV_TERMINAL = frozenset({_EV_TTS_ENDED, _EV_NO_CONTENT})


def _build(msg_type: int, event_id: int, payload: bytes,
           session_id: str = None, serialize: int = _SER_JSON) -> bytes:
    hdr = bytes([
        _HDR0,
        (msg_type << 4) | _FLAG_HAS_EVENT,
        (serialize << 4) | _COMP_NONE,
        0x00,
    ])
    ev = struct.pack(">I", event_id)
    if session_id is not None:
        sid_b = session_id.encode()
        sess  = struct.pack(">I", len(sid_b)) + sid_b
    else:
        sess = b""
    return hdr + ev + sess + struct.pack(">I", len(payload)) + payload


def _parse(data: bytes) -> dict:
    b1, b2 = data[1], data[2]
    msg_type  = (b1 >> 4) & 0xF
    flags     = b1 & 0xF
    serialize = (b2 >> 4) & 0xF

    pos = 4
    event_id = None
    if flags & _FLAG_HAS_EVENT:
        event_id = struct.unpack(">I", data[pos:pos+4])[0]
        pos += 4

    session_id = None
    if event_id is not None and event_id >= 100:
        sid_len = struct.unpack(">I", data[pos:pos+4])[0]
        pos += 4
        session_id = data[pos:pos+sid_len].decode(errors="replace")
        pos += sid_len

    psize = struct.unpack(">I", data[pos:pos+4])[0]
    pos += 4
    payload = data[pos:pos+psize]

    return {
        "msg_type":   msg_type,
        "event_id":   event_id,
        "session_id": session_id,
        "serialize":  serialize,
        "payload":    payload,
    }


def _log_frame(tag: str, fr: dict):
    try:
        payload_preview = fr["payload"][:200].decode(errors="replace") if fr["payload"] else ""
    except Exception:
        payload_preview = repr(fr["payload"][:40])
    print(f"[Volcano] {tag}: event={fr['event_id']} msg_type={fr['msg_type']} "
          f"payload_len={len(fr['payload'])} preview={payload_preview!r}")


async def _run(pcm: bytes, app_id: str, api_key: str,
               system_role: str, speaker: str) -> bytes:
    sid = uuid.uuid4().hex

    headers = {
        "X-Api-App-ID":      app_id,
        "X-Api-Access-Key":  api_key,
        "X-Api-Resource-Id": "volc.speech.dialog",
        "X-Api-App-Key":     "PlgvMymc7f3tQnJ6",
    }

    start_payload = json.dumps({
        "tts": {"speaker": speaker},
        "dialog": {
            "bot_name":    "賽馬AI助手",
            "system_role": system_role,
            "model":       "1.2.1.1",
            "extra":       {"input_mod": "push_to_talk"},
        },
        "asr": {"audio_info": {
            "format":      "raw",
            "sample_rate": 16000,
            "channel":     1,
        }},
    }, ensure_ascii=False).encode()

    audio_out: list[bytes] = []

    print(f"[Volcano] Connecting to {_WS_URL} ...")
    async with websockets.connect(
        _WS_URL,
        additional_headers=headers,
        open_timeout=15,
        close_timeout=5,
    ) as ws:
        # ── 1. StartConnection → wait for ack ────────────────────────────
        await ws.send(_build(_MT_FULL_CLIENT, _EV_START_CONN, b"{}"))
        print("[Volcano] Sent StartConnection, waiting for ack...")
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        fr = _parse(raw)
        _log_frame("StartConn-ack", fr)
        if fr["msg_type"] == _MT_ERROR:
            raise RuntimeError(f"Connection refused: {fr['payload'].decode(errors='replace')}")

        # ── 2. StartSession → wait for ack ───────────────────────────────
        await ws.send(_build(_MT_FULL_CLIENT, _EV_START_SESSION,
                             start_payload, session_id=sid))
        print("[Volcano] Sent StartSession, waiting for ack...")
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        fr = _parse(raw)
        _log_frame("StartSession-ack", fr)
        if fr["msg_type"] == _MT_ERROR:
            raise RuntimeError(f"Session refused: {fr['payload'].decode(errors='replace')}")

        # ── 3. Stream PCM (100 ms chunks) ────────────────────────────────
        chunk_count = 0
        for i in range(0, len(pcm), 3200):
            await ws.send(_build(_MT_AUDIO_CLIENT, _EV_TASK_REQUEST,
                                 pcm[i:i+3200], session_id=sid,
                                 serialize=_SER_RAW))
            chunk_count += 1
        print(f"[Volcano] Streamed {chunk_count} audio chunks")

        # ── 4. EndASR ────────────────────────────────────────────────────
        await ws.send(_build(_MT_FULL_CLIENT, _EV_END_ASR, b"{}",
                             session_id=sid))
        print("[Volcano] Sent EndASR, collecting TTS response...")

        # ── 5. Collect TTS audio ─────────────────────────────────────────
        async def _collect():
            async for msg in ws:
                if not isinstance(msg, bytes):
                    continue
                fr = _parse(msg)
                eid = fr.get("event_id")
                _log_frame(f"recv", fr)
                if fr["msg_type"] == _MT_ERROR:
                    raise RuntimeError(fr["payload"].decode(errors="replace"))
                if eid == _EV_TTS_RESPONSE:
                    audio_out.append(fr["payload"])
                elif eid in _EV_TERMINAL:
                    if eid == _EV_NO_CONTENT:
                        print("[Volcano] NoContent (no speech detected), exiting cleanly")
                    else:
                        print(f"[Volcano] TTSEnded, total audio={sum(len(x) for x in audio_out)} bytes")
                    break

        await asyncio.wait_for(_collect(), timeout=60)

        # ── 6. Graceful shutdown ─────────────────────────────────────────
        try:
            await ws.send(_build(_MT_FULL_CLIENT, _EV_FINISH_SESSION,
                                 b"{}", session_id=sid))
            await ws.send(_build(_MT_FULL_CLIENT, _EV_FINISH_CONN, b"{}"))
        except Exception:
            pass

    return b"".join(audio_out)


_SYSTEM_ROLE = (
    "你是專業的香港賽馬分析師，為VIP貴客提供賽事諮詢及投注建議。"
    "請用廣東話或普通話作答，語氣專業親切，每次回答控制在100字以內。"
)
_DEFAULT_SPEAKER = "zh_male_yunzhou_jupiter_bigtts"


def volcano_chat_sync(
    pcm_bytes: bytes,
    app_id: str,
    api_key: str,
    system_role: str = _SYSTEM_ROLE,
    speaker: str = _DEFAULT_SPEAKER,
) -> bytes:
    """Blocking wrapper. Returns raw TTS audio bytes (OGG/Opus)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _run(pcm_bytes, app_id, api_key, system_role, speaker)
        )
    finally:
        loop.close()
