"""
Main application file for the RateAcuity Data Importer.
This Streamlit app allows importing utility rate data from RateAcuity API
into the Supabase database used by the EVready Playbook.
"""

import streamlit as st
import os
import sys

# Add the parent directory to the path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Try direct import first
try:
    from database_connection import initialize_database
except ImportError:
    # If that fails, try to import from the parent directory
    from evready_playbook.database_connection import initialize_database

# Import database connection
from database_connection import initialize_database

# Import UI components
from ui.components import create_header, create_about_section
from ui.utilities_page import render_utilities_section
from ui.schedules_page import render_schedules_section

def configure_page():
    """
    Configure Streamlit page settings.
    
    Returns:
        None
    """
    st.set_page_config(
        page_title="RateAcuity Data Importer",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def main():
    """
    Main application entry point.
    
    Returns:
        None
    """
    # Configure page settings
    configure_page()
    
    # Create header
    create_header()
    
    # Initialize database connection
    supabase = initialize_database()
    if not supabase:
        st.error("Failed to connect to the database. Please check your configuration.")
        st.stop()
    
    # Create tabs for different functions
    tab1, tab2, tab3 = st.tabs(["Utilities", "Rate Schedules", "About"])
    
    # Utilities tab
    with tab1:
        render_utilities_section(supabase)
    
    # Schedules tab
    with tab2:
        render_schedules_section(supabase)
    
    # About tab
    with tab3:
        create_about_section()

if __name__ == "__main__":
    main()
