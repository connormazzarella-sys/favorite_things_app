import os
from flask import Flask, jsonify, send_file, render_template, abort, Response, request
from backend import library, radio

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/manifest.json")
def manifest():
    return send_file(os.path.join(app.static_folder, "manifest.json"), mimetype="application/manifest+json")


@app.route("/api/genres", methods=["GET", "POST"])
def api_genres():
    if request.method == "POST":
        name = (request.get_json(silent=True) or {}).get("name", "")
        try:
            library.create_genre(name)
        except ValueError:
            abort(400)
    return jsonify(library.list_genres())


@app.route("/api/genres/<genre>/albums")
def api_albums(genre):
    try:
        return jsonify(library.list_albums(genre))
    except ValueError:
        abort(400)


@app.route("/api/albums/<genre>/<album>/songs")
def api_songs(genre, album):
    try:
        return jsonify(library.list_songs(genre, album))
    except ValueError:
        abort(400)


@app.route("/api/stream/<genre>/<album>/<filename>")
def api_stream(genre, album, filename):
    try:
        path = library.get_song_path(genre, album, filename)
    except ValueError:
        abort(400)
    if not path:
        abort(404)
    return send_file(path, conditional=True, mimetype="audio/mpeg")


@app.route("/api/cover/<genre>/<album>")
def api_cover(genre, album):
    try:
        data, mime = library.get_cover_bytes(genre, album)
    except ValueError:
        abort(400)
    return Response(data, mimetype=mime)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    genre = request.form.get("genre", "").strip()
    album = request.form.get("album", "").strip()
    artist = request.form.get("artist", "").strip()
    title = request.form.get("title", "").strip()
    files = request.files.getlist("files")
    if not genre or not album or not files:
        abort(400)
    try:
        library.create_album(genre, album, artist, title)
        for f in files:
            library.save_uploaded_song(genre, album, f.filename, f)
    except ValueError:
        abort(400)
    return jsonify({"ok": True})


@app.route("/api/radio/search")
def api_radio_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    try:
        return jsonify(radio.search_stations(q))
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/radio/stations", methods=["GET", "POST"])
def api_radio_stations():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name, url = data.get("name"), data.get("url")
        if not name or not url:
            abort(400)
        return jsonify(radio.add_station(name, url))
    return jsonify(radio.load_stations())


@app.route("/api/radio/stations/<int:idx>", methods=["DELETE"])
def api_radio_station_delete(idx):
    return jsonify(radio.remove_station(idx))


if __name__ == "__main__":
    print(f"Music library: {library.MUSIC_DIR}")
    app.run(host="127.0.0.1", port=8080, threaded=True, debug=False)
