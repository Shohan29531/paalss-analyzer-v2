import json
import os
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

from lib.docx_report import report_text_to_docx_bytes
from lib.ollama import OllamaError, chat_once, chat_stream, list_models
from lib.prompts import DEFAULT_SYSTEM_PROMPT
from lib.transcript_parser import (
    build_numbered_transcript_block,
    parse_transcript_docx,
    parse_transcript_txt,
)

# -----------------------------
# i18n (UI language only)
# -----------------------------
STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "language": "Language",
        "app_title": "PAALSS Transcript Analyzer",
        "connection": "Connection",
        "ollama_host": "Ollama host",
        "ollama_host_help": "Examples: https://ollama.com (Cloud) or http://localhost:11434 (Local)",
        "api_key_caption": "Get your key here: [Ollama API keys](https://ollama.com/settings/keys)",
        "api_key": "API key",
        "api_key_placeholder": "Paste your Ollama API key",
        "model": "Model",
        "refresh_models": "Refresh model list",
        "could_not_fetch_models": "Could not fetch model list from this host.",
        "save_model": "Save model",
        "saved": "Saved",
        "saved_model": "Saved model",
        "temperature": "Temperature",
        "tab_analyzer": "Analyzer",
        "tab_prompt": "Base System Prompt",
        "prompt_title": "Base System Prompt",
        "prompt_caption": "Edit this prompt to control the structure and level of detail in the generated PAALSS report.",
        "prompt_help": "This is sent as the system message. Changes take effect on the next run.",
        "reset_prompt": "Reset prompt",
        "download_prompt": "Download prompt",
        "upload_step": "1) Upload transcript",
        "uploader_label": "Upload a transcript (.docx or .txt)",
        "uploader_drop": "Drag and drop file here",
        "uploader_limit": "Limit 200MB per file • DOCX, TXT",
        "detected_info": "Detected sample info",
        "learner": "Learner",
        "date": "Date",
        "session": "Session",
        "sample": "Sample",
        "edit_step": "2) Review / edit transcript sent to the model",
        "transcript_placeholder": "Your transcript will appear here after upload…",
        "transcript_help": "This exact text is what will be analyzed. You can edit it before running analysis.",
        "generate_step": "3) Generate PAALSS report",
        "run_analysis": "Run analysis",
        "stream_output": "Stream output",
        "err_missing_key": "Missing API key for Ollama Cloud. Paste it in the sidebar or set OLLAMA_API_KEY.",
        "err_missing_transcript": "Please upload a transcript (or paste one) before running analysis.",
        "err_saved_model_unavailable": "Saved model is not available on this host. Choose a model from the dropdown and click Save model.",
        "user_prompt_intro": "Analyze the following transcript according to PAALSS and write the full report.",
        "user_prompt_transcript": "TRANSCRIPT (numbered enunciados):",
        "output": "Output",
        "report_plain": "PAALSS report (plain text)",
        "download_report": "Download report (.docx)",
        "info_run": "Run an analysis to see the PAALSS report here.",
        "how_it_works": "How it works",
        "how_body": (
            "- Upload a transcript (.docx or .txt).\n"
            "- The app extracts utterances and pre-fills a numbered transcript block.\n"
            "- Edit the transcript block if needed.\n"
            "- Edit the base system prompt in the “Base System Prompt” tab.\n"
            "- Pick a model, click “Save model”, then run analysis."
        ),
    },
    "es": {
        "language": "Idioma",
        "app_title": "Analizador de transcripciones PAALSS",
        "connection": "Conexión",
        "ollama_host": "Host de Ollama",
        "ollama_host_help": "Ejemplos: https://ollama.com (Nube) o http://localhost:11434 (Local)",
        "api_key_caption": "Consigue tu clave aquí: [Claves API de Ollama](https://ollama.com/settings/keys)",
        "api_key": "Clave API",
        "api_key_placeholder": "Pega tu clave API de Ollama",
        "model": "Modelo",
        "refresh_models": "Actualizar lista de modelos",
        "could_not_fetch_models": "No se pudo obtener la lista de modelos de este host.",
        "save_model": "Guardar modelo",
        "saved": "Guardado",
        "saved_model": "Modelo guardado",
        "temperature": "Temperatura",
        "tab_analyzer": "Analizador",
        "tab_prompt": "Prompt base del sistema",
        "prompt_title": "Prompt base del sistema",
        "prompt_caption": "Edita este prompt para controlar la estructura y el nivel de detalle del informe PAALSS generado.",
        "prompt_help": "Esto se envía como el mensaje del sistema. Los cambios se aplican en la próxima ejecución.",
        "reset_prompt": "Restablecer prompt",
        "download_prompt": "Descargar prompt",
        "upload_step": "1) Subir transcripción",
        "uploader_label": "Sube una transcripción (.docx o .txt)",
        "uploader_drop": "Arrastra y suelta el archivo aquí",
        "uploader_limit": "Límite 200 MB por archivo • DOCX, TXT",
        "detected_info": "Información detectada de la muestra",
        "learner": "Participante",
        "date": "Fecha",
        "session": "Sesión",
        "sample": "Muestra",
        "edit_step": "2) Revisar / editar transcripción enviada al modelo",
        "transcript_placeholder": "Tu transcripción aparecerá aquí después de subirla…",
        "transcript_help": "Este texto exacto es lo que se analizará. Puedes editarlo antes de ejecutar el análisis.",
        "generate_step": "3) Generar informe PAALSS",
        "run_analysis": "Ejecutar análisis",
        "stream_output": "Transmitir salida",
        "err_missing_key": "Falta la clave API para Ollama Cloud. Pégala en la barra lateral o configura OLLAMA_API_KEY.",
        "err_missing_transcript": "Sube una transcripción (o pégala) antes de ejecutar el análisis.",
        "err_saved_model_unavailable": "El modelo guardado no está disponible en este host. Elige un modelo y haz clic en Guardar modelo.",
        "user_prompt_intro": "Analiza la siguiente transcripción según PAALSS y escribe el informe completo.",
        "user_prompt_transcript": "TRANSCRIPCIÓN (enunciados numerados):",
        "output": "Salida",
        "report_plain": "Informe PAALSS (texto plano)",
        "download_report": "Descargar informe (.docx)",
        "info_run": "Ejecuta un análisis para ver el informe PAALSS aquí.",
        "how_it_works": "Cómo funciona",
        "how_body": (
            "- Sube una transcripción (.docx o .txt).\n"
            "- La app extrae enunciados y pre-rellena un bloque numerado.\n"
            "- Edita el bloque si hace falta.\n"
            "- Edita el prompt base en la pestaña “Prompt base del sistema”.\n"
            "- Elige un modelo, haz clic en “Guardar modelo” y ejecuta el análisis."
        ),
    },
}


