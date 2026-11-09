import streamlit as st

def init_state():
    st.session_state.setdefault("evidence", [])
    st.session_state.setdefault("events", [])
    st.session_state.setdefault("chat_history", [])

def add_evidence(meta, result):
    st.session_state.evidence.append({"metadata": meta, "analysis": result})

def all_evidence():
    return st.session_state.evidence

def add_event(event):
    st.session_state.events.append(event)

def all_events():
    return st.session_state.events
