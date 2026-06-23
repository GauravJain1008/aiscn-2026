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
    page_title="AISCN'26 // root@aiscn:~#",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================
# BACKEND LOGIC & HELPERS
# =========================
DB_FILE = "submission_registry.json"
SUBMISSION_LIMIT = 3

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
    creds_info = st.secrets["oauth"]
    creds = Credentials(
        token=None,
        refresh_token=creds_info["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_info["client_id"],
        client_secret=creds_info["client_secret"]
    )
    service = build('drive', 'v3', credentials=creds)
    folder_id = st.secrets["drive"]["folder_id"]
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
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
            drive_file_name = f"{sub_type}_{safe_name}_{email}_{timestamp}.pdf"
            drive_link = upload_to_drive(file_bytes, drive_file_name)
            human_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            send_admin_email(name, email, sub_type, drive_link, human_time)
            log_submission(email, sub_type)
            key_map = {"MP1": "mp1_file", "MP2": "mp2_file", "MJP": "mjp_file"}
            st.session_state.pop(key_map.get(sub_type, ""), None)

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
# INJECTED CSS — HACKER TERMINAL THEME
# =========================
CUSTOM_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&family=Share+Tech+Mono&family=Major+Mono+Display&family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Fira+Code:wght@300;400;500;600;700&display=swap');

:root {
    --bg-main: #050708;
    --bg-deep: #08100C;
    --bg-card: #0A1410;
    --bg-card-hover: #0E1A14;
    --neon-green: #3FD37A;        /* softer, less acid */
    --neon-green-soft: #2BA85F;
    --neon-cyan: #4FC3E0;          /* less electric */
    --neon-amber: #E8A23A;
    --neon-red: #E84855;           /* desaturated crimson — not eyeball-burn red */
    --neon-red-deep: #B83545;
    --neon-magenta: #B85A8E;
    --text-main: #CFE6D4;          /* warm off-white instead of neon-tinged */
    --text-muted: #6B8478;
    --border-color: #1A2820;
    --border-glow: rgba(63, 211, 122, 0.22);
    --scanline: rgba(63, 211, 122, 0.025);
}

/* ====== GLOBAL BASE ====== */
html, body, .stApp {
    color: var(--text-main) !important;
    font-family: 'Share Tech Mono', 'JetBrains Mono', monospace !important;
    caret-color: var(--neon-green);
}

.stApp {
    background-color: #050708 !important;
    background-image:
        radial-gradient(ellipse at 18% 0%, rgba(63,211,122,0.05) 0%, transparent 55%),
        radial-gradient(ellipse at 82% 100%, rgba(232,72,85,0.045) 0%, transparent 55%),
        repeating-linear-gradient(90deg, rgba(63,211,122,0.018) 0px, rgba(63,211,122,0.018) 1px, transparent 1px, transparent 36px),
        repeating-linear-gradient(0deg, rgba(63,211,122,0.012) 0px, rgba(63,211,122,0.012) 1px, transparent 1px, transparent 36px),
        repeating-linear-gradient(0deg, rgba(63,211,122,0.018) 0px, rgba(63,211,122,0.018) 1px, transparent 1px, transparent 4px) !important;
    background-attachment: fixed !important;
}

/* ====== HEADINGS ====== */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Share Tech Mono', 'JetBrains Mono', monospace !important;
    color: var(--text-main) !important;
    text-shadow: 0 0 3px rgba(63,211,122,0.18);
    letter-spacing: 0.04em;
}

header {visibility: hidden;}
footer {visibility: hidden;}
#MainMenu {visibility: hidden;}

.block-container { max-width: 1400px; padding-top: 1rem; padding-bottom: 5rem; }

/* ====== UTILITY CLASSES ====== */
.mono { font-family: 'JetBrains Mono', 'Share Tech Mono', monospace; }
.term { font-family: 'VT323', 'Share Tech Mono', monospace; }
.text-neon { color: var(--neon-green); text-shadow: 0 0 2px rgba(63,211,122,0.25); }
.text-cyan { color: var(--neon-cyan); text-shadow: 0 0 2px rgba(79,195,224,0.22); }
.text-amber { color: var(--neon-amber); text-shadow: 0 0 2px rgba(232,162,58,0.25); }
.text-red { color: var(--neon-red); text-shadow: 0 0 2px rgba(232,72,85,0.25); }
.text-muted { color: var(--text-muted); }
.text-xs { font-size: 0.75rem; }
.text-sm { font-size: 0.875rem; }
.tracking-wide { letter-spacing: 0.08em; }
.tracking-widest { letter-spacing: 0.15em; }

/* ====== STATUS BAR ====== */
.status-bar {
    background: #050708;
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--neon-red);
    color: var(--neon-green);
    font-family: 'VT323', monospace;
    font-size: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 16px;
    letter-spacing: 0.05em;
    margin-bottom: 18px;
}
.status-bar .rec {
    color: var(--neon-red);
    font-weight: bold;
    letter-spacing: 0.2em;
}
.status-bar .rec::before {
    content: "● ";
    animation: rec-blink 1.4s steps(2) infinite;
}
@keyframes rec-blink {
    50% { opacity: 0.25; }
}
.status-bar .left, .status-bar .right {
    display: flex; gap: 18px; align-items: center;
}
.status-bar .blink { animation: status-blink 1s steps(2) infinite; }
@keyframes status-blink {
    50% { opacity: 0; }
}

/* ====== BOOT BANNER ====== */
.boot-banner {
    margin-top: 40px;
    padding: 14px 18px;
    background: rgba(10, 20, 16, 0.55);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--neon-green);
    border-radius: 0;
    font-family: 'VT323', monospace;
    color: var(--text-main);
    font-size: 16px;
    line-height: 1.55;
    position: relative;
    overflow: hidden;
}
.boot-line { display: block; }
.boot-line .ok   { color: var(--neon-green); }
.boot-line .warn { color: var(--neon-amber); }
.boot-line .err  { color: var(--neon-red); }

/* ====== ASCII BANNER ====== */
.ascii-banner {
    font-family: 'VT323', 'Share Tech Mono', monospace;
    color: var(--neon-green);
    white-space: pre;
    line-height: 1.0;
    font-size: 12px;
    margin: 1rem 0;
    overflow-x: auto;
    opacity: 0.85;
}

/* ====== CYBER TITLE — BOLD, CLEAN, ONE-LINE ====== */
.cyber-title {
    position: relative;
    display: inline-block;
    font-family: 'Share Tech Mono', 'JetBrains Mono', monospace !important;
    font-weight: 900;
    font-size: 7rem;
    line-height: 1;
    letter-spacing: 0.04em;
    white-space: nowrap;
    color: var(--text-main);
    text-shadow:
        0 0 1px rgba(255,255,255,0.6),
        0 0 4px var(--neon-green),
        0 0 12px rgba(63,211,122,0.35);
    animation: title-decrypt 1.2s ease-out 1;
    padding: 0 8px;
}
.cyber-title .pct {
    color: var(--neon-red);
    text-shadow: 0 0 3px rgba(232,72,85,0.6), 0 0 10px rgba(232,72,85,0.3);
}
@keyframes title-decrypt {
    0%   { filter: blur(6px) brightness(0.7); opacity: 0; letter-spacing: 0.35em; }
    100% { filter: blur(0) brightness(1); opacity: 1; letter-spacing: 0.04em; }
}

