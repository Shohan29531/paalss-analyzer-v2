from __future__ import annotations

import io
import os
import re
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

import streamlit as st
from streamlit_cookies_manager_ext import EncryptedCookieManager

from lib.docx_report import report_text_to_docx_bytes
from lib.ollama import OllamaError, chat_once, chat_stream, list_models
from lib.prompts import (
    DEFAULT_SYSTEM_PROMPTS,
    build_recommendation_user_prompt,
    get_default_system_prompt,
)
from lib.storage import (
    any_admin_exists,
    change_user_password,
    create_analysis,
    create_session,
    delete_analysis_for_user,
    delete_session,
    get_active_model,
    get_analysis,
    get_session,
    get_system_prompt,
    get_user_language,
    init_db,
    list_aac_users,
    list_analyses_for_user,
    list_users,
    rename_analysis_for_user,
    search_analyses,
    set_active_model,
    set_system_prompt,
    set_user_language,
    upsert_aac_user,
    upsert_user,
    update_analysis,
    verify_user,
)
from lib.transcript_parser import (
    build_numbered_transcript_block,
    parse_transcript_docx,
    parse_transcript_txt,
)

APP_TITLES = {"en": "PAALSS Transcript Analyzer", "es": "Analizador de Transcripciones PAALSS"}
PREFERRED_DEFAULT_MODEL = "qwen3-vl:235b-cloud"
DEFAULT_TEMPERATURE = 0.2
COOKIE_KEY = "paalss_session_token"
LANGUAGE_COOKIE_KEY = "paalss_lang"

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "language": "Language",
        "app_title": "PAALSS Transcript Analyzer",
        "signed_in_as": "Signed in as",
        "role_admin": "admin",
        "role_user": "Clinician",
        "logout": "Logout",
        "navigation": "Navigation",
        "new_analysis": "Start new analysis",
        "previous_analyses": "Previous analyses",
        "no_previous_analyses": "No saved analyses yet.",
        "chat_tab": "Chat",
        "search_tab": "Search",
        "search_chats": "Search chats",
        "search_placeholder": "Search titles, transcripts, reports...",
        "chat_filters": "Filters",
        "all_clinicians": "All Clinicians",
        "all_aac_users": "All AAC Users",
        "clinician_id": "Clinician ID",
        "aac_user_patient": "AAC User",
        "unnamed_aac_user": "Unnamed AAC User",
        "no_matching_analyses": "No chats match these filters.",
        "export_sheet": "Export as Sheet",
        "export_all_chats": "Export All Chats as Sheet",
        "rename_chat": "Rename chat",
        "delete_chat": "Delete chat",
        "chat_title": "Chat title",
        "title_required": "Enter a chat title.",
        "save": "Save",
        "cancel": "Cancel",
        "chat_renamed": "Chat renamed.",
        "rename_failed": "Could not rename this chat.",
        "delete_chat_title": "Delete chat?",
        "delete_chat_warning": "This will permanently delete the chat, transcript, report, and recommendations. This action cannot be undone.",
        "confirm_delete": "Delete permanently",
        "chat_deleted": "Chat deleted.",
        "delete_failed": "Could not delete this chat.",
        "bootstrap_title": "Create the first admin account",
        "bootstrap_caption": "No admin exists yet. The first account created here becomes the admin.",
        "username": "Username",
        "password": "Password",
        "clinician_username": "Clinician Username",
        "clinician_password": "Clinician Password",
        "clinician_credentials_required": "Clinician username and password are required.",
        "login": "Login",
        "create_admin": "Create admin",
        "invalid_credentials": "Invalid credentials.",
        "admin": "Admin",
        "analyzer": "Analyzer",
        "system_settings": "System settings",
        "users": "Clinicians",
        "aac_users_patients": "AAC Users",
        "active_model": "Active model",
        "refresh_models": "Refresh models",
        "save_model": "Save model",
        "model_saved": "Active model saved.",
        "models_unavailable": "Could not fetch models from the configured Ollama host. You can still type a model name manually.",
        "prompt_editor": "System prompt",
        "save_prompt": "Save prompt",
        "reset_prompt": "Reset prompt",
        "prompt_saved": "System prompt saved.",
        "create_or_update_user": "Add or update Clinician",
        "role": "Role",
        "save_user": "Save Clinician",
        "user_saved": "Clinician saved.",
        "existing_users": "Existing Clinicians",
        "add_aac_user": "Add or update AAC User",
        "aac_user_id": "AAC User ID",
        "save_aac_user": "Save AAC User",
        "aac_user_saved": "AAC User saved.",
        "aac_user_required": "AAC User ID is required.",
        "existing_aac_users": "Existing AAC Users",
        "no_aac_users": "No AAC Users have been added yet.",
        "change_password": "Change password",
        "current_password": "Current password",
        "new_password": "New password",
        "update_password": "Update password",
        "password_changed": "Password changed.",
        "password_change_failed": "Could not change password. Check your current password.",
        "upload_title": "Upload transcript",
        "upload_help": "Each upload creates its own saved analysis entry on the left.",
        "uploader_label": "Upload a transcript (.docx or .txt)",
        "select_patient_first": "Select the AAC User before uploading the transcript.",
        "select_aac_user": "Select an AAC User",
        "start_new_to_upload": "Click Start new analysis to select an AAC User and upload another transcript.",
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
        "patient": "AAC User",
        "user_prompt_intro": "Analyze the following transcript according to PAALSS and write the full report.",
        "user_prompt_transcript": "TRANSCRIPT (numbered enunciados):",
        "empty_state": "Upload a transcript to create the first saved analysis.",
        "username_password_required": "Username and password are required.",
        "learner": "Learner",
        "date": "Date",
        "session": "Session",
        "sample": "Sample",
        "untitled_transcript": "Untitled transcript",
        "db_init_failed": "Database initialization failed. Check DATABASE_URL / Supabase connection settings.",
        "db_init_help": "If you are using Supabase on Streamlit Cloud, use the Supavisor session pooler connection string, not the direct db.<project-ref>.supabase.co host.",
    },
    "es": {
        "language": "Idioma",
        "app_title": "Analizador de Transcripciones PAALSS",
        "signed_in_as": "Sesión iniciada como",
        "role_admin": "admin",
        "role_user": "Clínico",
        "logout": "Cerrar sesión",
        "navigation": "Navegación",
        "new_analysis": "Iniciar nuevo análisis",
        "previous_analyses": "Análisis anteriores",
        "no_previous_analyses": "Aún no hay análisis guardados.",
        "chat_tab": "Chat",
        "search_tab": "Buscar",
        "search_chats": "Buscar chats",
        "search_placeholder": "Buscar en títulos, transcripciones e informes...",
        "chat_filters": "Filtros",
        "all_clinicians": "Todos los clínicos",
        "all_aac_users": "Todos los usuarios de CAA",
        "clinician_id": "ID del clínico",
        "aac_user_patient": "Usuario de CAA",
        "unnamed_aac_user": "Usuario de CAA sin nombre",
        "no_matching_analyses": "Ningún chat coincide con estos filtros.",
        "export_sheet": "Exportar como hoja",
        "export_all_chats": "Exportar todos los chats como hoja",
        "rename_chat": "Renombrar chat",
        "delete_chat": "Eliminar chat",
        "chat_title": "Título del chat",
        "title_required": "Escribe un título para el chat.",
        "save": "Guardar",
        "cancel": "Cancelar",
        "chat_renamed": "Chat renombrado.",
        "rename_failed": "No se pudo renombrar este chat.",
        "delete_chat_title": "¿Eliminar chat?",
        "delete_chat_warning": "Esto eliminará permanentemente el chat, la transcripción, el informe y las recomendaciones. Esta acción no se puede deshacer.",
        "confirm_delete": "Eliminar permanentemente",
        "chat_deleted": "Chat eliminado.",
        "delete_failed": "No se pudo eliminar este chat.",
        "bootstrap_title": "Crear la primera cuenta de administrador",
        "bootstrap_caption": "Todavía no existe un administrador. La primera cuenta creada aquí será admin.",
        "username": "Usuario",
        "password": "Contraseña",
        "clinician_username": "Nombre de usuario del clínico",
        "clinician_password": "Contraseña del clínico",
        "clinician_credentials_required": "Se requieren el nombre de usuario y la contraseña del clínico.",
        "login": "Entrar",
        "create_admin": "Crear admin",
        "invalid_credentials": "Credenciales inválidas.",
        "admin": "Administración",
        "analyzer": "Analizador",
        "system_settings": "Configuración del sistema",
        "users": "Clínicos",
        "aac_users_patients": "Usuarios de CAA",
        "active_model": "Modelo activo",
        "refresh_models": "Actualizar modelos",
        "save_model": "Guardar modelo",
        "model_saved": "Modelo activo guardado.",
        "models_unavailable": "No se pudieron obtener los modelos del host de Ollama configurado. Aun así puedes escribir el nombre del modelo manualmente.",
        "prompt_editor": "Prompt del sistema",
        "save_prompt": "Guardar prompt",
        "reset_prompt": "Restablecer prompt",
        "prompt_saved": "Prompt del sistema guardado.",
        "create_or_update_user": "Agregar o actualizar clínico",
        "role": "Rol",
        "save_user": "Guardar clínico",
        "user_saved": "Clínico guardado.",
        "existing_users": "Clínicos existentes",
        "add_aac_user": "Agregar o actualizar usuario de CAA",
        "aac_user_id": "ID del usuario de CAA",
        "save_aac_user": "Guardar usuario de CAA",
        "aac_user_saved": "Usuario de CAA guardado.",
        "aac_user_required": "Se requiere el ID del usuario de CAA.",
        "existing_aac_users": "Usuarios de CAA existentes",
        "no_aac_users": "Todavía no se han agregado usuarios de CAA.",
        "change_password": "Cambiar contraseña",
        "current_password": "Contraseña actual",
        "new_password": "Nueva contraseña",
        "update_password": "Actualizar contraseña",
        "password_changed": "Contraseña actualizada.",
        "password_change_failed": "No se pudo cambiar la contraseña. Revisa la contraseña actual.",
        "upload_title": "Subir transcripción",
        "upload_help": "Cada archivo subido crea su propia entrada guardada en la izquierda.",
        "uploader_label": "Sube una transcripción (.docx o .txt)",
        "select_patient_first": "Selecciona el usuario de CAA antes de subir la transcripción.",
        "select_aac_user": "Selecciona un usuario de CAA",
        "start_new_to_upload": "Haz clic en Iniciar nuevo análisis para seleccionar un usuario de CAA y subir otra transcripción.",
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
        "patient": "Usuario de CAA",
        "user_prompt_intro": "Analiza la siguiente transcripción según PAALSS y escribe el informe completo.",
        "user_prompt_transcript": "TRANSCRIPCIÓN (enunciados numerados):",
        "empty_state": "Sube una transcripción para crear el primer análisis guardado.",
        "username_password_required": "Se requieren nombre de usuario y contraseña.",
        "learner": "Aprendiz",
        "date": "Fecha",
        "session": "Sesión",
        "sample": "Muestra",
        "untitled_transcript": "Transcripción sin título",
        "db_init_failed": "La inicialización de la base de datos falló. Revisa DATABASE_URL y la configuración de conexión de Supabase.",
        "db_init_help": "Si usas Supabase en Streamlit Cloud, utiliza la cadena de conexión de Supavisor en modo session pooler, no el host directo db.<project-ref>.supabase.co.",
    },
}


