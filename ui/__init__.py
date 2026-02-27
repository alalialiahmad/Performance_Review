"""
ui — User interface modules for the Parking Analytics application.

Shared constants for colors, fonts, and styling used across all tabs.
"""

# Color palette for KPI status indicators
COLORS = {
    "green": "#27AE60",
    "yellow": "#F39C12",
    "red": "#E74C3C",
    "bg_dark": "#1a1a2e",
    "card_bg": "#16213e",
    "text": "#e0e0e0",
    "accent": "#0f3460",
    "border": "#2a2a4a",
    "header_bg": "#4472C4",
}

# Status to color mapping
STATUS_COLORS = {
    "good": COLORS["green"],
    "warning": COLORS["yellow"],
    "critical": COLORS["red"],
}

# Font definitions
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SUBTITLE = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 12)
FONT_SMALL = ("Segoe UI", 10)
FONT_KPI_VALUE = ("Segoe UI", 28, "bold")
FONT_KPI_LABEL = ("Segoe UI", 11)
FONT_TABLE_HEADER = ("Segoe UI", 11, "bold")
FONT_TABLE_BODY = ("Segoe UI", 10)

# Chart colors for matplotlib
CHART_BG = "#1a1a2e"
CHART_FACE = "#16213e"
CHART_TEXT = "#e0e0e0"
CHART_GRID = "#2a2a4a"

# Pie chart color palette for 7 manual review reasons
REASON_COLORS = [
    "#3498DB", "#E74C3C", "#F39C12", "#9B59B6",
    "#1ABC9C", "#E67E22", "#2ECC71",
]
