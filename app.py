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
        # Get base schedule
        schedule = supabase.table("Schedule_Table").select("*").eq("ScheduleID", schedule_id).single().execute().data

        # TIP tables and check presence
        detail_tables = [
            "DemandTime_Table",
            "Demand_Table",
            "EnergyTime_Table",
            "IncrementalDemand_Table",
            "IncrementalEnergy_Table",
            "OtherCharges_Table",
            "ReactiveDemand_Table",
            "ServiceCharge_Table",
            "TaxInfo_Table"
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

if __name__ == "__main__":
    app.run(debug=True)
