import streamlit as st
import pandas as pd
from database_connection import get_states_with_utilities, get_utilities_by_state, get_schedules_by_utility

def create_dcfc_inputs(supabase):
    """Create input forms for DCFC payback model."""
    st.header("DC Fast Charging Payback Model")
    st.markdown("Analyze the return on investment for DC Fast Charging infrastructure")
    
    # Initialize session state for DCFC inputs if not exists
    initialize_dcfc_session_state()
    
    # Create main layout with columns
    col1, col2 = st.columns([1, 1])
    
    with col1:
        create_equipment_section()
        create_technical_specifications_section()
        create_funding_section()
    
    with col2:
        create_model_parameters_section()
        create_driver_pricing_section()
        create_other_parameters_section()
        create_utility_selection_section(supabase)
    
    # Additional sections in full width
    create_gas_equivalent_section()
    create_service_assumptions_section()
    create_sessions_range_section()

def initialize_dcfc_session_state():
    """Initialize all DCFC-related session state variables."""
    # Equipment defaults
    if 'dcfc_equipment' not in st.session_state:
        st.session_state.dcfc_equipment = [
            {'name': 'Charger', 'msrp': 0.0, 'quantity': 0},
            {'name': 'Network', 'msrp': 0.0, 'quantity': 0},
            {'name': 'Maintenance', 'msrp': 0.0, 'quantity': 0}
        ]
    
    # Additional costs
    if 'dcfc_hw_sw_upfront_maint' not in st.session_state:
        st.session_state.dcfc_hw_sw_upfront_maint = 0.0
    if 'dcfc_install' not in st.session_state:
        st.session_state.dcfc_install = 0.0
    
    # Technical specifications
    if 'dcfc_total_dc_ports' not in st.session_state:
        st.session_state.dcfc_total_dc_ports = 0
    if 'dcfc_total_dc_power' not in st.session_state:
        st.session_state.dcfc_total_dc_power = 0.0
    if 'dcfc_total_parking_spots' not in st.session_state:
        st.session_state.dcfc_total_parking_spots = 0
    
    # Funding
    if 'dcfc_funding' not in st.session_state:
        st.session_state.dcfc_funding = 0.0
    
    # Model parameters
    if 'dcfc_first_year_kwh_per_session' not in st.session_state:
        st.session_state.dcfc_first_year_kwh_per_session = 45.0
    if 'dcfc_state_code' not in st.session_state:
        st.session_state.dcfc_state_code = ""
    if 'dcfc_exchange_rate' not in st.session_state:
        st.session_state.dcfc_exchange_rate = 1.0
    
    # Driver pricing
    if 'dcfc_fee_per_session' not in st.session_state:
        st.session_state.dcfc_fee_per_session = 0.0
    if 'dcfc_fee_per_kwh' not in st.session_state:
        st.session_state.dcfc_fee_per_kwh = 0.0
    if 'dcfc_fee_per_minute' not in st.session_state:
        st.session_state.dcfc_fee_per_minute = 0.0
    
    # Other parameters
    if 'dcfc_operational_days_per_year' not in st.session_state:
        st.session_state.dcfc_operational_days_per_year = 365
    if 'dcfc_percent_first_year_activated' not in st.session_state:
        st.session_state.dcfc_percent_first_year_activated = 100.0
    if 'dcfc_land_use_costs' not in st.session_state:
        st.session_state.dcfc_land_use_costs = 0.0
    if 'dcfc_other_revenue_per_session' not in st.session_state:
        st.session_state.dcfc_other_revenue_per_session = 0.0
    if 'dcfc_other_revenue_per_year' not in st.session_state:
        st.session_state.dcfc_other_revenue_per_year = 0.0
    
    # Utility selection
    if 'dcfc_selected_state' not in st.session_state:
        st.session_state.dcfc_selected_state = ""
    if 'dcfc_selected_utility' not in st.session_state:
        st.session_state.dcfc_selected_utility = ""
    if 'dcfc_selected_schedule' not in st.session_state:
        st.session_state.dcfc_selected_schedule = ""
    
    # Gas equivalent assumptions
    if 'dcfc_miles_per_gallon' not in st.session_state:
        st.session_state.dcfc_miles_per_gallon = 28.0
    if 'dcfc_cost_per_gallon' not in st.session_state:
        st.session_state.dcfc_cost_per_gallon = 3.75
    if 'dcfc_kwh_per_mile' not in st.session_state:
        st.session_state.dcfc_kwh_per_mile = 3.0
    if 'dcfc_cost_per_mile_gas' not in st.session_state:
        st.session_state.dcfc_cost_per_mile_gas = 0.13
    if 'dcfc_cost_per_mile_ev' not in st.session_state:
        st.session_state.dcfc_cost_per_mile_ev = 0.17
    if 'dcfc_bev_gas_parity' not in st.session_state:
        st.session_state.dcfc_bev_gas_parity = 1.28
    
    # Service assumptions
    if 'dcfc_cloud_service_plan' not in st.session_state:
        st.session_state.dcfc_cloud_service_plan = "Enterprise"
    if 'dcfc_idle_energy_per_dc_port' not in st.session_state:
        st.session_state.dcfc_idle_energy_per_dc_port = 50.0
    if 'dcfc_annual_service_costs' not in st.session_state:
        st.session_state.dcfc_annual_service_costs = 5000.0
    
    # Sessions range
    if 'dcfc_sessions_min' not in st.session_state:
        st.session_state.dcfc_sessions_min = 4.0
    if 'dcfc_sessions_max' not in st.session_state:
        st.session_state.dcfc_sessions_max = 9.0

