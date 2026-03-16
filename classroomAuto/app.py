import streamlit as st
import pandas as pd
import json
import requests
from google.oauth2.credentials import Credentials
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
    web_config = client_config["web"]
    client_id = web_config["client_id"]
    client_secret = web_config["client_secret"]
    auth_uri = web_config["auth_uri"]
    token_uri = web_config["token_uri"]

    # Paso 2: Intercambio Manual
    if "code" in st.query_params:
        code = st.query_params["code"]
        
        # Preparamos el POST
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
            st.error(f"Error en intercambio: {token_data.get('error_description', token_data.get('error'))}")
            st.stop()

    # Paso 1: Generar URL de autorización (Sin usar Flow para evitar PKCE conflictivo)
    # Construimos la URL manualmente para evitar cualquier interferencia de librerías
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"{auth_uri}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"

    st.title("🔑 Iniciar Sesión")
    st.link_button("Login con Google", auth_url)
    st.stop()

def main():
    st.title("📊 Generador de calificaciones")
    creds = get_credentials()
    
    # Si llegamos aquí, ya tenemos credenciales
    service = build("classroom", "v1", credentials=creds)
    
    # Lógica de cursos (Tu implementación original)
    results = service.courses().list().execute()
    courses = results.get("courses", [])
    
    if not courses:
        st.write("No se encontraron cursos.")
    else:
        st.write(f"Conectado a {len(courses)} cursos.")
        # Aquí continúa tu lógica de UI...

if __name__ == "__main__":
    main()
