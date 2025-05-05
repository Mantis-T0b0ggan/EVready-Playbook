import os
import math
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure page settings
st.set_page_config(
    page_title="EVready Playbook",
    page_icon="⚡",
    layout="wide", 
    initial_sidebar_state="expanded"
)

# -----------------------
# HELPER FUNCTIONS
# -----------------------

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

def calculate_bill(schedule_id, usage_kwh, demand_kw, billing_days, voltage_input):
    """Calculate estimated bill based on inputs"""
    try:
        # Convert input values with proper handling of None values
        usage_kwh = float(usage_kwh or 0)  # Convert None to 0
        demand_kw = float(demand_kw or 0)   # Convert None to 0
        billing_days = int(billing_days or 30)  # Convert None to 30
        
        # Handle voltage value - if it's None or empty string, set to None
        voltage = float(voltage_input) if voltage_input and voltage_input != "" else None
        
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
        
        return detailed_breakdown, total_cost
    except Exception as e:
        st.error(f"Error calculating bill: {str(e)}")
        return {}, 0

def get_all_states():
    """Returns a list of all states"""
    try:
        # Define all 50 US states plus DC, Puerto Rico, etc.
        all_states = [
            "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", 
            "GA", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", 
            "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", 
            "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "PR", 
            "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", 
            "WV", "WY"
        ]
        
        return sorted(all_states)
    except Exception as e:
        st.error(f"Error getting states: {str(e)}")
        return []

def get_utilities_by_state(state):
    """Get all utilities for a specific state"""
    try:
        # Get all utilities in the selected state
        utilities = supabase.table("Utility").select("UtilityID, UtilityName, State").eq("State", state).execute().data
        
        # Check if we found any utilities for this state
        if not utilities:
            return {"no_utilities": True, "message": f"No utilities found for {state}", "utilities": []}
        
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
        
        return {"utilities": utilities_with_schedules}
    except Exception as e:
        st.error(f"Error getting utilities for state {state}: {str(e)}")
        return {"error": str(e), "utilities": []}

def get_schedules_by_utility(utility_id):
    """Get all schedules for a specific utility"""
    try:
        result = supabase.table("Schedule_Table") \
            .select("ScheduleID, ScheduleName, ScheduleDescription") \
            .eq("UtilityID", utility_id) \
            .execute()
        return result.data
    except Exception as e:
        st.error(f"Error getting schedules for utility {utility_id}: {str(e)}")
        return []

def get_schedule_details(schedule_id):
    """Get details for a specific schedule"""
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
        st.error(f"Error getting schedule details for schedule {schedule_id}: {str(e)}")
        return None

# -----------------------
# STREAMLIT APP PAGES
# -----------------------

def main():
    """Main application flow"""
    # Sidebar navigation
    st.sidebar.title("EVready Playbook")
    page = st.sidebar.radio("Choose a page", ["Bill Estimator", "Browse Schedules", "Compare Rates"])
    
    if page == "Bill Estimator":
        bill_estimator_page()
    elif page == "Browse Schedules":
        browse_schedules_page()
    elif page == "Compare Rates":
        compare_rates_page()

