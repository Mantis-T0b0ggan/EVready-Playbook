"""
UI components for the Schedules page of the Rate Importer application.
Handles the display and interaction for importing schedules and their details.
"""

import streamlit as st
import sys
import os
import pandas as pd
import time

# Add rate_importer to path to enable imports
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(current_dir)

# Direct imports instead of relative
from utils.state_utils import get_us_states
from utils.api_client import get_schedules_by_utility, get_schedule_detail
from utils.db_operations import (
    insert_schedules, 
    insert_schedule_details,
    get_utilities_from_database,
    get_schedules_from_database,
    check_schedule_status  # New import
)
from ui.components import show_result_message

def render_schedules_section(supabase):
    """
    Render the schedules management section of the application.
    
    Args:
        supabase: Supabase client instance
    
    Returns:
        None
    """
    st.header("Load Rate Schedules")
    st.markdown("Import rate schedules from RateAcuity into your database")
    
    # Get the list of US states
    states = get_us_states()
    state_options = list(states.items())
    
    # Create a selectbox for state selection
    col1, col2 = st.columns([1, 1])
    
    with col1:
        selected_state = st.selectbox(
            "Select a State",
            options=[code for code, name in state_options],
            format_func=lambda x: f"{x} - {states.get(x, '')}",
            key="schedule_state_select"
        )
    
    # Get utilities for the selected state
    if selected_state:
        utilities = get_utilities_from_database(supabase, selected_state)
        
        with col2:
            # If utilities exist, show a selectbox
            if utilities:
                utility_options = [(str(u["UtilityID"]), u["UtilityName"]) for u in utilities]
                selected_utility_id = st.selectbox(
                    "Select a Utility",
                    options=[id for id, name in utility_options],
                    format_func=lambda x: next((name for id, name in utility_options if id == x), x),
                    key="schedule_utility_select"
                )
            else:
                st.warning(f"No utilities found for {states.get(selected_state, '')}. Please load utilities first.")
                selected_utility_id = None
    else:
        selected_utility_id = None
    
    # Load schedules button
    if selected_utility_id:
        load_schedules_clicked = st.button(
            "Load Schedules",
            key="load_schedules_button",
            help="Fetch schedules from RateAcuity and save to database"
        )
    
    # Display existing schedules
    st.subheader("Existing Schedules")
    existing_schedules = get_schedules_from_database(supabase, selected_utility_id)
    
    if existing_schedules:
        # Create a dataframe for display
        schedule_data = []
        for schedule in existing_schedules:
            schedule_data.append({
                "Schedule ID": schedule.get("ScheduleID"),
                "Schedule Name": schedule.get("ScheduleName"),
                "Description": schedule.get("ScheduleDescription") or "-"  # Display "-" if no description
            })
        
        # Create DataFrame and display with custom column widths
        df = pd.DataFrame(schedule_data)
        
        # Define custom column widths
        column_config = {
            "Schedule ID": st.column_config.NumberColumn(
                "Schedule ID",
                width="small",  # This makes the column narrow
            ),
            "Schedule Name": st.column_config.TextColumn(
                "Schedule Name",
                width="small",  # Medium width for the name
            ),
            "Description": st.column_config.TextColumn(
                "Description",
                width=650,  # Allow description to use more space
            ),
        }
        
        # Display with custom column widths
        st.dataframe(
            df,
            use_container_width=True,
            column_config=column_config,
            hide_index=True
        )
    else:
        st.info("No schedules found in the database for this utility.")
    
    # Process the load schedules request if button was clicked
    if load_schedules_clicked and selected_utility_id:
        handle_load_schedules(supabase, selected_utility_id)
    
    # Add a separator
    st.markdown("---")
    
    # Render the schedule details section
    render_schedule_details_section(supabase)

