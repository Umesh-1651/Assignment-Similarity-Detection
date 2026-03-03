import streamlit as st
from datetime import datetime
from pathlib import Path
import os
import pymongo
import traceback

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
# reset parameter from query string returns to Home
params = st.experimental_get_query_params() if hasattr(st, 'experimental_get_query_params') else st.query_params

if "page" not in st.session_state:
    st.session_state.page = "Home"

if params.get("reset"):
    st.session_state.page = "Home"


def navigate(page):
    st.session_state.page = page

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


def save_file(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile, assignment_id: str, roll_no: str):
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_name = f"{assignment_id}_{roll_no}_{ts}_{uploaded_file.name}"
    dest = UPLOAD_DIR / safe_name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(dest)

# -------------------------
# Navbar with logo text and role buttons
# -------------------------
# columns structure; small left for logo, spacer, right for role buttons
nav_cols = st.columns([1, 6, 3])

# title text (clickable) for logo area
with nav_cols[0]:
    # anchor sends query param to reset page
    st.markdown(
        "<a href='?reset=1' class='nav-title' style='white-space:nowrap;'>Assignment Similarity Detection</a>",
        unsafe_allow_html=True,
    )

# middle spacer (nav_cols[1]) stays empty

# role buttons (right)
with nav_cols[2]:
    btn_cols = st.columns(3)
    with btn_cols[0]:
        if st.button("Student"):
            navigate("Student")
    with btn_cols[1]:
        if st.button("Teacher"):
            navigate("Teacher")
    with btn_cols[2]:
        if st.button("Moderator"):
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
            rows = []
            for a in active:
                rows.append({
                    "ID": a["assignment_id"],
                    "Title": a.get("title", ""),
                    "Teacher": a.get("teacher_name", a.get("teacher_email", "")),
                    "Submissions": db.submissions.count_documents({"assignment_id": a["assignment_id"]}),
                })
            st.table(rows)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("🎓 Student")
        st.write("Submit your assignment (images or PDF)")
        if st.button("Enter as Student"):
            navigate("Student")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("👩‍🏫 Teacher")
        st.write("Create assignments & check similarity")
        if st.button("Enter as Teacher"):
            navigate("Teacher")
        st.markdown("</div>", unsafe_allow_html=True)

