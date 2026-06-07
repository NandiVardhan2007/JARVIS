"""Media playback — JioSaavn streams & YouTube fallback."""

import logging
import urllib.parse
import webbrowser
import requests
from base64 import b64decode
from Crypto.Cipher import DES
from livekit.agents import function_tool

try:
    import vlc
except ImportError:
    vlc = None

logger = logging.getLogger(__name__)

# Global VLC player instance
_vlc_instance = vlc.Instance('--no-video', '--quiet', '--no-plugins-cache') if vlc else None
_media_player = _vlc_instance.media_player_new() if _vlc_instance else None

import threading
import socket

def _media_command_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = 5006
    while port <= 5010:
        try:
            sock.bind(("127.0.0.1", port))
            break
        except OSError:
            port += 1
    else:
        logger.error("Could not bind media listener to any port (5006-5010)")
        return
    
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            command = data.decode('utf-8').strip()
            if _media_player:
                if command == "playpause":
                    if _media_player.is_playing():
                        _media_player.pause()
                    else:
                        _media_player.play()
                elif command == "stop":
                    _media_player.stop()
                elif command == "duck":
                    _media_player.audio_set_volume(20)
                elif command == "unduck":
                    _media_player.audio_set_volume(100)
        except Exception as e:
            logger.error(f"UDP listener error: {e}")

def _song_finished_callback(event):
    import json
    import socket
    try:
        island_payload = {
            "state": "idle",
            "context": "",
            "category": "",
            "tool_name": "",
            "description": "",
            "notify": {
                "title": "Playback Ended",
                "body": "Song finished. Play another?",
                "category": "MEDIA"
            }
        }
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(json.dumps(island_payload).encode(), ("127.0.0.1", 5005))
        sock.close()
    except Exception as e:
        logger.error(f"Failed to notify island on end: {e}")

_listener_started = False
def _ensure_listener():
    global _listener_started
    if _listener_started or not _vlc_instance:
        return
    _listener_started = True
    listener_thread = threading.Thread(target=_media_command_listener, daemon=True)
    listener_thread.start()

    if _media_player:
        event_manager = _media_player.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, _song_finished_callback)

def _decrypt_saavn_url(encrypted_url: str) -> str:
    """Decrypts JioSaavn encrypted_media_url."""
    des = DES.new(b'38346591', DES.MODE_ECB)
    decrypted = des.decrypt(b64decode(encrypted_url))
    # Remove PKCS5 padding
    pad_len = decrypted[-1]
    if 0 < pad_len <= 8:
        decrypted = decrypted[:-pad_len]
    url = decrypted.decode('utf-8').strip()
    # Upgrade to 320kbps
    url = url.replace('preview.saavncdn.com', 'aac.saavncdn.com')
    if '_96.mp4' in url:
        url = url.replace('_96.mp4', '_320.mp4')
    elif '_96_p.mp4' in url:
        url = url.replace('_96_p.mp4', '_320.mp4')
    return url

@function_tool
async def play_media(media_name: str, media_type: str = "song") -> str:
    """
    Plays media content directly in the background using JioSaavn.

    Args:
        media_name: Name of the song, video, or content to play.
        media_type: Type of content — "song", "video", "movie", etc.
    """
    logger.info(f"Playing media: {media_name} ({media_type})")
    _ensure_listener()
    try:
        # Clean query for better search results
        import re
        clean_query = media_name
        for word in ["song by", "song", "by", "play", "music"]:
            clean_query = re.sub(rf'\b{word}\b', '', clean_query, flags=re.IGNORECASE)
        clean_query = clean_query.strip()
        if not clean_query:
            clean_query = media_name
            
        # Search JioSaavn
        search_resp = requests.get(
            "https://www.jiosaavn.com/api.php",
            params={
                "__call": "autocomplete.get",
                "query": clean_query,
                "_format": "json",
                "_marker": "0",
                "ctx": "web6dot0"
            },
            timeout=5
        ).json()

        if "songs" in search_resp and "data" in search_resp["songs"] and len(search_resp["songs"]["data"]) > 0:
            song_id = search_resp["songs"]["data"][0]["id"]
            
            # Get song details
            details_resp = requests.get(
                "https://www.jiosaavn.com/api.php",
                params={
                    "__call": "song.getDetails",
                    "pids": song_id,
                    "_format": "json",
                    "_marker": "0",
                    "ctx": "web6dot0"
                },
                timeout=5
            ).json()
            
            if "songs" in details_resp and len(details_resp["songs"]) > 0:
                song_data = details_resp["songs"][0]
                title = song_data.get("title", media_name)
                # Unescape HTML entities like &quot;
                import html
                title = html.unescape(title)
                
                # Get artist and image
                artist = song_data.get("primary_artists", "Unknown Artist")
                artist = html.unescape(artist)
                image_url = song_data.get("image", "").replace("150x150", "500x500")

                encrypted_url = song_data.get("encrypted_media_url")
                if encrypted_url and _media_player:
                    stream_url = _decrypt_saavn_url(encrypted_url)
                    media = _vlc_instance.media_new(stream_url)
                    _media_player.set_media(media)
                    _media_player.play()
                    
                    # Update dynamic island
                    try:
                        import json
                        import socket
                        island_payload = {
                            "state": "expanded",
                            "context": "tool",
                            "category": "MEDIA",
                            "tool_name": "Now Playing",
                            "description": f"{title}\nBy {artist}",
                            "image_url": image_url
                        }
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.sendto(json.dumps(island_payload).encode(), ("127.0.0.1", 5005))
                        sock.close()
                    except Exception as e:
                        logger.error(f"Failed to update island: {e}")
                        
                    return f"Now playing directly: {title} by {artist}"

        # Fallback: YouTube search
        query = urllib.parse.quote(f"{media_name} {media_type}")
        webbrowser.open(f"https://www.youtube.com/results?search_query={query}")
        return f"Opening YouTube search for '{media_name}'."
    except Exception as e:
        logger.error(f"Playback error: {e}")
        return f"Media playback failed: {e}"

@function_tool
async def stop_media() -> str:
    """Stops the currently playing background music."""
    if _media_player and _media_player.is_playing():
        _media_player.stop()
        return "Music stopped."
    return "No background music is currently playing."
