import streamlit as st
import pandas as pd
import json
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Configuración
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]
REDIRECT_URI = "https://classroomauto-waii8w8kkpdnbm9226rdwu.streamlit.app/"

def get_credentials():
    if "creds" in st.session_state:
        return st.session_state.creds

    client_config = json.loads(st.secrets["CREDENTIALS_JSON"])
    client_id = client_config["web"]["client_id"]
    client_secret = client_config["web"]["client_secret"]
    token_uri = client_config["web"]["token_uri"]

    # Paso de intercambio manual
    if "code" in st.query_params:
        code = st.query_params["code"]
        data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        
        response = requests.post(token_uri, data=data)
        token_data = response.json()

        if "access_token" in token_data:
            st.session_state.creds = Credentials(
                token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=SCOPES
            )
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Error en intercambio: {token_data.get('error')}")
            st.stop()

    # Paso de inicio de sesión
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

    st.title("🔑 Iniciar Sesión")
    st.link_button("Login con Google", auth_url)
    st.stop()

# --- Funciones de Classroom ---
def get_courses(service):
    return service.courses().list().execute().get("courses", [])

# ... (Aquí incluyes tus funciones get_coursework, get_students, get_submissions) ...

def main():
    st.title("📊 Generador de calificaciones")
    creds = get_credentials()
    service = build("classroom", "v1", credentials=creds)
    
    courses = get_courses(service)
    # ... (Resto de tu lógica de UI) ...

if __name__ == "__main__":
    main()