def t(key: str) -> str:
    lang = st.session_state.get("lang", "en")
    return STRINGS.get(lang, STRINGS["en"]).get(key, STRINGS["en"].get(key, key))


def _normalize_lang(lang: Any) -> str:
    return "es" if str(lang).strip().lower() == "es" else "en"


def _app_title(lang: Optional[str] = None) -> str:
    chosen = _normalize_lang(lang or st.session_state.get("lang", "en"))
    return APP_TITLES.get(chosen, APP_TITLES["en"])


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
        return t("untitled_transcript")
    line = re.sub(r"\s+", " ", line).strip("`\"' ")
    return line if len(line) <= max_chars else line[: max_chars - 1].rstrip() + "…"


_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _format_date(dt: datetime) -> str:
    return f"{dt.day} {_MONTH_NAMES[dt.month - 1]}, {dt.year}"


def _clean_participant_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()

    # Some source documents place several metadata fields in one paragraph.
    # Keep only the participant name and stop at the next known field label.
    name = re.split(
        r"\b(?:"
        r"actividades?\s+de\s+elicitaci[oó]n"
        r"|elicitation\s+activities?"
        r"|fecha|date|sesi[oó]n|session|muestra|sample"
        r")\s*:",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" -–—:;,.")

    unavailable = {
        "",
        "n/a",
        "na",
        "none",
        "unknown",
        "not available",
        "no disponible",
    }
    return "Unnamed Participant" if name.casefold() in unavailable else name


def _derive_title(filename: str, transcript_text: str, meta: Dict[str, Any]) -> str:
    del filename, transcript_text  # Titles are intentionally metadata-based.

    participant_name = _clean_participant_name(meta.get("learner_name"))
    timezone_name = os.getenv("APP_TIMEZONE", "America/New_York")

    try:
        created_at = datetime.now(ZoneInfo(timezone_name))
    except Exception:
        created_at = datetime.now()

    return f"[{_format_date(created_at)}] - {participant_name} Script Analysis"


# ---------------- cookies / auth ----------------


cookies = EncryptedCookieManager(prefix="paalss_auth", password=COOKIE_SECRET)
if not cookies.ready():
    st.stop()

st.session_state.setdefault("lang", _normalize_lang(cookies.get(LANGUAGE_COOKIE_KEY) or "en"))
st.set_page_config(page_title=_app_title(), page_icon="🧾", layout="wide")

_COOKIE_SAVE_DONE = False


def _save_cookies_once() -> None:
    global _COOKIE_SAVE_DONE
    if not _COOKIE_SAVE_DONE:
        cookies.save()
        _COOKIE_SAVE_DONE = True


@st.cache_resource
def _ensure_db() -> tuple[bool, str]:
    try:
        init_db()
        if not get_system_prompt("", "en"):
            set_system_prompt(get_default_system_prompt("en"), "en")
        if not get_system_prompt("", "es"):
            set_system_prompt(get_default_system_prompt("es"), "es")
        if not get_active_model(""):
            set_active_model(DEFAULT_MODEL_FROM_CONFIG)
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


