import streamlit as st
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import math
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="Utility Bill Estimator",
    page_icon="⚡",
    layout="wide"
)

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Helper Functions for Bill Calculation
def is_applicable(record, voltage=None):
    """Determine if a rate record is applicable based on voltage and other criteria"""
    min_kv = record.get('MinKV')
    max_kv = record.get('MaxKV')
    
    # Check if this record has voltage constraints
    if min_kv is not None and max_kv is not None and voltage is not None:
        if not (min_kv <= voltage <= max_kv):
            return False
    
    # Check if record is pending (not yet active)
    pending = record.get('Pending', False)
    if pending:
        return False
        
    return True

def get_current_season():
    """Get the current season based on month"""
    current_month = datetime.now().month
    
    # Simple seasonal mapping - can be expanded for more detailed seasonal definitions
    if 3 <= current_month <= 5:
        return "Spring"
    elif 6 <= current_month <= 8:
        return "Summer"
    elif 9 <= current_month <= 11:
        return "Fall"
    else:
        return "Winter"

def is_in_season(record):
    """Check if a record is applicable for the current season"""
    season = record.get('Season')
    if not season:
        return True  # No season specified, always applicable
        
    current_season = get_current_season()
    return season.lower() == current_season.lower()

def is_in_date_range(record):
    """Check if current date is within record's date range"""
    start_date = record.get('StartDate')
    end_date = record.get('EndDate')
    
    if not start_date or not end_date:
        return True  # No date range specified, always applicable
    
    # Convert to datetime objects if they're strings
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
    current_date = datetime.now()
    return start_date <= current_date <= end_date

def estimate_time_distribution(total_usage, time_entries):
    """
    Estimate usage distribution across different time periods
    without actual hourly data.
    """
    # Simple distribution logic - divide usage proportionally
    # This could be enhanced with more sophisticated load profiling
    
    # If no time entries, return all usage in one entry
    if not time_entries:
        return [{"usage": total_usage, "label": "All Hours"}]
    
    # Count total hours covered
    total_hours = 0
    for entry in time_entries:
        # Get time period definition
        start_time = entry.get('StartTime')
        end_time = entry.get('EndTime')
        
        # Default to full day if not specified
        if not start_time or not end_time:
            hours = 24
        else:
            # Parse times (assuming HH:MM format)
            if isinstance(start_time, str) and isinstance(end_time, str):
                start_hour = int(start_time.split(':')[0])
                end_hour = int(end_time.split(':')[0])
                hours = end_hour - start_hour
                if hours <= 0:  # Handle overnight periods
                    hours += 24
            else:
                hours = 24  # Default if time format is unexpected
                
        total_hours += hours
    
    # Distribute usage based on hours
    distributed_usage = []
    
    for entry in time_entries:
        start_time = entry.get('StartTime', '00:00')
        end_time = entry.get('EndTime', '24:00')
        
        if isinstance(start_time, str) and isinstance(end_time, str):
            start_hour = int(start_time.split(':')[0])
            end_hour = int(end_time.split(':')[0])
            hours = end_hour - start_hour
            if hours <= 0:
                hours += 24
        else:
            hours = 24
        
        # Calculate proportion of usage for this time period
        proportion = hours / total_hours if total_hours > 0 else 1
        period_usage = total_usage * proportion
        
        distributed_usage.append({
            "usage": period_usage,
            "hours": hours,
            "label": f"{start_time}-{end_time}"
        })
    
    return distributed_usage

def calculate_incremental_charges(usage, incremental_entries, rate_field="RatekWh"):
    """Calculate charges for tiered/incremental rate structures"""
    total_charge = 0
    remaining_usage = usage
    
    # Sort entries by StartKWh or StepMin (ascending)
    sort_field = 'StartKWh' if 'StartKWh' in incremental_entries[0] else 'StepMin'
    sorted_entries = sorted(incremental_entries, key=lambda x: x.get(sort_field, 0))
    
    for i, entry in enumerate(sorted_entries):
        # Get tier boundaries
        if 'StartKWh' in entry and 'EndKWh' in entry:
            start = entry.get('StartKWh', 0)
            end = entry.get('EndKWh')
        else:
            start = entry.get('StepMin', 0)
            end = entry.get('StepMax')
        
        # Calculate usage in this tier
        if end is None:  # Last tier
            tier_usage = remaining_usage
        else:
            tier_usage = min(remaining_usage, end - start)
        
        if tier_usage <= 0:
            break
            
        # Apply rate to this tier
        rate = entry.get(rate_field, 0)
        tier_charge = tier_usage * rate
        total_charge += tier_charge
        
        # Update remaining usage
        remaining_usage -= tier_usage
        if remaining_usage <= 0:
            break
    
    return total_charge

