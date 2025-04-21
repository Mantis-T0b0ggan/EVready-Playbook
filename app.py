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
        # Get the base schedule
        schedule = supabase.table("Schedule_Table").select("*").eq("ScheduleID", schedule_id).single().execute().data

        # TIP tables
        detail_tables = [
            "Demand_Table",
            "DemandTime_Table",
            "EnergyTime_Table",
            "IncrementalDemand_Table",
            "IncrementalEnergy_Table",
            "OtherCharges_Table",
            "Rate_Table",
            "RateTime_Table"
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

@app.route("/load_schedule_detail", methods=["POST"])
def load_schedule_detail():
    data = request.get_json()
    schedule_id = data.get("schedule_id")

    if not schedule_id:
        return jsonify({"error": "Schedule ID is required"}), 400

    url = f"https://secure.rateacuity.com/RateAcuityJSONAPI/api/scheduledetailtip/{schedule_id}"
    params = {
        "p1": os.getenv("RATEACUITY_USERNAME"),
        "p2": os.getenv("RATEACUITY_PASSWORD")
    }
    response = requests.get(url, params=params)

    try:
        details = response.json()
        print(f"🔗 Full detail URL: {response.url}")
        print("📦 Raw keys returned in response:", details.keys())  # DEBUG LINE
        return jsonify({"message": f"Fetched detail response for ScheduleID {schedule_id}."})
    except Exception as e:
        return jsonify({
            "error": f"Failed to parse detail response: {str(e)}",
            "raw_response": response.text[:300]
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
