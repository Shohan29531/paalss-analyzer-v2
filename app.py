from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from streamlit_cookies_manager_ext import EncryptedCookieManager

from lib.docx_report import report_text_to_docx_bytes
from lib.ollama import OllamaError, chat_once, chat_stream, list_models
from lib.prompts import DEFAULT_SYSTEM_PROMPT, build_recommendation_user_prompt
from lib.storage import (
    any_admin_exists,
    change_user_password,
    create_analysis,
    create_session,
    delete_session,
    get_active_model,
    get_analysis,
    get_session,
    get_system_prompt,
    init_db,
    list_analyses_for_user,
    list_users,
    set_active_model,
    set_system_prompt,
    upsert_user,
    update_analysis,
    verify_user,
)
from lib.transcript_parser import (
    build_numbered_transcript_block,
    parse_transcript_docx,
    parse_transcript_txt,
)

APP_TITLE = "PAALSS Transcript Analyzer"
PREFERRED_DEFAULT_MODEL = "qwen3.5:cloud"
DEFAULT_TEMPERATURE = 0.2
COOKIE_KEY = "paalss_session_token"

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "language": "Language",
        "signed_in_as": "Signed in as",
        "role_admin": "admin",
        "role_user": "user",
        "logout": "Logout",
        "new_analysis": "Start new analysis",
        "previous_analyses": "Previous analyses",
        "no_previous_analyses": "No saved analyses yet.",
        "bootstrap_title": "Create the first admin account",
        "bootstrap_caption": "No admin exists yet. The first account created here becomes the admin.",
        "username": "Username",
        "password": "Password",
        "login": "Login",
        "create_admin": "Create admin",
        "invalid_credentials": "Invalid credentials.",
        "admin": "Admin",
        "analyzer": "Analyzer",
        "system_settings": "System settings",
        "users": "Users",
        "active_model": "Active model",
        "refresh_models": "Refresh models",
        "save_model": "Save model",
        "model_saved": "Active model saved.",
        "models_unavailable": "Could not fetch models from the configured Ollama host. You can still type a model name manually.",
        "prompt_editor": "System prompt",
        "save_prompt": "Save prompt",
        "reset_prompt": "Reset prompt",
        "prompt_saved": "System prompt saved.",
        "create_or_update_user": "Create or update user",
        "role": "Role",
        "save_user": "Save user",
        "user_saved": "User saved.",
        "existing_users": "Existing users",
        "change_password": "Change password",
        "current_password": "Current password",
        "new_password": "New password",
        "update_password": "Update password",
        "password_changed": "Password changed.",
        "password_change_failed": "Could not change password. Check your current password.",
        "upload_title": "Upload transcript",
        "upload_help": "Each upload creates its own saved analysis entry on the left.",
        "uploader_label": "Upload a transcript (.docx or .txt)",
        "detected_info": "Detected sample info",
        "title": "Title",
        "save_title": "Save title",
        "title_saved": "Title saved.",
        "transcript_editor": "Transcript sent to the model",
        "save_transcript": "Save transcript edits",
        "transcript_saved": "Transcript saved.",
        "run_analysis": "Run analysis",
        "stream_output": "Stream output",
        "missing_transcript": "Please upload a transcript or open a saved analysis first.",
        "missing_key": "Missing API key for Ollama Cloud. Set OLLAMA_API_KEY in secrets or environment variables.",
        "saved_model_unavailable": "The saved model is not available on this host.",
        "generating_report": "Generating PAALSS report...",
        "generating_recommendation": "Generating recommendations document...",
        "output": "Output",
        "report": "PAALSS report",
        "recommendations": "Recommendations document",
        "download_report": "Download report (.docx)",
        "download_recommendations": "Download recommendations (.docx)",
        "no_output": "Run an analysis to generate and save outputs.",
        "current_record": "Current analysis",
        "filename": "Source file",
        "created": "Created",
        "updated": "Updated",
        "id": "ID",
        "user_prompt_intro": "Analyze the following transcript according to PAALSS and write the full report.",
        "user_prompt_transcript": "TRANSCRIPT (numbered enunciados):",
        "empty_state": "Upload a transcript to create the first saved analysis.",
    },
    "es": {
        "language": "Idioma",
        "signed_in_as": "Sesión iniciada como",
        "role_admin": "admin",
        "role_user": "usuario",
        "logout": "Cerrar sesión",
        "new_analysis": "Iniciar nuevo análisis",
        "previous_analyses": "Análisis anteriores",
        "no_previous_analyses": "Aún no hay análisis guardados.",
        "bootstrap_title": "Crear la primera cuenta de administrador",
        "bootstrap_caption": "Todavía no existe un administrador. La primera cuenta creada aquí será admin.",
        "username": "Usuario",
        "password": "Contraseña",
        "login": "Entrar",
        "create_admin": "Crear admin",
        "invalid_credentials": "Credenciales inválidas.",
        "admin": "Administración",
        "analyzer": "Analizador",
        "system_settings": "Configuración del sistema",
        "users": "Usuarios",
        "active_model": "Modelo activo",
        "refresh_models": "Actualizar modelos",
        "save_model": "Guardar modelo",
        "model_saved": "Modelo activo guardado.",
        "models_unavailable": "No se pudieron obtener los modelos del host de Ollama configurado. Aun así puedes escribir el nombre del modelo manualmente.",
        "prompt_editor": "Prompt del sistema",
        "save_prompt": "Guardar prompt",
        "reset_prompt": "Restablecer prompt",
        "prompt_saved": "Prompt del sistema guardado.",
        "create_or_update_user": "Crear o actualizar usuario",
        "role": "Rol",
        "save_user": "Guardar usuario",
        "user_saved": "Usuario guardado.",
        "existing_users": "Usuarios existentes",
        "change_password": "Cambiar contraseña",
        "current_password": "Contraseña actual",
        "new_password": "Nueva contraseña",
        "update_password": "Actualizar contraseña",
        "password_changed": "Contraseña actualizada.",
        "password_change_failed": "No se pudo cambiar la contraseña. Revisa la contraseña actual.",
        "upload_title": "Subir transcripción",
        "upload_help": "Cada archivo subido crea su propia entrada guardada en la izquierda.",
        "uploader_label": "Sube una transcripción (.docx o .txt)",
        "detected_info": "Información detectada de la muestra",
        "title": "Título",
        "save_title": "Guardar título",
        "title_saved": "Título guardado.",
        "transcript_editor": "Transcripción enviada al modelo",
        "save_transcript": "Guardar cambios de la transcripción",
        "transcript_saved": "Transcripción guardada.",
        "run_analysis": "Ejecutar análisis",
        "stream_output": "Transmitir salida",
        "missing_transcript": "Primero sube una transcripción o abre un análisis guardado.",
        "missing_key": "Falta la clave API para Ollama Cloud. Configura OLLAMA_API_KEY en secrets o variables de entorno.",
        "saved_model_unavailable": "El modelo guardado no está disponible en este host.",
        "generating_report": "Generando informe PAALSS...",
        "generating_recommendation": "Generando documento de recomendaciones...",
        "output": "Salida",
        "report": "Informe PAALSS",
        "recommendations": "Documento de recomendaciones",
        "download_report": "Descargar informe (.docx)",
        "download_recommendations": "Descargar recomendaciones (.docx)",
        "no_output": "Ejecuta un análisis para generar y guardar salidas.",
        "current_record": "Análisis actual",
        "filename": "Archivo fuente",
        "created": "Creado",
        "updated": "Actualizado",
        "id": "ID",
        "user_prompt_intro": "Analiza la siguiente transcripción según PAALSS y escribe el informe completo.",
        "user_prompt_transcript": "TRANSCRIPCIÓN (enunciados numerados):",
        "empty_state": "Sube una transcripción para crear el primer análisis guardado.",
    },
}


