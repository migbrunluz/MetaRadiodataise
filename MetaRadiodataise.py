from flask import Flask, request, Response
import requests
import json
import feedparser
from datetime import datetime
from html import escape
import uuid

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


    GENRE_NAMESPACE = uuid.NAMESPACE_URL
ITUNES_GENRES_URL = "https://itunes.apple.com/WebObjects/MZStoreServices.woa/ws/genres"

itunes_podcast_genres = {}
uuid_to_genre_id = {}

def load_podcast_genres():
    global itunes_podcast_genres, uuid_to_genre_id
    try:
        r = requests.get(ITUNES_GENRES_URL, timeout=10, verify=False)
        genres_json = r.json()
        itunes_podcast_genres = genres_json.get("26", {}).get("subgenres", {})
        uuid_to_genre_id.clear()
        for gid in itunes_podcast_genres:
            u = str(uuid.uuid5(GENRE_NAMESPACE, gid))
            uuid_to_genre_id[u] = gid
    except Exception as e:
        print(f"Error loading podcast genres: {e}")

load_podcast_genres()

def lookup_feed_url(itunes_id):
    lookup_url = f"https://itunes.apple.com/lookup?id={itunes_id}"
    r = requests.get(lookup_url, timeout=10, verify=False)
    data = r.json()
    if data.get("resultCount", 0) > 0:
        result = data["results"][0]
        return {
            "feedUrl": result.get("feedUrl"),
            "artwork": result.get("artworkUrl600"),
            "author": result.get("artistName", "Unknown Author"),
            "title": result.get("trackName", result.get("collectionName", "Podcast")),
            "summary": result.get("collectionCensoredName", "")
        }
    return None

@app.route("/v3.2/en-US/music/hub/podcast/")
def zune_podcast_feed():
    genre = request.args.get("genre", "1310")
    limit = int(request.args.get("limit", "10"))
    country = request.args.get("country", "us")

    rss_url = f"https://itunes.apple.com/{country}/rss/toppodcasts/limit={limit}/genre={genre}/json"
    try:
        r = requests.get(rss_url, timeout=10, verify=False)
        podcasts = r.json()["feed"]["entry"]

        editorial_items_xml = []
        media_items_xml = []
        seq = 1
        for podcast in podcasts:
            title = escape(podcast["title"]["label"])
            itunes_id = podcast["id"]["attributes"]["im:id"]
            feed_info = lookup_feed_url(itunes_id)
            if not feed_info:
                continue
            image_url = escape(feed_info.get("artwork", ""))

            editorial_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, str(itunes_id))}"
            image_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, str(itunes_id) + '-img')}"

            editorial_items_xml.append(f"""
            <editorialItem>
                <id>{editorial_id}</id>
                <link>
                    <type>Podcast</type>
                    <target>{itunes_id}</target>
                </link>
                <title>{title}</title>
                <text>{escape(feed_info.get('summary', ''))}</text>
                <sequenceNumber>{seq}</sequenceNumber>
                <image>
                    <id>{image_id}</id>
                </image>
                <backgroundImage>
                    <id>{image_id}</id>
                </backgroundImage>
            </editorialItem>
            """)

            media_items_xml.append(f"""
            <media>
                <id>{image_id}</id>
                <uri>{image_url}</uri>
                <format>jpg</format>
                <height>300</height>
                <width>300</width>
            </media>
            """)

            seq += 1

        now_iso = datetime.utcnow().isoformat() + "Z"

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<a:feed xmlns:a="http://www.w3.org/2005/Atom"
    xmlns:os="http://a9.com/-/spec/opensearch/1.1/"
    xmlns="http://schemas.zune.net/catalog/music/2007/10">
    <a:link rel="self" type="application/atom+xml" href="/v3.2/en-US/music/hub/podcast" />
    <a:updated>{now_iso}</a:updated>
    <a:title type="text">podcast</a:title>
    <a:id>podcast</a:id>
    <templates>
        <template>
            <mimeType>application/uix</mimeType>
            <templateName>PodcastHub</templateName>
        </template>
    </templates>
    <a:entry>
        <a:title type="text">List Of Items</a:title>
        <a:id>urn:uuid:podcastlist-{uuid.uuid4()}</a:id>
        <index>1</index>
        <editorialItems>
            {''.join(editorial_items_xml)}
        </editorialItems>
    </a:entry>
    <a:author>
        <a:name>Microsoft Corporation</a:name>
    </a:author>
    <mediaItems>
        {''.join(media_items_xml)}
    </mediaItems>