def create_equipment_section():
    """Create the charging equipment input section."""
    st.subheader("Charging Equipment Needed")
    
    # Create equipment table
    equipment_data = []
    
    for i, item in enumerate(st.session_state.dcfc_equipment):
        col1, col2, col3, col4 = st.columns([3, 2, 1, 2])
        
        with col1:
            st.write(item['name'])
        
        with col2:
            msrp = st.number_input(
                "MSRP", 
                value=item['msrp'], 
                step=0.01, 
                key=f"dcfc_msrp_{i}",
                label_visibility="collapsed"
            )
            st.session_state.dcfc_equipment[i]['msrp'] = msrp
        
        with col3:
            quantity = st.number_input(
                "Quantity", 
                value=item['quantity'], 
                step=1, 
                key=f"dcfc_quantity_{i}",
                label_visibility="collapsed"
            )
            st.session_state.dcfc_equipment[i]['quantity'] = quantity
        
        with col4:
            total = msrp * quantity
            st.write(f"${total:,.2f}")
        
        equipment_data.append({
            'Equipment': item['name'],
            'MSRP': f"${msrp:,.2f}",
            'Quantity': quantity,
            'Total': f"${total:,.2f}"
        })
    
    # Additional costs
    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**HW/SW/Upfront Maint:**")
    with col2:
        hw_sw_upfront = st.number_input(
            "HW/SW/Upfront Maint", 
            value=st.session_state.dcfc_hw_sw_upfront_maint,
            step=0.01,
            key="dcfc_hw_sw_upfront_input",
            label_visibility="collapsed"
        )
        st.session_state.dcfc_hw_sw_upfront_maint = hw_sw_upfront
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Install:**")
    with col2:
        install = st.number_input(
            "Install", 
            value=st.session_state.dcfc_install,
            step=0.01,
            key="dcfc_install_input",
            label_visibility="collapsed"
        )
        st.session_state.dcfc_install = install
    
    # Calculate grand total
    equipment_total = sum([item['msrp'] * item['quantity'] for item in st.session_state.dcfc_equipment])
    grand_total = equipment_total + hw_sw_upfront + install
    
    st.markdown("---")
    st.markdown(f"**Hardware, Upfront Network/Maintenance Fees & Install: ${grand_total:,.2f}**")

def create_technical_specifications_section():
    """Create technical specifications input section."""
    st.subheader("Technical Specifications")
    
    st.session_state.dcfc_total_dc_ports = st.number_input(
        "Total DC Ports",
        value=st.session_state.dcfc_total_dc_ports,
        step=1,
        key="dcfc_total_dc_ports_input"
    )
    
    st.session_state.dcfc_total_dc_power = st.number_input(
        "Total DC Power (kW)",
        value=st.session_state.dcfc_total_dc_power,
        step=0.1,
        key="dcfc_total_dc_power_input"
    )
    
    st.session_state.dcfc_total_parking_spots = st.number_input(
        "Total Parking Spots Needed",
        value=st.session_state.dcfc_total_parking_spots,
        step=1,
        key="dcfc_total_parking_spots_input"
    )

def create_funding_section():
    """Create funding input section."""
    st.subheader("Funding")
    
    st.session_state.dcfc_funding = st.number_input(
        "Funding Amount ($)",
        value=st.session_state.dcfc_funding,
        step=0.01,
        key="dcfc_funding_input"
    )

