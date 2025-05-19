import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

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
        option_name = f"Option {i+1}" + (" - Current Rate" if i == 0 else "")
        
        # Use the full schedule name (includes description)
        schedule_name = result["schedule_name"]
        
        data["Option"].append(option_name)
        data["Rate Name"].append(schedule_name)
        data["Present"].append(f"${result['total']:.2f}")
        data["Future (Projected)"].append(f"${result['projected']:.2f}")
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    return df, best_rate_id, projected_best

def create_comparison_visualization(comparison_results):
    """Create visual comparison of different rate schedules with improved clarity."""
    
    # Sort results by total cost (ascending)
    sorted_results = sorted(comparison_results, key=lambda x: x["total"])
    
    # Prepare data for chart
    labels = []
    values = []
    colors = []
    
    current_rate_id = comparison_results[0]["schedule_id"]
    
    for result in sorted_results:
        # Extract the short name (without description)
        schedule_name = result["schedule_name"].split(" - ")[0] if " - " in result["schedule_name"] else result["schedule_name"]
        
        labels.append(schedule_name)
        values.append(result['total'])
        colors.append('#ff7f0e' if result['schedule_id'] == current_rate_id else '#1f77b4')
    
    # Create horizontal bar chart with improved styling
    fig, ax = plt.subplots(figsize=(10, max(3, len(labels) * 0.6)))
    
    # Create horizontal bars with better spacing
    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, height=0.4, color=colors)
    
    # Set y-tick labels with the rate names
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=11, fontweight='bold')
    
    # Add data labels with better positioning and contrast
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 5, bar.get_y() + bar.get_height()/2, f'${width:,.2f}',
                ha='left', va='center', fontweight='bold', fontsize=11, 
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))
    
    # Add a legend with better positioning
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#ff7f0e', label='Current Rate'),
        Patch(facecolor='#1f77b4', label='Alternative Rates')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    # Customize appearance
    ax.set_xlabel('Monthly Cost ($)', fontsize=12, fontweight='bold')
    ax.set_title('Rate Comparison', fontsize=14, fontweight='bold')
    
    # Add gridlines for better readability
    ax.grid(axis='x', linestyle='--', alpha=0.6, color='gray')
    ax.tick_params(axis='both', which='major', labelsize=10)
    
    # Set background color
    ax.set_facecolor('#f8f8f8')
    fig.patch.set_facecolor('white')
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Set x-axis to show dollar values with commas
    def currency_formatter(x, pos):
        return f'${x:,.0f}'
    ax.xaxis.set_major_formatter(FuncFormatter(currency_formatter))
    
    # Ensure left margin for labels
    plt.tight_layout()
    
    return fig

