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
    try:
        result = supabase.table("Utility").select("State").execute()
        unique_states = sorted(set([row["State"] for row in result.data if "State" in row]))
        return jsonify(unique_states)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/utilities")
def get_utilities():
    state = request.args.get("state")
    try:
        result = supabase.table("Utility").select("UtilityID, UtilityName").eq("State", state).execute()
        return jsonify(result.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/schedules")
def get_schedules():
    utility_id = request.args.get("utility_id")
    try:
        result = supabase.table("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", utility_id).execute()
        return jsonify(result.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/schedule_details")
def get_schedule_details():
    schedule_id = request.args.get("schedule_id")
    try:
        schedule = supabase.table("Schedule_Table").select("*").eq("ScheduleID", schedule_id).single().execute().data
        detail_tables = [
            "Demand_Table",
            "DemandTime_Table",
            "EnergyTime_Table",
            "IncrementalDemand_Table",
            "IncrementalEnergy_Table",
            "OtherCharges_Table",
            "ReactiveDemand_Table",
            "ServiceCharge_Table",
            "TaxInfo_Table",
            "Percentages_Table",
            "Notes_Table"
        ]
        detail_data = {}
        for table in detail_tables:
            res = supabase.table(table).select("*").eq("ScheduleID", schedule_id).execute()
            detail_data[table] = res.data if res.data else []
        return jsonify({
            "schedule": schedule,
            "details": detail_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/calculate_bill")
def calculate_bill():
    try:
        schedule_id = request.args.get("schedule_id")
        kwh = float(request.args.get("kwh"))
        kw = float(request.args.get("kw"))
        days = int(request.args.get("days"))

        # Pull Energy rates
        energy_rows = supabase.table("EnergyTime_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        energy_rate = float(energy_rows[0]["Rate"]) if energy_rows else 0
        energy_cost = kwh * energy_rate

        # Pull Demand rates
        demand_rows = supabase.table("DemandTime_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        demand_rate = float(demand_rows[0]["Rate"]) if demand_rows else 0
        demand_cost = kw * demand_rate

        # Pull Fixed Charges (OtherCharges_Table)
        fixed_rows = supabase.table("OtherCharges_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        fixed_cost = sum(float(row["ChargeType"]) for row in fixed_rows if row.get("ChargeType") not in [None, ""])

        total = energy_cost + demand_cost + fixed_cost

        return jsonify({
            "energy": energy_cost,
            "demand": demand_cost,
            "fixed": fixed_cost,
            "total": total
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
