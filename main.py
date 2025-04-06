import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables (used locally only)
load_dotenv()

# --- Load Secrets from Environment ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USERNAME = os.getenv("RATEACUITY_USERNAME")
PASSWORD = os.getenv("RATEACUITY_PASSWORD")

# --- Validate secrets ---
if not all([SUPABASE_URL, SUPABASE_KEY, USERNAME, PASSWORD]):
    raise ValueError("One or more environment variables are missing.")

# --- Initialize Supabase client ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Set up RateAcuity request ---
API_URL = "https://secure.rateacuity.com/RateAcuityJSONAPI/api/utility/MA"
params = {"p1": USERNAME, "p2": PASSWORD}

try:
    response = requests.get(API_URL, params=params)
    print("Status code:", response.status_code)

    # TEMP: log the raw response
    print("Raw response text:")
    print(response.text)

    response.raise_for_status()
    utilities = response.json()

    if not utilities:
        raise ValueError("RateAcuity returned no data or invalid format.")

    # --- Filter for Eversource only ---
    filtered_utilities = [
        u for u in utilities
        if u.get("State") == "MA" and "Eversource" in u.get("UtilityName", "")
    ]

    print(f"Filtered down to {len(filtered_utilities)} Eversource utilities in MA")

    # --- Upsert into Supabase ---
    for util in filtered_utilities:
        utility_id = util.get("UtilityID")
        utility_name = util.get("UtilityName")
        state = util.get("State")

        if not utility_id or not utility_name:
            continue  # Skip incomplete entries

        data = {
            "UtilityID": utility_id,
            "UtilityName": utility_name,
            "State": state
        }

        result = supabase.table("Utility").upsert(data).execute()
        print(f"Upserted: {utility_id} - {utility_name}")

except Exception as e:
    print("Unexpected error:", e)
