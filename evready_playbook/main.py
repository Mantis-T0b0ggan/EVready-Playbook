import streamlit as st
import os
from datetime import datetime

# These will be imports from other modules we'll create
from config import configure_page
from database_connection import initialize_database
from bill_calculator import calculate_current_bill, calculate_bill
from visualizations import (
    create_comparison_dataframe,
    create_comparison_visualization,
    create_cost_breakdown_comparison
)
from ui_components import display_bill_results, create_usage_inputs, display_comparison_results
from dcfc_payback_model import create_dcfc_inputs, display_dcfc_results

def main():
    """Main application entry point."""
    # Configure page settings first
    configure_page()
    
    # Initialize Supabase database connection with error handling
    supabase = initialize_database()
    if not supabase:
        st.stop()
    
    # Main app title with logo
    col1, col2, col3 = st.columns([3, 4, 3])
    with col2:
        try:
            st.image("logo.png", width=400, use_column_width=True)
        except Exception:
            st.warning("Note: Company logo could not be loaded. Please ensure logo.png exists in the app directory.")
    
    # Title centered on the page
    st.markdown("<h1 style='text-align: center; margin-top: 1.5rem;'>EVready Playbook</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; margin-bottom: 2rem; color: #666;'>Comprehensive Utility Rate Analysis & EV Infrastructure Planning</p>", unsafe_allow_html=True)
    
    # Add reset button at the top of the app
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("Reset All"):
            # Clear all session state variables
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.experimental_rerun()
    
    # Create tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["Bill Estimation & Comparison", "Schedule Browser", "DCFC Payback Model"])
    
    # Tab 1: Bill Estimation Tool
    with tab1:
        st.header("Electric Bill Estimation Tool")
        st.markdown("Estimate your electric bill based on your usage and utility rate schedule.")
        
        # Step 1: State Selection
        selected_state = select_state(supabase, "tab1")
        
        # Step 2: Utility Selection
        selected_utility, selected_utility_id = select_utility(supabase, selected_state, "tab1")
        
        # Step 3: Schedule Selection
        selected_schedule, selected_schedule_id = select_schedule(supabase, selected_utility_id, "tab1")
        
        # Step 4: Check rate components
        rate_components = check_rate_components(supabase, selected_schedule_id)
        
        # Step 5: Usage inputs
        usage_inputs = create_usage_inputs(
            selected_schedule_id, 
            rate_components, 
            "tab1"
        )
        
        # Step 6: Calculate button and display results
        if process_calculation_request(
            supabase, 
            selected_schedule_id, 
            selected_schedule, 
            selected_state, 
            selected_utility,
            usage_inputs, 
            rate_components
        ):
            # Display comparison section
            display_comparison_section(supabase, selected_utility_id, selected_schedule_id, usage_inputs)
    
    # Tab 2: Schedule Browser
    with tab2:
        st.header("Utility Rate Schedule Browser")
        st.info("This feature will allow you to browse through rate schedules. Coming soon!")
        
        # Schedule browser functionality (simplified version of Tab 1)
        selected_state_tab2 = select_state(supabase, "tab2")
        selected_utility_tab2, selected_utility_id_tab2 = select_utility(supabase, selected_state_tab2, "tab2")
        selected_schedule_tab2, selected_schedule_id_tab2 = select_schedule(supabase, selected_utility_id_tab2, "tab2")
        
        if selected_schedule_id_tab2:
            rate_components_tab2 = check_rate_components(supabase, selected_schedule_id_tab2)
            usage_inputs_tab2 = create_usage_inputs(selected_schedule_id_tab2, rate_components_tab2, "tab2")
            
            if st.button("Calculate Bill Estimate", key="calculate_bill_tab2"):
                st.info("Schedule browser functionality will be implemented in a future update. Please use the 'Bill Estimation & Comparison' tab for now.")
    
    # Tab 3: DCFC Payback Model
    with tab3:
        # Create the DCFC input forms
        create_dcfc_inputs()
        
        # Add calculate button
        st.markdown("---")
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("Calculate Payback", key="calculate_dcfc_payback"):
                # For now, just display the placeholder results
                # Later we'll implement actual calculations
                display_dcfc_results()
                st.success("DCFC payback calculations completed! (Note: This is currently showing placeholder data)")
        
        # Display results if they exist in session state
        if st.session_state.get('dcfc_calculated', False):
            display_dcfc_results()


