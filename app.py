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

@app.route("/test_connection")
def test_connection():
    try:
        result = supabase.table("Utility").select("*").limit(1).execute()
        return {
            "status": "success",
            "sample": result.data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }, 500

# NEW: Get utilities by state
@app.route("/utilities_by_state")
def get_utilities_by_state():
    state_code = request.args.get("state")
    if not state_code:
        return jsonify([])

    try:
        response = supabase.table("Utility") \
            .select("UtilityID, UtilityName") \
            .eq("State", state_code) \
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# NEW: Get schedules by utility
@app.route("/schedules_by_utility")
def get_schedules_by_utility():
    utility_id = request.args.get("utility_id")
    if not utility_id:
        return jsonify([])

    try:
        response = supabase.table("Schedule_Table") \
            .select("ScheduleID, ScheduleName") \
            .eq("UtilityID", utility_id) \
            .execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
