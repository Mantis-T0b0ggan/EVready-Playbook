import os
import math
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables from .env file if it exists (for local development)
# Otherwise, rely on environment variables set in the deployment platform
load_dotenv()

# Get credentials with fallbacks
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Verify credentials are available
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials not found. Please check your environment variables.")
    st.stop()  # Stop execution if credentials are missing

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure page settings
st.set_page_config(
    page_title="EVready Playbook",
    page_icon="⚡",
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Rest of your code continues here...
