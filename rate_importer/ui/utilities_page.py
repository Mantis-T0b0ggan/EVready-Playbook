"""
UI components for the Utilities page of the Rate Importer application.
Handles the display and interaction for importing utilities.
"""

import streamlit as st
from ..utils.state_utils import get_us_states
from ..utils.api_client import get_utilities
from ..utils.db_operations import insert_utilities, get_utilities_from_database

def render_utilities_section(supabase):
    """
    Render the utilities management section of the application.
    
    Args:
        supabase: Supabase client instance
    
    Returns:
        None
    """
    st.header("Load Utilities")
    st.markdown("Import utilities from RateAcuity into your database")
    
    # Get the list of US states
    states = get_us_states()
    state_options = list(states.items())
    
    # Create a selectbox for state selection
    col1, col2 = st.columns([2, 1])
    
    with col1:
        selected_state = st.selectbox(
            "Select a State",
            options=[code for code, name in state_options],
            format_func=lambda x: f"{x} - {states.get(x, '')}",
            key="utility_state_select"
        )
    
    with col2:
        # Load utilities button
        load_utilities_clicked = st.button(
            "Load Utilities",
            key="load_utilities_button",
            help="Fetch utilities from RateAcuity and save to database"
        )
    
    # Display existing utilities in the database for the selected state
    if selected_state:
        st.subheader(f"Existing Utilities for {states.get(selected_state, selected_state)}")
        existing_utilities = get_utilities_from_database(supabase, selected_state)
        
        if existing_utilities:
            # Create a dataframe for display
            utility_data = []
            for utility in existing_utilities:
                utility_data.append({
                    "Utility ID": utility.get("UtilityID"),
                    "Utility Name": utility.get("UtilityName")
                })
            
            st.dataframe(utility_data, use_container_width=True)
        else:
            st.info("No utilities found in the database for this state.")
    
    # Process the load utilities request if button was clicked
    if load_utilities_clicked and selected_state:
        handle_load_utilities(supabase, selected_state, states.get(selected_state, ""))

def handle_load_utilities(supabase, state_code, state_name):
    """
    Handle the process of loading utilities for a state.
    
    Args:
        supabase: Supabase client instance
        state_code (str): Two-letter state code
        state_name (str): Full state name
    
    Returns:
        None
    """
    # Show loading spinner
    with st.spinner(f"Loading utilities for {state_name}..."):
        # Fetch utilities from the API
        utilities = get_utilities(state_code)
        
        if not utilities:
            st.warning(f"No utilities found for {state_name} in RateAcuity API.")
            return
        
        # Insert utilities into the database
        result = insert_utilities(supabase, utilities, state_code)
        
        # Show the result
        from ..ui.components import show_result_message
        show_result_message(result)
        
        # If successful, refresh the list of utilities
        if result.get("inserted", 0) > 0:
            st.experimental_rerun()