def create_cost_breakdown_comparison(comparison_results):
    """Create stacked bar chart showing cost breakdown across rate schedules with better clarity."""
    
    # Prepare data structure
    rate_names = []
    service_charges = []
    energy_charges = []
    demand_charges = []
    other_charges = []
    tax_amounts = []
    totals = []
    
    for i, result in enumerate(comparison_results):
        # Extract name
        schedule_name = result["schedule_name"].split(" - ")[0] if " - " in result["schedule_name"] else result["schedule_name"]
        rate_names.append(schedule_name)
        totals.append(result["total"])
        
        # Get detailed breakdown for this rate
        if "breakdown" in result:
            breakdown = result["breakdown"]
            service_charges.append(breakdown.get('service_charge', 0))
            energy_charges.append(breakdown.get('energy_charge', 0))
            demand_charges.append(breakdown.get('demand_charge', 0))
            other_charges.append(breakdown.get('other_charges', 0))
            tax_amounts.append(breakdown.get('tax_amount', 0))
        else:
            # Fallback if detailed breakdown not available
            service_charges.append(0)
            energy_charges.append(0)
            demand_charges.append(0)
            other_charges.append(0)
            tax_amounts.append(0)
    
    # Create figure with better styling
    fig, ax = plt.subplots(figsize=(12, max(4, len(rate_names) * 0.6)))
    
    # Create stacked bars
    bar_width = 0.5
    y_pos = np.arange(len(rate_names))
    
    # Bottom positions for stacking
    bottoms = np.zeros(len(rate_names))
    
    # Use more distinguishable colors
    component_data = [
        (service_charges, 'Service Charges', '#4878D0'),  # Blue
        (energy_charges, 'Energy Charges', '#EE854A'),    # Orange
        (demand_charges, 'Demand Charges', '#6ACC64'),    # Green
        (other_charges, 'Other Charges', '#D65F5F'),      # Red
        (tax_amounts, 'Taxes', '#956CB4')                 # Purple
    ]
    
    # Filter out components with all zeros
    component_data = [(data, label, color) for data, label, color in component_data if sum(data) > 0]
    
    # Track component positions for labels
    component_positions = {}
    
    for data, label, color in component_data:
        bars = ax.barh(y_pos, data, bar_width, left=bottoms, label=label, color=color)
        
        # Store midpoints of each component for labels
        for i, (value, bottom) in enumerate(zip(data, bottoms)):
            if value > max(totals) * 0.05:  # Only for significant components (>5% of max)
                midpoint = bottom + value/2
                if label not in component_positions:
                    component_positions[label] = []
                component_positions[label].append((i, midpoint, value))
        
        bottoms += np.array(data)
    
    # Add component labels after all bars are drawn
    for label, positions in component_positions.items():
        for i, x_mid, value in positions:
            # Only add labels for components that take up enough space
            if value > max(totals) * 0.07:  # Increased threshold for readability
                ax.text(x_mid, i, f"${value:,.0f}", 
                        ha='center', va='center', 
                        color='white', fontweight='bold', fontsize=10,
                        bbox=dict(facecolor='black', alpha=0.4, boxstyle='round,pad=0.2'))
    
    # Add total cost labels at the end of each bar with better contrast
    for i, total in enumerate(totals):
        ax.text(total + max(totals)*0.02, i, f'Total: ${total:,.2f}', 
                va='center', fontweight='bold', fontsize=11,
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=3))
    
    # Set y-tick labels with the rate names
    ax.set_yticks(y_pos)
    ax.set_yticklabels(rate_names, fontsize=11, fontweight='bold')
    
    # Customize appearance
    ax.set_xlabel('Cost ($)', fontsize=12, fontweight='bold')
    ax.set_title('Cost Breakdown Comparison', fontsize=14, fontweight='bold')
    
    # Position legend better - outside the plot
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), 
              fontsize=10, ncol=len(component_data))
    
    # Add gridlines
    ax.grid(axis='x', linestyle='--', alpha=0.4, color='gray')
    ax.tick_params(axis='both', which='major', labelsize=10)
    
    # Set background color
    ax.set_facecolor('#f8f8f8')
    fig.patch.set_facecolor('white')
    
    # Remove top and right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Format x-axis to show dollar values with commas
    def currency_formatter(x, pos):
        return f'${x:,.0f}'
    ax.xaxis.set_major_formatter(FuncFormatter(currency_formatter))
    
    # Add more space at the bottom for the legend
    plt.subplots_adjust(bottom=0.2)
    
    return fig

