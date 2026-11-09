# CrimeVision AI — Intelligent Multimodal Forensic Analysis Platform

Streamlit capstone prototype with five modules: image evidence tagging, audio transcription, CCTV frame sampling, evidence-ledger chat, and PDF export.

## Important scope and limitations

This is a **training / investigative-aid prototype**, not a validated forensic system. It does not produce court-admissible conclusions. It does not implement RT-DETR, person identification, verified speaker diarization, multi-object tracking, trajectory reconstruction, or secure evidentiary storage. The image module can ask Gemini for visible observations when configured; the Groq integration is used for text and Whisper transcription. Demo mode deliberately does not fabricate detections or transcripts. Model outputs require independent human verification.

The session-memory ledger is cleared when the Streamlit session resets. SHA-256 values prove only which bytes were hashed at ingestion; they do not prove authenticity, capture time, or an unbroken chain of custody. For real deployments, add immutable object storage, role-based access, append-only audit logs, trusted timestamping, key management, retention controls, and validated forensic procedures.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## API keys

You can enter a key in the sidebar for the current session. For deployment, configure Streamlit secrets:

`.streamlit/secrets.toml`
```toml
GROQ_API_KEY = "your-groq-key"
GEMINI_API_KEY = "your-gemini-key"
```

Do not commit this file. Groq supports Whisper transcription and text-based grounded Q&A. Gemini supports image analysis, audio analysis, and grounded Q&A. If a provider call fails, the application falls back to explicitly labelled demo mode.

## Streamlit Community Cloud

1. Push this project to a GitHub repository.
2. Create a new app in Streamlit Community Cloud and select `app.py`.
3. Add provider keys under the app's **Secrets** settings.
4. Keep uploaded files small enough for your deployment limits.

## Evidence handling

Each upload receives an application evidence ID, UTC ingestion timestamp, SHA-256 digest, case reference, investigator field, and a user-declared review checkbox. These are bookkeeping indicators only, not a legally sufficient chain of custody.
