import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt 
from pybaseball import playerid_lookup, statcast_pitcher

# Streamlit App Layout

st.set_page_config(page_title="MLB Pitcher Scouting Tool", layout="wide")

st.title("MLB Pitcher Scouting Tool")

# Sidebar controls
st.sidebar.header("Pitcher Search")
pitcher_id = st.sidebar.text_input("Enter MLBAM ID (e.g., Gerrit Cole = 543037):")
season = st.sidebar.selectbox("Season", list(range(2015, 2025))[::-1])

# Tabs
tab1, tab2 = st.tabs(["Pitcher Overview", "Situational Analysis"])