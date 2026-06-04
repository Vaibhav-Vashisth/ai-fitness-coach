import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime
import pandas as pd
import json

# Page Configuration
st.set_page_config(page_title="AI Physical Trainer", page_icon="🏋️‍♂️", layout="wide")

# Fetch Secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
AIRTABLE_TOKEN = st.secrets["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

# Database: Save Data
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

# Database: Read Data
def fetch_airtable_data():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Workout_Logs"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('records', [])
    return []

# Helper to separate visual plan from hidden data payload
def parse_ai_response(full_text):
    if "===LOG_DATA_START===" in full_text and "===LOG_DATA_END===" in full_text:
        parts = full_text.split("===LOG_DATA_START===")
        visual_plan = parts[0].strip()
        data_part = parts[1].split("===LOG_DATA_END===")[0].strip()
        return visual_plan, data_part
    return full_text, ""

# App UI Header
st.title("🏋️‍♂️ AI Personal Coach & Dashboard")
st.markdown("---")

tab1, tab2 = st.tabs(["🤖 Live Coaching Session", "📈 Progress Analytics"])

with tab1:
    # Sidebar: Initial Generation
    st.sidebar.header("🎯 Start a New Session")
    workout_environment = st.sidebar.selectbox("Where are you training today?", ["Gym (Full Equipment)", "Non-Gym (Bodyweight/Bands)", "Calisthenics (Bars/Rings/Floor)"])
    workout_focus = st.sidebar.selectbox("What is the focus?", ["Whole Body", "Specified Muscle Group"])
    
    specific_muscle = ""
    if workout_focus == "Specified Muscle Group":
        specific_muscle = st.sidebar.text_input("Which muscle group? (e.g., Chest, Legs)")
    
    if st.sidebar.button("🚀 Generate New Routine"):
        with st.spinner("Analyzing history and crafting your session..."):
            records = fetch_airtable_data()
            recent_records = records[-10:] if len(records) > 10 else records
            
            history_text = ""
            for rec in recent_records:
                fields = rec.get('fields', {})
                history_text += f"- {fields.get('Date')}: {fields.get('Exercise')} ({fields.get('Sets')}x{fields.get('Reps')}) | RPE: {fields.get('RPE')}/10\n"
            
            focus_text = specific_muscle if workout_focus == "Specified Muscle Group" else "Whole Body"
            
            prompt = f"""
            Act as an elite interactive personal trainer. Design a structured workout routine for a {workout_environment} session focusing on {focus_text}.
            Recent history:
            {history_text}
            
            Provide an explicit visual workout plan with clear instructions, sets, reps, and target rest periods.
            
            CRITICAL REQUIREMENT: At the very end of your response, you MUST provide a structured, easily parsable block containing the exact exercises you recommended so the app can auto-log them. Use this exact syntax:
            
            ===LOG_DATA_START===
            [
              {{"exercise": "Exercise Name 1", "sets": 3, "reps": 10, "equipment": "Bodyweight", "rpe": 7}},
              {{"exercise": "Exercise Name 2", "sets": 4, "reps": 12, "equipment": "Bars", "rpe": 8}}
            ]
            ===LOG_DATA_END===
            """
            
            response = model.generate_content(prompt)
            visual_plan, raw_payload = parse_ai_response(response.text)
            st.session_state['visual_plan'] = visual_plan
            st.session_state['raw_payload'] = raw_payload

    # Main Workspace Layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Active Workout Plan")
        if 'visual_plan' in st.session_state:
            st.markdown(st.session_state['visual_plan'])
        else:
            st.info("Set your environment in the sidebar and click 'Generate New Routine' to begin your coached session.")

    with col2:
        st.subheader("⚡ Live Coach Interactions")
        
        # Feature 1: Mid-Workout Course Correction
        if 'visual_plan' in st.session_state:
            st.markdown("**Need an adjustment?** Tell the coach if an exercise hurts, if it's too heavy, or if you can't finish the reps.")
            with st.form("adjustment_form", clear_on_submit=True):
                user_feedback = st.text_input("Feedback to coach (e.g., 'Can't do pullups, arms are shot')", placeholder="Tell the coach...")
                submit_adjustment = st.form_submit_button("Modify Remaining Plan")
                
                if submit_adjustment and user_feedback:
                    with st.spinner("Modifying your active routine..."):
                        adjust_prompt = f"""
                        You are the active personal trainer coaching this user right now. 
                        Here is the current workout plan you assigned:
                        {st.session_state['visual_plan']}
                        
                        The user just gave you this feedback mid-workout:
                        "{user_feedback}"
                        
                        Modify the remaining part of the workout instantly to accommodate this feedback. Keep the parts they may have already finished if reasonable, but pivot the rest immediately.
                        
                        CRITICAL REQUIREMENT: You must output the complete updated visual workout plan, followed by the newly updated JSON block matching the updated plan for auto-logging:
                        
                        ===LOG_DATA_START===
                        [
                          {{"exercise": "Updated Exercise", "sets": 3, "reps": 10, "equipment": "Floor", "rpe": 6}}
                        ]
                        ===LOG_DATA_END===
                        """
                        response = model.generate_content(adjust_prompt)
                        visual_plan, raw_payload = parse_ai_response(response.text)
                        st.session_state['visual_plan'] = visual_plan
                        st.session_state['raw_payload'] = raw_payload
                        st.rerun()

            st.markdown("---")
            
            # Feature 2: Automation Loop (Auto-Logging Entire Workout)
            st.markdown("**Finished training?** Save the entire active routine to your database with one click.")
            if st.button("✅ Finish & Auto-Log Workout", type="primary"):
                if 'raw_payload' in st.session_state and st.session_state['raw_payload']:
                    try:
                        workout_list = json.loads(st.session_state['raw_payload'])
                        success_count = 0
                        
                        with st.spinner("Recording all movements to Airtable..."):
                            for item in workout_list:
                                item_success = save_to_airtable(
                                    exercise=item.get('exercise', 'Unknown'),
                                    sets=item.get('sets', 3),
                                    reps=item.get('reps', 10),
                                    equipment=item.get('equipment', 'None'),
                                    rpe=item.get('rpe', 7)
                                )
                                if item_success:
                                    success_count += 1
                        
                        if success_count == len(workout_list):
                            st.success(f"Excellent session! All {success_count} exercises logged automatically.")
                            # Clear current session data safely
                            del st.session_state['visual_plan']
                            del st.session_state['raw_payload']
                        else:
                            st.warning(f"Logged {success_count} out of {len(workout_list)} exercises. Check Airtable setup.")
                    except Exception as e:
                        st.error("Error parsing the active workout tracking data. You can still log manually or try adjusting again.")
                else:
                    st.error("No active tracking payload found. Try re-generating the routine.")

with tab2:
    st.subheader("📊 Volume Over Time")
    records = fetch_airtable_data()
    if records:
        chart_data = []
        for rec in records:
            fields = rec.get('fields', {})
            date = fields.get('Date')
            sets = fields.get('Sets', 0)
            reps = fields.get('Reps', 0)
            if date and sets and reps:
                chart_data.append({"Date": date, "Total Volume (Reps)": sets * reps})
        
        if chart_data:
            df = pd.DataFrame(chart_data)
            df_grouped = df.groupby("Date").sum().reset_index()
            df_grouped.set_index("Date", inplace=True)
            st.bar_chart(df_grouped)
        else:
            st.info("Log a completed session to populate analytics.")
    else:
        st.info("No workout history found yet.")
