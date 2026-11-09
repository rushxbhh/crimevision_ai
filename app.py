import streamlit as st
from datetime import datetime, timezone
from pathlib import Path
import uuid

from core.config import get_settings
from core.security import get_api_key
from core.storage import init_state, add_evidence, all_evidence, add_event, all_events
from core.analysis import analyze_image, analyze_audio, analyze_video, answer_evidence_question
from core.reporting import build_pdf

st.set_page_config(page_title="CrimeVision AI", page_icon="🔎", layout="wide")
settings = get_settings()
init_state()

st.markdown("""
<style>
.stApp { background: #0b1018; color: #e7edf5; }
[data-testid="stSidebar"] { background: #101824; }
.block-container { padding-top: 1.5rem; max-width: 1500px; }
.cv-card { background:#121d2a; border:1px solid #26374a; border-radius:12px; padding:16px; margin:8px 0; }
.cv-muted { color:#9aabba; font-size:.88rem; }
.cv-title { letter-spacing:.04em; color:#dce8f5; }
div[data-testid="stMetric"] { background:#121d2a; border:1px solid #26374a; padding:12px; border-radius:10px; }
.stButton button { border-radius:8px; }
</style>
""", unsafe_allow_html=True)

st.title("CrimeVision AI")
st.caption("Intelligent Multimodal Forensic Analysis Platform · Skill Wallet Capstone Project 2")
st.warning("Research / training prototype. Automated outputs are investigative aids, not verified forensic findings or court-admissible conclusions. Preserve originals and obtain qualified human review.")

with st.sidebar:
    st.header("Case configuration")
    case_id = st.text_input("Case reference", value=st.session_state.get("case_id", "CASE-2026-001"))
    investigator = st.text_input("Investigator / reviewer", value=st.session_state.get("investigator", ""))
    signoff = st.checkbox("I confirm I reviewed the uploaded evidence metadata")
    st.session_state.case_id = case_id
    st.session_state.investigator = investigator
    st.session_state.signoff = signoff
    st.divider()
    st.subheader("AI provider")
    provider = st.selectbox("Provider", ["Demo fallback", "Groq", "Gemini"], index=0)
    api_key = get_api_key(provider)
    if provider != "Demo fallback":
        api_key = st.text_input("API key", type="password", help="Used only for this session. Prefer Streamlit secrets in deployments.")
    st.session_state.provider = provider
    st.session_state.api_key = api_key
    st.caption("No external database. Case state is held in Streamlit session memory.")
    if provider != "Demo fallback" and not api_key:
        st.info("No API key supplied: analyses will use clearly labelled demo fallback.")

def evidence_meta(kind, filename, content):
    evidence_id = f"EV-{uuid.uuid4().hex[:10].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()
    metadata = {
        "evidence_id": evidence_id, "kind": kind, "filename": filename,
        "timestamp": timestamp, "investigator": investigator or "Not specified",
        "signoff": bool(signoff), "case_id": case_id,
        "sha256": __import__("hashlib").sha256(content).hexdigest()
    }
    return metadata

tabs = st.tabs([
    "1 · Image evidence tagger", "2 · Witness audio", "3 · CCTV progression",
    "4 · Multimodal fusion & chat", "5 · PDF export"
])

with tabs[0]:
    st.subheader("Crime scene visual evidence tagger")
    image_file = st.file_uploader("Upload crime scene photograph", type=["png","jpg","jpeg","webp"], key="image")
    if image_file:
        st.image(image_file, caption=image_file.name, use_container_width=True)
        if st.button("Analyze image", type="primary"):
            raw = image_file.getvalue()
            meta = evidence_meta("image", image_file.name, raw)
            with st.spinner("Analyzing image evidence…"):
                result = analyze_image(raw, image_file.type, provider, api_key)
            add_evidence(meta, result)
            for event in result.get("events", []):
                add_event({**event, "evidence_id": meta["evidence_id"], "source": "image"})
            st.session_state.last_image = {"meta": meta, "result": result}
    data = st.session_state.get("last_image")
    if data:
        meta, result = data["meta"], data["result"]
        st.markdown(f"**Evidence ID:** `{meta['evidence_id']}` · **SHA-256:** `{meta['sha256'][:20]}…`")
        st.markdown(f"**Captured in system:** {meta['timestamp']} · **Sign-off:** {'Recorded' if meta['signoff'] else 'Pending'}")
        c1,c2,c3 = st.columns(3)
        c1.metric("Threat level", result.get("threat_level","Unknown"))
        c2.metric("Scene classification", result.get("scene_classification","Undetermined"))
        c3.metric("Detected items", len(result.get("detections",[])))
        st.caption(f"Analysis mode: {result.get('analysis_mode','demo')} · {result.get('limitations','')}")
        st.dataframe(result.get("detections",[]), use_container_width=True)
        st.markdown("**Prioritized investigative leads**")
        for lead in result.get("leads", []): st.write(f"- {lead}")

