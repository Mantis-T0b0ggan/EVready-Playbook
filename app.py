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

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/states")
def get_states():
    result = supabase.table("Utility").select("State").execute()
    states = sorted(set(row["State"] for row in result.data))
    return jsonify(states)

@app.route("/utilities")
def get_utilities():
    state = request.args.get("state")
    result = supabase.table("Utility").select("UtilityID, UtilityName").eq("State", state).execute()
    return jsonify(result.data)

@app.route("/schedules")
def get_schedules():
    utility_id = request.args.get("utility_id")
    result = supabase.table("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", utility_id).execute()
    return jsonify(result.data)

@app.route("/schedule_details")
def get_schedule_details():
    schedule_id = request.args.get("schedule_id")
    detail_tables = [
        "Energy_Table", "EnergyTime_Table", "IncrementalEnergy_Table",
        "Demand_Table", "DemandTime_Table", "IncrementalDemand_Table",
        "ServiceCharge_Table", "OtherCharges_Table", "TaxInfo_Table"
    ]
    present_tables = []
    for table in detail_tables:
        result = supabase.table(table).select("*").eq("ScheduleID", schedule_id).execute()
        if result.data:
            present_tables.append(table)
    return jsonify({"present_tables": present_tables})

@app.route("/calculate_bill", methods=["POST"])
def calculate_bill():
    data = request.get_json()
    schedule_id = data.get("schedule_id")
    usage_kwh = float(data.get("usage_kwh", 0))
    demand_kw = float(data.get("demand_kw", 0))
    billing_days = float(data.get("billing_days", 30))

    total_cost = 0.0
    breakdown = {}

    # --- BASE ENERGY CHARGE (hardcoded flat rate) ---
    energy_rate = 0.029959
    energy_charge = usage_kwh * energy_rate
    breakdown["Energy Charges (@ $0.029959)"] = energy_charge
    total_cost += energy_charge

    # --- ADDITIONAL ENERGY SURCHARGES FROM ENERGY_TABLE ---
    energy_rows = supabase.table("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute().data
    for row in energy_rows:
        try:
            desc = row.get("Description", "").strip()
            rate = float(row.get("RatekWh", 0))
            if round(rate, 6) == round(energy_rate, 6):  # skip base rate
                continue
            if desc and rate > 0:
                charge = usage_kwh * rate
                breakdown[desc] = charge
                total_cost += charge
        except:
            continue

    # --- DEMAND PSC CHARGE ---
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

    # --- OTHER CHARGES (Low-Income Fund) ---
    other_charge = 0.0
    other_rows = supabase.table("OtherCharges_Table").select("*").eq("ScheduleID", schedule_id).execute().data
    for row in other_rows:
        try:
            desc = row.get("Description", "").lower()
            unit = row.get("ChargeUnit", "").lower()
            charge = float(row.get("ChargeType", 0))
            if "low-income" in desc and "per meter" in unit:
                other_charge += charge  # assume 1 meter
        except:
            continue
    breakdown["Other Charges"] = other_charge
    total_cost += other_charge

    return jsonify({
        "total_cost": round(total_cost, 2),
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()}
    })

if __name__ == "__main__":
    app.run(debug=True)
