import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime
import pandas as pd

# Page Configuration
st.set_page_config(page_title="AI Physical Trainer", page_icon="🏋️‍♂️", layout="wide")

# Fetch Secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
AIRTABLE_TOKEN = st.secrets["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

# Database: Save Data (Now includes RPE)
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

# Database: Read Data (Now returns raw data for both AI and Charts)
def fetch_airtable_data():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Workout_Logs"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('records', [])
    return []

# App UI Header
st.title("🏋️‍♂️ AI Personal Coach & Dashboard")
st.markdown("---")

# Navigation Tabs (Separating Coach from Analytics)
tab1, tab2 = st.tabs(["🤖 AI Coach & Logger", "📈 Progress Analytics"])

with tab1:
    # Sidebar for AI Coaching Adjustments
    st.sidebar.header("🎯 Target & Environment")
    workout_environment = st.sidebar.selectbox("Where are you training today?", ["Gym (Full Equipment)", "Non-Gym (Bodyweight/Bands)", "Calisthenics (Bars/Rings/Floor)"])
    workout_focus = st.sidebar.selectbox("What is the focus?", ["Whole Body", "Specified Muscle Group"])
    
    specific_muscle = ""
    if workout_focus == "Specified Muscle Group":
        specific_muscle = st.sidebar.text_input("Which muscle group? (e.g., Chest, Legs, Arms)")
    
    st.sidebar.markdown("---")
    
    # Main Layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Today's Training Plan")
        if st.sidebar.button("Generate My Personalized Plan"):
            with st.spinner("Analyzing your past workouts and exertion levels..."):
                records = fetch_airtable_data()
                recent_records = records[-15:] if len(records) > 15 else records
                
                history_text = ""
                for rec in recent_records:
                    fields = rec.get('fields', {})
                    history_text += f"- {fields.get('Date', 'Date')}: {fields.get('Exercise', 'Ex')} ({fields.get('Sets', 0)}x{fields.get('Reps', 0)}) | RPE: {fields.get('RPE', 'Unknown')}/10\n"
                
                focus_text = specific_muscle if workout_focus == "Specified Muscle Group" else "Whole Body"
                
                prompt = f"""
                Act as an expert physical trainer. Design a workout plan for a user training in a {workout_environment} environment focusing on: {focus_text}.
                
                Here is their recent history including RPE (Rate of Perceived Exertion from 1-10, 10 being failure):
                {history_text}
                
                CRITICAL LOGIC: 
                - If they logged an RPE of 8-10 for a muscle group, they are fatigued. Focus on recovery or different muscles.
                - If they logged an RPE of 4-6, push them harder today with progressive overload.
                
                Provide clear instructions, sets, reps, and recommended rest times. Format beautifully with bullet points.
                """
                
                response = model.generate_content(prompt)
                st.session_state['current_plan'] = response.text
                
        if 'current_plan' in st.session_state:
            st.write(st.session_state['current_plan'])
        else:
            st.info("Click 'Generate My Personalized Plan' in the sidebar to get started!")

    with col2:
        st.subheader("📝 Log Your Set")
        with st.form("log_form", clear_on_submit=True):
            ex_name = st.text_input("Exercise Name")
            ex_sets = st.number_input("Sets", min_value=1, value=3)
            ex_reps = st.number_input("Reps", min_value=1, value=10)
            ex_rpe = st.slider("RPE (1=Easy, 10=Failure)", 1, 10, 7)
            ex_equip = st.text_input("Equipment (e.g., Bodyweight)")
            submit_btn = st.form_submit_button("Save to Database")
            
            if submit_btn and ex_name:
                if save_to_airtable(ex_name, ex_sets, ex_reps, ex_equip, ex_rpe):
                    st.success(f"Logged {ex_name} at RPE {ex_rpe}!")
                else:
                    st.error("Failed to save.")

with tab2:
    st.subheader("📊 Volume Over Time")
    st.markdown("This chart tracks your total workload (Sets × Reps) per day.")
    
    records = fetch_airtable_data()
    if records:
        # Process data for the chart
        chart_data = []
        for rec in records:
            fields = rec.get('fields', {})
            date = fields.get('Date')
            sets = fields.get('Sets', 0)
            reps = fields.get('Reps', 0)
            if date and sets and reps:
                volume = sets * reps
                chart_data.append({"Date": date, "Total Volume (Reps)": volume})
        
        if chart_data:
            df = pd.DataFrame(chart_data)
            # Group by date to sum volume if multiple exercises are done in one day
            df_grouped = df.groupby("Date").sum().reset_index()
            df_grouped.set_index("Date", inplace=True)
            
            st.bar_chart(df_grouped)
        else:
            st.info("Not enough data to graph yet.")
    else:
        st.info("No workout history found. Log some sets in the first tab to see your charts!")