/* ====== DECRYPT TERMINAL LINE (above title) ====== */
.decrypt-line {
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    color: var(--neon-green);
    letter-spacing: 0.15em;
    margin-bottom: 0.6rem;
    display: flex; gap: 10px; align-items: center;
    animation: fadeup 0.9s ease-out both;
}
.decrypt-tag { color: var(--neon-cyan); text-shadow: 0 0 6px var(--neon-cyan); }
.decrypt-text {
    overflow: hidden; white-space: nowrap;
    border-right: 8px solid var(--neon-green);
    animation: typing-once 1.4s steps(28, end) 1 both, caret-blink 0.7s step-end infinite;
    max-width: 0; padding-right: 2px;
}
.decrypt-ok {
    color: #050708; background: var(--neon-green);
    padding: 1px 8px; font-weight: bold;
    opacity: 0; animation: pop-in 0.3s 1.4s ease-out forwards;
}
@keyframes typing-once {
    0%   { max-width: 0; }
    100% { max-width: 32ch; }
}
@keyframes caret-blink {
    0%, 100% { border-right-color: var(--neon-green); }
    50% { border-right-color: transparent; }
}
@keyframes pop-in {
    0%   { opacity: 0; transform: scale(0.5); }
    60%  { opacity: 1; transform: scale(1.15); }
    100% { opacity: 1; transform: scale(1); }
}
@keyframes fadeup {
    0% { opacity: 0; transform: translateY(8px); }
    100% { opacity: 1; transform: translateY(0); }
}

/* ====== BUTTON SHIMMER SWEEP ON HOVER ====== */
.stButton > button {
    position: relative;
    overflow: hidden;
}
.stButton > button::after {
    content: "";
    position: absolute;
    top: 0; left: -100%;
    width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent 0%, rgba(0,255,65,0.55) 50%, transparent 100%);
    transition: left 0.6s ease;
    pointer-events: none;
}
.stButton > button:hover::after { left: 130%; }

/* hero CTA buttons get the sweep too */
a[href="#submission-portal"], a[href="#workflow"] {
    position: relative;
    overflow: hidden;
}
a[href="#submission-portal"]::after, a[href="#workflow"]::after {
    content: "";
    position: absolute;
    top: 0; left: -100%;
    width: 60%; height: 100%;
    background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.35) 50%, transparent 100%);
    transition: left 0.55s ease;
    pointer-events: none;
}
a[href="#submission-portal"]:hover::after, a[href="#workflow"]:hover::after { left: 130%; }

/* ====== CYBER CARD: scan-line sweep on hover ====== */
.cyber-card { overflow: hidden; }
.cyber-card::after {
    content: "";
    position: absolute;
    top: -100%; left: 0;
    width: 100%; height: 100%;
    background: linear-gradient(180deg, transparent 0%, rgba(0,255,65,0.08) 50%, transparent 100%);
    transition: top 0.7s ease;
    pointer-events: none;
}
.cyber-card:hover::after { top: 100%; }

/* ====== INPUT FOCUS: expanding glow ring ====== */
input {
    transition: border-color 0.18s ease, box-shadow 0.25s ease, background-color 0.18s ease;
}
/* refined focus state (subtle red ring, no halo) */
input:focus {
    background-color: #08100D !important;
    box-shadow:
        0 0 0 1px var(--neon-red),
        inset 0 0 0 1px rgba(232,72,85,0.12) !important;
}

/* ====== SMOOTH SCROLL on every container Streamlit might scroll ====== */
html, body, .stApp, .main,
[data-testid="stAppViewContainer"],
[data-testid="stMainBlockContainer"],
section.main { scroll-behavior: smooth !important; }

/* anchor targets: a touch of offset + give them physical presence so browser scrolls to them */
#workflow, #submission-portal {
    display: block;
    height: 1px;
    scroll-margin-top: 90px;
    scroll-snap-margin-top: 90px;
}

/* ====== 3D PERSPECTIVE STAGE ====== */
.hero-grid, .timeline-container {
    perspective: 1400px;
    transform-style: preserve-3d;
}

/* ====== 3D CYBER CARDS — tilt + lift on hover ====== */
.cyber-card {
    transform-style: preserve-3d;
    transform: perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0);
    transition:
        transform 0.45s cubic-bezier(0.16, 1, 0.3, 1),
        border-color 0.3s ease,
        box-shadow 0.4s ease,
        background-color 0.3s ease;
    will-change: transform;
}
.cyber-card:hover {
    transform: perspective(1100px) rotateX(1.5deg) rotateY(-1.5deg) translateY(-2px);
    border-color: rgba(63,211,122,0.45);
    box-shadow:
        0 12px 22px -10px rgba(0,0,0,0.7),
        0 0 12px rgba(63,211,122,0.18),
        inset 0 0 14px rgba(63,211,122,0.03);
}
.cyber-card:nth-child(2n):hover {
    transform: perspective(1100px) rotateX(1.5deg) rotateY(1.5deg) translateY(-2px);
}

.cyber-card .corner {
    transition: transform 0.45s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease;
}
.cyber-card:hover .corner { transform: translateZ(8px); border-color: var(--neon-red); }

/* stat numbers float toward viewer */
.cyber-card:hover .text-neon.mono {
    text-shadow: 0 0 14px var(--neon-green), 0 0 28px rgba(0,255,65,0.55);
}

/* ====== 3D BUTTONS — physical press ====== */
.stButton > button {
    transform-style: preserve-3d;
    transform: translateY(0) translateZ(0);
    transition:
        transform 0.18s cubic-bezier(0.16, 1, 0.3, 1),
        background-color 0.18s ease,
        color 0.18s ease,
        box-shadow 0.25s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    border-color: var(--neon-red) !important;
    color: var(--neon-red) !important;
    box-shadow:
        0 6px 12px -4px rgba(0,0,0,0.5),
        0 0 10px rgba(232,72,85,0.25) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
    transition-duration: 0.08s !important;
}

/* ====== HERO CTA buttons — beefier 3D ====== */
a[href="#submission-portal"], a[href="#workflow"] {
    transform-style: preserve-3d;
    transform: translateY(0) translateZ(0);
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease, background-color 0.2s ease, color 0.2s ease !important;
}
a[href="#submission-portal"]:hover, a[href="#workflow"]:hover {
    transform: translateY(-2px) !important;
    box-shadow:
        0 8px 14px -6px rgba(0,0,0,0.55),
        0 0 12px rgba(63,211,122,0.25) !important;
}
a[href="#submission-portal"]:active, a[href="#workflow"]:active {
    transform: translateY(0) !important;
}

