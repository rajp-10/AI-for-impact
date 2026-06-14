import streamlit as st
from ai_engine import analyze_job_posting
from pdf_generator import generate_pdf

# Configure Page Layout to look professional
st.set_page_config(page_title="ShieldAI | Recruitment Fraud Detector", layout="wide")

st.title("Job Posting Scam Detector")
st.caption("Multi-step threat intelligence engine for student internship protection.")

# Create Two Pillars/Columns for Layout Structure
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input Job Details")
    company = st.text_input("Company Name / Recruiter Email Domain", placeholder="e.g. hr-booking@gmail.com")
    job_details = st.text_area("Paste Job Description or Email Message", placeholder="Paste the full text here...", height=300)
    
    analyze_btn = st.button("Run Security Audit", type="primary", use_container_width=True)

with col2:
    st.subheader(" Threat Analysis Report")
    
    if analyze_btn:
        if not company or not job_details:
            st.error("Please fill in both input fields to run the evaluation pipeline.")
        else:
            with st.spinner("Analyzing operational headers and linguistic threat metrics..."):
                # Run backend execution
                report = analyze_job_posting(company, job_details)
                
                if "error" in report:
                    st.error(report["error"])
                else:
                    # Render the Trust Score Card visually
                    score = report['risk_score']
                    level = report['risk_level']
                    
                    if level == "High":
                        st.error(f"🚨 RISK LEVEL: {level.upper()} ({score}% Match for Fraud)")
                    elif level == "Medium":
                        st.warning(f"⚠️ RISK LEVEL: {level.upper()} ({score}% Suspicious Indicators)")
                    else:
                        st.success(f"✅ RISK LEVEL: {level.upper()} ({score}% Risk - Appears Legitimate)")
                    
                    # Section 1: Summary
                    st.write(f"**Analysis Verdict:** {report['analysis_summary']}")
                    st.divider()
                    
                    # Section 2: Red Flags
                    st.markdown("### 🚩 Identified Red Flags")
                    for flag in report['red_flags']:
                        st.markdown(f"- {flag}")
                    st.divider()
                    
                    # Section 3: Next Steps
                    st.markdown("### 🛡️ Recommended Student Action Plan")
                    for step in report['safety_checklist']:
                        st.markdown(f"- [ ] {step}")

                    pdf_file = generate_pdf(company, report)

                    with open(pdf_file, "rb") as file:
                        st.download_button(
                            label="📄 Download Audit Report",
                            data=file,
                            file_name="ShieldAI_Report.pdf",
                            mime="application/pdf"
                        )

                    
    else:
        st.info("Input a job posting and run security audit to generate output metrics.")

