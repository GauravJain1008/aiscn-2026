import os
import json
import ssl
import smtplib
import io
from datetime import datetime
from email.message import EmailMessage

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


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


def safe_json_load(path: str) -> dict:
    """Safely loads JSON, returning empty dict on any issue."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def is_blocked(email: str) -> bool:
    """Strict global limit: block once total submissions for an email reach SUBMISSION_LIMIT."""
    db = safe_json_load(DB_FILE)
    return len(db.get(email.lower(), [])) >= SUBMISSION_LIMIT


def check_duplicate(email: str, sub_type: str) -> bool:
    """Checks local JSON registry to prevent duplicate submissions."""
    db = safe_json_load(DB_FILE)
    return sub_type in db.get(email.lower(), [])


def log_submission(email: str, sub_type: str):
    """Logs successful submission to local JSON registry."""
    db = safe_json_load(DB_FILE)
    email_key = email.lower()

    if email_key not in db:
        db[email_key] = []

    if sub_type not in db[email_key]:
        db[email_key].append(sub_type)

    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


def upload_to_drive(file_bytes: bytes, file_name: str) -> str:
    """Uploads file to Google Drive via OAuth Refresh Token and returns View Link."""
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

    file_metadata = {
        "name": file_name,
        "parents": [folder_id],
    }

    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype="application/pdf",
        resumable=True,
    )

    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )

    return file.get("webViewLink", "")


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
            human_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

            safe_name = name.replace(" ", "_").replace("/", "")
            safe_email = email.replace("/", "_").replace(" ", "_")
            drive_file_name = f"{sub_type}_{safe_name}_{safe_email}_{timestamp}.pdf"

            drive_link = upload_to_drive(file_bytes, drive_file_name)
            send_admin_email(name, email, sub_type, drive_link, human_time)
            log_submission(email, sub_type)

        st.success(f">> UPLINK SUCCESSFUL. {sub_type} SECURED IN VAULT.")
        st.markdown(
            f"""
            <div style="
                margin-top:0.5rem;
                padding:10px;
                background:rgba(0, 229, 255, 0.05);
                border:1px solid #00e5ff;
                border-radius:6px;
                font-size:0.85rem;
            ">
                <strong>FILE_ACCESS_URL:</strong>
                <a href="{drive_link}" target="_blank" style="color:#00e5ff; text-decoration:underline; font-weight:bold;">
                    {drive_link}
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.balloons()

    except Exception as e:
        st.error(f">> CRITICAL UPLINK FAILURE: {str(e)}")


# =========================
# INJECTED CSS
# =========================
CUSTOM_CSS = """
<style>
    .main {
        background: linear-gradient(180deg, #050608 0%, #090d12 100%);
        color: #e6f1ff;
    }
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #00ffaa;
        color: #00ffaa;
        background: transparent;
        font-weight: 700;
    }
    .stDownloadButton > button {
        border-radius: 8px;
        border: 1px solid #00e5ff;
        color: #00e5ff;
        background: transparent;
        font-weight: 700;
    }
    .card {
        padding: 18px;
        border: 1px solid rgba(0,255,170,0.18);
        border-radius: 16px;
        background: rgba(255,255,255,0.03);
        box-shadow: 0 0 18px rgba(0,255,170,0.06);
    }
    .mono {
        font-family: monospace;
    }
    .title {
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: 0.04em;
    }
    .subtitle {
        color: #8ca3b8;
        font-size: 1rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================
# SIDEBAR: OPERATOR IDENTITY
# =========================
with st.sidebar:
    st.markdown("### OPERATOR IDENTITY")
    user_name = st.text_input("Name", placeholder="Enter your name")
    user_email = st.text_input("Email", placeholder="Enter your email")

    st.markdown("---")
    st.caption("Upload limit per email: 3 total submissions")
    st.caption("Supported files: PDF only")

# =========================
# 1. HERO SECTION
# =========================
st.markdown(
    """
    <div class="card">
        <div class="title">AISCN'26 // PORTAL</div>
        <div class="subtitle">Secure submission gateway for MP1, MP2, and MJP uplinks.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