def select_state(supabase, tab_key):
    """Get states that have utilities with schedules."""
    try:
        # Get all utilities that have schedules
        utilities_with_schedules = supabase.from_("Schedule_Table").select("UtilityID").execute()
        utility_ids = [item['UtilityID'] for item in utilities_with_schedules.data]
        
        # If there are utilities with schedules, get the states
        if utility_ids:
            states_response = supabase.from_("Utility").select("State").in_("UtilityID", utility_ids).execute()
            states_data = states_response.data
            
            # Extract unique states and sort them
            states = sorted(list(set([state["State"] for state in states_data if state["State"]])))
        else:
            states = []
        
        if not states:
            st.warning("No states with utilities and rate schedules found in the database.")
            return ""
        
        state_key = f"selected_state_{tab_key}"
        if state_key not in st.session_state:
            st.session_state[state_key] = ""
        
        selected_state = st.selectbox(
            "Select State", 
            [""] + states, 
            index=states.index(st.session_state[state_key]) + 1 if st.session_state[state_key] in states else 0,
            key=f"state_selector_{tab_key}"
        )
        st.session_state[state_key] = selected_state
        return selected_state
    
    except Exception as e:
        st.error(f"Error loading states: {str(e)}")
        return ""


def select_utility(supabase, selected_state, tab_key):
    """Select utility based on state."""
    selected_utility = None
    selected_utility_id = None
    
    if selected_state:
        try:
            # Get utilities in the selected state that have schedules
            utilities_with_schedules = supabase.from_("Schedule_Table").select("UtilityID").execute()
            utility_ids = [item['UtilityID'] for item in utilities_with_schedules.data]
            
            if utility_ids:
                utilities_response = supabase.from_("Utility").select("UtilityID, UtilityName").eq("State", selected_state).in_("UtilityID", utility_ids).execute()
                utilities_data = utilities_response.data
            else:
                utilities_data = []
            
            if not utilities_data:
                st.warning(f"No utilities with rate schedules found in {selected_state}.")
            else:
                # Create a dictionary for easy lookup of UtilityID by name
                utilities_dict = {utility["UtilityName"]: utility["UtilityID"] for utility in utilities_data}
                utility_names = sorted(list(utilities_dict.keys()))
                
                utility_key = f"selected_utility_{tab_key}"
                if utility_key not in st.session_state:
                    st.session_state[utility_key] = ""
                
                selected_utility = st.selectbox(
                    "Select Utility", 
                    [""] + utility_names, 
                    index=utility_names.index(st.session_state[utility_key]) + 1 if st.session_state[utility_key] in utility_names else 0,
                    key=f"utility_selector_{tab_key}"
                )
                st.session_state[utility_key] = selected_utility
                
                if selected_utility:
                    selected_utility_id = utilities_dict[selected_utility]
                    st.session_state[f"selected_utility_id_{tab_key}"] = selected_utility_id
        except Exception as e:
            st.error(f"Error loading utilities: {str(e)}")
    
    return selected_utility, selected_utility_id


def select_schedule(supabase, selected_utility_id, tab_key):
    """Select rate schedule based on utility."""
    selected_schedule = None
    selected_schedule_id = None
    
    if selected_utility_id:
        try:
            schedules_response = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName, ScheduleDescription").eq("UtilityID", selected_utility_id).execute()
            schedules_data = schedules_response.data
            
            if not schedules_data:
                st.warning(f"No rate schedules found for the selected utility.")
            else:
                # Format schedule options with name and description
                schedule_options = {}
                for schedule in schedules_data:
                    name = schedule.get("ScheduleName", "")
                    desc = schedule.get("ScheduleDescription", "")
                    
                    # Create display text with both name and description
                    if desc:
                        display_text = f"{name} - {desc}"
                    else:
                        display_text = name
                    
                    schedule_options[display_text] = schedule.get("ScheduleID")
                
                schedule_display_options = sorted(list(schedule_options.keys()))
                
                schedule_key = f"selected_schedule_{tab_key}"
                if schedule_key not in st.session_state:
                    st.session_state[schedule_key] = ""
                
                selected_schedule_display = st.selectbox(
                    "Select Rate Schedule", 
                    [""] + schedule_display_options, 
                    index=schedule_display_options.index(st.session_state[schedule_key]) + 1 if st.session_state[schedule_key] in schedule_display_options else 0,
                    key=f"schedule_selector_{tab_key}"
                )
                
                if selected_schedule_display:
                    selected_schedule_id = schedule_options[selected_schedule_display]
                    selected_schedule = selected_schedule_display
                    st.session_state[schedule_key] = selected_schedule
                    st.session_state[f"selected_schedule_id_{tab_key}"] = selected_schedule_id
        except Exception as e:
            st.error(f"Error loading schedules: {str(e)}")
    
    return selected_schedule, selected_schedule_id