def bill_estimator_page():
    """Bill Estimator Page (Home)"""
    st.title("Electric Vehicle Rate Calculator")
    st.write("Estimate your electricity costs with EV-specific utility rates.")
    
    # Step 1: Select State
    st.subheader("Step 1: Select Your State")
    states = get_all_states()
    selected_state = st.selectbox("State", states, index=0)
    
    # Step 2: Select Utility
    if selected_state:
        st.subheader("Step 2: Select Your Utility")
        utilities_result = get_utilities_by_state(selected_state)
        
        if "no_utilities" in utilities_result and utilities_result["no_utilities"]:
            st.warning(utilities_result["message"])
            return
            
        if "no_schedules" in utilities_result and utilities_result["no_schedules"]:
            st.warning(utilities_result["message"])
            utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities_result["utilities"]]
            selected_utility_id = st.selectbox(
                "Utility (no schedules available)", 
                [opt[0] for opt in utility_options],
                format_func=lambda x: next((opt[1] for opt in utility_options if opt[0] == x), "")
            )
            return
            
        utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities_result["utilities"] if u.get("has_schedules", False)]
        if not utility_options:
            st.warning(f"No utilities with available schedules found for {selected_state}")
            return
            
        selected_utility_id = st.selectbox(
            "Utility", 
            [opt[0] for opt in utility_options],
            format_func=lambda x: next((opt[1] for opt in utility_options if opt[0] == x), ""),
            key="browse_utility"
        )
        
        # Step 3: View Schedules
        if selected_utility_id:
            st.subheader("Step 3: Available Rate Schedules")
            all_schedules = supabase.table("Schedule_Table") \
                .select("*") \
                .eq("UtilityID", selected_utility_id) \
                .execute().data
                
            if not all_schedules:
                st.warning("No schedules available for the selected utility.")
                return
                
            # Display schedules in expandable sections
            for schedule in all_schedules:
                with st.expander(f"{schedule['ScheduleName']} - {schedule.get('ScheduleDescription', 'No description')}"):
                    # Get full schedule details
                    schedule_details = get_schedule_details(schedule["ScheduleID"])
                    
                    if not schedule_details:
                        st.write("No detailed information available for this schedule.")
                        continue
                    
                    # Display basic information
                    st.write(f"**Schedule ID:** {schedule['ScheduleID']}")
                    if schedule.get('EffectiveDate'):
                        st.write(f"**Effective Date:** {schedule['EffectiveDate']}")
                        
                    # Create tabs for different types of charges
                    if schedule_details["present_tables"]:
                        tabs = st.tabs([table.replace("_Table", "").replace("Time", " Time-of-Use") 
                                      for table in schedule_details["present_tables"]])
                        
                        for i, table_name in enumerate(schedule_details["present_tables"]):
                            with tabs[i]:
                                # Convert table data to DataFrame for better display
                                import pandas as pd
                                df = pd.DataFrame(schedule_details["details"][table_name])
                                st.dataframe(df)
                    else:
                        st.write("No detailed rate components found for this schedule.")

