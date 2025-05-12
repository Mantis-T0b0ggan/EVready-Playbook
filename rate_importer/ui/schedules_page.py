"""
UI components for the Schedules page of the Rate Importer application.
Handles the display and interaction for importing schedules and their details.
"""

import streamlit as st
import sys
import os

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
    get_schedules_from_database
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
                width="medium",  # Medium width for the name
            ),
            "Description": st.column_config.TextColumn(
                "Description",
                width="large",  # Allow description to use more space
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
    st.header("Load Schedule Details")
    st.markdown("Import detailed rate components for a specific schedule")
    
    # Get the list of US states
    states = get_us_states()
    state_options = list(states.items())
    
    # Create a three-column layout
    col1, col2, col3 = st.columns(3)
    
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
    
    # Get schedules for the selected utility
    selected_schedule_id = None
    if selected_utility_id:
        schedules = get_schedules_from_database(supabase, selected_utility_id)
        
        with col3:
            # If schedules exist, show a selectbox
            if schedules:
                schedule_options = [(str(s["ScheduleID"]), s["ScheduleName"]) for s in schedules]
                selected_schedule_id = st.selectbox(
                    "Select a Schedule",
                    options=[id for id, name in schedule_options],
                    format_func=lambda x: next((name for id, name in schedule_options if id == x), x),
                    key="detail_schedule_select"
                )
            else:
                st.warning("No schedules found for this utility.")
    
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
        from ui.components import show_result_message
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
        from ui.components import show_result_message
        show_result_message(result)
