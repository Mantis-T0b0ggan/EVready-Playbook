import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

def initialize_database():
    """Initialize Supabase client and handle connection errors."""
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    # Try to get credentials from Streamlit secrets first, then environment variables
    try:
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    except Exception:
        # Fall back to environment variables
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    # Verify credentials
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ Supabase credentials not found. Please check your environment variables or Streamlit secrets.")
        st.info("This app requires Supabase credentials to function. Please set up your credentials and try again.")
        return None
    
    try:
        # Initialize Supabase client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
    except Exception as e:
        st.error(f"⚠️ Failed to connect to Supabase: {str(e)}")
        st.info("Please check your credentials and make sure your Supabase project is running.")
        return None
