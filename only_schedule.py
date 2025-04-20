import re
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from datetime import datetime, timedelta, date
import pytz
from urllib.parse import urlparse, parse_qs

def parse_schedule(url):
    def iso_to_gregorian(iy, iw, id):
        fourth = date(iy,1,4)
        return fourth + timedelta(days=id - fourth.isoweekday(), weeks=iw-1)

    qs   = parse_qs(urlparse(url).query)
    week = int(qs.get('week', [datetime.now().isocalendar()[1]])[0])
    week = get_adjusted_week(week, url)
    year = datetime.now().year

    TYPE_MAP = {'V':'Vorlesung','LU':'Laborübung','SU':'Seminarübung'}
    DAY_MAP  = {
        'Mo':1,'Montag':1,'Di':2,'Dienstag':2,'Mi':3,'Mittwoch':3,
        'Do':4,'Donnerstag':4,'Fr':5,'Freitag':5,'Sa':6,'Samstag':6,
        'So':7,'Sonntag':7
    }

    resp    = requests.get(url); resp.raise_for_status()
    soup    = BeautifulSoup(resp.content, 'html.parser')
    table   = soup.find('table', class_='plan')
    headers = table.find_all('th')[1:]
    slots   = [h.text.strip().split('-') for h in headers]

    tz       = pytz.timezone("Europe/Sofia")
    schedule = []

    for row in table.find_all('tr')[1:]:
        day_name = row.find('th').text.strip()
        wd       = DAY_MAP.get(day_name)
        if not wd:
            print(f"Unknown day '{day_name}', skipping.")
            continue

        row_date = iso_to_gregorian(year, week, wd)
        col = 0

        for cell in row.find_all('td'):
            span = int(cell.get('colspan', 1))

            if 'busy' in cell.get('class', []):
                start_s = slots[col][0]
                end_s   = slots[col + span - 1][1]
                start_t = datetime.strptime(start_s, '%H:%M').time()
                end_t   = datetime.strptime(end_s,   '%H:%M').time()

                lines = [L.strip() for L in cell.get_text('\n').split('\n') if L.strip()]
                if len(lines) < 2:
                    print("Skipping malformed cell:", lines)
                    col += span
                    continue

                course = lines[-1]
                a = cell.find('a')
                lecturer = a.text.strip() if a else None

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

def check_semester(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    h2_headers = soup.find_all('h2')
    for header in h2_headers:
        if "Sommersemester" in header.text:
            return "Sommersemester"
        elif "Wintersemester" in header.text:
            return "Wintersemester"
    return None

def get_adjusted_week(week, url):
    semester = check_semester(url)
    if semester == "Sommersemester":
        week += 5
    elif semester == "Wintersemester":
        week += 38
    return week

def calendar_to_semester_week(week, semester):
    if semester == "Sommersemester":
        week -= 5
    elif semester == "Wintersemester":
        week -= 38
    return week

def url_exists(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    info_paragraph = soup.find('p', class_='info')
    return info_paragraph is None

def main():
    base_url = 'https://programm.fdiba.tu-sofia.bg/de/?q=plan_group'
    group = '339'
    today = datetime.now()
    current_week = today.isocalendar()[1]
    url = f"{base_url}&week={current_week}&group={group}"
    semester = check_semester(url)
    semester_week = calendar_to_semester_week(current_week, semester)

    all_events = []
    for week in range(semester_week, semester_week + 3):
        url = f"{base_url}&week={week}&group={group}"
        if url_exists(url):
            print(f"Processing schedule for week {week}...")
            sched = parse_schedule(url)
            evs = create_events(sched)
            all_events.extend(evs)
        else:
            print(f"Schedule for week {week} does not exist. Skipping...")

    print(f"Saving {len(all_events)} events to merged_schedule.ics")
    save_events_to_ics(all_events, 'merged_schedule.ics')

if __name__ == '__main__':
    main()
