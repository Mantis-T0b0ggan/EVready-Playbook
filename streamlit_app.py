import os
import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Configure page settings first (must be the first Streamlit command)
st.set_page_config(
    page_title="EVready Playbook",
    page_icon="⚡",
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Load environment variables from .env file if it exists (for local development)
# Otherwise, rely on environment variables set in the deployment platform
load_dotenv()

# Try to get credentials from Streamlit secrets first, then fall back to environment variables
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    # Fall back to environment variables
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Verify credentials and initialize Supabase client
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Supabase credentials not found. Please check your environment variables or Streamlit secrets.")
    st.info("This app requires Supabase credentials to function. Please set up your credentials and try again.")
    st.stop()  # This will prevent the rest of the app from running

try:
    # Initialize Supabase client with error handling
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ Failed to connect to Supabase: {str(e)}")
    st.info("Please check your credentials and make sure your Supabase project is running.")
    st.stop()

# Main app title
st.title("⚡ Utility Rate Analysis Tool")

# Create tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["Bill Estimation", "Rate Comparison", "Schedule Browser"])

# Tab 1: Bill Estimation Tool
with tab1:
    st.header("Electric Bill Estimation Tool")
    st.markdown("Estimate your electric bill based on your usage and utility rate schedule.")
    
    # Step 1: State Selection
    # Get states that have utilities with schedules
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
            st.stop()
            
        selected_state = st.selectbox("Select State", [""] + states, index=0)
    except Exception as e:
        st.error(f"Error loading states: {str(e)}")
        selected_state = ""
    
    # Step 2: Utility Selection (only show if state is selected)
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
                
                selected_utility = st.selectbox("Select Utility", [""] + utility_names, index=0)
                
                if selected_utility:
                    selected_utility_id = utilities_dict[selected_utility]
        except Exception as e:
            st.error(f"Error loading utilities: {str(e)}")
    
    # Step 3: Schedule Selection (only show if utility is selected)
    selected_schedule = None
    selected_schedule_id = None
    
    if selected_utility_id:
        try:
            schedules_response = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName, ScheduleDescription").eq("UtilityID", selected_utility_id).execute()
            schedules_data = schedules_response.data
            
            if not schedules_data:
                st.warning(f"No rate schedules found for {selected_utility}.")
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
                
                selected_schedule_display = st.selectbox("Select Rate Schedule", [""] + schedule_display_options, index=0)
                
                if selected_schedule_display:
                    selected_schedule_id = schedule_options[selected_schedule_display]
                    selected_schedule = selected_schedule_display
        except Exception as e:
            st.error(f"Error loading schedules: {str(e)}")
    
    # Step 4: Check if selected schedule has various charge components
    has_demand_charges = False
    has_energy_charges = False
    has_reactive_demand = False
    has_tou_energy = False
    tou_periods = []
    
    if selected_schedule_id:
        try:
            # Check if there are demand charges for this schedule
            demand_response = supabase.from_("Demand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            demand_time_response = supabase.from_("DemandTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            
            has_demand_charges = (
                len(demand_response.data) > 0 or 
                len(demand_time_response.data) > 0 or 
                len(incremental_demand_response.data) > 0
            )
            
            # Check if there are energy charges for this schedule
            energy_response = supabase.from_("Energy_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            energy_time_response = supabase.from_("EnergyTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            
            has_energy_charges = (
                len(energy_response.data) > 0 or 
                len(energy_time_response.data) > 0 or 
                len(incremental_energy_response.data) > 0
            )
            
            # Check for reactive demand charges
            reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            has_reactive_demand = len(reactive_demand_response.data) > 0
            
            # Check for time-of-use energy periods
            if len(energy_time_response.data) > 0:
                has_tou_energy = True
                tou_response = supabase.from_("EnergyTime_Table").select("Description, TimeOfDay").eq("ScheduleID", selected_schedule_id).execute()
                
                # Get unique TOU periods
                tou_periods = []
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
            
        except Exception as e:
            st.error(f"Error checking rate components: {str(e)}")
    
    # Step 5: Usage Inputs (only show if schedule is selected)
    usage_kwh = None
    usage_by_tou = {}
    demand_kw = None
    demand_by_tou = {}
    power_factor = 0.9  # Default power factor
    billing_month = None
    
    if selected_schedule_id:
        st.subheader("Enter Usage Information")
        
        # Billing period (month)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        current_month_index = datetime.now().month - 1  # 0-based index
        billing_month = st.selectbox("Billing Month", months, index=current_month_index)
        
        # Always ask for energy usage (kWh)
        if has_energy_charges:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                usage_kwh = st.number_input("Total Energy Usage (kWh)", min_value=0.0, step=10.0)
            
            # Time-of-use energy inputs
            if has_tou_energy and tou_periods:
                st.subheader("Time-of-Use Energy Breakdown")
                st.info("Enter your energy usage for each time period. The total should equal your total energy usage.")
                
                # Create two columns for TOU inputs
                tou_cols = st.columns(2)
                col_idx = 0
                
                remaining_kwh = usage_kwh
                for i, period in enumerate(tou_periods):
                    with tou_cols[col_idx]:
                        if i == len(tou_periods) - 1:  # Last period
                            # For the last period, show the remaining amount
                            st.text(f"{period['display']}")
                            st.text(f"Remaining: {remaining_kwh:.1f} kWh")
                            usage_by_tou[period['display']] = remaining_kwh
                        else:
                            period_usage = st.number_input(
                                f"{period['display']} (kWh)", 
                                min_value=0.0, 
                                max_value=usage_kwh if usage_kwh else 0.0,
                                step=1.0,
                                key=f"tou_energy_{i}"
                            )
                            usage_by_tou[period['display']] = period_usage
                            remaining_kwh -= period_usage
                    
                    # Alternate columns
                    col_idx = (col_idx + 1) % 2
                
                # Show warning if the sum doesn't match the total
                sum_tou = sum(usage_by_tou.values())
                if abs(sum_tou - usage_kwh) > 0.01 and usage_kwh > 0:
                    st.warning(f"Time-of-use breakdown ({sum_tou:.1f} kWh) doesn't match your total energy usage ({usage_kwh:.1f} kWh). Please adjust your inputs.")
        
        # Only ask for demand if the schedule has demand charges
        if has_demand_charges:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                demand_kw = st.number_input("Peak Demand (kW)", min_value=0.0, step=1.0)
            
            # If reactive demand is applicable, show power factor input
            if has_reactive_demand:
                with col2:
                    power_factor = st.slider(
                        "Power Factor", 
                        min_value=0.7, 
                        max_value=1.0, 
                        value=0.9, 
                        step=0.01,
                        help="Power factor is the ratio of real power to apparent power in an electrical circuit."
                    )
    
    # Step 6: Calculate button
    if selected_schedule_id and ((has_energy_charges and usage_kwh is not None) or not has_energy_charges) and ((has_demand_charges and demand_kw is not None) or not has_demand_charges):
        if st.button("Calculate Bill Estimate"):
            st.subheader("Bill Estimate")
            
            # 1. Get service charges
            service_charge = 0.0
            service_charge_breakdown = []
            
            try:
                service_charge_response = supabase.from_("ServiceCharge_Table").select("Description, Rate, ChargeUnit").eq("ScheduleID", selected_schedule_id).execute()
                
                for charge in service_charge_response.data:
                    rate = float(charge.get("Rate", 0))
                    description = charge.get("Description", "Service Charge")
                    unit = charge.get("ChargeUnit", "")
                    
                    service_charge += rate
                    service_charge_breakdown.append({
                        "Description": f"{description} ({unit})",
                        "Amount": rate
                    })
            except Exception as e:
                st.warning(f"Error getting service charges: {str(e)}")
            
            # 2. Calculate energy charges
            energy_charge = 0.0
            energy_charges_breakdown = []
            
            if has_energy_charges and usage_kwh:
                try:
                    # Check standard energy rates (Energy_Table)
                    energy_response = supabase.from_("Energy_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    for rate in energy_response.data:
                        rate_kwh = float(rate.get("RatekWh", 0))
                        description = rate.get("Description", "Energy Charge")
                        min_v = float(rate.get("MinkV", 0))
                        max_v = rate.get("MaxkV")
                        max_v = float(max_v) if max_v is not None else float('inf')
                        determinant = rate.get("Determinant", "")
                        
                        # Check if usage falls within this rate's range
                        if min_v <= usage_kwh <= max_v:
                            charge_amount = rate_kwh * usage_kwh
                            energy_charge += charge_amount
                            energy_charges_breakdown.append({
                                "Description": f"{description} ({rate_kwh:.4f} $/kWh)",
                                "Amount": charge_amount
                            })
                    
                    # Check incremental/tiered energy rates (IncrementalEnergy_Table)
                    incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if incremental_energy_response.data:
                        # Sort tiers by StartkWh to ensure proper order
                        tiers = sorted(incremental_energy_response.data, key=lambda x: float(x.get("StartkWh", 0)))
                        
                        remaining_kwh = usage_kwh
                        for tier in tiers:
                            rate_kwh = float(tier.get("RatekWh", 0))
                            start_kwh = float(tier.get("StartkWh", 0))
                            end_kwh = tier.get("EndkWh")
                            end_kwh = float(end_kwh) if end_kwh is not None else float('inf')
                            description = tier.get("Description", "Tiered Energy Charge")
                            season = tier.get("Season", "")
                            
                            # Check if we're in the right season (if specified)
                            if season and billing_month:
                                # Simple season check - can be enhanced for more complex seasonal definitions
                                summer_months = ["June", "July", "August", "September"]
                                winter_months = ["December", "January", "February", "March"]
                                
                                if (season.lower() == "summer" and billing_month not in summer_months) or \
                                   (season.lower() == "winter" and billing_month not in winter_months):
                                    continue
                            
                            # Calculate tier usage and charge
                            tier_usage = min(max(0, remaining_kwh - start_kwh), end_kwh - start_kwh)
                            
                            if tier_usage > 0:
                                tier_charge = tier_usage * rate_kwh
                                energy_charge += tier_charge
                                energy_charges_breakdown.append({
                                    "Description": f"{description} ({start_kwh}-{end_kwh if end_kwh != float('inf') else '∞'} kWh @ {rate_kwh:.4f} $/kWh)",
                                    "Amount": tier_charge
                                })
                                
                                remaining_kwh -= tier_usage
                                if remaining_kwh <= 0:
                                    break
                    
                    # Check time-of-use energy rates (EnergyTime_Table)
                    energy_time_response = supabase.from_("EnergyTime_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if energy_time_response.data and len(energy_time_response.data) > 0:
                        # If user specified TOU breakdown, use it
                        if usage_by_tou:
                            for period in energy_time_response.data:
                                rate_kwh = float(period.get("RatekWh", 0))
                                description = period.get("Description", "Time-of-Use Energy")
                                time_of_day = period.get("TimeOfDay", "")
                                season = period.get("Season", "")
                                
                                # Format period key to match usage_by_tou keys
                                period_key = f"{description} ({time_of_day})"
                                
                                # Check if we're in the right season (if specified)
                                if season and billing_month:
                                    # Simple season check
                                    summer_months = ["June", "July", "August", "September"]
                                    winter_months = ["December", "January", "February", "March"]
                                    
                                    if (season.lower() == "summer" and billing_month not in summer_months) or \
                                       (season.lower() == "winter" and billing_month not in winter_months):
                                        continue
                                
                                # Use the specified usage for this period if available
                                period_usage = usage_by_tou.get(period_key, 0)
                                
                                if period_usage > 0:
                                    period_charge = rate_kwh * period_usage
                                    energy_charge += period_charge
                                    energy_charges_breakdown.append({
                                        "Description": f"{description} ({time_of_day}, {rate_kwh:.4f} $/kWh)",
                                        "Amount": period_charge
                                    })
                        else:
                            # If no TOU breakdown provided, distribute usage evenly
                            time_periods = energy_time_response.data
                            num_periods = len(time_periods)
                            usage_per_period = usage_kwh / num_periods if num_periods > 0 else 0
                            
                            for period in time_periods:
                                rate_kwh = float(period.get("RatekWh", 0))
                                description = period.get("Description", "Time-of-Use Energy")
                                time_of_day = period.get("TimeOfDay", "")
                                season = period.get("Season", "")
                                
                                # Check if we're in the right season (if specified)
                                if season and billing_month:
                                    # Simple season check
                                    summer_months = ["June", "July", "August", "September"]
                                    winter_months = ["December", "January", "February", "March"]
                                    
                                    if (season.lower() == "summer" and billing_month not in summer_months) or \
                                       (season.lower() == "winter" and billing_month not in winter_months):
                                        continue
                                
                                period_charge = rate_kwh * usage_per_period
                                energy_charge += period_charge
                                energy_charges_breakdown.append({
                                    "Description": f"{description} ({time_of_day}, {rate_kwh:.4f} $/kWh)",
                                    "Amount": period_charge
                                })
                    
                except Exception as e:
                    st.warning(f"Error calculating energy charges: {str(e)}")
            
            # 3. Calculate demand charges
            demand_charge = 0.0
            demand_charges_breakdown = []
            
            if has_demand_charges and demand_kw:
                try:
                    # Check standard demand rates (Demand_Table)
                    demand_response = supabase.from_("Demand_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    for rate in demand_response.data:
                        rate_kw = float(rate.get("RatekW", 0))
                        description = rate.get("Description", "Demand Charge")
                        min_kv = float(rate.get("MinkV", 0))
                        max_kv = rate.get("MaxkV")
                        max_kv = float(max_kv) if max_kv is not None else float('inf')
                        determinant = rate.get("Determinant", "")
                        
                        # Check if demand falls within this rate's range
                        if min_kv <= demand_kw <= max_kv:
                            charge_amount = rate_kw * demand_kw
                            demand_charge += charge_amount
                            demand_charges_breakdown.append({
                                "Description": f"{description} ({rate_kw:.2f} $/kW)",
                                "Amount": charge_amount
                            })
                    
                    # Check time-of-use demand rates (DemandTime_Table)
                    demand_time_response = supabase.from_("DemandTime_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if demand_time_response.data and len(demand_time_response.data) > 0:
                        # For simplicity, we'll use the highest demand rate for now
                        # In a real implementation, you'd need user input for demand during specific time periods
                        
                        highest_rate = max(demand_time_response.data, key=lambda x: float(x.get("RatekW", 0)))
                        rate_kw = float(highest_rate.get("RatekW", 0))
                        description = highest_rate.get("Description", "Time-of-Use Demand")
                        time_of_day = highest_rate.get("TimeOfDay", "")
                        season = highest_rate.get("Season", "")
                        
                        # Check if we're in the right season (if specified)
                        if not season or not billing_month or \
                           (season.lower() == "summer" and billing_month in ["June", "July", "August", "September"]) or \
                           (season.lower() == "winter" and billing_month in ["December", "January", "February", "March"]):
                            
                            period_charge = rate_kw * demand_kw
                            demand_charge += period_charge
                            demand_charges_breakdown.append({
                                "Description": f"{description} ({time_of_day}, {rate_kw:.2f} $/kW)",
                                "Amount": period_charge
                            })
                    
                    # Check incremental/tiered demand rates (IncrementalDemand_Table)
                    incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if incremental_demand_response.data:
                        # Sort tiers by StepMin to ensure proper order
                        tiers = sorted(incremental_demand_response.data, key=lambda x: float(x.get("StepMin", 0)))
                        
                        remaining_kw = demand_kw
                        for tier in tiers:
                            rate_kw = float(tier.get("RatekW", 0))
                            step_min = float(tier.get("StepMin", 0))
                            step_max = tier.get("StepMax")
                            step_max = float(step_max) if step_max is not None else float('inf')
                            description = tier.get("Description", "Tiered Demand Charge")
                            
                            # Calculate tier usage and charge
                            tier_usage = min(max(0, remaining_kw - step_min), step_max - step_min)
                            
                            if tier_usage > 0:
                                tier_charge = tier_usage * rate_kw
                                demand_charge += tier_charge
                                demand_charges_breakdown.append({
                                    "Description": f"{description} ({step_min}-{step_max if step_max != float('inf') else '∞'} kW @ {rate_kw:.2f} $/kW)",
                                    "Amount": tier_charge
                                })
                                
                                remaining_kw -= tier_usage
                                if remaining_kw <= 0:
                                    break
                    
                    # Check reactive demand charges (ReactiveDemand_Table)
                    reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if reactive_demand_response.data and demand_kw > 0:
                        # Calculate reactive demand based on power factor
                        # Formula: reactive_power = active_power * tan(acos(power_factor))
                        reactive_kvar = demand_kw * math.tan(math.acos(power_factor))
                        
                        for rate in reactive_demand_response.data:
                            rate_value = float(rate.get("Rate", 0))
                            min_val = float(rate.get("Min", 0))
                            max_val = rate.get("Max")
                            max_val = float(max_val) if max_val is not None else float('inf')
                            description = rate.get("Description", "Reactive Demand Charge")
                            
                            # Check if reactive demand falls within this rate's range
                            if min_val <= reactive_kvar <= max_val:
                                charge_amount = rate_value * reactive_kvar
                                demand_charge += charge_amount
                                demand_charges_breakdown.append({
                                    "Description": f"{description} ({rate_value:.2f} $/kVAR, PF={power_factor:.2f})",
                                    "Amount": charge_amount
                                })
                    
                except Exception as e:
                    st.warning(f"Error calculating demand charges: {str(e)}")
            
            # 4. Get other charges
            other_charges = 0.0
            other_charges_breakdown = []
            
            try:
                other_charges_response = supabase.from_("OtherCharges_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                
                for charge in other_charges_response.data:
                    charge_type = float(charge.get("ChargeType", 0))
                    description = charge.get("Description", "Other Charge")
                    charge_unit = charge.get("ChargeUnit", "")
                    
                    other_charges += charge_type
                    other_charges_breakdown.append({
                        "Description": f"{description} ({charge_unit})",
                        "Amount": charge_type
                    })
            except Exception as e:
                st.warning(f"Error calculating other charges: {str(e)}")
            
            # 5. Calculate taxes
            tax_amount = 0.0
            subtotal = service_charge + energy_charge + demand_charge + other_charges
            tax_breakdown = []
            
            try:
                tax_response = supabase.from_("TaxInfo_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                
                for tax in tax_response.data:
                    tax_rate = float(tax.get("Per_cent", 0))
                    tax_desc = tax.get("Type", "Tax")
                    city = tax.get("City", "")
                    basis = tax.get("Basis", "")
                    
                    # Add city info to description if available
                    if city:
                        tax_desc = f"{tax_desc} ({city})"
                    
                    # Calculate tax amount based on percentage
                    amount = subtotal * (tax_rate / 100)
                    tax_amount += amount
                    tax_breakdown.append({
                        "Description": f"{tax_desc} ({tax_rate}%)",
                        "Amount": amount
                    })
            except Exception as e:
                st.warning(f"Error calculating taxes: {str(e)}")
            
            # Calculate total bill
            total_bill = subtotal + tax_amount
            
            # Display the bill breakdown
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Bill Summary")
                st.markdown(f"**Selected State:** {selected_state}")
                st.markdown(f"**Selected Utility:** {selected_utility}")
                st.markdown(f"**Selected Schedule:** {selected_schedule}")
                st.markdown(f"**Billing Month:** {billing_month}")
                
                if has_energy_charges:
                    st.markdown(f"**Energy Usage:** {usage_kwh} kWh")
                if has_demand_charges:
                    st.markdown(f"**Peak Demand:** {demand_kw} kW")
                if has_reactive_demand:
                    st.markdown(f"**Power Factor:** {power_factor}")
                    
                # Add a simple pie chart for visualization
                if has_energy_charges or has_demand_charges:
                    st.markdown("### Bill Visualization")
                    
                    # Prepare data for pie chart
                    chart_data = {
                        'Category': [],
                        'Amount': []
                    }
                    
                    # Add service charge
                    if service_charge > 0:
                        chart_data['Category'].append('Service Charge')
                        chart_data['Amount'].append(service_charge)
                    
                    # Add energy charges
                    if energy_charge > 0:
                        chart_data['Category'].append('Energy Charges')
                        chart_data['Amount'].append(energy_charge)
                    
                    # Add demand charges
                    if demand_charge > 0:
                        chart_data['Category'].append('Demand Charges')
                        chart_data['Amount'].append(demand_charge)
                    
                    # Add other charges as a single item
                    if other_charges > 0:
                        chart_data['Category'].append('Other Charges')
                        chart_data['Amount'].append(other_charges)
                    
                    # Add taxes as a single item
                    if tax_amount > 0:
                        chart_data['Category'].append('Taxes')
                        chart_data['Amount'].append(tax_amount)
                    
                    # Create DataFrame
                    chart_df = pd.DataFrame(chart_data)
                    
                    # Create pie chart
                    fig, ax = plt.subplots(figsize=(4, 4))
                    ax.pie(chart_df['Amount'], labels=chart_df['Category'], autopct='%1.1f%%')
                    ax.set_title('Bill Composition')
                    st.pyplot(fig)
            
            with col2:
                st.markdown("### Charges Breakdown")
                
                # Create a dataframe for the bill breakdown
                bill_items = []
                
                # Add service charges
                for charge in service_charge_breakdown:
                    bill_items.append(charge)
                
                # Add detailed energy charges breakdown
                if has_energy_charges:
                    if energy_charges_breakdown:
                        for charge in energy_charges_breakdown:
                            bill_items.append(charge)
                    else:
                        bill_items.append({"Description": "Energy Charges", "Amount": energy_charge})
                
                # Add detailed demand charges breakdown
                if has_demand_charges:
                    if demand_charges_breakdown:
                        for charge in demand_charges_breakdown:
                            bill_items.append(charge)
                    else:
                        bill_items.append({"Description": "Demand Charges", "Amount": demand_charge})
                
                # Add other charges
                for charge in other_charges_breakdown:
                    bill_items.append(charge)
                
                # Add subtotal line
                bill_items.append({"Description": "Subtotal", "Amount": subtotal})
                
                # Add taxes
                for tax in tax_breakdown:
                    bill_items.append({"Description": tax["Description"], "Amount": tax["Amount"]})
                
                # Add total line
                bill_items.append({"Description": "Total", "Amount": total_bill})
                
                # Convert to dataframe and display
                bill_df = pd.DataFrame(bill_items)
                
                if not bill_df.empty:
                    # Format the Amount column with currency formatting
                    bill_df["Amount"] = bill_df["Amount"].map("${:.2f}".format)
                    
                    # Display the dataframe without index
                    st.table(bill_df)
                else:
                    st.warning("No charges found for this schedule.")
            
            # Display a note about the bill estimate
            st.info("Note: This is an estimate based on the selected rate schedule and may not reflect all potential charges or adjustments.")
            
            # Export option
            if st.button("Export Bill Estimate to CSV"):
                csv = bill_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"{selected_utility}_{selected_schedule}_bill_estimate.csv",
                    mime="text/csv"
                )

# Tab 2: Rate Comparison (placeholder for future implementation)
with tab2:
    st.header("Rate Schedule Comparison")
    st.info("This feature will allow you to compare different rate schedules. Coming soon!")

# Tab 3: Schedule Browser (placeholder for future implementation)
with tab3:
    st.header("Utility Rate Schedule Browser")
    st.info("This feature will allow you to browse through rate schedules. Coming soon!")
