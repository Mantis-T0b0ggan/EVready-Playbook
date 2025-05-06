import os
import math
import streamlit as st
import pandas as pd
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

# Main app title
st.title("⚡ Utility Rate Analysis Tool")

# Create tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["Bill Estimation", "Rate Comparison", "Schedule Browser"])

# Tab 1: Bill Estimation Tool
with tab1:
    st.header("Electric Bill Estimation Tool")
    st.markdown("Estimate your electric bill based on your usage and utility rate schedule.")
    
    # Step 1: State Selection
    # Get unique states from the Utility table
    try:
        states_response = supabase.table("Utility").select("State").execute()
        states_data = states_response.data
        
        # Extract unique states and sort them
        states = sorted(list(set([state["State"] for state in states_data if state["State"]])))
        
        selected_state = st.selectbox("Select State", [""] + states, index=0)
    except Exception as e:
        st.error(f"Error loading states: {str(e)}")
        selected_state = ""
    
    # Step 2: Utility Selection (only show if state is selected)
    selected_utility = None
    selected_utility_id = None
    
    if selected_state:
        try:
            utilities_response = supabase.table("Utility").select("UtilityID, UtilityName").eq("State", selected_state).execute()
            utilities_data = utilities_response.data
            
            # Create a dictionary for easy lookup of UtilityID by name
            utilities_dict = {utility["UtilityName"]: utility["UtilityID"] for utility in utilities_data}
            utility_names = sorted(list(utilities_dict.keys()))
            
            selected_utility = st.selectbox("Select Utility", [""] + utility_names, index=0)
            
            if selected_utility:
                selected_utility_id = utilities_dict[selected_utility]
        except Exception as e:
            st.error(f"Error loading utilities: {str(e)}")
    
    # Step 3: Schedule Selection (only show if utility is selected)
    selected_schedule = None
    selected_schedule_id = None
    
    if selected_utility_id:
        try:
            schedules_response = supabase.table("Schedule_Table").select("ScheduleID, ScheduleName").eq("UtilityID", selected_utility_id).execute()
            schedules_data = schedules_response.data
            
            # Create a dictionary for easy lookup of ScheduleID by name
            schedules_dict = {schedule["ScheduleName"]: schedule["ScheduleID"] for schedule in schedules_data}
            schedule_names = sorted(list(schedules_dict.keys()))
            
            selected_schedule = st.selectbox("Select Rate Schedule", [""] + schedule_names, index=0)
            
            if selected_schedule:
                selected_schedule_id = schedules_dict[selected_schedule]
        except Exception as e:
            st.error(f"Error loading schedules: {str(e)}")
    
    # Step 4: Check if selected schedule has demand charges
    has_demand_charges = False
    has_energy_charges = False
    
    if selected_schedule_id:
        # Check if there are demand charges for this schedule
        try:
            demand_response = supabase.table("Demand_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            demand_time_response = supabase.table("DemandTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            
            has_demand_charges = len(demand_response.data) > 0 or len(demand_time_response.data) > 0
            
            # Check if there are energy charges for this schedule
            energy_response = supabase.table("Energy_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            energy_time_response = supabase.table("EnergyTime_Table").select("id").eq("ScheduleID", selected_schedule_id).execute()
            
            has_energy_charges = len(energy_response.data) > 0 or len(energy_time_response.data) > 0
        except Exception as e:
            st.error(f"Error checking rate components: {str(e)}")
    
    # Step 5: Usage Inputs (only show if schedule is selected)
    usage_kwh = None
    demand_kw = None
    billing_month = None
    
    if selected_schedule_id:
        st.subheader("Enter Usage Information")
        
        # Always ask for energy usage (kWh)
        if has_energy_charges:
            usage_kwh = st.number_input("Energy Usage (kWh)", min_value=0.0, step=10.0)
        
        # Only ask for demand if the schedule has demand charges
        if has_demand_charges:
            demand_kw = st.number_input("Peak Demand (kW)", min_value=0.0, step=1.0)
        
        # Billing period (month)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        current_month_index = datetime.now().month - 1  # 0-based index
        billing_month = st.selectbox("Billing Month", months, index=current_month_index)
    
    # Step 6: Calculate button
    if selected_schedule_id and ((has_energy_charges and usage_kwh is not None) or not has_energy_charges) and ((has_demand_charges and demand_kw is not None) or not has_demand_charges):
        if st.button("Calculate Bill Estimate"):
            st.subheader("Bill Estimate")
            
            # Placeholder for bill calculation logic
            # This would be expanded to include all the different charge components
            
            # 1. Get service charges
            service_charge = 0.0
            try:
                service_charge_response = supabase.table("ServiceCharge_Table").select("Rate").eq("ScheduleID", selected_schedule_id).execute()
                if service_charge_response.data:
                    service_charge = service_charge_response.data[0]["Rate"]
            except Exception as e:
                st.warning(f"Error getting service charges: {str(e)}")
            
            # 2. Calculate energy charges
            energy_charge = 0.0
            energy_charges_breakdown = []
            
            if has_energy_charges and usage_kwh:
                try:
                    # Check standard energy rates (Energy_Table)
                    energy_response = supabase.table("Energy_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    if energy_response.data:
                        for rate in energy_response.data:
                            rate_kwh = rate.get("RatekWh", 0)
                            description = rate.get("Description", "Energy Charge")
                            min_v = rate.get("MinV", 0)
                            max_v = rate.get("MaxV", float('inf'))
                            determinant = rate.get("Determinant", "")
                            
                            # Check if usage falls within this rate's range
                            if min_v <= usage_kwh <= (max_v if max_v is not None else float('inf')):
                                charge_amount = rate_kwh * usage_kwh
                                energy_charge += charge_amount
                                energy_charges_breakdown.append({
                                    "Description": f"{description} ({rate_kwh:.4f} $/kWh)",
                                    "Amount": charge_amount
                                })
                    
                    # Check incremental/tiered energy rates (IncrementalEnergy_Table)
                    incremental_energy_response = supabase.table("IncrementalEnergy_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    if incremental_energy_response.data:
                        # Sort tiers by StartKWh to ensure proper order
                        tiers = sorted(incremental_energy_response.data, key=lambda x: x.get("StartkWh", 0))
                        
                        remaining_kwh = usage_kwh
                        for tier in tiers:
                            rate_kwh = tier.get("RatekWh", 0)
                            start_kwh = tier.get("StartkWh", 0)
                            end_kwh = tier.get("EndkWh")
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
                            tier_max = float('inf') if end_kwh is None else end_kwh
                            tier_usage = min(max(0, remaining_kwh - start_kwh), tier_max - start_kwh)
                            
                            if tier_usage > 0:
                                tier_charge = tier_usage * rate_kwh
                                energy_charge += tier_charge
                                energy_charges_breakdown.append({
                                    "Description": f"{description} ({start_kwh}-{end_kwh if end_kwh else '∞'} kWh @ {rate_kwh:.4f} $/kWh)",
                                    "Amount": tier_charge
                                })
                                
                                remaining_kwh -= tier_usage
                                if remaining_kwh <= 0:
                                    break
                    
                    # Check time-of-use energy rates (EnergyTime_Table)
                    energy_time_response = supabase.table("EnergyTime_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if energy_time_response.data and len(energy_time_response.data) > 0:
                        # For simplicity, we'll divide usage evenly among time periods for now
                        # In a real implementation, you'd need user input for usage during specific time periods
                        
                        time_periods = energy_time_response.data
                        
                        # Check if user has already specified TOU breakdown
                        # For now, we'll assume equal distribution across periods
                        num_periods = len(time_periods)
                        usage_per_period = usage_kwh / num_periods if num_periods > 0 else 0
                        
                        for period in time_periods:
                            rate_kwh = period.get("RatekWh", 0)
                            description = period.get("Description", "Time-of-Use Energy")
                            time_of_day = period.get("TimeOfDay", "")
                            season = period.get("Season", "")
                            
                            # Check if we're in the right season (if specified)
                            if season and billing_month:
                                # Simple season check - can be enhanced for more complex seasonal definitions
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
                    
                except Exception as e:
                    st.warning(f"Error calculating energy charges: {str(e)}")
            
            # 3. Calculate demand charges
            demand_charge = 0.0
            demand_charges_breakdown = []
            
            if has_demand_charges and demand_kw:
                try:
                    # Check standard demand rates (Demand_Table)
                    demand_response = supabase.table("Demand_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    if demand_response.data:
                        for rate in demand_response.data:
                            rate_kw = rate.get("RatekW", 0)
                            description = rate.get("Description", "Demand Charge")
                            min_kv = rate.get("MinkV", 0)
                            max_kv = rate.get("MaxkV", float('inf'))
                            determinant = rate.get("Determinant", "")
                            
                            # Check if demand falls within this rate's range
                            if min_kv <= demand_kw <= (max_kv if max_kv is not None else float('inf')):
                                charge_amount = rate_kw * demand_kw
                                demand_charge += charge_amount
                                demand_charges_breakdown.append({
                                    "Description": f"{description} ({rate_kw:.2f} $/kW)",
                                    "Amount": charge_amount
                                })
                    
                    # Check time-of-use demand rates (DemandTime_Table)
                    demand_time_response = supabase.table("DemandTime_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if demand_time_response.data and len(demand_time_response.data) > 0:
                        # For simplicity, we'll use the highest demand rate for now
                        # In a real implementation, you'd need user input for demand during specific time periods
                        
                        highest_rate = max(demand_time_response.data, key=lambda x: x.get("RatekW", 0))
                        rate_kw = highest_rate.get("RatekW", 0)
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
                    
                    # Check incremental/tiered demand rates (IncrementalDemand_Table)
                    incremental_demand_response = supabase.table("IncrementalDemand_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    if incremental_demand_response.data:
                        # Sort tiers by StepMin to ensure proper order
                        tiers = sorted(incremental_demand_response.data, key=lambda x: x.get("StepMin", 0))
                        
                        remaining_kw = demand_kw
                        for tier in tiers:
                            rate_kw = tier.get("RatekW", 0)
                            step_min = tier.get("StepMin", 0)
                            step_max = tier.get("StepMax")
                            description = tier.get("Description", "Tiered Demand Charge")
                            
                            # Calculate tier usage and charge
                            tier_max = float('inf') if step_max is None else step_max
                            tier_usage = min(max(0, remaining_kw - step_min), tier_max - step_min)
                            
                            if tier_usage > 0:
                                tier_charge = tier_usage * rate_kw
                                demand_charge += tier_charge
                                demand_charges_breakdown.append({
                                    "Description": f"{description} ({step_min}-{step_max if step_max else '∞'} kW @ {rate_kw:.2f} $/kW)",
                                    "Amount": tier_charge
                                })
                                
                                remaining_kw -= tier_usage
                                if remaining_kw <= 0:
                                    break
                    
                    # Check reactive demand charges (ReactiveDemand_Table)
                    reactive_demand_response = supabase.table("ReactiveDemand_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                    
                    if reactive_demand_response.data and demand_kw > 0:
                        # Simplified calculation - in a real implementation, you'd need power factor input
                        # Assuming a default power factor of 0.9 for now
                        power_factor = 0.9
                        
                        for rate in reactive_demand_response.data:
                            rate_value = rate.get("Rate", 0)
                            min_val = rate.get("Min", 0)
                            max_val = rate.get("Max", float('inf'))
                            description = rate.get("Description", "Reactive Demand Charge")
                            
                            # Calculate reactive demand based on power factor
                            # Formula: reactive_power = active_power * tan(acos(power_factor))
                            import math
                            reactive_kvar = demand_kw * math.tan(math.acos(power_factor))
                            
                            # Check if reactive demand falls within this rate's range
                            if min_val <= reactive_kvar <= (max_val if max_val is not None else float('inf')):
                                charge_amount = rate_value * reactive_kvar
                                demand_charge += charge_amount
                                demand_charges_breakdown.append({
                                    "Description": f"{description} ({rate_value:.2f} $/kVAR)",
                                    "Amount": charge_amount
                                })
                    
                except Exception as e:
                    st.warning(f"Error calculating demand charges: {str(e)}")
            
            # 4. Get other charges
            other_charges = 0.0
            other_charges_breakdown = []
            try:
                other_charges_response = supabase.table("OtherCharges_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                for charge in other_charges_response.data:
                    charge_type = charge.get("ChargeType", 0)
                    description = charge.get("Description", "Other Charge")
                    
                    # Assume charge_type is the amount for now
                    # In a real implementation, you'd need to interpret what ChargeType means
                    other_charges += charge_type
                    other_charges_breakdown.append({"Description": description, "Amount": charge_type})
            except Exception as e:
                st.warning(f"Error calculating other charges: {str(e)}")
            
            # 5. Calculate taxes
            tax_amount = 0.0
            subtotal = service_charge + energy_charge + demand_charge + other_charges
            tax_breakdown = []
            try:
                tax_response = supabase.table("TaxInfo_Table").select("*").eq("ScheduleID", selected_schedule_id).execute()
                for tax in tax_response.data:
                    tax_rate = tax.get("Per_cent", 0)
                    tax_desc = tax.get("Type", "Tax")
                    
                    # Calculate tax amount based on percentage
                    amount = subtotal * (tax_rate / 100)
                    tax_amount += amount
                    tax_breakdown.append({"Description": tax_desc, "Rate": f"{tax_rate}%", "Amount": amount})
            except Exception as e:
                st.warning(f"Error calculating taxes: {str(e)}")
            
            # Calculate total bill
            total_bill = subtotal + tax_amount
            
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
                    
                # Add a simple pie chart for visualization
                if has_energy_charges or has_demand_charges:
                    st.markdown("### Bill Visualization")
                    
                    # Prepare data for pie chart
                    chart_data = {
                        'Category': [],
                        'Amount': []
                    }
                    
                    # Add service charge
                    if service_charge > 0:
                        chart_data['Category'].append('Service Charge')
                        chart_data['Amount'].append(service_charge)
                    
                    # Add energy charges
                    if energy_charge > 0:
                        chart_data['Category'].append('Energy Charges')
                        chart_data['Amount'].append(energy_charge)
                    
                    # Add demand charges
                    if demand_charge > 0:
                        chart_data['Category'].append('Demand Charges')
                        chart_data['Amount'].append(demand_charge)
                    
                    # Add other charges as a single item
                    if other_charges > 0:
                        chart_data['Category'].append('Other Charges')
                        chart_data['Amount'].append(other_charges)
                    
                    # Add taxes as a single item
                    if tax_amount > 0:
                        chart_data['Category'].append('Taxes')
                        chart_data['Amount'].append(tax_amount)
                    
                    # Create DataFrame
                    chart_df = pd.DataFrame(chart_data)
                    
                    # Create pie chart
                    import matplotlib.pyplot as plt
                    fig, ax = plt.subplots(figsize=(4, 4))
                    ax.pie(chart_df['Amount'], labels=chart_df['Category'], autopct='%1.1f%%')
                    ax.set_title('Bill Composition')
                    st.pyplot(fig)
            
            with col2:
                st.markdown("### Charges Breakdown")
                
                # Create a dataframe for the bill breakdown
                bill_items = [
                    {"Description": "Service Charge", "Amount": service_charge},
                ]
                
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
                
                bill_items.append({"Description": "Subtotal", "Amount": subtotal})
                
                # Add taxes
                for tax in tax_breakdown:
                    bill_items.append({"Description": f"{tax['Description']} ({tax['Rate']})", "Amount": tax["Amount"]})
                
                bill_items.append({"Description": "Total", "Amount": total_bill})
                
                # Convert to dataframe and display
                bill_df = pd.DataFrame(bill_items)
                
                # Format the Amount column with currency formatting
                bill_df["Amount"] = bill_df["Amount"].map("${:.2f}".format)
                
                # Display the dataframe without index
                st.table(bill_df)
            
            # Display a note about the bill estimate
            st.info("Note: This is an estimate based on the selected rate schedule and may not reflect all potential charges or adjustments.")

# Tab 2: Rate Comparison (placeholder for future implementation)
with tab2:
    st.header("Rate Schedule Comparison")
    st.info("This feature will allow you to compare different rate schedules. Coming soon!")

# Tab 3: Schedule Browser (placeholder for future implementation)
with tab3:
    st.header("Utility Rate Schedule Browser")
    st.info("This feature will allow you to browse through rate schedules. Coming soon!")
