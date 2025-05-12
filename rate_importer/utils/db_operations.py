"""
Database operations for the Rate Importer application.
Handles interactions with the Supabase database for storing utility rate data.
"""

import streamlit as st

def insert_utilities(supabase, utilities, state_code):
    """
    Insert or update utilities in the Supabase database.
    
    Args:
        supabase: Supabase client
        utilities (list): List of utility data dictionaries
        state_code (str): Two-letter state code
        
    Returns:
        dict: Results summary
    """
    if not utilities:
        return {
            "message": f"No utilities returned for state {state_code}.",
            "inserted": 0,
            "failed": 0
        }
    
    inserted = 0
    failed = 0
    
    for utility in utilities:
        try:
            utility_data = {
                "UtilityID": utility["UtilityID"],
                "UtilityName": utility["UtilityName"],
                "State": state_code
            }
            
            # Use upsert to insert or update
            supabase.table("Utility").upsert(utility_data).execute()
            inserted += 1
        except Exception as e:
            st.error(f"Failed to insert UtilityID {utility.get('UtilityID')}: {e}")
            failed += 1
    
    return {
        "message": f"Loaded {inserted} utilities for state {state_code}.",
        "inserted": inserted,
        "failed": failed
    }

def insert_schedules(supabase, schedules, utility_id):
    """
    Insert or update schedules in the Supabase database.
    
    Args:
        supabase: Supabase client
        schedules (list): List of schedule data dictionaries
        utility_id (str): Utility ID from RateAcuity
        
    Returns:
        dict: Results summary
    """
    if not schedules:
        return {
            "message": f"No schedules returned for Utility {utility_id}.",
            "inserted": 0,
            "failed": 0
        }
    
    inserted = 0
    failed = 0
    
    numeric_fields = ["MinDemand", "MaxDemand", "MinUsage", "MaxUsage"]
    timestamp_fields = ["EffectiveDate"]
    
    for schedule in schedules:
        try:
            # Ensure utility ID is present and properly formatted
            schedule["UtilityID"] = int(utility_id)
            
            # Clean up empty fields
            for field in numeric_fields + timestamp_fields:
                if field in schedule and schedule[field] == "":
                    schedule[field] = None
            
            # Clean up numeric fields that contain text (like "80 MW")
            for field in numeric_fields:
                if field in schedule and schedule[field]:
                    try:
                        # Extract the numeric part
                        value = schedule[field]
                        if isinstance(value, str):
                            # Remove any non-numeric characters except decimal point
                            # This assumes the numeric value comes first
                            import re
                            numeric_part = re.match(r'^\s*(\d+(?:\.\d+)?)', value)
                            if numeric_part:
                                schedule[field] = float(numeric_part.group(1))
                            else:
                                schedule[field] = None
                    except (ValueError, TypeError):
                        # If conversion fails, set to None
                        schedule[field] = None
            
            # Use upsert to insert or update
            supabase.table("Schedule_Table").upsert(schedule).execute()
            inserted += 1
        except Exception as e:
            st.error(f"Failed to insert ScheduleID {schedule.get('ScheduleID')} for UtilityID {utility_id}: {e}")
            failed += 1
    
    return {
        "message": f"Loaded {inserted} schedule(s) for Utility {utility_id}.",
        "inserted": inserted,
        "failed": failed
    }

def insert_schedule_details(supabase, detail_data, schedule_id):
    """
    Insert or update schedule details in the Supabase database.
    
    Args:
        supabase: Supabase client
        detail_data (dict): Schedule detail data dictionary
        schedule_id (str): Schedule ID from RateAcuity
        
    Returns:
        dict: Results summary
    """
    if not detail_data:
        return {
            "message": f"No detail data returned for Schedule {schedule_id}.",
            "inserted": 0,
            "skipped": 0
        }
    
    inserted_count = 0
    skipped_count = 0
    
    # Tables we want to process from the detail data
    allowed_tables = [
        "EnergyTime_Table",
        "DemandTime_Table",
        "ServiceCharge_Table",
        "OtherCharges_Table",
        "RateAdjustment_Table",
        "Tax_Table"
    ]
    
    for table_name, records in detail_data.items():
        if table_name not in allowed_tables:
            st.info(f"Skipping unknown table: {table_name}")
            continue
        
        if not records:
            continue
        
        for record in records:
            try:
                # Add schedule ID to the record
                record["ScheduleID"] = schedule_id
                
                # Clean up empty values
                for key in record:
                    if record[key] == "":
                        record[key] = None
                
                # Use upsert to insert or update
                supabase.table(table_name).upsert(record).execute()
                inserted_count += 1
            except Exception as e:
                st.error(f"Failed to upsert into {table_name}: {e}")
                skipped_count += 1
    
    return {
        "message": f"Inserted/Updated {inserted_count} records for Schedule {schedule_id}.",
        "inserted": inserted_count,
        "skipped": skipped_count
    }

def get_utilities_from_database(supabase, state_code=None):
    """
    Retrieve utilities from the database, optionally filtered by state.
    
    Args:
        supabase: Supabase client
        state_code (str, optional): Two-letter state code
        
    Returns:
        list: List of utility records
    """
    try:
        query = supabase.table("Utility").select("UtilityID, UtilityName, State")
        
        if state_code:
            query = query.eq("State", state_code)
        
        response = query.execute()
        
        return response.data
    except Exception as e:
        st.error(f"Error retrieving utilities: {str(e)}")
        return []

def get_schedules_from_database(supabase, utility_id):
    """
    Retrieve schedules from the database for a specific utility.
    
    Args:
        supabase: Supabase client
        utility_id (str): Utility ID
        
    Returns:
        list: List of schedule records
    """
    try:
        response = supabase.table("Schedule_Table") \
            .select("ScheduleID, ScheduleName, ScheduleDescription") \
            .eq("UtilityID", utility_id) \
            .execute()
        
        return response.data
    except Exception as e:
        st.error(f"Error retrieving schedules: {str(e)}")
        return []
