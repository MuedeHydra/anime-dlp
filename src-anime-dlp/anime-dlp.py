# !/bin/python3

# ---------------------------------
#
#   Anime-dlp
#   Autor: MüdeHydra
#   Datum: 26.11.2024
#   version: 0.9
#
# ---------------------------------

from flask import Flask, render_template, request
from flask_socketio import SocketIO
# import socketio
import threading
import time
import requests
import os
import subprocess
from pathlib import Path

from conf_reader import conf_reader
import extractors

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')

open_queue: list = []
open_dowanload: list = []
open_to_pars: list = []
faild: list = []
thread: bool = False  # global var set socket io on else it hibernats

conf: dict = {}


threads: list = []
threads_output: list = []

for n in range(1):
    threads.append(n)
    threads_output.append(f"thread {n}: idle")


# ----------------------------------------------------------
# aniworld
# ----------------------------------------------------------
def read_html_from_requests(url: str):
    html = requests.get(url)
    return html.text


def find_episode(html_data: str) -> int:
    """count the episodes"""
    start: int = (html_data.find('<strong>Episoden:</strong>')) + 41 # to remove class=row
    stop: int = start +html_data[start:].find("</ul>")
    hoster: str = html_data[start:stop].replace("  ", "")

    hoster_li: list = hoster.split("</li>")
    hoster_li.pop()  # remove the last element because its emty

    return len(hoster_li)


def find_hoster(html_data: str):
    """finds the strams from aniworld"""
    start: int = (html_data.find('<ul class="row">')) + 17  # to remove class=row
    stop: int = start + html_data[start:].find("</ul>")
    hoster: str = html_data[start:stop].replace("  ", "")

    hoster_li: list = hoster.split("</li>")
    hoster_li.pop()  # remove the last element because its emty

    hoster_data: list = []

    def pars(data: str, id: str) -> str:
        start: int = data.find(id) + len(id)
        if data[start] == '"':
            start += 1
        stop: int = start + data[start:].find('"')
        return data[start:stop]

    for i in hoster_li:
        data_link_id: str = pars(i, "data-link-id=")
        data_lang_key: str = pars(i, "data-lang-key=")
        hoster_name: str = pars(i, "Hoster ")
        hoster_data.append([data_link_id, data_lang_key, hoster_name])

    return hoster_data


def find_stream_from_hoster(hoster_data: list) -> list:
    """search the stream in the prefered lang and hoster"""
    # build preferred list
    preferred_list: list = []
    for i in conf["preferred_lang"]:
        for j in conf["preferred_provider"]:
            preferred_list.append([i.replace("Sub", "1").replace("OUM_EN", "2").replace("OUM_DE", "3"), j])

    # find aniworld id
    for i in preferred_list:
        for j in hoster_data:
            if i[0] == j[1] and i[1] == j[2]:
                return j


def get_anime_name(url: str) -> str:
    name = ""
    for n in url:
        name += n
    name = name.rpartition("/")
    name = name[2]
    return name


def get_episoden(url: str) -> tuple[int, int, int, str]:
    """get the start and stop from the url + it storts the url"""
    start: int = 0
    stop: int = 0
    season: int = 0

    if url.count("episode") == 1:
        url_s = url.split("/")
        season = int(url_s[len(url_s)-2].split("-")[1])
        episode = int(url_s[len(url_s)-1].split("-")[1])
        start = episode
        stop = episode
        url = url.removesuffix(f"/staffel-{season}/episode-{episode}")
    elif url.count("staffel") == 1:
        url_s = url.split("/")
        season = int(url_s[len(url_s)-1].split("-")[1])
        start = 1
        url = url.removesuffix(f"/staffel-{season}")
        stop = find_episode(read_html_from_requests(f"{url}/staffel-{season}"))

    return start, stop, season, url


def get_url(base_url: str, season: int, episode: int) -> str:
    url: str = f"{base_url}/staffel-{season}/episode-{episode}"
    html = read_html_from_requests(url)
    hoster_li: list = find_hoster(html)
    stream: list = find_stream_from_hoster(hoster_li)

    if stream[2] == "Vidoza":
        link_id: str = stream[0]
        html = read_html_from_requests(f"https://aniworld.to/redirect/{link_id}")
        return extractors.get_download_url_Vidoza(html)
    elif stream[2] == "Filemoon":
        link_id: str = stream[0]
        return extractors.get_donload_url_Filemoon(url, f"redirect/{link_id}")
    elif stream[2] == "VOE":
        link_id: str = stream[0]
        return extractors.get_donload_url_VOE(f"https://aniworld.to/redirect/{link_id}")
    else:
        print("No hoster found")
        return ""


def if_already_downloaded(path: str) -> bool:
    if path.startswith("~"):
        path = path.replace("~", str(Path.home()))
    return os.path.isfile(path)


def anime_download_prepare(url: str, format: str = "mp4", website: str = "aniworld") -> None:

    start, stop, season, url = get_episoden(url)

    anime_name = get_anime_name(url)

    for start in range(start, stop + 1):
        filename = f"{anime_name}/Season {season:02}/"
        filename += f"{anime_name}_S{season:02}E{start:02}.mp4"
        if if_already_downloaded(f"{conf["path_anime"]}/{filename}"):
            print("anime is already donloaded", filename)
            continue
        open_to_pars.append({"url": url, "filename": filename, "episode": start,
                             "season": season, "format": format, "website": website})