def create_model_parameters_section():
    """Create model parameters input section."""
    st.subheader("Model Parameters")
    
    st.session_state.dcfc_first_year_kwh_per_session = st.number_input(
        "First Year kWh Per Session",
        value=st.session_state.dcfc_first_year_kwh_per_session,
        step=0.1,
        key="dcfc_first_year_kwh_input"
    )
    
    # US States dropdown
    us_states = [
        "", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    ]
    
    state_index = 0
    if st.session_state.dcfc_state_code in us_states:
        state_index = us_states.index(st.session_state.dcfc_state_code)
    
    st.session_state.dcfc_state_code = st.selectbox(
        "State",
        options=us_states,
        index=state_index,
        key="dcfc_state_code_select"
    )
    
    st.session_state.dcfc_exchange_rate = st.number_input(
        "Exchange Rate",
        value=st.session_state.dcfc_exchange_rate,
        step=0.01,
        key="dcfc_exchange_rate_input"
    )

def create_driver_pricing_section():
    """Create driver pricing input section."""
    st.subheader("Driver Pricing")
    
    st.session_state.dcfc_fee_per_session = st.number_input(
        "Driver fee per charging session ($/session)",
        value=st.session_state.dcfc_fee_per_session,
        step=0.01,
        key="dcfc_fee_per_session_input"
    )
    
    st.session_state.dcfc_fee_per_kwh = st.number_input(
        "Driver fee per kWh of charging ($/kWh)",
        value=st.session_state.dcfc_fee_per_kwh,
        step=0.001,
        key="dcfc_fee_per_kwh_input"
    )
    
    st.session_state.dcfc_fee_per_minute = st.number_input(
        "Driver fee per minute of charging ($/min)",
        value=st.session_state.dcfc_fee_per_minute,
        step=0.01,
        key="dcfc_fee_per_minute_input"
    )

def create_other_parameters_section():
    """Create other parameters input section."""
    st.subheader("Other Parameters")
    
    st.session_state.dcfc_operational_days_per_year = st.number_input(
        "# of operational days per year",
        value=st.session_state.dcfc_operational_days_per_year,
        step=1,
        key="dcfc_operational_days_input"
    )
    
    st.session_state.dcfc_percent_first_year_activated = st.number_input(
        "Percent of first year stations activated (%)",
        value=st.session_state.dcfc_percent_first_year_activated,
        step=0.1,
        key="dcfc_percent_activated_input"
    )
    
    st.session_state.dcfc_land_use_costs = st.number_input(
        "Land use costs ($/month/charging spot)",
        value=st.session_state.dcfc_land_use_costs,
        step=0.01,
        key="dcfc_land_use_costs_input"
    )
    
    st.session_state.dcfc_other_revenue_per_session = st.number_input(
        "Other revenue per session ($)",
        value=st.session_state.dcfc_other_revenue_per_session,
        step=0.01,
        key="dcfc_other_revenue_session_input"
    )
    
    st.session_state.dcfc_other_revenue_per_year = st.number_input(
        "Other revenue per year ($)",
        value=st.session_state.dcfc_other_revenue_per_year,
        step=0.01,
        key="dcfc_other_revenue_year_input"
    )

