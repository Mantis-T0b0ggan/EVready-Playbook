import streamlit as st
import pandas as pd
from datetime import datetime

def display_bill_results(state, utility, schedule_name, usage_inputs, rate_components):
    """Display the bill results from session state."""
    st.subheader("Bill Estimate")
    
    # Display the bill breakdown
    col1, col2 = st.columns(2)
    
    with col1:
        display_bill_summary(state, utility, schedule_name, usage_inputs, rate_components)
    
    with col2:
        display_charges_breakdown()

def display_bill_summary(state, utility, schedule_name, usage_inputs, rate_components):
    """Display the bill summary section."""
    st.markdown("### Bill Summary")
    st.markdown(f"**Selected State:** {state}")
    st.markdown(f"**Selected Utility:** {utility}")
    st.markdown(f"**Selected Schedule:** {schedule_name}")
    st.markdown(f"**Billing Month:** {usage_inputs.get('billing_month', '')}")
    
    if rate_components.get("has_energy_charges", False):
        st.markdown(f"**Energy Usage:** {usage_inputs.get('usage_kwh', 0)} kWh")
    if rate_components.get("has_demand_charges", False):
        st.markdown(f"**Peak Demand:** {usage_inputs.get('demand_kw', 0)} kW")
    if rate_components.get("has_reactive_demand", False):
        st.markdown(f"**Power Factor:** {usage_inputs.get('power_factor', 0.9)}")
    
    # Import visualization function
    from visualizations import create_bill_breakdown_chart
    
    # Add a simple pie chart for visualization
    if rate_components.get("has_energy_charges", False) or rate_components.get("has_demand_charges", False):
        st.markdown("### Bill Visualization")
        
        # Create and display the pie chart
        if "bill_breakdown" in st.session_state:
            fig = create_bill_breakdown_chart(st.session_state.bill_breakdown)
            st.pyplot(fig)
        else:
            st.info("Bill breakdown data not available for visualization.")

def display_charges_breakdown():
    """Display the detailed charges breakdown."""
    st.markdown("### Charges Breakdown")
    
    # Display the bill breakdown dataframe
    if "bill_df" in st.session_state and st.session_state.bill_df is not None:
        # Format the Amount column as currency
        df = st.session_state.bill_df.copy()
        df["Amount"] = df["Amount"].apply(lambda x: f"${x:,.2f}")
        st.table(df)
    else:
        st.warning("No charges found for this schedule.")

def display_comparison_results(comparison_results):
    """Display comparison results including tables and charts."""
    from visualizations import (
        create_comparison_dataframe, 
        create_comparison_visualization,
        create_cost_breakdown_comparison,
        generate_savings_analysis
    )
    
    # Create a comparison table using pandas DataFrame
    comparison_df, best_rate_id, projected_best = create_comparison_dataframe(comparison_results)
    
    # Display the comparison table
    st.subheader("Rate Comparison Table")
    st.dataframe(comparison_df, use_container_width=True)
    
    # Add a container for the visual comparisons
    with st.container():
        st.subheader("Visual Rate Comparison")
        st.caption("Monthly cost comparison between your current rate and alternatives")
        
        # Basic bar chart for rate comparison
        comparison_chart = create_comparison_visualization(comparison_results)
        st.pyplot(comparison_chart)
    
    # Add a container for the cost breakdown
    with st.container():
        st.subheader("Cost Breakdown Comparison")
        st.caption("See how different components contribute to your total bill")
        
        # Show cost breakdown comparison
        breakdown_chart = create_cost_breakdown_comparison(comparison_results)
        st.pyplot(breakdown_chart)
    
    # Add analysis text with better formatting
    st.markdown("---")
    
    # Generate savings analysis
    savings_text, is_current_best, savings, annual_savings = generate_savings_analysis(comparison_results)
    
    # Display with appropriate styling
    if is_current_best:
        st.success(savings_text)
    else:
        st.success(savings_text)

