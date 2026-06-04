import streamlit as st
import google.generativeai as genai
import requests
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="AI Physical Trainer", page_icon="🏋️‍♂️", layout="wide")

# Fetch Secrets securely from Streamlit
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
AIRTABLE_TOKEN = st.secrets["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = st.secrets["AIRTABLE_BASE_ID"]

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

# Airtable: Save Data
def save_to_airtable(exercise, sets, reps, equipment):
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
                "Equipment Used": equipment
            }
        }]
    }
    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 200

# Airtable: Read Data (The New Memory Function)
def get_workout_history():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Workout_Logs"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        records = response.json().get('records', [])
        # Grab the last 15 exercises logged
        recent_records = records[-15:] if len(records) > 15 else records
        
        history_text = ""
        for rec in recent_records:
            fields = rec.get('fields', {})
            date = fields.get('Date', 'Unknown Date')
            ex = fields.get('Exercise', 'Unknown Exercise')
            s = fields.get('Sets', 0)
            r = fields.get('Reps', 0)
            equip = fields.get('Equipment Used', 'None')
            history_text += f"- {date}: {ex} ({s} sets of {r} reps) using {equip}\n"
            
        return history_text if history_text else "No past workout data available yet. This is the user's first logged workout."
    return "Error reading past data."

# App UI
st.title("🏋️‍♂️ AI Personal Coach & Dashboard")
st.markdown("---")

# Sidebar for AI Coaching Adjustments
st.sidebar.header("🎯 Target & Environment")
workout_environment = st.sidebar.selectbox("Where are you training today?", ["Gym (Full Equipment)", "Non-Gym (Bodyweight/Bands)"])
workout_focus = st.sidebar.selectbox("What is the focus?", ["Whole Body", "Specified Muscle Group"])

specific_muscle = ""
if workout_focus == "Specified Muscle Group":
    specific_muscle = st.sidebar.text_input("Which muscle group? (e.g., Chest, Legs, Arms)")

st.sidebar.markdown("---")
if st.sidebar.button("🤖 Generate My Personalized Plan"):
    with st.spinner("Analyzing your past workouts and designing today's routine..."):
        
        # 1. Fetch user history
        past_history = get_workout_history()
        
        # 2. Build the intelligent prompt
        focus_text = specific_muscle if workout_focus == "Specified Muscle Group" else "Whole Body"
        
        prompt = f"""
        Act as an expert physical trainer. Design a safe, effective workout plan for a user training in a {workout_environment} environment. 
        The focus today is: {focus_text}.
        
        Here is the user's recent workout history so you know their current level and what they have already done:
        {past_history}
        
        Based on this history, provide a structured routine for today. If they are training a muscle group they recently hit, suggest progressive overload (slightly more reps or weight). 
        Provide clear instructions, sets, and reps. Format it beautifully with bullet points.
        """
        
        # 3. Ask the AI
        response = model.generate_content(prompt)
        st.session_state['current_plan'] = response.text

# Main Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📋 Today's Training Plan")
    if 'current_plan' in st.session_state:
        st.write(st.session_state['current_plan'])
    else:
        st.info("Click 'Generate My Personalized Plan' in the sidebar to get started with your coach!")

with col2:
    st.subheader("📝 Log Your Completed Exercise")
    with st.form("log_form", clear_on_submit=True):
        ex_name = st.text_input("Exercise Name")
        ex_sets = st.number_input("Sets completed", min_value=1, value=3)
        ex_reps = st.number_input("Reps per set", min_value=1, value=10)
        ex_equip = st.text_input("Equipment Used (e.g., Dumbbells, None)")
        submit_btn = st.form_submit_button("Save to Dashboard")
        
        if submit_btn:
            if ex_name:
                success = save_to_airtable(ex_name, ex_sets, ex_reps, ex_equip)
                if success:
                    st.success(f"Successfully logged {ex_name}!")
                else:
                    st.error("Failed to save to database.")
            else:
                st.warning("Please enter an exercise name.")