def render_schedule_details_section(supabase):
    """
    Render the schedule details management section of the application.
    
    Args:
        supabase: Supabase client instance
    
    Returns:
        None
    """
    st.header("Manage Schedule Details")
    st.markdown("Import detailed rate components for schedules")
    
    # Get the list of US states
    states = get_us_states()
    state_options = list(states.items())
    
    # Create a two-column layout
    col1, col2 = st.columns(2)
    
    with col1:
        selected_state = st.selectbox(
            "Select a State",
            options=[code for code, name in state_options],
            format_func=lambda x: f"{x} - {states.get(x, '')}",
            key="detail_state_select"
        )
    
    # Get utilities for the selected state
    selected_utility_id = None
    if selected_state:
        utilities = get_utilities_from_database(supabase, selected_state)
        
        with col2:
            # If utilities exist, show a selectbox
            if utilities:
                utility_options = [(str(u["UtilityID"]), u["UtilityName"]) for u in utilities]
                selected_utility_id = st.selectbox(
                    "Select a Utility",
                    options=[id for id, name in utility_options],
                    format_func=lambda x: next((name for id, name in utility_options if id == x), x),
                    key="detail_utility_select"
                )
            else:
                st.warning(f"No utilities found for {states.get(selected_state, '')}.")
    
    # Check Schedule Status button
    if selected_utility_id:
        check_status_clicked = st.button(
            "Check Schedule Status",
            key="check_status_button",
            help="Check the status of all schedules for this utility"
        )
        
        # Process if button was clicked
        if check_status_clicked:
            handle_check_schedule_status(supabase, selected_utility_id)
    
    # Legacy individual schedule selection (Keep this for Option 3 approach)
    st.markdown("---")
    st.subheader("Single Schedule Detail Import")
    st.markdown("Or, select a specific schedule to import details for:")
    
    if selected_utility_id:
        schedules = get_schedules_from_database(supabase, selected_utility_id)
        
        # If schedules exist, show a selectbox
        if schedules:
            schedule_options = [(str(s["ScheduleID"]), s["ScheduleName"]) for s in schedules]
            selected_schedule_id = st.selectbox(
                "Select a Schedule",
                options=[id for id, name in schedule_options],
                format_func=lambda x: next((name for id, name in schedule_options if id == x), x),
                key="detail_schedule_select"
            )
            
            # Load schedule details button
            if selected_schedule_id:
                load_details_clicked = st.button(
                    "Load Schedule Details",
                    key="load_details_button",
                    help="Fetch schedule details from RateAcuity and save to database"
                )
                
                # Process the load details request if button was clicked
                if load_details_clicked and selected_schedule_id:
                    handle_load_schedule_detail(supabase, selected_schedule_id)
        else:
            st.warning("No schedules found for this utility.")

def handle_load_schedules(supabase, utility_id):
    """
    Handle the process of loading schedules for a utility.
    
    Args:
        supabase: Supabase client instance
        utility_id (str): Utility ID from RateAcuity
    
    Returns:
        None
    """
    # Show loading spinner
    with st.spinner(f"Loading schedules for Utility {utility_id}..."):
        # Fetch schedules from the API
        schedules = get_schedules_by_utility(utility_id)
        
        if not schedules:
            st.warning(f"No schedules found for Utility {utility_id} in RateAcuity API.")
            return
        
        # Insert schedules into the database
        result = insert_schedules(supabase, schedules, utility_id)
        
        # Show the result
        show_result_message(result)
        
        # If successful, refresh the list of schedules
        if result.get("inserted", 0) > 0:
            st.experimental_rerun()

def handle_load_schedule_detail(supabase, schedule_id):
    """
    Handle the process of loading schedule details.
    
    Args:
        supabase: Supabase client instance
        schedule_id (str): Schedule ID from RateAcuity
    
    Returns:
        None
    """
    # Show loading spinner
    with st.spinner(f"Loading details for Schedule {schedule_id}..."):
        # Fetch schedule details from the API
        detail_data = get_schedule_detail(schedule_id)
        
        if not detail_data:
            st.warning(f"No details found for Schedule {schedule_id} in RateAcuity API.")
            return
        
        # Insert schedule details into the database
        result = insert_schedule_details(supabase, detail_data, schedule_id)
        
        # Show the result
        show_result_message(result)

# New functions for schedule status checking and management