_db_ready, _db_error = _ensure_db()
if not _db_ready:
    st.error(f"{t('db_init_failed')}\n\nDetails: {_db_error}")
    st.info(t("db_init_help"))
    st.stop()


def _persist_language(lang: str, save_cookie: bool = True) -> None:
    chosen = _normalize_lang(lang)
    st.session_state["lang"] = chosen
    cookies[LANGUAGE_COOKIE_KEY] = chosen
    if save_cookie:
        _save_cookies_once()
    if st.session_state.get("user_id"):
        try:
            set_user_language(str(st.session_state["user_id"]), chosen)
        except Exception:
            pass


def _login(user_id: str, role: str, language: Optional[str] = None) -> None:
    token = create_session(user_id, role)
    cookies[COOKIE_KEY] = token
    st.session_state["user_id"] = user_id
    st.session_state["role"] = role
    st.session_state["session_token"] = token
    _persist_language(language or get_user_language(user_id, st.session_state.get("lang", "en")), save_cookie=False)
    _save_cookies_once()


def _logout() -> None:
    token = st.session_state.get("session_token") or cookies.get(COOKIE_KEY)
    if token:
        try:
            delete_session(str(token))
        except Exception:
            pass
    cookies[COOKIE_KEY] = ""
    _save_cookies_once()
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
            _persist_language(get_user_language(sess["user_id"], st.session_state.get("lang", "en")))


# ---------------- state helpers ----------------



st.markdown(
    """
<style>
  section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.6rem;
  }

  /* Low-emphasis account/model metadata shown above the sidebar title. */
  section[data-testid="stSidebar"] .sidebar-session-meta {
    color: #a8acb6 !important;
    font-size: 0.78rem !important;
    line-height: 1.35 !important;
    margin: 0 0 0.35rem 0 !important;
    padding: 0 !important;
  }

  section[data-testid="stSidebar"] .sidebar-session-meta > div {
    margin: 0 !important;
    padding: 0 !important;
  }

  div.block-container {
    max-width: 100% !important;
    padding-left: 1.2rem;
    padding-right: 1.2rem;
    padding-top: 1rem !important;
  }

  /* Each saved chat is one full-width title button. The menu trigger is
     overlaid in the title's top-right corner instead of using a side column. */
  /* Keep saved-chat rows close together. Streamlit applies spacing on the
     history container's nested vertical blocks, not only on each keyed item. */
  section[data-testid="stSidebar"]
  .st-key-sidebar_analysis_section
  div[data-testid="stVerticalBlock"] {
    gap: 0.22rem !important;
  }

  section[data-testid="stSidebar"] [class*="st-key-sidebar_chat_item_"] {
    position: relative !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  > div[data-testid="stVerticalBlock"] {
    gap: 0 !important;
  }

  /* The popover is wrapped in another Streamlit element. That wrapper must
     also be absolutely positioned; otherwise it leaves a blank row below
     every chat title even when the visible three-dot button is overlaid. */
  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div:has(> div[data-testid="stPopover"]) {
    position: absolute !important;
    top: 0.32rem !important;
    right: 0.32rem !important;
    width: 1.75rem !important;
    min-width: 1.75rem !important;
    max-width: 1.75rem !important;
    height: 1.75rem !important;
    min-height: 1.75rem !important;
    margin: 0 !important;
    padding: 0 !important;
    z-index: 15 !important;
  }

  /* Let long titles wrap while reserving room for the overlaid menu button. */
  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stButton"] > button {
    white-space: normal !important;
    height: auto !important;
    min-height: 3.15rem !important;
    padding: 0.55rem 2.25rem 0.55rem 0.75rem !important;
    text-align: left !important;
  }

  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stButton"] > button p {
    width: 100% !important;
    text-align: left !important;
  }

  /* Compact three-dot menu overlaid in the title's top-right corner. */
  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] {
    position: static !important;
    top: auto !important;
    right: auto !important;
    width: 1.75rem !important;
    min-width: 1.75rem !important;
    max-width: 1.75rem !important;
    height: 1.75rem !important;
    min-height: 1.75rem !important;
    z-index: 15 !important;
  }

  /* Streamlit may place one or more wrappers between stPopover and button.
     Constrain every wrapper so the trigger cannot expand into a large box. */
  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] > div {
    width: 1.75rem !important;
    min-width: 1.75rem !important;
    max-width: 1.75rem !important;
    height: 1.75rem !important;
    min-height: 1.75rem !important;
  }

  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] button {
    width: 1.75rem !important;
    min-width: 1.75rem !important;
    max-width: 1.75rem !important;
    height: 1.75rem !important;
    min-height: 1.75rem !important;
    max-height: 1.75rem !important;
    padding: 0 !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: transparent !important;
    border: 0 !important;
    border-radius: 0.35rem !important;
    box-shadow: none !important;
    color: inherit !important;
    font-size: 0 !important;
    line-height: 1 !important;
  }

  /* Hide Streamlit's built-in label and dropdown chevron. Recreate only the
     ellipsis so the trigger is visually just three dots. */
  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] button > * {
    display: none !important;
  }

  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] button::before {
    content: "⋯";
    display: block !important;
    font-size: 1.25rem !important;
    font-weight: 600 !important;
    line-height: 1 !important;
    transform: translateY(-0.08rem);
  }

  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] button:hover {
    background: rgba(128, 128, 128, 0.10) !important;
  }

  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] button:focus,
  section[data-testid="stSidebar"]
  [class*="st-key-sidebar_chat_item_"]
  div[data-testid="stPopover"] button:focus-visible {
    background: rgba(128, 128, 128, 0.10) !important;
    box-shadow: none !important;
    outline: none !important;
  }

  /* Sidebar layout: keep account controls at the bottom while only the
     analysis history scrolls. Streamlit renders keyed st.container blocks
     inside stLayoutWrapper elements, so the wrapper—not stElementContainer—
     must be the flex item. */
  section[data-testid="stSidebar"] div[data-testid="stSidebarContent"] {
    height: 100dvh !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
  }

  section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] {
    flex: 0 0 auto !important;
  }

  section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    overflow: hidden !important;
    padding-bottom: 0.5rem !important;
  }

  section[data-testid="stSidebar"]
  div[data-testid="stSidebarUserContent"]
  > div[data-testid="stVerticalBlock"] {
    height: 100% !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
  }

  /* The keyed analysis container is wrapped by stLayoutWrapper. Give that
     wrapper all remaining height and make the chat list independently scroll. */
  section[data-testid="stSidebar"]
  div[data-testid="stSidebarUserContent"]
  > div[data-testid="stVerticalBlock"]
  > div[data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_analysis_section) {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
  }

  section[data-testid="stSidebar"] .st-key-sidebar_analysis_section {
    height: 100% !important;
    max-height: calc(100dvh - 19rem) !important;
    min-height: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding-right: 0.25rem !important;
    padding-bottom: 0.75rem !important;
  }

  /* The account controls remain outside the scrolling history and stay at the
     bottom of the sidebar, regardless of the number of saved chats. */
  section[data-testid="stSidebar"]
  div[data-testid="stSidebarUserContent"]
  > div[data-testid="stVerticalBlock"]
  > div[data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_account_actions) {
    flex: 0 0 auto !important;
    margin-top: auto !important;
  }

  section[data-testid="stSidebar"] .st-key-sidebar_account_actions {
    position: sticky !important;
    bottom: 0 !important;
    z-index: 20 !important;
    flex: 0 0 auto !important;
    padding-top: 0.45rem !important;
    padding-bottom: 0.25rem !important;
    background: var(--secondary-background-color) !important;
    border-top: 1px solid rgba(128, 128, 128, 0.45) !important;
    box-shadow: 0 -0.5rem 0.9rem rgba(0, 0, 0, 0.05) !important;
  }

  section[data-testid="stSidebar"] .st-key-sidebar_account_actions hr {
    display: none !important;
  }
</style>
""",
    unsafe_allow_html=True,
)

