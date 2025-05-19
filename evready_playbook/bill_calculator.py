import math
import streamlit as st
import pandas as pd

def calculate_current_bill(supabase, schedule_id, schedule_name, usage_kwh, usage_by_tou, 
                          demand_kw, power_factor, billing_month, 
                          has_energy_charges, has_demand_charges, has_reactive_demand):
    """Calculate full bill breakdown for the current schedule."""
    
    # 1. Get service charges
    service_charge, service_charge_breakdown = calculate_service_charges(supabase, schedule_id)
    
    # 2. Calculate energy charges if applicable
    energy_charge = 0.0
    energy_charges_breakdown = []
    if has_energy_charges and usage_kwh:
        energy_charge, energy_charges_breakdown = calculate_energy_charges(
            supabase, schedule_id, usage_kwh, usage_by_tou, billing_month
        )
    
    # 3. Calculate demand charges if applicable
    demand_charge = 0.0
    demand_charges_breakdown = []
    if has_demand_charges and demand_kw:
        demand_charge, demand_charges_breakdown = calculate_demand_charges(
            supabase, schedule_id, demand_kw, power_factor, billing_month, has_reactive_demand
        )
    
    # 4. Get other charges
    other_charges, other_charges_breakdown = calculate_other_charges(supabase, schedule_id)
    
    # 5. Calculate taxes
    subtotal = service_charge + energy_charge + demand_charge + other_charges
    tax_amount, tax_breakdown, using_default_tax = calculate_taxes(supabase, schedule_id, subtotal)
    
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
        'total': total_bill,
        'using_default_tax': using_default_tax  # Add this flag to the breakdown
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

