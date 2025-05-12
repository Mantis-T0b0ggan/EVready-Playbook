import streamlit as st

def configure_page():
    """Configure page settings and initialize session state variables."""
    # Configure page settings
    st.set_page_config(
        page_title="EVready Playbook",
        page_icon="⚡",
        layout="wide", 
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state variables
    if 'bill_calculated' not in st.session_state:
        st.session_state.bill_calculated = False
    if 'current_bill' not in st.session_state:
        st.session_state.current_bill = None
    if 'comparison_results' not in st.session_state:
        st.session_state.comparison_results = []
    if 'bill_df' not in st.session_state:
        st.session_state.bill_df = None
    if 'bill_breakdown' not in st.session_state:
        st.session_state.bill_breakdown = {}
    if 'comparison_breakdowns' not in st.session_state:
        st.session_state.comparison_breakdowns = []

def get_months():
    """Return list of months for billing period selection."""
    return [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

def get_summer_months():
    """Return list of summer months for seasonal rate calculations."""
    return ["June", "July", "August", "September"]

def get_winter_months():
    """Return list of winter months for seasonal rate calculations."""
    return ["December", "January", "February", "March"]

def add_custom_styles():
    """Add custom CSS to the Streamlit app."""
    st.markdown(
        """
        <style>
            .centered {
                display: flex;
                justify-content: center;
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 2px;
            }
            .stTabs [data-baseweb="tab"] {
                height: 50px;
                white-space: pre-wrap;
                background-color: #f0f2f6;
                border-radius: 4px 4px 0px 0px;
                gap: 1px;
                padding-top: 10px;
                padding-bottom: 10px;
            }
            .stTabs [aria-selected="true"] {
                background-color: #ffffff;
                border-bottom: none;
                border-radius: 4px 4px 0px 0px;
                font-weight: bold;
            }
            div[data-testid="stDecoration"] {
                background-image: linear-gradient(90deg, #4CAF50, #87CEEB);
            }
            div.stButton > button:first-child {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            div.stButton > button:hover {
                background-color: #45a049;
                color: white;
            }
        </style>
        """, 
        unsafe_allow_html=True
    )

def get_currency_formatter():
    """Return a function to format currency values."""
    def format_currency(value):
        return f"${value:,.2f}"
    return format_currency
