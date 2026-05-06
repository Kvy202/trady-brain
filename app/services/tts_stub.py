# Phase 2 uses device-side TTS (Android TextToSpeech).
# This stub is a placeholder for future cloud TTS (e.g. Google Cloud TTS, ElevenLabs).
import logging

logger = logging.getLogger("trady.tts_stub")


def synthesize_stub(text: str, lang: str = "en-IN") -> dict:
    logger.debug(f"[TTSStub] Would synthesize: '{text[:60]}' lang={lang}")
    return {"audio_url": None, "text": text, "lang": lang, "engine": "device"}