/* ====== INPUTS — subtle depth ====== */
input {
    transform: translateZ(0);
    box-shadow:
        0 0 8px rgba(0,255,65,0.18) inset,
        0 2px 0 rgba(0,255,65,0.12) !important;
}

/* ====== TITLE — soft 3D lift on hover ====== */
.cyber-title {
    transform: translateZ(0) rotateX(0);
    transition: transform 0.6s cubic-bezier(0.16, 1, 0.3, 1), text-shadow 0.6s ease;
}
.cyber-title:hover {
    transform: translateZ(20px) rotateX(-4deg);
}

/* (stat-card floating removed — felt too restless. cards still tilt on hover.) */

/* ====== TIMELINE DOTS pop forward ====== */
.timeline-dot {
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.timeline-item:hover .timeline-dot {
    transform: scale(1.25);
    background: var(--neon-red);
    border-color: var(--neon-red);
}

/* ====== TERM-WINDOW subtle 3D ====== */
.term-window {
    transform: perspective(1200px) rotateX(0deg) translateZ(0);
    transition: transform 0.45s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.4s ease;
}
.term-window:hover {
    transform: perspective(1400px) rotateX(1deg);
    box-shadow: 0 14px 28px -14px rgba(0,0,0,0.7);
}

/* ====== CHIP press depth ====== */
.chip { transition: transform 0.18s ease, border-color 0.2s ease, color 0.2s ease; }
.chip:hover { transform: translateY(-1px); border-color: var(--neon-red); color: var(--neon-red); }

/* ====== ACCESS GRANTED gentle tilt ====== */
.access-flash {
    transform: perspective(600px) rotateX(0);
    transition: transform 0.35s ease;
}
.access-flash:hover { transform: perspective(600px) rotateX(-4deg) scale(1.02); }

/* ====== LINK HOVER GROW UNDERLINE ====== */
a:not([href^="#"]) {
    position: relative;
    transition: color 0.2s ease, text-shadow 0.2s ease;
}
a:not([href^="#"])::after {
    content: "";
    position: absolute;
    left: 0; bottom: -2px;
    width: 0; height: 1px;
    background: var(--neon-cyan);
    box-shadow: 0 0 6px var(--neon-cyan);
    transition: width 0.3s ease;
}
a:not([href^="#"]):hover::after { width: 100%; }

/* ====== TICKER FASTER + PULSE ====== */
.ticker-wrap { border-color: var(--neon-green); box-shadow: inset 0 0 16px rgba(0,255,65,0.08); }

/* ====== ACCESS GRANTED FLASH on hero load ====== */
.access-flash {
    display: inline-block;
    padding: 3px 10px;
    color: #061010;
    background: var(--neon-green);
    border-left: 3px solid var(--neon-red);
    font-family: 'VT323', monospace;
    font-size: 14px;
    letter-spacing: 0.2em;
    margin-bottom: 14px;
    box-shadow: 0 0 6px rgba(63,211,122,0.35);
}

/* ====== BOOT BANNER lines stagger in ====== */
.boot-banner .boot-line {
    opacity: 0;
    animation: boot-in 0.28s ease-out forwards;
}
.boot-banner .boot-line:nth-child(1) { animation-delay: 0.05s; }
.boot-banner .boot-line:nth-child(2) { animation-delay: 0.25s; }
.boot-banner .boot-line:nth-child(3) { animation-delay: 0.45s; }
.boot-banner .boot-line:nth-child(4) { animation-delay: 0.65s; }
.boot-banner .boot-line:nth-child(5) { animation-delay: 0.85s; }
.boot-banner .boot-line:nth-child(6) { animation-delay: 1.05s; }
.boot-banner .boot-line:nth-child(7) { animation-delay: 1.30s; }
@keyframes boot-in {
    0%   { opacity: 0; transform: translateX(-6px); }
    100% { opacity: 1; transform: translateX(0); }
}

/* ====== FILE UPLOADER smooth hover ====== */
div[data-testid="stFileUploader"] > section {
    transition: border-color 0.2s ease, box-shadow 0.3s ease, transform 0.2s ease;
}
div[data-testid="stFileUploader"] > section:hover {
    transform: translateY(-1px);
}

/* (pill pulse removed for calmer feel) */

/* ====== CYBER CARD ====== */
.cyber-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 0;
    padding: 1.5rem;
    transition: all 0.25s ease;
    position: relative;
    clip-path: polygon(
        0 12px, 12px 0,
        calc(100% - 12px) 0, 100% 12px,
        100% calc(100% - 12px), calc(100% - 12px) 100%,
        12px 100%, 0 calc(100% - 12px)
    );
}
.cyber-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--neon-green) 30%, var(--neon-red) 70%, transparent);
    opacity: 0.5;
}
.cyber-card:hover {
    background-color: var(--bg-card-hover);
    border-color: var(--neon-green);
    box-shadow:
        0 0 18px rgba(0,255,65,0.25),
        inset 0 0 24px rgba(0,255,65,0.04);
    transform: translateY(-2px);
}
.cyber-card-top-accent { border-top: 2px solid var(--neon-green); }
.cyber-card-top-accent:nth-child(2n) { border-top-color: var(--neon-red); }

/* corner brackets */
.cyber-card .corner {
    position: absolute; width: 14px; height: 14px;
    border: 1px solid var(--neon-green);
}
.cyber-card .corner.tl { top: 4px; left: 4px; border-right: 0; border-bottom: 0; }
.cyber-card .corner.tr { top: 4px; right: 4px; border-left: 0; border-bottom: 0; }
.cyber-card .corner.bl { bottom: 4px; left: 4px; border-right: 0; border-top: 0; }
.cyber-card .corner.br { bottom: 4px; right: 4px; border-left: 0; border-top: 0; }

/* ====== PILL ====== */
.pill {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 4px 12px; border-radius: 0;
    border: 1px solid var(--border-color);
    border-left: 2px solid var(--neon-red);
    font-family: 'Share Tech Mono', monospace; font-size: 11px;
    color: var(--neon-green); text-transform: uppercase;
    background: rgba(10,20,16,0.6);
}
.dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--neon-green);
    box-shadow: 0 0 4px rgba(63,211,122,0.55);
    animation: pulse-dot 2.2s ease-in-out infinite;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.55; }
}

/* ====== ANIMATED HERO LINK BUTTONS ====== */
a[href="#submission-portal"], a[href="#workflow"] {
    background: transparent !important;
    color: var(--neon-green) !important;
    border: 1px solid var(--neon-green) !important;
    padding: 12px 22px !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-weight: bold !important;
    text-decoration: none !important;
    border-radius: 0 !important;
    position: relative;
    overflow: hidden;
    letter-spacing: 0.1em !important;
    text-transform: uppercase;
    transition: all 0.2s ease;
}
a[href="#submission-portal"] {
    background: var(--neon-green) !important;
    color: #050708 !important;
    border-color: var(--neon-green) !important;
}
a[href="#submission-portal"]:hover {
    background: var(--neon-red) !important;
    color: #FFFFFF !important;
    border-color: var(--neon-red) !important;
}
a[href="#workflow"]:hover {
    color: var(--neon-red) !important;
    border-color: var(--neon-red) !important;
}

