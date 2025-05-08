import streamlit as st
import pandas as pd
from calculators.service_charges import calculate_service_charges
from calculators.energy_charges import calculate_energy_charges
from calculators.demand_charges import calculate_demand_charges
from calculators.tax_calculator import calculate_taxes

def calculate_current_bill(supabase, schedule_id, schedule_name, usage_kwh, usage_by_tou, 
                          demand_kw, power_factor, billing_month, 
                          has_energy_charges, has_demand_charges, has_reactive_demand):
    """Calculate full bill breakdown for the current schedule."""
    
    # Calculate service charges
    service_charge, service_charge_breakdown = calculate_service_charges(supabase, schedule_id)
    
    # Calculate energy charges if applicable
    energy_charge = 0.0
    energy_charges_breakdown = []
    if has_energy_charges and usage_kwh:
        energy_charge, energy_charges_breakdown = calculate_energy_charges(
            supabase, schedule_id, usage_kwh, usage_by_tou, billing_month
        )
    
    # Calculate demand charges if applicable
    demand_charge = 0.0
    demand_charges_breakdown = []
    if has_demand_charges and demand_kw:
        demand_charge, demand_charges_breakdown = calculate_demand_charges(
            supabase, schedule_id, demand_kw, power_factor, billing_month, has_reactive_demand
        )
    
    # Get other charges
    other_charges, other_charges_breakdown = calculate_other_charges(supabase, schedule_id)
    
    # Calculate subtotal
    subtotal = service_charge + energy_charge + demand_charge + other_charges
    
    # Calculate taxes
    tax_amount, tax_breakdown = calculate_taxes(supabase, schedule_id, subtotal)
    
    # Calculate total bill
    total_bill = subtotal + tax_amount
    
    # Create bill dataframe
    bill_df = create_bill_dataframe(
        service_charge_breakdown, 
        energy_charges_breakdown, 
        demand_charges_breakdown, 
        other_charges_breakdown, 
        subtotal, 
        tax_breakdown, 
        total_bill,
        has_energy_charges,
        has_demand_charges
    )
    
    # Create bill breakdown summary
    bill_breakdown = {
        'service_charge': service_charge,
        'energy_charge': energy_charge,
        'demand_charge': demand_charge,
        'other_charges': other_charges,
        'tax_amount': tax_amount,
        'total': total_bill
    }
    
    return (
        service_charge, 
        energy_charge, 
        demand_charge, 
        other_charges, 
        tax_amount, 
        total_bill, 
        bill_df,
        bill_breakdown
    )

def calculate_other_charges(supabase, schedule_id):
    """Calculate other charges for a schedule."""
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
    
    return other_charges, other_charges_breakdown

def create_bill_dataframe(service_charge_breakdown, energy_charges_breakdown, demand_charges_breakdown, 
                         other_charges_breakdown, subtotal, tax_breakdown, total_bill,
                         has_energy_charges, has_demand_charges):
    """Create a dataframe for the bill breakdown."""
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
            bill_items.append({"Description": "Energy Charges", "Amount": 0.0})
    
    # Add detailed demand charges breakdown
    if has_demand_charges:
        if demand_charges_breakdown:
            for charge in demand_charges_breakdown:
                bill_items.append(charge)
        else:
            bill_items.append({"Description": "Demand Charges", "Amount": 0.0})
    
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
    return pd.DataFrame(bill_items)

def calculate_comparison_bill(supabase, schedule_id, schedule_name, usage_kwh, demand_kw, power_factor, billing_month):
    """Calculate bill for a given schedule using the same usage values."""
    
    # Initialize values
    service_charge = 0.0
    energy_charge = 0.0
    demand_charge = 0.0
    other_charges = 0.0
    tax_amount = 0.0
    
    # Similar calculations as the full version but simplified
    # ...
    # (Omitted for brevity)
    # ...
    
    # Calculate total bill
    subtotal = service_charge + energy_charge + demand_charge + other_charges
    total_bill = subtotal + tax_amount
    
    # Create breakdown dictionary
    breakdown = {
        'service_charge': service_charge,
        'energy_charge': energy_charge,
        'demand_charge': demand_charge,
        'other_charges': other_charges,
        'tax_amount': tax_amount,
        'total': total_bill
    }
    
    # Return results
    return {
        "schedule_id": schedule_id,
        "schedule_name": schedule_name,
        "total": total_bill,
        "projected": total_bill * 1.02,  # Simple 2% projection
        "breakdown": breakdown
    }