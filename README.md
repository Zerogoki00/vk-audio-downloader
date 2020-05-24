# VK Audio Downloader
Download music from vk.com

## Requirements
Python 3 is required to run this program and *ffmpeg* binary should be in PATH.
You can install required modules using this command:
`pip install -r requirements.txt`

## Usage
First you need to authenticate on vk.com using your login and password:
`./vkaudio.py auth <login> <password>`
VKaudio will receive token and store it in *token.txt* file.
You can switch to another account by running previous command with another credentials

Now you can use this tool simply by running it with no arguments:
`./vkaudio.py`
Type number of song to download it or type `a` to download everything. (playlists support will be added in future)

You can also save full list of your songs in file using this command:
`./vkaudio.py dump <filename>`