def check_rate_components(supabase, selected_schedule_id):
    """Check what types of charges are included in the selected schedule."""
    if not selected_schedule_id:
        return {}

    try:
        # Check for energy charges
        energy_response = supabase.from_("Energy_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
        energy_time_response = supabase.from_("EnergyTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
        incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
        
        has_energy_charges = (
            len(energy_response.data) > 0 or 
            len(energy_time_response.data) > 0 or 
            len(incremental_energy_response.data) > 0
        )
        
        # Check for demand charges
        demand_response = supabase.from_("Demand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
        demand_time_response = supabase.from_("DemandTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
        incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
        
        has_demand_charges = (
            len(demand_response.data) > 0 or 
            len(demand_time_response.data) > 0 or 
            len(incremental_demand_response.data) > 0
        )
        
        # Check for reactive demand charges
        reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
        has_reactive_demand = len(reactive_demand_response.data) > 0
        
        # Check for time-of-use energy periods
        has_tou_energy = False
        tou_periods = []
        
        if len(energy_time_response.data) > 0:
            has_tou_energy = True
            tou_response = supabase.from_("EnergyTime_Table").select("Description, TimeOfDay").eq("ScheduleID", selected_schedule_id).execute()
            
            # Get unique TOU periods
            seen_periods = set()
            for period in tou_response.data:
                description = period.get("Description", "")
                time_of_day = period.get("TimeOfDay", "")
                
                period_key = f"{description} ({time_of_day})"
                if period_key not in seen_periods:
                    tou_periods.append({
                        "description": description,
                        "timeofday": time_of_day,
                        "display": period_key
                    })
                    seen_periods.add(period_key)
        
        return {
            "has_energy_charges": has_energy_charges,
            "has_demand_charges": has_demand_charges,
            "has_reactive_demand": has_reactive_demand,
            "has_tou_energy": has_tou_energy,
            "tou_periods": tou_periods
        }
    
    except Exception as e:
        st.error(f"Error checking rate components: {str(e)}")
        return {}


def process_calculation_request(supabase, schedule_id, schedule_name, state, utility, usage_inputs, rate_components):
    """Process bill calculation request and display results."""
    if not schedule_id:
        return False
        
    # Check if we have required inputs
    has_required_inputs = (
        (not rate_components.get("has_energy_charges", False) or usage_inputs.get("usage_kwh") is not None) and
        (not rate_components.get("has_demand_charges", False) or usage_inputs.get("demand_kw") is not None)
    )
    
    if not has_required_inputs:
        return False
    
    # Calculate button
    calc_col1, calc_col2 = st.columns([1, 5])
    with calc_col1:
        calculate_pressed = st.button("Calculate Bill Estimate", key="calculate_bill_tab1")
    
    if calculate_pressed or st.session_state.get('bill_calculated', False):
        if calculate_pressed:  # Only recalculate if the button was just pressed
            st.session_state.bill_calculated = True
            
            # Calculate the bill for the selected schedule
            try:
                service_charge, energy_charge, demand_charge, other_charges, tax_amount, total_bill, bill_df, bill_breakdown = calculate_current_bill(
                    supabase, 
                    schedule_id, 
                    schedule_name, 
                    usage_inputs.get("usage_kwh", 0), 
                    usage_inputs.get("usage_by_tou", {}),
                    usage_inputs.get("demand_kw", 0), 
                    usage_inputs.get("power_factor", 0.9), 
                    usage_inputs.get("billing_month", ""),
                    rate_components.get("has_energy_charges", False),
                    rate_components.get("has_demand_charges", False),
                    rate_components.get("has_reactive_demand", False)
                )
                
                # Store the results in session state
                st.session_state.service_charge = service_charge
                st.session_state.energy_charge = energy_charge
                st.session_state.demand_charge = demand_charge
                st.session_state.other_charges = other_charges
                st.session_state.tax_amount = tax_amount
                st.session_state.total_bill = total_bill
                st.session_state.bill_df = bill_df
                st.session_state.bill_breakdown = bill_breakdown
                
                # Store the current bill details for comparison
                st.session_state.current_bill = {
                    "schedule_id": schedule_id,
                    "schedule_name": schedule_name,
                    "total": total_bill,
                    "projected": total_bill * 1.02,  # Simple 2% projection for example purposes
                    "breakdown": bill_breakdown  # Store the breakdown for visualization
                }
                
                # Clear previous comparison results when recalculating
                if 'comparison_results' in st.session_state:
                    st.session_state.comparison_results = []
                    
            except Exception as e:
                st.error(f"Error calculating bill: {str(e)}")
        
        # Display the bill results
        display_bill_results(
            state, 
            utility, 
            schedule_name, 
            usage_inputs, 
            rate_components
        )
        
        return True
    
    return False


def display_comparison_section(supabase, utility_id, schedule_id, usage_inputs):
    """Display the rate comparison section."""
    st.markdown("---")
    st.subheader("Rate Comparison")
    st.markdown("Compare your current rate with other available rate schedules from this utility.")
    
    try:
        other_schedules_response = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName, ScheduleDescription").eq("UtilityID", utility_id).not_.eq("ScheduleID", schedule_id).execute()
        other_schedules_data = other_schedules_response.data
        
        if not other_schedules_data:
            st.info(f"No other rate schedules available for comparison from the selected utility.")
            return
            
        # Format schedule options with name and description
        other_schedule_options = {}
        for schedule in other_schedules_data:
            name = schedule.get("ScheduleName", "")
            desc = schedule.get("ScheduleDescription", "")
            
            # Create display text with both name and description
            if desc:
                display_text = f"{name} - {desc}"
            else:
                display_text = name
            
            other_schedule_options[display_text] = schedule.get("ScheduleID")
        
        # Allow selection of up to 3 schedules to compare
        st.markdown("Select up to 3 rate schedules to compare with your current rate:")
        
        # Get or initialize the comparison selections in session state
        if 'selected_comparison_schedules' not in st.session_state:
            st.session_state.selected_comparison_schedules = []
        
        # Use multiselect for choosing comparison schedules
        comparison_schedule_options = list(other_schedule_options.keys())
        selected_comparison_schedules = st.multiselect(
            "Select schedules to compare", 
            comparison_schedule_options,
            default=st.session_state.selected_comparison_schedules,
            max_selections=3,
            key="comparison_schedules_tab1"
        )
        
        # Store the selection in session state
        st.session_state.selected_comparison_schedules = selected_comparison_schedules
        
        # Create a button to calculate the comparison
        comp_col1, comp_col2 = st.columns([1, 5])
        with comp_col1:
            compare_pressed = st.button("Compare Rates", key="compare_rates_tab1")
        
        if selected_comparison_schedules and (compare_pressed or 'comparison_results' in st.session_state and st.session_state.comparison_results):
            # Start a spinner for better user experience
            with st.spinner("Calculating rate comparisons..."):
                try:
                    if compare_pressed or not st.session_state.comparison_results:  # Only recalculate if the button was just pressed
                        comparison_results = [st.session_state.current_bill]
                        
                        # Calculate bills for each selected comparison schedule
                        for schedule_display in selected_comparison_schedules:
                            comp_schedule_id = other_schedule_options[schedule_display]
                            
                            # Calculate bill using the same usage values but different schedule
                            comp_bill = calculate_bill(
                                supabase=supabase,
                                schedule_id=comp_schedule_id,
                                schedule_name=schedule_display,
                                usage_kwh=usage_inputs.get("usage_kwh", 0),
                                demand_kw=usage_inputs.get("demand_kw", 0),
                                power_factor=usage_inputs.get("power_factor", 0.9),
                                billing_month=usage_inputs.get("billing_month", "")
                            )
                            
                            comparison_results.append(comp_bill)
                        
                        # Store the comparison results in session state
                        st.session_state.comparison_results = comparison_results
                    
                    # Display comparison results
                    display_comparison_results(st.session_state.comparison_results)
                    
                except Exception as e:
                    st.error(f"Error during comparison calculation: {str(e)}")
                    st.info("Try selecting your schedules again or use the Reset All button at the top to start fresh.")
    
    except Exception as e:
        st.error(f"Error loading comparison schedules: {str(e)}")


if __name__ == "__main__":
    main()
