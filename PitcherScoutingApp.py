import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt 
from pybaseball import playerid_lookup, statcast_pitcher

# Streamlit App Layout

st.set_page_config(page_title="MLB Pitcher Scouting Tool", layout="wide")

st.title("MLB Pitcher Scouting Tool")

# Sidebar controls
st.sidebar.header("Pitcher Search")
first = st.sidebar.text_input("First Name (e.g., Gerrit)")
last = st.sidebar.text_input("Last Name (e.g., Cole)")
season = st.sidebar.selectbox("Season", list(range(2015, 2025))[::-1])

pitcher_id = None
if first and last:
    try:
        player_info = playerid_lookup(last, first)
        if not player_info.empty:
            pitcher_id = int(player_info.iloc[0]["key_mlbam"])
            st.sidebar.success(f"Found {first} {last} (MLBAM ID: {pitcher_id})")
        else:
            st.sidebar.error("No player found with that name.")
    except Exception as e:
        st.sidebar.error(f"Lookup failed: {e}")

# Tabs
tab1, tab2 = st.tabs(["Pitcher Overview", "Situational Analysis"])