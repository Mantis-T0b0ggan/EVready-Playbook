import os
import requests
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file (for local runs)
load_dotenv()

SUPABASE_URL = os.getenv("https://woylxuwhzlbkufgklcto.supabase.co")
SUPABASE_KEY = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndveWx4dXdoemxia3VmZ2tsY3RvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDM1NDgxMTgsImV4cCI6MjA1OTEyNDExOH0.9bt8CQQcVTp01jCbJeuvhsB7oNlaLI63W6uEPOHNYiE")
USERNAME = os.getenv("martin@opt-apps.com")
PASSWORD = os.getenv("Power200")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

API_URL = "https://secure.rateacuity.com/RateAcuityJSONAPI/api/utility/CT"

response = requests.get(API_URL, params={"p1": USERNAME, "p2": PASSWORD})

if response.status_code == 200:
    utilities = response.json()
    for util in utilities:
        utility_id = util.get("UtilityID")
        utility_name = util.get("UtilityName")
        state = util.get("State")

        data = {
            "UtilityID": utility_id,
            "UtilityName": utility_name,
            "State": state
        }

        result = supabase.table("Utility").upsert(data).execute()
        print(f"Inserted: {utility_id} - {utility_name}")
else:
    print(f"Failed to fetch data: {response.status_code} - {response.text}")

