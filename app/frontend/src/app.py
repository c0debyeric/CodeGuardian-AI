"""Streamlit frontend for CodeGuardian AI."""

import os

import httpx
import streamlit as st

# Configuration
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# Page configuration
st.set_page_config(
    page_title="CodeGuardian AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for severity colors
st.markdown(
    """
    <style>
    .severity-critical {
        background-color: #dc3545;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .severity-high {
        background-color: #fd7e14;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .severity-medium {
        background-color: #ffc107;
        color: black;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .severity-low {
        background-color: #28a745;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .severity-info {
        background-color: #17a2b8;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .finding-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        background-color: #f8f9fa;
    }
    .summary-box {
        text-align: center;
        padding: 10px;
        border-radius: 8px;
        margin: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_severity_badge(severity: str) -> str:
    """Get HTML badge for severity level."""
    severity_lower = severity.lower()
    return f'<span class="severity-{severity_lower}">{severity}</span>'


def analyze_code(code: str, language: str) -> dict | None:
    """Send code to backend for analysis."""
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{BACKEND_URL}/analyze",
                json={"code": code, "language": language},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API Error: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        st.error(f"Connection Error: Could not reach the backend at {BACKEND_URL}")
        return None


def check_backend_health() -> bool:
    """Check if backend is healthy."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{BACKEND_URL}/health")
            return response.status_code == 200
    except Exception:
        return False


# Main UI
st.title("🛡️ CodeGuardian AI")
st.markdown("*AI-powered security code reviewer that catches vulnerabilities before deployment*")

# Backend status indicator
col1, col2 = st.columns([3, 1])
with col2:
    if check_backend_health():
        st.success("✅ Backend Connected")
    else:
        st.error("❌ Backend Offline")

st.divider()

# Input section
col_input, col_options = st.columns([3, 1])

with col_options:
    st.subheader("Options")
    language = st.selectbox(
        "Language",
        options=["auto", "python", "javascript", "terraform"],
        index=0,
        help="Select the programming language or let it auto-detect",
    )

with col_input:
    st.subheader("Paste your code")
    code = st.text_area(
        "Code",
        height=300,
        placeholder="Paste your Python, JavaScript, or Terraform code here...",
        label_visibility="collapsed",
    )

# Analyze button
analyze_button = st.button("🔍 Analyze Code", type="primary", use_container_width=True)

# Results section
if analyze_button:
    if not code.strip():
        st.warning("Please paste some code to analyze.")
    else:
        with st.spinner("Analyzing code for security vulnerabilities..."):
            result = analyze_code(code, language)

        if result:
            st.divider()
            st.subheader("📊 Analysis Results")

            # Summary boxes
            summary = result.get("summary", {})
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("Critical", summary.get("critical", 0), delta=None)
            with col2:
                st.metric("High", summary.get("high", 0), delta=None)
            with col3:
                st.metric("Medium", summary.get("medium", 0), delta=None)
            with col4:
                st.metric("Low", summary.get("low", 0), delta=None)
            with col5:
                st.metric("Info", summary.get("info", 0), delta=None)

            # Metadata
            metadata = result.get("metadata", {})
            st.caption(
                f"📝 Language: {metadata.get('language_detected', 'unknown')} | "
                f"📄 Lines: {metadata.get('lines_analyzed', 0)} | "
                f"⏱️ Time: {metadata.get('scan_time_ms', 0)}ms"
            )

            st.divider()

            # Findings
            findings = result.get("findings", [])
            if not findings:
                st.success("✅ No security vulnerabilities found!")
            else:
                st.subheader(f"🔍 {len(findings)} Finding(s)")

                for i, finding in enumerate(findings):
                    severity = finding.get("severity", "MEDIUM")
                    title = finding.get("title", "Security Issue")

                    # Create expandable section for each finding
                    with st.expander(
                        f"{get_severity_badge(severity)} **{title}** (Line {finding.get('line_start', '?')})",
                        expanded=(severity in ["CRITICAL", "HIGH"]),
                    ):
                        # Details in columns
                        col_a, col_b = st.columns(2)

                        with col_a:
                            st.markdown(f"**Type:** {finding.get('vulnerability_type', 'Unknown')}")
                            if finding.get("cwe_id"):
                                st.markdown(f"**CWE:** {finding.get('cwe_id')}")
                            if finding.get("owasp_category"):
                                st.markdown(f"**OWASP:** {finding.get('owasp_category')}")

                        with col_b:
                            st.markdown(f"**Lines:** {finding.get('line_start', '?')} - {finding.get('line_end', '?')}")

                        st.markdown("---")
                        st.markdown(f"**Description:**\n{finding.get('description', 'No description')}")

                        st.markdown(f"**Recommendation:**\n{finding.get('recommendation', 'No recommendation')}")

                        if finding.get("code_snippet"):
                            st.markdown("**Vulnerable Code:**")
                            st.code(finding.get("code_snippet"), language=metadata.get("language_detected", "python"))

                        if finding.get("fix_example"):
                            st.markdown("**Fix Example:**")
                            st.code(finding.get("fix_example"), language=metadata.get("language_detected", "python"))

# Footer
st.divider()
st.caption("CodeGuardian AI - Powered by AWS Bedrock Claude")