def t(key: str) -> str:
    lang = st.session_state.get("lang", "en")
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))


def _cfg(key: str, default: str = "") -> str:
    """Priority: st.secrets -> env -> default."""
    try:
        if key in st.secrets:
            val = str(st.secrets[key])
            if val:
                return val
    except Exception:
        pass
    return os.environ.get(key, default)


APP_TITLE = "PAALSS Transcript Analyzer"
PREFERRED_DEFAULT_MODEL = "qwen3.5:cloud"  # user-requested default
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), ".paalss_settings.json")


def _strip_trailing_slash(s: str) -> str:
    return (s or "").strip().rstrip("/")


def _normalize_host(host: str) -> str:
    """Allow users to paste https://ollama.com or https://ollama.com/api; normalize to base host."""
    h = _strip_trailing_slash(host)
    if h.endswith("/api"):
        h = h[:-4]
    return h


def _load_settings() -> Dict[str, Any]:
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def _save_settings(d: Dict[str, Any]) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception:
        # If the FS is read-only (rare), we still keep the value in session.
        pass


def _save_settings_merged(update: Dict[str, Any]) -> None:
    settings = _load_settings()
    settings.update(update)
    _save_settings(settings)


@st.cache_data(ttl=120)
def _get_models_cached(host: str, api_key: str) -> List[str]:
    models = list_models(host, api_key=api_key)
    # Stable ordering; also remove empties
    return sorted({m for m in models if m and isinstance(m, str)})


def _is_cloud_host(host: str) -> bool:
    # Keep this conservative: if user targets ollama.com, assume cloud.
    return host.startswith("https://ollama.com") or host.startswith("http://ollama.com")


def _set_lang(lang: str) -> None:
    lang = "es" if lang == "es" else "en"
    st.session_state.lang = lang
    st.session_state.lang_en = lang == "en"
    st.session_state.lang_es = lang == "es"
    _save_settings_merged({"lang": lang})


def _on_lang_en_change() -> None:
    # If English is checked, force English. If unchecked, keep at least one selected.
    if st.session_state.lang_en:
        _set_lang("en")
    else:
        if st.session_state.get("lang_es"):
            _set_lang("es")
        else:
            st.session_state.lang_en = True
            _set_lang("en")


def _on_lang_es_change() -> None:
    # If Español is checked, force Spanish. If unchecked, fall back to English.
    if st.session_state.lang_es:
        _set_lang("es")
    else:
        _set_lang("en")


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🧾",
    layout="wide",
)

# --- Session defaults ---
settings_boot = _load_settings()

