# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from pybaseball import statcast_pitcher, playerid_lookup, pitching_stats

# Streamlit App Setup
st.set_page_config(page_title="MLB Pitcher Scouting Tool", layout="wide")
st.title("MLB Pitcher Scouting Tool")

# Helpers & Caching
@st.cache_data(show_spinner=False)
def load_statcast(season: int, pitcher_mlbam: int) -> pd.DataFrame:
    return statcast_pitcher(f"{season}-03-01", f"{season}-11-30", pitcher_mlbam)

@st.cache_data(show_spinner=False)
def load_fg_pitching(season: int) -> pd.DataFrame:
    return pitching_stats(season, season)

def get_fg_row(fg_df: pd.DataFrame, fg_id: int | None, player_name: str | None) -> pd.Series | None:
    if fg_df is None or fg_df.empty:
        return None
    if fg_id is not None:
        m = fg_df.loc[fg_df["IDfg"] == int(fg_id)]
        if not m.empty:
            return m.iloc[0]
    if player_name:
        m2 = fg_df.loc[fg_df["Name"].str.contains(player_name, case=False, na=False)]
        if not m2.empty:
            return m2.iloc[0]
    return None

def compute_pa_level_rates(statcast_df: pd.DataFrame) -> tuple[float | None, float | None, int]:
    pa_df = statcast_df[statcast_df["events"].notna()]
    pa_count = len(pa_df)
    if pa_count == 0:
        return None, None, 0
    k_pct = round((pa_df["events"].eq("strikeout").mean()) * 100, 1)
    bb_pct = round((pa_df["events"].eq("walk").mean()) * 100, 1)
    return k_pct, bb_pct, pa_count

def compute_pitch_metrics(statcast_df: pd.DataFrame) -> dict:
    desc = statcast_df["description"].fillna("")
    strike_descriptions = {"called_strike", "swinging_strike", "swinging_strike_blocked",
                           "foul", "foul_tip", "foul_bunt"}
    swing_descriptions = {"swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "hit_into_play"}

    total_pitches = len(statcast_df)
    strikes = desc.isin(strike_descriptions).sum()
    swings = desc.isin(swing_descriptions).sum()
    whiffs = desc.isin({"swinging_strike", "swinging_strike_blocked"}).sum()

    strike_pct = round((strikes / total_pitches) * 100, 1) if total_pitches else None
    whiff_pct = round((whiffs / swings) * 100, 1) if swings else None

    batted = statcast_df[statcast_df["launch_speed"].notna()]
    avg_ev = round(batted["launch_speed"].mean(), 1) if not batted.empty else None
    avg_la = round(batted["launch_angle"].mean(), 1) if not batted.empty else None

    return {
        "Total Pitches": total_pitches,
        "Strike %": strike_pct,
        "Whiff % (Swings)": whiff_pct,
        "Avg Exit Velo": avg_ev,
        "Avg Launch Angle": avg_la,
    }

# Sidebar: Player Search
st.sidebar.header("Pitcher Search")
first = st.sidebar.text_input("First Name (e.g., Gerrit)")
last = st.sidebar.text_input("Last Name (e.g., Cole)")
season = st.sidebar.selectbox("Season", list(range(2015, 2026))[::-1])

pitcher_id = None
player_name = None
fg_id = None

if first and last:
    try:
        lookup = playerid_lookup(last, first)
        if not lookup.empty:
            row0 = lookup.iloc[0]
            pitcher_id = int(row0.get("key_mlbam"))
            fg_id = int(row0.get("key_fangraphs")) if pd.notna(row0.get("key_fangraphs")) else None
            player_name = f"{row0.get('name_first')} {row0.get('name_last')}"
            st.sidebar.success(f"Found {player_name} (MLBAM {pitcher_id}{', FG ' + str(fg_id) if fg_id else ''})")
        else:
            st.sidebar.error("No player found with that name.")
    except Exception as e:
        st.sidebar.error(f"Lookup failed: {e}")

# Tabs
tab1, tab2 = st.tabs(["Pitcher Overview", "Situational Analysis"])

# Pitcher Overview
with tab1:
    st.header("Pitcher Overview")
    if pitcher_id:
        # Load Statcast
        with st.spinner(f"Loading Statcast for {player_name} ({season})..."):
            data = load_statcast(season, pitcher_id)

        # Load FanGraphs summary for ERA/WHIP/IP
        era = whip = ip = None
        try:
            with st.spinner(f"Fetching FanGraphs season stats ({season})..."):
                fg = load_fg_pitching(season)
                fg_row = get_fg_row(fg, fg_id, player_name)
                if fg_row is not None:
                    ip = float(fg_row["IP"])
                    era = float(fg_row["ERA"])
                    whip = float(fg_row["WHIP"])
                else:
                    st.info("FanGraphs row not found for this player/season; ERA/WHIP unavailable.")
        except Exception as e:
            st.info(f"FanGraphs lookup issue: {e}")

        if data is not None and not data.empty:
            k_pct, bb_pct, pa_count = compute_pa_level_rates(data)
            pitch_metrics = compute_pitch_metrics(data)

            # Assemble Basic Stats table 
            basic = {
                "IP": ip,
                "ERA": era,
                "WHIP": whip,
                "PAs Faced": pa_count,
                "K %": k_pct,
                "BB %": bb_pct,
                **pitch_metrics,
            }
            st.subheader(f"Basic Stats – {player_name} ({season})")
            st.dataframe(pd.DataFrame([basic]))

            # Pitch Mix
            st.subheader("Pitch Mix")
            label_col = "pitch_name" if "pitch_name" in data.columns else "pitch_type"
            mix = (
                data.dropna(subset=[label_col])
                    .groupby(label_col)
                    .size()
                    .reset_index(name="count")
                    .sort_values("count", ascending=False)
            )
            if not mix.empty:
                mix["usage %"] = mix["count"] / mix["count"].sum() * 100
                st.dataframe(mix.reset_index(drop=True))

                # Pitch Usage Pie Chart
                fig = px.pie(
                    mix,
                    values="usage %",
                    names=label_col,
                    title=f"Pitch Usage – {player_name} ({season})",
                    hover_data=["count"],
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No pitch mix data available.")
        else:
            st.warning("No Statcast data found for this pitcher/season.")