st.session_state.setdefault("page", "analyzer")
st.session_state.setdefault("uploader_nonce", 0)
st.session_state.setdefault("suppress_autoload", False)


def _fmt_ts(value: Any) -> str:
    s = str(value or "")
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return _format_date(dt)
    except Exception:
        return s


def _patient_display(patient_id: Any, known_patient_ids: Optional[set[str]] = None) -> str:
    clean_id = str(patient_id or "").strip()
    if not clean_id:
        return t("unnamed_aac_user")
    if known_patient_ids is not None and clean_id not in known_patient_ids:
        return t("unnamed_aac_user")
    return clean_id



PAALSS_EXPORT_COLUMNS: Tuple[str, ...] = (
    "Clinician ID",
    "AAC User ID",
    "Transcript #",
    "Gender",
    "Age",
    "Length",
    "Elicitation Activity",
    "Total Number of Utterances (ENUNCIADOS)",
    "MLUw",
    "Total Number of Words (TNW) (PALABRAS)",
    "Total Number of Different Words (TNDW) (PALABRAS DIFERENTES)",
    "Total Number of Different Nouns (SUSTANTIVOS)",
    "Total Number of Nouns ",
    "Total Number of Different Verbs        (VERBOS)",
    "Total Number of Verbs ",
    "Total Number of Different Pronouns and Determinants (PRONOMBRES Y DETERMINANTES)",
    "Total Number of Different Adverbs (ADVERBIOS)",
    "Total Number of Different Adjectives (ADJETIVOS)",
    "Total Number of Different Substitutes (SUSTITUTOS)",
    "Total Number of Different Articles (ARTÍCULOS)",
    "Total Number of Different Numerals (NUMERALES)",
    "Total Number of Different Prepositions (PREPOSICIONES)",
    "Total Number of Different Interjections (INTERJECCIONES)",
    "Total Number of Different Conjunctions (CONJUNCIONES)",
    "Total Number of Different Morphological Structures MORFOLÓLOGICAS DIFERENTES",
    "Total Number of Morphological Structures MORFOLÓGICAS",
    "Grammatical Complexity Score COMPLEJIDAD GRAMATICAL",
    "Total Number of Different Syntactic Structures ESTRUCTURAS SINÁCTICAS DIFERENTES",
    "Total Number of Syntactic Structures ESTRUCTURAS SINTÁCTICAS",
)

_EXPORT_MISSING_VALUES = {
    "", "na", "n/a", "none", "null", "unknown", "not provided",
    "not available", "no proporcionado", "no disponible",
}


def _export_value(value: Any) -> str:
    clean = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n:;,-–—")
    return "NA" if clean.casefold() in _EXPORT_MISSING_VALUES else clean


def _report_lines(report_text: str) -> List[str]:
    lines: List[str] = []
    for raw_line in str(report_text or "").splitlines():
        line = raw_line.strip()
        line = re.sub(r"^\s*[-*•]+\s*", "", line)
        line = line.replace("**", "").replace("__", "").replace("`", "")
        if line:
            lines.append(line)
    return lines


def _number_from_text(value: str) -> Optional[str]:
    match = re.search(r"(?<![\w])(-?\d+(?:[.,]\d+)?)", str(value or ""))
    if not match:
        return None
    number = match.group(1)
    if "," in number and "." not in number:
        left, right = number.split(",", 1)
        number = f"{left}.{right}" if len(right) <= 2 else f"{left}{right}"
    return number


def _extract_report_number(report_text: str, labels: Tuple[str, ...]) -> str:
    lines = _report_lines(report_text)
    for label in labels:
        label_pattern = re.escape(label).replace(r"\ ", r"\s+")
        pattern = re.compile(
            rf"^(?:\d+[.)]\s*)?{label_pattern}(?=\s|:|\(|-|=|$)(.*)$",
            flags=re.IGNORECASE,
        )
        for line in lines:
            matched = pattern.match(line)
            if not matched:
                continue
            number = _number_from_text(matched.group(1).strip())
            if number is not None:
                return number
    return "NA"


def _sum_report_numbers(first: str, second: str) -> str:
    if first == "NA" or second == "NA":
        return "NA"
    try:
        total = float(first) + float(second)
    except (TypeError, ValueError):
        return "NA"
    return str(int(total)) if total.is_integer() else str(total)


