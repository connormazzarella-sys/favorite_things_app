"""Radio station search (radio-browser.info) + saved station list.

Mirrors the desktop app's radio tab, but playback is just an <audio src>
in the browser instead of spawning ffplay - the browser streams it directly.
"""
import os
import json
import requests
from . import library

RADIO_SEARCH_API = "https://de1.api.radio-browser.info/json/stations/search"


def _stations_file():
    return os.path.join(library.DATA_DIR, "radio_stations.json")


def load_stations():
    path = _stations_file()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_stations(stations):
    with open(_stations_file(), "w") as f:
        json.dump(stations, f, indent=2)


def search_stations(query):
    resp = requests.get(RADIO_SEARCH_API, params={
        "name": query, "limit": 25, "hidebroken": "true",
        "order": "clickcount", "reverse": "true",
    }, timeout=10, headers={"User-Agent": "MyFavoriteThingsMobile/1.0"})
    resp.raise_for_status()
    return [{
        "name": r.get("name", "Unknown"),
        "url": r.get("url_resolved") or r.get("url"),
        "country": r.get("countrycode", ""),
        "codec": r.get("codec", ""),
        "bitrate": r.get("bitrate", ""),
    } for r in resp.json() if r.get("url_resolved") or r.get("url")]


def add_station(name, url):
    stations = load_stations()
    if any(s["url"] == url for s in stations):
        return stations
    stations.append({"name": name, "url": url})
    save_stations(stations)
    return stations


def remove_station(index):
    stations = load_stations()
    if 0 <= index < len(stations):
        stations.pop(index)
        save_stations(stations)
    return stations
