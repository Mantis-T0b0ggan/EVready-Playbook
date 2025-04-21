import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Flask app
app = Flask(__name__, template_folder="templates")

# ----------------------------
# ROUTES
# ----------------------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/states")
def get_states():
    try:
        response = supabase.table("Utility").select("State").execute()
        states = sorted(list(set(item["State"] for item in response.data if item["State"])))
        return jsonify(states)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/utilities_by_state")
def get_utilities_by_state():
    state = request.args.get("state")
    if not state:
        return jsonify({"error": "State required"}), 400

    try:
        response = supabase.table("Utility").select("UtilityID, UtilityName").eq("State", state).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/schedules_by_utility")
def get_schedules_by_utility():
    utility_id = request.args.get("utility_id")
    if not utility_id:
        return jsonify({"error": "Utility ID required"}), 400

    try:
        response = supabase.table("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", utility_id).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/view_schedule")
def view_schedule():
    schedule_id = request.args.get("schedule_id")
    if not schedule_id:
        return jsonify({"error": "Schedule ID is required"}), 400

    try:
        result = supabase.table("Schedule_Table").select("*").eq("ScheduleID", schedule_id).single().execute()
        return jsonify(result.data)
    except Exception as e:
        return jsonify({"error": f"Error retrieving schedule: {str(e)}"}), 500

# ----------------------------
# Run the App
# ----------------------------

if __name__ == "__main__":
    app.run(debug=True)