def _first_meta_value(meta: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    normalized = {str(key).casefold(): value for key, value in (meta or {}).items()}
    for key in keys:
        clean = _export_value(normalized.get(key.casefold()))
        if clean != "NA":
            return clean
    return "NA"


def _sample_information_text(report_text: str) -> str:
    text = str(report_text or "")
    section_two = re.search(r"(?m)^\s*2\s*[.)]\s+", text)
    return text[: section_two.start()] if section_two else text


def _extract_report_text(report_text: str, labels: Tuple[str, ...]) -> str:
    for label in labels:
        label_pattern = re.escape(label).replace(r"\ ", r"\s+")
        pattern = re.compile(
            rf"^(?:\d+[.)]\s*)?{label_pattern}\s*[:=-]\s*(.+)$",
            flags=re.IGNORECASE,
        )
        for line in _report_lines(report_text):
            matched = pattern.match(line)
            if matched:
                clean = _export_value(matched.group(1))
                if clean != "NA":
                    return clean
    return "NA"


def _extract_labeled_text(sources: List[str], labels: Tuple[str, ...]) -> str:
    all_labels = (
        "Gender", "Sex", "Género", "Genero", "Sexo", "Age", "Edad",
        "Length", "Duration", "Recording Length", "Recording Duration",
        "Duración", "Duracion", "Duración de la grabación", "Duracion de la grabacion",
        "Elicitation Activity", "Elicitation Activities", "Actividad de elicitación",
        "Actividades de elicitación", "Actividad de elicitacion", "Actividades de elicitacion",
        "Learner", "Aprendiz", "Date", "Fecha", "Session", "Sesión", "Sesion",
        "Sample", "Muestra", "Interlocutor", "Nombre de la/el interlocutor",
    )
    next_label_pattern = "|".join(
        re.escape(item).replace(r"\ ", r"\s+") for item in all_labels
    )
    for source in sources:
        source_text = str(source or "")
        for label in labels:
            label_pattern = re.escape(label).replace(r"\ ", r"\s+")
            pattern = re.compile(
                rf"{label_pattern}\s*:\s*(.+?)(?=\s+(?:{next_label_pattern})\s*:|$)",
                flags=re.IGNORECASE | re.DOTALL,
            )
            matched = pattern.search(source_text)
            if matched:
                clean = _export_value(matched.group(1))
                if clean != "NA":
                    return clean
    return "NA"


def _analysis_export_row(record: Dict[str, Any]) -> List[str]:
    report_text = str(record.get("report_text") or "")
    meta = record.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}

    sample_info = _sample_information_text(report_text)
    metadata_sources = [
        str(value) for value in meta.values() if value is not None and str(value).strip()
    ] + [sample_info]

    gender = _first_meta_value(meta, ("gender", "sex", "género", "genero", "sexo"))
    if gender == "NA":
        gender = _extract_labeled_text(
            metadata_sources, ("Gender", "Sex", "Género", "Genero", "Sexo")
        )

    age = _first_meta_value(meta, ("age", "edad"))
    if age == "NA":
        age = _extract_labeled_text(metadata_sources, ("Age", "Edad"))

    length = _first_meta_value(
        meta,
        (
            "length", "duration", "recording_length", "recording_duration",
            "duración", "duracion", "duración_de_la_grabación",
            "duracion_de_la_grabacion",
        ),
    )
    if length == "NA":
        length = _extract_labeled_text(
            metadata_sources,
            (
                "Recording Length", "Recording Duration", "Duration", "Length",
                "Duración de la grabación", "Duracion de la grabacion",
                "Duración", "Duracion",
            ),
        )

    elicitation = _first_meta_value(
        meta,
        (
            "elicitation_activity", "elicitation_activities", "activity", "activities",
            "actividad_de_elicitación", "actividades_de_elicitación",
            "actividad_de_elicitacion", "actividades_de_elicitacion",
        ),
    )
    if elicitation == "NA":
        elicitation = _extract_labeled_text(
            metadata_sources,
            (
                "Elicitation Activity", "Elicitation Activities",
                "Actividad de elicitación", "Actividades de elicitación",
                "Actividad de elicitacion", "Actividades de elicitacion",
            ),
        )

    pronouns_and_determiners = _extract_report_number(
        report_text,
        (
            "Pronouns + Determiners", "Pronouns and Determiners",
            "Pronombres + Determinantes", "Pronombres y Determinantes",
        ),
    )
    if pronouns_and_determiners == "NA":
        pronouns_and_determiners = _sum_report_numbers(
            _extract_report_number(report_text, ("Pronouns", "Pronombres")),
            _extract_report_number(report_text, ("Determiners", "Determinantes")),
        )

    transcript_number = _first_meta_value(
        meta,
        ("transcript_number", "transcript_no", "transcript_id", "sample", "sample_id", "muestra"),
    )
    if transcript_number == "NA":
        transcript_number = _extract_report_text(
            sample_info,
            ("Transcript #", "Transcript Number", "Sample ID", "Número de transcripción", "Muestra"),
        )
    if transcript_number == "NA":
        transcript_number = _export_value(record.get("id"))

    values = {
        "Clinician ID": _export_value(record.get("user_id")),
        "AAC User ID": _export_value(record.get("patient_id")),
        "Transcript #": transcript_number,
        "Gender": gender,
        "Age": age,
        "Length": length,
        "Elicitation Activity": elicitation,
        "Total Number of Utterances (ENUNCIADOS)": _extract_report_number(
            report_text,
            (
                "Total Utterances (Enunciados)", "Total Number of Utterances",
                "Number of Utterances", "Número total de enunciados", "Total de enunciados",
            ),
        ),
        "MLUw": _extract_report_number(
            report_text,
            (
                "MLUw (Rounded)", "MLUw", "Mean Length of Utterance in words",
                "Mean Length of Utterance (MLU)",
                "Longitud media del enunciado en palabras",
                "Longitud media del enunciado",
            ),
        ),
        "Total Number of Words (TNW) (PALABRAS)": _extract_report_number(
            report_text,
            ("Total Number of Words (TNW)", "TNW", "Número total de palabras (TNW)"),
        ),
        "Total Number of Different Words (TNDW) (PALABRAS DIFERENTES)": _extract_report_number(
            report_text,
            (
                "Total Number of Different Words (TNDW)", "TNDW",
                "Número total de palabras diferentes (TNDW)",
            ),
        ),
        "Total Number of Different Nouns (SUSTANTIVOS)": _extract_report_number(
            report_text,
            ("Noun Types", "Different Nouns", "Nouns", "Tipos de sustantivos", "Sustantivos"),
        ),
        "Total Number of Nouns ": _extract_report_number(
            report_text,
            ("Noun Tokens", "Total Nouns", "Total Number of Nouns", "Tokens de sustantivos", "Total de sustantivos"),
        ),
        "Total Number of Different Verbs        (VERBOS)": _extract_report_number(
            report_text,
            ("Verb Types", "Different Verbs", "Tipos verbales", "Tipos de verbos"),
        ),
        "Total Number of Verbs ": _extract_report_number(
            report_text,
            ("Verb Tokens", "Total Verbs", "Total Number of Verbs", "Tokens verbales", "Total de verbos"),
        ),
        "Total Number of Different Pronouns and Determinants (PRONOMBRES Y DETERMINANTES)": pronouns_and_determiners,
        "Total Number of Different Adverbs (ADVERBIOS)": _extract_report_number(report_text, ("Adverbs", "Adverbios")),
        "Total Number of Different Adjectives (ADJETIVOS)": _extract_report_number(report_text, ("Adjectives", "Adjetivos")),
        "Total Number of Different Substitutes (SUSTITUTOS)": _extract_report_number(report_text, ("Substitutes", "Sustitutos")),
        "Total Number of Different Articles (ARTÍCULOS)": _extract_report_number(report_text, ("Articles", "Artículos", "Articulos")),
        "Total Number of Different Numerals (NUMERALES)": _extract_report_number(report_text, ("Numerals", "Numerales")),
        "Total Number of Different Prepositions (PREPOSICIONES)": _extract_report_number(report_text, ("Prepositions", "Preposiciones")),
        "Total Number of Different Interjections (INTERJECCIONES)": _extract_report_number(report_text, ("Interjections", "Interjecciones")),
        "Total Number of Different Conjunctions (CONJUNCIONES)": _extract_report_number(report_text, ("Conjunctions", "Conjunciones")),
        "Total Number of Different Morphological Structures MORFOLÓLOGICAS DIFERENTES": _extract_report_number(
            report_text,
            (
                "Total Different Morphological Structures Observed",
                "Total Different Morphological Structures",
                "Total de estructuras morfológicas diferentes observadas",
                "Total de estructuras morfológicas diferentes",
            ),
        ),
        "Total Number of Morphological Structures MORFOLÓGICAS": _extract_report_number(
            report_text,
            (
                "Total Morphological Marking Observed",
                "Total Morphological Structures Observed",
                "Total Morphological Structures",
                "Total de marcación morfológica observada",
                "Total de estructuras morfológicas observadas",
            ),
        ),
        "Grammatical Complexity Score COMPLEJIDAD GRAMATICAL": _extract_report_number(
            report_text,
            (
                "Total Grammatical Complexity Score",
                "Total Grammatical Complexity Points",
                "Grammatical Complexity Score",
                "Puntuación total de complejidad gramatical",
                "Puntos totales de complejidad gramatical",
            ),
        ),
        "Total Number of Different Syntactic Structures ESTRUCTURAS SINÁCTICAS DIFERENTES": _extract_report_number(
            report_text,
            (
                "Total Different Syntactic Structures Observed",
                "Total Different Syntactic Structures",
                "Total de estructuras sintácticas diferentes observadas",
                "Total de estructuras sintácticas diferentes",
            ),
        ),
        "Total Number of Syntactic Structures ESTRUCTURAS SINTÁCTICAS": _extract_report_number(
            report_text,
            (
                "Total Syntactic Structures Observed",
                "Total Syntactic Structures",
                "Total de estructuras sintácticas observadas",
                "Total de estructuras sintácticas",
            ),
        ),
    }
    return [_export_value(values.get(column)) for column in PAALSS_EXPORT_COLUMNS]


