"""Download mascot logos for every school on the scores sheet.

Reads the same Google Sheet the overlay uses, looks each school up on MaxPreps
(Michigan only), saves its mascot image to Graphics/maxpreps/ and records the
mapping in Graphics/logos.json. Schools already in MANUAL (or already
downloaded) are skipped, so it is safe to re-run whenever new schools appear.

    python fetch_logos.py            # fetch only schools that have no logo yet
    python fetch_logos.py --refresh  # re-download everything
"""
import csv, io, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
GRAPHICS = ROOT / "Graphics"
OUT_DIR = GRAPHICS / "maxpreps"
MAP_FILE = GRAPHICS / "logos.json"
SHEET_ID = "1o4IOGoVeV1ljEpoNxnMS56SN_hezE266Gvr7_GhYB9k"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
UA = {"User-Agent": "Mozilla/5.0"}

# Hand-picked logos from the Graphics folder; never overwritten.
MANUAL = {
    "colon": "Graphics/Colon_Community_Schools_Logo.png",
    "constantine": "Graphics/ConstantineHighSchoolPrimaryLogoImage.png",
    "decatur": "Graphics/Decatur_Public_Schools_Logo.png",
    "mendon": "Graphics/logo-mendon-hornets-125.png",
    "three rivers": "Graphics/TRHS.jpg",
    "burr oak": "Graphics/burroak.jpg",
    "centreville": "Graphics/bulldogs.jpg",
}

# Sheet name -> search text, for names that don't match MaxPreps' wording.
ALIASES = {
    "north adams": "North Adams-Jerome",
    "vermontville maple valley": "Maple Valley",
    "adrian lenawee": "Lenawee Christian",
    "battle creek pennfield": "Pennfield",
    "climax scotts": "Climax-Scotts",
    "parma western": "Western",
    "bronson": "Bronson Vikings",
    "portland st. patrick": "St. Patrick",
}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()


def sheet_teams():
    rows = list(csv.reader(io.StringIO(get(CSV_URL).decode("utf-8"))))[1:]
    teams = []
    for row in rows:
        text = (row[0] if row else "").strip()
        text = re.sub(r"\s+\(.*?\)\s*$", "", text)
        text = re.sub(r"\s+play\s+\w+.*$", "", text, flags=re.I)
        for side in re.split(r"\s+vs\.?\s+", text, flags=re.I):
            name = re.sub(r"[\s-]+\d+\s*$", "", side).strip()
            name = re.sub(r"^vs\.?\s+", "", name, flags=re.I)  # sheet typo: "56 vs  vs Coloma"
            if name and name.lower() not in [t.lower() for t in teams]:
                teams.append(name)
    return teams


def tokens(s):
    s = s.lower().replace("st.", "st").replace("saint", "st")
    return [t for t in re.split(r"[^a-z0-9]+", s) if t]


def find_team_page(team):
    query = ALIASES.get(team.lower(), team)
    html = get("https://www.maxpreps.com/search/?q=" + urllib.parse.quote(query)).decode("utf-8", "ignore")
    links = sorted(set(re.findall(r"/mi/[a-z0-9-]+/[a-z0-9-]+/", html)))
    want = tokens(query)
    best, best_score = None, 0
    for link in links:
        have = tokens(link)
        score = sum(1 for t in want if t in have)
        # prefer links where every wanted word is present, then fewer extra words
        if score == len(want) and (score * 10 - len(have)) > best_score:
            best, best_score = link, score * 10 - len(have)
    return best


def mascot_url(page, team):
    html = get("https://www.maxpreps.com" + page).decode("utf-8", "ignore")
    m = re.search(r'"schoolName":"([^"]+)"[^{}]*?"mascotUrl":"([^"]+)"', html)
    pairs = re.findall(r'"schoolName":"([^"]+)"[^{}]*?"mascotUrl":"([^"]+)"', html)
    slug_words = tokens(page)
    for name, url in pairs:
        if all(t in slug_words for t in tokens(name)[:1]):
            return json.loads('"' + url + '"')
    return json.loads('"' + m.group(2) + '"') if m else None


def load_map():
    mapping = json.loads(MAP_FILE.read_text()) if MAP_FILE.exists() else {}
    for k, v in MANUAL.items():
        mapping.setdefault(k, v)
    return mapping


def save_map(mapping):
    MAP_FILE.write_text(json.dumps(mapping, indent=2, sort_keys=True))


def download_logo(team, page=None):
    """Save the MaxPreps mascot for `team` and return its path relative to ROOT.

    `page` is a MaxPreps team path such as /mi/sturgis/sturgis-trojans/; when
    omitted the school is searched for by name.
    """
    page = page or find_team_page(team)
    url = page and mascot_url(page, team)
    if not url:
        raise RuntimeError("no MaxPreps match")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ext = re.search(r"\.(gif|png|jpg|jpeg|svg)", url).group(1)
    dest = OUT_DIR / (re.sub(r"[^a-z0-9]+", "-", team.lower()).strip("-") + "." + ext)
    dest.write_bytes(get(url))
    return dest.relative_to(ROOT).as_posix(), page


def main():
    refresh = "--refresh" in sys.argv
    mapping = {} if refresh else load_map()
    mapping.update(MANUAL)
    missing = []
    for team in sheet_teams():
        key = team.lower()
        if key in MANUAL or (key in mapping and (ROOT / mapping[key]).exists()):
            continue
        try:
            mapping[key], page = download_logo(team)
            print(f"OK   {team:28} {page}")
        except Exception as e:
            missing.append(team)
            print(f"MISS {team:28} {e}")
        time.sleep(0.5)
    save_map(mapping)
    print(f"\nSaved {len(mapping)} logos to {MAP_FILE.relative_to(ROOT)}")
    if missing:
        print("No logo found for:", ", ".join(missing))


if __name__ == "__main__":
    main()
