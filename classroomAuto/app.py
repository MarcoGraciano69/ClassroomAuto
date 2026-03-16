import streamlit as st
import pandas as pd
import json
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Configuraciones base
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]

# Asegurar que el redirect_uri sea idéntico al de Google Cloud Console
REDIRECT_URI = "https://classroomauto-waii8w8kkpdnbm9226rdwu.streamlit.app/"

def get_credentials():
    # 1. Si ya hay credenciales, las usamos
    if "creds" in st.session_state:
        return st.session_state.creds

    client_config = json.loads(st.secrets["CREDENTIALS_JSON"])
    
    # Creamos el Flow en cada ejecución para evitar errores de serialización
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # 2. Paso de intercambio: El usuario regresa de Google con el código
    # Usamos st.query_params directamente
    query_params = st.query_params
    if "code" in query_params:
        try:
            # EL TRUCO: Desactivamos la verificación de PKCE si es necesario
            # o simplemente inicializamos el fetch sin el flow original.
            # google-auth-oauthlib requiere el code_verifier si se inició con él.
            # Para evitarlo, usamos el flow recién creado.
            flow.fetch_token(code=query_params["code"])
            
            st.session_state.creds = flow.credentials
            
            # Limpiar la URL para que no intente canjear el código de nuevo al recargar
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Error crítico en OAuth: {e}")
            st.info("Reintentando el login...")
            # Si falla, borramos parámetros y dejamos que el flujo se reinicie
            st.query_params.clear()
            if st.button("Reintentar Login"):
                st.rerun()
            st.stop()

    # 3. Paso inicial: Generar URL de autorización
    # IMPORTANTE: Desactivamos PKCE manualmente para evitar el error 'Missing code verifier'
    # Esto se logra NO guardando el flow y recreándolo, o forzando el método
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
        # Nota: No definimos code_challenge para evitar que lo pida después
    )

    st.title("🔑 Iniciar Sesión")
    st.markdown("Para generar el Excel, primero debes autorizar el acceso a tu Google Classroom.")
    st.link_button("Login con Google", auth_url)
    st.stop()

# --- Resto de tus funciones (get_courses, get_students, etc.) ---
# Se mantienen igual, pero asegúrate de que el bloque principal use 'creds' correctamente

def get_courses(service):
    results = service.courses().list().execute()
    return results.get("courses", [])

# ... (tus otras funciones de Classroom) ...

# --- CUERPO PRINCIPAL DE LA APP ---

def main():
    st.title("📊 Generador de calificaciones de Google Classroom")
    
    # Obtener credenciales (esto detendrá la app si no está logueado)
    creds = get_credentials()

    try:
        service = build("classroom", "v1", credentials=creds)
        courses = get_courses(service)

        if not courses:
            st.warning("No se encontraron cursos.")
            return

        course_names = [course["name"] for course in courses]
        selected_course_name = st.selectbox("Selecciona curso", course_names)
        
        selected_course = next(c for c in courses if c["name"] == selected_course_name)
        course_id = selected_course["id"]

        # ... (Tu lógica de selección de tareas y generación de Excel) ...
        # [Nota: Mantén tu lógica de procesamiento de tareas aquí]
        
        # Ejemplo de botón de Logout para pruebas
        if st.sidebar.button("Cerrar Sesión"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    except Exception as e:
        st.error(f"Error al conectar con Classroom: {e}")
        if "invalid_grant" in str(e).lower():
            del st.session_state.creds
            st.rerun()

if __name__ == "__main__":
    main()