def _excel_column_name(index: int) -> str:
    name = ""
    current = index
    while current:
        current, remainder = divmod(current - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_inline_cell(cell_ref: str, value: Any, style_id: int) -> str:
    text = str(value if value is not None else "NA")
    preserve = ' xml:space="preserve"' if text != text.strip() else ""
    return (
        f'<c r="{cell_ref}" s="{style_id}" t="inlineStr">'
        f'<is><t{preserve}>{escape(text)}</t></is></c>'
    )


def _analyses_sheet_bytes(records: List[Dict[str, Any]]) -> bytes:
    headers = list(PAALSS_EXPORT_COLUMNS)
    all_row_values = [_analysis_export_row(record) for record in records]
    last_column = _excel_column_name(len(headers))
    last_row = len(all_row_values) + 1

    column_xml: List[str] = []
    for index, header in enumerate(headers, start=1):
        column_values = [str(row[index - 1]) for row in all_row_values]
        longest = max([len(str(header)), *[len(value) for value in column_values]])
        width = max(12.0, min(42.0, longest * 0.9 + 2.0))
        column_xml.append(
            f'<col min="{index}" max="{index}" width="{width:.1f}" customWidth="1"/>'
        )

    header_cells = "".join(
        _xlsx_inline_cell(f"{_excel_column_name(index)}1", header, 1)
        for index, header in enumerate(headers, start=1)
    )

    data_rows: List[str] = []
    for row_number, row_values in enumerate(all_row_values, start=2):
        data_cells = "".join(
            _xlsx_inline_cell(
                f"{_excel_column_name(index)}{row_number}",
                value,
                2,
            )
            for index, value in enumerate(row_values, start=1)
        )
        data_rows.append(
            f'<row r="{row_number}" ht="30" customHeight="1">{data_cells}</row>'
        )

    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="18"/>
  <cols>{''.join(column_xml)}</cols>
  <sheetData>
    <row r="1" ht="66" customHeight="1">{header_cells}</row>
    {''.join(data_rows)}
  </sheetData>
  <autoFilter ref="A1:{last_column}{last_row}"/>
</worksheet>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left style="thin"><color rgb="FFD9E2F3"/></left><right style="thin"><color rgb="FFD9E2F3"/></right><top style="thin"><color rgb="FFD9E2F3"/></top><bottom style="thin"><color rgb="FFD9E2F3"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''

    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''

    workbook_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews>
  <sheets><sheet name="PAALSS Admin Data View" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''

    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    core_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>PAALSS Transcript Analyzer</dc:creator>
  <cp:lastModifiedBy>PAALSS Transcript Analyzer</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>
</cp:coreProperties>'''

    app_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>PAALSS Transcript Analyzer</Application>
</Properties>'''

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("docProps/app.xml", app_xml)
    return output.getvalue()


def _analysis_sheet_bytes(record: Dict[str, Any]) -> bytes:
    return _analyses_sheet_bytes([record])


def _all_chats_sheet_filename() -> str:
    return f"PAALSS_all_chats_{datetime.now().strftime('%Y-%m-%d')}.xlsx"


def _sheet_filename(record: Dict[str, Any]) -> str:
    clinician = _export_value(record.get("user_id"))
    patient = _export_value(record.get("patient_id"))
    transcript_number = _analysis_export_row(record)[2]
    stem = f"PAALSS_{clinician}_{patient}_{transcript_number}"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return f"{safe_stem or 'PAALSS_analysis'}.xlsx"


def _notify_success(message: str) -> None:
    try:
        st.toast(message)
    except Exception:
        st.success(message)


def _clear_analysis_state() -> None:
    for key in [
        "active_analysis_id",
        "editor_title",
        "editor_transcript_text",
        "editor_source_filename",
        "editor_meta",
        "report_text",
        "recommendation_text",
        "selected_patient_id",
    ]:
        st.session_state.pop(key, None)


def _apply_pending_analysis_state() -> None:
    # Dialog widgets rerun independently. Apply changes here, before the main
    # editor widgets are instantiated, to avoid Session State widget errors.
    pending_title = st.session_state.pop("_pending_editor_title", None)
    if pending_title is not None:
        st.session_state["editor_title"] = str(pending_title)

    if st.session_state.pop("_pending_clear_analysis_state", False):
        _clear_analysis_state()
        st.session_state["suppress_autoload"] = False

    if st.session_state.pop("_pending_selected_patient_clear", False):
        st.session_state.pop("selected_patient_id", None)


_dialog = getattr(st, "dialog", None) or getattr(st, "experimental_dialog")


@_dialog(t("rename_chat"))
def _rename_chat_dialog(analysis_id: int, current_title: str) -> None:
    new_title = st.text_input(
        t("chat_title"),
        value=current_title,
        key=f"rename_chat_input_{analysis_id}",
    )

    save_col, cancel_col = st.columns(2)

    if save_col.button(
        t("save"),
        type="primary",
        use_container_width=True,
        key=f"save_rename_{analysis_id}",
    ):
        clean_title = new_title.strip()
        if not clean_title:
            st.error(t("title_required"))
            return

        renamed = rename_analysis_for_user(
            analysis_id=int(analysis_id),
            user_id=str(st.session_state["user_id"]),
            title=clean_title,
            is_admin=st.session_state.get("role") == "admin",
        )
        if not renamed:
            st.error(t("rename_failed"))
            return

        if int(st.session_state.get("active_analysis_id") or 0) == int(analysis_id):
            st.session_state["_pending_editor_title"] = clean_title

        _notify_success(t("chat_renamed"))
        st.rerun()

    if cancel_col.button(
        t("cancel"),
        use_container_width=True,
        key=f"cancel_rename_{analysis_id}",
    ):
        st.rerun()


@_dialog(t("delete_chat_title"))
def _delete_chat_dialog(analysis_id: int, current_title: str) -> None:
    st.markdown(f"**{current_title}**")
    st.warning(t("delete_chat_warning"))

    delete_col, cancel_col = st.columns(2)

    if delete_col.button(
        t("confirm_delete"),
        type="primary",
        use_container_width=True,
        key=f"confirm_delete_{analysis_id}",
    ):
        deleted = delete_analysis_for_user(
            analysis_id=int(analysis_id),
            user_id=str(st.session_state["user_id"]),
            is_admin=st.session_state.get("role") == "admin",
        )
        if not deleted:
            st.error(t("delete_failed"))
            return

        if int(st.session_state.get("active_analysis_id") or 0) == int(analysis_id):
            st.session_state["_pending_clear_analysis_state"] = True

        _notify_success(t("chat_deleted"))
        st.rerun()

    if cancel_col.button(
        t("cancel"),
        use_container_width=True,
        key=f"cancel_delete_{analysis_id}",
    ):
        st.rerun()


def _record_accessible(record: Optional[Dict[str, Any]]) -> bool:
    if not record:
        return False
    if st.session_state.get("role") == "admin":
        return True
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
    title = str(st.session_state.get("editor_title") or "").strip() or t("untitled_transcript")
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
    patient_id = str(st.session_state.get("selected_patient_id") or "").strip()
    if not patient_id:
        st.error(t("select_patient_first"))
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
        patient_id=patient_id,
    )
    _load_analysis_into_state(int(analysis_id))
    st.session_state["uploader_nonce"] = int(st.session_state.get("uploader_nonce", 0)) + 1
    st.session_state["_pending_selected_patient_clear"] = True
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


