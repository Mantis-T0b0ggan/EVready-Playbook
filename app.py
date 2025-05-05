import os
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta
import math

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, template_folder="templates")

# ----------------------
# ROUTES
# ----------------------

# Home Page (Bill Estimator)
@app.route("/")
def home():
    return render_template("index.html")

# Browse Schedules Page
@app.route("/browse_schedules")
def browse_schedules():
    return render_template("browse_schedules.html")

# GET States that have Utilities with at least one Schedule in EVready Database
@app.route("/states")
def get_states():
    try:
        # First, get all schedules to find which utility IDs have schedules
        schedules = supabase.table("Schedule_Table").select("UtilityID").execute().data
        
        # Create a set of utility IDs that have at least one schedule
        utility_ids_with_schedules = {s['UtilityID'] for s in schedules if s.get('UtilityID') is not None}
        
        print(f"Utility IDs with schedules: {utility_ids_with_schedules}")  # Debug log
        
        # Get all utilities that have schedules
        states_with_schedules = set()
        for util_id in utility_ids_with_schedules:
            utility = supabase.table("Utility").select("State").eq("UtilityID", util_id).execute().data
            if utility and len(utility) > 0:
                state_abbr = utility[0].get('State')
                if state_abbr:
                    states_with_schedules.add(state_abbr)
        
        print(f"States with schedules (abbreviations): {states_with_schedules}")  # Debug log
        
        return jsonify(sorted(list(states_with_schedules)))
    except Exception as e:
        print(f"Error in get_states: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500

# GET Utilities filtered by selected State
@app.route("/get_utilities_by_state")
def get_utilities_by_state():
    state = request.args.get("state")
    try:
        # Get all utilities in the selected state
        utilities = supabase.table("Utility").select("UtilityID, UtilityName, State").eq("State", state).execute().data
        
        # Get all schedules
        schedules = supabase.table("Schedule_Table").select("UtilityID").execute().data
        
        # Create a set of utility IDs that have at least one schedule
        utility_ids_with_schedules = {s['UtilityID'] for s in schedules if s.get('UtilityID') is not None}
        
        # Filter utilities to only include those with schedules
        filtered_utilities = [
            {"UtilityID": u["UtilityID"], "UtilityName": u["UtilityName"]}
            for u in utilities if u["UtilityID"] in utility_ids_with_schedules
        ]
        
        print(f"Filtered utilities for state {state}: {filtered_utilities}")  # Debug log
        
        return jsonify(filtered_utilities)
    except Exception as e:
        print(f"Error in get_utilities_by_state: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500

# GET Schedules for a selected Utility
@app.route("/schedules")
def get_schedules():
    utility_id = request.args.get("utility_id")
    try:
        result = supabase.table("Schedule_Table") \
            .select("ScheduleID, ScheduleName, ScheduleDescription") \
            .eq("UtilityID", utility_id) \
            .execute()
        return jsonify(result.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# GET All Schedule Data for a selected Utility (for browsing)
@app.route("/get_schedules_by_utility")
def get_schedules_by_utility():
    utility_id = request.args.get("utility_id")
    try:
        result = supabase.table("Schedule_Table") \
            .select("*") \
            .eq("UtilityID", utility_id) \
            .execute()
        return jsonify(result.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# GET Schedule Details (used for showing dynamic input fields)
@app.route("/schedule_details")
def get_schedule_details():
    schedule_id = request.args.get("schedule_id")
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

        return jsonify({
            "schedule": schedule,
            "present_tables": present_tables,
            "details": details
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

# POST Calculate Estimated Bill
@app.route("/calculate_bill", methods=["POST"])
def calculate_bill():
    try:
        data = request.json
        schedule_id = int(data.get("schedule_id"))
        
        # Convert input values with proper handling of None values
        usage_kwh = float(data.get("kwh", 0) or 0)  # Convert None to 0
        demand_kw = float(data.get("kw", 0) or 0)   # Convert None to 0
        billing_days = int(data.get("days", 30) or 30)  # Convert None to 30
        
        # Handle voltage value - if it's None or empty string, set to None
        voltage_input = data.get("voltage")
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
        
        return jsonify({
            "breakdown": detailed_breakdown,
            "total_cost": total_cost
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/compare_rates")
def compare_rates():
    return render_template("compare_rates.html")

# Diagnostic endpoint to help troubleshoot state/utility/schedule relationships
@app.route("/diagnostic")
def diagnostic():
    try:
        # Get all schedules
        schedules = supabase.table("Schedule_Table").select("ScheduleID, UtilityID, ScheduleName").execute().data
        print(f"Found {len(schedules)} schedules in database")
        
        # Get all utilities
        utilities = supabase.table("Utility").select("UtilityID, UtilityName, State").execute().data
        print(f"Found {len(utilities)} utilities in database")
        
        # Create a dictionary to map UtilityID to utility details
        utility_map = {u["UtilityID"]: u for u in utilities}
        
        # Create a comprehensive report of what's in the database
        utility_schedules = {}
        state_utilities = {}
        
        for schedule in schedules:
            util_id = schedule.get("UtilityID")
            if util_id is None:
                continue
                
            if util_id not in utility_schedules:
                utility_schedules[util_id] = []
                
            utility_schedules[util_id].append({
                "ScheduleID": schedule.get("ScheduleID"),
                "ScheduleName": schedule.get("ScheduleName")
            })
            
            # Get the utility details
            utility = utility_map.get(util_id)
            if utility:
                state_abbr = utility.get("State")
                if state_abbr:
                    if state_abbr not in state_utilities:
                        state_utilities[state_abbr] = []
                        
                    if util_id not in [u["UtilityID"] for u in state_utilities[state_abbr]]:
                        state_utilities[state_abbr].append({
                            "UtilityID": util_id,
                            "UtilityName": utility.get("UtilityName")
                        })
        
        # Check specifically for Tennessee (TN)
        tn_utilities = [u for u in utilities if u.get("State") == "TN"]
        tn_utility_ids = [u["UtilityID"] for u in tn_utilities]
        tn_utility_with_schedules = [
            util_id for util_id in tn_utility_ids 
            if util_id in utility_schedules
        ]
        
        # Prepare the results
        results = {
            "states_with_utilities": list(state_utilities.keys()),
            "utility_count_by_state": {state: len(utils) for state, utils in state_utilities.items()},
            "schedule_count_by_utility": {util_id: len(scheds) for util_id, scheds in utility_schedules.items()},
            "state_utility_details": state_utilities,
            "utility_schedule_details": utility_schedules,
            "tennessee_check": {
                "tn_utilities": tn_utilities,
                "tn_utility_ids": tn_utility_ids,
                "tn_utilities_with_schedules": tn_utility_with_schedules
            }
        }
        
        return jsonify(results)
    except Exception as e:
        print(f"Error in diagnostic: {str(e)}")
        return jsonify({"error": str(e)}), 500
        
# ----------------------
# RUN APP
# ----------------------
if __name__ == "__main__":
    app.run(debug=True)
