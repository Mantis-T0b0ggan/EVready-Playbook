import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USERNAME = os.getenv("RATEACUITY_USERNAME")
PASSWORD = os.getenv("RATEACUITY_PASSWORD")

if not all([SUPABASE_URL, SUPABASE_KEY, USERNAME, PASSWORD]):
    raise ValueError("Missing one or more environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

API_URL = "https://secure.rateacuity.com/RateAcuityJSONAPI/api/utility/MA"
params = {"p1": USERNAME, "p2": PASSWORD}

try:
    response = requests.get(API_URL, params=params)
    print("Status code:", response.status_code)
    print("Raw response text preview:")
    print(response.text[:500])  # Preview response

    response.raise_for_status()

    try:
        data = response.json()
    except Exception as json_error:
        raise ValueError(f"Failed to parse JSON: {json_error}")

    if not data or "Utility" not in data:
        raise ValueError("No 'Utility' key in API response or response is null.")

    utilities = data["Utility"]

    # Filter for Eversource + National Grid + Western MA Electric
    filtered_utilities = [
        u for u in utilities
        if any(name in u["UtilityName"] for name in [
            "Eversource",
            "National Grid",
            "Western Massachusetts Electric Company"
        ])
    ]

    print(f"Found {len(filtered_utilities)} matching utilities in MA.")

    for util in filtered_utilities:
        data = {
            "UtilityID": util["UtilityID"],
            "UtilityName": util["UtilityName"],
            "State": util["State"]
        }
        supabase.table("Utility").upsert(data).execute()
        print(f"Upserted: {data}")

except Exception as e:
    print("Unexpected error:", e)
