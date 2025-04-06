import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables locally
load_dotenv()

# Get credentials from env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USERNAME = os.getenv("RATEACUITY_USERNAME")
PASSWORD = os.getenv("RATEACUITY_PASSWORD")

# Validate environment
if not all([SUPABASE_URL, SUPABASE_KEY, USERNAME, PASSWORD]):
    raise ValueError("Missing one or more environment variables")

# Init Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Call the generic /utility endpoint (no state filter)
API_URL = "https://secure.rateacuity.com/RateAcuityJSONAPI/api/utility"
params = {"p1": USERNAME, "p2": PASSWORD}

try:
    response = requests.get(API_URL, params=params)
    print("Status code:", response.status_code)
    print("Raw response preview (first 500 chars):")
    print(response.text[:500])  # Short preview only

    response.raise_for_status()
    utilities = response.json()

    if not utilities or not isinstance(utilities, list):
        raise ValueError("RateAcuity returned no data or unexpected format.")

    # Filter for Eversource in MA
    filtered_utilities = [
        u for u in utilities
        if u.get("State") == "MA" and "Eversource" in u.get("UtilityName", "")
    ]

    print(f"Found {len(filtered_utilities)} Eversource utilities in MA.")

    for util in filtered_utilities:
        utility_id = util.get("UtilityID")
        utility_name = util.get("UtilityName")
        state = util.get("State")

        if not utility_id or not utility_name:
            continue  # Skip if incomplete

        data = {
            "UtilityID": utility_id,
            "UtilityName": utility_name,
            "State": state
        }

        result = supabase.table("Utility").upsert(data).execute()
        print(f"Upserted: {utility_id} - {utility_name}")

except Exception as e:
    print("Unexpected error:", e)