def handle_check_schedule_status(supabase, utility_id):
    """
    Handle checking the status of all schedules for a utility.
    
    Args:
        supabase: Supabase client instance
        utility_id (str): Utility ID
    
    Returns:
        None
    """
    # Show loading spinner
    with st.spinner(f"Checking schedules for Utility {utility_id}..."):
        # Fetch schedules from the API
        schedules = get_schedules_by_utility(utility_id)
        
        if not schedules:
            st.warning(f"No schedules found for Utility {utility_id} in RateAcuity API.")
            return
        
        # Make sure all schedules have the utility_id
        for schedule in schedules:
            schedule["UtilityID"] = utility_id
        
        # Check status against the database
        schedules_with_status = check_schedule_status(supabase, schedules, utility_id)
        
        # Display schedules with status
        display_schedules_status_table(supabase, schedules_with_status)

def display_schedules_status_table(supabase, schedules):
    """
    Display a table of schedules with their status and action buttons.
    
    Args:
        supabase: Supabase client instance
        schedules (list): List of schedules with status information
    
    Returns:
        None
    """
    if not schedules:
        st.warning("No schedules found.")
        return
    
    st.subheader("Schedule Status")
    
    # Prepare the data for display
    table_data = []
    for schedule in schedules:
        table_data.append({
            "Schedule ID": schedule.get("ScheduleID"),
            "Schedule Name": schedule.get("ScheduleName", ""),
            "Description": schedule.get("ScheduleDescription", ""),
            "Status": schedule.get("status", "")
        })
    
    # Create DataFrame for display
    df = pd.DataFrame(table_data)
    
    # Display the table
    st.dataframe(df, hide_index=True)
    
    # Add action buttons below the table
    st.subheader("Actions")
    
    # Group schedules by status for better UI organization
    needs_import = [s for s in schedules if s.get("status") == "Needs Full Import"]
    needs_details = [s for s in schedules if s.get("status") == "Import Schedule Details"]
    complete = [s for s in schedules if s.get("status") == "Full Schedule Data in EVready Database!"]
    
    # Display counts
    st.write(f"📊 Summary: {len(needs_import)} need full import, {len(needs_details)} need details, {len(complete)} complete")
    
    # Action for schedules needing full import
    if needs_import:
        st.markdown("### Schedules Needing Full Import")
        for schedule in needs_import:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{schedule.get('ScheduleID')} - {schedule.get('ScheduleName')}")
            with col2:
                if st.button("Import Schedule", key=f"import_schedule_{schedule.get('ScheduleID')}"):
                    handle_import_single_schedule(supabase, schedule, schedule.get('UtilityID'))
    
    # Action for schedules needing details
    if needs_details:
        st.markdown("### Schedules Needing Details")
        for schedule in needs_details:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{schedule.get('ScheduleID')} - {schedule.get('ScheduleName')}")
            with col2:
                if st.button("Import Details", key=f"import_details_{schedule.get('ScheduleID')}"):
                    handle_load_schedule_detail(supabase, schedule.get('ScheduleID'))
    
    # Display complete schedules (no action needed)
    if complete:
        st.markdown("### Complete Schedules")
        for schedule in complete:
            st.write(f"✅ {schedule.get('ScheduleID')} - {schedule.get('ScheduleName')}")

def handle_import_single_schedule(supabase, schedule, utility_id):
    """
    Handle importing a single schedule.
    
    Args:
        supabase: Supabase client instance
        schedule (dict): Schedule data
        utility_id (str): Utility ID
    
    Returns:
        None
    """
    # Show loading spinner
    with st.spinner(f"Importing schedule {schedule.get('ScheduleID')}..."):
        # Prepare the schedule data
        schedules_list = [schedule]
        
        # Insert the schedule
        result = insert_schedules(supabase, schedules_list, utility_id)
        
        # Show the result
        show_result_message(result)
        
        # Prompt for details import
        if result.get("inserted", 0) > 0:
            st.success("Schedule imported successfully!")
            import_details = st.button(
                "Import Details Now?", 
                key=f"details_prompt_{schedule.get('ScheduleID')}"
            )
            
            if import_details:
                handle_load_schedule_detail(supabase, schedule.get('ScheduleID'))
