import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

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