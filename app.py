import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime
import pandas as pd
import json

# 1. Page Configuration (Must be first)
st.set_page_config(page_title="AI Physical Trainer", page_icon="🏋️‍♂️", layout="wide", initial_sidebar_state="expanded")

# 2. Custom Premium UI CSS Injection
st.markdown("""
<style>
/* Cinematic Background with Dark Slate Overlay for Readability */
.stApp {
    background: linear-gradient(rgba(15, 23, 42, 0.85), rgba(15, 23, 42, 0.95)), url("https://images.unsplash.com/photo-1534438327276-14e5300c3a48?q=80&w=2070&auto=format&fit=crop");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    color: #ffffff;
}

/* Style the top metrics to look massive and premium */
[data-testid="stMetricValue"] {
    font-size: 2.5rem !important;
    color: #00ff88 !important; /* Electric Neon Green */
    font-weight: 800;
}
[data-testid="stMetricLabel"] {
    font-size: 1.1rem !important;
    color: #a0aec0 !important;
    font-weight: 600;
}

/* Style the Tabs to look like floating UI cards */
.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
    background-color: transparent;
}
.stTabs [data-baseweb="tab"] {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 8px 8px 0px 0px;
    padding: 12px 24px;
    color: #cbd5e1;
    border: 1px solid rgba(255,255,255,0.1);
    border-bottom: none;
}
.stTabs [aria-selected="true"] {
    background-color: #00ff88 !important;
    color: #0f172a !important;
    font-weight: 800;
}

/* Premium Primary Buttons */
div.stButton > button:first-child {
    background-color: #00ff88;
    color: #0f172a;
    font-weight: 800;
    border-radius: 8px;
    border: none;
    padding: 12px 24px;
    transition: all 0.3s ease;
}
div.stButton > button:first-child:hover {
    background-color: #00cc6a;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: rgba(15, 23, 42, 0.95);
    border-right: 1px solid rgba(255,255,255,0.1);
}
</style>
""", unsafe_allow_html=True)

# Fetch Secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
AIRTABLE_TOKEN = st.secrets["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

# Database Functions
def save_to_airtable(exercise, sets, reps, equipment, rpe):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Workout_Logs"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "records": [{
            "fields": {
                "Date": datetime.today().strftime('%Y-%m-%d'),
                "Exercise": exercise,
                "Sets": int(sets),
                "Reps": int(reps),
                "Equipment Used": equipment,
                "RPE": int(rpe)
            }
        }]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 200

@st.cache_data(ttl=60) # Caches data for 60 seconds to make app lightning fast
def fetch_airtable_data():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Workout_Logs"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('records', [])
    return []

def parse_ai_response(full_text):
    if "===LOG_DATA_START===" in full_text and "===LOG_DATA_END===" in full_text:
        parts = full_text.split("===LOG_DATA_START===")
        visual_plan = parts[0].strip()
        data_part = parts[1].split("===LOG_DATA_END===")[0].strip()
        return visual_plan, data_part
    return full_text, ""

# --- APP UI START ---
st.title("⚡ APEX AI: Coaching & Analytics")
st.markdown("---")

# Fetch data once for the whole app
records = fetch_airtable_data()

# Calculate High-Level Metrics for Dashboard
total_workouts = len(set([r.get('fields', {}).get('Date') for r in records if r.get('fields', {}).get('Date')]))
total_sets = sum([r.get('fields', {}).get('Sets', 0) for r in records])
total_volume = sum([r.get('fields', {}).get('Sets', 0) * r.get('fields', {}).get('Reps', 0) for r in records])

# Display Metrics
m1, m2, m3 = st.columns(3)
with m1: st.metric("Sessions Completed", f"{total_workouts}")
with m2: st.metric("Total Sets Pushed", f"{total_sets}")
with m3: st.metric("Total Rep Volume", f"{total_volume}")

st.markdown("<br>", unsafe_allow_html=True) # Spacer

# Navigation
tab1, tab2, tab3 = st.tabs(["🤖 Live Coaching Session", "📝 Manual Log", "📈 Progress Analytics"])