def compare_rates_page():
    """Compare Rates Page"""
    st.title("Compare Electric Utility Rates")
    st.write("Compare multiple utility rate schedules side by side.")
    
    # Create containers for comparison
    st.subheader("Select Rates to Compare")
    
    # Allow user to select multiple rate schedules to compare
    num_comparisons = st.number_input("Number of rates to compare", min_value=2, max_value=4, value=2)
    
    # Create comparison columns
    cols = st.columns(num_comparisons)
    
    # Store the selected schedules
    selected_schedules = []
    
    # Loop through each column
    for i, col in enumerate(cols):
        with col:
            st.write(f"Rate #{i+1}")
            
            # Select state
            states = get_all_states()
            selected_state = st.selectbox(f"State #{i+1}", states, key=f"compare_state_{i}")
            
            if selected_state:
                # Select utility
                utilities_result = get_utilities_by_state(selected_state)
                
                if "utilities" in utilities_result and utilities_result["utilities"]:
                    utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities_result["utilities"] 
                                      if u.get("has_schedules", False)]
                    
                    if utility_options:
                        selected_utility_id = st.selectbox(
                            f"Utility #{i+1}", 
                            [opt[0] for opt in utility_options],
                            format_func=lambda x: next((opt[1] for opt in utility_options if opt[0] == x), ""),
                            key=f"compare_utility_{i}"
                        )
                        
                        # Select schedule
                        if selected_utility_id:
                            schedules = get_schedules_by_utility(selected_utility_id)
                            
                            if schedules:
                                schedule_options = [(s["ScheduleID"], s["ScheduleName"]) for s in schedules]
                                selected_schedule_id = st.selectbox(
                                    f"Schedule #{i+1}",
                                    [opt[0] for opt in schedule_options],
                                    format_func=lambda x: next((opt[1] for opt in schedule_options if opt[0] == x), ""),
                                    key=f"compare_schedule_{i}"
                                )
                                
                                # Add to selected schedules for comparison
                                if selected_schedule_id:
                                    schedule_details = get_schedule_details(selected_schedule_id)
                                    if schedule_details:
                                        selected_schedules.append({
                                            "state": selected_state,
                                            "utility_id": selected_utility_id,
                                            "utility_name": next((opt[1] for opt in utility_options if opt[0] == selected_utility_id), ""),
                                            "schedule_id": selected_schedule_id,
                                            "schedule_name": next((opt[1] for opt in schedule_options if opt[0] == selected_schedule_id), ""),
                                            "details": schedule_details
                                        })
                            else:
                                st.warning("No schedules available for this utility")
                    else:
                        st.warning("No utilities with schedules available for this state")
                else:
                    st.warning("No utilities available for this state")
    
    # If we have selected schedules, allow comparison
    if len(selected_schedules) >= 2:
        st.subheader("Compare Selected Rates")
        
        # Input box for usage scenario
        st.write("Enter a usage scenario to compare costs:")
        
        # Create two columns for the form inputs
        col1, col2 = st.columns(2)
        
        with col1:
            usage_kwh = st.number_input("Monthly Usage (kWh)", min_value=0, value=1000, key="compare_kwh")
            demand_kw = st.number_input("Peak Demand (kW)", min_value=0, value=10, key="compare_kw")
        
        with col2:
            billing_days = st.number_input("Billing Days", min_value=1, max_value=31, value=30, key="compare_days")
            voltage = st.number_input("Service Voltage (kV)", min_value=0.0, step=0.1, value=None, key="compare_voltage")
        
        # Calculate button
        if st.button("Compare Rates"):
            # Show a spinner while calculating
            with st.spinner("Calculating..."):
                # Calculate bill for each selected schedule
                comparison_results = []
                
                for schedule in selected_schedules:
                    breakdown, total_cost = calculate_bill(
                        schedule["schedule_id"], 
                        usage_kwh, 
                        demand_kw, 
                        billing_days, 
                        voltage
                    )
                    
                    comparison_results.append({
                        "state": schedule["state"],
                        "utility": schedule["utility_name"],
                        "schedule": schedule["schedule_name"],
                        "breakdown": breakdown,
                        "total_cost": total_cost
                    })
                
                # Display comparison results
                st.success("Comparison completed")
                
                # Create comparison table
                import pandas as pd
                
                # Basic comparison of total costs
                comparison_df = pd.DataFrame({
                    "Utility": [r["utility"] for r in comparison_results],
                    "Rate Schedule": [r["schedule"] for r in comparison_results],
                    "Total Cost ($)": [f"${r['total_cost']:.2f}" for r in comparison_results],
                    "Cost per kWh ($)": [f"${r['total_cost']/usage_kwh:.3f}" if usage_kwh > 0 else "N/A" for r in comparison_results]
                })
                
                st.table(comparison_df)
                
                # Create bar chart for visual comparison
                chart_data = pd.DataFrame({
                    "Rate": [f"{r['utility']} - {r['schedule']}" for r in comparison_results],
                    "Cost ($)": [r["total_cost"] for r in comparison_results]
                })
                
                st.subheader("Cost Comparison Chart")
                st.bar_chart(chart_data.set_index("Rate"))
                
                # Detailed breakdown comparison
                st.subheader("Detailed Charge Breakdown")
                
                # Get all possible charge types from all breakdowns
                all_charge_types = set()
                for result in comparison_results:
                    all_charge_types.update(result["breakdown"].keys())
                
                # Create a DataFrame with all charge types
                breakdown_comparison = {}
                
                for charge_type in sorted(all_charge_types):
                    breakdown_comparison[charge_type] = []
                    
                    for result in comparison_results:
                        value = result["breakdown"].get(charge_type, 0)
                        breakdown_comparison[charge_type].append(f"${value:.2f}")
                
                # Add column headers (utility and rate names)
                column_headers = [f"{r['utility']} - {r['schedule']}" for r in comparison_results]
                
                # Create and display the DataFrame
                breakdown_df = pd.DataFrame(breakdown_comparison, index=column_headers)
                st.dataframe(breakdown_df.transpose())
                
                # Provide insights and analysis
                st.subheader("Rate Comparison Analysis")
                
                # Find the lowest cost option
                lowest_cost_index = min(range(len(comparison_results)), key=lambda i: comparison_results[i]["total_cost"])
                lowest_cost = comparison_results[lowest_cost_index]
                
                st.write(f"**Lowest Cost Option:** {lowest_cost['utility']} - {lowest_cost['schedule']} at ${lowest_cost['total_cost']:.2f}")
                
                # Calculate average cost
                avg_cost = sum(r["total_cost"] for r in comparison_results) / len(comparison_results)
                st.write(f"**Average Cost:** ${avg_cost:.2f}")
                
                # Calculate potential savings compared to highest cost
                highest_cost_index = max(range(len(comparison_results)), key=lambda i: comparison_results[i]["total_cost"])
                highest_cost = comparison_results[highest_cost_index]
                
                potential_savings = highest_cost["total_cost"] - lowest_cost["total_cost"]
                st.write(f"**Potential Monthly Savings:** ${potential_savings:.2f} by choosing the lowest cost option instead of the highest")
                
                # Annual projection
                annual_savings = potential_savings * 12
                st.write(f"**Potential Annual Savings:** ${annual_savings:.2f}")