def create_utility_selection_section(supabase):
    """Create utility selection section using existing database functions."""
    st.subheader("Utility Rate Selection")
    
    # Get states that have utilities with schedules
    try:
        states = get_states_with_utilities(supabase)
        
        if not states:
            st.warning("No states with utilities and rate schedules found in the database.")
            return
        
        # State selection
        state_index = 0
        if st.session_state.dcfc_selected_state in states:
            state_index = states.index(st.session_state.dcfc_selected_state) + 1
        
        st.session_state.dcfc_selected_state = st.selectbox(
            "Select State for Utility Rates",
            options=[""] + states,
            index=state_index,
            key="dcfc_utility_state_select"
        )
        
        # Utility selection
        if st.session_state.dcfc_selected_state:
            utilities_data = get_utilities_by_state(supabase, st.session_state.dcfc_selected_state)
            
            if utilities_data:
                # Create utility options
                utility_options = {utility["UtilityName"]: utility["UtilityID"] for utility in utilities_data}
                utility_names = sorted(list(utility_options.keys()))
                
                utility_index = 0
                if st.session_state.dcfc_selected_utility in utility_names:
                    utility_index = utility_names.index(st.session_state.dcfc_selected_utility) + 1
                
                st.session_state.dcfc_selected_utility = st.selectbox(
                    "Select Utility",
                    options=[""] + utility_names,
                    index=utility_index,
                    key="dcfc_utility_select"
                )
                
                # Store utility ID for schedule lookup
                if st.session_state.dcfc_selected_utility:
                    st.session_state.dcfc_selected_utility_id = utility_options[st.session_state.dcfc_selected_utility]
                
                # Schedule selection
                if st.session_state.dcfc_selected_utility:
                    utility_id = utility_options[st.session_state.dcfc_selected_utility]
                    schedules_data = get_schedules_by_utility(supabase, utility_id)
                    
                    if schedules_data:
                        # Format schedule options
                        schedule_options = {}
                        for schedule in schedules_data:
                            name = schedule.get("ScheduleName", "")
                            desc = schedule.get("ScheduleDescription", "")
                            
                            if desc:
                                display_text = f"{name} - {desc}"
                            else:
                                display_text = name
                            
                            schedule_options[display_text] = schedule.get("ScheduleID")
                        
                        schedule_names = sorted(list(schedule_options.keys()))
                        
                        schedule_index = 0
                        if st.session_state.dcfc_selected_schedule in schedule_names:
                            schedule_index = schedule_names.index(st.session_state.dcfc_selected_schedule) + 1
                        
                        st.session_state.dcfc_selected_schedule = st.selectbox(
                            "Select Rate Schedule",
                            options=[""] + schedule_names,
                            index=schedule_index,
                            key="dcfc_schedule_select"
                        )
                        
                        # Store schedule ID
                        if st.session_state.dcfc_selected_schedule:
                            st.session_state.dcfc_selected_schedule_id = schedule_options[st.session_state.dcfc_selected_schedule]
                    else:
                        st.warning("No rate schedules found for the selected utility.")
            else:
                st.warning(f"No utilities with rate schedules found in {st.session_state.dcfc_selected_state}.")
    
    except Exception as e:
        st.error(f"Error loading utility data: {str(e)}")

def create_gas_equivalent_section():
    """Create gas equivalent assumptions section."""
    st.subheader("Gas Equivalent Assumptions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.session_state.dcfc_miles_per_gallon = st.number_input(
            "Miles per Gallon",
            value=st.session_state.dcfc_miles_per_gallon,
            step=0.1,
            key="dcfc_miles_per_gallon_input"
        )
        
        st.session_state.dcfc_cost_per_gallon = st.number_input(
            "Cost per Gallon ($)",
            value=st.session_state.dcfc_cost_per_gallon,
            step=0.01,
            key="dcfc_cost_per_gallon_input"
        )
    
    with col2:
        st.session_state.dcfc_kwh_per_mile = st.number_input(
            "kWh per Mile",
            value=st.session_state.dcfc_kwh_per_mile,
            step=0.1,
            key="dcfc_kwh_per_mile_input"
        )
        
        st.session_state.dcfc_cost_per_mile_gas = st.number_input(
            "Cost per Mile Gas ($)",
            value=st.session_state.dcfc_cost_per_mile_gas,
            step=0.001,
            key="dcfc_cost_per_mile_gas_input"
        )
    
    with col3:
        st.session_state.dcfc_cost_per_mile_ev = st.number_input(
            "Cost per Mile EV ($)",
            value=st.session_state.dcfc_cost_per_mile_ev,
            step=0.001,
            key="dcfc_cost_per_mile_ev_input"
        )
        
        st.session_state.dcfc_bev_gas_parity = st.number_input(
            "BEV/Gas Parity Ratio",
            value=st.session_state.dcfc_bev_gas_parity,
            step=0.01,
            key="dcfc_bev_gas_parity_input"
        )

def create_service_assumptions_section():
    """Create service assumptions section."""
    st.subheader("Service Assumptions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.session_state.dcfc_cloud_service_plan = st.selectbox(
            "Cloud Service Plan",
            options=["Enterprise", "Professional", "Basic"],
            index=0,
            key="dcfc_cloud_service_select"
        )
    
    with col2:
        st.session_state.dcfc_idle_energy_per_dc_port = st.number_input(
            "Idle energy per DC port (watts)",
            value=st.session_state.dcfc_idle_energy_per_dc_port,
            step=1.0,
            key="dcfc_idle_energy_input"
        )
    
    with col3:
        st.session_state.dcfc_annual_service_costs = st.number_input(
            "Annual Service Costs ($)",
            value=st.session_state.dcfc_annual_service_costs,
            step=100.0,
            key="dcfc_annual_service_input"
        )