with tabs[1]:
    st.subheader("Witness audio transcription & timeline")
    audio_file = st.file_uploader("Upload witness statement / emergency call", type=["wav","mp3","m4a","ogg","webm"], key="audio")
    if audio_file and st.button("Transcribe and analyze audio", type="primary"):
        raw = audio_file.getvalue()
        meta = evidence_meta("audio", audio_file.name, raw)
        with st.spinner("Transcribing audio…"):
            result = analyze_audio(raw, audio_file.name, provider, api_key)
        add_evidence(meta, result)
        for event in result.get("events", []):
            add_event({**event, "evidence_id": meta["evidence_id"], "source": "audio"})
        st.session_state.last_audio = {"meta": meta, "result": result}
    data = st.session_state.get("last_audio")
    if data:
        st.markdown(f"**Evidence ID:** `{data['meta']['evidence_id']}` · **SHA-256:** `{data['meta']['sha256'][:20]}…`")
        st.caption(f"Analysis mode: {data['result'].get('analysis_mode','demo')}")
        st.text_area("Transcript", data["result"].get("transcript",""), height=180)
        st.dataframe(data["result"].get("events",[]), use_container_width=True)
        st.info("Speaker labels are provisional diarization labels, not verified identities.")

with tabs[2]:
    st.subheader("CCTV video analysis & event progression")
    st.caption("Frames are sampled locally. Trajectory and vehicle tracking are illustrative unless a configured vision model can support the observation.")
    video_file = st.file_uploader("Upload CCTV clip", type=["mp4","mov","avi","mkv"], key="video")
    sample_rate = st.slider("Sample interval (seconds)", 1, 10, 2)
    if video_file and st.button("Analyze CCTV clip", type="primary"):
        raw = video_file.getvalue()
        meta = evidence_meta("video", video_file.name, raw)
        with st.spinner("Sampling and analyzing video…"):
            result = analyze_video(raw, video_file.name, sample_rate, provider, api_key)
        add_evidence(meta, result)
        for event in result.get("events", []):
            add_event({**event, "evidence_id": meta["evidence_id"], "source": "video"})
        st.session_state.last_video = {"meta": meta, "result": result}
    data = st.session_state.get("last_video")
    if data:
        st.markdown(f"**Evidence ID:** `{data['meta']['evidence_id']}` · **SHA-256:** `{data['meta']['sha256'][:20]}…`")
        st.caption(f"Analysis mode: {data['result'].get('analysis_mode','demo')}")
        st.dataframe(data["result"].get("events",[]), use_container_width=True)
        st.write("**Tracking notes**")
        for note in data["result"].get("tracking_notes",[]): st.write(f"- {note}")

with tabs[3]:
    st.subheader("Multimodal fusion & grounded evidence chat")
    evidence = all_evidence()
    events = all_events()
    st.metric("Evidence items in this session", len(evidence))
    if events:
        st.markdown("**Master event ledger**")
        st.dataframe(sorted(events, key=lambda x: str(x.get("timestamp",""))), use_container_width=True)
    else:
        st.info("Analyze at least one image, audio file, or video clip to populate the ledger.")
    question = st.text_input("Ask a question about the uploaded evidence", placeholder="Was a weapon visible before the suspect fled?")
    if st.button("Ask evidence", disabled=not question.strip()):
        answer = answer_evidence_question(question, evidence, events, provider, api_key)
        st.session_state.chat_history.append({"question": question, "answer": answer})
    for item in reversed(st.session_state.chat_history):
        with st.container(border=True):
            st.markdown(f"**Investigator:** {item['question']}")
            st.write(item["answer"].get("answer",""))
            refs = item["answer"].get("citations",[])
            st.caption("Cited evidence: " + (", ".join(refs) if refs else "None — insufficient supporting evidence"))
            if item["answer"].get("analysis_mode") == "demo":
                st.caption("Demo response: no inference was made from source media.")

with tabs[4]:
    st.subheader("Automated forensic summary export")
    st.write("Exports the current session ledger, evidence hashes, timestamps, review status, and analysis outputs.")
    if not all_evidence():
        st.info("Upload and analyze evidence before generating a report.")
    else:
        if st.button("Generate PDF report", type="primary"):
            try:
                pdf = build_pdf(case_id, investigator, all_evidence(), all_events())
                st.download_button("Download forensic summary PDF", data=pdf, file_name=f"{case_id}_forensic_summary.pdf", mime="application/pdf")
            except Exception as exc:
                st.error(f"PDF generation failed: {exc}")

st.divider()
st.caption("CrimeVision AI · Session-local prototype · Do not use as sole basis for investigative, charging, or evidentiary decisions.")