if "lang" not in st.session_state:
    raw = str(settings_boot.get("lang") or "").strip().lower()
    st.session_state.lang = "es" if raw in ("es", "spanish", "español", "espanol") else "en"

if "lang_en" not in st.session_state:
    st.session_state.lang_en = st.session_state.lang == "en"

if "lang_es" not in st.session_state:
    st.session_state.lang_es = st.session_state.lang == "es"

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT

if "transcript_text" not in st.session_state:
    st.session_state.transcript_text = ""

if "report_text" not in st.session_state:
    st.session_state.report_text = ""

if "meta" not in st.session_state:
    st.session_state.meta = {}

if "saved_model" not in st.session_state:
    st.session_state.saved_model = ""

if "model_pick" not in st.session_state:
    st.session_state.model_pick = ""


# --- Sidebar (language + connection + model) ---
with st.sidebar:
    st.markdown(f"### {t('language')}")
    lcols = st.columns(2)
    with lcols[0]:
        st.checkbox("English", key="lang_en", on_change=_on_lang_en_change)
    with lcols[1]:
        st.checkbox("Español", key="lang_es", on_change=_on_lang_es_change)

    st.divider()
    st.markdown(f"## {t('app_title')}")

    st.markdown(f"### {t('connection')}")

    default_host = _cfg("OLLAMA_HOST", "https://ollama.com")
    host_input = st.text_input(
        t("ollama_host"),
        value=default_host,
        help=t("ollama_host_help"),
    )
    host = _normalize_host(host_input)

    st.markdown(t("api_key_caption"))
    env_key = _cfg("OLLAMA_API_KEY", "").strip()
    user_key = st.text_input(
        t("api_key"),
        value="",
        type="password",
        placeholder=t("api_key_placeholder"),
    )
    api_key = user_key.strip() if user_key.strip() else env_key

    st.divider()

    st.markdown(f"### {t('model')}")

    # Refresh button (clears cached model list)
    if st.button(t("refresh_models"), use_container_width=True):
        st.cache_data.clear()

    # Load model list (best-effort)
    models: List[str] = []
    models_err: str = ""
    if api_key or not _is_cloud_host(host):
        try:
            models = _get_models_cached(host, api_key)
        except Exception as e:
            models_err = str(e)
            models = []

    if models_err:
        st.caption(t("could_not_fetch_models"))

    # Load persisted choice (file) once, then keep in session.
    if not st.session_state.saved_model:
        persisted = str(settings_boot.get("model") or "").strip()

        # Choose default deterministically.
        if persisted:
            chosen = persisted
        elif PREFERRED_DEFAULT_MODEL:
            chosen = PREFERRED_DEFAULT_MODEL
        else:
            chosen = ""

        # If we have a model list, try to map to something real.
        if models:
            if chosen not in models:
                preferred_base = chosen.split(":", 1)[0] if chosen else ""
                candidates = [m for m in models if preferred_base and preferred_base in m]
                chosen = candidates[0] if candidates else models[0]

        st.session_state.saved_model = chosen
        st.session_state.model_pick = chosen

    # Dropdown options: show discovered models when available.
    options = models[:] if models else []
    if st.session_state.saved_model and st.session_state.saved_model not in options:
        options = [st.session_state.saved_model] + options
    if PREFERRED_DEFAULT_MODEL and PREFERRED_DEFAULT_MODEL not in options:
        options = [PREFERRED_DEFAULT_MODEL] + options

    # de-dupe while preserving order
    seen = set()
    options = [m for m in options if not (m in seen or seen.add(m))]

    if not options:
        options = [PREFERRED_DEFAULT_MODEL]

    st.selectbox(
        t("model"),
        options=options,
        index=options.index(st.session_state.model_pick) if st.session_state.model_pick in options else 0,
        key="model_pick",
    )

    save_cols = st.columns([0.55, 0.45])
    with save_cols[0]:
        if st.button(t("save_model"), type="primary", use_container_width=True):
            st.session_state.saved_model = st.session_state.model_pick
            _save_settings_merged({"model": st.session_state.saved_model})
            st.success(t("saved"))

    with save_cols[1]:
        st.caption("\n")

    st.caption(f"{t('saved_model')}: `{st.session_state.saved_model}`")

    temperature = st.slider(t("temperature"), 0.0, 1.0, 0.2, 0.05)


# --- Main UI ---
st.markdown(
    """
<style>
  div.block-container {
    max-width: 100% !important;
    padding-left: 1.25rem;
    padding-right: 1.25rem;
    padding-top: 4.25rem !important;
  }

  /* Hide Streamlit default file-uploader instruction text (so we can localize) */
  div[data-testid="stFileUploaderDropzoneInstructions"] { display: none !important; }

</style>
""",
    unsafe_allow_html=True,
)

