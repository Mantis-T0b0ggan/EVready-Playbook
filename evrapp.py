import streamlit as st
import sys
import os

# Add current directory to path to make imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import components based on actual file structure
from config import configure_page  # Changed from config.app_config
from database_connection import initialize_database  # Changed from database.connection

def create_header():
    """Create the header section for the application."""
    st.title("EVready Playbook")
    st.subheader("Electric Rate Analysis for EV Charging Infrastructure")
    st.markdown("---")

def create_input_forms(supabase, tab_id):
    """Create input forms for bill estimation."""
    with st.form(f"input_form_{tab_id}"):
        # Basic inputs
        col1, col2 = st.columns(2)
        
        with col1:
            selected_state = st.selectbox("Select State", ["California", "Oregon", "Washington"])
            
            # Query utilities based on state
            utilities_query = supabase.from_("Utility").select("UtilityID, UtilityName").eq("State", selected_state).execute()
            utilities = utilities_query.data if hasattr(utilities_query, 'data') else []
            utility_options = [f"{u['UtilityName']}" for u in utilities]
            
            selected_utility = st.selectbox("Select Utility", utility_options)
            utility_id = next((u['UtilityID'] for u in utilities if u['UtilityName'] == selected_utility), None)
            
        with col2:
            # Query rate schedules based on utility
            if utility_id:
                schedules_query = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", utility_id).execute()
                schedules = schedules_query.data if hasattr(schedules_query, 'data') else []
                schedule_options = [f"{s['ScheduleName']}" for s in schedules]
                
                selected_schedule = st.selectbox("Select Rate Schedule", schedule_options)
                schedule_id = next((s['ScheduleID'] for s in schedules if s['ScheduleName'] == selected_schedule), None)
            else:
                selected_schedule = st.selectbox("Select Rate Schedule", ["No schedules available"])
                schedule_id = None
            
            billing_month = st.selectbox("Billing Month", 
                                      ["January", "February", "March", "April", "May", "June", 
                                       "July", "August", "September", "October", "November", "December"])
        
        # Usage inputs
        st.subheader("Usage Information")
        col1, col2 = st.columns(2)
        
        with col1:
            usage_kwh = st.number_input("Energy Usage (kWh)", min_value=0.0, value=1000.0, step=100.0)
        
        with col2:
            demand_kw = st.number_input("Peak Demand (kW)", min_value=0.0, value=20.0, step=1.0)
            power_factor = st.slider("Power Factor", min_value=0.7, max_value=1.0, value=0.95, step=0.01)
        
        # Submit button
        calculate_pressed = st.form_submit_button("Calculate Bill")
        
        # Return inputs
        return {
            'selected_state': selected_state,
            'selected_utility': selected_utility,
            'utility_id': utility_id,
            'selected_schedule': selected_schedule,
            'schedule_id': schedule_id,
            'billing_month': billing_month,
            'usage_kwh': usage_kwh,
            'demand_kw': demand_kw,
            'power_factor': power_factor,
            'calculate_pressed': calculate_pressed
        }

def display_results(supabase, inputs, tab_id):
    """Display bill estimation results."""
    if not inputs.get('schedule_id'):
        st.warning("Please select a valid rate schedule.")
        return
    
    # Placeholder for actual bill calculation
    # In a real implementation, this would call functions from bill_est_calculator.py
    st.subheader("Bill Estimation Results")
    
    # Display a simple placeholder result
    st.metric("Estimated Monthly Bill", f"${1000:.2f}")
    
    # Display a placeholder for the bill breakdown
    st.subheader("Bill Breakdown")
    placeholder_data = {
        "Description": ["Service Charge", "Energy Charges", "Demand Charges", "Taxes", "Total"],
        "Amount": [50.00, 650.00, 250.00, 50.00, 1000.00]
    }
    import pandas as pd
    st.dataframe(pd.DataFrame(placeholder_data), hide_index=True)
    
    # Placeholder for bill comparison visualization
    st.subheader("Rate Comparison")
    st.info("Select alternative rates to compare costs.")

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