/* ====== TIMELINE ====== */
.timeline-container { position: relative; padding-left: 3rem; margin-top: 2rem; }
.timeline-line {
    position: absolute; left: 11px; top: 0; bottom: 0; width: 1px;
    background: linear-gradient(to bottom,
        var(--neon-green) 0%,
        var(--neon-red) 60%,
        var(--border-color) 100%);
}
.timeline-item { position: relative; margin-bottom: 1.5rem; }
.timeline-dot {
    position: absolute; left: -3rem; top: 1.5rem; width: 12px; height: 12px;
    background: var(--bg-main); border: 2px solid var(--neon-green);
    border-radius: 50%;
    transition: all 0.25s ease;
}
.timeline-dot.active {
    background: var(--neon-red); border-color: var(--neon-red);
    animation: pulse-dot 1.6s ease-in-out infinite;
}

/* ====== STREAMLIT WIDGETS OVERRIDE ====== */
div[data-testid="stFileUploader"] {
    background-color: transparent !important;
}
div[data-testid="stFileUploader"] > section {
    background-color: var(--bg-card) !important;
    border: 1px dashed rgba(63,211,122,0.45) !important;
    border-radius: 0 !important;
    padding: 2rem !important;
    color: var(--neon-green) !important;
    transition: all 0.2s ease;
}
div[data-testid="stFileUploader"] > section:hover {
    border-color: var(--neon-red) !important;
    background-color: var(--bg-card-hover) !important;
}
div[data-testid="stFileUploader"] section button {
    background: transparent !important;
    border: 1px solid var(--neon-green) !important;
    color: var(--neon-green) !important;
    font-family: 'Share Tech Mono', monospace !important;
    border-radius: 0 !important;
}

div[data-testid="stFileUploader"] small,
div[data-testid="stFileUploader"] span,
div[data-testid="stFileUploader"] p {
    color: var(--text-muted) !important;
}

/* Submit Buttons */
.stButton > button {
    width: 100%;
    background: transparent !important;
    border: 1px solid var(--neon-green) !important;
    color: var(--neon-green) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 14px !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
    border-radius: 0 !important;
    padding: 12px 0 !important;
    box-shadow: none;
    transition: all 0.2s ease;
    position: relative;
}
.stButton > button::before { content: "> "; }

/* Text inputs */
div[data-testid="stTextInput"] label {
    color: var(--neon-green) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 12px !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
}
div[data-testid="stTextInput"] label::before { content: "> "; color: var(--neon-cyan); }

input {
    background-color: #060A08 !important;
    color: var(--neon-green) !important;
    border: 1px solid var(--border-color) !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 0 !important;
    caret-color: var(--neon-green) !important;
    box-shadow: none !important;
}
input::placeholder {
    color: var(--text-muted) !important;
    font-style: italic;
}
input:focus {
    border-color: var(--neon-red) !important;
    box-shadow: inset 0 0 0 1px rgba(232,72,85,0.18) !important;
    outline: none !important;
}

/* Streamlit alerts -> terminal */
div[data-testid="stAlert"] {
    border-radius: 0 !important;
    font-family: 'Share Tech Mono', monospace !important;
    border-left: 4px solid var(--neon-green) !important;
}
div[data-baseweb="notification"] { border-radius: 0 !important; }

/* Spinner restyle */
.stSpinner > div > div {
    border-color: var(--neon-green) transparent var(--neon-green) transparent !important;
}

/* ====== TERMINAL TYPEWRITER EFFECT ====== */
.tw-text {
    display: inline-block;
    overflow: hidden;
    white-space: nowrap;
    vertical-align: bottom;
    border-right: 10px solid var(--neon-cyan);
    animation:
        typing-delete 12s steps(14, end) infinite,
        blink-cursor 0.7s step-end infinite;
    height: 1.3em;
    line-height: 1.3em;
    margin-left: 8px;
    color: var(--neon-cyan);
    text-shadow: 0 0 8px var(--neon-cyan);
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

/* ====== SECTION DIVIDER ====== */
.divider-ascii {
    text-align: center;
    color: var(--text-muted);
    font-family: 'VT323', monospace;
    font-size: 17px;
    letter-spacing: 0.1em;
    margin: 3rem 0 2rem 0;
    opacity: 0.7;
}
.divider-ascii::first-letter { color: var(--neon-red); }

/* ====== HERO GRID ====== */
.hero-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: start; }
@media (max-width: 1000px) { .hero-grid { grid-template-columns: 1fr; gap: 2rem; } }

/* ====== TERMINAL WINDOW WRAPPER ====== */
.term-window {
    background: rgba(10, 18, 14, 0.75);
    border: 1px solid var(--border-color);
    border-top: 1px solid var(--neon-green);
    border-radius: 0;
    padding: 0;
    margin: 1rem 0;
    backdrop-filter: blur(2px);
}
.term-header {
    background: linear-gradient(180deg, #0E1A14 0%, #050708 100%);
    border-bottom: 1px solid var(--border-color);
    padding: 6px 12px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 10px;
}
.term-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.term-dot.red { background: var(--neon-red); }
.term-dot.amb { background: var(--neon-amber); }
.term-dot.grn { background: var(--neon-green); }
.term-body { padding: 14px 18px; font-family: 'Share Tech Mono', monospace; }

/* ====== TICKER ====== */
.ticker-wrap {
    overflow: hidden;
    border-top: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    background: rgba(0,0,0,0.5);
    margin: 1rem 0 2rem 0;
    height: 28px;
    display: flex;
    align-items: center;
}
.ticker {
    display: inline-block;
    white-space: nowrap;
    animation: ticker-scroll 55s linear infinite;
    font-family: 'Share Tech Mono', monospace;
    color: var(--text-main);
    font-size: 13px;
    letter-spacing: 0.1em;
}
.ticker span { padding: 0 30px; }
.ticker span.hot { color: var(--neon-red); }
.ticker .sep { color: var(--neon-red); opacity: 0.6; }
@keyframes ticker-scroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}

/* ====== SECTION LABEL ====== */
.section-label {
    color: var(--neon-green);
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.25em;
}
.section-label::before { content: "▌ "; color: var(--neon-red); }
.section-h2 {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 2.6rem !important;
    color: var(--text-main) !important;
    letter-spacing: 0.05em;
    margin: 0.4rem 0 0.8rem 0;
}
.section-h2 .accent {
    color: var(--neon-red);
}

/* ====== LINKS ====== */
a { color: var(--neon-cyan); text-decoration: none; }
a:hover { color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green); }

/* Hide Streamlit's deploy floater */
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }

/* ====== UPLOADED FILE NAME color fix ====== */
div[data-testid="stFileUploader"] li {
    background: rgba(0,255,65,0.06) !important;
    color: var(--neon-green) !important;
    border: 1px solid var(--neon-green) !important;
    border-radius: 0 !important;
    margin-top: 8px !important;
}

/* file uploader button text */
div[data-testid="stFileUploader"] section button:hover {
    background: var(--neon-green) !important;
    color: #000 !important;
}

