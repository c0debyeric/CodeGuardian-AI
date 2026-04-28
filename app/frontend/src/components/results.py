"""Results display components for the Streamlit UI."""

import streamlit as st


def severity_color(severity: str) -> str:
    """Get color code for severity level."""
    colors = {
        "CRITICAL": "#dc3545",
        "HIGH": "#fd7e14",
        "MEDIUM": "#ffc107",
        "LOW": "#28a745",
        "INFO": "#17a2b8",
    }
    return colors.get(severity.upper(), "#6c757d")


def render_finding_card(finding: dict, language: str = "python") -> None:
    """Render a single finding as a card."""
    severity = finding.get("severity", "MEDIUM")
    color = severity_color(severity)
    
    st.markdown(
        f"""
        <div style="border-left: 4px solid {color}; padding-left: 16px; margin-bottom: 16px;">
            <h4 style="margin: 0; color: {color};">{severity}: {finding.get('title', 'Security Issue')}</h4>
            <p style="color: #666; margin: 4px 0;">Line {finding.get('line_start', '?')} | {finding.get('vulnerability_type', 'Unknown')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown(finding.get("description", "No description"))
    
    if finding.get("recommendation"):
        st.info(f"💡 **Recommendation:** {finding.get('recommendation')}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if finding.get("code_snippet"):
            st.markdown("**Vulnerable Code:**")
            st.code(finding["code_snippet"], language=language)
    
    with col2:
        if finding.get("fix_example"):
            st.markdown("**Fixed Code:**")
            st.code(finding["fix_example"], language=language)


def render_summary(summary: dict) -> None:
    """Render the analysis summary."""
    cols = st.columns(5)
    
    metrics = [
        ("🔴 Critical", summary.get("critical", 0), "#dc3545"),
        ("🟠 High", summary.get("high", 0), "#fd7e14"),
        ("🟡 Medium", summary.get("medium", 0), "#ffc107"),
        ("🟢 Low", summary.get("low", 0), "#28a745"),
        ("🔵 Info", summary.get("info", 0), "#17a2b8"),
    ]
    
    for col, (label, value, color) in zip(cols, metrics):
        with col:
            st.metric(label, value)
