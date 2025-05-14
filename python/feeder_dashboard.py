import streamlit as st
import sqlite3
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="Bee Pump Monitoring Dashboard",
    page_icon="💧",
    layout="wide",
)

# Database file
DATABASE = "res.db"

# Function to connect to the database
def connect_db():
    conn = sqlite3.connect(DATABASE)
    return conn

# Function to fetch data from the database
def fetch_data():
    conn = connect_db()
    query = "SELECT * FROM pumplog ORDER BY Timestamp DESC"  # Order by timestamp descending for latest first
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Convert Timestamp to datetime if it's not already
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    
    return df

# Function to calculate total pumped volume
def calculate_total_volume(df):
    total_pumps = len(df)
    total_volume_ml = total_pumps * 2.6
    return total_volume_ml

# Function to prepare time series data
def prepare_time_series_data(df):
    if df.empty:
        return pd.DataFrame(columns=['Timestamp', 'Cumulative_Pumps', 'Cumulative_Volume_ml'])
    
    # Sort by timestamp (ascending)
    df_sorted = df.sort_values('Timestamp')
    
    # Create a new dataframe with cumulative counts
    time_series = pd.DataFrame()
    time_series['Timestamp'] = df_sorted['Timestamp']
    time_series['Cumulative_Pumps'] = range(1, len(df_sorted) + 1)
    time_series['Cumulative_Volume_ml'] = time_series['Cumulative_Pumps'] * 2.6
    
    return time_series

# Function to get today's data
def get_today_data(df):
    if df.empty:
        return pd.DataFrame(columns=df.columns)
    
    # Get today's date
    today = datetime.datetime.now().date()
    
    # Filter data for today
    today_df = df[df['Timestamp'].dt.date == today]
    
    return today_df

# Create the database and table if they don't exist (initial setup)
conn = connect_db()
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS pumplog (
        ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        pump_id TEXT
    )
""")
conn.commit()
conn.close()

# Sidebar
st.sidebar.title("Dashboard Controls")
if st.sidebar.button("Refresh Data", use_container_width=True):
    st.rerun()

st.sidebar.write(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Main dashboard
st.title("Bee Pump Monitoring Dashboard")

# Fetch data
df = fetch_data()

# Calculate total volume
total_volume_ml = calculate_total_volume(df)

# Get today's data
today_df = get_today_data(df)
today_pumps = len(today_df)
today_volume_ml = today_pumps * 2.6

# Prepare time series data
time_series_df = prepare_time_series_data(df)

# Create tabs for different views
tab1, tab2 = st.tabs(["Overview", "Time Series Analysis"])

# Tab 1: Overview
with tab1:
    # Create a row with metrics for all-time stats
    st.subheader("All-Time Statistics")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(label="Total Pumps", value=len(df))
    
    with col2:
        st.metric(label="Total Water Pumped (ml)", value=f"{total_volume_ml:.2f}")
    
    # Create a row with metrics for today's stats
    st.subheader("Today's Statistics")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(label="Pumps Today", value=today_pumps)
    
    with col2:
        st.metric(label="Water Pumped Today (ml)", value=f"{today_volume_ml:.2f}")
    
    # Display recent pump activity
    st.subheader("Recent Pump Activity")
    st.dataframe(df.head(10), use_container_width=True)
    
    # Display today's hourly activity
    if not today_df.empty:
        st.subheader("Today's Hourly Activity")
        
        # Group by hour and count pumps
        today_df['Hour'] = today_df['Timestamp'].dt.hour
        hourly_stats = today_df.groupby('Hour').size().reset_index(name='Pumps')
        hourly_stats['Volume_ml'] = hourly_stats['Pumps'] * 2.6
        
        # Create a bar chart for hourly pumping
        fig_hourly = px.bar(
            hourly_stats,
            x='Hour',
            y='Volume_ml',
            labels={'Hour': 'Hour of Day', 'Volume_ml': 'Volume Pumped (ml)'},
            title='Hourly Pumping Volume Today'
        )
        
        # Customize x-axis to show all hours (0-23)
        fig_hourly.update_xaxes(
            tickmode='array',
            tickvals=list(range(24)),
            ticktext=[f"{h:02d}:00" for h in range(24)]
        )
        
        st.plotly_chart(fig_hourly, use_container_width=True)

# Tab 2: Time Series Analysis
with tab2:
    st.subheader("Water Pumped Over Time")
    
    if not time_series_df.empty:
        # Create a time series chart with Plotly
        fig = go.Figure()
        
        # Add cumulative volume line
        fig.add_trace(go.Scatter(
            x=time_series_df['Timestamp'],
            y=time_series_df['Cumulative_Volume_ml'],
            mode='lines',
            name='Cumulative Volume (ml)',
            line=dict(color='blue', width=2)
        ))
        
        # Add individual pump events as markers
        fig.add_trace(go.Scatter(
            x=time_series_df['Timestamp'],
            y=time_series_df['Cumulative_Volume_ml'],
            mode='markers',
            name='Pump Events',
            marker=dict(color='red', size=8)
        ))
        
        # Customize the layout
        fig.update_layout(
            xaxis_title='Time',
            yaxis_title='Cumulative Volume (ml)',
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            height=500,
            margin=dict(l=20, r=20, t=30, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Daily pumping statistics
        st.subheader("Daily Pumping Statistics")
        
        # Create a copy of the dataframe with just the date part of the timestamp
        df_copy = df.copy()
        df_copy['Date'] = df_copy['Timestamp'].dt.date
        
        # Group by date and count pumps
        daily_stats = df_copy.groupby('Date').size().reset_index(name='Pumps')
        daily_stats['Volume_ml'] = daily_stats['Pumps'] * 2.6
        
        # Create a bar chart for daily pumping
        fig_daily = px.bar(
            daily_stats,
            x='Date',
            y='Volume_ml',
            labels={'Date': 'Date', 'Volume_ml': 'Volume Pumped (ml)'},
            title='Daily Pumping Volume'
        )
        
        st.plotly_chart(fig_daily, use_container_width=True)
        
        # Display the daily statistics table
        st.dataframe(daily_stats, use_container_width=True)
    else:
        st.info("No pump data available yet.")
