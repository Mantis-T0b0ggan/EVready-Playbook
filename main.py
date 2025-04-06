import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load .env variables (locally or from GitHub Secrets)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USERNAME = os.getenv("RATEACUITY_USERNAME")
PASSWORD = os.getenv("RATEACUITY_PASSWORD")

if not all([SUPABASE_URL, SUPABASE_KEY, USERNAME, PASSWORD]):
    raise ValueError("Missing one or more environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Pull MA utilities
API_URL = "https://secure.rateacuity.com/RateAcuityJSONAPI/api/utility/MA"
params = {"p1": USERNAME, "p2": PASSWORD}

try:
    response = requests.get(API_URL, params=params)
    print("Status code:", response.status_code)
    response.raise_for_status()

    data = response.json()
    utilities = data.get("Utility", [])

    if not utilities:
        raise ValueError("No utilities returned in response.")

    # Filter for Eversource and National Grid
    filtered_utilities = [
        u for u in utilities
        if "Eversource" in u["UtilityName"] or "National Grid" in u["UtilityName"]
    ]

    print(f"Found {len(filtered_utilities)} Eversource/National Grid utilities in MA.")

    for util in filtered_utilities:
        data = {
            "UtilityID": util["UtilityID"],
            "UtilityName": util["UtilityName"],
            "State": util["State"]
        }
        result = supabase.table("Utility").upsert(data).execute()
        print(f"Upserted: {data}")

except Exception as e:
    print("Unexpected error:", e)