def create_sessions_range_section():
    """Create sessions per day range section."""
    st.subheader("Sessions Per Day Analysis Range")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.session_state.dcfc_sessions_min = st.number_input(
            "Minimum Sessions/Day",
            value=st.session_state.dcfc_sessions_min,
            step=0.1,
            key="dcfc_sessions_min_input"
        )
    
    with col2:
        st.session_state.dcfc_sessions_max = st.number_input(
            "Maximum Sessions/Day",
            value=st.session_state.dcfc_sessions_max,
            step=0.1,
            key="dcfc_sessions_max_input"
        )
    
    st.info(f"Analysis will be performed for sessions per day ranging from {st.session_state.dcfc_sessions_min} to {st.session_state.dcfc_sessions_max}")

def display_dcfc_results():
    """Display the DCFC payback model results table."""
    st.subheader("Model Output")
    
    # Placeholder for results table
    st.info("Results table will be displayed here after calculations are implemented.")
    
    # Create placeholder table structure
    sessions_range = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    
    # Create empty dataframe structure for display
    results_data = []
    
    for sessions in sessions_range:
        results_data.append({
            'Sessions/Day/Site': sessions,
            'Sessions/Day/Port': f"Calculation pending",
            '5 Year NPV': f"#DIV/0!",
            '5 Year IRR': f"#DIV/0!",
            '7 Year NPV': f"#DIV/0!",
            '7 Year IRR': f"#DIV/0!",
            '10 Year NPV': f"#DIV/0!",
            '10 Year IRR': f"#DIV/0!"
        })
    
    results_df = pd.DataFrame(results_data)
    st.dataframe(results_df, use_container_width=True)

def get_dcfc_input_summary():
    """Get summary of all DCFC inputs for calculations."""
    return {
        'equipment': st.session_state.dcfc_equipment,
        'hw_sw_upfront_maint': st.session_state.dcfc_hw_sw_upfront_maint,
        'install': st.session_state.dcfc_install,
        'total_dc_ports': st.session_state.dcfc_total_dc_ports,
        'total_dc_power': st.session_state.dcfc_total_dc_power,
        'total_parking_spots': st.session_state.dcfc_total_parking_spots,
        'funding': st.session_state.dcfc_funding,
        'first_year_kwh_per_session': st.session_state.dcfc_first_year_kwh_per_session,
        'state_code': st.session_state.dcfc_state_code,
        'exchange_rate': st.session_state.dcfc_exchange_rate,
        'fee_per_session': st.session_state.dcfc_fee_per_session,
        'fee_per_kwh': st.session_state.dcfc_fee_per_kwh,
        'fee_per_minute': st.session_state.dcfc_fee_per_minute,
        'operational_days_per_year': st.session_state.dcfc_operational_days_per_year,
        'percent_first_year_activated': st.session_state.dcfc_percent_first_year_activated,
        'land_use_costs': st.session_state.dcfc_land_use_costs,
        'other_revenue_per_session': st.session_state.dcfc_other_revenue_per_session,
        'other_revenue_per_year': st.session_state.dcfc_other_revenue_per_year,
        'selected_state': st.session_state.dcfc_selected_state,
        'selected_utility': st.session_state.dcfc_selected_utility,
        'selected_schedule': st.session_state.dcfc_selected_schedule,
        'gas_assumptions': {
            'miles_per_gallon': st.session_state.dcfc_miles_per_gallon,
            'cost_per_gallon': st.session_state.dcfc_cost_per_gallon,
            'kwh_per_mile': st.session_state.dcfc_kwh_per_mile,
            'cost_per_mile_gas': st.session_state.dcfc_cost_per_mile_gas,
            'cost_per_mile_ev': st.session_state.dcfc_cost_per_mile_ev,
            'bev_gas_parity': st.session_state.dcfc_bev_gas_parity
        },
        'service_assumptions': {
            'cloud_service_plan': st.session_state.dcfc_cloud_service_plan,
            'idle_energy_per_dc_port': st.session_state.dcfc_idle_energy_per_dc_port,
            'annual_service_costs': st.session_state.dcfc_annual_service_costs
        },
        'sessions_range': {
            'min': st.session_state.dcfc_sessions_min,
            'max': st.session_state.dcfc_sessions_max
        }
    }
