import os
import re
import requests
from datetime import date, timedelta
from bs4 import BeautifulSoup

URL = "https://www.nyurban.com/?page_id=400&filter_id=1&gametypeid=1"

# Required for Discord notification
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# Optional: narrow to a specific gym substring (leave blank for any gym)
TARGET_GYM = os.getenv("TARGET_GYM", "").strip()

# Allowed skill levels (case-insensitive contains checks)
ALLOWED_LEVELS = ["beginner", "advanced beginner", "intermediate"]

# Exclude "advanced" unless it is exactly part of "advanced beginner"
def level_allowed(level_text: str) -> bool:
    lt = level_text.lower().strip()
    if "advanced beginner" in lt:
        return True
    # Exclude advanced (e.g., "Advanced", "Advanced - Court 1", etc.)
    if "advanced" in lt:
        return False
    return any(x in lt for x in ["beginner", "intermediate"])

def fetch_html() -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (NYUrban availability checker)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(URL, headers=headers, timeout=25)
    r.raise_for_status()
    return r.text

def find_openplay_table(soup: BeautifulSoup):
    # Find a table that contains the schedule headers
    for t in soup.find_all("table"):
        header_text = " ".join(t.get_text(" ", strip=True).split())
        if ("Select Date" in header_text
            and "Gym" in header_text
            and "Level" in header_text
            and "Available" in header_text):
            return t
    return None

def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def parse_mmdd(raw_date_cell: str) -> str:
    # Extract MM/DD from things like "Fri 02/13"
    raw = normalize_spaces(raw_date_cell)
    m = re.search(r"\b(\d{2}/\d{2})\b", raw)
    return m.group(1) if m else ""

def mmdd_to_next_occurrence(mmdd: str, today: date) -> date | None:
    """
    Interpret MM/DD as the next occurrence relative to 'today'.
    If MM/DD already happened this year, assume next year.
    """
    try:
        month, day = map(int, mmdd.split("/"))
        candidate = date(today.year, month, day)
        if candidate < today:
            candidate = date(today.year + 1, month, day)
        return candidate
    except Exception:
        return None

def status_is_sold_out(status_text: str) -> bool:
    return "sold out" in status_text.lower()

def status_looks_purchasable(status_text: str) -> bool:
    """
    Conservative: treat anything NOT sold out as potentially purchasable,
    but exclude empty/unknown states if you want.
    """
    st = status_text.strip().lower()
    if not st:
        return False
    if "sold out" in st:
        return False
    # Often sites use words like available/open/register/spots left/etc.
    # We'll accept any non-sold-out non-empty status.
    return True

def send_discord(webhook_url: str, message: str):
    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not set.")
    resp = requests.post(webhook_url, json={"content": message}, timeout=20)
    resp.raise_for_status()

def main():
    today = date.today()
    end = today + timedelta(days=7)

    html = fetch_html()
    soup = BeautifulSoup(html, "html.parser")
    table = find_openplay_table(soup)
    if table is None:
        raise RuntimeError("Could not find the Open Play table. Page layout may have changed.")

    matches = []
    for tr in table.find_all("tr"):
        cells = [normalize_spaces(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        # Expect columns: Select Date | Gym | Level | Time | Fee | Available
        if len(cells) < 6 or cells[0] == "Select Date":
            continue

        raw_date, gym, level, time_str, fee, status = cells[:6]

        if TARGET_GYM and TARGET_GYM.lower() not in gym.lower():
            continue
        if not level_allowed(level):
            continue

        mmdd = parse_mmdd(raw_date)
        d = mmdd_to_next_occurrence(mmdd, today)
        if d is None:
            continue
        if not (today <= d <= end):
            continue

        if status_looks_purchasable(status):
            matches.append({
                "date": d.isoformat(),
                "raw_date": raw_date,
                "gym": gym,
                "level": level,
                "time": time_str,
                "fee": fee,
                "status": status
            })

    if matches:
        # Build a single concise message
        lines = ["🏐 **NY Urban Open Gym available in the next 7 days:**"]
        for m in matches[:10]:  # avoid spam if tons are open
            lines.append(f"- **{m['raw_date']}** | {m['gym']} | {m['level']} | {m['time']} | {m['fee']} | {m['status']}")
        lines.append(f"\nLink: {URL}")

        msg = "\n".join(lines)
        send_discord(DISCORD_WEBHOOK_URL, msg)
        print("Sent Discord notification.")
    else:
        print("No purchasable spots found in the next 7 days (within allowed levels).")

if __name__ == "__main__":
    main()
