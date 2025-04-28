import os
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__, template_folder="templates")

# ---- MAIN PAGES ----

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/browse_schedules")
def browse_schedules():
    return render_template("browse_schedules.html")

# ---- BILL ESTIMATOR API ENDPOINTS ----

@app.route("/states")
def get_states_bill_estimator():
    """Fetch states (for Bill Estimator page)."""
    result = supabase.table("Utility").select("State").execute()
    states = sorted(set(row["State"] for row in result.data))
    return jsonify(states)

@app.route("/utilities")
def get_utilities_bill_estimator():
    """Fetch utilities for selected state (Bill Estimator page)."""
    state = request.args.get("state")
    result = supabase.table("Utility").select("UtilityID, UtilityName").eq("State", state).execute()
    return jsonify(result.data)

@app.route("/schedules")
def get_schedules_bill_estimator():
    """Fetch schedules for selected utility (Bill Estimator page)."""
    utility_id = request.args.get("utility_id")
    result = supabase.table("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", utility_id).execute()
    return jsonify(result.data)

@app.route("/schedule_details")
def get_schedule_details():
    """Fetch full schedule details and TIP tables for selected schedule."""
    schedule_id = request.args.get("schedule_id")
    detail_tables = [
        "EnergyTime_Table", "Energy_Table", "IncrementalEnergy_Table",
        "DemandTime_Table", "Demand_Table", "IncrementalDemand_Table",
        "OtherCharges_Table", "ServiceCharge_Table", "TaxInfo_Table"
    ]
    details = {}
    present_tables = []

    for table in detail_tables:
        res = supabase.table(table).select("*").eq("ScheduleID", schedule_id).execute()
        if res.data:
            details[table] = res.data
            present_tables.append(table)

    return jsonify({
        "present_tables": present_tables,
        "details": details
    })

@app.route("/calculate_bill", methods=["POST"])
def calculate_bill():
    """Main bill calculation logic."""
    data = request.get_json()
    schedule_id = data.get("schedule_id")
    usage_kwh = float(data.get("usage_kwh", 0))
    demand_kw = float(data.get("demand_kw", 0))
    billing_days = float(data.get("billing_days", 30))

    total_cost = 0.0
    breakdown = {}

    # --- BASE ENERGY CHARGE (hardcoded rate) ---
    energy_rate = 0.029959
    energy_charge = usage_kwh * energy_rate
    breakdown["Energy Charges (@ $0.029959)"] = energy_charge
    total_cost += energy_charge

    # --- ADDITIONAL ENERGY SURCHARGES (Energy_Table) ---
    energy_rows = supabase.table("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute().data
    for row in energy_rows:
        try:
            desc = row.get("Description", "").strip()
            rate = float(row.get("RatekWh", 0))
            if round(rate, 6) == round(energy_rate, 6):
                continue
            if desc and rate > 0:
                charge = usage_kwh * rate
                breakdown[desc] = charge
                total_cost += charge
        except:
            continue

    # --- DEMAND CHARGES ---
    psc_rate = 16.55
    psc_charge = demand_kw * psc_rate
    breakdown["Demand Charges (PSC @ $16.55)"] = psc_charge
    total_cost += psc_charge

    # --- DELIVERY CAPACITY CHARGE ---
    delivery_rate = 1.00
    delivery_charge = demand_kw * delivery_rate
    breakdown["Delivery Capacity Charge (@ $1.00)"] = delivery_charge
    total_cost += delivery_charge

    # --- SERVICE CHARGES ---
    service_charge = 0.0
    service_rows = supabase.table("ServiceCharge_Table").select("*").eq("ScheduleID", schedule_id).execute().data
    for row in service_rows:
        try:
            rate = float(row.get("Rate", 0))
            service_charge += rate * (billing_days / 30)
        except:
            continue
    breakdown["Service Charges"] = service_charge
    total_cost += service_charge

    # --- OTHER FIXED CHARGES (Low Income Fund) ---
    other_charge = 0.0
    other_rows = supabase.table("OtherCharges_Table").select("*").eq("ScheduleID", schedule_id).execute().data
    for row in other_rows:
        try:
            desc = row.get("Description", "").lower()
            unit = row.get("ChargeUnit", "").lower()
            charge = float(row.get("ChargeType", 0))
            if "low-income" in desc and "per meter" in unit:
                other_charge += charge
        except:
            continue
    breakdown["Other Charges"] = other_charge
    total_cost += other_charge

    return jsonify({
        "total_cost": round(total_cost, 2),
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()}
    })

# ---- SCHEDULE BROWSER API ENDPOINTS ----

@app.route("/get_states")
def get_states_browser():
    """Fetch states (for Schedule Browser page)."""
    result = supabase.table("Utility").select("State").execute()
    states = sorted(set(row["State"] for row in result.data))
    return jsonify(states)

@app.route("/get_utilities_by_state")
def get_utilities_browser():
    """Fetch utilities for selected state (Schedule Browser page)."""
    state = request.args.get("state")
    result = supabase.table("Utility").select("UtilityID, UtilityName").eq("State", state).execute()
    return jsonify(result.data)

@app.route("/get_schedules_by_utility")
def get_schedules_browser():
    """Fetch schedules with TIP table details if present."""
    utility_id = request.args.get("utility_id")

    # Get schedules tied to utility
    schedules = supabase.table("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", utility_id).execute().data
    if not schedules:
        return jsonify([])

    full_schedule_info = []

    for sched in schedules:
        schedule_id = sched.get("ScheduleID")
        schedule_name = sched.get("ScheduleName")
        schedule_info = {
            "ScheduleID": schedule_id,
            "ScheduleName": schedule_name
        }

        # Pull Energy Rate (EnergyTime_Table)
        energy_rows = supabase.table("EnergyTime_Table").select("RatekWh").eq("ScheduleID", schedule_id).execute().data
        if energy_rows:
            try:
                ratekwh = float(energy_rows[0].get("RatekWh", 0))
                if ratekwh > 0:
                    schedule_info["Energy Rate ($/kWh)"] = ratekwh
            except:
                pass

        # Pull Demand Rate (DemandTime_Table)
        demand_rows = supabase.table("DemandTime_Table").select("RatekW").eq("ScheduleID", schedule_id).execute().data
        if demand_rows:
            try:
                ratekw = float(demand_rows[0].get("RatekW", 0))
                if ratekw > 0:
                    schedule_info["Demand Rate ($/kW)"] = ratekw
            except:
                pass

        # Pull Service Charge (ServiceCharge_Table)
        service_rows = supabase.table("ServiceCharge_Table").select("Rate").eq("ScheduleID", schedule_id).execute().data
        if service_rows:
            try:
                rate = float(service_rows[0].get("Rate", 0))
                if rate > 0:
                    schedule_info["Service Charge ($/month)"] = rate
            except:
                pass

        # Only add schedules that have at least one detail (besides ScheduleID/Name)
        if len(schedule_info.keys()) > 2:
            full_schedule_info.append(schedule_info)

    return jsonify(full_schedule_info)

            })

# ---- RUN APP ----

if __name__ == "__main__":
    app.run(debug=True)