def create_usage_inputs(selected_schedule_id, rate_components, tab_key):
    """Create input forms for usage information."""
    if not selected_schedule_id:
        return {}
    
    usage_inputs = {}
    
    st.subheader("Enter Usage Information")
    
    # Billing period (month)
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    current_month_index = datetime.now().month - 1  # 0-based index
    
    billing_month_key = f"billing_month_{tab_key}"
    if billing_month_key not in st.session_state:
        st.session_state[billing_month_key] = months[current_month_index]
    
    billing_month = st.selectbox(
        "Billing Month", 
        months, 
        index=months.index(st.session_state[billing_month_key]) if st.session_state[billing_month_key] in months else current_month_index,
        key=f"billing_month_{tab_key}"
    )
    st.session_state[billing_month_key] = billing_month
    usage_inputs["billing_month"] = billing_month
    
    # Always ask for energy usage (kWh) if applicable
    if rate_components.get("has_energy_charges", False):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            usage_kwh_key = f"usage_kwh_{tab_key}"
            if usage_kwh_key not in st.session_state:
                st.session_state[usage_kwh_key] = 0.0
                
            usage_kwh = st.number_input(
                "Total Energy Usage (kWh)", 
                min_value=0.0, 
                step=10.0, 
                value=st.session_state[usage_kwh_key],
                key=f"usage_kwh_{tab_key}"
            )
            st.session_state[usage_kwh_key] = usage_kwh
            usage_inputs["usage_kwh"] = usage_kwh
        
        # Time-of-use energy inputs if applicable
        if rate_components.get("has_tou_energy", False) and rate_components.get("tou_periods", []):
            handle_tou_inputs(tab_key, usage_kwh, rate_components.get("tou_periods", []), usage_inputs)
    
    # Ask for demand if the schedule has demand charges
    if rate_components.get("has_demand_charges", False):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            demand_kw_key = f"demand_kw_{tab_key}"
            if demand_kw_key not in st.session_state:
                st.session_state[demand_kw_key] = 0.0
                
            demand_kw = st.number_input(
                "Peak Demand (kW)", 
                min_value=0.0, 
                step=1.0,
                value=st.session_state[demand_kw_key],
                key=f"demand_kw_{tab_key}"
            )
            st.session_state[demand_kw_key] = demand_kw
            usage_inputs["demand_kw"] = demand_kw
        
        # If reactive demand is applicable, show power factor input
        if rate_components.get("has_reactive_demand", False):
            with col2:
                power_factor_key = f"power_factor_{tab_key}"
                if power_factor_key not in st.session_state:
                    st.session_state[power_factor_key] = 0.9
                    
                power_factor = st.slider(
                    "Power Factor", 
                    min_value=0.7, 
                    max_value=1.0, 
                    value=st.session_state[power_factor_key], 
                    step=0.01,
                    key=f"power_factor_{tab_key}",
                    help="Power factor is the ratio of real power to apparent power in an electrical circuit."
                )
                st.session_state[power_factor_key] = power_factor
                usage_inputs["power_factor"] = power_factor
    
    return usage_inputs

def handle_tou_inputs(tab_key, usage_kwh, tou_periods, usage_inputs):
    """Handle time-of-use input fields."""
    st.subheader("Time-of-Use Energy Breakdown")
    st.info("Enter your energy usage for each time period. The total should equal your total energy usage.")
    
    # Create two columns for TOU inputs
    tou_cols = st.columns(2)
    col_idx = 0
    
    usage_by_tou_key = f"usage_by_tou_{tab_key}"
    if usage_by_tou_key not in st.session_state:
        st.session_state[usage_by_tou_key] = {}
    
    usage_by_tou = {}
    remaining_kwh = usage_kwh
    
    for i, period in enumerate(tou_periods):
        period_key = period['display']
        
        with tou_cols[col_idx]:
            if i == len(tou_periods) - 1:  # Last period
                # For the last period, show the remaining amount
                st.text(f"{period_key}")
                st.text(f"Remaining: {remaining_kwh:.1f} kWh")
                st.session_state[usage_by_tou_key][period_key] = remaining_kwh
                usage_by_tou[period_key] = remaining_kwh
            else:
                # Set default value for this period
                if period_key not in st.session_state[usage_by_tou_key]:
                    st.session_state[usage_by_tou_key][period_key] = 0.0
                    
                period_usage = st.number_input(
                    f"{period_key} (kWh)", 
                    min_value=0.0, 
                    max_value=usage_kwh if usage_kwh else 0.0,
                    step=1.0,
                    key=f"tou_energy_{i}_{tab_key}",
                    value=st.session_state[usage_by_tou_key][period_key]
                )
                
                st.session_state[usage_by_tou_key][period_key] = period_usage
                usage_by_tou[period_key] = period_usage
                remaining_kwh -= period_usage
        
        # Alternate columns
        col_idx = (col_idx + 1) % 2
    
    # Show warning if the sum doesn't match the total
    sum_tou = sum(usage_by_tou.values())
    if abs(sum_tou - usage_kwh) > 0.01 and usage_kwh > 0:
        st.warning(f"Time-of-use breakdown ({sum_tou:.1f} kWh) doesn't match your total energy usage ({usage_kwh:.1f} kWh). Please adjust your inputs.")
    
    # Add the usage_by_tou to the usage_inputs
    usage_inputs["usage_by_tou"] = usage_by_tou
