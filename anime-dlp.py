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
from requests_html import HTMLSession
import os
import csv
import datetime
import subprocess
from pathlib import Path
from waitress import serve

from conf_reader import conf_reader

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins='*')
# sio = socketio.Client()  # (app, cors_allowed_origins='*')
# sio = socketio.Server()  # (app, cors_allowed_origins='*')
session = HTMLSession()

open_queue: list = []
open_dowanload: list = []
thread: bool = False  # global var set socket io on else it hibernats

conf: dict = {}

path_tags: str = "~/python/anime-dlp-2/tags.csv"
path_wallpaper: str = "$HOME/dokumente-sync/wallpaper"


threads: list = []
threads_output: list = []

for n in range(1):
    threads.append(n)
    threads_output.append(f"thread {n}: idle")


# ----------------------------------------------------------
# wallpaper
# ----------------------------------------------------------
def get_data(url: str) -> list:
    """download html data from url"""
    if not url.endswith("download"):
        url += "/download"
    # respnse = requests.get(url)
    respnse = session.get(url)
    html: str = respnse.text
    line: list = html.splitlines()
    return (line)


def get_name(html: list) -> str:
    """get name from wallpaper"""
    for i in html:
        if """<h1 class="view_h1">HD wallpaper:""" in i:
            title: str = i[34:len(i) - 5]
            return (title[:title.find(",")].replace(" ", "-"))


def get_time() -> str:
    """get and format time"""
    t = datetime.datetime.now()
    return (t.strftime("%Y-%m-%d_%H:%M:%S"))


def get_tags(html: list) -> list:
    """read tags and return them alphabeticly"""
    for i in html:
        if """<meta name="keywords" content=""" in i:
            # print(i[31:len(i) - 460])
            # l:list = (i[31:i.find("HD wallpapers") - 2]).split(", ")
            l: set = set((i[31:i.find('"> <meta name=')]).split(", "))
            black_list: set = {
                'HD wallpapers', 'PC wallpapers', 'mobile wallpapers',
                'tablet wallpapers', 'HD desktop', 'free download',
                '1080P', '2K', '4K', '5K', "8k", "8K", "720p", "8k uhd"
            }
            return (sorted(list(l - black_list)))