# STUDENT
elif st.session_state.page == "Student":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Submit Assignment")

    with st.form("student_submit", clear_on_submit=True):
        assignment_id = st.text_input("Assignment ID", placeholder="e.g. ASG-001")
        roll_no = st.text_input("Roll No / Student ID", placeholder="10-digit roll number")
        uploads = st.file_uploader("Select files (PDF only)", type=["pdf"], accept_multiple_files=True)
        submitted = st.form_submit_button("Submit Assignment")

    if submitted:
        # basic presence
        if not assignment_id or not roll_no or not uploads:
            st.error("Please provide Assignment ID, Roll No and at least one file.")
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
                        for f in uploads:
                            # Streamlit already restricts types, but verify extension for safety
                            if not f.name.lower().endswith(".pdf"):
                                st.error(f"File {f.name} is not a PDF.")
                                continue
                            try:
                                path = save_file(f, assignment_id, roll_no)
                                saved_paths.append(path)
                            except Exception as e:
                                st.error(f"Failed to save {f.name}: {e}")
                        if not saved_paths:
                            st.error("No valid PDF files to submit.")
                        else:
                            submission = {
                                "assignment_id": assignment_id,
                                "roll_no": roll_no,
                                "files": saved_paths,
                                "created_at": datetime.utcnow(),
                                "status": "submitted"
                            }
                            try:
                                db.submissions.insert_one(submission)
                                st.success("Assignment Submitted Successfully!")
                            except Exception as e:
                                st.error(f"DB error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

# TEACHER
elif st.session_state.page == "Teacher":
    st.header("Teacher Dashboard")

    tab1, tab2 = st.tabs(["Create Assignment", "Active Assignments"])

    with tab1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("New Assignment")
        with st.form("create_assignment", clear_on_submit=True):
            asg_id = st.text_input("Assignment ID", placeholder="e.g. ASG-001")
            title = st.text_input("Title", placeholder="e.g. Data Structures Report")
            desc = st.text_area("Description (optional)")
            teacher_name = st.text_input("Your Name/ID", placeholder="e.g. Prof123 or John Doe")
            teacher_email = st.text_input("Your Email (to receive results)")
            ok = st.form_submit_button("Create Assignment")

        if ok:
            if not asg_id or not title:
                st.error("Assignment ID and Title required.")
            else:
                if db is None:
                    st.error("Database not available. Check MongoDB connection.")
                else:
                    try:
                        db.assignments.insert_one({
                            "assignment_id": asg_id,
                            "title": title,
                            "description": desc,
                            "teacher_name": teacher_name,
                            "teacher_email": teacher_email,
                            "created_at": datetime.utcnow(),
                            "active": True,
                        })
                        st.success("Assignment Created Successfully!")
                    except pymongo.errors.DuplicateKeyError:
                        st.error("This Assignment ID already exists. Please use a different ID.")
                    except Exception as e:
                        st.error(f"DB error: {e}")

        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.subheader("Currently Active Assignments")
        if db is None:
            st.error("Database not available. Check MongoDB connection.")
        else:
            assignments = list(db.assignments.find({"active": True}))
            if not assignments:
                st.info("No active assignments yet.")
            else:
                rows = []
                for a in assignments:
                    count = db.submissions.count_documents({"assignment_id": a["assignment_id"]})
                    rows.append({
                        "ID": a["assignment_id"],
                        "Title": a.get("title", ""),
                        "Teacher": a.get("teacher_name", a.get("teacher_email", "")),
                        "Created": a.get("created_at", ""),
                        "Submissions": count,
                    })
                st.table(rows)

# MODERATOR
elif st.session_state.page == "Moderator":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Moderator Access")

    key = st.text_input("Moderator Key", placeholder="Enter Key", type="password")

    if st.button("Authenticate"):
        if key == "admin123":
            st.session_state.page = "ServerModerator"
        else:
            st.error("Invalid Key")

    st.markdown("</div>", unsafe_allow_html=True)

# SERVER MODERATOR
elif st.session_state.page == "ServerModerator":
    st.header("Server Moderator Dashboard")
    st.write("Manage assignments and submissions")

    if db is None:
        st.error("Database not available. Check MongoDB connection.")
    else:
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
                            st.session_state._analyze_assignment = a["assignment_id"]

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
                            st.rerun()

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
                        st.rerun()

                # Analyze if triggered
                if st.session_state.get("_analyze_assignment") == a["assignment_id"]:
                    st.subheader(f"📊 Analysis for {a['assignment_id']}")
                    try:
                        subs = list(db.submissions.find({"assignment_id": a["assignment_id"]}))
                        file_paths = []
                        for s in subs:
                            file_paths.extend(s.get("files", []))

                        if len(file_paths) < 2:
                            st.warning("Need at least 2 submissions/files to analyze similarity.")
                        else:
                            from Project import main_pipeline

                            with st.spinner("Running analysis..."):
                                df = main_pipeline.run_pipeline(file_paths)
                                percentage_matrix = (df * 100).round(2)
                                st.write("**Similarity Matrix (%)**")
                                st.dataframe(percentage_matrix, use_container_width=True)

                                # compute average
                                import numpy as _np
                                values = (percentage_matrix.values)
                                upper = values[_np.triu_indices(len(values), k=1)]
                                avg = round(_np.mean(upper), 2) if len(upper) > 0 else 0
                                verdict = main_pipeline.get_verdict(avg)

                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("Average Similarity", f"{avg}%")
                                with col2:
                                    st.metric("Verdict", verdict)

                                # store results
                                db.results.insert_one({
                                    "assignment_id": a["assignment_id"],
                                    "created_at": datetime.utcnow(),
                                    "average_similarity": float(avg),
                                    "verdict": verdict,
                                    "matrix": percentage_matrix.to_dict(),
                                })
                                # notify teacher
                                teacher_email = a.get("teacher_email")
                                if teacher_email:
                                    st.info(f"✓ Results recorded. Teacher {teacher_email} can be notified via email.")
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")

                    if st.button("Close Analysis", key=f"close_analyze_{a['_id']}"):
                        st.session_state._analyze_assignment = None
                        st.rerun()

        st.divider()
        if st.button("Logout", key="logout_btn"):
            st.session_state.page = "Home"
            st.rerun()