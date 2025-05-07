import os
import math
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Configure page settings first (must be the first Streamlit command)
st.set_page_config(
    page_title="EVready Playbook",
    page_icon="⚡",
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Load environment variables from .env file if it exists (for local development)
# Otherwise, rely on environment variables set in the deployment platform
load_dotenv()

# Try to get credentials from Streamlit secrets first, then fall back to environment variables
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    # Fall back to environment variables
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Verify credentials and initialize Supabase client
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Supabase credentials not found. Please check your environment variables or Streamlit secrets.")
    st.info("This app requires Supabase credentials to function. Please set up your credentials and try again.")
    st.stop()  # This will prevent the rest of the app from running

try:
    # Initialize Supabase client with error handling
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"⚠️ Failed to connect to Supabase: {str(e)}")
    st.info("Please check your credentials and make sure your Supabase project is running.")
    st.stop()

# Main app title with logo - centered above the title
st.markdown(
    """
    <div style='display: flex; justify-content: center; margin-bottom: 1rem;'>
        <div style='width: 300px; text-align: center;'>
    """, 
    unsafe_allow_html=True
)

# Display logo image
try:
    # Display logo with increased width
    st.image("logo.png", width=300)
except Exception as e:
    # If loading fails, show warning
    st.warning("Note: Company logo could not be loaded. Please ensure logo.png exists in the app directory.")

st.markdown("</div></div>", unsafe_allow_html=True)

# Title centered on the page
st.markdown("<h1 style='text-align: center;'>Utility Rate Analysis Tool</h1>", unsafe_allow_html=True)

# Add reset button at the top of the app
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("Reset All"):
        # Clear all session state variables
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

# Initialize session state variables
if 'bill_calculated' not in st.session_state:
    st.session_state.bill_calculated = False
if 'current_bill' not in st.session_state:
    st.session_state.current_bill = None
if 'comparison_results' not in st.session_state:
    st.session_state.comparison_results = []
if 'bill_df' not in st.session_state:
    st.session_state.bill_df = None

# Create tabs for different functionalities
tab1, tab2 = st.tabs(["Bill Estimation & Comparison", "Schedule Browser"])