def calculate_bill(supabase, schedule_id, schedule_name, usage_kwh, demand_kw, power_factor, billing_month):
    """Calculate bill for a given schedule using the same usage values."""
    
    # Initialize breakdown components
    service_charge = 0.0
    energy_charge = 0.0
    demand_charge = 0.0
    other_charges = 0.0
    tax_amount = 0.0
    using_default_tax = False
    
    try:
        # 1. Get service charges
        service_charge_response = supabase.from_("ServiceCharge_Table").select("Rate").eq("ScheduleID", schedule_id).execute()
        for charge in service_charge_response.data:
            try:
                rate = float(charge.get("Rate", 0)) if charge.get("Rate") is not None else 0.0
                service_charge += rate
            except (ValueError, TypeError):
                pass
        
        # 2. Calculate energy charges
        if usage_kwh:
            # Standard energy rates
            energy_response = supabase.from_("Energy_Table").select("*").eq("ScheduleID", schedule_id).execute()
            for rate in energy_response.data:
                try:
                    rate_kwh = float(rate.get("RatekWh", 0)) if rate.get("RatekWh") is not None else 0.0
                    min_v = float(rate.get("MinkV", 0)) if rate.get("MinkV") is not None else 0.0
                    max_v = float(rate.get("MaxkV")) if rate.get("MaxkV") is not None else float('inf')
                    
                    if min_v <= usage_kwh <= max_v:
                        energy_charge += rate_kwh * usage_kwh
                except (ValueError, TypeError):
                    pass
            
            # Incremental/tiered energy rates
            incremental_energy_response = supabase.from_("IncrementalEnergy_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if incremental_energy_response.data:
                try:
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
                        
                        tier_usage = min(max(0, remaining_kwh - start_kwh), end_kwh - start_kwh)
                        if tier_usage > 0:
                            energy_charge += tier_usage * rate_kwh
                            remaining_kwh -= tier_usage
                            if remaining_kwh <= 0:
                                break
                except (ValueError, TypeError):
                    pass
            
            # Time-of-use energy rates (simplified - equal distribution)
            energy_time_response = supabase.from_("EnergyTime_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if energy_time_response.data:
                try:
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
        if demand_kw:
            # Standard demand rates
            demand_response = supabase.from_("Demand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            for rate in demand_response.data:
                try:
                    rate_kw = float(rate.get("RatekW", 0)) if rate.get("RatekW") is not None else 0.0
                    min_kv = float(rate.get("MinkV", 0)) if rate.get("MinkV") is not None else 0.0
                    max_kv = float(rate.get("MaxkV")) if rate.get("MaxkV") is not None else float('inf')
                    
                    if min_kv <= demand_kw <= max_kv:
                        demand_charge += rate_kw * demand_kw
                except (ValueError, TypeError):
                    pass
            
            # Time-of-use demand rates (simplified)
            demand_time_response = supabase.from_("DemandTime_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if demand_time_response.data:
                try:
                    rates_kw = [float(rate.get("RatekW", 0)) if rate.get("RatekW") is not None else 0.0 
                               for rate in demand_time_response.data]
                    
                    if rates_kw:
                        highest_rate_kw = max(rates_kw)
                        highest_rate_index = rates_kw.index(highest_rate_kw)
                        highest_rate = demand_time_response.data[highest_rate_index]
                        
                        season = highest_rate.get("Season", "")
                        
                        if not season or not billing_month or \
                           (season.lower() == "summer" and billing_month in ["June", "July", "August", "September"]) or \
                           (season.lower() == "winter" and billing_month in ["December", "January", "February", "March"]):
                            
                            demand_charge += highest_rate_kw * demand_kw
                except (ValueError, TypeError):
                    pass
            
            # Incremental/tiered demand rates
            incremental_demand_response = supabase.from_("IncrementalDemand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            if incremental_demand_response.data:
                try:
                    tiers = sorted(incremental_demand_response.data, 
                                key=lambda x: float(x.get("StepMin", 0)) if x.get("StepMin") is not None else 0.0)
                    
                    remaining_kw = demand_kw
                    for tier in tiers:
                        rate_kw = float(tier.get("RatekW", 0)) if tier.get("RatekW") is not None else 0.0
                        step_min = float(tier.get("StepMin", 0)) if tier.get("StepMin") is not None else 0.0
                        step_max = float(tier.get("StepMax")) if tier.get("StepMax") is not None else float('inf')
                        
                        tier_usage = min(max(0, remaining_kw - step_min), step_max - step_min)
                        if tier_usage > 0:
                            demand_charge += tier_usage * rate_kw
                            remaining_kw -= tier_usage
                            if remaining_kw <= 0:
                                break
                except (ValueError, TypeError):
                    pass
            
            # Reactive demand charges
            if power_factor < 1.0:
                reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("*").eq("ScheduleID", schedule_id).execute()
                if reactive_demand_response.data:
                    try:
                        reactive_kvar = demand_kw * math.tan(math.acos(power_factor))
                        
                        for rate in reactive_demand_response.data:
                            rate_value = float(rate.get("Rate", 0)) if rate.get("Rate") is not None else 0.0
                            min_val = float(rate.get("Min", 0)) if rate.get("Min") is not None else 0.0
                            max_val = float(rate.get("Max")) if rate.get("Max") is not None else float('inf')
                            
                            if min_val <= reactive_kvar <= max_val:
                                demand_charge += rate_value * reactive_kvar
                    except (ValueError, TypeError):
                        pass
        
        # 4. Get other charges
        other_charges_response = supabase.from_("OtherCharges_Table").select("ChargeType").eq("ScheduleID", schedule_id).execute()
        for charge in other_charges_response.data:
            try:
                charge_type = float(charge.get("ChargeType", 0)) if charge.get("ChargeType") is not None else 0.0
                other_charges += charge_type
            except (ValueError, TypeError):
                pass
        
        # 5. Calculate taxes
        subtotal = service_charge + energy_charge + demand_charge + other_charges
        
        # Check if tax data exists for this schedule
        tax_response = supabase.from_("TaxInfo_Table").select("Per_cent").eq("ScheduleID", schedule_id).execute()
        
        if tax_response.data and len(tax_response.data) > 0:
            # Use tax data from database
            for tax in tax_response.data:
                try:
                    tax_rate = float(tax.get("Per_cent", 0)) if tax.get("Per_cent") is not None else 0.0
                    tax_amount += subtotal * (tax_rate / 100)
                except (ValueError, TypeError):
                    pass
        else:
            # No tax data found, use default 6% tax rate
            default_tax_rate = 6.0
            tax_amount = subtotal * (default_tax_rate / 100)
            using_default_tax = True
        
        # Calculate total bill
        total_bill = subtotal + tax_amount
        
    except Exception as e:
        st.warning(f"Error calculating bill for schedule {schedule_id}: {str(e)}")
        # If there's an error, still try to calculate with default tax rate
        subtotal = service_charge + energy_charge + demand_charge + other_charges
        default_tax_rate = 6.0
        tax_amount = subtotal * (default_tax_rate / 100)
        total_bill = subtotal + tax_amount
        using_default_tax = True
    
    # Create breakdown dictionary
    breakdown = {
        'service_charge': service_charge,
        'energy_charge': energy_charge,
        'demand_charge': demand_charge,
        'other_charges': other_charges,
        'tax_amount': tax_amount,
        'total': total_bill,
        'using_default_tax': using_default_tax
    }
    
    # Return the bill results
    return {
        "schedule_id": schedule_id,
        "schedule_name": schedule_name,
        "total": total_bill,
        "projected": total_bill * 1.02,  # Simple 2% projection
        "breakdown": breakdown  # Store the breakdown for visualization
    }

def calculate_service_charges(supabase, schedule_id):
    """Calculate service charges for a schedule."""
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
    
    return service_charge, service_charge_breakdown

def calculate_energy_charges(supabase, schedule_id, usage_kwh, usage_by_tou, billing_month):
    """Calculate energy charges for a schedule."""
    energy_charge = 0.0
    energy_charges_breakdown = []
    
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
    
    return energy_charge, energy_charges_breakdown

def calculate_demand_charges(supabase, schedule_id, demand_kw, power_factor, billing_month, has_reactive_demand):
    """Calculate demand charges for a schedule."""
    demand_charge = 0.0
    demand_charges_breakdown = []
    
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
        if has_reactive_demand and demand_kw > 0:
            reactive_demand_response = supabase.from_("ReactiveDemand_Table").select("*").eq("ScheduleID", schedule_id).execute()
            
            if reactive_demand_response.data:
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
    
    return demand_charge, demand_charges_breakdown

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

def calculate_taxes(supabase, schedule_id, subtotal):
    """Calculate taxes for a schedule."""
    tax_amount = 0.0
    tax_breakdown = []
    using_default_tax = False
    
    try:
        tax_response = supabase.from_("TaxInfo_Table").select("*").eq("ScheduleID", schedule_id).execute()
        
        # Check if tax data exists for this schedule
        if tax_response.data and len(tax_response.data) > 0:
            # Use tax data from database
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
        else:
            # No tax data found, use default 6% tax rate
            default_tax_rate = 6.0
            default_tax_amount = subtotal * (default_tax_rate / 100)
            tax_amount = default_tax_amount
            tax_breakdown.append({
                "Description": f"Default Tax Rate ({default_tax_rate}%)",
                "Amount": default_tax_amount
            })
            using_default_tax = True
            
    except Exception as e:
        st.warning(f"Error calculating taxes: {str(e)}")
        # Fall back to default tax rate if there's an error
        default_tax_rate = 6.0
        default_tax_amount = subtotal * (default_tax_rate / 100)
        tax_amount = default_tax_amount
        tax_breakdown.append({
            "Description": f"Default Tax Rate ({default_tax_rate}%)",
            "Amount": default_tax_amount
        })
        using_default_tax = True
    
    return tax_amount, tax_breakdown, using_default_tax

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