tabs = st.tabs([t("tab_analyzer"), t("tab_prompt")])


with tabs[1]:
    st.markdown(f"### {t('prompt_title')}")
    st.caption(t("prompt_caption"))

    # NOTE: Prompt content is NOT translated.
    st.session_state.system_prompt = st.text_area(
        "",
        value=st.session_state.system_prompt,
        height=720,
        help=t("prompt_help"),
    )

    pcols = st.columns([0.25, 0.25, 0.50])
    with pcols[0]:
        if st.button(t("reset_prompt"), use_container_width=True):
            st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT
            st.rerun()
    with pcols[1]:
        st.download_button(
            t("download_prompt"),
            data=st.session_state.system_prompt.encode("utf-8"),
            file_name="paalss_system_prompt.txt",
            mime="text/plain",
            use_container_width=True,
        )


with tabs[0]:
    left, right = st.columns([0.55, 0.45], gap="large")

    with left:
        st.markdown(f"### {t('upload_step')}")
        st.caption(t("uploader_limit"))

        uploaded = st.file_uploader(
            t("uploader_label"),
            type=["docx", "txt"],
            accept_multiple_files=False,
        )

        if uploaded is not None:
            if uploaded.name.lower().endswith(".docx"):
                data = parse_transcript_docx(uploaded.getvalue())
            else:
                data = parse_transcript_txt(uploaded.getvalue().decode("utf-8", errors="ignore"))

            st.session_state.meta = data.meta
            st.session_state.transcript_text = build_numbered_transcript_block(data.utterances)

        meta: Dict[str, Any] = st.session_state.meta or {}
        if meta:
            st.markdown(f"**{t('detected_info')}**")
            meta_lines: List[str] = []
            if meta.get("learner_name"):
                meta_lines.append(f"- {t('learner')}: {meta['learner_name']}")
            if meta.get("date_iso"):
                meta_lines.append(f"- {t('date')}: {meta['date_iso']}")
            elif meta.get("date_raw"):
                meta_lines.append(f"- {t('date')}: {meta['date_raw']}")
            if meta.get("session"):
                meta_lines.append(f"- {t('session')}: {meta['session']}")
            if meta.get("sample"):
                meta_lines.append(f"- {t('sample')}: {meta['sample']}")
            st.markdown("\n".join(meta_lines))

        st.markdown(f"### {t('edit_step')}")
        st.session_state.transcript_text = st.text_area(
            "",
            value=st.session_state.transcript_text,
            height=420,
            placeholder=t("transcript_placeholder"),
            help=t("transcript_help"),
        )

        st.markdown(f"### {t('generate_step')}")

        run_cols = st.columns([0.55, 0.45])
        with run_cols[0]:
            run = st.button(t("run_analysis"), type="primary", use_container_width=True)
        with run_cols[1]:
            stream = st.toggle(t("stream_output"), value=True)

        if run:
            if _is_cloud_host(host) and not api_key:
                st.error(t("err_missing_key"))
            elif not st.session_state.transcript_text.strip():
                st.error(t("err_missing_transcript"))
            else:
                # Validate saved model if we can see a list.
                if models and st.session_state.saved_model not in models:
                    st.error(t("err_saved_model_unavailable"))
                else:
                    user_prompt = (
                        f"{t('user_prompt_intro')}\n\n"
                        f"{t('user_prompt_transcript')}\n"
                        f"{st.session_state.transcript_text.strip()}\n"
                    )

                    messages = [
                        {"role": "system", "content": st.session_state.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ]

                    out = st.empty()
                    acc = ""

                    try:
                        if stream:
                            for chunk in chat_stream(
                                host=host,
                                api_key=api_key,
                                model=st.session_state.saved_model,
                                messages=messages,
                                temperature=temperature,
                            ):
                                acc += chunk
                                out.text(acc)
                        else:
                            acc = chat_once(
                                host=host,
                                api_key=api_key,
                                model=st.session_state.saved_model,
                                messages=messages,
                                temperature=temperature,
                            )
                            out.text(acc)

                        st.session_state.report_text = acc

                    except OllamaError as e:
                        st.error(str(e))

    with right:
        st.markdown(f"### {t('output')}")

        if st.session_state.report_text.strip():
            st.text_area(
                t("report_plain"),
                value=st.session_state.report_text,
                height=560,
            )

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            docx_bytes = report_text_to_docx_bytes(st.session_state.report_text)

            st.download_button(
                t("download_report"),
                data=docx_bytes,
                file_name=f"paalss_report_{ts}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        else:
            st.info(t("info_run"))

        with st.expander(t("how_it_works")):
            st.markdown(t("how_body"))
