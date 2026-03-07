# PAALSS Transcript Analyzer

A lightweight app created using streamlit for generating **PAALSS-style analyses** from **Spanish aided AAC transcripts** using an **Ollama** model (Ollama Cloud or local Ollama).

This app is designed for **research/clinical drafting support**. The output is **not diagnostic** and should be reviewed by a qualified clinician/researcher.

---

## What this app does

- Upload a transcript (`.docx` or `.txt`).
- Extract / prefill a **numbered transcript block** (Enunciados).
- Let you **edit the transcript** before analysis (the model analyzes exactly what you see in the editor).
- Let you edit a **base system prompt** to control the PAALSS report format and level of detail.
  - Note: the **system prompt text is not translated** when you switch UI language.
- Send transcript + prompt to a selected Ollama model and return a **PAALSS-style report**.
- Stream the output (optional) and download the report as **.docx**.
- UI language toggle (English / Español) for the **app interface**.

---

## Key UI behaviors

### UI language toggle (English / Español)
- In the left sidebar, you can choose **English** or **Español**.
- Default is **English**.
- Only the **UI labels/help text** are translated. The **system prompt** remains unchanged.

### Model selection is explicit (dropdown + Save)
- The model dropdown is always visible.
- Default model is **`qwen3.5:cloud`** (if available on the configured host).
- If you change the dropdown, the app will not “lock it in” until you click **Save model**.
- The saved model is persisted locally in `./.paalss_settings.json` so it stays fixed across reloads.

### File uploader instruction text
Streamlit’s built-in uploader “Drag and drop…” text is not i18n-friendly. The app hides that built-in text and shows localized instructions instead.

---

## Setup

### 1) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure Ollama

You can use either:

#### Option A — Environment variables

```bash
export OLLAMA_HOST="https://ollama.com"     # Ollama Cloud
export OLLAMA_API_KEY="..."                 # required for Cloud
```

For local Ollama:

```bash
export OLLAMA_HOST="http://localhost:11434" # local Ollama
# OLLAMA_API_KEY usually not needed locally
```

#### Option B — Streamlit secrets file (recommended for local dev)

Create:

- `./.streamlit/secrets.toml`  (do NOT commit)

Example:

```toml
OLLAMA_HOST = "https://ollama.com"
OLLAMA_API_KEY = "..."
```

If deploying on Streamlit Cloud, use the **Secrets** UI instead of committing files.

### 3) Run

```bash
streamlit run app.py
```

If your entrypoint file is named differently, rename it to `app.py` or run:

```bash
streamlit run <your_file>.py
```

---

## Using the app

1) **Upload transcript**
- Supported formats: `.docx`, `.txt`
- Recommended `.docx`: transcripts formatted as **tables** (with a numbered Enunciado column) parse best.
- `.txt`: one utterance per line; optionally numbered like `1. ...`, `2. ...`

2) **Review / edit transcript**
- The app generates a numbered transcript block.
- You can edit this block directly before running analysis.

3) **Choose model + Save model**
- Pick a model from the dropdown.
- Click **Save model** to persist that selection.

4) **Generate report**
- Click **Run analysis**
- Optional: enable/disable **Stream output**
- Adjust **Temperature** (lower = more consistent formatting; higher = more variation)

5) **Export**
- Download as `.docx` from the right panel.

---

## Notes on transcripts

- Each numbered line is treated as one utterance (Enunciado).
- If the transcript contains `/`, the analyzer prompt may treat slash-separated units as tokens.
- If there are unintelligible/unknown items (e.g., “??”), those should be represented clearly in the transcript so they can be excluded from counts.

---

## Troubleshooting

### “401 Unauthorized” (Ollama Cloud)
- Your API key is missing/invalid/revoked.
- Ensure `OLLAMA_API_KEY` is set (env var or secrets) and that you’re using the correct host.

### “404 Not Found” for `/api/chat`
- Verify `OLLAMA_HOST` is set to `https://ollama.com` (or your local host).
- If you pasted `https://ollama.com/api`, the app normalizes it to `https://ollama.com`.

### “model '<name>' not found”
- The saved model name must match exactly what the host provides.
- Click **Refresh model list**, pick an available model from the dropdown, then click **Save model**.

### “Saved model is not available on this host”
- This happens if you saved a model while pointing to one host (e.g., Cloud), then switched to another host (e.g., local).
- Pick a model for the current host and click **Save model**.

---

## Files created locally (do not commit)

- `./.streamlit/secrets.toml` (if you use it)
- `./.paalss_settings.json` (stores saved UI language + saved model)
- Any exported `.docx` files you download locally

Add these to `.gitignore`:

```gitignore
.streamlit/secrets.toml
.paalss_settings.json
```

---

## Security

- Never commit API keys (Ollama, Supabase, etc.) to Git.
- Prefer environment variables or Streamlit secrets.
- If you ever accidentally committed a key, treat it as compromised and rotate/revoke it immediately.
