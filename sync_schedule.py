import re
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta, date
from caldav import DAVClient
import pytz
import getpass  # secure password input
from urllib.parse import urlparse, parse_qs
from collections import defaultdict


def parse_schedule(url):

    # ISO‑week → Gregorian date (Mon=1…Sun=7)
    def iso_to_gregorian(iy, iw, id):
        fourth = date(iy,1,4)
        return fourth + timedelta(days=id - fourth.isoweekday(), weeks=iw-1)

    # extract week/year from URL
    qs   = parse_qs(urlparse(url).query)
    week = int(qs.get('week', [datetime.now().isocalendar()[1]])[0])
    week = get_adjusted_week(week, url) # we don't want to start from the first week of the year
    year = datetime.now().year

    TYPE_MAP = {'V':'Vorlesung','LU':'Laborübung','SU':'Seminarübung'}
    DAY_MAP  = {
        'Mo':1,'Montag':1,'Di':2,'Dienstag':2,'Mi':3,'Mittwoch':3,
        'Do':4,'Donnerstag':4,'Fr':5,'Freitag':5,'Sa':6,'Samstag':6,
        'So':7,'Sonntag':7
    }

    # fetch the table and pull out the time‑slot headers
    resp    = requests.get(url); resp.raise_for_status()
    soup    = BeautifulSoup(resp.content, 'html.parser')
    table   = soup.find('table', class_='plan')
    headers = table.find_all('th')[1:]                      # skip the day‑col
    slots   = [h.text.strip().split('-') for h in headers]  # [ ['7:30','8:15'], … ]

    tz       = pytz.timezone("Europe/Sofia")
    schedule = []

    for row in table.find_all('tr')[1:]:
        day_name = row.find('th').text.strip()
        wd       = DAY_MAP.get(day_name)
        if not wd:
            print(f"Unknown day '{day_name}', skipping.")
            continue

        row_date = iso_to_gregorian(year, week, wd)
        col      = 0   # ← this tracks actual slot index across colspan

        for cell in row.find_all('td'):
            span = int(cell.get('colspan', 1))

            if 'busy' in cell.get('class', []):
                # compute start/end from header slots[col] … slots[col+span-1]
                start_s = slots[col][0]
                end_s   = slots[col + span - 1][1]
                start_t = datetime.strptime(start_s, '%H:%M').time()
                end_t   = datetime.strptime(end_s,   '%H:%M').time()

                # parse text lines
                lines = [L.strip() for L in cell.get_text('\n').split('\n') if L.strip()]
                if len(lines) < 2:
                    print("Skipping malformed cell:", lines)
                    col += span
                    continue

                course = lines[-1]

                # get lecturer from <a> or fallback to text parse
                a = cell.find('a')
                lecturer = a.text.strip() if a else None

                # stitch split prefix‑room‑lecturer
                first = lines[0]
                if first in TYPE_MAP and len(lines) > 1 and lines[1].startswith('-'):
                    first = f"{first} - {lines[1].lstrip('-').strip()}"

                parts  = first.split()
                prefix = parts[0]
                room   = parts[2]
                if lecturer is None:
                    lecturer = ' '.join(parts[3:]).strip()

                start_dt = tz.localize(datetime.combine(row_date, start_t))
                end_dt   = tz.localize(datetime.combine(row_date, end_t))

                schedule.append({
                    'day':       day_name,
                    'start':     start_dt,
                    'end':       end_dt,
                    'course':    course,
                    'type':      TYPE_MAP[prefix],
                    'location':  room,
                    'lecturer':  lecturer
                })

            # advance the slot pointer by colspan, busy or not
            col += span

    return schedule

def create_events(schedule_data):
    evs = []
    for D in schedule_data:
        ev = Event()
        ev.add('uid', f"{D['day']}-{D['start'].isoformat()}@tusofia")
        ev.add('summary', D['course'])
        ev.add('dtstart', D['start'])
        ev.add('dtend',   D['end'])
        ev.add('location', D['location'])
        ev.add('description', f"Lecturer: {D['lecturer']}")
        evs.append(ev)
    return evs

def save_events_to_ics(events, path):
    cal = Calendar()
    for e in events:
        cal.add_component(e)
    with open(path, 'wb') as f:
        f.write(cal.to_ical())

def sync_events_with_caldav(events, caldav_url, username, password):
    client = DAVClient(url=caldav_url, username=username, password=password)
    principal = client.principal()
    cals = principal.calendars()

    if not cals:
        print("No calendars found → creating one named 'TU Schedule'")
        cal = principal.make_calendar(name="TU Schedule")
        cal.save()
    else:
        cal = cals[0]

    # push each VEVENT separately
    for ev in events:
        single = Calendar()
        single.add_component(ev)
        ical = single.to_ical()
        cal.add_event(ical)   # auto‑handles URL, POST, etc.

def check_semester(url):
    # Send an HTTP request to fetch the HTML content
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find all <h2> headers in the HTML content
    h2_headers = soup.find_all('h2')

    # Initialize a variable to store the result
    semester_type = None

    # Iterate through the <h2> headers and check their content
    for header in h2_headers:
        if "Sommersemester" in header.text:
            semester_type = "Sommersemester"
            break
        elif "Wintersemester" in header.text:
            semester_type = "Wintersemester"
            break

    # Return the result
    return semester_type

def get_adjusted_week(week, url):
    # Check the semester type
    semester = check_semester(url)

    # Adjust the week number based on the semester type
    if semester == "Sommersemester":
        week += 5
    elif semester == "Wintersemester":
        week += 38

    return week

def calendar_to_semester_week(week, semester):
    '''Reversed get_adjusted_week'''
    if semester == "Sommersemester":
        week -=5
    elif semester == "Wintersemester":
        week -= 38

    return week

def url_exists(url):
    """Check if the URL contains a valid weekly schedule."""
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Check if the <p class='info'> element is present
    info_paragraph = soup.find('p', class_='info')

    # If the <p class='info'> element is found, return False (no schedule)
    if info_paragraph:
        return False

    return True


def main():
    base_url = 'https://programm.fdiba.tu-sofia.bg/de/?q=plan_group'
    group = '339'
    caldav_url = 'http://localhost:5232/'

    user = input("CalDAV username: ")
    pwd  = getpass.getpass("CalDAV password: ")

    # Current date and week number
    today = datetime.now()
    current_week = today.isocalendar()[1]

    url = f"{base_url}&week={current_week}&group={group}"

    semester = check_semester(url)
    semester_week = calendar_to_semester_week(current_week, semester)

    for week in range(semester_week, semester_week + 3):
        
        url = f"{base_url}&week={week}&group={group}"

        if url_exists(url):
            print(f"Processing schedule for week {week}...")

            sched = parse_schedule(url)
            evs   = create_events(sched)

            save_events_to_ics(evs, f'schedule_w{semester_week}.ics')
            sync_events_with_caldav(evs, caldav_url, user, pwd)
            print("Done — your TU‑Sofia schedule is now on your CalDAV server.")
        else:
            print(f"Schedule for week {week} does not exist. Skipping...")

if __name__ == '__main__':
    main()
