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
            "DemandTime_Table",
            "Demand_Table",
            "EnergyTime_Table",
            "Energy_Table",
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

@app.route("/calculate_bill", methods=["POST"])
def calculate_bill():
    try:
        data = request.get_json()
        schedule_id = data.get("schedule_id")
        usage_kwh = float(data.get("usage_kwh", 0))
        demand_kw = float(data.get("demand_kw", 0))
        billing_days = float(data.get("billing_days", 30))

        total_cost = 0.0
        breakdown = {}

        # --- ENERGY CHARGES ---
        energy_charge = 0.0

        energy_time_data = supabase.table("EnergyTime_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        energy_flat_data = supabase.table("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute().data

        for row in energy_time_data:
            try:
                rate = float(row.get("RatekWH", 0))
                energy_charge += usage_kwh * rate
            except (TypeError, ValueError):
                continue

        for row in energy_flat_data:
            try:
                rate = float(row.get("RatekWH", 0))
                energy_charge += usage_kwh * rate
            except (TypeError, ValueError):
                continue

        breakdown["Energy Charges"] = energy_charge
        total_cost += energy_charge

        # --- DEMAND CHARGES ---
        demand_data = supabase.table("Demand_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        demand_charge = 0.0
        for row in demand_data:
            try:
                rate = float(row.get("RatekW", 0))
                demand_charge += demand_kw * rate
            except (TypeError, ValueError):
                continue
        breakdown["Demand Charges"] = demand_charge
        total_cost += demand_charge

        # --- SERVICE CHARGES ---
        service_data = supabase.table("ServiceCharge_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        service_charge = 0.0
        for row in service_data:
            try:
                rate = float(row.get("Rate", 0))
                service_charge += rate * (billing_days / 30)
            except (TypeError, ValueError):
                continue
        breakdown["Service Charges"] = service_charge
        total_cost += service_charge

        # --- OTHER CHARGES ---
        other_data = supabase.table("OtherCharges_Table").select("*").eq("ScheduleID", schedule_id).execute().data
        other_charge = 0.0

        for row in other_data:
            try:
                desc = row.get("Description", "").lower()
                unit = row.get("ChargeUnit", "").lower()
                charge = float(row.get("ChargeType", 0))  # No ChargeAmount, assume ChargeType is the $ amount

                if "low-income" in desc and "per meter" in unit:
                    other_charge += charge  # Assume 1 meter for now

                # Add more mappings here as needed
            except Exception:
                continue

        breakdown["Other Charges"] = other_charge
        total_cost += other_charge

        return jsonify({
            "total_cost": round(total_cost, 2),
            "breakdown": {k: round(v, 2) for k, v in breakdown.items()}
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