def write_csv(name: str, tags: list) -> None:
    """write tags to csv file"""
    to_add: list = [f"{name}"]
    to_add.extend(tags)
    with open(path_tags, "a", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(to_add)


def add_metadata(url: str, filename: str) -> None:
    """add url to img as metadata"""
    print(f'exiftool -Comment="{url}" {filename}')
    os.system(f'exiftool -overwrite_original -Comment="{url}" "{filename}"')


def prepare_download(name: str, tags: list, url: str, img_url: str) -> None:

    timeformatet: str = get_time()
    filetyp: str = img_url[-3:]
    filename: str = f"{name}_{timeformatet}.{filetyp}"

    os.system(f'wget -O "{path_wallpaper}/{filename}" {img_url}')
    write_csv(filename, tags)
    add_metadata(url, f"{path_wallpaper}/{filename}")


def wallpaperflare(url: str) -> None:
    html: list = get_data(url)
    name: str = get_name(html)
    tags: list = get_tags(html)
    link: str = ""

    for i in html:
        if 'show_img' in i:
            link = i[i.find('src="') + 5:len(i) - 2]

    prepare_download(name, tags, url, link)


def wallhaven(url: str) -> None:
    # html: list = get_data(url)
    r = session.get(url)
    html: str = r.text
    start: int = str(html).find("<title>")
    stop: int = str(html).find("</title>")
    print(html)
    stream: str = str(html[start + 7: stop]).split(" |")[0]

    tags: list = stream.split(", ")
    name: str = str(tags[0]).replace(" ", "-")

    start: int = str(html).find('src="https://w.wallhaven.cc/full')
    stop: int = str(html[start:]).find('" alt=')
    link: str = (html[start + 5: start + stop])

    prepare_download(name, tags, url, link)
    # print(tags, link)


# ----------------------------------------------------------
# aniworld
# ----------------------------------------------------------
def read_html_from_requests(url: str):
    html =  requests.get(url)
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


def find_download_url_VOE(html_data: str) -> str:
    """finds the stramurl from VOE"""
    start: int = (html_data.find("let nodeDetails = prompt")) + 34  # to remove class=row
    stop: int = start + html_data[start:].find('");')
    url: str =html_data[start:stop]
    return url


def find_download_url_VOE_url_fetch(html_data: str) -> str:
    """finds the stramurl from Vidoza"""
    start: int = (html_data.find("window.location.href = 'https:")) + 24  # to remove class=row
    stop: int = start + html_data[start:].find("';")
    url: str =html_data[start:stop]
    return url


def find_download_url_Vidoza(html_data: str) -> str:
    """finds the stramurl from Vidoza"""
    start: int = (html_data.find("<source src=")) + 13  # to remove class=row
    stop: int = start + html_data[start:].find('"')
    url: str =html_data[start:stop]
    return url


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
        return find_download_url_Vidoza(html)
    elif stream[2] == "VOE":
        link_id: str = stream[0]
        html = read_html_from_requests(f"https://aniworld.to/redirect/{link_id}")
        url: str = find_download_url_VOE_url_fetch(html)
        html = read_html_from_requests(url)
        return find_download_url_VOE(html)
    else:
        print("No hoster found")
        return ""


def anime_download(url: str, typ: str = "mp4", website: str = "aniworld") -> None:

    start, stop, season, url = get_episoden(url)

    anime_name = get_anime_name(url)

    for start in range(start, stop + 1):
        filename = f"{anime_name}/Season {season:02}/"
        filename += f"{anime_name}_S{season:02}E{start:02}.mp4"
        download_URL = get_url(url, season, start)
        open_dowanload.append([download_URL, typ, filename, website])
        time.sleep(2)


# ----------------------------------------------------------
# event handeler
# ----------------------------------------------------------
def anime_dlp(url: str, file_format="mp4") -> None:
    print(url, file_format)
    anime_download(url, file_format)


def youtube(url: str, file_format="mp4") -> None:
    print(url, file_format)
    open_dowanload.append([url, file_format, None,"youtube"])


def download(index: int, data: list) -> None:
    """start the download in a thread"""

    if len(data) == []:
        data[2] = "%(title)s.%(ext)s"

    threads_output[index] = f"thread {index}: starting"

    if data[3] == "aniworld":
        args = ["yt-dlp", "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b",
                "--fragment-retries", "infinite", "--concurrent-fragments", "4",
                "-o", f"{conf["path_anime"]}/{data[2]}", data[0]]
    elif data[1] == "m4a":
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

    if data[3] == "aniworld":
        name: str = short_name(data[2])
    else:
        name: str = data[0]

    while p.poll() is None:
        s = f"thread {index}: {name} | {p.stdout.readline()}"
        threads_output[index] = s
    p.wait()
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
            wallhaven(i[0])
        elif "wallpaperflare" in i[0]:
            wallpaperflare(i[0])
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
        if i[3] == "aniworld":
            name = i[2]
            name = short_name(name)
        else:
            name = i[0]
        s += f"<li>{name}</li>"
    return s


def background_thread() -> None:
    """works in background and handle events like main_loop"""
    handler: bool = False
    handler_thread = threading.Thread()

    while True:
        # handle download urls
        if len(open_queue) > 0 and not handler:
            handler_thread = threading.Thread(target=download_handler)
            handler_thread.start()

        handler = handler_thread.is_alive()

        # start one download
        if len(open_dowanload) > 0 and len(threads) > 0:
            threading.Thread(target=download,
                             args=(threads.pop(0), open_dowanload.pop(0))
                             ).start()

        # update the web site
        if thread:
            socketio.emit('anime', {
                'open': make_html_list(open_dowanload),
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
    conf = conf_reader(f"{Path.home}/python/anime-dlp-3/anime-dlp.conf")
    # conf = conf_reader("~/python/anime-dlp-3/anime-dlp.conf")
    threading.Thread(target=background_thread, daemon=True).start()
    app.run()
    # app = socketio.WSGIApp(sio, app)
    # serve(app, host="0.0.0.0", port=5000)