def _set_language(lang: str) -> None:
    chosen = _normalize_lang(lang)
    _persist_language(chosen)


def _select_english(prefix: str) -> None:
    st.session_state[f"{prefix}_lang_en"] = True
    st.session_state[f"{prefix}_lang_es"] = False
    _set_language("en")


def _select_spanish(prefix: str) -> None:
    st.session_state[f"{prefix}_lang_en"] = False
    st.session_state[f"{prefix}_lang_es"] = True
    _set_language("es")


def _render_language_checkboxes(prefix: str) -> None:
    current = _normalize_lang(st.session_state.get("lang", "en"))
    st.session_state[f"{prefix}_lang_en"] = current == "en"
    st.session_state[f"{prefix}_lang_es"] = current == "es"
    cols = st.columns(2)
    with cols[0]:
        st.checkbox("English", key=f"{prefix}_lang_en", on_change=_select_english, args=(prefix,))
    with cols[1]:
        st.checkbox("Español", key=f"{prefix}_lang_es", on_change=_select_spanish, args=(prefix,))


def _render_login() -> None:
    st.title(_app_title())
    if not any_admin_exists():
        st.subheader(t("bootstrap_title"))
        st.caption(t("bootstrap_caption"))
        with st.form("bootstrap_admin_form"):
            username = st.text_input(t("username"))
            password = st.text_input(t("password"), type="password")
            submitted = st.form_submit_button(t("create_admin"))
        if submitted:
            if not username.strip() or not password:
                st.error(t("username_password_required"))
            else:
                upsert_user(username.strip(), password, "admin", language=st.session_state.get("lang", "en"))
                _login(username.strip(), "admin", st.session_state.get("lang", "en"))
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
            _login(auth["user_id"], auth["role"], auth.get("language", st.session_state.get("lang", "en")))
            st.rerun()


