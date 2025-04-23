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
        "ServiceCharge_Table", "OtherCharges_Table", "Percentages_Table",
        "TaxInfo_Table"
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

    # --- ENERGY (Hardcoded flat rate) ---
    energy_rate = 0.029959
    energy_charge = usage_kwh * energy_rate
    breakdown["Energy Charges (@ $0.029959)"] = energy_charge
    total_cost += energy_charge

    # --- DEMAND PSC ($16.55/kW) ---
    psc_rate = 16.55
    psc_charge = demand_kw * psc_rate
    breakdown["Demand Charges (PSC @ $16.55)"] = psc_charge
    total_cost += psc_charge

    # --- DELIVERY CAPACITY ($1.00/kW) ---
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

    # --- OTHER CHARGES (Fixed) ---
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

        # --- PERCENTAGE-BASED CHARGES (Expanded) ---
    percent_rows = supabase.table("Percentages_Table").select("*").eq("ScheduleID", schedule_id).execute().data
    for row in percent_rows:
        try:
            label = row.get("Description", "").strip() or "Energy Surcharge"
            pct = float(row.get("Per_cent", 0))
            if pct > 0:
                surcharge = usage_kwh * pct
                breakdown[label] = surcharge
                total_cost += surcharge
        except:
            continue

    return jsonify({
        "total_cost": round(total_cost, 2),
        "breakdown": {k: round(v, 2) for k, v in breakdown.items()}
    })

if __name__ == "__main__":
    app.run(debug=True)