def calculate_bill(schedule_id, usage_kwh, demand_kw, billing_days, voltage):
    """Calculate the bill based on user inputs"""
    try:
        # Initialize charge components
        charges = {}
        detailed_breakdown = {}
        
        # 1. SERVICE CHARGES
        service_charges = supabase.table("ServiceCharge_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        service_total = 0
        
        for charge in service_charges:
            if not is_applicable(charge, voltage):
                continue
                
            rate = charge.get('Rate', 0)
            if rate is None:
                rate = 0
                
            charge_unit = charge.get('ChargeUnit', 'per_month')
            
            # Apply rate based on charge unit
            if charge_unit == 'per_day':
                service_total += rate * billing_days
            elif charge_unit == 'per_bill':
                service_total += rate  # Just apply once per bill
            else:  # Default to monthly
                service_total += rate
        
        charges['ServiceCharge'] = service_total
        detailed_breakdown['Service Charges'] = service_total
        
        # 2. ENERGY CHARGES
        # Standard energy charges
        energy_charges = supabase.table("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        energy_total = 0
        
        for charge in energy_charges:
            if not is_applicable(charge, voltage) or not is_in_season(charge) or not is_in_date_range(charge):
                continue
                
            rate = charge.get('RatekWh', 0)
            if rate is None:
                rate = 0
                
            energy_total += rate * usage_kwh
        
        # Incremental/tiered energy charges
        inc_energy_charges = supabase.table("IncrementalEnergy_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        
        if inc_energy_charges:
            applicable_entries = [charge for charge in inc_energy_charges 
                                if is_applicable(charge, voltage) and is_in_season(charge) and is_in_date_range(charge)]
            if applicable_entries:
                # Replace simple multiplication with tiered calculation
                energy_total = calculate_incremental_charges(usage_kwh, applicable_entries, "RatekWh")
        
        # Time-of-use energy charges
        tou_energy_charges = supabase.table("EnergyTime_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        tou_energy_total = 0
        
        if tou_energy_charges:
            applicable_entries = [charge for charge in tou_energy_charges 
                                 if is_applicable(charge, voltage) and is_in_season(charge) and is_in_date_range(charge)]
            
            if applicable_entries:
                # Distribute usage across time periods
                distributed_usage = estimate_time_distribution(usage_kwh, applicable_entries)
                
                # Apply rates to each time period
                for i, period in enumerate(distributed_usage):
                    if i < len(applicable_entries):
                        rate = applicable_entries[i].get('RatekWh', 0)
                        if rate is None:
                            rate = 0
                        tou_energy_total += period['usage'] * rate
        
        # If we have TOU charges, use them instead of standard energy charges
        if tou_energy_total > 0:
            energy_total = tou_energy_total
        
        charges['Energy'] = energy_total
        detailed_breakdown['Energy Charges'] = energy_total
        
        # 3. DEMAND CHARGES
        # Standard demand charges
        demand_charges = supabase.table("Demand_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        demand_total = 0
        
        for charge in demand_charges:
            if not is_applicable(charge, voltage) or not is_in_season(charge) or not is_in_date_range(charge):
                continue
                
            rate = charge.get('RatekW', 0)
            if rate is None:
                rate = 0
                
            demand_total += rate * demand_kw
        
        # Incremental/tiered demand charges
        inc_demand_charges = supabase.table("IncrementalDemand_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        
        if inc_demand_charges:
            applicable_entries = [charge for charge in inc_demand_charges 
                                if is_applicable(charge, voltage) and is_in_season(charge) and is_in_date_range(charge)]
            if applicable_entries:
                # Replace simple multiplication with tiered calculation
                demand_total = calculate_incremental_charges(demand_kw, applicable_entries, "RatekW")
        
        # Time-of-use demand charges
        tou_demand_charges = supabase.table("DemandTime_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        tou_demand_total = 0
        
        if tou_demand_charges:
            applicable_entries = [charge for charge in tou_demand_charges 
                                 if is_applicable(charge, voltage) and is_in_season(charge) and is_in_date_range(charge)]
            
            if applicable_entries:
                # For simplicity, assume demand is the same across all time periods
                # A more sophisticated approach would model demand profiles
                for entry in applicable_entries:
                    rate = entry.get('RatekW', 0)
                    if rate is None:
                        rate = 0
                    tou_demand_total += rate * demand_kw
        
        # Reactive demand charges
        reactive_demand_charges = supabase.table("ReactiveDemand_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        reactive_demand_total = 0
        
        if reactive_demand_charges and demand_kw > 0:  # Only calculate if there's actual demand
            # Typical power factor assumption (0.9)
            power_factor = 0.9
            kvar_demand = demand_kw * math.tan(math.acos(power_factor))
            
            for charge in reactive_demand_charges:
                if not is_applicable(charge, voltage):
                    continue
                    
                rate = charge.get('RatekVAR', 0)
                if rate is None:
                    rate = 0
                    
                reactive_demand_total += rate * kvar_demand
        
        # If we have TOU demand charges, use them instead of standard demand charges
        if tou_demand_total > 0:
            demand_total = tou_demand_total
        
        # Add reactive demand to total demand charges
        demand_total += reactive_demand_total
        
        charges['Demand'] = demand_total
        detailed_breakdown['Demand Charges'] = demand_total
        
        # 4. OTHER CHARGES
        other_charges = supabase.table("OtherCharges_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        other_total = 0
        
        for charge in other_charges:
            if not is_applicable(charge, voltage):
                continue
                
            # Determine charge amount based on ChargeType and ChargeUnit
            charge_type = charge.get('ChargeType', '')
            charge_unit = charge.get('ChargeUnit', '')
            rate = charge.get('Rate', 0)
            
            if rate is None:
                rate = 0
                
            if charge_unit == 'per_kwh':
                other_total += rate * usage_kwh
            elif charge_unit == 'per_kw':
                other_total += rate * demand_kw
            elif charge_unit == 'per_day':
                other_total += rate * billing_days
            else:  # Flat rate or per_month
                other_total += rate
        
        charges['OtherCharges'] = other_total
        detailed_breakdown['Other Charges'] = other_total
        
        # Calculate subtotal before percentages and taxes
        subtotal = sum(charges.values())
        
        # 5. PERCENTAGE-BASED CHARGES
        percentage_charges = supabase.table("Percentages_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        percentage_total = 0
        
        for charge in percentage_charges:
            if not is_applicable(charge, voltage):
                continue
                
            percentage = charge.get('PercentageRate', 0)
            if percentage is None:
                percentage = 0
                
            basis = charge.get('Basis', 'all')
            
            # Determine which charges to apply percentage to
            if basis == 'energy_only':
                base_amount = charges.get('Energy', 0)
            elif basis == 'demand_only':
                base_amount = charges.get('Demand', 0)
            elif basis == 'service_only':
                base_amount = charges.get('ServiceCharge', 0)
            else:  # Apply to all charges
                base_amount = subtotal
                
            percentage_total += (percentage / 100) * base_amount
        
        charges['PercentageCharges'] = percentage_total
        detailed_breakdown['Percentage-based Charges'] = percentage_total
        
        # 6. TAXES
        taxes = supabase.table("TaxInfo_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        tax_total = 0
        
        for tax in taxes:
            if not is_applicable(tax, voltage):
                continue
                
            tax_rate = tax.get('TaxRate', 0)
            if tax_rate is None:
                tax_rate = 0
                
            tax_basis = tax.get('Basis', 'all')
            
            # Determine which charges to apply tax to
            if tax_basis == 'energy_only':
                base_amount = charges.get('Energy', 0)
            elif tax_basis == 'demand_only':
                base_amount = charges.get('Demand', 0)
            elif tax_basis == 'service_only':
                base_amount = charges.get('ServiceCharge', 0)
            elif tax_basis == 'subtotal':
                base_amount = subtotal
            else:  # Apply to all charges including percentages
                base_amount = subtotal + percentage_total
                
            tax_total += (tax_rate / 100) * base_amount
        
        charges['Taxes'] = tax_total
        detailed_breakdown['Taxes'] = tax_total
        
        # 7. TOTAL BILL CALCULATION
        total_cost = subtotal + percentage_total + tax_total
        
        return {
            "breakdown": detailed_breakdown,
            "total_cost": total_cost
        }
    except Exception as e:
        st.error(f"Error in calculation: {str(e)}")
        return None

# Data Fetching Functions
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_all_states():
    """Get all 50 US states for dropdown"""
    try:
        all_states = [
            "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DE", "FL", 
            "GA", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", 
            "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", 
            "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", 
            "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", 
            "WV", "WY"
        ]
        return sorted(all_states)
    except Exception as e:
        st.error(f"Error fetching states: {str(e)}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_utilities_by_state(state):
    """Get utilities filtered by selected state"""
    try:
        # Get all utilities in the selected state
        utilities = supabase.table("Utility").select("UtilityID, UtilityName, State").eq("State", state).execute().data
        
        # Check if we found any utilities for this state
        if not utilities:
            return {"no_utilities": True, "message": f"No utilities found for {state}"}
        
        # Get all utilities that have at least one schedule
        utilities_with_schedules = []
        
        for utility in utilities:
            # Check if this utility has any schedules
            utility_id = utility["UtilityID"]
            schedules = supabase.table("Schedule_Table").select("ScheduleID").eq("UtilityID", utility_id).execute().data
            
            if schedules and len(schedules) > 0:
                utilities_with_schedules.append({
                    "UtilityID": utility["UtilityID"],
                    "UtilityName": utility["UtilityName"],
                    "has_schedules": True
                })
            else:
                utilities_with_schedules.append({
                    "UtilityID": utility["UtilityID"],
                    "UtilityName": utility["UtilityName"],
                    "has_schedules": False
                })
        
        # If no utilities have schedules, return a message
        if all(not u.get("has_schedules", False) for u in utilities_with_schedules):
            return {
                "no_schedules": True, 
                "utilities": utilities_with_schedules,
                "message": f"No schedule data available for utilities in {state}"
            }
        
        return utilities_with_schedules
    except Exception as e:
        st.error(f"Error fetching utilities: {str(e)}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_schedules(utility_id):
    """Get schedules for a selected utility"""
    try:
        result = supabase.table("Schedule_Table") \
            .select("ScheduleID, ScheduleName, ScheduleDescription") \
            .eq("UtilityID", utility_id) \
            .execute()
        return result.data
    except Exception as e:
        st.error(f"Error fetching schedules: {str(e)}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_schedule_details(schedule_id):
    """Get schedule details"""
    try:
        schedule = supabase.table("Schedule_Table").select("*").eq("ScheduleID", schedule_id).single().execute().data

        detail_tables = [
            "DemandTime_Table",
            "Demand_Table",
            "EnergyTime_Table",
            "Energy_Table",
            "IncrementalDemand_Table",
            "IncrementalEnergy_Table",
            "ReactiveDemand_Table",
            "ServiceCharge_Table",
            "OtherCharges_Table",
            "TaxInfo_Table",
            "Percentages_Table",
            "Notes_Table"
        ]

        details = {}
        present_tables = []

        for table in detail_tables:
            res = supabase.table(table).select("*").eq("ScheduleID", schedule_id).execute()
            if res.data:
                details[table] = res.data
                present_tables.append(table)

        return {
            "schedule": schedule,
            "present_tables": present_tables,
            "details": details
        }
    except Exception as e:
        st.error(f"Error fetching schedule details: {str(e)}")
        return None

# Main app
def main():
    # Sidebar for navigation
    st.sidebar.title("⚡ Utility Bill Estimator")
    
    # Navigation
    page = st.sidebar.radio("Navigation", ["Bill Estimator", "Browse Schedules", "Compare Rates"])
    
    if page == "Bill Estimator":
        show_bill_estimator()
    elif page == "Browse Schedules":
        show_browse_schedules()
    elif page == "Compare Rates":
        show_compare_rates()

def show_bill_estimator():
    st.title("⚡ Utility Bill Estimator")
    st.write("Estimate your utility bill based on usage, demand, and rate schedule.")
    
    # Set up columns for input
    col1, col2 = st.columns(2)
    
    with col1:
        # State selection
        states = get_all_states()
        selected_state = st.selectbox("Select State", states)
        
        # Utility selection
        if selected_state:
            utilities = get_utilities_by_state(selected_state)
            
            if isinstance(utilities, dict) and utilities.get("no_utilities"):
                st.warning(utilities.get("message", "No utilities found for this state."))
            elif isinstance(utilities, dict) and utilities.get("no_schedules"):
                utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities.get("utilities", [])]
                if utility_options:
                    utility_ids, utility_names = zip(*utility_options)
                    selected_utility_index = st.selectbox("Select Utility", range(len(utility_names)), format_func=lambda i: utility_names[i])
                    selected_utility_id = utility_ids[selected_utility_index]
                    st.warning(utilities.get("message", "No schedules available for this utility."))
                else:
                    st.warning("No utilities found with schedules.")
            else:
                # Filter out utilities with no schedules
                utilities_with_schedules = [u for u in utilities if u.get("has_schedules", False)]
                
                if not utilities_with_schedules:
                    st.warning(f"No utilities with rate schedules found for {selected_state}.")
                else:
                    utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities_with_schedules]
                    utility_ids, utility_names = zip(*utility_options)
                    selected_utility_index = st.selectbox("Select Utility", range(len(utility_names)), format_func=lambda i: utility_names[i])
                    selected_utility_id = utility_ids[selected_utility_index]
                    
                    # Schedule selection
                    schedules = get_schedules(selected_utility_id)
                    if schedules:
                        schedule_options = [(s["ScheduleID"], s["ScheduleName"]) for s in schedules]
                        schedule_ids, schedule_names = zip(*schedule_options)
                        selected_schedule_index = st.selectbox("Select Rate Schedule", range(len(schedule_names)), format_func=lambda i: schedule_names[i])
                        selected_schedule_id = schedule_ids[selected_schedule_index]
                    else:
                        st.warning("No rate schedules available for this utility.")
    
    with col2:
        # Usage inputs
        usage_kwh = st.number_input("Monthly Energy Usage (kWh)", min_value=0.0, value=1000.0, step=100.0)
        demand_kw = st.number_input("Monthly Demand (kW)", min_value=0.0, value=5.0, step=1.0)
        billing_days = st.number_input("Billing Days", min_value=1, value=30, step=1)
        voltage = st.number_input("Voltage (kV, optional)", min_value=0.0, value=None, step=1.0)
    
    # Calculate button
    calculate_pressed = st.button("Calculate Bill")
    
    if calculate_pressed and 'selected_schedule_id' in locals():
        with st.spinner("Calculating bill..."):
            result = calculate_bill(
                selected_schedule_id, 
                usage_kwh, 
                demand_kw, 
                billing_days, 
                voltage
            )
            
            if result:
                # Display results
                st.success(f"Total Estimated Bill: ${result['total_cost']:.2f}")
                
                # Breakdown of charges
                st.subheader("Bill Breakdown")
                breakdown = result["breakdown"]
                
                # Create a formatted table
                data = []
                for charge_type, amount in breakdown.items():
                    data.append([charge_type, f"${amount:.2f}"])
                
                # Display as a table
                st.table({"Charge Type": [item[0] for item in data], 
                         "Amount": [item[1] for item in data]})

def show_browse_schedules():
    st.title("Browse Rate Schedules")
    st.write("View detailed information about utility rate schedules.")
    
    # State selection
    states = get_all_states()
    selected_state = st.selectbox("Select State", states)
    
    # Utility selection
    if selected_state:
        utilities = get_utilities_by_state(selected_state)
        
        if isinstance(utilities, dict) and utilities.get("no_utilities"):
            st.warning(utilities.get("message", "No utilities found for this state."))
        elif isinstance(utilities, dict) and utilities.get("no_schedules"):
            utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities.get("utilities", [])]
            if utility_options:
                utility_ids, utility_names = zip(*utility_options)
                selected_utility_index = st.selectbox("Select Utility", range(len(utility_names)), format_func=lambda i: utility_names[i])
                selected_utility_id = utility_ids[selected_utility_index]
                st.warning(utilities.get("message", "No schedules available for this utility."))
            else:
                st.warning("No utilities found with schedules.")
        else:
            utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities]
            utility_ids, utility_names = zip(*utility_options)
            selected_utility_index = st.selectbox("Select Utility", range(len(utility_names)), format_func=lambda i: utility_names[i])
            selected_utility_id = utility_ids[selected_utility_index]
            
            # Schedule selection
            schedules = get_schedules(selected_utility_id)
            if schedules:
                schedule_options = [(s["ScheduleID"], s["ScheduleName"]) for s in schedules]
                schedule_ids, schedule_names = zip(*schedule_options)
                selected_schedule_index = st.selectbox("Select Rate Schedule", range(len(schedule_names)), format_func=lambda i: schedule_names[i])
                selected_schedule_id = schedule_ids[selected_schedule_index]
                
                # Show schedule details
                schedule_details = get_schedule_details(selected_schedule_id)
                
                if schedule_details:
                    st.subheader(f"Schedule: {schedule_names[selected_schedule_index]}")
                    
                    # Basic schedule info
                    schedule = schedule_details.get("schedule", {})
                    st.write(f"Description: {schedule.get('ScheduleDescription', 'N/A')}")
                    
                    # Display tables that are present for this schedule
                    present_tables = schedule_details.get("present_tables", [])
                    details = schedule_details.get("details", {})
                    
                    # Create expandable sections for each table type
                    table_display_names = {
                        "ServiceCharge_Table": "Service Charges",
                        "Energy_Table": "Energy Charges",
                        "Demand_Table": "Demand Charges",
                        "EnergyTime_Table": "Time-of-Use Energy Charges",
                        "DemandTime_Table": "Time-of-Use Demand Charges",
                        "IncrementalEnergy_Table": "Tiered Energy Charges",
                        "IncrementalDemand_Table": "Tiered Demand Charges",
                        "ReactiveDemand_Table": "Reactive Demand Charges",
                        "OtherCharges_Table": "Other Charges",
                        "TaxInfo_Table": "Taxes",
                        "Percentages_Table": "Percentage-based Charges",
                        "Notes_Table": "Notes"
                    }
                    
                    for table_name in present_tables:
                        display_name = table_display_names.get(table_name, table_name)
                        with st.expander(f"{display_name}"):
                            table_data = details.get(table_name, [])
                            
                            if table_data:
                                # Format the data for display
                                # Remove technical fields and rename for clarity
                                display_data = []
                                for row in table_data:
                                    clean_row = {k: v for k, v in row.items() 
                                                if k not in ["ScheduleID", "id"] and not k.startswith("created_")}
                                    display_data.append(clean_row)
                                
                                # Display as a table
                                if display_data:
                                    st.dataframe(display_data)
                            else:
                                st.write("No data available.")
                else:
                    st.warning("No schedule details available.")
            else:
                st.warning("No rate schedules available for this utility.")

def show_compare_rates():
    st.title("Compare Rate Schedules")
    st.write("Compare utility rate schedules to find the best option for your usage pattern.")
    
    # Set up columns for inputs
    col1, col2 = st.columns(2)
    
    with col1:
        # State selection
        states = get_all_states()
        selected_state = st.selectbox("Select State", states)
        
        # Usage inputs
        usage_kwh = st.number_input("Monthly Energy Usage (kWh)", min_value=0.0, value=1000.0, step=100.0, key="compare_kwh")
        demand_kw = st.number_input("Monthly Demand (kW)", min_value=0.0, value=5.0, step=1.0, key="compare_kw")
        billing_days = st.number_input("Billing Days", min_value=1, value=30, step=1, key="compare_days")
        voltage = st.number_input("Voltage (kV, optional)", min_value=0.0, value=None, step=1.0, key="compare_voltage")
    
    with col2:
        # Utility selection
        if selected_state:
            utilities = get_utilities_by_state(selected_state)
            
            if isinstance(utilities, dict) and utilities.get("no_utilities"):
                st.warning(utilities.get("message", "No utilities found for this state."))
            elif isinstance(utilities, dict) and utilities.get("no_schedules"):
                st.warning(utilities.get("message", "No schedules available for utilities in this state."))
            else:
                utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities if u.get("has_schedules", False)]
                
                if not utility_options:
                    st.warning(f"No utilities with rate schedules found for {selected_state}.")
                else:
                    utility_ids, utility_names = zip(*utility_options)
                    selected_utility_index = st.selectbox("Select Utility", range(len(utility_names)), format_func=lambda i: utility_names[i])
                    selected_utility_id = utility_ids[selected_utility_index]
                    
                    # Get schedules for this utility
                    schedules = get_schedules(selected_utility_id)
                    
                    if schedules:
                        # Allow multiple schedule selection for comparison
                        schedule_options = [(s["ScheduleID"], s["ScheduleName"]) for s in schedules]
                        schedule_ids, schedule_names = zip(*schedule_options)
                        
                        # Create a multiselect for choosing schedules to compare
                        selected_schedules = st.multiselect(
                            "Select Schedules to Compare",
                            options=schedule_ids,
                            format_func=lambda x: next((s["ScheduleName"] for s in schedules if s["ScheduleID"] == x), "Unknown"),
                            default=schedule_ids[0:min(2, len(schedule_ids))]  # Default select first 2 schedules
                        )
                    else:
                        st.warning("No rate schedules available for this utility.")
    
    # Compare button
    compare_pressed = st.button("Compare Schedules")
    
    if compare_pressed and 'selected_schedules' in locals() and selected_schedules:
        with st.spinner("Calculating and comparing bills..."):
            # Calculate bill for each selected schedule
            results = []
            
            for schedule_id in selected_schedules:
                result = calculate_bill(
                    schedule_id, 
                    usage_kwh, 
                    demand_kw, 
                    billing_days, 
                    voltage
                )
                
                if result:
                    # Get schedule name
                    schedule_name = next((s["ScheduleName"] for s in schedules if s["ScheduleID"] == schedule_id), "Unknown")
                    
                    results.append({
                        "schedule_id": schedule_id,
                        "schedule_name": schedule_name,
                        "total_cost": result["total_cost"],
                        "breakdown": result["breakdown"]
                    })
            
            if results:
                # Sort by total cost
                results.sort(key=lambda x: x["total_cost"])
                
                # Create comparison visualization
                st.subheader("Bill Comparison Results")
                
                # Comparison table
                comparison_data = {
                    "Schedule": [r["schedule_name"] for r in results],
                    "Total Cost": [f"${r['total_cost']:.2f}" for r in results]
                }
                
                # Add breakdown categories to comparison
                all_categories = set()
                for r in results:
                    all_categories.update(r["breakdown"].keys())
                
                for category in sorted(all_categories):
                    comparison_data[category] = [f"${r['breakdown'].get(category, 0):.2f}" for r in results]
                
                st.table(comparison_data)
                
                # Create bar chart for visual comparison
                import altair as alt
                import pandas as pd
                
                chart_data = pd.DataFrame({
                    'Schedule': [r["schedule_name"] for r in results],
                    'Cost': [r["total_cost"] for r in results]
                })
                
                chart = alt.Chart(chart_data).mark_bar().encode(
                    x=alt.X('Schedule', sort=None),
                    y='Cost',
                    color='Schedule'
                ).properties(
                    title='Total Cost Comparison'
                )
                
                st.altair_chart(chart, use_container_width=True)
                
                # Show the best option
                if len(results) > 1:
                    best_option = results[0]  # Already sorted by cost
                    savings = results[1]["total_cost"] - best_option["total_cost"]
                    
                    st.success(f"Best option: {best_option['schedule_name']} (${best_option['total_cost']:.2f})")
                    
                    if savings > 0:
                        st.info(f"Potential savings: ${savings:.2f} compared to {results[1]['schedule_name']}")
            else:
                st.warning("Could not calculate bills for the selected schedules.")
        
if __name__ == "__main__":
    main()
