#!/usr/bin/env python3
"""
only_exams.py

Scrape the summer exam schedule for a given group from the TU‑Sofia page
and export all exams into a single .ics file. No CalDAV is needed.

Usage:
    python3 only_exams.py 87
    python3 only_exams.py        # will prompt you
"""

import sys
from datetime import datetime, timedelta

import pytz
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from requests.utils import requote_uri

EXAMS_URL = (
    "https://tu-sofia.bg/examsfiles/"
    "%D0%A4%D0%B0%D0%93%D0%98%D0%9E%D0%9F%D0%9C-"
    "%D0%9A%D0%A1%D0%A2%D0%9D%D0%95--potok-17-kurs-2_1.html"
)

#— FIXED: use plain ASCII hyphens so header is Latin-1 safe —#
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TU-Sofia-Scraper/1.0)"
}

def get_group_number(raw):
    """Validate that raw is a non-negative integer string."""
    if raw.isdigit():
        return raw
    print("Error: group must be a non-negative integer.")
    sys.exit(1)

def fetch_page(url):
    """Fetch the URL with proper encoding and headers, returns BeautifulSoup."""
    safe = requote_uri(url)
    try:
        resp = requests.get(safe, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"Failed to fetch schedule (HTTP {resp.status_code}).")
        print("→ Check the URL or try again later.")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print("Network error:", e)
        sys.exit(1)

    return BeautifulSoup(resp.content, "html.parser")

def parse_exams(soup, group):
    """Return a list of dicts with exam info for the given group."""
    tz = pytz.timezone("Europe/Sofia")
    exams = []

    target = f"Група : {group}"
    for header in soup.find_all("h4"):
        if target in header.get_text():
            table = header.find_next("table")
            for row in table.find_all("tr")[1:]:
                cols       = row.find_all("td")
                subject    = cols[0].get_text(strip=True)
                instructor = cols[2].get_text(strip=True)
                room       = cols[3].get_text(strip=True)
                dt_text    = cols[4].get_text(strip=True)  # "06.06.2025 11:30"

                dt = datetime.strptime(dt_text, "%d.%m.%Y %H:%M")
                dt = tz.localize(dt)

                exams.append({
                    "summary":     subject,
                    "description": f"Instructor: {instructor}",
                    "location":    room,
                    "dtstart":     dt,
                    "dtend":       dt + timedelta(hours=2),
                })
            break

    if not exams:
        print(f"No exams found for group {group}.")
        sys.exit(1)

    return exams

def save_exams_to_ics(exams, group):
    """Write all exam events into merged_exams_<group>.ics."""
    cal = Calendar()
    for idx, ex in enumerate(exams, start=1):
        ev = Event()
        ev.add("uid",        f"exam-{group}-{idx}@tusofia")
        ev.add("summary",    ex["summary"])
        ev.add("description",ex["description"])
        ev.add("location",   ex["location"])
        ev.add("dtstart",    ex["dtstart"])
        ev.add("dtend",      ex["dtend"])
        cal.add_component(ev)

    path = f"merged_exams_{group}.ics"
    with open(path, "wb") as f:
        f.write(cal.to_ical())

    print(f"✔ Saved {len(exams)} exams to {path}")

def main():
    if len(sys.argv) > 1:
        group = get_group_number(sys.argv[1])
    else:
        print("""\
Tip:
You can also run this directly with your group number, e.g.:
    python3 only_exams.py 87
""")
        user_in = input("Enter your group number: ").strip()
        group = get_group_number(user_in)

    url   = sys.argv[2] if len(sys.argv) > 2 else EXAMS_URL
    soup  = fetch_page(url)
    exams = parse_exams(soup, group)
    save_exams_to_ics(exams, group)

if __name__ == "__main__":
    main()