def anime_download():
    while len(open_to_pars) > 0:
        data = open_to_pars.pop(0)
        download_URL = get_url(data["url"], data["season"], data["episode"])
        data["download_URL"] = download_URL
        open_dowanload.append(data)
        time.sleep(120)
        # if len(open_to_pars) == 0:
        #     break


# ----------------------------------------------------------
# event handeler
# ----------------------------------------------------------
def anime_dlp(url: str, file_format="mp4") -> None:
    print(url, file_format)
    anime_download_prepare(url, file_format)


def youtube(url: str, file_format="mp4") -> None:
    print(url, file_format)
    open_dowanload.append([url, file_format, None,"youtube"])


def download(index: int, data: dict) -> None:
    """start the download in a thread"""

    threads_output[index] = f"thread {index}: starting"

    if data["website"] == "aniworld":
        args = ["yt-dlp", "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b",
                "--fragment-retries", "infinite", "--concurrent-fragments", "4",
                "-o", f"{conf["path_anime"]}/{data["filename"]}", data["download_URL"]]
    elif data["format"] == "m4a":
        args = ["yt-dlp", "--embed-metadata", "-f",
                "ba[ext=m4a]",
                "--embed-thumbnail", "--fragment-retries", "infinite",
                "--concurrent-fragments", "4",
                "-o", f"{conf["path_yt"]}/%(title)s.%(ext)s", data[0]]
    else:
        args = ["yt-dlp", "--embed-metadata", "-f",
                "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b",
                "--embed-thumbnail", "--fragment-retries", "infinite",
                "--concurrent-fragments", "4",
                "-o", f"{conf["path_yt"]}/%(title)s.%(ext)s", data[0]]
    p = subprocess.Popen(args,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, universal_newlines=True)

    # print(f"download: {p}")

    if data["website"] == "aniworld":
        name: str = short_name(data["filename"])
    else:
        name: str = data["filename"]

    while p.poll() is None:
        s = f"thread {index}: {name} | {p.stdout.readline()}"
        threads_output[index] = s
    p.wait()

    if not if_already_downloaded(f"{conf["path_anime"]}/{data["filename"]}"):
        faild.append(data)
    threads.append(index)
    threads_output[index] = f"thread {index}: done"


def download_handler() -> None:
    """put the url to the right queue"""
    while len(open_queue) > 0:
        i = open_queue.pop()
        print(f"download_handler: {i}")
        if ("aniworld.to" or "s.to") in i[0]:
            anime_dlp(i[0], i[1])
        elif "wallhaven" in i[0]:
            # wallhaven(i[0])
            pass
        elif "wallpaperflare" in i[0]:
            # wallpaperflare(i[0])
            pass
        elif "youtu" in i[0]:
            youtube(i[0], i[1])


# website
def short_name(name: str) -> str:
    if "/" in name:
        name = name.rpartition("/")[-1]
    return name


def progress():
    """prepare the text for the website"""
    output = ""
    for n in threads_output:
        if n.count("\n") == 0:
            output += n + "\n"
        else:
            output += n
    return f"{output}"


def make_html_list(li: list) -> str:
    """create a html list for the website"""
    s: str = ""
    for i in li:
        if i["website"] == "aniworld":
            name = i["filename"]
            name = short_name(name)
        else:
            name = i["url"]
        s += f"<li>{name}</li>"
    return s


def background_thread() -> None:
    """works in background and handle events like main_loop"""
    url_fetcher: bool = False
    url_handler_thread = threading.Thread()
    handler: bool = False
    handler_thread = threading.Thread()

    while True:
        # handle download urls
        if len(open_queue) > 0 and not handler:
            handler_thread = threading.Thread(target=download_handler)
            handler_thread.start()

        handler = handler_thread.is_alive()

        if len(open_to_pars) > 0 and not url_fetcher:
            print("starting url fetchung")
            url_handler_thread = threading.Thread(target=anime_download)
            url_handler_thread.start()

        url_fetcher = url_handler_thread.is_alive()

        # start one download
        if len(open_dowanload) > 0 and len(threads) > 0:
            threading.Thread(target=download,
                             args=(threads.pop(0), open_dowanload.pop(0))
                             ).start()

        # update the web site
        if thread:
            socketio.emit('anime', {
                'open': make_html_list(open_dowanload),
                'open_to_pars': make_html_list(open_to_pars),
                'faild': make_html_list(faild),
                "progress": progress()
            })
            time.sleep(2)
        else:
            time.sleep(5)


# ----------------------------------------------------------
# webseite
# ----------------------------------------------------------
@app.route("/", methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        file_format = request.form['file_format']
    else:
        url = request.args.get('url')
        file_format = request.args.get('file_format')
    print(f"new link resived. format = {file_format} | url = {url}")
    if url is not None:
        if file_format is None:
            open_queue.append([url, "mp4"])
        else:
            open_queue.append([url, file_format])
    print(open_queue)

    return render_template("index.html")


@socketio.on('connect')
def connect():
    global thread
    thread = True
    print('Client connected')


@socketio.on('disconnect')
def disconnect():
    global thread
    thread = False
    print('Client disconnected', request.sid)


if __name__ == '__main__':
    conf = conf_reader(f"{Path.home()}/python/anime-dlp-3/src-anime-dlp/anime-dlp.conf")
    # conf = conf_reader("~/python/anime-dlp-3/anime-dlp.conf")
    threading.Thread(target=background_thread, daemon=True).start()
    app.run()
    # app = socketio.WSGIApp(sio, app)
    # serve(app, host="0.0.0.0", port=5000)
