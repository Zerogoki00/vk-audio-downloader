#!/usr/bin/env python3
from utils.vkapi import *
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import requests
import re
import sys
import os

HEADERS = {"Accept-Encoding": "identity"}


def get_decryptor(k_url):
    k = requests.get(k_url, headers=headers).content
    c = Cipher(algorithms.AES(k), modes.CBC(b'\x00' * 16), backend=default_backend())
    return c.decryptor()


output_dir = os.path.join(os.getcwd(), "output")
if not os.path.exists(output_dir):
    os.mkdir(output_dir)

if len(sys.argv) == 4:
    _, command, username, password = sys.argv
    vk = VkAPI(login=username, password=password)
    if command == "auth":
        with open("token.txt", "w") as f:
            f.write(vk.token)
else:
    if os.path.exists("token.txt"):
        token = open("token.txt", "r").read().splitlines()[0]
    else:
        print("token.txt not found. Please authorize: ./vkaudio.py auth <login> <password>")
        sys.exit(1)
    vk = VkAPI(token=token)

dump = False
dump_filename = ""
if len(sys.argv) == 3:
    dump = sys.argv[1] == "dump"
    dump_filename = sys.argv[2]

print("Logged as", vk.user_id)
headers = HEADERS
headers["User-Agent"] = vk.user_agent
resp = vk.request("catalog.getAudio", {"need_blocks": 1})
sections = resp["catalog"]["sections"]
default_section_id = resp["catalog"]["default_section"]
audios = resp["audios"]
print("Received %d audios" % len(audios))
music_section = sections[0]
for s in sections:
    if s["id"] == default_section_id:
        music_section = s
        break
print('Default section: "%s": %s: %s' % (music_section["title"], music_section["id"], music_section["url"]))
next_start = music_section.get("next_from")
while next_start:
    # print("Next from:", next_start)
    resp = vk.request("catalog.getSection", {"start_from": next_start, "section_id": music_section["id"]})
    next_start = resp["section"].get("next_from")
    received_audios = resp["audios"]
    audios += received_audios
    print("Received %d audios" % len(received_audios))

if dump:
    dump_file = open(dump_filename, "w")
else:
    dump_file = None
for i, track in enumerate(audios):
    print("%d. %s — %s" % (i + 1, track["artist"], track["title"]), file=dump_file)
    # if not dump:
    #    print(track.get("url"))
if dump:
    print("Dumped %d tracks" % len(audios))
    dump_file.close()
    sys.exit()
while True:
    download_all = False
    download_range = False
    task = []
    user_input = input("Select track (e.g. 1 or 1,2,3 or 1-5,7,9 / a = all / q to exit): ")
    if user_input == "q":
        break
    if user_input == "a":
        task = audios
        download_all = True
    elif not user_input.isnumeric():
        parse_in = user_input.split(",")
        parse_good = True
        for el in parse_in:
            if "-" in el:
                rng = el.split("-")
                if len(rng) != 2 or not (rng[0].isnumeric() and rng[1].isnumeric()):
                    print("Incorrect range input format")
                    parse_good = False
                    break
                for i in range(int(rng[0]), int(rng[1])+1):
                    task.append(audios[i])
            elif el.isnumeric():
                task.append(audios[int(el)])
            else:
                parse_good = False
        if not parse_good:
            print("Enter number, list of numbers or ranges")
            continue
        else:
            download_range = True
    else:
        selected_id = int(user_input) - 1
        if selected_id + 1 > len(audios):
            print("No such track")
        task.append(audios[selected_id])
    for n, audio in enumerate(task):
        url = audio.get("url")
        artist = audio["artist"]
        title = audio["title"]
        track_name = "%s — %s" % (artist, title)
        if download_all or download_range:
            result_number = n + 1
        else:
            result_number = int(user_input)
        print("Processing track %d/%d: %s" % (n + 1, len(task), track_name))
        out_file_base = re.sub(r'[/\\?%*:|"<>]', "-", "%d. %s" % (result_number, track_name))
        out_file_path = os.path.join(output_dir, out_file_base)
        out_file_ts = out_file_path + ".ts"
        out_file_mp3 = out_file_path + ".mp3"
        if url:
            if re.findall(r'/\w*\.mp3', url):
                print("Downloading mp3")
                with open(out_file_mp3, "wb") as f:
                    f.write(requests.get(url, headers=headers).content)
            elif re.findall(r'/\w*\.m3u8', url):
                base_url = url[:url.rfind("/")]
                # print("Base url:", base_url)
                playlist = requests.get(url, headers=headers).content.decode("utf-8")
                blocks = [b for b in playlist.split("#EXT-X-KEY") if "#EXTINF" in b]
                # print("Track contains %d blocks" % len(blocks))
                key_url = re.findall(r':METHOD=AES-128,URI="(\S*)"', blocks[0])[0]
                decryptor = get_decryptor(key_url)
                for i, block in enumerate(blocks):
                    segment_urls = re.findall(r'#EXTINF:\d+\.\d{3},\s(\S*)', block)
                    # print("Block %d: %d segments" % (i + 1, len(segment_urls)))
                    segments = []
                    for s_url in segment_urls:
                        segments.append(requests.get(base_url + "/" + s_url, headers=headers).content)
                        # print("Downloaded segment %d/%d" % (n + 1, len(segment_urls)))
                    if "METHOD=AES-128" in block:
                        segment_key_url = re.findall(r':METHOD=AES-128,URI="(\S*)"', block)[0]
                        if segment_key_url != key_url:
                            key_url = segment_key_url
                            decryptor.finalize()
                            decryptor = get_decryptor(key_url)
                            # print("Found new key:", key)
                        for j, seg in enumerate(segments):
                            segments[j] = decryptor.update(seg)
                            # print("Decrypted segment %d/%d" % (j + 1, len(segment_urls)))
                    downloaded_block = b''.join(segments)
                    print("Processed block %d/%d" % (i + 1, len(blocks)), end="\r")
                    with open(out_file_ts, "ab") as f:
                        f.write(downloaded_block)
                os.system('ffmpeg -y -hide_banner -loglevel panic -i "%s" -c copy "%s"' % (out_file_ts, out_file_mp3))
                print("\nConverted to mp3")
                os.remove(out_file_ts)
        else:
            print("Track unavailable")
