"""
Common UI components for the Rate Importer application.
Provides reusable UI elements used across the application.
"""

import streamlit as st
import os

def create_header():
    """
    Creates the application header with logo and title.
    
    Returns:
        None
    """
    # Create a container for the header
    header_container = st.container()
    
    with header_container:
        col1, col2 = st.columns([1, 5])
        
        # Display logo in the first column if available
        try:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(current_dir, "logo.png")
            if os.path.exists(logo_path):
                col1.image(logo_path, width=80)
            else:
                col1.write("Logo not found")
        except Exception as e:
            col1.write(f"Error loading logo: {e}")
        
        # Display title in the second column
        col2.title("RateAcuity Data Importer")
        col2.markdown("Import utility rate data from RateAcuity API to the Supabase database")
    
    # Add a separator
    st.markdown("---")

def show_result_message(result, success_icon="✅", error_icon="❌"):
    """
    Displays operation result messages with appropriate styling.
    
    Args:
        result (dict): Result dictionary containing message and count information
        success_icon (str): Icon to display for success messages
        error_icon (str): Icon to display for error messages
    
    Returns:
        None
    """
    if not result:
        return
    
    message = result.get("message", "")
    
    # Determine if this is a success or error message
    inserted = result.get("inserted", 0)
    failed = result.get("failed", 0)
    skipped = result.get("skipped", 0)
    
    if failed > 0 or skipped > 0:
        # Partial success or error
        if inserted > 0:
            # Partial success
            st.warning(f"⚠️ {message}")
            
            if failed > 0:
                st.warning(f"- Failed to process {failed} items")
            
            if skipped > 0:
                st.warning(f"- Skipped {skipped} items")
        else:
            # Complete failure
            st.error(f"{error_icon} {message}")
    else:
        # Complete success
        st.success(f"{success_icon} {message}")

def create_about_section():
    """
    Creates an expandable section with information about the application.
    
    Returns:
        None
    """
    with st.expander("About this tool"):
        st.markdown("""
        ## RateAcuity Data Importer
        
        This tool imports utility rate data from the RateAcuity API into the Supabase database
        used by the EVready Playbook application.
        
        ### Features:
        
        - Import utilities by state
        - Import schedules for specific utilities
        - Import detailed rate components for specific schedules
        
        ### Process:
        
        1. Select a state and load utilities
        2. Select a utility and load schedules
        3. Select a schedule and load detailed rate components
        """)
