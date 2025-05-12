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

def get_states_with_utilities(supabase):
    """Get list of states that have utilities with rate schedules."""
    try:
        # Get all utilities that have schedules
        utilities_with_schedules = supabase.from_("Schedule_Table").select("UtilityID").execute()
        utility_ids = [item['UtilityID'] for item in utilities_with_schedules.data]
        
        # If there are utilities with schedules, get the states
        if utility_ids:
            states_response = supabase.from_("Utility").select("State").in_("UtilityID", utility_ids).execute()
            states_data = states_response.data
            
            # Extract unique states and sort them
            states = sorted(list(set([state["State"] for state in states_data if state["State"]])))
            return states
        else:
            return []
    except Exception as e:
        st.error(f"Error loading states: {str(e)}")
        return []

def get_utilities_by_state(supabase, state):
    """Get utilities in a specific state that have rate schedules."""
    try:
        # Get utilities in the selected state that have schedules
        utilities_with_schedules = supabase.from_("Schedule_Table").select("UtilityID").execute()
        utility_ids = [item['UtilityID'] for item in utilities_with_schedules.data]
        
        if utility_ids:
            utilities_response = supabase.from_("Utility").select("UtilityID, UtilityName").eq("State", state).in_("UtilityID", utility_ids).execute()
            return utilities_response.data
        else:
            return []
    except Exception as e:
        st.error(f"Error loading utilities: {str(e)}")
        return []

def get_schedules_by_utility(supabase, utility_id):
    """Get rate schedules for a specific utility."""
    try:
        schedules_response = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName, ScheduleDescription").eq("UtilityID", utility_id).execute()
        return schedules_response.data
    except Exception as e:
        st.error(f"Error loading schedules: {str(e)}")
        return []

def check_energy_charges(supabase, schedule_id):
    """Check if a schedule has energy charges."""
    try:
        # Check standard energy rates
        energy_response = supabase.from_("Energy_Table").select("id").eq("ScheduleID", schedule_id).execute()
        # Check time-of-use energy rates
        energy_time_response = supabase.from_("EnergyTime_Table").select("id").eq("ScheduleID", schedule_id).execute()
        # Check incremental energy rates
        incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("id").eq("ScheduleID", schedule_id).execute()
        
        return (
            len(energy_response.data) > 0 or 
            len(energy_time_response.data) > 0 or 
            len(incremental_energy_response.data) > 0
        )
    except Exception as e:
        st.error(f"Error checking energy charges: {str(e)}")
        return False

def check_demand_charges(supabase, schedule_id):
    """Check if a schedule has demand charges."""
    try:
        # Check standard demand rates
        demand_response = supabase.from_("Demand_Table").select("id").eq("ScheduleID", schedule_id).execute()
        # Check time-of-use demand rates
        demand_time_response = supabase.from_("DemandTime_Table").select("id").eq("ScheduleID", schedule_id).execute()
        # Check incremental demand rates
        incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("id").eq("ScheduleID", schedule_id).execute()
        
        return (
            len(demand_response.data) > 0 or 
            len(demand_time_response.data) > 0 or 
            len(incremental_demand_response.data) > 0
        )
    except Exception as e:
        st.error(f"Error checking demand charges: {str(e)}")
        return False

def check_reactive_demand(supabase, schedule_id):
    """Check if a schedule has reactive demand charges."""
    try:
        reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("id").eq("ScheduleID", schedule_id).execute()
        return len(reactive_demand_response.data) > 0
    except Exception as e:
        st.error(f"Error checking reactive demand: {str(e)}")
        return False

def get_tou_periods(supabase, schedule_id):
    """Get time-of-use periods for a schedule if it has TOU energy rates."""
    try:
        energy_time_response = supabase.from_("EnergyTime_Table").select("id").eq("ScheduleID", schedule_id).execute()
        
        if len(energy_time_response.data) > 0:
            tou_response = supabase.from_("EnergyTime_Table").select("Description, TimeOfDay").eq("ScheduleID", schedule_id).execute()
            
            # Get unique TOU periods
            tou_periods = []
            seen_periods = set()
            
            for period in tou_response.data:
                description = period.get("Description", "")
                time_of_day = period.get("TimeOfDay", "")
                
                period_key = f"{description} ({time_of_day})"
                if period_key not in seen_periods:
                    tou_periods.append({
                        "description": description,
                        "timeofday": time_of_day,
                        "display": period_key
                    })
                    seen_periods.add(period_key)
            
            return tou_periods, True
        else:
            return [], False
    except Exception as e:
        st.error(f"Error getting TOU periods: {str(e)}")
        return [], False
