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

# POST Calculate Estimated Bill
@app.route("/calculate_bill", methods=["POST"])
def calculate_bill():
    try:
        data = request.json
        schedule_id = int(data.get("schedule_id"))
        usage_kwh = float(data.get("kwh", 0))
        demand_kw = float(data.get("kw", 0))
        billing_days = int(data.get("days", 0))

        charges = {
            "delivery_charge": 0.0,
            "demand_charge": 0.0,
            "energy_charge": 0.0,
            "other_charges": 0.0,
            "service_charge": 0.0
        }

        # Service Charges (monthly flat rate)
        service_data = supabase.table("ServiceCharge_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        if service_data:
            charges["service_charge"] = sum(item.get("Rate", 0) for item in service_data)

        # Demand Charges ($/kW)
        demand_data = supabase.table("Demand_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        if demand_data:
            charges["demand_charge"] = sum(item.get("RatekW", 0) * demand_kw for item in demand_data)

        # Energy Charges ($/kWh)
        energy_data = supabase.table("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        if energy_data:
            charges["energy_charge"] = sum(item.get("RatekWh", 0) * usage_kwh for item in energy_data)

        # Other Charges (flat charges) - ChargeType field
        other_data = supabase.table("OtherCharges_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        if other_data:
            charges["other_charges"] = sum(item.get("ChargeType", 0) for item in other_data)

        total_cost = sum(charges.values())

        return jsonify({
            **charges,
            "total_cost": total_cost
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------
# RUN APP
# ----------------------
if __name__ == "__main__":
    app.run(debug=True)
