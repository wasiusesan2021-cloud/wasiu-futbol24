import re
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}
SLEEP = 1.2

TEAM_URLS = {
  "Bayern Munich": "https://www.futbol24.com/team/Germany/Bayern-Munchen/",
  "Stuttgart": "https://www.futbol24.com/team/Germany/VfB-Stuttgart/",
  "Manchester City": "https://www.futbol24.com/team/England/Manchester-City/",
  "Barcelona": "https://www.futbol24.com/team/Spain/Barcelona/",
  "PSV": "https://www.futbol24.com/team/Holland/PSV-Eindhoven/",
  "PSG": "https://www.futbol24.com/team/France/Paris-Saint-Germain/",
  "Ajax": "https://www.futbol24.com/team/Holland/Ajax/",
  "Club Brugge": "https://www.futbol24.com/team/Belgium/Club-Brugge/",
  "Brighton": "https://www.futbol24.com/team/England/Brighton/",
  "Bournemouth": "https://www.futbol24.com/team/England/AFC-Bournemouth/",
  "Leverkusen": "https://www.futbol24.com/team/Germany/Bayer-Leverkusen/",
  "Hoffenheim": "https://www.futbol24.com/team/Germany/Hoffenheim/",
  "Werder Bremen": "https://www.futbol24.com/team/Germany/Werder-Bremen/",
  "Real Madrid": "https://www.futbol24.com/team/Spain/Real-Madrid/",
  "Liverpool": "https://www.futbol24.com/team/England/Liverpool/",
  "Midtjylland": "https://www.futbol24.com/team/Denmark/Midtjylland/",
  "Crvena Zvezda": "https://www.futbol24.com/team/Serbia/Crvena-Zvezda/",
  "Lincoln Red Imps": "https://www.futbol24.com/team/Gibraltar/Lincoln-Red-Imps/",
}

def get_next_two(team, url):
    html = requests.get(url, headers=HEADERS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    if "Next matches" not in text:
        return []

    after = text.split("Next matches", 1)[1]
    lines = [ln.strip() for ln in after.splitlines() if ln.strip()][:100]

    pat = re.compile(r"(\d{2}\.\d{2}\.\d{4}).*?\s+(.+?)\s+(.+?)\s+-\s+(.+)$")

    out = []
    for ln in lines:
        m = pat.search(
