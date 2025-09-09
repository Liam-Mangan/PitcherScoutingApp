# PitcherScoutingApp.py
import streamlit as st
import pandas as pd
import plotly.express as px
from pybaseball import statcast_pitcher, playerid_lookup, pitching_stats

# Streamlit App Config
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
    k_pct = round(pa_df["events"].eq("strikeout").mean() * 100, 1)
    bb_pct = round(pa_df["events"].eq("walk").mean() * 100, 1)
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
        "Whiff %": whiff_pct,
        "Avg Exit Velo": avg_ev,
        "Avg Launch Angle": avg_la,
    }

def format_num(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        s = f"{val:.2f}".rstrip("0").rstrip(".")
        return s
    return val

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
            pitcher_id = int(row0.get("key_mlbam")) if pd.notna(row0.get("key_mlbam")) else None
            fg_id = int(row0.get("key_fangraphs")) if pd.notna(row0.get("key_fangraphs")) else None
            player_name = f"{row0.get('name_first')} {row0.get('name_last')}"
            st.sidebar.success(f"Found {player_name} (MLBAM {pitcher_id}{', FG ' + str(fg_id) if fg_id else ''})")
        else:
            st.sidebar.error("No player found with that name.")
    except Exception as e:
        st.sidebar.error(f"Lookup failed: {e}")

# Tabs
tab1, tab2 = st.tabs(["Pitcher Overview", "Situational Analysis"])

# --- Pitcher Overview ---
with tab1:
    st.header("Pitcher Overview")
    if pitcher_id is None:
        st.info("Enter a player's first and last name in the sidebar to begin.")
    else:
        with st.spinner(f"Loading data for {player_name} ({season})..."):
            data = load_statcast(season, pitcher_id)
            fg = load_fg_pitching(season)

        era = whip = ip = None
        fg_row = get_fg_row(fg, fg_id, player_name) if fg is not None else None
        if fg_row is not None:
            try: ip = round(float(fg_row["IP"]), 1)
            except: ip = None
            try: era = round(float(fg_row["ERA"]), 2)
            except: era = None
            try: whip = round(float(fg_row["WHIP"]), 2)
            except: whip = None

        if data is None or data.empty:
            st.warning(f"No Statcast data found for {player_name} in {season}.")
        else:
            k_pct, bb_pct, pa_count = compute_pa_level_rates(data)
            pitch_metrics = compute_pitch_metrics(data)

            stats = {
                "IP": ip,
                "ERA": era,
                "WHIP": whip,
                "PAs Faced": pa_count,
                "K %": k_pct,
                "BB %": bb_pct,
                **pitch_metrics,
            }

            st.subheader(f"Basic Stats – {player_name} ({season})")
            st.caption("ERA, WHIP, and IP are from FanGraphs when available; other numbers are from Statcast.")
            
            per_row = 4
            stats_items = list(stats.items())
            for i in range(0, len(stats_items), per_row):
                row_items = stats_items[i : i + per_row]
                cols = st.columns(len(row_items))
                for (label, value), col in zip(row_items, cols):
                    if value is None:
                        col.markdown(f"**{label}**\n\n<div style='font-size:20px'>—</div>", unsafe_allow_html=True)
                    else:
                        try:
                            v_float = float(value)
                            col.metric(label, format_num(v_float))
                        except:
                            col.markdown(f"**{label}**\n\n<div style='font-size:20px'>{value}</div>", unsafe_allow_html=True)

            st.subheader("Pitch Mix")
            label_col = "pitch_name" if "pitch_name" in data.columns else "pitch_type"
            mix = (
                data.dropna(subset=[label_col])
                    .groupby(label_col)
                    .size()
                    .reset_index(name="count")
                    .sort_values("count", ascending=False)
            )
            if mix.empty:
                st.warning("No pitch mix data available.")
            else:
                mix["usage %"] = mix["count"] / mix["count"].sum() * 100
                fig = px.pie(
                    mix,
                    values="usage %",
                    names=label_col,
                    title=f"Pitch Usage – {player_name} ({season})",
                    hover_data=["count"],
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)

# Situational Analysis 
with tab2:
    st.header("Situational Analysis")
    st.caption("Filter to inspect pitch usage in specific situations. Pitch mix shown as an interactive pie (hover for counts).")

    if pitcher_id is None:
        st.info("Enter a player's first and last name in the sidebar to begin.")
    else:
        if "data" not in locals() or data is None or data.empty:
            st.warning("Load pitcher data in the Pitcher Overview tab first.")
        else:
            compare_mode = st.checkbox("Compare two situations (side-by-side)", value=False)

            def apply_filters(df, handedness, count_option, outs_option, base_state_option):
                situ_df = df.copy()
                if handedness != "All":
                    handed_col = None
                    for c in ["stand", "bat_side", "batting_hand", "bat_hand", "batter_hand"]:
                        if c in situ_df.columns:
                            handed_col = c
                            break
                    if handed_col is not None:
                        want = "L" if handedness == "Left" else "R"
                        situ_df = situ_df[situ_df[handed_col] == want]
                if count_option != "All":
                    try:
                        balls, strikes = count_option.split("-")
                        situ_df = situ_df[(situ_df["balls"] == int(balls)) & (situ_df["strikes"] == int(strikes))]
                    except: pass
                if outs_option != "All":
                    situ_df = situ_df[situ_df["outs_when_up"] == int(outs_option)]
                # base state filters
                if base_state_option == "Empty":
                    situ_df = situ_df[situ_df["on_1b"].isna() & situ_df["on_2b"].isna() & situ_df["on_3b"].isna()]
                elif base_state_option == "Runners On":
                    situ_df = situ_df[situ_df["on_1b"].notna() | situ_df["on_2b"].notna() | situ_df["on_3b"].notna()]
                elif base_state_option == "RISP":
                    situ_df = situ_df[situ_df["on_2b"].notna() | situ_df["on_3b"].notna()]
                elif base_state_option == "First occupied":
                    situ_df = situ_df[situ_df["on_1b"].notna()]
                elif base_state_option == "First Only":
                    situ_df = situ_df[situ_df["on_1b"].notna() & situ_df["on_2b"].isna() & situ_df["on_3b"].isna()]
                elif base_state_option == "First & Second":
                    situ_df = situ_df[situ_df["on_1b"].notna() & situ_df["on_2b"].notna() & situ_df["on_3b"].isna()]
                elif base_state_option == "First & Third":
                    situ_df = situ_df[situ_df["on_1b"].notna() & situ_df["on_2b"].isna() & situ_df["on_3b"].notna()]
                elif base_state_option == "Second Only":
                    situ_df = situ_df[situ_df["on_1b"].isna() & situ_df["on_2b"].notna() & situ_df["on_3b"].isna()]
                elif base_state_option == "Second occupied":
                    situ_df = situ_df[situ_df["on_2b"].notna()]
                elif base_state_option == "Second & Third":
                    situ_df = situ_df[situ_df["on_1b"].isna() & situ_df["on_2b"].notna() & situ_df["on_3b"].notna()]
                elif base_state_option == "Third Only":
                    situ_df = situ_df[situ_df["on_1b"].isna() & situ_df["on_2b"].isna() & situ_df["on_3b"].notna()]
                elif base_state_option == "Third occupied":
                    situ_df = situ_df[situ_df["on_3b"].notna()]
                elif base_state_option == "Bases Loaded":
                    situ_df = situ_df[situ_df["on_1b"].notna() & situ_df["on_2b"].notna() & situ_df["on_3b"].notna()]
                return situ_df

            if not compare_mode:
                handedness = st.selectbox("Batter Handedness", ["All", "Left", "Right"])
                count_option = st.selectbox("Count", ["All", "0-0", "0-1", "1-0", "1-1", "0-2", "1-2", "2-2", "3-2", "3-0"])
                outs_option = st.selectbox("Outs", ["All", 0, 1, 2])
                base_state_option = st.selectbox("Base State", ["All", "Empty", "RISP", "Runners On",
                                                                "First occupied", "First Only", "First & Second", "First & Third",
                                                                "Second occupied", "Second Only", "Second & Third",
                                                                "Third occupied", "Third Only", "Bases Loaded"])
                situ_df = apply_filters(data, handedness, count_option, outs_option, base_state_option)
                st.write(f"Found {len(situ_df)} pitches matching filters.")
                if situ_df.empty:
                    st.info("No pitches found for this situation.")
                else:
                    label_col = "pitch_name" if "pitch_name" in situ_df.columns else "pitch_type"
                    situ_mix = (
                        situ_df.dropna(subset=[label_col])
                            .groupby(label_col)
                            .size()
                            .reset_index(name="count")
                            .sort_values("count", ascending=False)
                    )
                    if situ_mix.empty:
                        st.info("No pitch-type data available for this filtered situation.")
                    else:
                        situ_mix["usage %"] = situ_mix["count"] / situ_mix["count"].sum() * 100
                        fig2 = px.pie(
                            situ_mix,
                            values="usage %",
                            names=label_col,
                            title=f"Pitch Usage — {count_option}, Outs: {outs_option}, {base_state_option}",
                            hover_data=["count"],
                        )
                        fig2.update_traces(textposition="inside", textinfo="percent+label")
                        st.plotly_chart(fig2, use_container_width=True)
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Situation A")
                    hand1 = st.selectbox("Batter Handedness (A)", ["All", "Left", "Right"], key="hand1")
                    count1 = st.selectbox("Count (A)", ["All", "0-0", "0-1", "1-0", "1-1", "0-2", "1-2", "2-2", "3-2", "3-0"], key="count1")
                    outs1 = st.selectbox("Outs (A)", ["All", 0, 1, 2], key="outs1")
                    base1 = st.selectbox("Base State (A)", ["All", "Empty", "RISP", "Runners On",
                                                            "First occupied", "First Only", "First & Second", "First & Third",
                                                            "Second occupied", "Second Only", "Second & Third",
                                                            "Third occupied", "Third Only", "Bases Loaded"], key="base1")
                    situ_a = apply_filters(data, hand1, count1, outs1, base1)
                    st.write(f"{len(situ_a)} pitches")
                    if not situ_a.empty:
                        label_col = "pitch_name" if "pitch_name" in situ_a.columns else "pitch_type"
                        mix_a = (
                            situ_a.dropna(subset=[label_col])
                                .groupby(label_col)
                                .size()
                                .reset_index(name="count")
                                .sort_values("count", ascending=False)
                        )
                        mix_a["usage %"] = mix_a["count"] / mix_a["count"].sum() * 100
                        figA = px.pie(mix_a, values="usage %", names=label_col, hover_data=["count"])
                        figA.update_traces(textposition="inside", textinfo="percent+label")
                        st.plotly_chart(figA, use_container_width=True)

                with col2:
                    st.subheader("Situation B")
                    hand2 = st.selectbox("Batter Handedness (B)", ["All", "Left", "Right"], key="hand2")
                    count2 = st.selectbox("Count (B)", ["All", "0-0", "0-1", "1-0", "1-1", "0-2", "1-2", "2-2", "3-2", "3-0"], key="count2")
                    outs2 = st.selectbox("Outs (B)", ["All", 0, 1, 2], key="outs2")
                    base2 = st.selectbox("Base State (B)", ["All", "Empty", "RISP", "Runners On",
                                                            "First occupied", "First Only", "First & Second", "First & Third",
                                                            "Second occupied", "Second Only", "Second & Third",
                                                            "Third occupied", "Third Only", "Bases Loaded"], key="base2")
                    situ_b = apply_filters(data, hand2, count2, outs2, base2)
                    st.write(f"{len(situ_b)} pitches")
                    if not situ_b.empty:
                        label_col = "pitch_name" if "pitch_name" in situ_b.columns else "pitch_type"
                        mix_b = (
                            situ_b.dropna(subset=[label_col])
                                .groupby(label_col)
                                .size()
                                .reset_index(name="count")
                                .sort_values("count", ascending=False)
                        )
                        mix_b["usage %"] = mix_b["count"] / mix_b["count"].sum() * 100
                        figB = px.pie(mix_b, values="usage %", names=label_col, hover_data=["count"])
                        figB.update_traces(textposition="inside", textinfo="percent+label")
                        st.plotly_chart(figB, use_container_width=True)