# Run the main application
if __name__ == "__main__":
    main()")
            return
            
        selected_utility_id = st.selectbox(
            "Utility", 
            [opt[0] for opt in utility_options],
            format_func=lambda x: next((opt[1] for opt in utility_options if opt[0] == x), "")
        )
        
        # Step 3: Select Rate Schedule
        if selected_utility_id:
            st.subheader("Step 3: Select Your Rate Schedule")
            schedules = get_schedules_by_utility(selected_utility_id)
            
            if not schedules:
                st.warning(f"No rate schedules available for the selected utility.")
                return
                
            schedule_options = [(s["ScheduleID"], s["ScheduleName"]) for s in schedules]
            selected_schedule_id = st.selectbox(
                "Rate Schedule", 
                [opt[0] for opt in schedule_options],
                format_func=lambda x: next((opt[1] for opt in schedule_options if opt[0] == x), "")
            )
            
            # Step 4: Enter Usage Information
            if selected_schedule_id:
                st.subheader("Step 4: Enter Your Usage Information")
                
                # Create two columns for the form inputs
                col1, col2 = st.columns(2)
                
                with col1:
                    usage_kwh = st.number_input("Monthly Usage (kWh)", min_value=0, value=1000)
                    demand_kw = st.number_input("Peak Demand (kW)", min_value=0, value=10)
                
                with col2:
                    billing_days = st.number_input("Billing Days", min_value=1, max_value=31, value=30)
                    voltage = st.number_input("Service Voltage (kV)", min_value=0.0, step=0.1, value=None)
                
                # Calculate button
                if st.button("Calculate Bill"):
                    # Show a spinner while calculating
                    with st.spinner("Calculating..."):
                        # Get the schedule details first (for display)
                        schedule_info = get_schedule_details(selected_schedule_id)
                        schedule_name = schedule_info["schedule"]["ScheduleName"] if schedule_info and "schedule" in schedule_info else "Selected Rate"
                        
                        # Calculate the bill
                        breakdown, total_cost = calculate_bill(
                            selected_schedule_id, 
                            usage_kwh, 
                            demand_kw, 
                            billing_days, 
                            voltage
                        )
                        
                        # Display results
                        st.success(f"Bill calculation completed for {schedule_name}")
                        
                        # Results section
                        st.subheader("Bill Estimate Results")
                        
                        # Create two columns for results display
                        result_col1, result_col2 = st.columns([2, 1])
                        
                        with result_col1:
                            # Display breakdown in a table
                            st.write("Breakdown of Charges:")
                            
                            # Convert breakdown to a dataframe for nicer display
                            import pandas as pd
                            breakdown_df = pd.DataFrame({
                                "Charge Type": breakdown.keys(),
                                "Amount ($)": [f"${value:.2f}" for value in breakdown.values()]
                            })
                            st.table(breakdown_df)
                            
                        with result_col2:
                            # Display total cost prominently
                            st.markdown(f"### Total Estimated Bill")
                            st.markdown(f"## ${total_cost:.2f}")
                            
                            # Display metrics comparing to average
                            if usage_kwh > 0:
                                cost_per_kwh = total_cost / usage_kwh
                                st.metric("Cost per kWh", f"${cost_per_kwh:.3f}")
                            
                            if demand_kw > 0:
                                cost_per_kw = total_cost / demand_kw
                                st.metric("Cost per kW of Demand", f"${cost_per_kw:.2f}")
                        
                        # Optional: Display detailed schedule information
                        with st.expander("View Rate Schedule Details"):
                            if schedule_info:
                                st.json(schedule_info)
                            else:
                                st.write("Schedule details not available")

def browse_schedules_page():
    """Browse Schedules Page"""
    st.title("Browse Utility Rate Schedules")
    st.write("View available electric utility rate schedules by state and utility.")
    
    # Step 1: Select State
    st.subheader("Step 1: Select State")
    states = get_all_states()
    selected_state = st.selectbox("State", states, index=0, key="browse_state")
    
    # Step 2: Select Utility
    if selected_state:
        st.subheader("Step 2: Select Utility")
        utilities_result = get_utilities_by_state(selected_state)
        
        if "no_utilities" in utilities_result and utilities_result["no_utilities"]:
            st.warning(utilities_result["message"])
            return
            
        if "no_schedules" in utilities_result and utilities_result["no_schedules"]:
            st.warning(utilities_result["message"])
            utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities_result["utilities"]]
            selected_utility_id = st.selectbox(
                "Utility (no schedules available)", 
                [opt[0] for opt in utility_options],
                format_func=lambda x: next((opt[1] for opt in utility_options if opt[0] == x), ""),
                key="browse_utility_no_schedules"
            )
            return
            
        utility_options = [(u["UtilityID"], u["UtilityName"]) for u in utilities_result["utilities"] if u.get("has_schedules", False)]
        if not utility_options:
            st.warning(f"No utilities with available schedules
