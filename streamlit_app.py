"""
Streamlit App: SMA Dashboard for S&P 500 Tickers
Allows selection by sector and/or ticker, displays price & SMA chart.
"""
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Optional

# ─── Page Config ───
st.set_page_config(
    page_title="S&P 500 SMA Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS for Compact Layout ───
st.markdown("""
<style>
    /* Reduce top padding */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }
    /* Compact metric cards */
    [data-testid="metric-container"] {
        padding: 0.25rem 0.5rem;
        background: transparent;
    }
    [data-testid="metric-container"] > div {
        padding: 0;
    }
    /* Reduce space between columns */
    .row-widget.stColumns {
        gap: 0.5rem;
    }
    /* Compact expander */
    .streamlit-expanderHeader {
        font-size: 0.85rem;
        padding: 0.25rem 0.5rem;
    }
    /* Tighter plot margins via matplotlib handled in code */
    /* Hide default streamlit padding around pyplot */
    .element-container:has(.stPyplot) {
        margin-top: -1rem;
        margin-bottom: -1rem;
    }
    /* Compact sidebar */
    .css-1d391kg {
        padding-top: 1rem;
    }
    /* Reduce caption size */
    .stCaption {
        font-size: 0.75rem;
        margin-bottom: 0.25rem;
    }
    /* Tighten markdown margins */
    .stMarkdown p {
        margin-bottom: 0.35rem;
    }
    /* Sub-industry: allow wrap, smaller font */
    .sub-industry-text {
        font-size: 0.7rem !important;
        line-height: 1.2 !important;
        white-space: normal !important;
        word-break: break-word !important;
        overflow-wrap: anywhere !important;
        max-width: 100%;
    }
    /* Metric label smaller */
    [data-testid="metric-container"] label {
        font-size: 0.65rem !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── Load Environment & Create Engine ───
@st.cache_resource
def get_engine():
    load_dotenv(override=True)
    BILLING_PROJECT = os.getenv("BILLING_PROJECT_ID", "dsaimodule2-509312")
    DATASET = os.getenv("DATASET_ID", "proj2sp500")
    DATABASE_URL = f"bigquery://{BILLING_PROJECT}/{DATASET}"
    return create_engine(DATABASE_URL), BILLING_PROJECT, DATASET

engine, BILLING_PROJECT, DATASET = get_engine()

# ─── Data Access Functions ───
@st.cache_data(ttl=3600)
def get_all_tickers():
    """Fetch all tickers with metadata from dim_ticker."""
    query = f"""
        SELECT ticker, company, sector, sub_industry
        FROM `{BILLING_PROJECT}.{DATASET}.dim_ticker`
        WHERE sector IS NOT NULL
        ORDER BY sector, ticker
    """
    return pd.read_sql(query, con=engine)

@st.cache_data(ttl=3600)
def get_sectors():
    """Fetch distinct sectors."""
    df = get_all_tickers()
    return sorted(df['sector'].unique().tolist())

@st.cache_data(ttl=300)
def get_ticker_data(ticker: str, days: int = 180):
    """Fetch latest price & SMA data for a ticker."""
    query = f"""
        SELECT
            date,
            ticker,
            close AS price,
            sma_20,
            sma_50,
            sma_100,
            sma_200,
            mkt_cap
        FROM `{BILLING_PROJECT}.{DATASET}.fact_dailyprice`
        WHERE ticker = '{ticker}'
          AND date >= DATE_SUB(
              (SELECT MAX(date) FROM `{BILLING_PROJECT}.{DATASET}.fact_dailyprice`),
              INTERVAL {days} DAY
          )
        ORDER BY date ASC
    """
    df = pd.read_sql(query, con=engine)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

# ─── Plotting Function ───
def plot_ticker_sma(
    df: pd.DataFrame,
    ticker: str,
    days: int = 180,
    show_sma_200: bool = False,
    figsize: tuple = (12, 4.5),
) -> plt.Figure:
    """Create Matplotlib figure for ticker SMA chart (compact)."""
    fig, ax = plt.subplots(figsize=figsize)

    # Price (thicker, prominent)
    ax.plot(df['date'], df['price'], label='Price (Close)', linewidth=2, color='#1f77b4', alpha=0.95)

    # SMA lines
    ax.plot(df['date'], df['sma_20'], label='SMA 20', linewidth=1, color='#ff7f0e', alpha=0.85)
    ax.plot(df['date'], df['sma_50'], label='SMA 50', linewidth=1, color='#2ca02c', alpha=0.85)
    ax.plot(df['date'], df['sma_100'], label='SMA 100', linewidth=1, color='#d62728', alpha=0.85)

    if show_sma_200:
        ax.plot(df['date'], df['sma_200'], label='SMA 200', linewidth=1, color='#7f7f7f', alpha=0.7, linestyle='--')

    # Compact formatting
    ax.set_title(f"{ticker} — Price & SMAs (Latest {days} Days)", fontsize=12, fontweight='bold', pad=8)
    ax.set_xlabel('Date', fontsize=10)
    ax.set_ylabel('Price (USD)', fontsize=10)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, ncols=2 if show_sma_200 else 1)
    ax.grid(True, alpha=0.25)

    # Date formatting on x-axis
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
    plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=8)
    plt.setp(ax.get_yticklabels(), fontsize=8)

    plt.tight_layout(pad=0.5)
    return fig

# ─── Sidebar Controls ───
st.sidebar.header("📊 Chart Controls")

# Load ticker metadata
tickers_df = get_all_tickers()
sectors = get_sectors()

# Sector filter (optional)
selected_sector = st.sidebar.selectbox(
    "Sector (optional)",
    options=["All Sectors"] + sectors,
    index=0,
    help="Filter tickers by sector. Leave as 'All Sectors' to see all tickers."
)

# Filter tickers based on sector selection
if selected_sector != "All Sectors":
    filtered_tickers = tickers_df[tickers_df['sector'] == selected_sector]['ticker'].tolist()
else:
    filtered_tickers = tickers_df['ticker'].tolist()

# Ticker selection
selected_ticker = st.sidebar.selectbox(
    "Ticker",
    options=filtered_tickers,
    index=0 if filtered_tickers else None,
    help="Select a ticker to display its SMA chart."
)

# Lookback period
lookback_days = st.sidebar.slider(
    "Lookback Period (days)",
    min_value=30,
    max_value=365,
    value=180,
    step=30,
    help="Number of calendar days to fetch."
)

# SMA 200 toggle
show_sma_200 = st.sidebar.checkbox(
    "Show SMA 200",
    value=False,
    help="Include 200-day SMA line (dashed gray)."
)

# ─── Main Content ───
st.title("📈 S&P 500 SMA Dashboard")
st.caption(f"Data: BigQuery `{BILLING_PROJECT}.{DATASET}` • Updated daily")

if selected_ticker:
    # Get ticker metadata
    ticker_info = tickers_df[tickers_df['ticker'] == selected_ticker].iloc[0]
    
    # Fetch data first to get latest market cap
    with st.spinner(f"Fetching {selected_ticker}..."):
        df = get_ticker_data(selected_ticker, days=lookback_days)
    
    if df.empty:
        st.warning(f"No data for {selected_ticker} in last {lookback_days} days.")
    else:
        latest = df.iloc[-1]
        latest_mkt_cap = latest.get('mkt_cap', None)
        
        # Display ticker info - compact single row with market cap
        if latest_mkt_cap and latest_mkt_cap > 0:
            mkt_cap_str = f"${latest_mkt_cap/1e9:.2f}B" if latest_mkt_cap >= 1e9 else f"${latest_mkt_cap/1e6:.2f}M"
            col1, col2, col3, col4, col5 = st.columns([1, 1.2, 1.5, 1.5, 1.5])
            with col1:
                st.metric("Ticker", ticker_info['ticker'])
            with col2:
                st.metric("Sector", ticker_info['sector'])
            with col3:
                st.markdown(f"<div class='sub-industry-text'><b>Sub-Industry</b><br>{ticker_info['sub_industry']}</div>", unsafe_allow_html=True)
            with col4:
                st.caption(f"**{ticker_info['company']}**")
            with col5:
                st.metric("Market Cap", mkt_cap_str)
        else:
            col1, col2, col3, col4 = st.columns([1, 1.5, 1.5, 2])
            with col1:
                st.metric("Ticker", ticker_info['ticker'])
            with col2:
                st.metric("Sector", ticker_info['sector'])
            with col3:
                st.markdown(f"<div class='sub-industry-text'><b>Sub-Industry</b><br>{ticker_info['sub_industry']}</div>", unsafe_allow_html=True)
            with col4:
                st.caption(f"**{ticker_info['company']}**")
        
        # Chart - compact
        fig = plot_ticker_sma(df, selected_ticker, days=lookback_days, show_sma_200=show_sma_200)
        st.pyplot(fig, use_container_width=True)
        
        # Key stats row - compact
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Price", f"${latest['price']:.2f}")
        with m2:
            st.metric("SMA 20", f"${latest['sma_20']:.2f}", delta=f"${latest['price'] - latest['sma_20']:.2f}")
        with m3:
            st.metric("SMA 50", f"${latest['sma_50']:.2f}", delta=f"${latest['price'] - latest['sma_50']:.2f}")
        with m4:
            st.metric("SMA 100", f"${latest['sma_100']:.2f}", delta=f"${latest['price'] - latest['sma_100']:.2f}")
        
        # Data table - compact expandable
        with st.expander("📋 Latest 10 Rows", expanded=False):
            display_df = df.tail(10).copy()
            display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
            for col in ['price', 'sma_20', 'sma_50', 'sma_100', 'sma_200']:
                display_df[col] = display_df[col].round(2)
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=280)

else:
    st.info("👈 Select a ticker from sidebar to display SMA chart.")
    
    # Sector summary - compact
    st.markdown("**Available Sectors & Counts**")
    sector_counts = tickers_df.groupby('sector').size().reset_index(name='count').sort_values('count', ascending=False)
    st.dataframe(sector_counts, use_container_width=True, hide_index=True, height=300)

# ─── Footer ───
st.markdown("---")
st.caption(
    "Built with Streamlit • Data from `fact_dailyprice` & `dim_ticker` tables • "
    "SMA values pre-computed in BigQuery"
)