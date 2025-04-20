from diagrams import Diagram, Cluster
from diagrams.onprem.client import User
from diagrams.onprem.network import Internet
from diagrams.programming.language import Python
from diagrams.onprem.compute import Server
from diagrams.generic.storage import Storage
from diagrams.generic.device import Mobile

with Diagram("University Schedule Sync Workflow TB", show=True, direction="TB"):

    user = User("User")
    schedule_url = Internet("University Schedule URL")

    with Cluster("Parse Schedule"):
        parser = Python("parse_schedule(url)")
        html_page = Server("HTML Page")
        parsed_data = Storage("Parsed Schedule Data")

        schedule_url >> html_page >> parser >> parsed_data

    with Cluster("Create Calendar Events"):
        event_creator = Python("create_events(data)")
        events = Storage("Calendar Events")

        parsed_data >> event_creator >> events

    with Cluster("Save to .ics File"):
        ics_saver = Python("save_events_to_ics(events, path)")
        ics_file = Storage(".ics File")

        events >> ics_saver >> ics_file

    with Cluster("Sync with CalDAV Server"):
        caldav_sync = Python("sync_events_with_caldav(...)")
        caldav_server = Internet("CalDAV Server")

        ics_file >> caldav_sync >> caldav_server

    with Cluster("Sync with Mobile App"):
        mobile_app = Mobile("CalDAV Mobile App")

        caldav_server >> mobile_app

    mobile_app >> user
