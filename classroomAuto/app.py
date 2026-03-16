import streamlit as st
import pandas as pd
import json
import requests
from openpyxl import load_workbook
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- CONFIGURACIÓN ---
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]
REDIRECT_URI = "https://classroomauto-waii8w8kkpdnbm9226rdwu.streamlit.app/"

# --- AUTENTICACIÓN ---
def get_credentials():
    if "creds" in st.session_state:
        return st.session_state.creds

    client_config = json.loads(st.secrets["CREDENTIALS_JSON"])
    web_config = client_config["web"]
    
    # Paso de intercambio manual (evita PKCE/InvalidGrant)
    if "code" in st.query_params:
        data = {
            "code": st.query_params["code"],
            "client_id": web_config["client_id"],
            "client_secret": web_config["client_secret"],
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        response = requests.post(web_config["token_uri"], data=data)
        token_data = response.json()

        if "access_token" in token_data:
            st.session_state.creds = Credentials(
                token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=web_config["token_uri"],
                client_id=web_config["client_id"],
                client_secret=web_config["client_secret"],
                scopes=SCOPES
            )
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Error: {token_data.get('error')}")
            st.stop()

    # Paso de generación de URL de login
    params = {
        "client_id": web_config["client_id"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"{web_config['auth_uri']}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    st.title("🔑 Iniciar Sesión")
    st.link_button("Login con Google", auth_url)
    st.stop()

# --- FUNCIONES DE CLASSROOM ---
def get_courses(service):
    return service.courses().list().execute().get("courses", [])

def get_coursework(service, course_id):
    return service.courses().courseWork().list(courseId=course_id).execute().get("courseWork", [])

def get_students(service, course_id):
    students = {}
    request = service.courses().students().list(courseId=course_id)
    while request:
        response = request.execute()
        for s in response.get("students", []):
            name = f"{s['profile']['name'].get('familyName', '')} {s['profile']['name'].get('givenName', '')}"
            students[s["userId"]] = name
        request = service.courses().students().list_next(request, response)
    return dict(sorted(students.items(), key=lambda x: x[1].lower()))

def get_submissions(service, course_id, task_id):
    submissions = []
    request = service.courses().courseWork().studentSubmissions().list(courseId=course_id, courseWorkId=task_id, pageSize=100)
    while request:
        response = request.execute()
        submissions.extend(response.get("studentSubmissions", []))
        request = service.courses().courseWork().list_next(request, response)
    return submissions

# --- INTERFAZ PRINCIPAL ---
def main():
    st.title("📊 Generador de calificaciones")
    creds = get_credentials()
    service = build("classroom", "v1", credentials=creds)

    courses = get_courses(service)
    if not courses:
        st.warning("No hay cursos.")
        return

    selected_course = st.selectbox("Selecciona curso", [c["name"] for c in courses])
    course_id = next(c["id"] for c in courses if c["name"] == selected_course)

    tasks = get_coursework(service, course_id)
    selected_tasks = st.multiselect("Selecciona tareas", [t["title"] for t in tasks])

    if st.button("Generar Excel"):
        students = get_students(service, course_id)
        grades = {name: [] for name in students.values()}
        
        for title in selected_tasks:
            task = next(t for t in tasks if t["title"] == title)
            submissions = get_submissions(service, course_id, task["id"])
            results = {sub["userId"]: (10 if any(e.get("stateHistory", {}).get("state") == "TURNED_IN" for e in sub.get("submissionHistory", [])) or (sub.get("assignedGrade", 0) > 0) else 0) for sub in submissions}
            
            for uid, name in students.items():
                grades[name].append(results.get(uid, 0))

        data = [[name] + scores + [round(sum(scores)/len(scores), 2) if scores else 0] for name, scores in grades.items()]
        df = pd.DataFrame(data, columns=["Alumno"] + selected_tasks + ["Promedio"])
        
        file_name = "calificaciones.xlsx"
        df.to_excel(file_name, index=False)
        
        # Ajustar ancho (logica original)
        wb = load_workbook(file_name)
        ws = wb.active
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(len(str(c.value)) for c in col) + 2
        wb.save(file_name)

        with open(file_name, "rb") as f:
            st.download_button("Descargar Excel", f, file_name)

if __name__ == "__main__":
    main()