# Function to calculate the bill for the current schedule
def calculate_current_bill(supabase, schedule_id, schedule_name, usage_kwh, usage_by_tou, demand_kw, power_factor, billing_month, has_energy_charges, has_demand_charges, has_reactive_demand):
    """Calculate full bill breakdown for the current schedule."""
    
    # 1. Get service charges
    service_charge = 0.0
    service_charge_breakdown = []
    
    try:
        service_charge_response = supabase.from_("ServiceCharge_Table").select("Description, Rate, ChargeUnit").eq("ScheduleID", schedule_id).execute()
        
        for charge in service_charge_response.data:
            rate = float(charge.get("Rate", 0)) if charge.get("Rate") is not None else 0.0
            description = charge.get("Description", "Service Charge")
            unit = charge.get("ChargeUnit", "")
            
            service_charge += rate
            service_charge_breakdown.append({
                "Description": f"{description} ({unit})",
                "Amount": rate
            })
    except Exception as e:
        st.warning(f"Error getting service charges: {str(e)}")
    
    # 2. Calculate energy charges
    energy_charge = 0.0
    energy_charges_breakdown = []
    
    if has_energy_charges and usage_kwh:
        try:
            # Check standard energy rates (Energy_Table)
            energy_response = supabase.from_("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            for rate in energy_response.data:
                try:
                    rate_kwh = float(rate.get("RatekWh", 0)) if rate.get("RatekWh") is not None else 0.0
                    min_v = float(rate.get("MinkV", 0)) if rate.get("MinkV") is not None else 0.0
                    max_v = float(rate.get("MaxkV")) if rate.get("MaxkV") is not None else float('inf')
                    description = rate.get("Description", "Energy Charge")
                    determinant = rate.get("Determinant", "")
                    
                    # Check if usage falls within this rate's range
                    if min_v <= usage_kwh <= max_v:
                        charge_amount = rate_kwh * usage_kwh
                        energy_charge += charge_amount
                        energy_charges_breakdown.append({
                            "Description": f"{description} ({rate_kwh:.4f} $/kWh)",
                            "Amount": charge_amount
                        })
                except (ValueError, TypeError) as e:
                    st.warning(f"Error processing energy rate: {str(e)}")
            
            # Check incremental/tiered energy rates (IncrementalEnergy_Table)
            incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            if incremental_energy_response.data:
                # Sort tiers by StartkWh to ensure proper order
                try:
                    tiers = sorted(incremental_energy_response.data, 
                                  key=lambda x: float(x.get("StartkWh", 0)) if x.get("StartkWh") is not None else 0.0)
                    
                    remaining_kwh = usage_kwh
                    for tier in tiers:
                        rate_kwh = float(tier.get("RatekWh", 0)) if tier.get("RatekWh") is not None else 0.0
                        start_kwh = float(tier.get("StartkWh", 0)) if tier.get("StartkWh") is not None else 0.0
                        end_kwh = float(tier.get("EndkWh")) if tier.get("EndkWh") is not None else float('inf')
                        description = tier.get("Description", "Tiered Energy Charge")
                        season = tier.get("Season", "")
                        
                        # Check if we're in the right season (if specified)
                        if season and billing_month:
                            # Simple season check - can be enhanced for more complex seasonal definitions
                            summer_months = ["June", "July", "August", "September"]
                            winter_months = ["December", "January", "February", "March"]
                            
                            if (season.lower() == "summer" and billing_month not in summer_months) or \
                               (season.lower() == "winter" and billing_month not in winter_months):
                                continue
                        
                        # Calculate tier usage and charge
                        tier_usage = min(max(0, remaining_kwh - start_kwh), end_kwh - start_kwh)
                        
                        if tier_usage > 0:
                            tier_charge = tier_usage * rate_kwh
                            energy_charge += tier_charge
                            energy_charges_breakdown.append({
                                "Description": f"{description} ({start_kwh}-{end_kwh if end_kwh != float('inf') else '∞'} kWh @ {rate_kwh:.4f} $/kWh)",
                                "Amount": tier_charge
                            })
                            
                            remaining_kwh -= tier_usage
                            if remaining_kwh <= 0:
                                break
                except (ValueError, TypeError) as e:
                    st.warning(f"Error processing tiered energy rates: {str(e)}")
            
            # Check time-of-use energy rates (EnergyTime_Table)
            energy_time_response = supabase.from_("EnergyTime_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            if energy_time_response.data and len(energy_time_response.data) > 0:
                try:
                    # If user specified TOU breakdown, use it
                    if usage_by_tou:
                        for period in energy_time_response.data:
                            rate_kwh = float(period.get("RatekWh", 0)) if period.get("RatekWh") is not None else 0.0
                            description = period.get("Description", "Time-of-Use Energy")
                            time_of_day = period.get("TimeOfDay", "")
                            season = period.get("Season", "")
                            
                            # Format period key to match usage_by_tou keys
                            period_key = f"{description} ({time_of_day})"
                            
                            # Check if we're in the right season (if specified)
                            if season and billing_month:
                                # Simple season check
                                summer_months = ["June", "July", "August", "September"]
                                winter_months = ["December", "January", "February", "March"]
                                
                                if (season.lower() == "summer" and billing_month not in summer_months) or \
                                   (season.lower() == "winter" and billing_month not in winter_months):
                                    continue
                            
                            # Use the specified usage for this period if available
                            period_usage = usage_by_tou.get(period_key, 0)
                            
                            if period_usage > 0:
                                period_charge = rate_kwh * period_usage
                                energy_charge += period_charge
                                energy_charges_breakdown.append({
                                    "Description": f"{description} ({time_of_day}, {rate_kwh:.4f} $/kWh)",
                                    "Amount": period_charge
                                })
                    else:
                        # If no TOU breakdown provided, distribute usage evenly
                        time_periods = energy_time_response.data
                        num_periods = len(time_periods)
                        usage_per_period = usage_kwh / num_periods if num_periods > 0 else 0
                        
                        for period in time_periods:
                            rate_kwh = float(period.get("RatekWh", 0)) if period.get("RatekWh") is not None else 0.0
                            description = period.get("Description", "Time-of-Use Energy")
                            time_of_day = period.get("TimeOfDay", "")
                            season = period.get("Season", "")
                            
                            # Check if we're in the right season (if specified)
                            if season and billing_month:
                                # Simple season check
                                summer_months = ["June", "July", "August", "September"]
                                winter_months = ["December", "January", "February", "March"]
                                
                                if (season.lower() == "summer" and billing_month not in summer_months) or \
                                   (season.lower() == "winter" and billing_month not in winter_months):
                                    continue
                            
                            period_charge = rate_kwh * usage_per_period
                            energy_charge += period_charge
                            energy_charges_breakdown.append({
                                "Description": f"{description} ({time_of_day}, {rate_kwh:.4f} $/kWh)",
                                "Amount": period_charge
                            })
                except (ValueError, TypeError) as e:
                    st.warning(f"Error processing time-of-use rates: {str(e)}")
            
        except Exception as e:
            st.warning(f"Error calculating energy charges: {str(e)}")
    
    # 3. Calculate demand charges
    demand_charge = 0.0
    demand_charges_breakdown = []
    
    if has_demand_charges and demand_kw:
        try:
            # Check standard demand rates (Demand_Table)
            demand_response = supabase.from_("Demand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            for rate in demand_response.data:
                try:
                    rate_kw = float(rate.get("RatekW", 0)) if rate.get("RatekW") is not None else 0.0
                    min_kv = float(rate.get("MinkV", 0)) if rate.get("MinkV") is not None else 0.0
                    max_kv = float(rate.get("MaxkV")) if rate.get("MaxkV") is not None else float('inf')
                    description = rate.get("Description", "Demand Charge")
                    determinant = rate.get("Determinant", "")
                    
                    # Check if demand falls within this rate's range
                    if min_kv <= demand_kw <= max_kv:
                        charge_amount = rate_kw * demand_kw
                        demand_charge += charge_amount
                        demand_charges_breakdown.append({
                            "Description": f"{description} ({rate_kw:.2f} $/kW)",
                            "Amount": charge_amount
                        })
                except (ValueError, TypeError) as e:
                    st.warning(f"Error processing demand rate: {str(e)}")
            
            # Check time-of-use demand rates (DemandTime_Table)
            demand_time_response = supabase.from_("DemandTime_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            if demand_time_response.data and len(demand_time_response.data) > 0:
                try:
                    # For simplicity, we'll use the highest demand rate for now
                    # In a real implementation, you'd need user input for demand during specific time periods
                    
                    # Convert all RatekW values to floats, filtering out None values
                    rates_kw = [float(rate.get("RatekW", 0)) if rate.get("RatekW") is not None else 0.0 
                               for rate in demand_time_response.data]
                    
                    if rates_kw:  # Check if the list is not empty
                        highest_rate_kw = max(rates_kw)
                        highest_rate_index = rates_kw.index(highest_rate_kw)
                        highest_rate = demand_time_response.data[highest_rate_index]
                        
                        rate_kw = highest_rate_kw
                        description = highest_rate.get("Description", "Time-of-Use Demand")
                        time_of_day = highest_rate.get("TimeOfDay", "")
                        season = highest_rate.get("Season", "")
                        
                        # Check if we're in the right season (if specified)
                        if not season or not billing_month or \
                           (season.lower() == "summer" and billing_month in ["June", "July", "August", "September"]) or \
                           (season.lower() == "winter" and billing_month in ["December", "January", "February", "March"]):
                            
                            period_charge = rate_kw * demand_kw
                            demand_charge += period_charge
                            demand_charges_breakdown.append({
                                "Description": f"{description} ({time_of_day}, {rate_kw:.2f} $/kW)",
                                "Amount": period_charge
                            })
                except (ValueError, TypeError) as e:
                    st.warning(f"Error processing time-of-use demand rates: {str(e)}")
            
            # Check incremental/tiered demand rates (IncrementalDemand_Table)
            incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            if incremental_demand_response.data:
                try:
                    # Sort tiers by StepMin to ensure proper order
                    tiers = sorted(incremental_demand_response.data, 
                                key=lambda x: float(x.get("StepMin", 0)) if x.get("StepMin") is not None else 0.0)
                    
                    remaining_kw = demand_kw
                    for tier in tiers:
                        rate_kw = float(tier.get("RatekW", 0)) if tier.get("RatekW") is not None else 0.0
                        step_min = float(tier.get("StepMin", 0)) if tier.get("StepMin") is not None else 0.0
                        step_max = float(tier.get("StepMax")) if tier.get("StepMax") is not None else float('inf')
                        description = tier.get("Description", "Tiered Demand Charge")
                        
                        # Calculate tier usage and charge
                        tier_usage = min(max(0, remaining_kw - step_min), step_max - step_min)
                        
                        if tier_usage > 0:
                            tier_charge = tier_usage * rate_kw
                            demand_charge += tier_charge
                            demand_charges_breakdown.append({
                                "Description": f"{description} ({step_min}-{step_max if step_max != float('inf') else '∞'} kW @ {rate_kw:.2f} $/kW)",
                                "Amount": tier_charge
                            })
                            
                            remaining_kw -= tier_usage
                            if remaining_kw <= 0:
                                break
                except (ValueError, TypeError) as e:
                    st.warning(f"Error processing tiered demand rates: {str(e)}")
            
            # Check reactive demand charges (ReactiveDemand_Table)
            reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            if reactive_demand_response.data and demand_kw > 0:
                try:
                    # Calculate reactive demand based on power factor
                    # Formula: reactive_power = active_power * tan(acos(power_factor))
                    reactive_kvar = demand_kw * math.tan(math.acos(power_factor))
                    
                    for rate in reactive_demand_response.data:
                        rate_value = float(rate.get("Rate", 0)) if rate.get("Rate") is not None else 0.0
                        min_val = float(rate.get("Min", 0)) if rate.get("Min") is not None else 0.0
                        max_val = float(rate.get("Max")) if rate.get("Max") is not None else float('inf')
                        description = rate.get("Description", "Reactive Demand Charge")
                        
                        # Check if reactive demand falls within this rate's range
                        if min_val <= reactive_kvar <= max_val:
                            charge_amount = rate_value * reactive_kvar
                            demand_charge += charge_amount
                            demand_charges_breakdown.append({
                                "Description": f"{description} ({rate_value:.2f} $/kVAR, PF={power_factor:.2f})",
                                "Amount": charge_amount
                            })
                except (ValueError, TypeError) as e:
                    st.warning(f"Error processing reactive demand rates: {str(e)}")
            
        except Exception as e:
            st.warning(f"Error calculating demand charges: {str(e)}")
    
    # 4. Get other charges
    other_charges = 0.0
    other_charges_breakdown = []
    
    try:
        other_charges_response = supabase.from_("OtherCharges_Table").select("*").eq("ScheduleID", schedule_id).execute()
        
        for charge in other_charges_response.data:
            try:
                charge_type = float(charge.get("ChargeType", 0)) if charge.get("ChargeType") is not None else 0.0
                description = charge.get("Description", "Other Charge")
                charge_unit = charge.get("ChargeUnit", "")
                
                other_charges += charge_type
                other_charges_breakdown.append({
                    "Description": f"{description} ({charge_unit})",
                    "Amount": charge_type
                })
            except (ValueError, TypeError) as e:
                st.warning(f"Error processing other charge: {str(e)}")
    except Exception as e:
        st.warning(f"Error calculating other charges: {str(e)}")
    
    # 5. Calculate taxes
    tax_amount = 0.0
    subtotal = service_charge + energy_charge + demand_charge + other_charges
    tax_breakdown = []
    
    try:
        tax_response = supabase.from_("TaxInfo_Table").select("*").eq("ScheduleID", schedule_id).execute()
        
        for tax in tax_response.data:
            try:
                tax_rate = float(tax.get("Per_cent", 0)) if tax.get("Per_cent") is not None else 0.0
                tax_desc = tax.get("Type", "Tax")
                city = tax.get("City", "")
                basis = tax.get("Basis", "")
                
                # Add city info to description if available
                if city:
                    tax_desc = f"{tax_desc} ({city})"
                
                # Calculate tax amount based on percentage
                amount = subtotal * (tax_rate / 100)
                tax_amount += amount
                tax_breakdown.append({
                    "Description": f"{tax_desc} ({tax_rate}%)",
                    "Amount": amount
                })
            except (ValueError, TypeError) as e:
                st.warning(f"Error processing tax: {str(e)}")
    except Exception as e:
        st.warning(f"Error calculating taxes: {str(e)}")
    
    # Calculate total bill
    total_bill = subtotal + tax_amount
    
    # Create a dataframe for the bill breakdown
    bill_items = []
    
    # Add service charges
    for charge in service_charge_breakdown:
        bill_items.append(charge)
    
    # Add detailed energy charges breakdown
    if has_energy_charges:
        if energy_charges_breakdown:
            for charge in energy_charges_breakdown:
                bill_items.append(charge)
        else:
            bill_items.append({"Description": "Energy Charges", "Amount": energy_charge})
    
    # Add detailed demand charges breakdown
    if has_demand_charges:
        if demand_charges_breakdown:
            for charge in demand_charges_breakdown:
                bill_items.append(charge)
        else:
            bill_items.append({"Description": "Demand Charges", "Amount": demand_charge})
    
    # Add other charges
    for charge in other_charges_breakdown:
        bill_items.append(charge)
    
    # Add subtotal line
    bill_items.append({"Description": "Subtotal", "Amount": subtotal})
    
    # Add taxes
    for tax in tax_breakdown:
        bill_items.append(tax)
    
    # Add total line
    bill_items.append({"Description": "Total", "Amount": total_bill})
    
    # Convert to dataframe
    bill_df = pd.DataFrame(bill_items)
    
    # Return all the calculated values
    return service_charge, energy_charge, demand_charge, other_charges, tax_amount, total_bill, bill_df

# Define the calculate_bill function for comparing different schedules
def calculate_bill(supabase, schedule_id, schedule_name, usage_kwh, demand_kw, power_factor, billing_month):
    """Calculate bill for a given schedule using the same usage values."""
    
    total_bill = 0.0
    
    try:
        # 1. Get service charges
        service_charge = 0.0
        service_charge_response = supabase.from_("ServiceCharge_Table").select("Rate").eq("ScheduleID", schedule_id).execute()
        for charge in service_charge_response.data:
            try:
                rate = float(charge.get("Rate", 0)) if charge.get("Rate") is not None else 0.0
                service_charge += rate
            except (ValueError, TypeError):
                pass
        
        # 2. Calculate energy charges
        energy_charge = 0.0
        
        if usage_kwh:
            # Check standard energy rates (Energy_Table)
            energy_response = supabase.from_("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute()
            for rate in energy_response.data:
                try:
                    rate_kwh = float(rate.get("RatekWh", 0)) if rate.get("RatekWh") is not None else 0.0
                    min_v = float(rate.get("MinkV", 0)) if rate.get("MinkV") is not None else 0.0
                    max_v = float(rate.get("MaxkV")) if rate.get("MaxkV") is not None else float('inf')
                    
                    # Check if usage falls within this rate's range
                    if min_v <= usage_kwh <= max_v:
                        energy_charge += rate_kwh * usage_kwh
                except (ValueError, TypeError):
                    pass
            
            # Check incremental/tiered energy rates
            incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if incremental_energy_response.data:
                try:
                    # Sort tiers by StartkWh
                    tiers = sorted(incremental_energy_response.data, 
                                  key=lambda x: float(x.get("StartkWh", 0)) if x.get("StartkWh") is not None else 0.0)
                    
                    remaining_kwh = usage_kwh
                    for tier in tiers:
                        rate_kwh = float(tier.get("RatekWh", 0)) if tier.get("RatekWh") is not None else 0.0
                        start_kwh = float(tier.get("StartkWh", 0)) if tier.get("StartkWh") is not None else 0.0
                        end_kwh = float(tier.get("EndkWh")) if tier.get("EndkWh") is not None else float('inf')
                        season = tier.get("Season", "")
                        
                        # Check if we're in the right season (if specified)
                        if season and billing_month:
                            summer_months = ["June", "July", "August", "September"]
                            winter_months = ["December", "January", "February", "March"]
                            
                            if (season.lower() == "summer" and billing_month not in summer_months) or \
                               (season.lower() == "winter" and billing_month not in winter_months):
                                continue
                        
                        # Calculate tier usage and charge
                        tier_usage = min(max(0, remaining_kwh - start_kwh), end_kwh - start_kwh)
                        if tier_usage > 0:
                            energy_charge += tier_usage * rate_kwh
                            remaining_kwh -= tier_usage
                            if remaining_kwh <= 0:
                                break
                except (ValueError, TypeError):
                    pass
            
            # Check time-of-use energy rates (simplified - equal distribution)
            energy_time_response = supabase.from_("EnergyTime_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if energy_time_response.data:
                try:
                    # For comparison purposes, distribute usage evenly among TOU periods
                    time_periods = energy_time_response.data
                    num_periods = len(time_periods)
                    usage_per_period = usage_kwh / num_periods if num_periods > 0 else 0
                    
                    for period in time_periods:
                        rate_kwh = float(period.get("RatekWh", 0)) if period.get("RatekWh") is not None else 0.0
                        season = period.get("Season", "")
                        
                        # Check if we're in the right season (if specified)
                        if season and billing_month:
                            summer_months = ["June", "July", "August", "September"]
                            winter_months = ["December", "January", "February", "March"]
                            
                            if (season.lower() == "summer" and billing_month not in summer_months) or \
                               (season.lower() == "winter" and billing_month not in winter_months):
                                continue
                        
                        energy_charge += rate_kwh * usage_per_period
                except (ValueError, TypeError):
                    pass
        
        # 3. Calculate demand charges
        demand_charge = 0.0
        
        if demand_kw:
            # Check standard demand rates
            demand_response = supabase.from_("Demand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            for rate in demand_response.data:
                try:
                    rate_kw = float(rate.get("RatekW", 0)) if rate.get("RatekW") is not None else 0.0
                    min_kv = float(rate.get("MinkV", 0)) if rate.get("MinkV") is not None else 0.0
                    max_kv = float(rate.get("MaxkV")) if rate.get("MaxkV") is not None else float('inf')
                    
                    # Check if demand falls within this rate's range
                    if min_kv <= demand_kw <= max_kv:
                        demand_charge += rate_kw * demand_kw
                except (ValueError, TypeError):
                    pass
            
            # Check time-of-use demand rates (simplified)
            demand_time_response = supabase.from_("DemandTime_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if demand_time_response.data:
                try:
                    # Convert all RatekW values to floats, filtering out None values
                    rates_kw = [float(rate.get("RatekW", 0)) if rate.get("RatekW") is not None else 0.0 
                               for rate in demand_time_response.data]
                    
                    if rates_kw:  # Check if the list is not empty
                        highest_rate_kw = max(rates_kw)
                        highest_rate_index = rates_kw.index(highest_rate_kw)
                        highest_rate = demand_time_response.data[highest_rate_index]
                        
                        season = highest_rate.get("Season", "")
                        
                        # Check if we're in the right season (if specified)
                        if not season or not billing_month or \
                           (season.lower() == "summer" and billing_month in ["June", "July", "August", "September"]) or \
                           (season.lower() == "winter" and billing_month in ["December", "January", "February", "March"]):
                            
                            demand_charge += highest_rate_kw * demand_kw
                except (ValueError, TypeError):
                    pass
            
            # Check incremental/tiered demand rates
            incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if incremental_demand_response.data:
                try:
                    # Sort tiers by StepMin
                    tiers = sorted(incremental_demand_response.data, 
                                key=lambda x: float(x.get("StepMin", 0)) if x.get("StepMin") is not None else 0.0)
                    
                    remaining_kw = demand_kw
                    for tier in tiers:
                        rate_kw = float(tier.get("RatekW", 0)) if tier.get("RatekW") is not None else 0.0
                        step_min = float(tier.get("StepMin", 0)) if tier.get("StepMin") is not None else 0.0
                        step_max = float(tier.get("StepMax")) if tier.get("StepMax") is not None else float('inf')
                        
                        # Calculate tier usage and charge
                        tier_usage = min(max(0, remaining_kw - step_min), step_max - step_min)
                        if tier_usage > 0:
                            demand_charge += tier_usage * rate_kw
                            remaining_kw -= tier_usage
                            if remaining_kw <= 0:
                                break
                except (ValueError, TypeError):
                    pass
            
            # Check reactive demand charges
            if power_factor < 1.0:
                reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("*").eq("ScheduleID", schedule_id).execute()
                if reactive_demand_response.data:
                    try:
                        # Calculate reactive demand based on power factor
                        reactive_kvar = demand_kw * math.tan(math.acos(power_factor))
                        
                        for rate in reactive_demand_response.data:
                            rate_value = float(rate.get("Rate", 0)) if rate.get("Rate") is not None else 0.0
                            min_val = float(rate.get("Min", 0)) if rate.get("Min") is not None else 0.0
                            max_val = float(rate.get("Max")) if rate.get("Max") is not None else float('inf')
                            
                            # Check if reactive demand falls within this rate's range
                            if min_val <= reactive_kvar <= max_val:
                                demand_charge += rate_value * reactive_kvar
                    except (ValueError, TypeError):
                        pass
        
        # 4. Get other charges
        other_charges = 0.0
        other_charges_response = supabase.from_("OtherCharges_Table").select("ChargeType").eq("ScheduleID", schedule_id).execute()
        for charge in other_charges_response.data:
            try:
                charge_type = float(charge.get("ChargeType", 0)) if charge.get("ChargeType") is not None else 0.0
                other_charges += charge_type
            except (ValueError, TypeError):
                pass
        
        # 5. Calculate taxes
        subtotal = service_charge + energy_charge + demand_charge + other_charges
        tax_amount = 0.0
        
        tax_response = supabase.from_("TaxInfo_Table").select("Per_cent").eq("ScheduleID", schedule_id).execute()
        for tax in tax_response.data:
            try:
                tax_rate = float(tax.get("Per_cent", 0)) if tax.get("Per_cent") is not None else 0.0
                tax_amount += subtotal * (tax_rate / 100)
            except (ValueError, TypeError):
                pass
        
        # Calculate total bill
        total_bill = subtotal + tax_amount
        
    except Exception as e:
        st.warning(f"Error calculating bill for schedule {schedule_id}: {str(e)}")
    
    # Return the bill results
    return {
        "schedule_id": schedule_id,
        "schedule_name": schedule_name,
        "total": total_bill,
        "projected": total_bill * 1.02  # Simple 2% projection for example purposes
    }

# Function to create a comparison table using pandas DataFrame
def create_comparison_dataframe(comparison_results):
    """Create a DataFrame for rate comparison."""
    
    # Find the best (lowest) rate
    best_rate_id = min(comparison_results, key=lambda x: x["total"])["schedule_id"]
    projected_best = min(comparison_results, key=lambda x: x["projected"])["schedule_id"]
    
    # Create the data for the DataFrame
    data = {
        "Option": [],
        "Rate Name": [],
        "Present": [],
        "Future (Projected)": []
    }
    
    # Add data for each rate
    for i, result in enumerate(comparison_results):
        option_name = f"Option {i+1} - Current Rate" if i == 0 else f"Option {i+1}"
        schedule_name = result["schedule_name"].split(" - ")[0] if " - " in result["schedule_name"] else result["schedule_name"]
        
        data["Option"].append(option_name)
        data["Rate Name"].append(schedule_name)
        data["Present"].append(f"${result['total']:.2f}")
        data["Future (Projected)"].append(f"${result['projected']:.2f}")
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    return df, best_rate_id, projected_best

# Tab 1: Bill Estimation Tool
with tab1:
    st.header("Electric Bill Estimation Tool")
    st.markdown("Estimate your electric bill based on your usage and utility rate schedule.")
    
    # Step 1: State Selection
    # Get states that have utilities with schedules
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
        else:
            states = []
        
        if not states:
            st.warning("No states with utilities and rate schedules found in the database.")
            st.stop()
            
        if 'selected_state' not in st.session_state:
            st.session_state.selected_state = ""
        
        selected_state = st.selectbox(
            "Select State", 
            [""] + states, 
            index=states.index(st.session_state.selected_state) + 1 if st.session_state.selected_state in states else 0,
            key="state_selector_tab1"  # Added unique key
        )
        st.session_state.selected_state = selected_state
    except Exception as e:
        st.error(f"Error loading states: {str(e)}")
        selected_state = ""
    
    # Step 2: Utility Selection (only show if state is selected)
    selected_utility = None
    selected_utility_id = None
    
    if selected_state:
        try:
            # Get utilities in the selected state that have schedules
            utilities_with_schedules = supabase.from_("Schedule_Table").select("UtilityID").execute()
            utility_ids = [item['UtilityID'] for item in utilities_with_schedules.data]
            
            if utility_ids:
                utilities_response = supabase.from_("Utility").select("UtilityID, UtilityName").eq("State", selected_state).in_("UtilityID", utility_ids).execute()
                utilities_data = utilities_response.data
            else:
                utilities_data = []
            
            if not utilities_data:
                st.warning(f"No utilities with rate schedules found in {selected_state}.")
            else:
                # Create a dictionary for easy lookup of UtilityID by name
                utilities_dict = {utility["UtilityName"]: utility["UtilityID"] for utility in utilities_data}
                utility_names = sorted(list(utilities_dict.keys()))
                
                if 'selected_utility' not in st.session_state:
                    st.session_state.selected_utility = ""
                
                selected_utility = st.selectbox(
                    "Select Utility", 
                    [""] + utility_names, 
                    index=utility_names.index(st.session_state.selected_utility) + 1 if st.session_state.selected_utility in utility_names else 0,
                    key="utility_selector_tab1"  # Added unique key
                )
                st.session_state.selected_utility = selected_utility
                
                if selected_utility:
                    selected_utility_id = utilities_dict[selected_utility]
                    st.session_state.selected_utility_id = selected_utility_id
        except Exception as e:
            st.error(f"Error loading utilities: {str(e)}")
    
    # Step 3: Schedule Selection (only show if utility is selected)
    selected_schedule = None
    selected_schedule_id = None
    
    if selected_utility_id:
        try:
            schedules_response = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName, ScheduleDescription").eq("UtilityID", selected_utility_id).execute()
            schedules_data = schedules_response.data
            
            if not schedules_data:
                st.warning(f"No rate schedules found for {selected_utility}.")
            else:
                # Format schedule options with name and description
                schedule_options = {}
                for schedule in schedules_data:
                    name = schedule.get("ScheduleName", "")
                    desc = schedule.get("ScheduleDescription", "")
                    
                    # Create display text with both name and description
                    if desc:
                        display_text = f"{name} - {desc}"
                    else:
                        display_text = name
                    
                    schedule_options[display_text] = schedule.get("ScheduleID")
                
                schedule_display_options = sorted(list(schedule_options.keys()))
                
                if 'selected_schedule' not in st.session_state:
                    st.session_state.selected_schedule = ""
                
                selected_schedule_display = st.selectbox(
                    "Select Rate Schedule", 
                    [""] + schedule_display_options, 
                    index=schedule_display_options.index(st.session_state.selected_schedule) + 1 if st.session_state.selected_schedule in schedule_display_options else 0,
                    key="schedule_selector_tab1"  # Added unique key
                )
                
                if selected_schedule_display:
                    selected_schedule_id = schedule_options[selected_schedule_display]
                    selected_schedule = selected_schedule_display
                    st.session_state.selected_schedule = selected_schedule
                    st.session_state.selected_schedule_id = selected_schedule_id
        except Exception as e:
            st.error(f"Error loading schedules: {str(e)}")
    
    # Step 4: Check if selected schedule has various charge components
    has_demand_charges = False
    has_energy_charges = False
    has_reactive_demand = False
    has_tou_energy = False
    tou_periods = []
    
    if selected_schedule_id:
        try:
            # Check if there are demand charges for this schedule
            demand_response = supabase.from_("Demand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            demand_time_response = supabase.from_("DemandTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            
            has_demand_charges = (
                len(demand_response.data) > 0 or 
                len(demand_time_response.data) > 0 or 
                len(incremental_demand_response.data) > 0
            )
            
            # Check if there are energy charges for this schedule
            energy_response = supabase.from_("Energy_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            energy_time_response = supabase.from_("EnergyTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            
            has_energy_charges = (
                len(energy_response.data) > 0 or 
                len(energy_time_response.data) > 0 or 
                len(incremental_energy_response.data) > 0
            )
            
            # Check for reactive demand charges
            reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            has_reactive_demand = len(reactive_demand_response.data) > 0
            
            # Check for time-of-use energy periods
            if len(energy_time_response.data) > 0:
                has_tou_energy = True
                tou_response = supabase.from_("EnergyTime_Table").select("Description, TimeOfDay").eq("ScheduleID", selected_schedule_id).execute()
                
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
            
        except Exception as e:
            st.error(f"Error checking rate components: {str(e)}")
    
    # Step 5: Usage Inputs (only show if schedule is selected)
    usage_kwh = None
    usage_by_tou = {}
    demand_kw = None
    demand_by_tou = {}
    power_factor = 0.9  # Default power factor
    billing_month = None
    
    if selected_schedule_id:
        st.subheader("Enter Usage Information")
        
        # Billing period (month)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        current_month_index = datetime.now().month - 1  # 0-based index
        
        if 'billing_month' not in st.session_state:
            st.session_state.billing_month = months[current_month_index]
        
        billing_month = st.selectbox(
            "Billing Month", 
            months, 
            index=months.index(st.session_state.billing_month) if st.session_state.billing_month in months else current_month_index,
            key="billing_month_tab1"  # Added unique key
        )
        st.session_state.billing_month = billing_month
        
        # Always ask for energy usage (kWh)
        if has_energy_charges:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if 'usage_kwh' not in st.session_state:
                    st.session_state.usage_kwh = 0.0
                    
                usage_kwh = st.number_input(
                    "Total Energy Usage (kWh)", 
                    min_value=0.0, 
                    step=10.0, 
                    value=st.session_state.usage_kwh,
                    key="usage_kwh_tab1"  # Added unique key
                )
                st.session_state.usage_kwh = usage_kwh
            
            # Time-of-use energy inputs
            if has_tou_energy and tou_periods:
                st.subheader("Time-of-Use Energy Breakdown")
                st.info("Enter your energy usage for each time period. The total should equal your total energy usage.")
                
                # Create two columns for TOU inputs
                tou_cols = st.columns(2)
                col_idx = 0
                
                if 'usage_by_tou' not in st.session_state:
                    st.session_state.usage_by_tou = {}
                
                remaining_kwh = usage_kwh
                for i, period in enumerate(tou_periods):
                    period_key = period['display']
                    
                    with tou_cols[col_idx]:
                        if i == len(tou_periods) - 1:  # Last period
                            # For the last period, show the remaining amount
                            st.text(f"{period_key}")
                            st.text(f"Remaining: {remaining_kwh:.1f} kWh")
                            st.session_state.usage_by_tou[period_key] = remaining_kwh
                            usage_by_tou[period_key] = remaining_kwh
                        else:
                            # Set default value for this period
                            if period_key not in st.session_state.usage_by_tou:
                                st.session_state.usage_by_tou[period_key] = 0.0
                                
                            period_usage = st.number_input(
                                f"{period_key} (kWh)", 
                                min_value=0.0, 
                                max_value=usage_kwh if usage_kwh else 0.0,
                                step=1.0,
                                key=f"tou_energy_{i}_tab1",  # Added unique key with index
                                value=st.session_state.usage_by_tou[period_key]
                            )
                            
                            st.session_state.usage_by_tou[period_key] = period_usage
                            usage_by_tou[period_key] = period_usage
                            remaining_kwh -= period_usage
                    
                    # Alternate columns
                    col_idx = (col_idx + 1) % 2
                
                # Show warning if the sum doesn't match the total
                sum_tou = sum(usage_by_tou.values())
                if abs(sum_tou - usage_kwh) > 0.01 and usage_kwh > 0:
                    st.warning(f"Time-of-use breakdown ({sum_tou:.1f} kWh) doesn't match your total energy usage ({usage_kwh:.1f} kWh). Please adjust your inputs.")
        
        # Only ask for demand if the schedule has demand charges
        if has_demand_charges:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if 'demand_kw' not in st.session_state:
                    st.session_state.demand_kw = 0.0
                    
                demand_kw = st.number_input(
                    "Peak Demand (kW)", 
                    min_value=0.0, 
                    step=1.0,
                    value=st.session_state.demand_kw,
                    key="demand_kw_tab1"  # Added unique key
                )
                st.session_state.demand_kw = demand_kw
            
            # If reactive demand is applicable, show power factor input
            if has_reactive_demand:
                with col2:
                    if 'power_factor' not in st.session_state:
                        st.session_state.power_factor = 0.9
                        
                    power_factor = st.slider(
                        "Power Factor", 
                        min_value=0.7, 
                        max_value=1.0, 
                        value=st.session_state.power_factor, 
                        step=0.01,
                        key="power_factor_tab1",  # Added unique key
                        help="Power factor is the ratio of real power to apparent power in an electrical circuit."
                    )
                    st.session_state.power_factor = power_factor
    
    # Step 6: Calculate button and comparison section
    if selected_schedule_id and ((has_energy_charges and usage_kwh is not None) or not has_energy_charges) and ((has_demand_charges and demand_kw is not None) or not has_demand_charges):
        calc_col1, calc_col2 = st.columns([1, 5])
        with calc_col1:
            calculate_pressed = st.button("Calculate Bill Estimate", key="calculate_bill_tab1")  # Added unique key
            
        if calculate_pressed or st.session_state.bill_calculated:
            if calculate_pressed:  # Only recalculate if the button was just pressed
                st.session_state.bill_calculated = True
                
                # Calculate the bill for the selected schedule
                try:
                    service_charge, energy_charge, demand_charge, other_charges, tax_amount, total_bill, bill_df = calculate_current_bill(
                        supabase, 
                        selected_schedule_id, 
                        selected_schedule, 
                        usage_kwh, 
                        usage_by_tou,
                        demand_kw, 
                        power_factor, 
                        billing_month,
                        has_energy_charges,
                        has_demand_charges,
                        has_reactive_demand
                    )
                    
                    # Store the results in session state
                    st.session_state.service_charge = service_charge
                    st.session_state.energy_charge = energy_charge
                    st.session_state.demand_charge = demand_charge
                    st.session_state.other_charges = other_charges
                    st.session_state.tax_amount = tax_amount
                    st.session_state.total_bill = total_bill
                    st.session_state.bill_df = bill_df
                    
                    # Store the current bill details for comparison
                    st.session_state.current_bill = {
                        "schedule_id": selected_schedule_id,
                        "schedule_name": selected_schedule,
                        "total": total_bill,
                        "projected": total_bill * 1.02  # Simple 2% projection for example purposes
                    }
                    
                    # Clear previous comparison results when recalculating
                    if 'comparison_results' in st.session_state:
                        st.session_state.comparison_results = []
                        
                except Exception as e:
                    st.error(f"Error calculating bill: {str(e)}")
            
            # Display the bill results from session state
            st.subheader("Bill Estimate")
            
            # Display the bill breakdown
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Bill Summary")
                st.markdown(f"**Selected State:** {selected_state}")
                st.markdown(f"**Selected Utility:** {selected_utility}")
                st.markdown(f"**Selected Schedule:** {selected_schedule}")
                st.markdown(f"**Billing Month:** {billing_month}")
                
                if has_energy_charges:
                    st.markdown(f"**Energy Usage:** {usage_kwh} kWh")
                if has_demand_charges:
                    st.markdown(f"**Peak Demand:** {demand_kw} kW")
                if has_reactive_demand:
                    st.markdown(f"**Power Factor:** {power_factor}")
                    
                # Add a simple pie chart for visualization
                if has_energy_charges or has_demand_charges:
                    st.markdown("### Bill Visualization")
                    
                    # Prepare data for pie chart
                    chart_data = {
                        'Category': [],
                        'Amount': []
                    }
                    
                    # Add service charge
                    if st.session_state.service_charge > 0:
                        chart_data['Category'].append('Service Charge')
                        chart_data['Amount'].append(st.session_state.service_charge)
                    
                    # Add energy charges
                    if st.session_state.energy_charge > 0:
                        chart_data['Category'].append('Energy Charges')
                        chart_data['Amount'].append(st.session_state.energy_charge)
                    
                    # Add demand charges
                    if st.session_state.demand_charge > 0:
                        chart_data['Category'].append('Demand Charges')
                        chart_data['Amount'].append(st.session_state.demand_charge)
                    
                    # Add other charges as a single item
                    if st.session_state.other_charges > 0:
                        chart_data['Category'].append('Other Charges')
                        chart_data['Amount'].append(st.session_state.other_charges)
                    
                    # Add taxes as a single item
                    if st.session_state.tax_amount > 0:
                        chart_data['Category'].append('Taxes')
                        chart_data['Amount'].append(st.session_state.tax_amount)
                    
                    # Create DataFrame
                    chart_df = pd.DataFrame(chart_data)
                    
                    # Create pie chart
                    fig, ax = plt.subplots(figsize=(4, 4))
                    ax.pie(chart_df['Amount'], labels=chart_df['Category'], autopct='%1.1f%%')
                    ax.set_title('Bill Composition')
                    st.pyplot(fig)
            
            with col2:
                st.markdown("### Charges Breakdown")
                
                # Display the bill breakdown dataframe
                if st.session_state.bill_df is not None:
                    st.table(st.session_state.bill_df)
                else:
                    st.warning("No charges found for this schedule.")
            
            # Add rate comparison section
            st.markdown("---")
            st.subheader("Rate Comparison")
            st.markdown("Compare your current rate with other available rate schedules from this utility.")
            
            # Get other available schedules from the same utility
            try:
                other_schedules_response = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName, ScheduleDescription").eq("UtilityID", selected_utility_id).not_.eq("ScheduleID", selected_schedule_id).execute()
                other_schedules_data = other_schedules_response.data
                
                if not other_schedules_data:
                    st.info(f"No other rate schedules available for comparison from {selected_utility}.")
                else:
                    # Format schedule options with name and description
                    other_schedule_options = {}
                    for schedule in other_schedules_data:
                        name = schedule.get("ScheduleName", "")
                        desc = schedule.get("ScheduleDescription", "")
                        
                        # Create display text with both name and description
                        if desc:
                            display_text = f"{name} - {desc}"
                        else:
                            display_text = name
                        
                        other_schedule_options[display_text] = schedule.get("ScheduleID")
                    
                    # Allow selection of up to 3 schedules to compare
                    st.markdown("Select up to 3 rate schedules to compare with your current rate:")
                    
                    # Get or initialize the comparison selections in session state
                    if 'selected_comparison_schedules' not in st.session_state:
                        st.session_state.selected_comparison_schedules = []
                    
                    # Use multiselect for choosing comparison schedules
                    comparison_schedule_options = list(other_schedule_options.keys())
                    selected_comparison_schedules = st.multiselect(
                        "Select schedules to compare", 
                        comparison_schedule_options,
                        default=st.session_state.selected_comparison_schedules,
                        max_selections=3,
                        key="comparison_schedules_tab1"  # Added unique key
                    )
                    
                    # Store the selection in session state
                    st.session_state.selected_comparison_schedules = selected_comparison_schedules
                    
                    # Create a button to calculate the comparison
                    comp_col1, comp_col2 = st.columns([1, 5])
                    with comp_col1:
                        compare_pressed = st.button("Compare Rates", key="compare_rates_tab1")  # Added unique key
                    
                    if selected_comparison_schedules and (compare_pressed or 'comparison_results' in st.session_state and st.session_state.comparison_results):
                        st.markdown("### Rate Comparison Results")
                        
                        try:
                            if compare_pressed or not st.session_state.comparison_results:  # Only recalculate if the button was just pressed
                                comparison_results = [st.session_state.current_bill]
                                
                                # Calculate bills for each selected comparison schedule
                                for schedule_display in selected_comparison_schedules:
                                    comp_schedule_id = other_schedule_options[schedule_display]
                                    
                                    # Calculate bill using the same usage values but different schedule
                                    comp_bill = calculate_bill(
                                        supabase=supabase,
                                        schedule_id=comp_schedule_id,
                                        schedule_name=schedule_display,
                                        usage_kwh=usage_kwh,
                                        demand_kw=demand_kw,
                                        power_factor=power_factor,
                                        billing_month=billing_month
                                    )
                                    
                                    comparison_results.append(comp_bill)
                                
                                # Store the comparison results in session state
                                st.session_state.comparison_results = comparison_results
                            
                            # Create a comparison table using pandas DataFrame
                            comparison_df, best_rate_id, projected_best = create_comparison_dataframe(st.session_state.comparison_results)
                            
                            # Display the comparison table
                            st.dataframe(comparison_df, use_container_width=True)
                            
                            # Add some analysis
                            best_option = min(st.session_state.comparison_results, key=lambda x: x["total"])
                            savings = st.session_state.current_bill["total"] - best_option["total"]
                            
                            if savings > 0 and best_option["schedule_id"] != st.session_state.current_bill["schedule_id"]:
                                st.success(f"**Potential Savings**: Switching to '{best_option['schedule_name']}' could save approximately ${savings:.2f} per month based on your current usage.")
                            else:
                                st.success(f"**Current Rate Optimal**: Your current rate '{st.session_state.current_bill['schedule_name']}' appears to be the most cost-effective option based on your usage pattern.")
                        
                        except Exception as e:
                            st.error(f"Error during comparison calculation: {str(e)}")
                            st.info("Try selecting your schedules again or use the Reset All button at the top to start fresh.")
            
            except Exception as e:
                st.error(f"Error loading comparison schedules: {str(e)}")
            
            # Display a note about the bill estimate
            st.info("Note: This is an estimate based on the selected rate schedule and may not reflect all potential charges or adjustments. Projected costs assume a 2% rate increase.")

# Tab 2: Schedule Browser (placeholder for future implementation)
with tab2:
    st.header("Utility Rate Schedule Browser")
    st.info("This feature will allow you to browse through rate schedules. Coming soon!")
    
    # Step 2: Utility Selection (only show if state is selected)
    selected_utility_tab2 = None
    selected_utility_id_tab2 = None
    
    # Get states that have utilities with schedules - reuse state list from Tab 1
    try:
        if 'selected_state_tab2' not in st.session_state:
            st.session_state.selected_state_tab2 = ""
            
        selected_state_tab2 = st.selectbox(
            "Select State", 
            [""] + states, 
            index=0,
            key="state_selector_tab2"  # Unique key for Tab 2
        )
        st.session_state.selected_state_tab2 = selected_state_tab2
        
        if selected_state_tab2:
            # Get utilities in the selected state that have schedules
            utilities_with_schedules = supabase.from_("Schedule_Table").select("UtilityID").execute()
            utility_ids = [item['UtilityID'] for item in utilities_with_schedules.data]
            
            if utility_ids:
                utilities_response = supabase.from_("Utility").select("UtilityID, UtilityName").eq("State", selected_state_tab2).in_("UtilityID", utility_ids).execute()
                utilities_data = utilities_response.data
            else:
                utilities_data = []
            
            if not utilities_data:
                st.warning(f"No utilities with rate schedules found in {selected_state_tab2}.")
            else:
                # Create a dictionary for easy lookup of UtilityID by name
                utilities_dict = {utility["UtilityName"]: utility["UtilityID"] for utility in utilities_data}
                utility_names = sorted(list(utilities_dict.keys()))
                
                if 'selected_utility_tab2' not in st.session_state:
                    st.session_state.selected_utility_tab2 = ""
                
                selected_utility_tab2 = st.selectbox(
                    "Select Utility", 
                    [""] + utility_names, 
                    index=0,
                    key="utility_selector_tab2"  # Unique key for Tab 2
                )
                
                if selected_utility_tab2:
                    selected_utility_id_tab2 = utilities_dict[selected_utility_tab2]
    except Exception as e:
        st.error(f"Error loading utilities in Tab 2: {str(e)}")
    
    # Step 3: Schedule Selection (only show if utility is selected)
    selected_schedule_tab2 = None
    selected_schedule_id_tab2 = None
    
    if selected_utility_id_tab2:
        try:
            schedules_response = supabase.from_("Schedule_Table").select("ScheduleID, ScheduleName, ScheduleDescription").eq("UtilityID", selected_utility_id_tab2).execute()
            schedules_data = schedules_response.data
            
            if not schedules_data:
                st.warning(f"No rate schedules found for {selected_utility_tab2}.")
            else:
                # Format schedule options with name and description
                schedule_options = {}
                for schedule in schedules_data:
                    name = schedule.get("ScheduleName", "")
                    desc = schedule.get("ScheduleDescription", "")
                    
                    # Create display text with both name and description
                    if desc:
                        display_text = f"{name} - {desc}"
                    else:
                        display_text = name
                    
                    schedule_options[display_text] = schedule.get("ScheduleID")
                
                schedule_display_options = sorted(list(schedule_options.keys()))
                
                if 'selected_schedule_tab2' not in st.session_state:
                    st.session_state.selected_schedule_tab2 = ""
                
                selected_schedule_display_tab2 = st.selectbox(
                    "Select Rate Schedule", 
                    [""] + schedule_display_options, 
                    index=0,
                    key="schedule_selector_tab2"  # Unique key for Tab 2
                )
                
                if selected_schedule_display_tab2:
                    selected_schedule_id_tab2 = schedule_options[selected_schedule_display_tab2]
                    selected_schedule_tab2 = selected_schedule_display_tab2
        except Exception as e:
            st.error(f"Error loading schedules in Tab 2: {str(e)}")
    
    # Step 4: Check if selected schedule has various charge components
    has_demand_charges_tab2 = False
    has_energy_charges_tab2 = False
    has_reactive_demand_tab2 = False
    has_tou_energy_tab2 = False
    tou_periods_tab2 = []
    
    if selected_schedule_id_tab2:
        try:
            # Check if there are demand charges for this schedule
            demand_response = supabase.from_("Demand_Table").select("id").eq("ScheduleID", selected_schedule_id_tab2).execute()
            demand_time_response = supabase.from_("DemandTime_Table").select("id").eq("ScheduleID", selected_schedule_id_tab2).execute()
            incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("id").eq("ScheduleID", selected_schedule_id_tab2).execute()
            
            has_demand_charges_tab2 = (
                len(demand_response.data) > 0 or 
                len(demand_time_response.data) > 0 or 
                len(incremental_demand_response.data) > 0
            )
            
            # Check if there are energy charges for this schedule
            energy_response = supabase.from_("Energy_Table").select("id").eq("ScheduleID", selected_schedule_id_tab2).execute()
            energy_time_response = supabase.from_("EnergyTime_Table").select("id").eq("ScheduleID", selected_schedule_id_tab2).execute()
            incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("id").eq("ScheduleID", selected_schedule_id_tab2).execute()
            
            has_energy_charges_tab2 = (
                len(energy_response.data) > 0 or 
                len(energy_time_response.data) > 0 or 
                len(incremental_energy_response.data) > 0
            )
            
            # Check for reactive demand charges
            reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("id").eq("ScheduleID", selected_schedule_id_tab2).execute()
            has_reactive_demand_tab2 = len(reactive_demand_response.data) > 0
            
            # Check for time-of-use energy periods
            if len(energy_time_response.data) > 0:
                has_tou_energy_tab2 = True
                tou_response = supabase.from_("EnergyTime_Table").select("Description, TimeOfDay").eq("ScheduleID", selected_schedule_id_tab2).execute()
                
                # Get unique TOU periods
                tou_periods_tab2 = []
                seen_periods = set()
                
                for period in tou_response.data:
                    description = period.get("Description", "")
                    time_of_day = period.get("TimeOfDay", "")
                    
                    period_key = f"{description} ({time_of_day})"
                    if period_key not in seen_periods:
                        tou_periods_tab2.append({
                            "description": description,
                            "timeofday": time_of_day,
                            "display": period_key
                        })
                        seen_periods.add(period_key)
            
        except Exception as e:
            st.error(f"Error checking rate components in Tab 2: {str(e)}")
    
    # Step 5: Usage Inputs (only show if schedule is selected)
    usage_kwh_tab2 = None
    usage_by_tou_tab2 = {}
    demand_kw_tab2 = None
    demand_by_tou_tab2 = {}
    power_factor_tab2 = 0.9  # Default power factor
    billing_month_tab2 = None
    
    if selected_schedule_id_tab2:
        st.subheader("Enter Usage Information")
        
        # Billing period (month)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        current_month_index = datetime.now().month - 1  # 0-based index
        
        if 'billing_month_tab2' not in st.session_state:
            st.session_state.billing_month_tab2 = months[current_month_index]
        
        billing_month_tab2 = st.selectbox(
            "Billing Month", 
            months, 
            index=current_month_index,
            key="billing_month_tab2"  # Unique key for Tab 2
        )
        st.session_state.billing_month_tab2 = billing_month_tab2
        
        # Always ask for energy usage (kWh)
        if has_energy_charges_tab2:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if 'usage_kwh_tab2' not in st.session_state:
                    st.session_state.usage_kwh_tab2 = 0.0
                    
                usage_kwh_tab2 = st.number_input(
                    "Total Energy Usage (kWh)", 
                    min_value=0.0, 
                    step=10.0,
                    value=st.session_state.usage_kwh_tab2,
                    key="usage_kwh_tab2"  # Unique key for Tab 2
                )
                st.session_state.usage_kwh_tab2 = usage_kwh_tab2
            
            # Time-of-use energy inputs
            if has_tou_energy_tab2 and tou_periods_tab2:
                st.subheader("Time-of-Use Energy Breakdown")
                st.info("Enter your energy usage for each time period. The total should equal your total energy usage.")
                
                # Create two columns for TOU inputs
                tou_cols = st.columns(2)
                col_idx = 0
                
                if 'usage_by_tou_tab2' not in st.session_state:
                    st.session_state.usage_by_tou_tab2 = {}
                
                remaining_kwh = usage_kwh_tab2
                for i, period in enumerate(tou_periods_tab2):
                    period_key = period['display']
                    
                    with tou_cols[col_idx]:
                        if i == len(tou_periods_tab2) - 1:  # Last period
                            # For the last period, show the remaining amount
                            st.text(f"{period_key}")
                            st.text(f"Remaining: {remaining_kwh:.1f} kWh")
                            st.session_state.usage_by_tou_tab2[period_key] = remaining_kwh
                            usage_by_tou_tab2[period_key] = remaining_kwh
                        else:
                            # Set default value for this period
                            if period_key not in st.session_state.usage_by_tou_tab2:
                                st.session_state.usage_by_tou_tab2[period_key] = 0.0
                                
                            period_usage = st.number_input(
                                f"{period_key} (kWh)", 
                                min_value=0.0, 
                                max_value=usage_kwh_tab2 if usage_kwh_tab2 else 0.0,
                                step=1.0,
                                key=f"tou_energy_{i}_tab2",  # Unique key with tab indicator
                                value=st.session_state.usage_by_tou_tab2[period_key]
                            )
                            
                            st.session_state.usage_by_tou_tab2[period_key] = period_usage
                            usage_by_tou_tab2[period_key] = period_usage
                            remaining_kwh -= period_usage
                    
                    # Alternate columns
                    col_idx = (col_idx + 1) % 2
                
                # Show warning if the sum doesn't match the total
                sum_tou = sum(usage_by_tou_tab2.values())
                if abs(sum_tou - usage_kwh_tab2) > 0.01 and usage_kwh_tab2 > 0:
                    st.warning(f"Time-of-use breakdown ({sum_tou:.1f} kWh) doesn't match your total energy usage ({usage_kwh_tab2:.1f} kWh). Please adjust your inputs.")
        
        # Only ask for demand if the schedule has demand charges
        if has_demand_charges_tab2:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if 'demand_kw_tab2' not in st.session_state:
                    st.session_state.demand_kw_tab2 = 0.0
                    
                demand_kw_tab2 = st.number_input(
                    "Peak Demand (kW)", 
                    min_value=0.0, 
                    step=1.0,
                    value=st.session_state.demand_kw_tab2,
                    key="demand_kw_tab2"  # Unique key for Tab 2
                )
                st.session_state.demand_kw_tab2 = demand_kw_tab2
            
            # If reactive demand is applicable, show power factor input
            if has_reactive_demand_tab2:
                with col2:
                    if 'power_factor_tab2' not in st.session_state:
                        st.session_state.power_factor_tab2 = 0.9
                        
                    power_factor_tab2 = st.slider(
                        "Power Factor", 
                        min_value=0.7, 
                        max_value=1.0, 
                        value=st.session_state.power_factor_tab2, 
                        step=0.01,
                        key="power_factor_tab2",  # Unique key for Tab 2
                        help="Power factor is the ratio of real power to apparent power in an electrical circuit."
                    )
                    st.session_state.power_factor_tab2 = power_factor_tab2
    
    # Step 6: Calculate button
    if selected_schedule_id_tab2 and ((has_energy_charges_tab2 and usage_kwh_tab2 is not None) or not has_energy_charges_tab2) and ((has_demand_charges_tab2 and demand_kw_tab2 is not None) or not has_demand_charges_tab2):
        if st.button("Calculate Bill Estimate", key="calculate_bill_tab2"):  # Unique key for Tab 2
            st.info("Schedule browser functionality will be implemented in a future update. Please use the 'Bill Estimation & Comparison' tab for now.")
