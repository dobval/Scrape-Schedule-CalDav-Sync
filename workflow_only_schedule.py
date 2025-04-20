from diagrams import Diagram, Cluster
from diagrams.onprem.client import User
from diagrams.onprem.network import Internet
from diagrams.programming.language import Python
from diagrams.generic.storage import Storage

with Diagram("only_schedule.py", show=True, direction="TB"):
    # Actor and data source
    user = User("User")
    schedule_url = Internet("University Schedule URL")

    # Parse Schedule Cluster
    with Cluster("Parse Schedule"):
        html_page = Storage("HTML Page")
        parser = Python("parse_schedule(url)")
        parsed_data = Storage("Parsed Schedule Data")

        schedule_url >> html_page >> parser >> parsed_data

    # Create Calendar Events Cluster
    with Cluster("Create Calendar Events"):
        event_creator = Python("create_events(parsed_data)")
        events = Storage("Calendar Events")

        parsed_data >> event_creator >> events

    # Save to .ics File Cluster
    with Cluster("Save to .ics File"):
        ics_saver = Python("save_events_to_ics(events, 'merged_schedule.ics')")
        ics_file = Storage("Merged .ics File")

        events >> ics_saver >> ics_file

    # Deliver .ics to user
    ics_file >> user
