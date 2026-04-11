import urllib.request
import os

os.makedirs('assets/fonts', exist_ok=True)
os.makedirs('assets/img', exist_ok=True)

fonts = {
    'Roboto-Bold.ttf': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf',
    'Roboto-Medium.ttf': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Medium.ttf',
    'Roboto-Regular.ttf': 'https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf'
}

for name, url in fonts.items():
    print(f"Downloading {name}...")
    urllib.request.urlretrieve(url, f"assets/fonts/{name}")

# Dark abstract gamer background
bg_url = "https://images.unsplash.com/photo-1511512578047-dfb367046420?q=80&w=900&h=350&fit=crop"
print("Downloading background...")
urllib.request.urlretrieve(bg_url, "assets/img/default_bg.jpg")

print("Done!")