hero_col1, hero_col2 = st.columns([1, 4])
with hero_col1:
    st.markdown(
        """
        <a href="#workflow" target="_top" style="text-decoration: none;">
            <button style="background-color: transparent; color: #00ffaa; border: 1px solid #00ffaa; padding: 10px 20px; font-weight: bold; cursor: pointer; font-family: inherit; border-radius: 6px;">
                VIEW WORKFLOW ↓
            </button>
        </a>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

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
st.markdown('<div id="workflow"></div>', unsafe_allow_html=True)
st.markdown("## WORKFLOW")

wf1, wf2, wf3 = st.columns(3)
with wf1:
    st.markdown(
        """
        <div class="card">
            <h4>STEP 01</h4>
            <p>Enter operator identity in the sidebar.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with wf2:
    st.markdown(
        """
        <div class="card">
            <h4>STEP 02</h4>
            <p>Upload the required PDF submission in its respective panel.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with wf3:
    st.markdown(
        """
        <div class="card">
            <h4>STEP 03</h4>
            <p>Submit and receive the Drive access link on success.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =========================
# 3. ROADMAP & ASSESSMENT
# =========================
st.markdown("## ROADMAP & ASSESSMENT")

rm1, rm2 = st.columns(2, gap="large")
with rm1:
    st.markdown(
        """
        <div class="card">
            <h4>ROADMAP</h4>
            <ul>
                <li>MP1 upload</li>
                <li>MP2 upload</li>
                <li>MJP upload</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
with rm2:
    st.markdown(
        """
        <div class="card">
            <h4>ASSESSMENT</h4>
            <ul>
                <li>Valid PDF required</li>
                <li>No duplicate submission for same type</li>
                <li>Email blocked after 3 total uploads</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =========================
# 4. SUBMISSION PORTAL
# =========================
st.markdown("## SUBMISSION PORTAL")

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown('<div class="card"><h4>MP1</h4></div>', unsafe_allow_html=True)
    mp1_file = st.file_uploader(
        "Upload MP1",
        type=["pdf"],
        label_visibility="collapsed",
        key="mp1",
    )
    if st.button("SUBMIT MP1", key="b1b", type="primary"):
        handle_submission(user_name, user_email, mp1_file, "MP1")

with col2:
    st.markdown('<div class="card"><h4>MP2</h4></div>', unsafe_allow_html=True)
    mp2_file = st.file_uploader(
        "Upload MP2",
        type=["pdf"],
        label_visibility="collapsed",
        key="mp2",
    )
    if st.button("SUBMIT MP2", key="b2b", type="primary"):
        handle_submission(user_name, user_email, mp2_file, "MP2")

with col3:
    st.markdown('<div class="card"><h4>MJP</h4></div>', unsafe_allow_html=True)
    mjp_file = st.file_uploader(
        "Upload MJP",
        type=["pdf"],
        label_visibility="collapsed",
        key="mjp",
    )
    if st.button("SUBMIT MJP", key="b3b", type="primary"):
        handle_submission(user_name, user_email, mjp_file, "MJP")

# =========================
# 5. FOOTER PANELS
# =========================
st.markdown("<br>", unsafe_allow_html=True)

f_col1, f_col2 = st.columns(2, gap="large")

with f_col1:
    st.markdown(
        """
        <div class="card">
            <h4>STATUS</h4>
            <p>Secure uplink active. Please ensure your submissions are final before sending.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with f_col2:
    st.markdown(
        """
        <div class="card">
            <h4>WARNING</h4>
            <p>Unauthorized reuse, spam, or malformed uploads may result in operator blocking.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <div style="text-align:center; margin-top:24px; opacity:0.8;">
        <small>© AISCN'26 // Portal • Secure Submission Interface</small>
    </div>
    """,
    unsafe_allow_html=True,
)
