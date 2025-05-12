"""
RateAcuity API client functions for the Rate Importer application.
Handles all interactions with the RateAcuity API.
"""

import os
import requests
import streamlit as st

# Base URL for RateAcuity API
BASE_URL = "https://secure.rateacuity.com/RateAcuityJSONAPI/api"

def get_api_credentials():
    """
    Get RateAcuity API credentials from Streamlit secrets.
    
    Returns:
        tuple: (username, password) for API authentication
    """
    # Try to get from Streamlit secrets first
    try:
        username = st.secrets["RATEACUITY_USERNAME"]
        password = st.secrets["RATEACUITY_PASSWORD"]
    except Exception:
        # Fall back to environment variables
        username = os.getenv("RATEACUITY_USERNAME")
        password = os.getenv("RATEACUITY_PASSWORD")
        
    return username, password

def get_utilities(state_code=None):
    """
    Get utilities from RateAcuity API, optionally filtered by state.
    
    Args:
        state_code (str, optional): Two-letter state code
        
    Returns:
        list: List of utility data dictionaries
    """
    username, password = get_api_credentials()
    
    if not username or not password:
        st.error("RateAcuity credentials not found. Please set RATEACUITY_USERNAME and RATEACUITY_PASSWORD.")
        return []
    
    # Build URL based on whether state_code is provided
    url = f"{BASE_URL}/utility"
    if state_code:
        url = f"{BASE_URL}/utility/{state_code}"
    
    # Prepare parameters for authentication
    params = {
        "p1": username,
        "p2": password
    }
    
    try:
        response = requests.get(url, params=params)
        
        # Ensure successful response
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Extract utilities from response
        utilities = data.get("Utility", [])
        return utilities
    except Exception as e:
        st.error(f"Error fetching utilities: {str(e)}")
        return []

def get_schedules_by_utility(utility_id):
    """
    Get schedules for a specific utility from RateAcuity API.
    
    Args:
        utility_id (str): Utility ID from RateAcuity
        
    Returns:
        list: List of schedule data dictionaries
    """
    username, password = get_api_credentials()
    
    if not username or not password:
        st.error("RateAcuity credentials not found.")
        return []
    
    url = f"{BASE_URL}/schedule/{utility_id}"
    params = {
        "p1": username,
        "p2": password
    }
    
    try:
        response = requests.get(url, params=params)
        
        # Ensure successful response
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Extract schedules from response
        schedules = data.get("Schedule", [])
        return schedules
    except Exception as e:
        st.error(f"Error fetching schedules: {str(e)}")
        return []

def get_schedule_detail(schedule_id):
    """
    Get detailed information for a specific schedule from RateAcuity API.
    
    Args:
        schedule_id (str): Schedule ID from RateAcuity
        
    Returns:
        dict: Schedule detail data
    """
    username, password = get_api_credentials()
    
    if not username or not password:
        st.error("RateAcuity credentials not found.")
        return {}
    
    url = f"{BASE_URL}/scheduledetailtip/{schedule_id}"
    params = {
        "p1": username,
        "p2": password
    }
    
    try:
        response = requests.get(url, params=params)
        
        # Ensure successful response
        response.raise_for_status()
        
        # Parse JSON response
        detail_list = response.json()
        
        if not detail_list or not isinstance(detail_list, list) or len(detail_list) == 0:
            raise ValueError("Unexpected response format from API")
        
        return detail_list[0]  # First item contains the details
    except Exception as e:
        st.error(f"Error fetching schedule details: {str(e)}")
        return {}
