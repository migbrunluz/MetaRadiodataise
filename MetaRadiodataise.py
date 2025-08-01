from flask import Flask, request, Response, stream_with_context, jsonify
from xml.etree import ElementTree as ET
import requests
import hashlib
import json

app = Flask(__name__)

RADIO_PARADISE_API = "https://api.radioparadise.com/api/now_playing?chan=3"

@app.route("/metadatas/goomradio/<utilisateur>.jsonp")
def goomradio_metadata(utilisateur):
    try:
        # Fetch metadata from Radio Paradise (channel 3 = Radio 2050)
        resp = requests.get(RADIO_PARADISE_API, timeout=10)
        data = resp.json()

        artist = data.get("artist", "Unknown Artist")
        title = data.get("title", "Unknown Title")
        cover_url = data.get("cover", "")
        started_timestamp = data.get("started", 0)  # Use Unix timestamp (e.g., 1721994741)

        # Construct JSONP response data
        jsonp_data = {
            "sj_config_id": "goomradio",
            "radio_id": "9571617",
            "utilisateur": utilisateur,
            "artist": artist,
            "title": title,
            "site": "2",
            "duration": "3600000",
            "media_type": "SONG",
            "objectid": "187222",
            "mediaid": "280261",
            "tracker7": "",
            "timestamp": str(started_timestamp),
            "cover_url": cover_url,
            "url_track": ""
        }

        return Response(
            f'jsonpCallback({json.dumps(jsonp_data)});',
            mimetype="application/javascript"
        )

    except Exception as e:
        error_response = {"error": "Could not fetch metadata", "details": str(e)}
        return Response(
            f'jsonpCallback({json.dumps(error_response)});',
            mimetype="application/javascript"
        )

@app.route('/brasil.stream.http')
def stream_radio_proxy():
    remote_url = "https://stream.radioparadise.com/mp3-192"  # Main Mix, MP3 192 kbps

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    upstream = requests.get(remote_url, headers=headers, stream=True)

    return Response(
        stream_with_context(upstream.iter_content(chunk_size=4096)),
        content_type=upstream.headers.get('Content-Type', 'audio/mpeg')
    )

@app.route('/now_playing_api/now_playing/id_station/2')
def now_playing_rp_mainmix():
    try:
        # Fetch the now playing info from Radio Paradise JSON API (Main Mix = chan=0)
        resp = requests.get("https://api.radioparadise.com/api/now_playing?chan=0", timeout=10)
        resp.raise_for_status()
        data = resp.json()

        artist = data.get("artist", "Radio Paradise")
        title = data.get("title", "Main Mix")
        album = data.get("album", "Radio Paradise")
        song_id = str(data.get("time", 0))  # Using `time` as a stand-in for ID

        # Use RP cover image, fallback to hash if missing
        cover = data.get("cover") or ""
        cover_med = data.get("cover_med") or cover
        cover_small = data.get("cover_small") or cover

        # If cover is missing, use generated hash fallback
        if not cover:
            hash_input = f"{artist}-{title}".encode("utf-8")
            image_id = hashlib.md5(hash_input).hexdigest()
            cover = f"http://web.archive.org/web/20140823084303/http://api.imusicaradios.com.br/now_playing_api/image/id/{image_id}"
            cover_med = cover_small = cover

        result = {
            "image_url_md": cover_med,
            "id_history": "0",
            "id_catalog": song_id,
            "image_url_hd": cover,
            "image_url": cover_small,
            "artist_name": artist,
            "id_station": "2",  # keep as-is
            "share_url": "http://web.archive.org/web/20140823084303/https://www.coca-cola.fm/mx/base/",
            "short_share_text": "Estoy escuchando Radio Paradise",
            "album_title": album,
            "track_title": title,
            "long_share_text": "Estoy escuchando Radio Paradise",
            "version": "java_now_playing"
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": "Failed to fetch now playing", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
