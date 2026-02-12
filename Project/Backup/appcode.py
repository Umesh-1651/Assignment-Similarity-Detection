import streamlit as st

st.set_page_config(page_title="Evalora", page_icon="📘", layout="wide")

# Custom CSS for styling
st.markdown("""
    <style>
    .main-title {
        font-size: 50px;
        font-weight: bold;
        text-align: center;
        margin-top: 20px;
    }
    .subtitle {
        text-align: center;
        font-size: 20px;
        color: gray;
        margin-bottom: 50px;
    }
    .card {
        background-color: #f5f7fa;
        padding: 40px;
        border-radius: 20px;
        text-align: center;
        transition: 0.3s;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .card:hover {
        transform: scale(1.05);
        box-shadow: 0 8px 25px rgba(0,0,0,0.2);
    }
    .btn {
        background-color: #4CAF50;
        color: white;
        padding: 10px 25px;
        border-radius: 10px;
        font-size: 16px;
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

# Title Section
st.markdown('<div class="main-title">📘 Evalora</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Smart Assignment Evaluation Platform</div>', unsafe_allow_html=True)

# Two Columns
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
        <div class="card">
            <h2>🧑‍🎓 Submit Assignment</h2>
            <p>Upload your assignment and get evaluated instantly.</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Enter as Student"):
        st.success("Student Portal Coming Soon 🚀")

with col2:
    st.markdown("""
        <div class="card">
            <h2>👨‍🏫 Create Assignment</h2>
            <p>Create assignments and evaluate student responses easily.</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Enter as Teacher"):
        st.success("Teacher Portal Coming Soon 🚀")