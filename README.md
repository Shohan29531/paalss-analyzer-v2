# PAALSS Transcript Analyzer (Streamlit)

A lightweight Streamlit app for generating **PAALSS**-style analyses from **Spanish aided AAC transcripts** using an **Ollama** model (e.g., Ollama Cloud).

## What this app does

- Upload a transcript (`.docx` or `.txt`).
- Extract / prefill a numbered transcript block.
- Let you edit the **base system prompt** (so changing the prompt changes the analysis output).
- Send the transcript + prompt to the selected Ollama model and return a **PAALSS-style report**.
- Download the report as **.docx**.

## Setup

### 1) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure Ollama

You can use environment variables:

```bash
export OLLAMA_HOST="https://ollama.com"
export OLLAMA_API_KEY="<optional>"
export OLLAMA_MODEL="<optional default model name>"
```

Or create a local secrets file (NOT committed):

- `./.streamlit/secrets.toml`

Example:

```toml
OLLAMA_HOST = "https://ollama.com"
OLLAMA_API_KEY = ""
OLLAMA_MODEL = ""
```

### 3) Run

```bash
streamlit run app.py
```

## Notes on transcripts

- `.docx` transcripts that use tables (with a numbered enunciado column) are parsed best.
- If a transcript is formatted differently, upload as `.txt` (one utterance per line, optionally prefixed with `1.` / `2.` etc.).
- The app always shows an editable transcript block. **That exact text is what gets analyzed**.

## Security

- API keys should be provided via environment variables or `secrets.toml`.
- Do not commit keys into source control.
# paalss-analyzer
