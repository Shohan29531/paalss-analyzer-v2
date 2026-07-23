# PAALSS Transcript Analyzer

A Streamlit app for analyzing Spanish aided AAC transcripts with an Ollama model. It generates a PAALSS report and a separate recommendations document.

## Features

- Admin and Clinician accounts
- AAC User assignment for each analysis
- `.docx` and `.txt` transcript uploads
- Editable, automatically renumbered transcript lines
- Saved chat history with search, rename, and delete
- English and Spanish interfaces
- Downloadable report and recommendations files
- Single-chat and all-chat spreadsheet exports
- SQLite for local use or PostgreSQL/Supabase for deployment

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

On Windows, activate the environment with:

```powershell
.venv\Scripts\activate
```

Edit `.streamlit/secrets.toml`:

```toml
OLLAMA_HOST = "https://ollama.com"
OLLAMA_API_KEY = "your-ollama-api-key"
OLLAMA_MODEL = "qwen3-vl:235b-cloud"
COOKIE_SECRET = "replace-with-a-long-random-secret"

# Optional. Leave unset to use data/app.db locally.
DATABASE_URL = "postgresql://username:password@host:port/database"
```

Run the app:

```bash
streamlit run app.py
```

## First use

1. Launch the app and create the first account. It becomes the Admin.
2. In **Admin**, add Clinicians and AAC Users.
3. Open **Analyzer** and select **Start new analysis**.
4. Select an AAC User and upload a transcript.
5. Review or edit the transcript, then run the analysis.

Transcript numbering is updated automatically when numbered lines are deleted or rearranged.

## Storage

Without `DATABASE_URL`, data is stored in:

```text
data/app.db
```

For Streamlit Community Cloud, use PostgreSQL or Supabase because the local filesystem is not reliable for permanent storage. Required tables are created automatically.

## Deployment

1. Push the project to GitHub.
2. Create a Streamlit Community Cloud app using `app.py`.
3. Add the secrets shown above.
4. Set `DATABASE_URL` to a persistent PostgreSQL database.
5. Deploy.

## Security

Never commit `.streamlit/secrets.toml`, API keys, database credentials, or real participant data. Change any credential that has previously been exposed.

The generated content is drafting support, not a diagnosis. A qualified Clinician must review all output.