</a:feed>
"""
        return Response(xml, mimetype="application/atom+xml")
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/v3.2/en-US/podcast/<podcast_id>")
def podcast_detail(podcast_id):
    try:
        feed_info = lookup_feed_url(podcast_id)
        if not feed_info or not feed_info.get("feedUrl"):
            return "Feed not found", 404

        feed = feedparser.parse(feed_info["feedUrl"])
        now_iso = datetime.utcnow().isoformat() + "Z"

        podcast_title = escape(feed_info["title"])
        podcast_summary = escape(feed.feed.get("subtitle", feed.feed.get("description", feed_info["summary"])))
        podcast_image = escape(feed_info["artwork"] or feed.feed.get("image", {}).get("href", ""))
        podcast_author = escape(feed_info["author"])
        podcast_uuid = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, podcast_id)}"
        image_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, podcast_id + '-img')}"

        entries_xml = []
        media_items_xml = []

        for idx, entry in enumerate(feed.entries[:20], 1):
            entry_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, entry.get('link', '') + str(idx))}"
            title = escape(entry.get("title", "Untitled"))
            summary = escape(entry.get("summary", entry.get("description", "")))
            media_url = entry.get("enclosures", [{}])[0].get("href", "")
            duration = entry.get("itunes_duration", "")

            entries_xml.append(f"""
            <a:entry>
                <a:id>{entry_id}</a:id>
                <a:title type="text">{title}</a:title>
                <a:updated>{now_iso}</a:updated>
                <a:content type="text">{summary}</a:content>
                <link>
                    <type>PodcastEpisode</type>
                    <target>{media_url}</target>
                </link>
                <media>
                    <uri>{media_url}</uri>
                    <format>mp3</format>
                    <duration>{duration}</duration>
                </media>
            </a:entry>
            """)

        if podcast_image:
            media_items_xml.append(f"""
            <media>
                <id>{image_id}</id>
                <uri>{podcast_image}</uri>
                <format>jpg</format>
                <height>600</height>
                <width>600</width>
            </media>
            """)

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<a:feed xmlns:a="http://www.w3.org/2005/Atom"
        xmlns:os="http://a9.com/-/spec/opensearch/1.1/"
        xmlns="http://schemas.zune.net/catalog/music/2007/10">
    <a:id>{podcast_uuid}</a:id>
    <a:title type="text">{podcast_title}</a:title>
    <a:updated>{now_iso}</a:updated>
    <a:author>
        <a:name>{podcast_author}</a:name>
    </a:author>
    <link>
        <type>Podcast</type>
        <target>{podcast_id}</target>
    </link>
    <a:subtitle>{podcast_summary}</a:subtitle>
    <image>
        <id>{image_id}</id>
    </image>
    {''.join(entries_xml)}
    <mediaItems>
        {''.join(media_items_xml)}
    </mediaItems>
</a:feed>
"""
        return Response(xml, mimetype="application/atom+xml")
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/v3.2/<string:locale>/podcast")
def podcast_passthrough(locale):
    podcast_url = request.args.get('url')
    try:
        response = requests.get(podcast_url, timeout=10, verify=False)
        response.raise_for_status()
        return Response(response.content, mimetype="application/rss+xml")
    except requests.RequestException as e:
        return Response(f"Error fetching podcast: {str(e)}", status=502)    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
