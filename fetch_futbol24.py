import time
import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0"}
SLEEP = 1.0

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

def safe_text(el):
    return el.get_text(" ", strip=True) if el else ""

def parse_next_matches(team: str, url: str, take: int = 2):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Futbol24 pages often contain a "Next matches" block.
    # We'll find the text and then scan the nearest table rows.
    all_text = soup.get_text("\n", strip=True)
    if "Next matches" not in all_text:
        return []

    # Find the header element containing "Next matches"
    header = None
    for h in soup.find_all(["h2", "h3", "div"]):
        if "Next matches" in safe_text(h):
            header = h
            break

    # Try to locate a table after that header
    rows = []
    table = header.find_next("table") if header else soup.find("table")
    if table:
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 3:
                continue
            line = [safe_text(td) for td in tds]
            row_txt = " | ".join(line)
            # Skip headers / junk rows
            if "Date" in row_txt and "Time" in row_txt:
                continue
            rows.append(line)

    out = []
    # Heuristic extraction from row lines
    for line in rows:
        joined = " ".join(line)
        if "vs" not in joined and "-" not in joined:
            continue

        # Try to guess date/time and match text
        date = ""
        time_ = ""
        comp = ""
        match = ""

        # Pick likely date/time tokens
        for token in line:
            if "." in token and any(ch.isdigit() for ch in token) and len(token) >= 8:
                # often dd.mm.yyyy
                date = token
            if ":" in token and len(token) <= 8:
                time_ = token

        # competition is often near the start
        comp = line[0] if line else ""

        # match is usually the part with vs or -
        for token in line:
            if " vs " in token.lower() or " - " in token:
                match = token
                break
        if not match:
            # fallback: use joined
            match = joined

        if not time_:
            time_ = "TBC"

        if match and date:
            out.append([team, match, comp, date, time_])
        if len(out) == take:
            break

    return out

def main():
    rows = []
    for team, url in TEAM_URLS.items():
        try:
            rows.extend(parse_next_matches(team, url, take=2))
        except Exception as e:
            rows.append([team, "ERROR", "ERROR", "ERROR", str(e)])
        time.sleep(SLEEP)

    df = pd.DataFrame(rows, columns=["Team", "Match", "Competition", "Date", "Time"])
    df.to_csv("output_fixtures.csv", index=False)
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()
