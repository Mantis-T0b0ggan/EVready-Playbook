"""
UI package for the Rate Importer application.
Contains modules for different UI components and pages.
"""

# Import commonly used functions for easier access
from .components import create_header, show_result_message
from .utilities_page import render_utilities_section
from .schedules_page import render_schedules_section, render_schedule_details_section

# This allows imports like:
# from rate_importer.ui import create_header
# instead of:
# from rate_importer.ui.components import create_header