def _render_sidebar(models: List[str]) -> None:
    with st.sidebar:
        is_admin = st.session_state.get("role") == "admin"
        role_key = "role_admin" if is_admin else "role_user"
        current_model = get_active_model(DEFAULT_MODEL_FROM_CONFIG)

        # Keep account/model details visible but intentionally low-emphasis.
        # They appear above the app title because they are secondary metadata.
        st.markdown(
            f"""
            <div class="sidebar-session-meta">
                <div>{escape(t('signed_in_as'))}: {escape(str(st.session_state['user_id']))} ({escape(t(role_key))})</div>
                <div>{escape(t('active_model'))}: {escape(str(current_model))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(f"## {_app_title()}")
        _render_language_checkboxes("sidebar")

        if is_admin:
            st.radio(
                t("navigation"),
                options=["analyzer", "admin"],
                format_func=lambda x: t("analyzer") if x == "analyzer" else t("admin"),
                key="page",
                horizontal=True,
                label_visibility="collapsed",
            )

        if st.button(t("new_analysis"), use_container_width=True):
            st.session_state["suppress_autoload"] = True
            _clear_analysis_state()
            st.rerun()

        # Keep the original sidebar focused only on the current clinician's
        # saved chats. Search and filters live in the main Search tab.
        with st.container(key="sidebar_analysis_section"):
            st.markdown(f"### {t('previous_analyses')}")
            rows = list_analyses_for_user(str(st.session_state["user_id"]), limit=200)
            if rows:
                for row in rows:
                    rid = int(row["id"])
                    label = str(
                        row.get("title")
                        or row.get("source_filename")
                        or f"Analysis {rid}"
                    )

                    with st.container(key=f"sidebar_chat_item_{rid}"):
                        if st.button(
                            label,
                            key=f"analysis_btn_{rid}",
                            use_container_width=True,
                        ):
                            _load_analysis_into_state(rid)
                            st.rerun()

                        with st.popover("⋯", use_container_width=False):
                            if st.button(
                                t("rename_chat"),
                                key=f"rename_chat_{rid}",
                                use_container_width=True,
                            ):
                                _rename_chat_dialog(rid, label)

                            if st.button(
                                t("delete_chat"),
                                key=f"delete_chat_{rid}",
                                use_container_width=True,
                            ):
                                _delete_chat_dialog(rid, label)
            else:
                st.caption(t("no_previous_analyses"))

        with st.container(key="sidebar_account_actions"):
            st.divider()

            with st.expander(t("change_password")):
                current_pw = st.text_input(
                    t("current_password"),
                    type="password",
                    key="cp_current",
                )
                new_pw = st.text_input(
                    t("new_password"),
                    type="password",
                    key="cp_new",
                )
                if st.button(t("update_password"), use_container_width=True):
                    if change_user_password(
                        str(st.session_state["user_id"]),
                        current_pw,
                        new_pw,
                    ):
                        _notify_success(t("password_changed"))
                    else:
                        st.error(t("password_change_failed"))

            if st.button(t("logout"), use_container_width=True):
                _logout()
                st.rerun()


def _render_admin_page(models: List[str]) -> None:
    st.title(t("admin"))
    tab_system, tab_users, tab_patients = st.tabs(
        [t("system_settings"), t("users"), t("aac_users_patients")]
    )

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
        current_lang = _normalize_lang(st.session_state.get("lang", "en"))
        prompt_value = get_system_prompt(get_default_system_prompt(current_lang), current_lang)
        prompt_edit = st.text_area(t("prompt_editor"), value=prompt_value, height=520)
        pcols = st.columns([0.5, 0.5])
        if pcols[0].button(t("save_prompt"), type="primary", use_container_width=True):
            set_system_prompt(prompt_edit, current_lang)
            _notify_success(t("prompt_saved"))
        if pcols[1].button(t("reset_prompt"), use_container_width=True):
            set_system_prompt(get_default_system_prompt(current_lang), current_lang)
            _notify_success(t("prompt_saved"))
            st.rerun()

    with tab_users:
        st.subheader(t("create_or_update_user"))
        with st.form("create_or_update_user_form"):
            username = st.text_input(t("clinician_username"))
            password = st.text_input(t("clinician_password"), type="password")
            role = st.selectbox(
                t("role"),
                ["user", "admin"],
                format_func=lambda x: t("role_admin") if x == "admin" else t("role_user"),
            )
            submitted = st.form_submit_button(t("save_user"))
        if submitted:
            if not username.strip() or not password:
                st.error(t("clinician_credentials_required"))
            else:
                upsert_user(username.strip(), password, role)
                _notify_success(t("user_saved"))
                st.rerun()

        st.subheader(t("existing_users"))
        rows = list_users()
        if rows:
            pretty_rows: List[Dict[str, Any]] = []
            for row in rows:
                pretty_rows.append({
                    t("clinician_username"): row.get("user_id"),
                    t("role"): t("role_admin") if row.get("role") == "admin" else t("role_user"),
                    t("language"): "Español" if row.get("language") == "es" else "English",
                })
            st.dataframe(pretty_rows, use_container_width=True)

    with tab_patients:
        st.subheader(t("add_aac_user"))
        with st.form("create_or_update_aac_user_form"):
            patient_id = st.text_input(t("aac_user_id"))
            patient_submitted = st.form_submit_button(t("save_aac_user"))
        if patient_submitted:
            if not patient_id.strip():
                st.error(t("aac_user_required"))
            elif upsert_aac_user(patient_id.strip()):
                _notify_success(t("aac_user_saved"))
                st.rerun()

        st.subheader(t("existing_aac_users"))
        patient_rows = list_aac_users()
        if patient_rows:
            st.dataframe(
                [{t("aac_user_id"): row.get("patient_id")} for row in patient_rows],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption(t("no_aac_users"))


def _render_chat_tab() -> None:
    record = _current_record()

    left, right = st.columns([0.56, 0.44], gap="large")

    with left:
        if not record:
            st.subheader(t("upload_title"))
            st.caption(t("upload_help"))

            patient_rows = list_aac_users()
            patient_ids = [
                str(row.get("patient_id") or "").strip()
                for row in patient_rows
                if str(row.get("patient_id") or "").strip()
            ]
            selected_patient_id = st.selectbox(
                t("aac_user_patient"),
                options=[""] + patient_ids,
                format_func=lambda value: t("select_aac_user") if not value else value,
                key="selected_patient_id",
            )

            if not patient_ids:
                st.warning(t("no_aac_users"))
            elif not selected_patient_id:
                st.info(t("select_patient_first"))

            uploaded = st.file_uploader(
                t("uploader_label"),
                type=["docx", "txt"],
                accept_multiple_files=False,
                disabled=not bool(selected_patient_id),
                key=f"transcript_uploader_{st.session_state.get('uploader_nonce', 0)}",
            )
            if uploaded is not None:
                _create_analysis_from_upload(uploaded)

            st.info(t("empty_state"))
            return

        st.caption(t("start_new_to_upload"))

        meta = st.session_state.get("editor_meta") or {}
        if meta:
            st.markdown(f"**{t('detected_info')}**")
            for key, label in [("learner_name", t("learner")), ("date_iso", t("date")), ("date_raw", t("date")), ("session", t("session")), ("sample", t("sample"))]:
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

            current_lang = _normalize_lang(st.session_state.get("lang", "en"))
            current_prompt = get_system_prompt(get_default_system_prompt(current_lang), current_lang)
            update_analysis(
                int(record["id"]),
                title=str(st.session_state.get("editor_title") or record.get("title") or t("untitled_transcript")),
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
                    lang=current_lang,
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
                # The editor widgets have already been instantiated in this run.
                # Reloading their keyed Session State values here raises a
                # StreamlitAPIException. The generated output is already saved
                # to the database, so rerun and let the next script execution
                # read the updated record safely.
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
        known_patient_ids = {
            str(row.get("patient_id") or "").strip()
            for row in list_aac_users()
            if str(row.get("patient_id") or "").strip()
        }
        st.caption(f"{t('clinician_id')}: {record.get('user_id') or '—'}")
        st.caption(
            f"{t('patient')}: "
            f"{_patient_display(record.get('patient_id'), known_patient_ids)}"
        )
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


def _render_search_tab() -> None:
    is_admin = st.session_state.get("role") == "admin"
    current_user_id = str(st.session_state["user_id"])

    st.subheader(t("search_chats"))

    patient_rows = list_aac_users()
    patient_ids = sorted(
        {
            str(row.get("patient_id") or "").strip()
            for row in patient_rows
            if str(row.get("patient_id") or "").strip()
        },
        key=str.lower,
    )
    known_patient_ids = set(patient_ids)

    search_query = st.text_input(
        t("search_chats"),
        placeholder=t("search_placeholder"),
        key="search_page_query",
        label_visibility="collapsed",
    )

    filter_cols = st.columns(2, gap="medium")
    clinician_filter = ""
    with filter_cols[0]:
        if is_admin:
            clinician_ids = sorted(
                {
                    str(row.get("user_id") or "").strip()
                    for row in list_users()
                    if str(row.get("user_id") or "").strip()
                },
                key=str.lower,
            )
            clinician_filter = st.selectbox(
                t("clinician_id"),
                options=[""] + clinician_ids,
                format_func=lambda value: t("all_clinicians") if not value else value,
                key="search_page_clinician_filter",
            )
        else:
            st.text_input(
                t("clinician_id"),
                value=current_user_id,
                disabled=True,
                key="search_page_current_clinician",
            )

    with filter_cols[1]:
        patient_filter = st.selectbox(
            t("aac_user_patient"),
            options=["", "__unnamed__"] + patient_ids,
            format_func=lambda value: (
                t("all_aac_users")
                if not value
                else t("unnamed_aac_user")
                if value == "__unnamed__"
                else value
            ),
            key="search_page_patient_filter",
        )

    rows = search_analyses(
        current_user_id=current_user_id,
        is_admin=is_admin,
        query=search_query,
        clinician_id=clinician_filter,
        patient_filter=patient_filter,
        limit=2_147_483_647,
    )

    if not rows:
        st.info(t("no_matching_analyses"))
        return

    full_records_by_id: Dict[int, Dict[str, Any]] = {}
    full_records: List[Dict[str, Any]] = []
    for row in rows:
        rid = int(row["id"])
        full_record = get_analysis(rid)
        if full_record and _record_accessible(full_record):
            full_records_by_id[rid] = full_record
            full_records.append(full_record)

    if full_records:
        st.download_button(
            t("export_all_chats"),
            data=_analyses_sheet_bytes(full_records),
            file_name=_all_chats_sheet_filename(),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="search_export_all_chats_sheet",
            use_container_width=True,
            type="primary",
        )

    st.caption(f"{len(rows)} result{'s' if len(rows) != 1 else ''}")
    for row in rows:
        rid = int(row["id"])
        label = str(
            row.get("title")
            or row.get("source_filename")
            or f"Analysis {rid}"
        )
        clinician_label = str(row.get("user_id") or "")
        patient_label = _patient_display(row.get("patient_id"), known_patient_ids)

        with st.container(border=True):
            title_col, export_col = st.columns([0.72, 0.28], vertical_alignment="center")
            with title_col:
                st.markdown(f"**{label}**")
                st.caption(
                    f"{t('clinician_id')}: {clinician_label} · "
                    f"{t('patient')}: {patient_label} · "
                    f"{t('updated')}: {_fmt_ts(row.get('updated_at'))}"
                )
                if row.get("source_filename"):
                    st.caption(f"{t('filename')}: {row.get('source_filename')}")
            with export_col:
                full_record = full_records_by_id.get(rid)
                if full_record:
                    st.download_button(
                        t("export_sheet"),
                        data=_analysis_sheet_bytes(full_record),
                        file_name=_sheet_filename(full_record),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"search_export_sheet_{rid}",
                        use_container_width=True,
                        type="primary",
                    )


def _render_analyzer_page() -> None:
    _ensure_active_selection()
    st.title(_app_title())

    chat_tab, search_tab = st.tabs([t("chat_tab"), t("search_tab")])
    with chat_tab:
        _render_chat_tab()
    with search_tab:
        _render_search_tab()


# ---------------- app ----------------


def main() -> None:
    _apply_pending_analysis_state()

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
