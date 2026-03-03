import streamlit as st
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import threading
import pymongo
import traceback
import time
import gridfs
import tempfile
from bson import ObjectId

# Add parent directory to path so we can import Project modules
sys.path.insert(0, str(Path(__file__).parent.parent))


st.set_page_config(page_title="ASD - Assignment Similarity Detection", layout="wide")

# Load Custom CSS
def load_css():
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# -------------------------
# State + Navigation
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "Home"


def navigate(page):
    st.session_state.page = page


def try_rerun():
    """Attempt to rerun Streamlit safely across Streamlit versions."""
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
    except Exception:
        pass
    # Fallback: update query params to force a rerun in newer Streamlit
    try:
        st.experimental_set_query_params(_rerun=int(datetime.now(timezone.utc).timestamp()))
    except Exception:
        # No-op if unavailable
        pass

# -------------------------
# Storage + DB helpers
# -------------------------
ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = ROOT / "storage" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_db(uri=None):
    uri = uri or st.secrets.get("MONGODB_URI") or "mongodb://localhost:27017"
    client = pymongo.MongoClient(uri)
    db = client["asd_app"]
    return db


def ensure_indexes(db):
    db.assignments.create_index("assignment_id", unique=True)
    db.submissions.create_index([("assignment_id", pymongo.ASCENDING), ("roll_no", pymongo.ASCENDING)])


def get_gridfs(db=None):
    """Return a GridFS instance for the current database."""
    db = db or get_db()
    return gridfs.GridFS(db)


def save_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile, assignment_id: str, roll_no: str):
    # rename to roll_assignment_timestamp.pdf for easier mapping
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ext = Path(uploaded_file.name).suffix
    safe_name = f"{roll_no}_{assignment_id}_{ts}{ext}"

    # read raw bytes from the uploaded file (works for PDFs, images, etc.)
    uploaded_file.seek(0)
    data_bytes = uploaded_file.read()

    # write local copy (for immediate OCR, backups, and convenience)
    dest = UPLOAD_DIR / safe_name
    with open(dest, "wb") as f:
        f.write(data_bytes)

    # also store in GridFS for persistence
    fs = get_gridfs()
    file_id = fs.put(data_bytes, filename=safe_name,
                     metadata={"assignment_id": assignment_id, "roll_no": roll_no})

    return str(dest), str(file_id)


# -------------------------
# Analysis helpers
# -------------------------

