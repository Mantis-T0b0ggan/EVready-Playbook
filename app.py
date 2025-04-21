import os
from supabase import create_client, Client
from dotenv import load_dotenv
from flask import Flask, render_template, request

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

if __name__ == "__main__":
    app.run(debug=True)
