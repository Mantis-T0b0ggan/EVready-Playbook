import os
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

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

# GET States that have Utilities with at least one Schedule
@app.route("/states")
def get_states():
    try:
        utilities = supabase.table("Utility").select("UtilityID, State").execute().data
        schedules = supabase.table("Schedule_Table").select("UtilityID").execute().data

        utility_ids_with_schedules = {s['UtilityID'] for s in schedules if s.get('UtilityID') is not None}

        states_with_schedules = set()
        for util in utilities:
            if util['UtilityID'] in utility_ids_with_schedules:
                states_with_schedules.add(util['State'])

        return jsonify(sorted(states_with_schedules))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# GET Utilities filtered by selected State
@app.route("/get_utilities_by_state")
def get_utilities_by_state():
    state = request.args.get("state")
    try:
        utilities = supabase.table("Utility").select("UtilityID, UtilityName, State").eq("State", state).execute().data
        schedules = supabase.table("Schedule_Table").select("UtilityID").execute().data

        utility_ids_with_schedules = {s['UtilityID'] for s in schedules if s.get('UtilityID') is not None}

        filtered_utilities = [
            {"UtilityID": u["UtilityID"], "UtilityName": u["UtilityName"]}
            for u in utilities if u["UtilityID"] in utility_ids_with_schedules
        ]

        return jsonify(filtered_utilities)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# GET Schedules for a selected Utility
@app.route("/schedules")
def get_schedules():
    utility_id = request.args.get("utility_id")
    try:
        result = supabase.table("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", utility_id).execute()
        return jsonify(result.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# GET Schedule Details (used for dynamic inputs)
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

# POST Calculate Bill
@app.route("/calculate_bill", methods=["POST"])
def calculate_bill():
    try:
        data = request.json
        schedule_id = int(data.get("schedule_id"))
        usage_kwh = float(data.get("kwh", 0))
        demand_kw = float(data.get("kw", 0))
        billing_days = int(data.get("days", 0))

        total_cost = 0.0
        breakdown = {}

        table_charge_map = {
            "DemandTime_Table": {"field": "RatekW", "multiplier": demand_kw},
            "Demand_Table": {"field": "RatekW", "multiplier": demand_kw},
            "EnergyTime_Table": {"field": "RatekWh", "multiplier": usage_kwh},
            "Energy_Table": {"field": "RatekWh", "multiplier": usage_kwh},
            "IncrementalDemand_Table": {"field": "RatekW", "multiplier": demand_kw},
            "IncrementalEnergy_Table": {"field": "RatekWh", "multiplier": usage_kwh},
            "ReactiveDemand_Table": {"field": "RatekVAR", "multiplier": demand_kw},
            "OtherCharges_Table": {"field": "ChargeType", "multiplier": 1},
            "ServiceCharge_Table": {"field": "Rate", "multiplier": 1},
            "TaxInfo_Table": {"field": "ChargeType", "multiplier": 1},
            "Percentages_Table": {"field": "PercentCharge", "multiplier": 1},
            "Notes_Table": {"field": None, "multiplier": 0}  # Notes are non-financial
        }

        for table, config in table_charge_map.items():
            field = config["field"]
            multiplier = config["multiplier"]

            if not field:
                continue  # Skip Notes table

            rows = supabase.table(table).select("*").eq("ScheduleID", schedule_id).execute().data

            if rows:
                table_total = sum(
                    (item.get(field, 0) or 0) * multiplier for item in rows
                )
                if table_total:
                    breakdown[table] = table_total
                    total_cost += table_total

        return jsonify({
            "breakdown": breakdown,
            "total_cost": total_cost
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------
# RUN APP
# ----------------------
if __name__ == "__main__":
    app.run(debug=True)
