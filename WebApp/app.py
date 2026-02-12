import streamlit as st

st.set_page_config(page_title="ASD - Assignment Similarity Detection", layout="wide")

# Load Custom CSS
def load_css():
    with open("styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# -------------------------
# Navigation State
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "Home"

def navigate(page):
    st.session_state.page = page

# -------------------------
# Navbar
# -------------------------
st.markdown("""
<div class="navbar">
    <div class="nav-title">Assignment Similarity Detection</div>
    <div class="nav-menu">
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1,1,1])

with col1:
    if st.button("Student"):
        navigate("Student")

with col2:
    if st.button("Teacher"):
        navigate("Teacher")

with col3:
    if st.button("Moderator"):
        navigate("Moderator")

st.markdown("</div></div>", unsafe_allow_html=True)

st.write("")

# -------------------------
# Pages
# -------------------------

# HOME PAGE
if st.session_state.page == "Home":
    st.markdown("<h1 style='text-align:center;'>Assignment Similarity Detection</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Upload, compare, and detect similarities in student assignments</p>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("🎓 Student")
        st.write("Submit your assignment PDF")
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

# -------------------------
# STUDENT PAGE
# -------------------------
elif st.session_state.page == "Student":

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Submit Assignment")

    assignment_id = st.text_input("Assignment ID", placeholder="e.g. ASG-001")
    student_id = st.text_input("Student ID", placeholder="e.g. STU-2024-001")
    pdf = st.file_uploader("Upload Assignment PDF", type=["pdf"])

    if st.button("Submit Assignment"):
        st.success("Assignment Submitted Successfully!")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# TEACHER PAGE
# -------------------------
elif st.session_state.page == "Teacher":

    st.header("Teacher Dashboard")

    tab1, tab2 = st.tabs(["Create Assignment", "View Assignments"])

    with tab1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("New Assignment")

        asg_id = st.text_input("Assignment ID", placeholder="e.g. ASG-001")
        title = st.text_input("Title", placeholder="e.g. Data Structures Report")
        desc = st.text_area("Description (optional)")

        if st.button("Create Assignment"):
            st.success("Assignment Created Successfully!")

        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.write("All Assignments")
        st.table({
            "ID": ["SriMathreNamaha999"],
            "Title": ["Namah Shivaya"],
            "Created": ["2/11/2026"],
            "Submissions": [0]
        })

# -------------------------
# MODERATOR PAGE
# -------------------------
elif st.session_state.page == "Moderator":

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Moderator Access")

    key = st.text_input("Moderator Key",placeholder="Enter Key", type="password")

    if st.button("Authenticate"):
        if key == "admin123":
            st.session_state.page = "ServerModerator"
        else:
            st.error("Invalid Key")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# SERVER MODERATOR PAGE
# -------------------------
elif st.session_state.page == "ServerModerator":

    st.header("Server Moderator")
    st.write("Manage all assignments and submissions")

    st.table({
        "ID": ["ASG01"],
        "Title": ["Example"],
        "Created": [""],
        "Submissions": [22]
    })

    if st.button("Logout"):
        st.session_state.page = "Home"