/* Number/percentage chips inside cards */
.chip {
    display: inline-block;
    padding: 2px 8px;
    border: 1px solid var(--neon-green);
    color: var(--neon-green);
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.chip.cyan {
    border-color: var(--neon-red);
    color: var(--neon-red);
}

</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Status bar — rendered with server-side UTC clock (refreshes on each Streamlit rerun)
_utc_now = datetime.utcnow().strftime("%H:%M:%S")
st.markdown(f"""
<div class="status-bar">
  <div class="left">
    <span class="rec">REC</span>
    <span>root@aiscn26:~#</span>
    <span>UPLINK::SECURE</span>
    <span>TLS/1.3</span>
  </div>
  <div class="right">
    <span>{_utc_now} UTC</span>
    <span class="blink">▮</span>
    <span>COHORT::2026</span>
  </div>
</div>
""", unsafe_allow_html=True)

# =========================
# BOOT BANNER
# =========================
st.markdown("""
<div class="boot-banner" style="margin-top:50px;">
<span class="boot-line">[<span class="ok">  OK  </span>] Initializing AISCN'26 secure submission node ...</span>
<span class="boot-line">[<span class="ok">  OK  </span>] Mounting /vault/projects on encrypted overlay ...</span>
<span class="boot-line">[<span class="ok">  OK  </span>] Loading OWASP LLM Top-10 / MITRE ATLAS modules ...</span>
<span class="boot-line">[<span class="ok">  OK  </span>] TLS-1.3 channel established :: cipher=AES_256_GCM</span>
<span class="boot-line">[<span class="ok">  OK  </span>] Operator session granted :: role=intern :: tier=2026</span>
<span class="boot-line">[<span class="err"> FAIL </span>] anonymous_recon_probe :: connection refused by firewall</span>
<span class="boot-line">[<span class="warn">  ** </span>] WARNING: All activity logged. Unauthorized recon prohibited.</span>
<span class="boot-line" style="color:var(--neon-cyan);">root@aiscn:~# launch --portal cohort-2026 --ui hacker_mode<span style="animation: blink-cursor 0.8s step-end infinite;">_</span></span>
</div>
""", unsafe_allow_html=True)

# =========================
# ASCII BANNER
# =========================
st.markdown("""
<pre class="ascii-banner">
   █████╗ ██╗███████╗ ██████╗███╗   ██╗   ██████╗  ██████╗
  ██╔══██╗██║██╔════╝██╔════╝████╗  ██║   ╚════██╗██╔════╝
  ███████║██║███████╗██║     ██╔██╗ ██║    █████╔╝███████╗
  ██╔══██║██║╚════██║██║     ██║╚██╗██║   ██╔═══╝ ██╔═══██╗
  ██║  ██║██║███████║╚██████╗██║ ╚████║   ███████╗╚██████╔╝
  ╚═╝  ╚═╝╚═╝╚══════╝ ╚═════╝╚═╝  ╚═══╝   ╚══════╝ ╚═════╝
  ────────────────────────────────────────────────────────
  &gt;&gt; AI · SECURITY · CYBER · NETWORKING — COHORT 2026 &lt;&lt;
</pre>
""", unsafe_allow_html=True)

# =========================
# TICKER
# =========================
st.markdown("""
<div class="ticker-wrap">
<div class="ticker">
<span>● UPLINK STATUS: ONLINE</span><span class="sep">::</span>
<span>● MP1 WINDOW: 21-28 JUN 2026</span><span class="sep">::</span>
<span>● MP2 WINDOW: 05-12 JUL 2026</span><span class="sep">::</span>
<span>● MAJOR PROJECT: 15-25 JUL 2026</span><span class="sep">::</span>
<span>● EXPERT TALK: 19 JUL 2026</span><span class="sep">::</span>
<span>● ETHICAL CONDUCT ENFORCED — IT ACT 2000 (IN)</span><span class="sep">::</span>
<span>● UPLINK STATUS: ONLINE</span><span class="sep">::</span>
<span>● MP1 WINDOW: 21-28 JUN 2026</span><span class="sep">::</span>
<span>● MP2 WINDOW: 05-12 JUL 2026</span><span class="sep">::</span>
<span>● MAJOR PROJECT: 15-25 JUL 2026</span><span class="sep">::</span>
<span>● EXPERT TALK: 19 JUL 2026</span><span class="sep">::</span>
<span>● ETHICAL CONDUCT ENFORCED — IT ACT 2000 (IN)</span><span class="sep">::</span>
</div>
</div>
""", unsafe_allow_html=True)

# =========================
# 1. HERO SECTION
# =========================
st.markdown("""
<div style="margin-top: 1rem; margin-bottom: 5rem;">
<div class="hero-grid">
<div>
<div class="pill" style="margin-bottom: 1.4rem;">
<div class="dot"></div> SYSTEM // ONLINE · COHORT 2026 · UPLINK_OK
</div>

<div class="access-flash">&gt;&gt; ACCESS GRANTED &lt;&lt;</div>

<div class="decrypt-line">
  <span class="decrypt-tag">[DECRYPT]</span>
  <span class="decrypt-text">cohort_2026.dat &rarr; AISCN_26</span>
  <span class="decrypt-ok">[OK]</span>
</div>

<h1 class="cyber-title" style="margin:0;">AISCN<span class="pct">'26</span></h1>

<div class="mono text-cyan tracking-widest text-sm" style="margin-top: 1rem; margin-bottom: 1rem;">
[ AI_SECURITY ] :: [ CYBERSECURITY ] :: [ NETWORKING ]
</div>

<div class="mono text-neon text-sm" style="margin-bottom: 2rem; display: flex; align-items: center; height: 1.5rem;">
&gt; ./scan --target <span class="tw-text"></span>
</div>

<h3 style="font-family: 'Share Tech Mono', monospace !important; font-weight: 400; margin-bottom: 1rem; color:var(--text-main);">
&gt;_ "45-Day Immersive Internship Program"
</h3>
<div style="border-left: 2px solid var(--neon-green); padding-left: 1rem; margin-bottom: 2rem; background: rgba(0,255,65,0.02);">
<p class="text-muted" style="line-height: 1.7; max-width: 92%; font-family:'JetBrains Mono', monospace; font-size: 0.92rem;">
Building the next generation of cybersecurity and AI security engineers through
structured learning, practical labs, industry projects and mentor guidance — a
curriculum that mirrors the actual threat landscape of 2026, from packet
captures to prompt injections, from SOC consoles to agentic AI threat models.
</p>
</div>
<div style="display: flex; gap: 1rem; margin-top: 2rem; margin-bottom: 2rem; flex-wrap: wrap;">
    <a href="#submission-portal"
       onclick="var t=document.getElementById('submission-portal');if(t){t.scrollIntoView({behavior:'smooth',block:'start'});history.replaceState(null,'','#submission-portal');return false;}">[ENTER SUBMISSION PORTAL] &rarr;</a>
    <a href="#workflow"
       onclick="var t=document.getElementById('workflow');if(t){t.scrollIntoView({behavior:'smooth',block:'start'});history.replaceState(null,'','#workflow');return false;}">[VIEW WORKFLOW] &darr;</a>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem 1rem; font-family: 'Share Tech Mono', monospace; font-size: 12px; margin-top: 1.5rem;">
<div><span class="text-neon">// CODE</span> <span class="text-muted">AISCN-2026-S1</span></div>
<div><span class="text-neon">// MODE</span> <span class="text-muted">Online / Hybrid · Live</span></div>
<div><span class="text-neon">// CORE LEAD</span> <span class="text-muted">Gaurav Jain · Ganesh Kanojiya</span></div>
<div><span class="text-neon">// FACULTY</span> <span class="text-muted">Ganesh · Kanishka · Anant · Sahil</span></div>
<div><span class="text-neon">// WINDOW</span> <span class="text-muted">14 Jun → 28 Jul 2026</span></div>
<div><span class="text-neon">// PROTOCOL</span> <span class="text-muted">TLS-1.3 / AES-256-GCM</span></div>
</div>
</div>

<div>
<div class="term-window">
<div class="term-header">
<span class="term-dot red"></span>
<span class="term-dot amb"></span>
<span class="term-dot grn"></span>
<span style="margin-left:6px;">root@aiscn26:~/cohort2026 — bash — 80x24</span>
</div>
<div class="term-body" style="font-size: 13px; color: var(--neon-green);">
<div>$ ./aiscn --cohort 2026 --mode=immersive --duration=45d</div>
<div style="color:var(--text-muted);">› parsing manifest ............................. <span class="text-neon">[OK]</span></div>
<div style="color:var(--text-muted);">› allocating mentor pool ....................... <span class="text-neon">[OK]</span></div>
<div style="color:var(--text-muted);">› binding lab targets (THM/HTB/Juice/PicoGym) .. <span class="text-neon">[OK]</span></div>
<div style="color:var(--text-muted);">› loading OWASP LLM Top-10 / MITRE ATLAS ....... <span class="text-neon">[OK]</span></div>
<div style="color:var(--text-cyan);">› cohort launched. operator stand by ...</div>
<div style="margin-top: 8px; color: var(--neon-cyan);">$ <span style="animation: blink-cursor 0.8s step-end infinite;">_</span></div>
</div>
</div>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; padding-top: 1rem;">
<div class="cyber-card cyber-card-top-accent">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="text-neon mono" style="font-size: 2.7rem; font-weight: bold; line-height: 1;">45</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">[ DAYS ]</div>
<div class="text-xs text-muted">Days of Training</div>
</div>
<div class="cyber-card cyber-card-top-accent">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="text-neon mono" style="font-size: 2.7rem; font-weight: bold; line-height: 1;">10</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">[ LIVE CLASSES ]</div>
<div class="text-xs text-muted">90-120 min blocks</div>
</div>
<div class="cyber-card cyber-card-top-accent">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="text-neon mono" style="font-size: 2.7rem; font-weight: bold; line-height: 1;">02</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">[ MINOR PROJECTS ]</div>
<div class="text-xs text-muted">MP1 · MP2</div>
</div>
<div class="cyber-card cyber-card-top-accent">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="text-neon mono" style="font-size: 2.7rem; font-weight: bold; line-height: 1;">01</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">[ MAJOR PROJECT ]</div>
<div class="text-xs text-muted">Capstone · 40% weight</div>
</div>
<div class="cyber-card cyber-card-top-accent" style="grid-column: span 2;">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="text-neon mono" style="font-size: 2.7rem; font-weight: bold; line-height: 1;">01</div>
<div class="mono text-xs tracking-widest text-muted" style="margin-top: 0.5rem; margin-bottom: 0.2rem;">[ EXPERT TALK ]</div>
<div class="text-xs text-muted">Industry practitioner · 19 Jul 2026</div>
</div>
</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# Divider
st.markdown('<div class="divider-ascii">▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  /var/log/aiscn.log  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰</div>', unsafe_allow_html=True)

# =========================
# 2. WORKFLOW SECTION
# =========================
st.markdown('<div id="workflow"></div>', unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; margin-bottom: 3rem;">
<div class="section-label">// PROGRAM_PIPELINE.SH</div>
<h2 class="section-h2">&gt;_ AISCN-2026 <span class="accent">Workflow</span></h2>
<p class="text-muted text-sm" style="font-family:'JetBrains Mono', monospace;">Sequential pipeline stages from onboarding through certification. Each node is a checkpoint in<br>the live program, mirroring the handbook timeline.</p>
</div>

<div style="max-width: 900px; margin: 0 auto 6rem auto;">
<div class="timeline-container">
<div class="timeline-line"></div>

<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[01] // STAGE</span> <span>// PRE_WEEK</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Onboarding</h3>
<div class="text-muted text-sm">Discord induction, prerequisites &amp; lab setup</div>
</div>
</div>

<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[02] // STAGE</span> <span>// 14 JUN → 15 JUL</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Live Classes</h3>
<div class="text-muted text-sm">10 live sessions · Sun + Wed · 90–120 min</div>
</div>
</div>

<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[03] // STAGE</span> <span>// CONTINUOUS</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Labs &amp; Practice</h3>
<div class="text-muted text-sm">Bandit, Wireshark, TryHackMe, PortSwigger, Juice Shop, PicoGym</div>
</div>
</div>

<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[04] // STAGE</span> <span>// MENTORS</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Doubt Sessions</h3>
<div class="text-muted text-sm">Continuous mentor support — live + async on Discord</div>
</div>
</div>

<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[05] // STAGE</span> <span>// 21-28 JUN</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Minor Project 1</h3>
<div class="text-muted text-sm">Network &amp; Web Security Observation Report · 15% weight</div>
</div>
</div>

<div class="timeline-item">
<div class="timeline-dot active"></div>
<div class="cyber-card" style="border-color: var(--neon-cyan); box-shadow: 0 0 18px rgba(0,229,255,0.25), inset 0 0 30px rgba(0,229,255,0.04);">
<span class="corner tl" style="border-color:var(--neon-cyan);"></span>
<span class="corner tr" style="border-color:var(--neon-cyan);"></span>
<span class="corner bl" style="border-color:var(--neon-cyan);"></span>
<span class="corner br" style="border-color:var(--neon-cyan);"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-cyan">[06] // ACTIVE</span> <span>// 05-12 JUL</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Minor Project 2</h3>
<div class="text-muted text-sm">Security Assessment &amp; Pentesting Workflow Report · 20% weight</div>
</div>
</div>

<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-neon">[07] // STAGE</span> <span>// 15-25 JUL</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Major Project</h3>
<div class="text-muted text-sm">AI Security Risk Assessment &amp; Secure AI Application Design · 40% weight</div>
</div>
</div>

<div class="timeline-item">
<div class="timeline-dot"></div>
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;" class="mono text-xs text-muted">
<span class="text-cyan">[08] // EVENT</span> <span>// 19 JUL 2026</span>
</div>
<h3 style="margin: 0 0 0.2rem 0; font-size: 1.2rem;">&gt; Expert Talk</h3>
<div class="text-muted text-sm">"Cybersecurity &amp; AI Security Careers in 2026 and Beyond"</div>
</div>
</div>

</div>
</div>
""", unsafe_allow_html=True)

# Divider
st.markdown('<div class="divider-ascii">▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  /etc/aiscn/projects.conf  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰</div>', unsafe_allow_html=True)

# =========================
# 3. ROADMAP & ASSESSMENT
# =========================
st.markdown("""
<div style="text-align: center; margin-bottom: 3rem;">
<div class="section-label">// PORTFOLIO_DELIVERABLES.MK</div>
<h2 class="section-h2">&gt;_ Project <span class="accent">Roadmap</span></h2>
<p class="text-muted text-sm" style="font-family:'JetBrains Mono', monospace;">Three progressive payloads scale in difficulty and align with the curriculum — 2 minor reports<br>and 1 major capstone.</p>
</div>

<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin-bottom: 1.5rem;">

<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 1rem;" class="mono text-xs">
<span class="chip">MINOR PROJECT 1</span>
<span class="chip cyan">15% WEIGHT</span>
</div>
<h4 style="margin: 0 0 1rem 0; font-size: 1.1rem; line-height: 1.4;">Network &amp; Web Security<br>Observation Report</h4>
<p class="text-muted text-sm" style="line-height: 1.5; margin-bottom: 1.5rem; font-family:'JetBrains Mono', monospace;">Document how networking and web security concepts manifest in a real lab environment — Wireshark captures, Burp annotations, OWASP findings, personal reflection.</p>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
<div style="border: 1px solid var(--border-color); padding: 0.5rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px;">ASSIGNED</div>
<div class="mono text-neon text-sm">21 Jun 2026</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.5rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px;">REVIEW</div>
<div class="mono text-neon text-sm">28 Jun 2026</div>
</div>
</div>
<div class="mono text-muted" style="font-size: 10px;">PDF · ≤ 10 pages · MP1_&lt;Name&gt;_AISCN2026.pdf</div>
</div>

<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 1rem;" class="mono text-xs">
<span class="chip">MINOR PROJECT 2</span>
<span class="chip cyan">20% WEIGHT</span>
</div>
<h4 style="margin: 0 0 1rem 0; font-size: 1.1rem; line-height: 1.4;">Security Assessment &amp;<br>Pentesting Workflow Report</h4>
<p class="text-muted text-sm" style="line-height: 1.5; margin-bottom: 1.5rem; font-family:'JetBrains Mono', monospace;">Simulate a junior pentester's workflow on a legal, intentionally vulnerable lab target (TryHackMe / HTB free / Juice Shop) and produce a structured, professional security assessment.</p>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
<div style="border: 1px solid var(--border-color); padding: 0.5rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px;">ASSIGNED</div>
<div class="mono text-neon text-sm">05 Jul 2026</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.5rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px;">REVIEW</div>
<div class="mono text-neon text-sm">12 Jul 2026</div>
</div>
</div>
<div class="mono text-muted" style="font-size: 10px;">PDF · ≤ 15 pages · MP2_&lt;Name&gt;_AISCN2026.pdf</div>
</div>

<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div style="display: flex; justify-content: space-between; margin-bottom: 1rem;" class="mono text-xs">
<span class="chip">MAJOR PROJECT</span>
<span class="chip cyan">40% WEIGHT</span>
</div>
<h4 style="margin: 0 0 1rem 0; font-size: 1.1rem; line-height: 1.4;">AI Security Risk Assessment &amp;<br>Secure AI Application Design</h4>
<p class="text-muted text-sm" style="line-height: 1.5; margin-bottom: 1.5rem; font-family:'JetBrains Mono', monospace;">Capstone deliverable — choose a hypothetical AI-powered application, conduct an AI security risk assessment (OWASP LLM Top 10 + MITRE ATLAS) and propose a secure design including agentic considerations.</p>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
<div style="border: 1px solid var(--border-color); padding: 0.5rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px;">ASSIGNED</div>
<div class="mono text-neon text-sm">15 Jul 2026</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.5rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px;">PRESENTATION</div>
<div class="mono text-neon text-sm">26 Jul 2026</div>
</div>
</div>
<div class="mono text-muted" style="font-size: 10px;">PDF 20-25 pages + PPT 8-12 slides · 10 min + 5 min Q&amp;A</div>
</div>

</div>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 4rem;">
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="section-label">// MARKING_SCHEME</div>
<h3 style="margin: 0.4rem 0 1.5rem 0; font-size: 1.3rem;">&gt; Assessment Structure</h3>
<div style="display: flex; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);" class="text-sm">
<span class="text-muted">Class Participation &amp; Lab Engagement</span> <span class="mono text-neon">10%</span>
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
<span class="text-cyan">[ TOTAL ]</span> <span class="mono text-neon">100%</span>
</div>
</div>

<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="section-label">// COMPLETION_CRITERIA</div>
<h3 style="margin: 0.4rem 0 1.5rem 0; font-size: 1.3rem;">&gt; Certificate Eligibility</h3>
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
<div style="border: 1px solid var(--border-color); padding: 0.75rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">ISSUED</div>
<div class="mono text-neon text-sm">Internship Completion</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.75rem; background: rgba(0,229,255,0.03);">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">&gt; 70%</div>
<div class="mono text-cyan text-sm">Performance Letter</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.75rem; background: rgba(0,255,65,0.03);">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">TOP 10%</div>
<div class="mono text-neon text-sm">Letter of Excellence</div>
</div>
<div style="border: 1px solid var(--border-color); padding: 0.75rem; background: rgba(0,229,255,0.03);">
<div class="mono text-muted" style="font-size: 10px; margin-bottom: 4px;">AWARD</div>
<div class="mono text-cyan text-sm">Best Project (per category)</div>
</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# Divider
st.markdown('<div class="divider-ascii">▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  /dev/uplink/submit  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰</div>', unsafe_allow_html=True)

# =========================
# 4. SUBMISSION PORTAL
# =========================
st.markdown('<div id="submission-portal"></div>', unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; margin-bottom: 1.5rem;">
<div class="section-label">// SECURE_UPLINK.PORTAL</div>
<h2 class="section-h2">&gt;_ Submission <span class="accent">Portal</span></h2>
<p class="text-muted text-sm" style="font-family:'JetBrains Mono', monospace;">All payloads encrypted in transit. Hash-logged. One uplink per operator per project.</p>
</div>
""", unsafe_allow_html=True)

# OPERATOR IDENTITY
st.markdown("""
<div class="term-window" style="margin: 0 auto 1.2rem auto; max-width: 100%;">
<div class="term-header">
<span class="term-dot red"></span><span class="term-dot amb"></span><span class="term-dot grn"></span>
<span style="margin-left:6px;">/usr/bin/auth — operator-identity --register</span>
</div>
<div class="term-body" style="padding:14px 18px;">
<div class="mono text-neon text-xs tracking-widest">// OPERATOR IDENTITY :: AUTH REQUIRED</div>
</div>
</div>
""", unsafe_allow_html=True)

id_col1, id_col2 = st.columns(2)
with id_col1:
    user_name = st.text_input("FULL_NAME", placeholder="enter operator handle / registered name", key="user_name")
with id_col2:
    user_email = st.text_input("EMAIL_ADDR", placeholder="operator@registered.domain", key="user_email")

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown("""
<div class="cyber-card" style="margin-bottom:1rem;">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="mono text-xs text-muted" style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
<span>PAYLOAD // MP1</span> <span class="text-neon">● READY</span>
</div>
<h3 style="margin:0 0 0.2rem 0;">&gt; MINOR PROJECT — 1</h3>
<div class="text-xs text-muted" style="margin-bottom: 0.6rem;">PDF format only · Max 20 MB</div>
<div class="text-xs text-cyan mono">$ scp ./MP1_&lt;Name&gt;.pdf vault@aiscn:/uplink</div>
</div>
    """, unsafe_allow_html=True)

    mp1_file = st.file_uploader("Upload MP1", type=["pdf"], label_visibility="collapsed", key="mp1")
    if mp1_file is not None:
        st.session_state["mp1_file"] = mp1_file
    if st.button("TRANSMIT MP1", key="b1b", type="primary"):
        handle_submission(user_name, user_email, st.session_state.get("mp1_file"), "MP1")

with col2:
    st.markdown("""
<div class="cyber-card" style="margin-bottom:1rem;">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="mono text-xs text-muted" style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
<span>PAYLOAD // MP2</span> <span class="text-neon">● READY</span>
</div>
<h3 style="margin:0 0 0.2rem 0;">&gt; MINOR PROJECT — 2</h3>
<div class="text-xs text-muted" style="margin-bottom: 0.6rem;">PDF format only · Max 20 MB</div>
<div class="text-xs text-cyan mono">$ scp ./MP2_&lt;Name&gt;.pdf vault@aiscn:/uplink</div>
</div>
    """, unsafe_allow_html=True)

    mp2_file = st.file_uploader("Upload MP2", type=["pdf"], label_visibility="collapsed", key="mp2")
    if mp2_file is not None:
        st.session_state["mp2_file"] = mp2_file
    if st.button("TRANSMIT MP2", key="b2b", type="primary"):
        handle_submission(user_name, user_email, st.session_state.get("mp2_file"), "MP2")

with col3:
    st.markdown("""
<div class="cyber-card" style="margin-bottom:1rem;">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="mono text-xs text-muted" style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
<span>PAYLOAD // MJP</span> <span class="text-neon">● READY</span>
</div>
<h3 style="margin:0 0 0.2rem 0;">&gt; MAJOR PROJECT</h3>
<div class="text-xs text-muted" style="margin-bottom: 0.6rem;">PDF format only · Max 20 MB</div>
<div class="text-xs text-cyan mono">$ scp ./MJP_&lt;Name&gt;.pdf vault@aiscn:/uplink</div>
</div>
    """, unsafe_allow_html=True)

    mjp_file = st.file_uploader("Upload MJP", type=["pdf"], label_visibility="collapsed", key="mjp")
    if mjp_file is not None:
        st.session_state["mjp_file"] = mjp_file
    if st.button("TRANSMIT MJP", key="b3b", type="primary"):
        handle_submission(user_name, user_email, st.session_state.get("mjp_file"), "MJP")

# Divider
st.markdown('<div class="divider-ascii">▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰  /etc/aiscn/personnel.lst  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰</div>', unsafe_allow_html=True)

# =========================
# 5. FOOTER PANELS
# =========================
f_col1, f_col2 = st.columns(2, gap="large")

with f_col1:
    st.markdown("""
<div class="cyber-card">
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="section-label">// OFFICE</div>
<h3 style="margin: 0.4rem 0 1rem 0;">&gt; Program Office</h3>
<div style="display: grid; grid-template-columns: 160px 1fr; gap: 0.5rem; font-size: 0.9rem;" class="mono text-muted">
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
<span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
<div class="section-label">// MENTOR_PANEL</div>
<h3 style="margin: 0.4rem 0 1rem 0;">&gt; Faculty &amp; Mentors</h3>
<div style="display: grid; grid-template-columns: 160px 1fr; gap: 0.5rem; font-size: 0.9rem;" class="mono text-muted">
<div class="text-cyan">Gaurav Jain</div> <div>— Linux, Pentesting, AI Security</div>
<div class="text-cyan">Ganesh Kanojiya</div> <div>— Networking, SOC, AI Security</div>
<div class="text-cyan">Kanishka Jain</div> <div>— Windows Security, SOC Ops</div>
<div class="text-cyan">Anant Awasthi</div> <div>— Web Security, Cryptography</div>
<div class="text-cyan">Sahil Bharti</div> <div>— Web Application Security</div>
</div>
</div>
    """, unsafe_allow_html=True)

# =========================
# FINAL FOOTER
# =========================
st.markdown("""
<div style="text-align: center; margin-top: 4rem; padding-bottom: 2rem;">

<div style="font-family:'VT323', monospace; color:var(--neon-green); font-size: 22px; letter-spacing: 0.2em; text-shadow: 0 0 8px var(--neon-green);">
&gt;&gt; AISCN'26 INTERNSHIP PROGRAM &lt;&lt;
</div>
<div class="mono text-muted text-xs tracking-widest" style="margin-top:0.5rem;">[ CORE TEAM SUBMISSION SYSTEM ]</div>

<div class="mono text-xs" style="margin-top:1rem;">
<span style="color:var(--neon-green); text-shadow:0 0 6px var(--neon-green);">●</span>
<span class="text-cyan">secure-channel://aiscn26.submissions</span>
<span style="color:var(--neon-green); text-shadow:0 0 6px var(--neon-green);">●</span>
</div>

<div style="display:flex; justify-content:center; gap:2rem; margin-top:1.5rem; font-family:'Share Tech Mono', monospace; font-size:11px; color:var(--text-muted); flex-wrap:wrap;">
<span>HASH: SHA-256</span>
<span>CIPHER: AES-256-GCM</span>
<span>PROTOCOL: TLS-1.3</span>
<span>UPTIME: 99.97%</span>
<span>NODES: 7</span>
</div>

<p class="text-muted text-xs" style="max-width: 680px; margin: 2rem auto 0 auto; line-height: 1.6; opacity: 0.7; font-family:'JetBrains Mono', monospace;">
[!] Stay ethical. All hands-on activities are restricted to legally authorized environments — TryHackMe, OverTheWire, Hack The Box,
OWASP Juice Shop, PicoGym. Application of any technique to unauthorized systems is strictly prohibited under the Information
Technology Act, 2000 (India).
</p>

<div style="margin-top: 2rem; font-family:'VT323', monospace; color: var(--neon-green); font-size: 16px;">
root@aiscn:~# logout<span style="animation: blink-cursor 0.8s step-end infinite;">_</span>
</div>

</div>
""", unsafe_allow_html=True)
