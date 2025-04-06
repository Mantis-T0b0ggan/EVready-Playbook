import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

# --- ENVIRONMENT VARIABLES ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
USERNAME = os.getenv("RATEACUITY_USERNAME")
PASSWORD = os.getenv("RATEACUITY_PASSWORD")

# --- CHECK FOR MISSING CONFIG ---
if not all([SUPABASE_URL, SUPABASE_KEY, USERNAME, PASSWORD]):
    raise ValueError("Missing one or more environment variables. Please check your .env file.")

# --- INITIALIZE SUPABASE CLIENT ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- RATEACUITY API REQUEST FOR MA UTILITIES ---
API_URL = "https://secure.rateacuity.com/RateAcuityJSONAPI/api/utility/MA"
params = {"p1": USERNAME, "p2": PASSWORD}

try:
    response = requests.get(API_URL, params=params)
    response.raise_for_status()  # raise an error for bad status codes
    utilities = response.json()

    print(f"Fetched {len(utilities)} utilities from RateAcuity for MA.")

    for util in utilities:
        utility_id = util.get("UtilityID")
        utility_name = util.get("UtilityName")
        state = util.get("State")

        if not utility_id or not utility_name:
            continue  # Skip invalid records

        data = {
            "UtilityID": utility_id,
            "UtilityName": utility_name,
            "State": state
        }

        result = supabase.table("Utility").upsert(data).execute()
        print(f"Upserted: {utility_id} - {utility_name}")

except requests.RequestException as e:
    print(f"Failed to fetch data from RateAcuity: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