def t(key: str) -> str:
    lang = st.session_state.get("lang", "en")
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))


# ---------------- configuration helpers ----------------


def _cfg(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            value = st.secrets.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    except Exception:
        pass
    return os.environ.get(key, default).strip()


OLLAMA_HOST = _cfg("OLLAMA_HOST", "https://ollama.com")
OLLAMA_API_KEY = _cfg("OLLAMA_API_KEY", "")
COOKIE_SECRET = _cfg("COOKIE_SECRET", _cfg("COOKIE_PASSWORD", "change-me"))
DEFAULT_MODEL_FROM_CONFIG = _cfg("OLLAMA_MODEL", PREFERRED_DEFAULT_MODEL)


def _normalize_host(host: str) -> str:
    h = (host or "").strip().rstrip("/")
    if h.endswith("/api"):
        h = h[:-4]
    return h


OLLAMA_HOST = _normalize_host(OLLAMA_HOST)


def _is_cloud_host(host: str) -> bool:
    return host.startswith("https://ollama.com") or host.startswith("http://ollama.com")


@st.cache_data(ttl=120, show_spinner=False)
def _get_models_cached(host: str, api_key: str) -> List[str]:
    models = list_models(host, api_key=api_key)
    return sorted({m for m in models if m and isinstance(m, str)})


def _title_from_first_line(text: str, max_chars: int = 72) -> str:
    line = ""
    for raw in (text or "").splitlines():
        cleaned = re.sub(r"^\s*\d+\s*[.)-]\s*", "", raw).strip()
        if cleaned:
            line = cleaned
            break
    if not line:
        return "Untitled transcript"
    line = re.sub(r"\s+", " ", line).strip("`\"' ")
    return line if len(line) <= max_chars else line[: max_chars - 1].rstrip() + "…"


def _derive_title(filename: str, transcript_text: str, meta: Dict[str, Any]) -> str:
    learner = str(meta.get("learner_name") or "").strip()
    date = str(meta.get("date_iso") or meta.get("date_raw") or "").strip()
    first_line = _title_from_first_line(transcript_text)
    if learner and date:
        return f"{learner} — {date}"
    if learner:
        return learner
    if first_line and first_line != "Untitled transcript":
        return first_line
    stem = Path(filename or "transcript").stem.strip()
    return stem or "Untitled transcript"


# ---------------- cookies / auth ----------------


cookies = EncryptedCookieManager(prefix="paalss_auth", password=COOKIE_SECRET)
if not cookies.ready():
    st.stop()


@st.cache_resource
def _ensure_db() -> bool:
    init_db()
    return True


_ensure_db()


if not get_system_prompt(""):
    set_system_prompt(DEFAULT_SYSTEM_PROMPT)
if not get_active_model(""):
    set_active_model(DEFAULT_MODEL_FROM_CONFIG)


def _login(user_id: str, role: str) -> None:
    token = create_session(user_id, role)
    cookies[COOKIE_KEY] = token
    cookies.save()
    st.session_state["user_id"] = user_id
    st.session_state["role"] = role
    st.session_state["session_token"] = token


def _logout() -> None:
    token = st.session_state.get("session_token") or cookies.get(COOKIE_KEY)
    if token:
        try:
            delete_session(str(token))
        except Exception:
            pass
    cookies[COOKIE_KEY] = ""
    cookies.save()
    for key in [
        "user_id",
        "role",
        "session_token",
        "active_analysis_id",
        "editor_title",
        "editor_transcript_text",
        "editor_source_filename",
        "editor_meta",
        "report_text",
        "recommendation_text",
    ]:
        st.session_state.pop(key, None)


if "user_id" not in st.session_state:
    token = cookies.get(COOKIE_KEY)
    if token:
        sess = get_session(str(token))
        if sess:
            st.session_state["user_id"] = sess["user_id"]
            st.session_state["role"] = sess["role"]
            st.session_state["session_token"] = sess["token"]


# ---------------- state helpers ----------------


st.set_page_config(page_title=APP_TITLE, page_icon="🧾", layout="wide")

st.markdown(
    """
<style>
  section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.6rem;
  }
  div.block-container {
    max-width: 100% !important;
    padding-left: 1.2rem;
    padding-right: 1.2rem;
    padding-top: 1rem !important;
  }
  .paalss-thread-btn button {
    text-align: left !important;
    justify-content: flex-start !important;
    white-space: normal !important;
    height: auto !important;
    padding-top: 0.55rem !important;
    padding-bottom: 0.55rem !important;
  }
</style>
""",
    unsafe_allow_html=True,
)

st.session_state.setdefault("lang", "en")
st.session_state.setdefault("page", "analyzer")
st.session_state.setdefault("uploader_nonce", 0)
st.session_state.setdefault("suppress_autoload", False)


def _fmt_ts(value: Any) -> str:
    s = str(value or "")
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s


def _notify_success(message: str) -> None:
    try:
        st.toast(message)
    except Exception:
        st.success(message)


def _record_accessible(record: Optional[Dict[str, Any]]) -> bool:
    if not record:
        return False
    current_user = st.session_state.get("user_id")
    return str(record.get("user_id") or "") == str(current_user or "")


def _load_analysis_into_state(analysis_id: int) -> None:
    record = get_analysis(int(analysis_id))
    if not _record_accessible(record):
        return
    st.session_state["active_analysis_id"] = int(analysis_id)
    st.session_state["suppress_autoload"] = False
    st.session_state["editor_title"] = str(record.get("title") or "")
    st.session_state["editor_transcript_text"] = str(record.get("transcript_text") or "")
    st.session_state["editor_source_filename"] = str(record.get("source_filename") or "")
    st.session_state["editor_meta"] = record.get("meta") or {}
    st.session_state["report_text"] = str(record.get("report_text") or "")
    st.session_state["recommendation_text"] = str(record.get("recommendation_text") or "")


def _current_record() -> Optional[Dict[str, Any]]:
    analysis_id = st.session_state.get("active_analysis_id")
    if not analysis_id:
        return None
    record = get_analysis(int(analysis_id))
    return record if _record_accessible(record) else None


def _save_title() -> None:
    analysis_id = st.session_state.get("active_analysis_id")
    if not analysis_id:
        return
    title = str(st.session_state.get("editor_title") or "").strip() or "Untitled transcript"
    update_analysis(int(analysis_id), title=title)
    _notify_success(t("title_saved"))


def _save_transcript() -> None:
    analysis_id = st.session_state.get("active_analysis_id")
    if not analysis_id:
        return
    update_analysis(
        int(analysis_id),
        transcript_text=str(st.session_state.get("editor_transcript_text") or ""),
        meta=st.session_state.get("editor_meta") or {},
    )
    _notify_success(t("transcript_saved"))


def _create_analysis_from_upload(uploaded: Any) -> None:
    if uploaded is None:
        return
    if uploaded.name.lower().endswith(".docx"):
        parsed = parse_transcript_docx(uploaded.getvalue())
    else:
        parsed = parse_transcript_txt(uploaded.getvalue().decode("utf-8", errors="ignore"))
    transcript_text = build_numbered_transcript_block(parsed.utterances)
    meta = parsed.meta or {}
    title = _derive_title(uploaded.name, transcript_text, meta)
    analysis_id = create_analysis(
        user_id=str(st.session_state["user_id"]),
        role=str(st.session_state["role"]),
        title=title,
        source_filename=str(uploaded.name),
        transcript_text=transcript_text,
        meta=meta,
    )
    _load_analysis_into_state(int(analysis_id))
    st.session_state["uploader_nonce"] = int(st.session_state.get("uploader_nonce", 0)) + 1
    st.rerun()


def _ensure_active_selection() -> None:
    if st.session_state.get("suppress_autoload"):
        return
    if st.session_state.get("active_analysis_id"):
        record = _current_record()
        if record:
            return
    rows = list_analyses_for_user(str(st.session_state.get("user_id") or ""), limit=200)
    if rows:
        _load_analysis_into_state(int(rows[0]["id"]))


# ---------------- rendering ----------------


def _render_login() -> None:
    st.title(APP_TITLE)
    if not any_admin_exists():
        st.subheader(t("bootstrap_title"))
        st.caption(t("bootstrap_caption"))
        with st.form("bootstrap_admin_form"):
            username = st.text_input(t("username"))
            password = st.text_input(t("password"), type="password")
            submitted = st.form_submit_button(t("create_admin"))
        if submitted:
            if not username.strip() or not password:
                st.error("Username and password are required.")
            else:
                upsert_user(username.strip(), password, "admin")
                _login(username.strip(), "admin")
                st.rerun()
        return

    st.subheader(t("login"))
    with st.form("login_form"):
        username = st.text_input(t("username"))
        password = st.text_input(t("password"), type="password")
        submitted = st.form_submit_button(t("login"))
    if submitted:
        auth = verify_user(username.strip(), password)
        if not auth:
            st.error(t("invalid_credentials"))
        else:
            _login(auth["user_id"], auth["role"])
            st.rerun()


def _render_sidebar(models: List[str]) -> None:
    with st.sidebar:
        st.markdown(f"## {APP_TITLE}")
        lang_cols = st.columns(2)
        with lang_cols[0]:
            if st.button("English", use_container_width=True):
                st.session_state["lang"] = "en"
                st.rerun()
        with lang_cols[1]:
            if st.button("Español", use_container_width=True):
                st.session_state["lang"] = "es"
                st.rerun()

        st.caption(f"{t('signed_in_as')}: **{st.session_state['user_id']}** ({st.session_state['role']})")
        current_model = get_active_model(DEFAULT_MODEL_FROM_CONFIG)
        st.caption(f"**{t('active_model')}:** {current_model}")

        if st.session_state.get("role") == "admin":
            st.radio(
                "",
                options=["analyzer", "admin"],
                format_func=lambda x: t("analyzer") if x == "analyzer" else t("admin"),
                key="page",
                horizontal=True,
                label_visibility="collapsed",
            )

        if st.button(t("new_analysis"), use_container_width=True):
            st.session_state["suppress_autoload"] = True
            for key in [
                "active_analysis_id",
                "editor_title",
                "editor_transcript_text",
                "editor_source_filename",
                "editor_meta",
                "report_text",
                "recommendation_text",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

        st.markdown(f"### {t('previous_analyses')}")
        rows = list_analyses_for_user(str(st.session_state["user_id"]), limit=200)
        if rows:
            for row in rows:
                rid = int(row["id"])
                label = str(row.get("title") or row.get("source_filename") or f"Analysis {rid}")
                ts = _fmt_ts(row.get("updated_at"))
                text = f"{label}\n{ts}" if ts else label
                st.markdown('<div class="paalss-thread-btn">', unsafe_allow_html=True)
                if st.button(text, key=f"analysis_btn_{rid}", use_container_width=True):
                    _load_analysis_into_state(rid)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.caption(t("no_previous_analyses"))

        with st.expander(t("change_password")):
            current_pw = st.text_input(t("current_password"), type="password", key="cp_current")
            new_pw = st.text_input(t("new_password"), type="password", key="cp_new")
            if st.button(t("update_password"), use_container_width=True):
                if change_user_password(str(st.session_state["user_id"]), current_pw, new_pw):
                    _notify_success(t("password_changed"))
                else:
                    st.error(t("password_change_failed"))

        if st.button(t("logout"), use_container_width=True):
            _logout()
            st.rerun()


def _render_admin_page(models: List[str]) -> None:
    st.title(t("admin"))
    tab_system, tab_users = st.tabs([t("system_settings"), t("users")])

    with tab_system:
        st.subheader(t("active_model"))
        current_model = get_active_model(DEFAULT_MODEL_FROM_CONFIG)
        options = models[:] if models else []
        if current_model and current_model not in options:
            options = [current_model] + options
        model_index = options.index(current_model) if current_model in options else 0

        if options:
            picked_model = st.selectbox(t("active_model"), options, index=model_index)
        else:
            picked_model = st.text_input(t("active_model"), value=current_model)
            st.caption(t("models_unavailable"))

        cols = st.columns([0.5, 0.5])
        if cols[0].button(t("save_model"), type="primary", use_container_width=True):
            set_active_model(str(picked_model).strip())
            _notify_success(t("model_saved"))
        if cols[1].button(t("refresh_models"), use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.subheader(t("prompt_editor"))
        prompt_value = get_system_prompt(DEFAULT_SYSTEM_PROMPT)
        prompt_edit = st.text_area(t("prompt_editor"), value=prompt_value, height=520)
        pcols = st.columns([0.5, 0.5])
        if pcols[0].button(t("save_prompt"), type="primary", use_container_width=True):
            set_system_prompt(prompt_edit)
            _notify_success(t("prompt_saved"))
        if pcols[1].button(t("reset_prompt"), use_container_width=True):
            set_system_prompt(DEFAULT_SYSTEM_PROMPT)
            _notify_success(t("prompt_saved"))
            st.rerun()

    with tab_users:
        st.subheader(t("create_or_update_user"))
        with st.form("create_or_update_user_form"):
            username = st.text_input(t("username"))
            password = st.text_input(t("password"), type="password")
            role = st.selectbox(t("role"), ["user", "admin"])
            submitted = st.form_submit_button(t("save_user"))
        if submitted:
            if not username.strip() or not password:
                st.error("Username and password are required.")
            else:
                upsert_user(username.strip(), password, role)
                _notify_success(t("user_saved"))
                st.rerun()

        st.subheader(t("existing_users"))
        rows = list_users()
        if rows:
            st.dataframe(rows, use_container_width=True)


def _render_analyzer_page() -> None:
    _ensure_active_selection()
    record = _current_record()

    st.title(APP_TITLE)

    left, right = st.columns([0.56, 0.44], gap="large")

    with left:
        st.subheader(t("upload_title"))
        st.caption(t("upload_help"))
        uploaded = st.file_uploader(
            t("uploader_label"),
            type=["docx", "txt"],
            accept_multiple_files=False,
            key=f"transcript_uploader_{st.session_state.get('uploader_nonce', 0)}",
        )
        if uploaded is not None:
            _create_analysis_from_upload(uploaded)

        record = _current_record()
        if not record:
            st.info(t("empty_state"))
            return

        meta = st.session_state.get("editor_meta") or {}
        if meta:
            st.markdown(f"**{t('detected_info')}**")
            for key, label in [("learner_name", "Learner"), ("date_iso", "Date"), ("date_raw", "Date"), ("session", "Session"), ("sample", "Sample")]:
                value = meta.get(key)
                if value:
                    st.caption(f"{label}: {value}")

        st.text_input(t("title"), key="editor_title")
        title_cols = st.columns([0.4, 0.6])
        if title_cols[0].button(t("save_title"), use_container_width=True):
            _save_title()

        st.text_area(t("transcript_editor"), key="editor_transcript_text", height=360)
        save_cols = st.columns([0.4, 0.6])
        if save_cols[0].button(t("save_transcript"), use_container_width=True):
            _save_transcript()

        run_cols = st.columns([0.45, 0.55])
        run = run_cols[0].button(t("run_analysis"), type="primary", use_container_width=True)
        stream = run_cols[1].toggle(t("stream_output"), value=True)

        if run:
            transcript_text = str(st.session_state.get("editor_transcript_text") or "").strip()
            if not transcript_text:
                st.error(t("missing_transcript"))
                return
            if _is_cloud_host(OLLAMA_HOST) and not OLLAMA_API_KEY:
                st.error(t("missing_key"))
                return

            saved_model = get_active_model(DEFAULT_MODEL_FROM_CONFIG)
            models: List[str] = []
            try:
                models = _get_models_cached(OLLAMA_HOST, OLLAMA_API_KEY) if (OLLAMA_API_KEY or not _is_cloud_host(OLLAMA_HOST)) else []
            except Exception:
                models = []
            if models and saved_model not in models:
                st.error(t("saved_model_unavailable"))
                return

            current_prompt = get_system_prompt(DEFAULT_SYSTEM_PROMPT)
            update_analysis(
                int(record["id"]),
                title=str(st.session_state.get("editor_title") or record.get("title") or "Untitled transcript"),
                transcript_text=transcript_text,
                meta=st.session_state.get("editor_meta") or {},
                model_snapshot=saved_model,
                system_prompt_snapshot=current_prompt,
            )

            with right:
                report_placeholder = st.empty()
                rec_placeholder = st.empty()
            report_acc = ""
            recommendation_acc = ""
            user_prompt = f"{t('user_prompt_intro')}\n\n{t('user_prompt_transcript')}\n{transcript_text}\n"
            report_messages = [
                {"role": "system", "content": current_prompt},
                {"role": "user", "content": user_prompt},
            ]

            try:
                with st.spinner(t("generating_report")):
                    if stream:
                        for chunk in chat_stream(
                            host=OLLAMA_HOST,
                            api_key=OLLAMA_API_KEY or None,
                            model=saved_model,
                            messages=report_messages,
                            temperature=DEFAULT_TEMPERATURE,
                        ):
                            report_acc += chunk
                            report_placeholder.text(report_acc)
                    else:
                        report_acc = chat_once(
                            host=OLLAMA_HOST,
                            api_key=OLLAMA_API_KEY or None,
                            model=saved_model,
                            messages=report_messages,
                            temperature=DEFAULT_TEMPERATURE,
                        )
                update_analysis(
                    int(record["id"]),
                    report_text=report_acc,
                    model_snapshot=saved_model,
                    system_prompt_snapshot=current_prompt,
                )

                recommendation_prompt = build_recommendation_user_prompt(
                    transcript_text=transcript_text,
                    report_text=report_acc,
                )
                recommendation_messages = [
                    {"role": "system", "content": current_prompt},
                    {"role": "user", "content": recommendation_prompt},
                ]

                with st.spinner(t("generating_recommendation")):
                    if stream:
                        for chunk in chat_stream(
                            host=OLLAMA_HOST,
                            api_key=OLLAMA_API_KEY or None,
                            model=saved_model,
                            messages=recommendation_messages,
                            temperature=DEFAULT_TEMPERATURE,
                        ):
                            recommendation_acc += chunk
                            report_placeholder.text(report_acc)
                            rec_placeholder.text(recommendation_acc)
                    else:
                        recommendation_acc = chat_once(
                            host=OLLAMA_HOST,
                            api_key=OLLAMA_API_KEY or None,
                            model=saved_model,
                            messages=recommendation_messages,
                            temperature=DEFAULT_TEMPERATURE,
                        )
                update_analysis(
                    int(record["id"]),
                    recommendation_text=recommendation_acc,
                    model_snapshot=saved_model,
                    system_prompt_snapshot=current_prompt,
                )
                _load_analysis_into_state(int(record["id"]))
                st.rerun()
            except OllamaError as e:
                st.error(str(e))

    with right:
        record = _current_record()
        st.subheader(t("output"))
        if not record:
            st.info(t("no_output"))
            return

        st.markdown(f"**{t('current_record')}**")
        st.caption(f"{t('filename')}: {record.get('source_filename') or '—'}")
        st.caption(f"{t('id')}: {record.get('analysis_uid')}")
        st.caption(f"{t('created')}: {_fmt_ts(record.get('created_at'))}")
        st.caption(f"{t('updated')}: {_fmt_ts(record.get('updated_at'))}")

        report_text = str(record.get("report_text") or "")
        recommendation_text = str(record.get("recommendation_text") or "")
        if not report_text and not recommendation_text:
            st.info(t("no_output"))
            return

        st.text_area(t("report"), value=report_text, height=280)
        report_docx = report_text_to_docx_bytes(report_text, title=t("report"))
        st.download_button(
            t("download_report"),
            data=report_docx,
            file_name=f"paalss_report_{record.get('analysis_uid')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

        st.text_area(t("recommendations"), value=recommendation_text, height=280)
        recommendation_docx = report_text_to_docx_bytes(recommendation_text, title=t("recommendations"))
        st.download_button(
            t("download_recommendations"),
            data=recommendation_docx,
            file_name=f"paalss_recommendations_{record.get('analysis_uid')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )


# ---------------- app ----------------


def main() -> None:
    try:
        models = _get_models_cached(OLLAMA_HOST, OLLAMA_API_KEY) if (OLLAMA_API_KEY or not _is_cloud_host(OLLAMA_HOST)) else []
    except Exception:
        models = []

    if "user_id" not in st.session_state:
        _render_login()
        return

    _render_sidebar(models)
    if st.session_state.get("role") == "admin" and st.session_state.get("page") == "admin":
        _render_admin_page(models)
    else:
        _render_analyzer_page()


if __name__ == "__main__":
    main()
