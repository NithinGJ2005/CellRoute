import streamlit as st
import os

# Set page config for a premium look
st.set_page_config(
    page_title="CellRoute | Intelligent Connectivity",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for aesthetics
st.markdown("""
    <style>
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stMarkdown h1, h2, h3 {
        color: #0ea5e9 !important;
    }
    .metric-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(14, 165, 233, 0.2);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Sidebar with Branding
with st.sidebar:
    st.image("L4_FRONTEND/assets/logo.png", width=100)
    st.title("CellRoute")
    st.markdown("---")
    st.success("📡 System Active")
    st.info("L4 Autonomy Capable")

# Main Content
st.title("📡 CellRoute: Intelligent Connectivity Routing")
st.subheader("MAHE-Harman AI in Mobility Challenge 2026")

st.markdown("""
CellRoute is a **cellular-aware multi-objective routing engine** that optimizes vehicle trajectories based on real-time 5G/4G network intelligence.
""")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(label="Scoring Features", value="16")
    st.write("Multi-objective heuristic including Signal Quality, Throughput, and Monsoon Penalty.")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(label="Data Layers", value="4")
    st.write("OpenCellID, Ookla Open Data, OpenStreetMap, and OpenTrafficData integration.")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(label="Assurance", value="Closed-Loop")
    st.write("Autonomous recovery and self-healing routing for simulated network outages.")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

st.header("🚀 Submission Overview")
st.write("The complete CellRoute platform includes a FastAPI-powered routing engine and a high-fidelity L4 Autonomy Dashboard.")

st.info("💡 **Evaluator Note:** To experience the full interactive L4 Dashboard with the real-time Bangalore road network graph, please follow the local execution steps in the README.md. The dashboard is served via FastAPI for maximum performance.")

# Display Project Documentation
if os.path.exists("README.md"):
    with st.expander("📄 View Project Documentation", expanded=True):
        with open("README.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())

st.markdown("---")
st.markdown("Built with ❤️ by the CellRoute Team")
