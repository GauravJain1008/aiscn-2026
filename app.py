import os
import json
import time
import ssl
import smtplib
import io
from datetime import datetime
from email.message import EmailMessage

import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials

# =========================
# PAGE CONFIGURATION
# =========================
st.set_page_config(
    page_title="AISCN'26 // Portal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================
# BACKEND LOGIC & HELPERS
# =========================
DB_FILE = "submission_registry.json"
HANDBOOK_PATH = "/home/parrot/AISCN_2026_Handbook.pdf"
SUBMISSION_LIMIT = 3

@st.cache_data
def load_handbook_bytes() -> bytes:
    """Loads the AISCN handbook PDF from disk for the download button."""
    if os.path.exists(HANDBOOK_PATH):
        with open(HANDBOOK_PATH, "rb") as f:
            return f.read()
    return b""

def is_blocked(email: str) -> bool:
    """Strict global limit: block once total submissions for an email reach SUBMISSION_LIMIT."""
    if not os.path.exists(DB_FILE):
        return False
    with open(DB_FILE, 'r') as f:
        db = json.load(f)
    return len(db.get(email.lower(), [])) >= SUBMISSION_LIMIT

def check_duplicate(email: str, sub_type: str) -> bool:
    """Checks local JSON registry to prevent duplicate submissions."""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            db = json.load(f)
        return sub_type in db.get(email.lower(), [])
    return False

def log_submission(email: str, sub_type: str):
    """Logs successful submission to local JSON registry."""
    db = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            db = json.load(f)
    email_key = email.lower()
    if email_key not in db:
        db[email_key] = []
    db[email_key].append(sub_type)
    with open(DB_FILE, 'w') as f:
        json.dump(db, f)

def upload_to_drive(file_bytes: bytes, file_name: str) -> str:
    """Uploads file to Google Drive via OAuth Refresh Token and returns View Link."""
    
    # 1. Load the new OAuth credentials from your secrets.toml
    creds_info = st.secrets["oauth"]
    creds = Credentials(
        token=None,
        refresh_token=creds_info["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_info["client_id"],
        client_secret=creds_info["client_secret"]
    )
    
    # 2. Initialize the Drive service acting as YOUR account
    service = build('drive', 'v3', credentials=creds)
    folder_id = st.secrets["drive"]["folder_id"]
    
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    
    # 3. Stream the file directly up to the folder
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='application/pdf', resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    
    return file.get('webViewLink')
def send_admin_email(name: str, email: str, sub_type: str, drive_link: str, timestamp: str):
    """Sends a notification email to the admin with the Drive link."""
    mail_user = st.secrets["smtp"]["mail_user"]
    mail_pass = st.secrets["smtp"]["mail_pass"]
    mail_to = st.secrets["smtp"]["mail_to"]
    
    msg = EmailMessage()
    msg["Subject"] = f"[AISCN'26 NEW UPLINK] {sub_type} - {name}"
    msg["From"] = mail_user
    msg["To"] = mail_to
    
    body = f"""
    New Project Submission Received!
    
    OPERATOR DETAILS:
    -----------------
    Name: {name}
    Email: {email}
    Submission Type: {sub_type}
    Timestamp: {timestamp}
    
    DRIVE LINK:
    -----------
    {drive_link}
    """
    msg.set_content(body)
    
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
        server.login(mail_user, mail_pass)
        server.send_message(msg)

def handle_submission(name: str, email: str, uploaded_file, sub_type: str):
    if not name or not email:
        st.error(">> ERR: OPERATOR IDENTITY (NAME & EMAIL) REQUIRED.")
        return
    if not uploaded_file:
        st.error(">> ERR: NO PAYLOAD DETECTED. ATTACH A PDF.")
        return
    if is_blocked(email):
        st.error(">> CRITICAL ERR: MAXIMUM SUBMISSION QUOTA REACHED. OPERATOR BLOCKED.")
        return
    if check_duplicate(email, sub_type):
        st.error(f">> ERR: UPLINK REJECTED. {sub_type} ALREADY SUBMITTED FOR {email}.")
        return

    try:
        with st.spinner(">> ESTABLISHING SECURE UPLINK..."):
            file_bytes = uploaded_file.read()
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_name = name.replace(" ", "_").replace("/", "")
            
            # File naming formatting
            drive_file_name = f"{sub_type}_{safe_name}_{email}_{timestamp}.pdf"
            
            # 1. Upload to Drive (calling your perfect function)
            drive_link = upload_to_drive(file_bytes, drive_file_name)
            
            # 2. Send Email Notification
            human_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            send_admin_email(name, email, sub_type, drive_link, human_time)
            
            # 3. Log Submission locally to block spam
            log_submission(email, sub_type)
            
        # === INJECT DRIVE LINK INTO SCREEN ON SUCCESS ===
        st.success(f">> UPLINK SUCCESSFUL. {sub_type} SECURED IN VAULT.")
        st.markdown(
            f'<div class="mono text-cyan text-xs" style="margin-top:0.5rem; padding:10px; background:rgba(0, 229, 255, 0.05); border:1px solid var(--neon-cyan); border-radius:4px;">'
            f'> FILE_ACCESS_URL: <a href="{drive_link}" target="_blank" style="color:var(--neon-cyan); text-decoration:underline; font-weight:bold;">{drive_link}</a>'
            f'</div>', 
            unsafe_allow_html=True
        )
        st.balloons()
        
    except Exception as e:
        st.error(f">> CRITICAL UPLINK FAILURE: {str(e)}")
# =========================
# INJECTED CSS
# =========================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

:root {
    --bg-main: #05080A;
    --bg-card: #0A0F14;
    --bg-card-hover: #0E151C;
    --neon-green: #00FF88;
    --neon-cyan: #00E5FF;
    --text-main: #E6EDF3;
    --text-muted: #7D8590;
    --border-color: #1A232C;
}

html, body, [class*="css"], .stApp {
    background-color: var(--bg-main) !important;
    color: var(--text-main) !important;
    font-family: 'Inter', sans-serif !important;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Fira Code', monospace !important;
}

header {visibility: hidden;}
footer {visibility: hidden;}
.block-container { max-width: 1400px; padding-top: 2rem; padding-bottom: 5rem; }

.mono { font-family: 'Fira Code', monospace; }
.text-neon { color: var(--neon-green); }
.text-cyan { color: var(--neon-cyan); }
.text-muted { color: var(--text-muted); }
.text-xs { font-size: 0.75rem; }
.text-sm { font-size: 0.875rem; }
.tracking-wide { letter-spacing: 0.05em; }
.tracking-widest { letter-spacing: 0.1em; }

.cyber-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    transition: all 0.3s ease;
}
.cyber-card:hover {
    background-color: var(--bg-card-hover);
    border-color: rgba(0, 255, 136, 0.3);
}
.cyber-card-top-accent {
    border-top: 2px solid var(--neon-green);
}

.pill {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 4px 12px; border-radius: 9999px;
    border: 1px solid rgba(0, 255, 136, 0.3);
    font-family: 'Fira Code', monospace; font-size: 11px;
    color: var(--neon-green); text-transform: uppercase;
}
.dot { width: 6px; height: 6px; border-radius: 50%; background: var(--neon-green); box-shadow: 0 0 8px var(--neon-green); }

.btn-primary {
    background: var(--neon-green); color: #000;
    padding: 10px 20px; border-radius: 6px; font-weight: 600;
    font-family: 'Fira Code', monospace; text-decoration: none; display: inline-block;
    border: none; cursor: pointer; font-size: 13px;
}
.btn-outline {
    background: transparent; color: var(--neon-cyan);
    padding: 10px 20px; border-radius: 6px; font-weight: 500;
    font-family: 'Fira Code', monospace; text-decoration: none; display: inline-block;
    border: 1px solid var(--neon-cyan); cursor: pointer; font-size: 13px;
}

.timeline-container { position: relative; padding-left: 3rem; margin-top: 2rem; }
.timeline-line {
    position: absolute; left: 11px; top: 0; bottom: 0; width: 2px;
    background: linear-gradient(to bottom, var(--neon-green) 0%, var(--border-color) 100%);
}
.timeline-item { position: relative; margin-bottom: 1.5rem; }
.timeline-dot {
    position: absolute; left: -3rem; top: 1.5rem; width: 10px; height: 10px;
    border-radius: 50%; background: var(--bg-main); border: 2px solid var(--neon-green);
}
.timeline-dot.active {
    background: var(--neon-cyan); border-color: var(--neon-cyan); box-shadow: 0 0 10px var(--neon-cyan);
}

/* Streamlit Native Input Styling Overrides */
div[data-testid="stFileUploader"] { background-color: transparent !important; }
div[data-testid="stFileUploader"] > section {
    background-color: var(--bg-card) !important;
    border: 1px dashed rgba(0, 255, 136, 0.4) !important;
    border-radius: 8px !important;
    padding: 2rem !important;
}
div[data-testid="stFileUploader"] > section:hover { border-color: var(--neon-green) !important; }
.stButton > button {
    width: 100%; background: transparent !important; border: 1px solid var(--neon-green) !important;
    color: var(--neon-green) !important; font-family: 'Fira Code', monospace !important; font-size: 13px !important;
}
.stButton > button:hover { background: var(--neon-green) !important; color: #000 !important; }

/* === DOWNLOAD HANDBOOK (mirrors .btn-outline) === */
div[data-testid="stDownloadButton"] > button {
    width: auto !important;
    background: transparent !important;
    color: var(--neon-cyan) !important;
    padding: 10px 20px !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-family: 'Fira Code', monospace !important;
    text-decoration: none !important;
    border: 1px solid var(--neon-cyan) !important;
    cursor: pointer !important;
    font-size: 13px !important;
    letter-spacing: normal !important;
    text-transform: none !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background: var(--neon-cyan) !important;
    color: #000 !important;
}

input {
    background-color: var(--bg-card) !important;
    color: var(--neon-green) !important;
    border: 1px solid var(--border-color) !important;
    font-family: 'Fira Code', monospace !important;
    border-radius: 4px !important;
}
input:focus {
    border-color: var(--neon-cyan) !important;
    box-shadow: 0 0 8px rgba(0, 229, 255, 0.2) !important;
}

/* === TERMINAL TYPEWRITER EFFECT === */
.tw-text {
    display: inline-block;
    overflow: hidden;
    white-space: nowrap;
    vertical-align: bottom;
    border-right: 8px solid var(--neon-cyan);
    animation: 
        typing-delete 12s steps(14, end) infinite, 
        blink-cursor 0.8s step-end infinite;
    height: 1.3em;
    line-height: 1.3em;
    margin-left: 8px;
}

.tw-text::before {
    content: "NETWORKING";
    animation: tw-words 12s infinite;
}

@keyframes tw-words {
    0%, 33.3% { content: "NETWORKING"; }
    33.4%, 66.6% { content: "CYBERSECURITY"; }
    66.7%, 100% { content: "AI SECURITY"; }
}

@keyframes typing-delete {
    0%, 5% { width: 0; }
    15%, 25% { width: 14ch; }
    30%, 33.3% { width: 0; }
    
    33.4%, 38% { width: 0; }
    48%, 58% { width: 14ch; }
    63%, 66.6% { width: 0; }
    
    66.7%, 71% { width: 0; }
    81%, 91% { width: 14ch; }
    96%, 100% { width: 0; }
}

@keyframes blink-cursor {
    0%, 100% { border-right-color: var(--neon-cyan); }
    50% { border-right-color: transparent; }
}

.hero-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: start; }
@media (max-width: 1000px) { .hero-grid { grid-template-columns: 1fr; gap: 2rem; } }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================
# 1. HERO SECTION
# =========================
st.markdown("""
<div style="margin-top: 4rem; margin-bottom: 6rem;">
<div class="hero-grid">
<div>
<div class="pill" style="margin-bottom: 2rem;">
<div class="dot"></div> SYSTEM // ONLINE · COHORT 2026
</div>
<h1 style="font-size: 4.5rem; margin: 0; line-height: 1; text-shadow: 0 0 20px rgba(0,255,136,0.2);">
AISCN'<span class="text-neon">26</span>
</h1>
<div class="mono text-cyan tracking-widest text-sm" style="margin-top: 1rem; margin-bottom: 1rem;">
AI SECURITY • CYBERSECURITY • NETWORKING
</div>

<div class="mono text-neon text-sm" style="margin-bottom: 2rem; display: flex; align-items: center; height: 1.5rem;">
> _ <span class="tw-text"></span>
</div>

<h3 style="font-family: 'Inter', sans-serif !important; font-weight: 400; margin-bottom: 1rem;">
“45-Day Immersive Internship Program”
</h3>
<div style="border-left: 2px solid var(--text-muted); padding-left: 1rem; margin-bottom: 2rem;">
<p class="text-muted" style="line-height: 1.6; max-width: 90%;">
Building the next generation of cybersecurity and AI security engineers through 
structured learning, practical labs, industry projects and mentor guidance — a 
curriculum that mirrors the actual threat landscape of 2026, from packet 
captures to prompt injections, from SOC consoles to agentic AI threat models.
</p>
</div>
<div style="display: flex; gap: 1rem; margin-top: 2rem;">
    <!-- Button 1 -->
    <a href="#submission-portal" target="_top" style="text-decoration: none;">
        <button style="background-color: #00ffaa; color: #000; border: none; padding: 10px 20px; font-weight: bold; cursor: pointer; font-family: inherit;">
            ENTER SUBMISSION PORTAL →
        </button>
    </a>

    <!-- Button 2 -->
    <a href="#workflow" target="_top" style="text-decoration: none;">
        <button style="background-color: transparent; color: #00ffaa; border: 1px solid #00ffaa; padding: 10px 20px; font-weight: bold; cursor: pointer; font-family: inherit;">
            VIEW WORKFLOW ↓
        </button>
    </a>
</div>
div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-family: 'Fira Code', monospace; font-size: 11px;">
<div><span class="text-neon">// CODE</span> <span class="text-muted">AISCN-2026-S1</span></div>
<div><span class="text-neon">// MODE</span> <span class="text-muted">Online / Hybrid · Live</span></div>
<div><span class="text-neon">// CORE LEAD</span> <span class="text-muted">Gaurav Jain · Ganesh Kanojiya</span></div>
<div><span class="text-neon">// FACULTY</span> <span class="text-muted">Ganesh · Kanishka · Anant · Sahil</span></div>
<div><span class="text-neon">// WINDOW</span> <span class="text-muted">14 Jun → 28 Jul 2026</span></div>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding-top: 2rem;">
<div class="cyber-card cyber-card-top-accent">
<div class="text-neon mono" style="font-size: 2.5rem; font-weight: bold; line-height: 1;">45</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">DAYS</div>
<div class="text-xs text-muted">Days of Training</div>
</div>
<div class="cyber-card cyber-card-top-accent">
<div class="text-neon mono" style="font-size: 2.5rem; font-weight: bold; line-height: 1;">10</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">LIVE CLASSES</div>
<div class="text-xs text-muted">90-120 min blocks</div>
</div>
<div class="cyber-card cyber-card-top-accent">
<div class="text-neon mono" style="font-size: 2.5rem; font-weight: bold; line-height: 1;">2</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">MINOR PROJECTS</div>
<div class="text-xs text-muted">MP1 · MP2</div>
</div>
<div class="cyber-card cyber-card-top-accent">
<div class="text-neon mono" style="font-size: 2.5rem; font-weight: bold; line-height: 1;">1</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">MAJOR PROJECT</div>
<div class="text-xs text-muted">Capstone · 40% weight</div>
</div>
<div class="cyber-card cyber-card-top-accent" style="grid-column: span 2;">
<div class="text-neon mono" style="font-size: 2.5rem; font-weight: bold; line-height: 1;">1</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">EXPERT TALK</div>
<div class="text-xs text-muted">Industry practitioner · 19 Jul 2026</div>
</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# === FUNCTIONAL DOWNLOAD HANDBOOK BUTTON (styled as .btn-outline) ===
dl_col, _ = st.columns([1, 4])
with dl_col:
    st.download_button(
        label="DOWNLOAD HANDBOOK ↓",
        data=load_handbook_bytes(),
        file_name="AISCN_Handbook_2026.pdf",
        mime="application/pdf",
        key="handbook_dl",
    )

# =========================
# 2. WORKFLOW SECTION
# =========================
st.markdown("""
<div style="text-align: center; margin-bottom: 3rem;">
<div class="mono text-neon text-xs tracking-widest mb-2">// PROGRAM PIPELINE</div>
<h2 style="font-size: 2.5rem; margin-top: 0.5rem;">AISCN-2026 Workflow</h2>
<p class="text-muted text-sm">Sequential pipeline stages from onboarding through certification. Each node is a checkpoint in<br>the live program, mirroring the handbook timeline.</p>
</div>
<div style="max-width: 900px; margin: 0 auto 6rem auto;">
<div class="timeline-container">
<div class="timeline-line"></div>
<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[01] // STAGE</span> <span>// PRE_WEEK</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Onboarding</h3>
<div class="text-muted text-sm">Discord induction, prerequisites & lab setup</div>
</div>
</div>
<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[02] // STAGE</span> <span>// 14 JUN → 15 JUL</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Live Classes</h3>
<div class="text-muted text-sm">10 live sessions · Sun + Wed · 90–120 min</div>
</div>
</div>
<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[03] // STAGE</span> <span>// CONTINUOUS</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Labs & Practice</h3>
<div class="text-muted text-sm">Bandit, Wireshark, TryHackMe, PortSwigger, Juice Shop, PicoGym</div>
</div>
</div>
<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[04] // STAGE</span> <span>// MENTORS</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Doubt Sessions</h3>
<div class="text-muted text-sm">Continuous mentor support — live + async on Discord</div>
</div>
</div>
<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[05] // STAGE</span> <span>// 21-28 JUN</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Minor Project 1</h3>
<div class="text-muted text-sm">Network & Web Security Observation Report · 15% weight</div>
</div>
</div>
<div class="timeline-item">
<div class="timeline-dot active"></div>
<div class="cyber-card" style="border-color: rgba(0, 229, 255, 0.4);">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[06] // STAGE</span> <span>// 05-12 JUL</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Minor Project 2</h3>
<div class="text-muted text-sm">Security Assessment & Pentesting Workflow Report · 20% weight</div>
</div>
</div>
<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[07] // STAGE</span> <span>// 15-25 JUL</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Major Project</h3>
<div class="text-muted text-sm">AI Security Risk Assessment & Secure AI Application Design · 40% weight</div>
</div>
</div>
<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-cyan">[08] // EVENT</span> <span>// 19 JUL 2026</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">Expert Talk</h3>
<div class="text-muted text-sm">"Cybersecurity & AI Security Careers in 2026 and Beyond"</div>
</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# =========================
# 3. ROADMAP & ASSESSMENT
# =========================
st.markdown("""
<div style="text-align: center; margin-bottom: 3rem;">
<div class="mono text-neon text-xs tracking-widest mb-2">// PORTFOLIO DELIVERABLES</div>
<h2 style="font-size: 2.5rem; margin-top: 0.5rem;">Project Roadmap</h2>
<p class="text-muted text-sm">Three progressive projects scale in difficulty and align with the curriculum — 2 minor reports<br>and 1 major capstone.</p>
</div>
<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin-bottom: 1.5rem;">
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 1rem;" class="mono text-xs">
<span style="border: 1px solid var(--neon-green); color: var(--neon-green); padding: 2px 6px; border-radius: 4px;">MINOR PROJECT 1</span>
<span class="text-cyan">15% WEIGHT</span>
</div>
<h4 style="margin: 0 0 1rem 0; font-size: 1.1rem; line-height: 1.4;">Network & Web Security<br>Observation Report</h4>
<p class="text-muted text-sm" style="line-height: 1.5; margin-bottom: 1.5rem;">Document how networking and web security concepts manifest in a real lab environment — Wireshark captures, Burp annotations, OWASP findings, personal reflection.</p>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
<div style="border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px;">ASSIGNED</div>
<div class="mono text-neon text-sm">21 Jun 2026</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px;">REVIEW</div>
<div class="mono text-neon text-sm">28 Jun 2026</div>
</div>
</div>
<div class="mono text-muted" style="font-size: 10px;">PDF · ≤ 10 pages · MP1_&#60;Name&#62;_AISCN2026.pdf</div>
</div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 1rem;" class="mono text-xs">
<span style="border: 1px solid var(--neon-green); color: var(--neon-green); padding: 2px 6px; border-radius: 4px;">MINOR PROJECT 2</span>
<span class="text-cyan">20% WEIGHT</span>
</div>
<h4 style="margin: 0 0 1rem 0; font-size: 1.1rem; line-height: 1.4;">Security Assessment &<br>Pentesting Workflow Report</h4>
<p class="text-muted text-sm" style="line-height: 1.5; margin-bottom: 1.5rem;">Simulate a junior pentester's workflow on a legal, intentionally vulnerable lab target (TryHackMe / HTB free / Juice Shop) and produce a structured, professional security assessment.</p>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
<div style="border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px;">ASSIGNED</div>
<div class="mono text-neon text-sm">05 Jul 2026</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px;">REVIEW</div>
<div class="mono text-neon text-sm">12 Jul 2026</div>
</div>
</div>
<div class="mono text-muted" style="font-size: 10px;">PDF · ≤ 15 pages · MP2_&#60;Name&#62;_AISCN2026.pdf</div>
</div>
<div class="cyber-card">
<div style="display: flex; justify-content: space-between; margin-bottom: 1rem;" class="mono text-xs">
<span style="border: 1px solid var(--neon-green); color: var(--neon-green); padding: 2px 6px; border-radius: 4px;">MAJOR PROJECT</span>
<span class="text-cyan">40% WEIGHT</span>
</div>
<h4 style="margin: 0 0 1rem 0; font-size: 1.1rem; line-height: 1.4;">AI Security Risk Assessment &<br>Secure AI Application Design</h4>
<p class="text-muted text-sm" style="line-height: 1.5; margin-bottom: 1.5rem;">Capstone deliverable — choose a hypothetical AI-powered application, conduct an AI security risk assessment (OWASP LLM Top 10 + MITRE ATLAS) and propose a secure design including agentic considerations.</p>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
<div style="border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px;">ASSIGNED</div>
<div class="mono text-neon text-sm">15 Jul 2026</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.5rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px;">PRESENTATION</div>
<div class="mono text-neon text-sm">26 Jul 2026</div>
</div>
</div>
<div class="mono text-muted" style="font-size: 10px;">PDF 20-25 pages + PPT 8-12 slides · 10 min + 5 min Q&A</div>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 6rem;">
<div class="cyber-card">
<div class="mono text-neon text-xs tracking-widest mb-2">// MARKING SCHEME</div>
<h3 style="margin-bottom: 1.5rem; font-size: 1.3rem;">Assessment Structure</h3>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Class Participation & Lab Engagement</span> <span class="mono text-neon">10%</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Minor Project 1</span> <span class="mono text-neon">15%</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Minor Project 2</span> <span class="mono text-neon">20%</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Major Project (Report + Presentation)</span> <span class="mono text-neon">40%</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Professionalism (docs, ethics, attendance)</span> <span class="mono text-neon">10%</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Expert Talk Reflection</span> <span class="mono text-neon">5%</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 1rem 0 0 0; font-weight: bold;" class="text-sm">
<span>TOTAL</span> <span class="mono text-neon">100%</span>
</div>
</div>
<div class="cyber-card">
<div class="mono text-neon text-xs tracking-widest mb-2">// COMPLETION CRITERIA</div>
<h3 style="margin-bottom: 1.5rem; font-size: 1.3rem;">Certificate Eligibility</h3>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Minimum Class Attendance</span> <span class="mono text-neon">≥ 70%</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Project Submissions</span> <span class="mono text-cyan">All 3</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Major Project Presentation</span> <span class="mono text-cyan">Mandatory</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Expert Talk</span> <span class="mono text-cyan">Mandatory</span>
</div>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color); margin-bottom: 1rem;" class="text-sm">
<span class="text-muted">Code of Conduct</span> <span class="mono text-cyan">Strict adherence</span>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
<div style="border: 1px solid var(--border-color); padding: 0.75rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">ISSUED</div>
<div class="mono text-neon text-sm">Internship Completion</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.75rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">> 70%</div>
<div class="mono text-cyan text-sm">Performance Letter</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.75rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">TOP 10%</div>
<div class="mono text-neon text-sm">Letter of Excellence</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.75rem; border-radius: 4px;">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">AWARD</div>
<div class="mono text-cyan text-sm">Best Project (per category)</div>
</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# =========================
# 4. SUBMISSION PORTAL
# =========================
st.markdown("""
<div style="display: flex; gap: 1rem; margin-top: 2rem;">
    <button style="background-color: #00ffaa; color: #000; border: none; padding: 10px 20px; font-weight: bold; cursor: pointer;">ENTER SUBMISSION PORTAL →</button>
    <button style="background-color: transparent; color: #00ffaa; border: 1px solid #00ffaa; padding: 10px 20px; font-weight: bold; cursor: pointer;">VIEW WORKFLOW ↓</button>
</div>

<!-- Niche wali line ka missing bracket fix kar diya hai -->
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; font-family: 'Fira Code', monospace; font-size: 11px;">
""", unsafe_allow_html=True)
# OPERATOR IDENTITY SECTION
st.markdown("""<div class="mono text-neon text-xs tracking-widest mb-2" style="max-width: 900px; margin: 0 auto;">// OPERATOR IDENTITY</div>""", unsafe_allow_html=True)
id_col1, id_col2 = st.columns(2)
with id_col1:
    user_name = st.text_input("FULL NAME", placeholder="Enter your registered name", key="user_name")
with id_col2:
    user_email = st.text_input("EMAIL ADDRESS", placeholder="Enter your registered email", key="user_email")

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown("""
<div class="mono text-xs text-muted" style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
<span>MP // 01</span> <span class="text-neon">● READY</span>
</div>
<h3 style="margin:0 0 0.2rem 0;">MINOR PROJECT — 1</h3>
<div class="text-xs text-muted" style="margin-bottom: 1.5rem;">PDF format only · Max 20 MB</div>
    """, unsafe_allow_html=True)
    
    mp1_file = st.file_uploader("Upload MP1", type=["pdf"], label_visibility="collapsed", key="mp1")
    if st.button("SUBMIT MP1", key="b1b", type="primary"):
        handle_submission(user_name, user_email, mp1_file, "MP1")

with col2:
    st.markdown("""
<div class="mono text-xs text-muted" style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
<span>MP // 02</span> <span class="text-neon">● READY</span>
</div>
<h3 style="margin:0 0 0.2rem 0;">MINOR PROJECT — 2</h3>
<div class="text-xs text-muted" style="margin-bottom: 1.5rem;">PDF format only · Max 20 MB</div>
    """, unsafe_allow_html=True)
    
    mp2_file = st.file_uploader("Upload MP2", type=["pdf"], label_visibility="collapsed", key="mp2")
    if st.button("SUBMIT MP2", key="b2b", type="primary"):
        handle_submission(user_name, user_email, mp2_file, "MP2")

with col3:
    st.markdown("""
<div class="mono text-xs text-muted" style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
<span>MJP // 01</span> <span class="text-neon">● READY</span>
</div>
<h3 style="margin:0 0 0.2rem 0;">MAJOR PROJECT</h3>
<div class="text-xs text-muted" style="margin-bottom: 1.5rem;">PDF format only · Max 20 MB</div>
    """, unsafe_allow_html=True)
    
    mjp_file = st.file_uploader("Upload MJP", type=["pdf"], label_visibility="collapsed", key="mjp")
    if st.button("SUBMIT MJP", key="b3b", type="primary"):
        handle_submission(user_name, user_email, mjp_file, "MJP")


# =========================
# 5. FOOTER PANELS
# =========================
st.markdown("<br><br>", unsafe_allow_html=True)
f_col1, f_col2 = st.columns(2, gap="large")

with f_col1:
    st.markdown("""
<div class="cyber-card">
<div class="mono text-neon text-xs tracking-widest mb-2">// OFFICE</div>
<h3 style="margin-bottom: 1rem;">Program Office</h3>
<div style="display: grid; grid-template-columns: 140px 1fr; gap: 0.5rem; font-size: 0.85rem;" class="mono text-muted">
<div>Program Director</div> <div class="text-neon">· AISCN-2026 Office</div>
<div>Core Lead</div> <div class="text-neon">· Gaurav Jain · Ganesh Kanojiya</div>
<div>Faculty Panel</div> <div>· Ganesh · Kanishka · Anant · Sahil</div>
<div>Doubt Sessions</div> <div>· Continuous (Live + Async)</div>
<div>Document Version</div> <div>· v1.0 · June 2026</div>
</div>
</div>
    """, unsafe_allow_html=True)

with f_col2:
    st.markdown("""
<div class="cyber-card">
<div class="mono text-neon text-xs tracking-widest mb-2">// MENTOR PANEL</div>
<h3 style="margin-bottom: 1rem;">Faculty & Mentors</h3>
<div style="display: grid; grid-template-columns: 140px 1fr; gap: 0.5rem; font-size: 0.85rem;" class="mono text-muted">
<div class="text-cyan">Gaurav Jain</div> <div>— Linux, Pentesting, AI Security</div>
<div class="text-cyan">Ganesh Kanojiya</div> <div>— Networking, SOC, AI Security</div>
<div class="text-cyan">Kanishka Jain</div> <div>— Windows Security, SOC Ops</div>
<div class="text-cyan">Anant Awasthi</div> <div>— Web Security, Cryptography</div>
<div class="text-cyan">Sahil Bharti</div> <div>— Web Application Security</div>
</div>
</div>
    """, unsafe_allow_html=True)

# Final Copyright & Warning Footer
st.markdown("""
<div style="text-align: center; margin-top: 4rem; padding-bottom: 2rem;">
<div class="mono text-neon text-sm tracking-widest" style="font-weight:bold;">AISCN'26 INTERNSHIP PROGRAM</div>
<div class="mono text-muted text-xs tracking-widest" style="margin-top:0.3rem;">CORE TEAM SUBMISSION SYSTEM</div>
<div class="mono text-muted text-xs" style="margin-top:1rem; opacity: 0.5;">
<span style="color:var(--neon-green);">●</span> secure-channel://aiscn26.submissions
</div>
<p class="text-muted text-xs" style="max-width: 600px; margin: 2rem auto 0 auto; line-height: 1.5; opacity: 0.6;">
Stay ethical. All hands-on activities are restricted to legally authorized environments — TryHackMe, OverTheWire, Hack The Box, 
OWASP Juice Shop, PicoGym. Application of any technique to unauthorized systems is strictly prohibited under the Information 
Technology Act, 2000 (India).
</p>
</div>
""", unsafe_allow_html=True)
