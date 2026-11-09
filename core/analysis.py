import json
import re
import tempfile
import os
from io import BytesIO

def _json_from_text(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.I|re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return a JSON object")
    return json.loads(text[start:end+1])

def _gemini_generate(prompt, api_key, image_bytes=None, mime_type=None):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    contents = [prompt]
    if image_bytes:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"))
    response = client.models.generate_content(model="gemini-2.5-flash", contents=contents)
    return response.text or ""

def _groq_chat(prompt, api_key):
    from groq import Groq
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":"You are an evidence summarization assistant. Do not infer facts not present in supplied material. Return valid JSON only."},
                  {"role":"user","content":prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

def _vision_call(prompt, provider, api_key, image_bytes=None, mime_type=None):
    if provider == "Gemini" and api_key:
        return _gemini_generate(prompt, api_key, image_bytes, mime_type)
    if provider == "Groq" and api_key and image_bytes is None:
        return _groq_chat(prompt, api_key)
    raise RuntimeError("No compatible configured model")

def analyze_image(raw, mime_type, provider, api_key):
    prompt = """Inspect this image as an investigative aid. Do not identify people or assert criminality.
Return JSON only with keys threat_level (Low/Medium/High/Critical/Unknown), scene_classification
(Burglary/Homicide/Vandalism/Assault/Undetermined), detections (array of {item, confidence_0_to_1,
bbox_normalized:[x1,y1,x2,y2], observation}), leads (array of cautious next investigative steps),
events (array of {timestamp, event, category, confidence}). Only report visible observations.
If an item is not clearly visible, omit it. Never claim RT-DETR was run."""
    try:
        text = _vision_call(prompt, provider, api_key, raw, mime_type)
        result = _json_from_text(text)
        result["analysis_mode"] = "model-assisted"
        result["limitations"] = "Model output requires independent verification; coordinates are normalized estimates."
        return result
    except Exception as exc:
        return {
            "threat_level":"Unknown", "scene_classification":"Undetermined", "detections":[],
            "leads":["Review the original image at full resolution.","Document scale, orientation, capture device, and original metadata."],
            "events":[], "analysis_mode":"demo", "limitations":f"No verified visual inference performed ({type(exc).__name__})."
        }

def analyze_audio(raw, filename, provider, api_key):
    transcript = ""
    mode = "demo"
    try:
        if provider == "Groq" and api_key:
            from groq import Groq
            client = Groq(api_key=api_key)
            suffix = os.path.splitext(filename)[1] or ".wav"
            with tempfile.NamedTemporaryFile(suffix=suffix) as f:
                f.write(raw); f.flush()
                with open(f.name, "rb") as audio:
                    out = client.audio.transcriptions.create(file=(filename, audio.read()), model="whisper-large-v3", response_format="verbose_json", timestamp_granularities=["segment"])
            transcript = out.text
            segments = getattr(out, "segments", None) or []
            events = [{"timestamp": str(getattr(s,"start","")), "event": getattr(s,"text",""),
                       "speaker": "Speaker-1 (unverified)", "category":"Witness statement"} for s in segments]
            mode = "Groq Whisper"
            return {"transcript": transcript, "events":events, "analysis_mode":mode}
        if provider == "Gemini" and api_key:
            prompt = "Transcribe the audio and return JSON only: {transcript:string, events:[{timestamp:string,event:string,speaker:string,category:string}]}. Speaker labels must be generic and unverified."
            text = _gemini_generate(prompt, api_key, raw, _audio_mime(filename))
            result = _json_from_text(text); result["analysis_mode"]="Gemini"
            return result
    except Exception:
        pass
    return {"transcript":"", "events":[], "analysis_mode":mode,
            "notice":"Demo fallback: audio was not transcribed. Configure Groq Whisper or Gemini to process it."}

def _audio_mime(filename):
    ext = os.path.splitext(filename)[1].lower()
    return {".mp3":"audio/mpeg",".m4a":"audio/mp4",".ogg":"audio/ogg",".webm":"audio/webm"}.get(ext,"audio/wav")

def analyze_video(raw, filename, sample_rate, provider, api_key):
    try:
        import cv2
        import numpy as np
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".mp4") as f:
            f.write(raw); f.flush()
            cap = cv2.VideoCapture(f.name)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            duration = frame_count / fps if fps else 0
            events, notes = [], []
            t = 0.0
            while t < duration and len(events) < 80:
                cap.set(cv2.CAP_PROP_POS_MSEC, t*1000)
                ok, frame = cap.read()
                if not ok: break
                h,w = frame.shape[:2]
                events.append({"timestamp":f"{t:.2f}s","event":"Frame sampled; visual review required",
                               "category":"Unclassified observation","confidence":"N/A",
                               "frame_dimensions":f"{w}x{h}"})
                t += sample_rate
            cap.release()
            notes.append(f"Sampled {len(events)} frames across approximately {duration:.1f} seconds.")
            notes.append("No identity recognition or automated trajectory tracking was performed in this build.")
            return {"events":events,"tracking_notes":notes,"analysis_mode":"local frame sampling"}
    except Exception as exc:
        return {"events":[],"tracking_notes":[f"Video processing unavailable: {type(exc).__name__}. Install opencv-python-headless."],
                "analysis_mode":"demo"}

def answer_evidence_question(question, evidence, events, provider, api_key):
    # Deterministic evidence-grounding gate: only answer from stored observations.
    evidence_ids = [x["metadata"]["evidence_id"] for x in evidence]
    context = {"evidence": [{"evidence_id":x["metadata"]["evidence_id"],"kind":x["metadata"]["kind"],
                             "analysis":x["analysis"]} for x in evidence], "events":events}
    if provider in ("Groq","Gemini") and api_key and evidence:
        prompt = ("Answer only from this JSON evidence context. If unsupported, say insufficient evidence. "
                  "Cite every factual claim using exact evidence IDs in citations. Return JSON "
                  "{answer:string,citations:[evidence_id]}. Do not infer identities or legal guilt.\n"
                  f"Question: {question}\nEvidence: {json.dumps(context, default=str)[:18000]}")
        try:
            raw = _gemini_generate(prompt, api_key) if provider=="Gemini" else _groq_chat(prompt, api_key)
            out = _json_from_text(raw)
            out["citations"] = [x for x in out.get("citations",[]) if x in evidence_ids]
            if not out["citations"]:
                out["answer"] = "Insufficient supporting evidence in the current case ledger."
            out["analysis_mode"]="grounded model-assisted"
            return out
        except Exception:
            pass
    return {"answer":"Insufficient supporting evidence. Demo mode does not inspect or infer facts from uploaded media.",
            "citations":[],"analysis_mode":"demo"}
