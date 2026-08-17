import os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

# ---------------------------------------------------------
# 1. Page Config & Layout
# ---------------------------------------------------------
st.set_page_config(
    page_title="Macro AI Analytics: Energy, Inflation & Policy",
    page_icon="📈",
    layout="wide"
)

# Relative path to find the Excel workbook in the same directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
EXCEL_FILE_PATH = os.path.join(BASE_DIR, "Macro_Gas_GDP_Analysis.xlsx")

# ---------------------------------------------------------
# 2. Pydantic Schema for Gemini AI Report
# ---------------------------------------------------------
class PolicyEventInsight(BaseModel):
    event_or_policy: str = Field(description="Name of the historical event or policy")
    quarter: str = Field(description="Quarter when it occurred")
    economic_impact: str = Field(description="Economic impact on energy prices and Real GDP")

class ExecutiveMacroReport(BaseModel):
    headline: str = Field(description="High-level executive headline")
    executive_summary: str = Field(description="2-3 sentence overview")
    key_takeaways: List[str] = Field(description="3-4 analytical bullet points")
    policy_and_event_analysis: List[PolicyEventInsight] = Field(description="Breakdown of key events")

# ---------------------------------------------------------
# 3. Data Loading Helper (Cached for Performance)
# ---------------------------------------------------------
@st.cache_data
def load_macro_data(file_path: str):
    if not os.path.exists(file_path):
        st.error(f"Excel file not found at: {file_path}. Please run Gas_GDP.v3.py first!")
        st.stop()
    
    # Load raw data table starting from Row 6 (Header row)
    df = pd.read_excel(file_path, sheet_name='Quarterly_Macro_Data', skiprows=5)
    
    # Ensure Date column is parsed as datetime for clean Plotly continuous axis shading
    df['Date_dt'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
    
    # Load correlation matrices if available
    try:
        df_corr = pd.read_excel(file_path, sheet_name='Correlation_Matrix')
    except Exception:
        df_corr = None
        
    return df, df_corr

df_macro, df_corr_sheet = load_macro_data(EXCEL_FILE_PATH)

# ---------------------------------------------------------
# 4. Gemini API Call Helper (Cached)
# ---------------------------------------------------------
@st.cache_data
def get_gemini_summary(df_tail_csv: str, df_events_str: str) -> ExecutiveMacroReport:
    # Check Streamlit Cloud secrets first, fallback to laptop environment variable
    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    client = genai.Client(api_key=api_key)
    
    system_instruction = """
    You are a Senior Macroeconomic & Quantitative Portfolio Strategist.
    Analyze the multi-variable macroeconomic dataset (Crude, Gas, Real GDP, Grocery CPI, Headline CPI, Unemployment, 30-Yr Mortgage Rates, and Presidential administrations).
    Highlight the transmission mechanisms from energy shocks and legislative policies into inflation, rates, and real economic growth.
    """

    user_prompt = f"""
    Analyze the following quarterly dataset and historical event/policy markers:

    --- RECENT QUARTERLY DATA ---
    {df_tail_csv}

    --- HISTORICAL EVENT & POLICY MARKERS ---
    {df_events_str}

    Provide a structured executive briefing.
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=ExecutiveMacroReport,
            temperature=0.2,
        ),
    )
    return ExecutiveMacroReport.model_validate_json(response.text)

# ---------------------------------------------------------
# 5. Sidebar Controls & AI Executive Briefing
# ---------------------------------------------------------
st.sidebar.title("🤖 Gemini AI Analyst")
st.sidebar.markdown("---")

st.sidebar.subheader("Interactive Event Filters")
show_events = st.sidebar.checkbox("Show Historical Events", value=True)
show_policies = st.sidebar.checkbox("Show Policies & Sanctions", value=True)
show_presidents = st.sidebar.checkbox("Show Presidential Tenures (Shading)", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("Executive Briefing")

# Dynamically build the active Event/Policy text per row
df_macro['Events_Policies_Active'] = ""

for idx, row in df_macro.iterrows():
    text_parts = []
    if show_events and str(row['Historical Event Marker']) != 'None':
        text_parts.append(str(row['Historical Event Marker']))
    if show_policies and str(row['Policy & Legislative Marker']) != 'None':
        text_parts.append(str(row['Policy & Legislative Marker']))
    
    df_macro.at[idx, 'Events_Policies_Active'] = " | ".join(text_parts) if text_parts else "None"

# Gemini Executive Report Display
with st.sidebar:
    with st.spinner("Generating AI Briefing..."):
        recent_csv = df_macro.tail(40).to_csv(index=False)
        active_events = df_macro[df_macro['Events_Policies_Active'] != "None"][
            ['Quarter', 'WTI Crude ($/bbl)', 'Retail Gas ($/gal)', 'Real GDP ($B)', 'Events_Policies_Active', 'President']
        ].to_string(index=False)
        
        try:
            report = get_gemini_summary(recent_csv, active_events)
            st.success("Analysis Current")
            st.markdown(f"### {report.headline}")
            st.write(report.executive_summary)
            
            st.markdown("**Key Takeaways:**")
            for point in report.key_takeaways:
                st.markdown(f"• {point}")
        except Exception as e:
            st.warning(f"Could not load AI briefing: {e}")

# ---------------------------------------------------------
# 6. Main Dashboard Layout & KPI Metric Cards
# ---------------------------------------------------------
st.title("📊 Macroeconomic Dynamics & Policy Impact Dashboard")
st.markdown("Multi-factor time-series modeling with dynamic dual-axis charting and presidential timeline overlays.")

# Top Metric Cards
col1, col2, col3, col4, col5 = st.columns(5)
latest_row = df_macro.iloc[-1]

col1.metric("Quarter", str(latest_row['Quarter']))
col2.metric("WTI Crude", f"${latest_row['WTI Crude ($/bbl)']:.2f}", f"{latest_row['WTI YoY %']}% YoY")
col3.metric("Retail Gas", f"${latest_row['Retail Gas ($/gal)']:.2f}", f"{latest_row['Retail Gas YoY %']}% YoY")
col4.metric("Real GDP", f"${latest_row['Real GDP ($B)']:.1f}B", f"{latest_row['GDP Growth YoY %']}% YoY")
col5.metric("Unemployment", f"{latest_row['Unemployment Rate (%)']:.1f}%", f"Mortgage: {latest_row['30-Yr Mortgage Rate (%)']:.2f}%")

st.markdown("---")

# ---------------------------------------------------------
# 7. Dynamic Axis Selection Controls (Combo Boxes)
# ---------------------------------------------------------
st.subheader("Interactive Metric Selection")

selectable_metrics = [
    "WTI Crude ($/bbl)",
    "Retail Gas ($/gal)",
    "Real GDP ($B)",
    "Grocery CPI",
    "Headline CPI",
    "Unemployment Rate (%)",
    "30-Yr Mortgage Rate (%)",
    "GDP Delta %"
]

sel_col1, sel_col2 = st.columns(2)
with sel_col1:
    primary_metric = st.selectbox(
        "Select Primary Axis (Left Y-Axis):",
        options=selectable_metrics,
        index=1  # Default: Retail Gas ($/gal)
    )

with sel_col2:
    secondary_metric = st.selectbox(
        "Select Secondary Axis (Right Y-Axis):",
        options=selectable_metrics,
        index=2  # Default: Real GDP ($B)
    )

# ---------------------------------------------------------
# 8. Dual-Axis Plotly Chart Construction
# ---------------------------------------------------------
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Primary Axis Trace
fig.add_trace(
    go.Scatter(
        x=df_macro['Date_dt'],
        y=df_macro[primary_metric],
        name=f"Primary: {primary_metric}",
        line=dict(color="#1f77b4", width=2.5),
        hovertemplate=f"<b>Date</b>: %{{x|%m/%d/%Y}}<br><b>{primary_metric}</b>: %{{y}}<extra></extra>"
    ),
    secondary_y=False
)

# Secondary Axis Trace
fig.add_trace(
    go.Scatter(
        x=df_macro['Date_dt'],
        y=df_macro[secondary_metric],
        name=f"Secondary: {secondary_metric}",
        line=dict(color="#ff7f0e", width=2.5, dash="dot"),
        hovertemplate=f"<b>Date</b>: %{{x|%m/%d/%Y}}<br><b>{secondary_metric}</b>: %{{y}}<extra></extra>"
    ),
    secondary_y=True
)

# Overlay Event/Policy Markers (Diamonds on the Primary Line)
df_markers = df_macro[df_macro['Events_Policies_Active'] != "None"]
if not df_markers.empty:
    fig.add_trace(
        go.Scatter(
            x=df_markers['Date_dt'],
            y=df_markers[primary_metric],
            mode='markers',
            name='Historical Events & Policies',
            marker=dict(color='red', size=9, symbol='diamond', line=dict(width=1, color='darkred')),
            text=df_markers['Events_Policies_Active'],
            hovertemplate="<b>Date</b>: %{x|%m/%d/%Y}<br><b>Event/Policy</b>: %{text}<extra></extra>"
        ),
        secondary_y=False
    )

# Presidential Administrations (Background Shading & Annotations)
if show_presidents:
    presidential_terms = [
        {"name": "Clinton", "start": "2000-01-01", "end": "2001-01-20", "color": "rgba(31, 119, 180, 0.07)"},
        {"name": "Bush (43)", "start": "2001-01-20", "end": "2009-01-20", "color": "rgba(214, 39, 40, 0.07)"},
        {"name": "Obama", "start": "2009-01-20", "end": "2017-01-20", "color": "rgba(31, 119, 180, 0.07)"},
        {"name": "Trump (45)", "start": "2017-01-20", "end": "2021-01-20", "color": "rgba(214, 39, 40, 0.07)"},
        {"name": "Biden", "start": "2021-01-20", "end": "2025-01-20", "color": "rgba(31, 119, 180, 0.07)"},
        {"name": "Trump (47)", "start": "2025-01-20", "end": df_macro['Date_dt'].max().strftime('%Y-%m-%d'), "color": "rgba(214, 39, 40, 0.07)"}
    ]

    for term in presidential_terms:
        # Add shaded background rectangle
        fig.add_vrect(
            x0=term["start"],
            x1=term["end"],
            fillcolor=term["color"],
            layer="below",
            line_width=0,
        )
        # Add presidential label annotation at top of chart
        mid_date = pd.to_datetime(term["start"]) + (pd.to_datetime(term["end"]) - pd.to_datetime(term["start"])) / 2
        fig.add_annotation(
            x=mid_date,
            y=1.03,
            yref="paper",
            text=f"<b>{term['name']}</b>",
            showarrow=False,
            font=dict(size=10, color="#555555"),
            xanchor="center"
        )

# Chart Layout Configuration
fig.update_layout(
    title=dict(
        text=f"<b>Macro Trend Comparison: {primary_metric} vs. {secondary_metric}</b>",
        font=dict(size=16)
    ),
    height=650,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="right", x=1),
    template="plotly_white",
    margin=dict(t=100, b=40, l=40, r=40)
)

fig.update_xaxes(title_text="Date", showgrid=True, gridcolor="#f0f0f0")
fig.update_yaxes(title_text=f"<b>{primary_metric}</b>", secondary_y=False, showgrid=True, gridcolor="#f0f0f0")
fig.update_yaxes(title_text=f"<b>{secondary_metric}</b>", secondary_y=True, showgrid=False)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# 9. Expandable Raw Data & Correlation Tables
# ---------------------------------------------------------
col_view1, col_view2 = st.columns(2)

with col_view1:
    with st.expander("🔍 View Filtered Macroeconomic Dataset"):
        display_cols = ['Date', 'Quarter', primary_metric, secondary_metric, 'Events_Policies_Active', 'President']
        st.dataframe(df_macro[display_cols], use_container_width=True)

with col_view2:
    with st.expander("📐 View Correlation Matrices"):
        if df_corr_sheet is not None:
            st.dataframe(df_corr_sheet, use_container_width=True)
        else:
            st.write("Run `Gas_GDP.v3.py` to populate the `Correlation_Matrix` sheet.")