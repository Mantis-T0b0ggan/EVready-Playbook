import streamlit as st
import sys
import os

# Add current directory to path to make imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import components
from config.app_config import configure_page
from database.connection import initialize_database
from ui.main_page import create_header
from ui.inputs import create_input_forms
from ui.outputs import display_results

def main():
    """Main application entry point."""
    # Configure page settings
    configure_page()
    
    # Initialize database connection
    supabase = initialize_database()
    if not supabase:
        st.stop()
    
    # Create header section
    create_header()
    
    # Create tabs
    tab1, tab2 = st.tabs(["Bill Estimation & Comparison", "Schedule Browser"])
    
    # Tab 1: Bill Estimation Tool
    with tab1:
        st.header("Electric Bill Estimation Tool")
        st.markdown("Estimate your electric bill based on your usage and utility rate schedule.")
        
        # Create input forms and get inputs
        inputs = create_input_forms(supabase, "tab1")
        
        # Display results if calculate button was pressed or calculation was already done
        if (inputs.get('calculate_pressed', False) or 
            st.session_state.get('bill_calculated', False)):
            
            # Set bill_calculated to True if calculate button was pressed
            if inputs.get('calculate_pressed', False):
                st.session_state.bill_calculated = True
            
            # Display results
            display_results(supabase, inputs, "tab1")
    
    # Tab 2: Schedule Browser (placeholder)
    with tab2:
        st.header("Utility Rate Schedule Browser")
        st.info("This feature will allow you to browse through rate schedules. Coming soon!")
        
        # Create input forms for Tab 2
        create_input_forms(supabase, "tab2")

if __name__ == "__main__":
    main()
