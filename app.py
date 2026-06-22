import os
import io
import json
import ssl
import smtplib
from datetime import datetime
from email.message import EmailMessage

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


st.set_page_config(
    page_title="AISCN'26 // Portal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DB_FILE = "submission_registry.json"
HANDBOOK_PATH = "/home/parrot/AISCN_2026_Handbook.pdf"
SUBMISSION_LIMIT = 3


@st.cache_data
def load_handbook_bytes() -> bytes:
    if os.path.exists(HANDBOOK_PATH):
        with open(HANDBOOK_PATH, "rb") as f:
            return f.read()
    return b""


def safe_json_load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def is_blocked(email: str) -> bool:
    db = safe_json_load(DB_FILE)
    return len(db.get(email.lower(), [])) >= SUBMISSION_LIMIT


def check_duplicate(email: str, sub_type: str) -> bool:
    db = safe_json_load(DB_FILE)
    return sub_type in db.get(email.lower(), [])


def log_submission(email: str, sub_type: str):
    db = safe_json_load(DB_FILE)
    email_key = email.lower()
    db.setdefault(email_key, [])
    if sub_type not in db[email_key]:
        db[email_key].append(sub_type)
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


def upload_to_drive(file_bytes: bytes, file_name: str) -> str:
    creds_info = st.secrets["oauth"]
    creds = Credentials(
        token=None,
        refresh_token=creds_info["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_info["client_id"],
        client_secret=creds_info["client_secret"],
    )
    service = build("drive", "v3", credentials=creds)
    folder_id = st.secrets["drive"]["folder_id"]
    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="application/pdf", resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()
    return file.get("webViewLink", "")


def send_admin_email(name: str, email: str, sub_type: str, drive_link: str, timestamp: str):
    mail_user = st.secrets["smtp"]["mail_user"]
    mail_pass = st.secrets["smtp"]["mail_pass"]
    mail_to = st.secrets["smtp"]["mail_to"]

    msg = EmailMessage()
    msg["Subject"] = f"[AISCN'26 NEW UPLINK] {sub_type} - {name}"
    msg["From"] = mail_user
    msg["To"] = mail_to
    msg.set_content(f"""
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
""")

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
            human_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            safe_name = name.replace(" ", "_").replace("/", "")
            safe_email = email.replace("/", "_").replace(" ", "_")
            drive_file_name = f"{sub_type}_{safe_name}_{safe_email}_{timestamp}.pdf"
            drive_link = upload_to_drive(file_bytes, drive_file_name)
            send_admin_email(name, email, sub_type, drive_link, human_time)
            log_submission(email, sub_type)

        st.success(f">> UPLINK SUCCESSFUL. {sub_type} SECURED IN VAULT.")
        st.markdown(
            f'<div style="margin-top:0.5rem;padding:10px;background:rgba(0, 229, 255, 0.05);border:1px solid #00e5ff;border-radius:6px;font-size:0.85rem;">'
            f'<strong>FILE_ACCESS_URL:</strong> '
            f'<a href="{drive_link}" target="_blank" style="color:#00e5ff;text-decoration:underline;font-weight:bold;">{drive_link}</a>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.balloons()
    except Exception as e:
        st.error(f">> CRITICAL UPLINK FAILURE: {str(e)}")


CUSTOM_CSS = """
<style>
:root {
  --bg:#05070A; --bg2:#0D1117; --accent:#00FF88; --accent2:#00E5FF; --text:#E6EDF3; --muted:#7D8590;
  --card: rgba(17, 25, 40, 0.85);
}
html, body, [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--text); }
#MainMenu, footer, header { visibility: hidden; }
.stApp { background:
  linear-gradient(rgba(0,255,136,0.06) 1px, transparent 1px),
  linear-gradient(90deg, rgba(0,255,136,0.06) 1px, transparent 1px),
  radial-gradient(circle at 20% 20%, rgba(0,255,136,0.10), transparent 40%),
  radial-gradient(circle at 80% 80%, rgba(0,229,255,0.08), transparent 45%),
  var(--bg); background-size: 48px 48px, 48px 48px, auto, auto, auto; }
.block-container { padding-top: 1.25rem; padding-bottom: 2rem; }
.glass {
  background: var(--card);
  backdrop-filter: blur(14px) saturate(140%);
  border: 1px solid rgba(0,255,136,0.18);
  border-radius: 16px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset, 0 0 0 1px rgba(0,255,136,0.05), 0 20px 50px -20px rgba(0,0,0,0.6);
}
.card-bar { height: 2px; background: linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent); opacity:0.7; border-radius: 16px 16px 0 0; }
.chip, .sec-eyebrow, .phase-tag, .stat-lbl, .stat-sub, .topic-list li, .date-cell .lbl, .date-cell .val, .signature-label, .signature-name, .hero-typer, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.chip { display:inline-flex; align-items:center; gap:8px; padding:4px 12px; border-radius:999px; border:1px solid rgba(0,255,136,0.3); background:rgba(0,255,136,0.05); font-size:11px; letter-spacing:0.25em; color:var(--accent); text-transform:uppercase; }
.chip .live-dot { width:6px; height:6px; border-radius:50%; background:var(--accent); box-shadow:0 0 8px var(--accent); animation:pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.35} }
.sec-eyebrow { font-size:10px; letter-spacing:0.4em; color:var(--accent); text-transform:uppercase; }
.sec-title { font-family: ui-monospace, monospace; font-weight:700; letter-spacing:0.05em; color:var(--text); text-shadow:0 0 12px rgba(0,255,136,0.35); }
.title { font-size: clamp(2.5rem, 6vw, 4.5rem); font-weight: 800; letter-spacing: 0.04em; }
.subtitle { color: var(--muted); font-size: 1rem; }
.text-glow { text-shadow: 0 0 12px rgba(0,255,136,0.45); }
.text-glow-cyan { text-shadow: 0 0 10px rgba(0,229,255,0.45); }
.stat-tile { position:relative; padding:18px 18px 16px; border-radius:14px; background:var(--card); border:1px solid rgba(0,255,136,0.15); overflow:hidden; transition:border-color .2s ease, transform .2s ease; }
.stat-tile::before { content:""; position:absolute; top:0; left:0; height:2px; width:36%; background:var(--accent); box-shadow:0 0 10px var(--accent); }
.stat-tile:hover { border-color: rgba(0,255,136,0.45); transform:translateY(-2px); }
.stat-val { font-size:36px; font-weight:800; color:var(--accent); line-height:1; text-shadow:0 0 14px rgba(0,255,136,0.35); }
.stat-lbl { font-size:10px; color:var(--muted); letter-spacing:0.25em; text-transform:uppercase; margin-top:6px; }
.stat-sub { font-size:9px; color:var(--muted); letter-spacing:0.18em; margin-top:2px; opacity:0.8; }
.wf-rail { position:relative; padding-left:28px; }
.wf-rail::before { content:""; position:absolute; left:9px; top:4px; bottom:4px; width:2px; background:linear-gradient(180deg, var(--accent) 0%, var(--accent2) 100%); border-radius:2px; opacity:0.55; }
.wf-node { position:relative; transition:transform .2s ease; }
.wf-node::before { content:""; position:absolute; left:-27px; top:18px; width:14px; height:14px; background:var(--bg2); border:2px solid var(--accent); border-radius:50%; box-shadow:0 0 0 3px rgba(0,255,136,0.08); }
.wf-node:hover { transform: translateX(3px); }
.wf-node.event::before { border-color: var(--accent2); }
.phase-tag { font-size:10px; letter-spacing:0.2em; background:rgba(0,255,136,0.08); border:1px solid rgba(0,255,136,0.35); color:var(--accent); padding:2px 8px; border-radius:4px; }
.topic-list li { position:relative; padding-left:18px; font-size:12px; color:var(--text); line-height:1.7; }
.topic-list li::before { content:"▸"; position:absolute; left:0; top:0; color:var(--accent); }
.date-cell { background:rgba(13,17,23,0.7); border:1px solid rgba(0,255,136,0.18); border-radius:8px; padding:8px 10px; }
.date-cell .lbl { font-size:9px; color:var(--muted); letter-spacing:0.25em; text-transform:uppercase; }
.date-cell .val { font-size:13px; color:var(--accent); margin-top:2px; letter-spacing:0.05em; }
.btn-primary > button, .btn-ghost > button { border-radius:12px !important; font-family: ui-monospace, monospace; letter-spacing:0.18em; text-transform:uppercase; }
.btn-primary > button { background: linear-gradient(135deg, var(--accent) 0%, #00C46A 100%); color:#04110A; border:1px solid rgba(0,255,136,0.6); box-shadow:0 0 20px -4px rgba(0,255,136,0.5); }
.btn-ghost > button { border:1px solid rgba(0,229,255,0.35); color:var(--accent2); background:rgba(0,229,255,0.05); }
.btn-ghost > button:hover { border-color: var(--accent2); background: rgba(0,229,255,0.12); }
.hero-typer { color: var(--accent2); letter-spacing: 0.32em; text-transform: uppercase; text-shadow: 0 0 10px rgba(0,229,255,0.45); min-height: 1.6em; display:inline-flex; align-items:center; }
.hero-typer::before { content: ">_ "; color: var(--accent); margin-right: 6px; opacity:0.7; }
.caret { display:inline-block; width:8px; height:1em; background:var(--accent2); margin-left:4px; animation: blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.signature { margin-top:32px; display:flex; justify-content:flex-end; }
.signature-card { position:relative; display:inline-flex; align-items:center; gap:12px; padding:10px 18px; border-radius:12px; background:linear-gradient(135deg, rgba(13,17,23,0.85), rgba(5,7,10,0.95)); border:1px solid rgba(0,255,136,0.25); overflow:hidden; }
.signature-card::before { content:""; position:absolute; top:0; left:0; right:0; height:1px; background:linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent); opacity:0.7; }
.signature-pulse { width:7px; height:7px; border-radius:50%; background:var(--accent); box-shadow:0 0 8px var(--accent), 0 0 18px rgba(0,255,136,0.6); animation:blink 1.4s ease-in-out infinite; }
.signature-label { font-size:9px; letter-spacing:0.4em; color:var(--muted); text-transform:uppercase; }
.signature-name { font-size:12px; letter-spacing:0.18em; background:linear-gradient(135deg, #ffffff 0%, var(--accent) 55%, var(--accent2) 100%); -webkit-background-clip:text; background-clip:text; color:transparent; font-weight:700; }
.signature-divider { width:1px; height:18px; background:linear-gradient(180deg, transparent, rgba(0,255,136,0.4), transparent); }
.dropzone { border:1.5px dashed rgba(0,255,136,0.35); border-radius:12px; background:rgba(0,255,136,0.03); transition:all .2s ease; }
.dropzone:hover { border-color: var(--accent); background: rgba(0,255,136,0.07); box-shadow: inset 0 0 24px rgba(0,255,136,0.10); }
.stFileUploader { background: transparent; }
.stFileUploader label { color: var(--muted) !important; }
.small-note { font-size: 11px; color: var(--muted); font-family: ui-monospace, monospace; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### OPERATOR IDENTITY")
    user_name = st.text_input("Name", placeholder="Enter your name")
    user_email = st.text_input("Email", placeholder="Enter your email")
    st.markdown("---")
    st.caption("Upload limit per email: 3 total submissions")
    st.caption("Supported files: PDF only")

st.markdown(
    """
    <div class="glass" style="padding:18px 20px;">
      <div class="chip"><span class="live-dot"></span> System // Online · Cohort 2026</div>
      <div class="title text-glow" style="margin-top:14px;">AISCN'<span style="color:var(--accent)">26</span></div>
      <div class="subtitle" style="margin-top:8px; letter-spacing:0.35em; text-transform:uppercase; color:var(--accent2);">AI Security · Cybersecurity · Networking</div>
      <div class="hero-typer" style="margin-top:10px;">Project Submission Portal<span class="caret"></span></div>
      <div style="margin-top:14px; color:var(--text); font-size:18px; font-family:ui-monospace, monospace;">45-Day Immersive Internship Program</div>
      <div style="margin-top:16px; color:var(--muted); line-height:1.7; max-width:900px; border-left:2px solid rgba(0,255,136,0.6); padding-left:16px;">
        Building the next generation of cybersecurity and AI security engineers through structured learning, practical labs, industry projects and mentor guidance.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 4])
with c1:
    st.markdown('<a href="#workflow" style="text-decoration:none;"><div class="btn-ghost"><button style="width:100%;padding:0.8rem 1rem;">VIEW WORKFLOW ↓</button></div></a>', unsafe_allow_html=True)
with c2:
    st.download_button(
        label="DOWNLOAD HANDBOOK ↓",
        data=load_handbook_bytes(),
        file_name="AISCN_Handbook_2026.pdf",
        mime="application/pdf",
        key="handbook_dl",
        use_container_width=True,
    )

st.markdown('<div id="workflow"></div>', unsafe_allow_html=True)
st.markdown("## WORKFLOW")
wf1, wf2, wf3 = st.columns(3)
with wf1:
    st.markdown('<div class="glass wf-node" style="padding:18px;"><div class="card-bar"></div><div class="sec-eyebrow" style="margin-top:10px;">STEP 01</div><div class="mono" style="font-size:18px;font-weight:700;margin-top:6px;">Onboarding</div><div class="small-note" style="margin-top:6px;">Discord induction, prerequisites & lab setup</div></div>', unsafe_allow_html=True)
with wf2:
    st.markdown('<div class="glass wf-node" style="padding:18px;"><div class="card-bar"></div><div class="sec-eyebrow" style="margin-top:10px;">STEP 02</div><div class="mono" style="font-size:18px;font-weight:700;margin-top:6px;">Upload</div><div class="small-note" style="margin-top:6px;">Submit MP1, MP2, or MJP in PDF only</div></div>', unsafe_allow_html=True)
with wf3:
    st.markdown('<div class="glass wf-node event" style="padding:18px;"><div class="card-bar"></div><div class="sec-eyebrow" style="margin-top:10px;color:var(--accent2);">STEP 03</div><div class="mono" style="font-size:18px;font-weight:700;margin-top:6px;">Secure Uplink</div><div class="small-note" style="margin-top:6px;">Drive link and admin email on success</div></div>', unsafe_allow_html=True)

st.markdown("## ROADMAP & ASSESSMENT")
rm1, rm2 = st.columns(2, gap="large")
with rm1:
    st.markdown('<div class="glass" style="padding:18px;"><div class="sec-eyebrow">ROADMAP</div><div class="mono" style="font-size:18px;font-weight:700;margin-top:8px;">Project Flow</div><ul class="topic-list" style="margin-top:12px;"><li>MP1</li><li>MP2</li><li>MJP</li></ul></div>', unsafe_allow_html=True)
with rm2:
    st.markdown('<div class="glass" style="padding:18px;"><div class="sec-eyebrow">ASSESSMENT</div><div class="mono" style="font-size:18px;font-weight:700;margin-top:8px;">Rules</div><ul class="topic-list" style="margin-top:12px;"><li>PDF required</li><li>No duplicate submission</li><li>Email blocked after 3 total uploads</li></ul></div>', unsafe_allow_html=True)

st.markdown("## PROGRAM PHASES")
phase_cols = st.columns(3)
phase_data = [
    ("P1 // CORE", "Foundation", ["Linux", "Networking", "Security Fundamentals", "SOC Intro"]),
    ("P2 // CORE", "Offensive & Defensive Awareness", ["Web Security", "Windows Security", "Cryptography"]),
    ("P3 // APPLIED", "Pentesting & Bug Bounty", ["Recon", "Enumeration", "Reporting"]),
    ("P4 // FRONTIER", "AI Security", ["LLMs", "OWASP LLM Top 10", "MITRE ATLAS"]),
    ("P5 // CAPSTONE", "Agentic AI & Capstone", ["MCP", "Agent Threat Models", "Major Project"]),
]
for i, (tag, title, items) in enumerate(phase_data):
    col = phase_cols[i % 3] if i < 3 else st.columns(3)[i - 2]
    with col:
        st.markdown('<div class="glass" style="padding:18px;"><div class="card-bar"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="phase-tag" style="display:inline-block;margin-top:12px;">{tag}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mono" style="font-size:18px;font-weight:700;margin-top:10px;">{title}</div>', unsafe_allow_html=True)
        st.markdown('<ul class="topic-list" style="margin-top:12px;">' + ''.join(f'<li>{x}</li>' for x in items) + '</ul>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("## SUBMISSION PORTAL")
col1, col2, col3 = st.columns(3, gap="large")
with col1:
    st.markdown('<div class="glass" style="padding:18px;"><div class="mono" style="font-size:22px;font-weight:700;">MP1</div><div class="small-note" style="margin:6px 0 12px;">PDF format only · Max 20 MB</div></div>', unsafe_allow_html=True)
    mp1_file = st.file_uploader("Upload MP1", type=["pdf"], label_visibility="collapsed", key="mp1")
    if st.button("SUBMIT MP1", key="b1b", type="primary", use_container_width=True):
        handle_submission(user_name, user_email, mp1_file, "MP1")
with col2:
    st.markdown('<div class="glass" style="padding:18px;"><div class="mono" style="font-size:22px;font-weight:700;">MP2</div><div class="small-note" style="margin:6px 0 12px;">PDF format only · Max 20 MB</div></div>', unsafe_allow_html=True)
    mp2_file = st.file_uploader("Upload MP2", type=["pdf"], label_visibility="collapsed", key="mp2")
    if st.button("SUBMIT MP2", key="b2b", type="primary", use_container_width=True):
        handle_submission(user_name, user_email, mp2_file, "MP2")
with col3:
    st.markdown('<div class="glass" style="padding:18px;"><div class="mono" style="font-size:22px;font-weight:700;">MJP</div><div class="small-note" style="margin:6px 0 12px;">PDF format only · Max 20 MB</div></div>', unsafe_allow_html=True)
    mjp_file = st.file_uploader("Upload MJP", type=["pdf"], label_visibility="collapsed", key="mjp")
    if st.button("SUBMIT MJP", key="b3b", type="primary", use_container_width=True):
        handle_submission(user_name, user_email, mjp_file, "MJP")

st.markdown("<br>", unsafe_allow_html=True)
ft1, ft2 = st.columns(2, gap="large")
with ft1:
    st.markdown(
        '<div class="glass" style="padding:18px;"><div class="sec-eyebrow">Office</div><div class="mono" style="font-size:18px;font-weight:700;margin-top:8px;">Program Office</div><div class="small-note" style="margin-top:10px;line-height:1.8;">Core Lead · Gaurav Jain · Ganesh Kanojiya<br>Faculty Panel · Ganesh · Kanishka · Anant · Sahil<br>Doubt Sessions · Continuous (Live + Async)<br>Document Version · v1.0 · June 2026</div></div>',
        unsafe_allow_html=True,
    )
with ft2:
    st.markdown(
        '<div class="glass" style="padding:18px;"><div class="sec-eyebrow">Mentor Panel</div><div class="mono" style="font-size:18px;font-weight:700;margin-top:8px;">Faculty & Mentors</div><div class="small-note" style="margin-top:10px;line-height:1.8;">Gaurav Jain — Linux, Pentesting, AI Security<br>Ganesh Kanojiya — Networking, SOC, AI Security<br>Kanishka Jain — Windows Security, SOC Ops<br>Anant Awasthi — Web Security, Cryptography<br>Sahil Bharti — Web Application Security</div></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="signature"><div class="signature-card"><span class="signature-pulse"></span><span class="signature-label">Crafted by</span><span class="signature-divider"></span><span class="signature-name">GAURAV JAIN</span></div></div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div style="text-align:center; margin-top:24px; opacity:0.8;"><small>© AISCN\'26 // Portal • Secure Submission Interface</small></div>',
    unsafe_allow_html=True,
)
