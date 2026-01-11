import re
import time
import random
import pandas as pd
import requests
from bs4 import BeautifulSoup

# -------------------------
# SETTINGS
# -------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
}

# Slow down to reduce 429 blocks
BASE_SLEEP = 2.5
JITTER = 1.5

# Score pattern to exclude past results
SCORE_RE = re.compile(r"\b\d{1,2}\s*-\s*\d{1,2}\b")

# Futbol24 team URLs (MEN + WOMEN)
TEAM_URLS = {
    # MEN
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

    # WOMEN  (If any of these pages 404, open Futbol24 search and adjust the URL slug)
    "Bayern Munich (W)": "https://www.futbol24.com/team/Germany/Bayern-Munchen-W/",
    "Barcelona (W)": "https://www.futbol24.com/team/Spain/FC-Barcelona-W/",
    "Lyon (W)": "https://www.futbol24.com/team/France/Lyon-W/",
}

# -------------------------
# HTTP
# -------------------------
def fetch(url: str, retries: int = 6) -> str:
    """
    Fetch with retry/backoff to survive Futbol24 429 blocks.
    """
    for i in range(retries):
        r = requests.get(url, headers=HEADERS, timeout=30)

        if r.status_code == 429:
            # exponential-ish backoff + jitter
            wait = (BASE_SLEEP * (i + 2)) + random.random() * JITTER
            time.sleep(wait)
            continue

        r.raise_for_status()
        return r.text

    raise RuntimeError(f"Blocked (429) too many times: {url}")

# -------------------------
# PARSING
# -------------------------
def extract_next_matches_table(soup: BeautifulSoup):
    """
    Find the table that belongs to the 'Next matches' section.
    Strategy:
    - Locate element containing exact text 'Next matches'
    - From there, find the next <table>
    """
    # Find a tag whose text contains 'Next matches'
    header_tag = None
    for tag in soup.find_all(["h1", "h2", "h3", "div", "span"]):
        txt = tag.get_text(" ", strip=True)
        if txt == "Next matches" or "Next matches" in txt:
            header_tag = tag
            break

    if not header_tag:
        return None

    table = header_tag.find_next("table")
    return table

def clean_cell_text(td) -> str:
    return td.get_text(" ", strip=True) if td else ""

def parse_fixture_row_text(row_text: str):
    """
    Parse a row text into (date, time, competition, match).
    Futbol24 rows vary. We do robust parsing using tokens.

    We reject anything that looks like a played match (scoreline).
    """
    if SCORE_RE.search(row_text):
        return None

    # Common: "11.01.2026 17:30 GER D1 Bayern München - Wolfsburg"
    # But sometimes time/competition order changes.
    date = ""
    time_ = "TBC"
    comp = ""
    match = ""

    # Date
    m_date = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", row_text)
    if m_date:
        date = m_date.group(1)

    # Time
    m_time = re.search(r"\b(\d{2}:\d{2})\b", row_text)
    if m_time:
        time_ = m_time.group(1)

    # Match teams: detect " - " or " vs "
    if " - " in row_text:
        # take rightmost teams segment
        parts = row_text.split(" - ")
        if len(parts) >= 2:
            away = parts[-1].strip()
            left = " - ".join(parts[:-1]).strip()
            # home is last chunk of left after removing date/time/comp
            # crude but works: take last 4-7 words as home if needed
            home_guess = left.split()[-6:]
            home = " ".join(home_guess).strip()
            match = f"{home} vs {away}"
    elif " vs " in row_text.lower():
        # already contains vs
        match = row_text

    # Competition (best effort): remove date/time and match, keep remaining short tokens
    tmp = row_text
    if date:
        tmp = tmp.replace(date, "")
    if time_ != "TBC":
        tmp = tmp.replace(time_, "")

    # If match contains away team, remove after that
    if match:
        # remove both team names if possible
        tmp = tmp.replace(match, "")

    tmp = re.sub(r"\s+", " ", tmp).strip()

    # competition usually short (<= 25 chars) or first 2-4 tokens
    if tmp:
        tokens = tmp.split()
        comp = " ".join(tokens[:4])[:35].strip()

    if not date or not match:
        return None

    return date, time_, comp, match

def get_next_two_fixtures(team_name: str, team_url: str, take: int = 2):
    html = fetch(team_url)
    soup = BeautifulSoup(html, "html.parser")

    table = extract_next_matches_table(soup)
    if table is None:
        return [[team_name, "ERROR", "Next matches not found", "", ""]]

    out = []
    for tr in table.find_all("tr"):
        # Combine the row into text
        row_text = tr.get_text(" ", strip=True)
        if not row_text:
            continue

        parsed = parse_fixture_row_text(row_text)
        if not parsed:
            continue

        date, time_, comp, match = parsed
        out.append([team_name, match, comp, date, time_])

        if len(out) >= take:
            break

    if not out:
        out.append([team_name, "ERROR", "No fixtures parsed", "", ""])

    return out

# -------------------------
# MAIN
# -------------------------
def main():
    rows = []
    for team, url in TEAM_URLS.items():
        try:
            rows.extend(get_next_two_fixtures(team, url, take=2))
        except Exception as e:
            rows.append([team, "ERROR", f"{type(e).__name__}: {e}", "", ""])

        time.sleep(BASE_SLEEP + random.random() * JITTER)

    df = pd.DataFrame(rows, columns=["Team", "Match", "Competition", "Date", "Time"])
    df.to_csv("output_fixtures.csv", index=False)
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()
