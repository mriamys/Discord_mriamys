import urllib.request
import re

url = "https://www.myinstants.com/ru/search/?name=%D0%BC%D0%B5%D0%BC%D1%8B"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8')
    matches = re.findall(r"/media/sounds/[^\".]+\.mp3", html)
    print("Found MP3s:", len(matches))
    for m in matches[:10]:
        print("https://www.myinstants.com" + m)
except Exception as e:
    print("Error:", e)