with tab1:
    st.sidebar.header("🎯 Start a New Session")
    workout_environment = st.sidebar.selectbox("Training Environment:", ["Gym (Full Equipment)", "Non-Gym (Bodyweight/Bands)", "Calisthenics (Bars/Rings/Floor)"])
    workout_focus = st.sidebar.selectbox("Session Focus:", ["Whole Body", "Specified Muscle Group"])
    
    specific_muscle = ""
    if workout_focus == "Specified Muscle Group":
        specific_muscle = st.sidebar.text_input("Target Muscle (e.g., Chest, Legs)")
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 Generate New Routine", use_container_width=True):
        with st.spinner("Analyzing history and crafting your session..."):
            recent_records = records[-10:] if len(records) > 10 else records
            history_text = "".join([f"- {r.get('fields', {}).get('Date')}: {r.get('fields', {}).get('Exercise')} ({r.get('fields', {}).get('Sets')}x{r.get('fields', {}).get('Reps')}) | RPE: {r.get('fields', {}).get('RPE')}/10\n" for r in recent_records])
            focus_text = specific_muscle if workout_focus == "Specified Muscle Group" else "Whole Body"
            
            prompt = f"""
            Act as an elite interactive personal trainer. Design a structured workout routine for a {workout_environment} session focusing on {focus_text}.
            Recent history:
            {history_text}
            
            Provide an explicit visual workout plan with clear instructions, sets, reps, and target rest periods.
            
            CRITICAL REQUIREMENT: At the very end of your response, you MUST provide a structured, easily parsable block containing the exact exercises you recommended so the app can auto-log them. Use this exact syntax:
            
            ===LOG_DATA_START===
            [
              {{"exercise": "Exercise Name 1", "sets": 3, "reps": 10, "equipment": "Bodyweight", "rpe": 7}}
            ]
            ===LOG_DATA_END===
            """
            
            response = model.generate_content(prompt)
            visual_plan, raw_payload = parse_ai_response(response.text)
            st.session_state['visual_plan'] = visual_plan
            st.session_state['raw_payload'] = raw_payload

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("📋 Active Workout Plan")
        if 'visual_plan' in st.session_state:
            with st.container():
                st.markdown(st.session_state['visual_plan'])
        else:
            st.info("Set your environment in the sidebar and click 'Generate New Routine' to begin your coached session.")

    with col2:
        st.subheader("⚡ Live Adjustments")
        if 'visual_plan' in st.session_state:
            with st.form("adjustment_form", clear_on_submit=True):
                user_feedback = st.text_input("Feedback to coach", placeholder="e.g., 'Wrists hurt, swap pushups'")
                submit_adjustment = st.form_submit_button("Modify Remaining Plan")
                
                if submit_adjustment and user_feedback:
                    with st.spinner("Pivoting routine..."):
                        adjust_prompt = f"""
                        You are the active trainer. Current plan: {st.session_state['visual_plan']}
                        User feedback: "{user_feedback}"
                        Modify the remaining workout instantly. Output the updated visual plan, followed by the newly updated JSON block:
                        ===LOG_DATA_START===
                        [ {{"exercise": "Updated", "sets": 3, "reps": 10, "equipment": "Floor", "rpe": 6}} ]
                        ===LOG_DATA_END===
                        """
                        response = model.generate_content(adjust_prompt)
                        visual_plan, raw_payload = parse_ai_response(response.text)
                        st.session_state['visual_plan'] = visual_plan
                        st.session_state['raw_payload'] = raw_payload
                        st.rerun()

            st.markdown("---")
            if st.button("✅ Finish & Auto-Log Workout", type="primary", use_container_width=True):
                if 'raw_payload' in st.session_state and st.session_state['raw_payload']:
                    try:
                        workout_list = json.loads(st.session_state['raw_payload'])
                        success_count = 0
                        with st.spinner("Recording to database..."):
                            for item in workout_list:
                                if save_to_airtable(item.get('exercise', 'Unknown'), item.get('sets', 3), item.get('reps', 10), item.get('equipment', 'None'), item.get('rpe', 7)):
                                    success_count += 1
                        if success_count == len(workout_list):
                            st.success(f"Session secured! {success_count} exercises logged.")
                            st.cache_data.clear() # Clear cache to update stats instantly
                            del st.session_state['visual_plan']
                            del st.session_state['raw_payload']
                        else:
                            st.warning("Partial logging success. Check Airtable.")
                    except Exception as e:
                        st.error("Error parsing the active workout tracking data.")

with tab2:
    st.subheader("📝 Manual Entry")
    spacer1, form_col, spacer2 = st.columns([1, 2, 1])
    with form_col:
        with st.form("manual_log_form", clear_on_submit=True):
            ex_name = st.text_input("Exercise Name", placeholder="e.g., Barbell Squat")
            c1, c2, c3 = st.columns(3)
            with c1: ex_sets = st.number_input("Sets", min_value=1, value=3)
            with c2: ex_reps = st.number_input("Reps", min_value=1, value=10)
            with c3: ex_rpe = st.number_input("RPE (1-10)", min_value=1, max_value=10, value=7)
            ex_equip = st.text_input("Equipment Used", placeholder="e.g., Barbell, Bodyweight")
            submit_manual = st.form_submit_button("Save Set to Database")
            
            if submit_manual and ex_name:
                if save_to_airtable(ex_name, ex_sets, ex_reps, ex_equip, ex_rpe):
                    st.success(f"Logged {ex_name}!")
                    st.cache_data.clear() # Update stats instantly
                else:
                    st.error("Failed to save.")

with tab3:
    st.subheader("📊 Workload Analytics")
    if records:
        chart_data = [{"Date": r.get('fields', {}).get('Date'), "Total Volume (Reps)": r.get('fields', {}).get('Sets', 0) * r.get('fields', {}).get('Reps', 0)} for r in records if r.get('fields', {}).get('Date')]
        if chart_data:
            df = pd.DataFrame(chart_data)
            df_grouped = df.groupby("Date").sum().reset_index().set_index("Date")
            st.bar_chart(df_grouped, color="#00ff88")
    else:
        st.info("Log a session to populate your analytics.")
