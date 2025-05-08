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