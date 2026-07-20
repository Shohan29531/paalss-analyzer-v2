# PAALSS Transcript Analyzer v2

A Streamlit app for generating and saving two sequential outputs from Spanish aided AAC transcripts using an Ollama model:
1. a PAALSS-style analysis report
2. a separate recommendations document grounded in the transcript and generated report

This version adds:
- username/password authentication
- two roles: `admin` and `user`
- persistent saved analyses in a database
- a ChatGPT-style analysis list in the sidebar
- searchable chat history with clinician and AAC-user filters
- admin-managed AAC user/patient IDs
- global admin control over the active model and system prompt

The app is intended for research and clinical drafting support. Its output is not diagnostic and should be reviewed by a qualified clinician or researcher.

## What changed in this version

### Authentication and roles
- Every person must sign in with a username and password.
- The first account ever created becomes the first `admin`.
- `admin` users can:
  - add/update users and admins
  - add/update AAC users/patients
  - search and open analyses across clinicians
  - change the global system prompt
  - change the active model
  - run analyses like any other user
- `user` users can:
  - upload transcripts
  - edit transcripts
  - run analyses
  - reopen old analyses
  - download saved outputs

### Persistent saved analyses
Each transcript upload creates a **new saved analysis record** with its own unique internal ID.

Even if the same file is uploaded twice:
- both analyses are saved separately
- there is no collision
- each one has a distinct ID and timestamp

Saved data includes:
- clinician ID (the signed-in user ID)
- AAC user/patient ID selected before upload
- title
- source filename
- parsed transcript text
- detected metadata
- PAALSS report text
- recommendations text
- model snapshot used for that run
- system prompt snapshot used for that run
- created / updated timestamps

### Sidebar workflow
The left sidebar now behaves more like ChatGPT:
- each uploaded transcript becomes its own saved entry
- clicking an entry reloads that analysis
- keyword search covers titles, filenames, transcripts, reports, recommendations, and IDs
- filters are available for clinician ID and AAC user/patient ID
- legacy analyses without a patient assignment appear as `Unnamed AAC user`
- starting a new analysis clears the current selection without deleting past work

### New-analysis workflow
1. An admin adds AAC user/patient IDs in the **AAC Users/Patients** admin tab.
2. A clinician clicks **Start new analysis**.
3. The clinician selects an AAC user/patient ID.
4. The transcript uploader becomes available.
5. The saved analysis records the signed-in user as the clinician and the selected ID as the patient.

## Data storage

### Local development
If `DATABASE_URL` is not set, the app falls back to a local SQLite database:
- `data/app.db`

### Production / Supabase
For deployment, the intended setup is:
- **Supabase Postgres** via `DATABASE_URL`
- Streamlit secrets for credentials

No manual SQL migration is required for the initial setup.
The app creates the required tables automatically at startup.

## Required secrets

Create `.streamlit/secrets.toml` locally, or paste the same contents into Streamlit Community Cloud secrets when deploying.

```toml
OLLAMA_HOST = "https://ollama.com"
OLLAMA_API_KEY = "your-ollama-api-key"
OLLAMA_MODEL = "qwen3.5:cloud"

# Leave empty locally if you want SQLite instead of Postgres.
DATABASE_URL = "postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres"

# Used to sign the auth cookie.
COOKIE_SECRET = "replace-with-a-long-random-secret"
```

## Local setup

### 1. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add secrets
Copy the example file and edit it:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

### 4. Run the app
```bash
streamlit run app.py
```

## Supabase setup

### Recommended connection choice
Use a **Supabase Postgres connection string** in `DATABASE_URL`.

For Streamlit Community Cloud, the simplest stable option is usually:
- **Session pooler** if you want an IPv4-friendly pooled connection

You can also use:
- **Direct connection** if your environment supports it and you prefer it

Avoid using the transaction pooler unless you specifically want that mode and know how your DB driver behaves with it.

### What the app will create automatically
At startup, the app will create these tables if they do not exist:
- `users`
- `sessions`
- `settings`
- `aac_users`
- `analyses`

Existing databases are migrated automatically by adding the nullable
`analyses.patient_id` column. Existing rows remain valid and are grouped under
`Unnamed AAC user` until a patient assignment exists.

## Streamlit Community Cloud deployment

1. Push this repo to GitHub.
2. Create a new app in Streamlit Community Cloud.
3. Point it to `app.py`.
4. In the deployment flow or app settings, paste your secrets.
5. Deploy.

## First-time bootstrap flow

On first launch:
- if no admin exists, the app shows a bootstrap form
- the first account created becomes the initial admin
- that admin can then create all other users and admins from the admin page

## Project structure

```text
.
├── app.py
├── data/
├── lib/
│   ├── docx_report.py
│   ├── ollama.py
│   ├── prompts.py
│   ├── storage.py
│   └── transcript_parser.py
├── requirements.txt
└── .streamlit/
    ├── secrets.toml
    └── secrets.toml.example
```

## Security notes
- Do not commit real secrets.
- Do not commit `.streamlit/secrets.toml` with real values.
- Rotate any key that was previously exposed.
- Passwords are stored as salted password hashes, not plaintext.
