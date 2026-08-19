"""
actions/music.py
---------------------------------------------------------------------
Plays music in response to "play <song>" commands.

Two paths, picked automatically:
  1. Spotify Web API (via spotipy), if NOVA_SPOTIFY_CLIENT_ID/SECRET
     are set in .env. Requires a Spotify Premium account and an active
     Spotify Connect device (phone/speaker/desktop app signed into the
     same account) to actually start playback -- the Web API can only
     control playback, it can't play audio itself.
  2. Local file playback, if Spotify isn't configured (or the query
     doesn't match anything on Spotify). Looks for a matching filename
     in python/music/ and plays it directly through the Bluetooth
     speaker via the `pygame` mixer -- no credentials needed at all,
     which is the more demo-safe default (NOVA_MUSIC_METHOD=local).

Drop a few royalty-free MP3s into python/music/ (see
python/music/README.md) so the "local" fallback has something to play.
---------------------------------------------------------------------
"""

import glob
import logging
import os

import config

logger = logging.getLogger("nova.music")

_spotify_client = None


def _get_spotify_client():
    global _spotify_client
    if _spotify_client is not None:
        return _spotify_client

    import spotipy
    from spotipy.oauth2 import SpotifyOAuth

    _spotify_client = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope="user-modify-playback-state user-read-playback-state",
    ))
    return _spotify_client


def _play_on_spotify(query: str) -> bool:
    try:
        sp = _get_spotify_client()
        results = sp.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            logger.warning("Spotify search for %r returned nothing.", query)
            return False

        track = items[0]
        devices = sp.devices().get("devices", [])
        if not devices:
            logger.warning("No active Spotify Connect device found to play on.")
            return False

        sp.start_playback(device_id=devices[0]["id"], uris=[track["uri"]])
        logger.info("Playing on Spotify: %s - %s", track["name"], track["artists"][0]["name"])
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Spotify playback failed (%s). Falling back to local files.", exc)
        return False


def _play_local(query: str) -> bool:
    if not os.path.isdir(config.LOCAL_MUSIC_DIR):
        logger.warning("Local music directory %s does not exist.", config.LOCAL_MUSIC_DIR)
        return False

    candidates = glob.glob(os.path.join(config.LOCAL_MUSIC_DIR, "*.mp3"))
    if not candidates:
        logger.warning("No .mp3 files found in %s.", config.LOCAL_MUSIC_DIR)
        return False

    # Naive "best match": filename contains the query (case-insensitive),
    # else just play the first track found so the demo always has *some*
    # audio response to "play music".
    query_lower = (query or "").lower().strip()
    match = next((c for c in candidates if query_lower and query_lower in os.path.basename(c).lower()),
                 candidates[0])

    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(match)
        pygame.mixer.music.play()
        logger.info("Playing local file: %s", match)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Local playback failed (%s).", exc)
        return False


def play(query: str = ""):
    if config.MUSIC_METHOD == "spotify" and config.SPOTIFY_CLIENT_ID:
        if _play_on_spotify(query):
            return
    _play_local(query)


def stop():
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:  # noqa: BLE001
        pass
