from flask import Flask, request, Response
import requests
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



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