def fetch_gridfs_file(file_id: str) -> str:
    """Download a GridFS file to a temporary location and return its path."""
    fs = get_gridfs()
    try:
        gridout = fs.get(ObjectId(file_id))
    except Exception as e:
        raise FileNotFoundError(f"GridFS file {file_id} not found: {e}")
    tmp = Path(tempfile.gettempdir()) / str(file_id)
    with open(tmp, "wb") as f:
        f.write(gridout.read())
    return str(tmp)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Send the supplied PDF file directly to the OCR.space API and return its text.

    The free tier allows up to 3‑page PDFs, so no intermediate image conversion
    is necessary. This helper simply invokes the `Project.ocr_module.extract_text`
    wrapper.
    """
    project_path = str(Path(__file__).parent.parent / "Project")
    if project_path not in sys.path:
        sys.path.insert(0, project_path)
    from Project import ocr_module

    # Add simple retry with exponential backoff to handle transient OCR.space errors (e.g. E208)
    max_attempts = 3
    delay = 1.0
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            return ocr_module.extract_text(pdf_path)
        except Exception as e:
            last_err = e
            print(f"OCR attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                time.sleep(delay)
                delay *= 2
            else:
                # re-raise so callers can decide how to handle
                raise Exception(f"OCR failed after {max_attempts} attempts: {e}")


def send_analysis_email(assignment_id: str, teacher_email: str, matrix, avg, verdict, flagged_pairs):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_server = st.secrets.get("SMTP_SERVER")
    smtp_port = st.secrets.get("SMTP_PORT")
    smtp_user = st.secrets.get("SMTP_USER")
    smtp_pass = st.secrets.get("SMTP_PASSWORD")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Similarity Report for {assignment_id}"
    msg["From"] = smtp_user
    msg["To"] = teacher_email

    # build HTML
    html = f"""
    <html><body>
    <h2>Assignment {assignment_id} Analysis</h2>
    <p>Total Submissions: {matrix.shape[0]}</p>
    <h3>Overall Verdict: {verdict} ({avg}%)</h3>
    <p>Pairs with &gt;=60% similarity require review.</p>
    <h4>Similarity Matrix</h4>
    {matrix.to_html()}
    """
    if not flagged_pairs.empty:
        html += "<h4>Flagged Pairs</h4>"
        html += flagged_pairs.to_html(index=False)
    html += "</body></html>"

    msg.attach(MIMEText(html, "html"))

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_user, smtp_pass)
    server.sendmail(smtp_user, teacher_email, msg.as_string())
    server.quit()

    return True


def send_started_email(assignment_id: str, teacher_email: str):
    """Send a short notification to teacher that analysis has started."""
    try:
        import smtplib
        from email.mime.text import MIMEText

        smtp_server = st.secrets.get("SMTP_SERVER")
        smtp_port = st.secrets.get("SMTP_PORT")
        smtp_user = st.secrets.get("SMTP_USER")
        smtp_pass = st.secrets.get("SMTP_PASSWORD")

        subject = f"Analysis started for assignment {assignment_id}"
        body = f"Your Assignment with ID: {assignment_id} is being analyzed. You will receive the final report by email when processing completes."

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = teacher_email

        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [teacher_email], msg.as_string())
        server.quit()
        return True
    except Exception:
        return False


def process_assignment(assignment_id: str):
    """Background worker: convert PDFs->images, run pipeline, store results, send final email."""
    db = get_db()
    print(f"[WORKER] Starting analysis for {assignment_id}")
    try:
        # mark running
        print(f"[WORKER] Marking assignment {assignment_id} as running")
        db.assignments.update_one({"assignment_id": assignment_id}, {"$set": {"processing_status": "running", "active": False}})

        print(f"[WORKER] Fetching submissions for {assignment_id}")
        subs = list(db.submissions.find({"assignment_id": assignment_id}))
        print(f"[WORKER] Found {len(subs)} submissions")
        
        # collect text for each submission
        texts = []
        rolls = []
        for s in subs:
            roll = s.get("roll_no", "")
            t = s.get("text", "")
            if not t:
                # fallback to re-extract from file if available locally or in GridFS
                pdf = s.get("files", [None])[0]
                if pdf and os.path.exists(pdf):
                    print(f"[WORKER] Re-extracting OCR for {roll}")
                    t = extract_text_from_pdf(pdf)
                else:
                    ids = s.get("gridfs_ids", [])
                    if ids:
                        try:
                            tmpfile = fetch_gridfs_file(ids[0])
                            print(f"[WORKER] Re-extracting OCR from GridFS for {roll}")
                            t = extract_text_from_pdf(tmpfile)
                        except Exception as err:
                            print(f"[WORKER] GridFS re-extract failed: {err}")
            if not t:
                # skip submissions without text
                print(f"[WORKER] Skipping {roll} - no text")
                continue
            texts.append(t)
            rolls.append(roll)

        print(f"[WORKER] Collected {len(texts)} submissions with text")
        if len(texts) < 2:
            raise Exception("Need at least 2 submissions with text for similarity.")

        # ensure imports work
        project_path = str(Path(__file__).parent.parent / "Project")
        if project_path not in sys.path:
            sys.path.insert(0, project_path)

        print(f"[WORKER] Importing modules")
        from Project import nlp_module, similarity_engine
        import pandas as _pd
        import numpy as _np

        # clean texts
        print(f"[WORKER] Cleaning texts")
        texts = [nlp_module.clean_text(t) for t in texts]

        # compute similarity matrix directly using roll labels
        print(f"[WORKER] Computing similarity matrix")
        df = similarity_engine.compute_similarity(texts, document_names=rolls)
        print(f"[WORKER] Similarity computed")

        rolls = list(rolls)
        roll_matrix = (df * 100).round(2)

        # average
        values = roll_matrix.values
        upper = values[_np.triu_indices(len(values), k=1)]
        avg = round(_np.mean(upper), 2) if len(upper) > 0 else 0
        # main_pipeline only needed for verdict
        print(f"[WORKER] Computing verdict (avg={avg})")
        from Project import main_pipeline
        verdict = main_pipeline.get_verdict(avg)
        print(f"[WORKER] Verdict: {verdict}")

        # flagged pairs
        flagged = _pd.DataFrame(
            [
                {"Roll1": r1, "Roll2": r2, "Similarity": roll_matrix.loc[r1, r2]}
                for r1 in rolls for r2 in rolls
                if r1 < r2 and roll_matrix.loc[r1, r2] >= 60
            ]
        )
        print(f"[WORKER] Flagged {len(flagged)} pairs")

        # store results
        print(f"[WORKER] Storing results in DB")
        db.results.insert_one({
            "assignment_id": assignment_id,
            "created_at": datetime.now(timezone.utc),
            "average_similarity": float(avg),
            "verdict": verdict,
            "matrix": roll_matrix.to_dict(),
            "flagged": flagged.to_dict(orient="records"),
        })

        # update assignment status
        print(f"[WORKER] Updating assignment status to done")
        db.assignments.update_one({"assignment_id": assignment_id}, {"$set": {"processing_status": "done", "status": "analyzed", "analyzed_at": datetime.now(timezone.utc)}})

        # send final email to teacher if available
        print(f"[WORKER] Fetching teacher email")
        assignment = db.assignments.find_one({"assignment_id": assignment_id})
        teacher_email = assignment.get("teacher_email") if assignment else None
        if teacher_email:
            try:
                print(f"[WORKER] Sending final email to {teacher_email}")
                send_analysis_email(assignment_id, teacher_email, roll_matrix, avg, verdict, flagged)
                print(f"[WORKER] Final email sent successfully")
            except Exception as email_err:
                print(f"[WORKER] Email send failed: {email_err}")
        else:
            print(f"[WORKER] No teacher email found")
        
        print(f"[WORKER] Analysis complete for {assignment_id}")

    except Exception as e:
        # mark failed and store full traceback
        print(f"[WORKER] Exception occurred: {e}")
        tb = traceback.format_exc()
        print(tb)
        try:
            db.assignments.update_one({"assignment_id": assignment_id}, {"$set": {"processing_status": "failed", "error": tb}})
            print(f"[WORKER] Error recorded in DB")
        except Exception as db_err:
            print(f"[WORKER] Could not update DB with error: {db_err}")

# -------------------------
# Navbar with logo text and role buttons
# -------------------------
# columns structure; slightly larger left area for logo to avoid wrapping
nav_cols = st.columns([2, 5, 3])

# title text (clickable button) for logo area
with nav_cols[0]:
    # Button to return home without opening new tab
    if st.button("Assignment Similarity Detection", key="home_btn", use_container_width=True):
        navigate("Home")

# middle spacer (nav_cols[1]) stays empty

# role buttons (right)
with nav_cols[2]:
    btn_cols = st.columns(2)
    with btn_cols[0]:
        if st.button("Student"):
            navigate("Student")
    with btn_cols[1]:
        if st.button("Teacher"):
            navigate("Moderator")

# -------------------------
# Pages
# -------------------------

db = None
try:
    db = get_db()
    ensure_indexes(db)
except Exception:
    db = None

# HOME
if st.session_state.page == "Home":
    # header display moved into navbar; no duplicate title/description here

    # show currently active assignments if db available
    if db is not None:
        active = list(db.assignments.find({"active": True}))
        st.markdown("<h2>Currently Active Assignments</h2>", unsafe_allow_html=True)
        if not active:
            st.write("<p style='text-align:center;'>No Active Assignments</p>", unsafe_allow_html=True)
        else:
            # header row
            hdr_cols = st.columns([2, 2, 1, 1])
            with hdr_cols[0]:
                st.markdown("**Assignment**")
            with hdr_cols[1]:
                st.markdown("**Teacher**")
            with hdr_cols[2]:
                st.markdown("**Submissions**")
            with hdr_cols[3]:
                st.markdown("**Question**")
            # custom display to include question paper link/button
            for a in active:
                cols = st.columns([2, 2, 1, 1])
                with cols[0]:
                    st.write(f"**{a['assignment_id']}**")
                    st.caption(a.get("title", ""))
                with cols[1]:
                    st.write(a.get("teacher_name", a.get("teacher_email", "")))
                with cols[2]:
                    st.write(db.submissions.count_documents({"assignment_id": a["assignment_id"]}))
                with cols[3]:
                    # always serve question paper from GridFS, local copy is optional
                    qp_id = a.get("question_gridfs_id")
                    if qp_id:
                        try:
                            data = get_gridfs().get(ObjectId(qp_id)).read()
                            st.download_button(label="Download Question", data=data, file_name=f"{a['assignment_id']}_question")
                        except Exception as e:
                            st.write(f"Error retrieving question paper: {e}")
                    else:
                        st.write("—")


# STUDENT
elif st.session_state.page == "Student":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Submit Assignment")

    with st.form("student_submit", clear_on_submit=True):
        assignment_id = st.text_input("Assignment ID", placeholder="e.g. ASG-001")
        roll_no = st.text_input("Roll No / Student ID", placeholder="10-digit roll number")
        upload = st.file_uploader("Select one PDF", type=["pdf"], accept_multiple_files=False)
        submitted = st.form_submit_button("Submit Assignment")

    if submitted:
        # basic presence
        if not assignment_id or not roll_no or not upload:
            st.error("Please provide Assignment ID, Roll No and a PDF file.")
        else:
            # roll number validation
            if len(roll_no.strip()) != 10:
                st.error("Roll number must be exactly 10 characters long.")
            elif db is None:
                st.error("Database not available. Check MongoDB connection.")
            else:
                # check assignment exists and is active
                assignment = db.assignments.find_one({"assignment_id": assignment_id, "active": True})
                if not assignment:
                    st.error("Assignment ID not found or no longer accepting submissions.")
                else:
                    # ensure unique roll number for this assignment
                    existing = db.submissions.find_one({"assignment_id": assignment_id, "roll_no": roll_no})
                    if existing:
                        st.error("A submission for this roll number already exists for the assignment.")
                    else:
                        saved_paths = []
                        grid_ids = []
                        f = upload
                        # Streamlit already restricts types, but verify extension for safety
                        if not f.name.lower().endswith(".pdf"):
                            st.error(f"File {f.name} is not a PDF.")
                        else:
                            try:
                                path, gf = save_file(f, assignment_id, roll_no)
                                saved_paths.append(path)
                                grid_ids.append(gf)
                            except Exception as e:
                                st.error(f"Failed to save {f.name}: {e}")
                        if not saved_paths:
                            st.error("No valid PDF file to submit.")
                        else:
                            # perform OCR now and save text to DB. Retry/backoff is handled in helper.
                            text_content = ""
                            ocr_error = None
                            with st.spinner("Performing OCR on uploaded file..."):
                                try:
                                    text_content = extract_text_from_pdf(saved_paths[0])
                                    # optional NLP cleaning
                                    project_path = str(Path(__file__).parent.parent / "Project")
                                    if project_path not in sys.path:
                                        sys.path.insert(0, project_path)
                                    from Project import nlp_module
                                    text_content = nlp_module.clean_text(text_content)
                                except Exception as ocre:
                                    ocr_error = str(ocre)
                                    print(f"OCR on upload failed: {ocr_error}")
                                    st.warning("OCR failed for the uploaded PDF. Submission will be saved but OCR text is unavailable. You can retry OCR from the moderator dashboard or re-upload the file.")

                            submission = {
                                "assignment_id": assignment_id,
                                "roll_no": roll_no,
                                "files": saved_paths,
                                "gridfs_ids": grid_ids,
                                "text": text_content,
                                "created_at": datetime.now(timezone.utc),
                                "status": "ocr_failed" if ocr_error else "submitted",
                            }
                            if ocr_error:
                                submission["ocr_error"] = ocr_error
                            try:
                                db.submissions.insert_one(submission)
                                st.success("Assignment Submitted Successfully!")
                            except Exception as e:
                                st.error(f"DB error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


# MODERATOR
elif st.session_state.page == "Moderator":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Teacher Access")

    key = st.text_input("Moderator Key", placeholder="Enter Key", type="password", key="moderator_key")

    def authenticate_moderator():
        if st.session_state.moderator_key == "admin123":
            st.session_state.page = "ServerModerator"
        else:
            st.error("Invalid Key")

    st.button("Authenticate", on_click=authenticate_moderator)

    st.markdown("</div>", unsafe_allow_html=True)

# SERVER MODERATOR
elif st.session_state.page == "ServerModerator":
    st.header("Teacher / Admin Dashboard")
    st.write("Use the tabs below to create assignments, manage the system, or view results.")

    if db is None:
        st.error("Database not available. Check MongoDB connection.")
    else:
        tab_assign, tab_admin, tab_results = st.tabs(["Assignments", "Admin", "Results"])

        with tab_assign:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.subheader("New Assignment")
            with st.form("create_assignment", clear_on_submit=True):
                asg_id = st.text_input("Assignment ID", placeholder="e.g. ASG-001")
                title = st.text_input("Title", placeholder="e.g. Data Structures Report")
                desc = st.text_area("Description (optional)")
                teacher_name = st.text_input("Your Name/ID", placeholder="e.g. Prof123 or John Doe")
                teacher_email = st.text_input("Your Email (to receive results)")
                question = st.file_uploader("Question Paper (optional)", type=["pdf","png","jpg"], accept_multiple_files=False)
                ok = st.form_submit_button("Create Assignment")

            if ok:
                if not asg_id or not title:
                    st.error("Assignment ID and Title required.")
                else:
                    if db is None:
                        st.error("Database not available. Check MongoDB connection.")
                    else:
                        doc = {
                            "assignment_id": asg_id,
                            "title": title,
                            "description": desc,
                            "teacher_name": teacher_name,
                            "teacher_email": teacher_email,
                            "created_at": datetime.now(timezone.utc),
                            "active": True,
                        }
                        # save question paper if provided
                        if question:
                            try:
                                qp_path, qp_id = save_file(question, asg_id, "question")
                                doc["question_path"] = qp_path
                                doc["question_gridfs_id"] = qp_id
                            except Exception as e:
                                st.error(f"Failed to save question paper: {e}")
                        try:
                            db.assignments.insert_one(doc)
                            st.success("Assignment Created Successfully!")
                        except pymongo.errors.DuplicateKeyError:
                            st.error("This Assignment ID already exists. Please use a different ID.")
                        except Exception as e:
                            st.error(f"DB error: {e}")
            st.markdown("</div>", unsafe_allow_html=True)

        with tab_admin:
            # existing admin code follows (indented)
            assignments = list(db.assignments.find())
            if not assignments:
                st.info("No assignments created yet.")
            else:
                # Table header
                header_cols = st.columns([2.5, 1.5, 1, 2.5])
                with header_cols[0]:
                    st.subheader("Assignment")
                with header_cols[1]:
                    st.subheader("Status")
                with header_cols[2]:
                    st.subheader("Submissions")
                with header_cols[3]:
                    st.subheader("Actions")

                st.divider()

                # Table rows
                for a in assignments:
                    row_cols = st.columns([2.5, 1.5, 1, 2.5])

                    # Assignment ID + Title
                    with row_cols[0]:
                        st.write(f"**{a.get('assignment_id', '')}**")
                        st.caption(a.get('title', ''))

                    # Status (Active/Locked)
                    with row_cols[1]:
                        status_text = "🟢 Active" if a.get("active", False) else "🔒 Locked"
                        st.write(status_text)

                    # Submissions count
                    sub_count = db.submissions.count_documents({"assignment_id": a["assignment_id"]})
                    with row_cols[2]:
                        st.write(f"{sub_count}")

                    # Actions
                    with row_cols[3]:
                        action_cols = st.columns([1, 1, 1, 1], gap="small")

                        # View button
                        with action_cols[0]:
                            if st.button("View", key=f"view_{a['_id']}"):
                                st.session_state._view_assignment = a["assignment_id"]

                        # Lock/Unlock button
                        with action_cols[1]:
                            lock_label = "Lock" if a.get("active", False) else "Unlock"
                            if st.button(lock_label, key=f"lock_{a['_id']}"):
                                new_status = not a.get("active", False)
                                db.assignments.update_one(
                                    {"assignment_id": a["assignment_id"]},
                                    {"$set": {"active": new_status}}
                                )
                                st.rerun()

                        # Analyze button
                        with action_cols[2]:
                            if st.button("Analyze", key=f"analyze_{a['_id']}"):
                                # Lock assignment and queue processing
                                try:
                                    db.assignments.update_one({"assignment_id": a["assignment_id"]}, {"$set": {"active": False, "processing_status": "queued"}})
                                    # send started email
                                    teacher_email = a.get("teacher_email")
                                    if teacher_email:
                                        try:
                                            send_started_email(a["assignment_id"], teacher_email)
                                        except Exception:
                                            pass

                                    # spawn background worker thread
                                    print(f"[MAIN] Spawning worker thread for {a['assignment_id']}")
                                    t = threading.Thread(target=process_assignment, args=(a["assignment_id"],), daemon=True)
                                    t.start()
                                    print(f"[MAIN] Worker thread started")

                                    st.session_state._analyze_assignment = a["assignment_id"]
                                    st.success("Analysis queued. Processing in background; teacher will be notified by email.")
                                    try_rerun()
                                except Exception as e:
                                    st.error(f"Failed to start analysis: {e}")

                        # Delete button
                        with action_cols[3]:
                            if st.button("Delete", key=f"delete_{a['_id']}"):
                                # Remove all submissions for this assignment
                                db.submissions.delete_many({"assignment_id": a["assignment_id"]})
                                # Remove the assignment
                                db.assignments.delete_one({"assignment_id": a["assignment_id"]})
                                # Remove results if any
                                db.results.delete_many({"assignment_id": a["assignment_id"]})
                                st.success(f"Assignment {a['assignment_id']} and its submissions deleted.")
                                try_rerun()

                    st.divider()

                    # View submissions if triggered
                    if st.session_state.get("_view_assignment") == a["assignment_id"]:
                        st.subheader(f"📋 Submissions for {a['assignment_id']}")
                        subs = list(db.submissions.find({"assignment_id": a["assignment_id"]}))
                        if not subs:
                            st.info("No submissions yet.")
                        else:
                            sub_data = [{"Roll No": s["roll_no"], "Submitted": s.get("created_at", "N/A"), "Status": s.get("status", "submitted")} for s in subs]
                            st.table(sub_data)
                        if st.button("Close", key=f"close_view_{a['_id']}"):
                            st.session_state._view_assignment = None
                            try_rerun()

                    # Analyze if triggered (show status from DB; actual processing runs in background)
                    if st.session_state.get("_analyze_assignment") == a["assignment_id"]:
                        st.subheader(f"📊 Analysis for {a['assignment_id']}")
                        try:
                            # refresh assignment from DB to read processing_status
                            fresh = db.assignments.find_one({"assignment_id": a["assignment_id"]}) or {}
                            status = fresh.get("processing_status", "idle")
                            if status in ("queued", "running"):
                                st.info(f"Processing status: {status}. Analysis is running in background.")
                            elif status == "done":
                                # show stored results
                                res = db.results.find_one({"assignment_id": a["assignment_id"]}, sort=[("created_at", -1)])
                                if not res:
                                    st.info("Analysis completed but no results found.")
                                else:
                                    import pandas as _pd
                                    roll_matrix = _pd.DataFrame(res["matrix"])
                                    st.write("**Roll-level Similarity (%)**")
                                    st.dataframe(roll_matrix, use_container_width=True)
                                    st.metric("Average Similarity", f"{res.get('average_similarity',0)}%")
                                    st.metric("Verdict", res.get("verdict", "N/A"))
                                    flagged = res.get("flagged", [])
                                    if flagged:
                                        st.write("**Flagged Pairs (>=60%)**")
                                        st.table(flagged)
                            elif status == "failed":
                                st.error(f"Processing failed: {fresh.get('error')}")
                            else:
                                st.info("Analysis queued. Click Close to return.")
                        except Exception as e:
                            st.error(f"Could not read analysis status: {e}")

                        if st.button("Close Analysis", key=f"close_analyze_{a['_id']}"):
                            st.session_state._analyze_assignment = None
                            try_rerun()

        with tab_results:
            st.subheader("Analysis Results")
            results = list(db.results.find().sort("created_at", -1))
            if not results:
                st.info("No results yet.")
            else:
                import pandas as _pd
                for res in results:
                    with st.expander(f"{res['assignment_id']} - {res.get('verdict', 'N/A')} ({res.get('average_similarity',0)}%)"):
                        mat = _pd.DataFrame(res['matrix'])
                        st.write("**Similarity Matrix (%)**")
                        st.dataframe(mat)
                        flagged = res.get('flagged', [])
                        if flagged:
                            st.write("**Flagged Pairs**")
                            st.table(flagged)

        st.divider()
        if st.button("Logout", key="logout_btn"):
            st.session_state.page = "Home"
            try_rerun()