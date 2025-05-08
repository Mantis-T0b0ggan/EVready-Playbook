import streamlit as st
import sys
import os

# Add current directory to path to make imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import components - adjusted to match your actual file structure
from config import configure_page  # Changed from config.app_config
from database_connection import initialize_database  # Changed from database.connection
# Create placeholder functions for missing modules
# These will need to be implemented or imported from the correct locations

def create_header():
    """Placeholder for header creation function."""
    st.title("EVready Playbook")
    st.markdown("Estimate and compare electricity costs for EV charging infrastructure")

def create_input_forms(supabase, tab_id):
    """Placeholder for input forms creation function."""
    st.subheader("Input Your Details")
    
    # Create columns for a cleaner layout
    col1, col2 = st.columns(2)
    
    with col1:
        # Select state - add tab_id to make each widget ID unique
        state = st.selectbox(
            "Select State", 
            ["California", "Oregon", "Washington"],
            key=f"{tab_id}_state"
        )
        
        # Select utility with unique key
        utility = st.selectbox(
            "Select Utility", 
            ["Pacific Power", "PG&E", "SCE"],
            key=f"{tab_id}_utility"
        )
        
        # Select rate schedule with unique key
        schedule = st.selectbox(
            "Select Rate Schedule", 
            ["GS-TOU", "B-19", "TOU-GS-3"],
            key=f"{tab_id}_schedule"
        )
    
    with col2:
        # Input usage details with unique keys
        usage_kwh = st.number_input(
            "Monthly Energy Usage (kWh)", 
            min_value=0.0, 
            value=10000.0,
            key=f"{tab_id}_usage_kwh"
        )
        
        demand_kw = st.number_input(
            "Peak Demand (kW)", 
            min_value=0.0, 
            value=50.0,
            key=f"{tab_id}_demand_kw"
        )
        
        power_factor = st.slider(
            "Power Factor", 
            min_value=0.8, 
            max_value=1.0, 
            value=0.95, 
            step=0.01,
            key=f"{tab_id}_power_factor"
        )
        
        billing_month = st.selectbox(
            "Billing Month", 
            ["January", "February", "March", "April", "May", "June", 
             "July", "August", "September", "October", "November", "December"],
            key=f"{tab_id}_billing_month"
        )
    
    # Calculate button with unique key
    calculate_pressed = st.button("Calculate Bill", key=f"{tab_id}_calculate_button")
    
    # Return inputs as dictionary
    return {
        'state': state,
        'utility': utility,
        'schedule': schedule,
        'usage_kwh': usage_kwh,
        'demand_kw': demand_kw,
        'power_factor': power_factor,
        'billing_month': billing_month,
        'calculate_pressed': calculate_pressed
    }

def display_results(supabase, inputs, tab_id):
    """Placeholder for results display function."""
    st.subheader("Bill Calculation Results")
    
    # Display a placeholder bill
    st.metric(f"{tab_id}_total_bill", "Estimated Monthly Bill", f"${2401.61}")
    
    # Create columns for bill breakdown
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Bill Breakdown")
        st.markdown(f"""
        - Service Charge: $49.28
        - Energy Charge: $1,275.35
        - Demand Charge: $925.00
        - Other Charges: $37.62
        - Taxes: $114.36
        """)
    
    with col2:
        st.subheader("Bill Composition")
        st.text("Placeholder for bill composition chart")

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
        
        # Create input forms for Tab 2 (with different tab_id to ensure unique widget IDs)
        create_input_forms(supabase, "tab2")

if __name__ == "__main__":
    main()
