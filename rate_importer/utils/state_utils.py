"""
Utility functions for state handling in the Rate Importer application.
Provides utility functions for working with US states.
"""

def get_us_states():
    """
    Returns a dictionary of US state codes and their full names.
    
    Returns:
        dict: Dictionary mapping state codes to state names
    """
    return {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", 
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", 
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", 
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", 
        "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", 
        "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", 
        "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", 
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", 
        "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", 
        "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", 
        "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", 
        "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", 
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
    }

def get_state_name(state_code):
    """
    Get the full state name for a state code.
    
    Args:
        state_code (str): Two-letter state code
        
    Returns:
        str: Full state name or the original code if not found
    """
    states = get_us_states()
    return states.get(state_code.upper(), state_code)

def get_state_choices():
    """
    Returns a list of (code, name) tuples for use in dropdown menus.
    
    Returns:
        list: List of tuples with state code and name
    """
    states = get_us_states()
    return [(code, name) for code, name in states.items()]