def create_bill_breakdown_chart(bill_breakdown):
    """Create a clean, professional pie chart with legend on the left and total at the bottom."""
    # Prepare data for pie chart
    chart_data = {
        'Category': [],
        'Amount': []
    }
    
    # Add components only if they exist and are > 0
    components = [
        ('Service Charge', 'service_charge'),
        ('Energy Charges', 'energy_charge'),
        ('Demand Charges', 'demand_charge'),
        ('Other Charges', 'other_charges'),
        ('Taxes', 'tax_amount')
    ]
    
    for label, key in components:
        if bill_breakdown.get(key, 0) > 0:
            chart_data['Category'].append(label)
            chart_data['Amount'].append(bill_breakdown[key])
    
    # Create DataFrame
    chart_df = pd.DataFrame(chart_data)
    
    if len(chart_df) == 0:
        # Return a figure with a "No data" message
        fig, ax = plt.subplots(figsize=(6, 6), facecolor='white')
        ax.text(0.5, 0.5, "No bill data available", ha='center', va='center', fontsize=14)
        ax.axis('off')
        return fig
    
    # Calculate total bill
    total = chart_df['Amount'].sum()
    
    # Calculate percentages
    chart_df['Percentage'] = chart_df['Amount'] / total * 100
    
    # Create a professional color palette
    colors = ['#4285F4', '#EA4335', '#34A853', '#FBBC05', '#8C9EFF']
    
    # Create figure with space for legend
    fig, ax = plt.subplots(figsize=(8, 5.5), facecolor='white')
    
    # Create pie chart without labels initially
    wedges, _ = ax.pie(
        chart_df['Amount'], 
        labels=None,  # No labels on the pie itself
        colors=colors[:len(chart_df)],
        startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5},
        shadow=False
    )
    
    # Add percentage labels inside the pie but only for segments > 3%
    for i, wedge in enumerate(wedges):
        pct = chart_df.iloc[i]['Percentage']
        if pct > 3:  # Only add percentage text for segments large enough
            ang = (wedge.theta2 - wedge.theta1) / 2. + wedge.theta1
            x = np.cos(np.deg2rad(ang)) * 0.5
            y = np.sin(np.deg2rad(ang)) * 0.5
            ax.text(
                x, y, 
                f"{pct:.1f}%", 
                ha='center', 
                va='center', 
                fontsize=12, 
                fontweight='bold', 
                color='white'
            )
    
    # Add a standalone legend - positioned to the left of the chart
    legend_labels = [f"{cat} (${amt:,.2f})" for cat, amt in zip(chart_df['Category'], chart_df['Amount'])]
    ax.legend(
        wedges, 
        legend_labels, 
        loc='center left', 
        bbox_to_anchor=(-0.35, 0.5),
        fontsize=11,
        frameon=True,
        edgecolor='lightgray',
        facecolor='white'
    )
    
    # Equal aspect ratio ensures that pie is drawn as a circle
    ax.axis('equal')
    
    # Add title with better styling
    plt.title('Bill Composition', fontsize=18, fontweight='bold', pad=15)
    
    # Add total at the bottom with improved styling
    plt.annotate(
        f"Total Bill: ${total:,.2f}",
        xy=(0.5, -0.1),
        xycoords='axes fraction',
        ha='center',
        fontsize=14,
        fontweight='bold',
        bbox=dict(boxstyle="round,pad=0.4", facecolor='#f8f8f8', edgecolor='lightgray', alpha=0.7)
    )
    
    # Adjust subplot positioning to make room for the legend on the left
    plt.subplots_adjust(left=0.35, bottom=0.15)
    
    return fig

def generate_savings_analysis(comparison_results):
    """Generate text and figures for savings analysis."""
    
    # Find the best (lowest cost) option
    best_option = min(comparison_results, key=lambda x: x["total"])
    current_bill = comparison_results[0]  # The first result is the current rate
    
    savings = current_bill["total"] - best_option["total"]
    annual_savings = savings * 12
    
    # Get the current rate name, handling possible formatting issues
    try:
        if " - " in current_bill["schedule_name"]:
            current_name = current_bill["schedule_name"].split(" - ")[0]
        else:
            current_name = current_bill["schedule_name"]
    except (KeyError, IndexError, AttributeError):
        current_name = "current rate"
    
    # Create savings analysis result
    if savings > 0 and best_option["schedule_id"] != current_bill["schedule_id"]:
        # Get the best rate name, handling possible formatting issues
        try:
            if " - " in best_option["schedule_name"]:
                best_name = best_option["schedule_name"].split(" - ")[0]
            else:
                best_name = best_option["schedule_name"]
        except (KeyError, IndexError, AttributeError):
            best_name = "alternative rate"
            
        savings_text = (
            f"**Potential Savings**: Switching to '{best_name}' "
            f"could save approximately ${savings:.2f} per month based on your current usage.\n\n"
            f"**Annual Savings**: This amounts to approximately ${annual_savings:.2f} per year."
        )
        is_current_best = False
    else:
        savings_text = (
            f"**Current Rate Optimal**: Your current rate '{current_name}' appears to be "
            f"the most cost-effective option based on your usage pattern."
        )
        is_current_best = True
    
    return savings_text, is_current_best, savings, annual_savings
