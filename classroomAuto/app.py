import os
import streamlit as st
import pandas as pd
from openpyxl import load_workbook

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# -----------------------------
# SCOPES
# -----------------------------
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]

# -----------------------------
# AUTH
# -----------------------------
def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return creds

# -----------------------------
# API CALLS (CACHEADOS)
# -----------------------------
@st.cache_data
def get_courses(service):
    return service.courses().list().execute().get("courses", [])

@st.cache_data
def get_coursework(service, course_id):
    return service.courses().courseWork().list(courseId=course_id).execute().get("courseWork", [])

@st.cache_data
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
    request = service.courses().courseWork().studentSubmissions().list(
        courseId=course_id, courseWorkId=task_id, pageSize=100
    )
    while request:
        response = request.execute()
        submissions.extend(response.get("studentSubmissions", []))
        request = service.courses().courseWork().studentSubmissions().list_next(request, response)
    return submissions

# -----------------------------
# PROCESAMIENTO
# -----------------------------
def build_dataframe(grades, selected_tasks_clean):
    data = []
    for student, scores in grades.items():
        promedio = round(sum(scores)/len(scores), 2) if scores else 0
        data.append([student] + scores + [promedio])
    return pd.DataFrame(data, columns=["Alumno"] + selected_tasks_clean + ["Promedio"])

# -----------------------------
# SESSION STATE
# -----------------------------
if "selected_tasks" not in st.session_state:
    st.session_state.selected_tasks = []

# -----------------------------
# UI
# -----------------------------
st.title("📊 Generador PRO de calificaciones")

creds = get_credentials()
service = build("classroom", "v1", credentials=creds)

# -----------------------------
# CURSOS
# -----------------------------
courses = get_courses(service)
if not courses:
    st.warning("No se encontraron cursos.")
    st.stop()

course_names = [c["name"] for c in courses]
selected_course_name = st.selectbox("Selecciona curso", course_names)
selected_course = next(c for c in courses if c["name"] == selected_course_name)
course_id = selected_course["id"]

# -----------------------------
# TAREAS
# -----------------------------
tasks = get_coursework(service, course_id)
if not tasks:
    st.warning("No hay tareas.")
    st.stop()

task_options = [f"{i+1} - {t['title']}" for i, t in enumerate(tasks)]

with st.form("form_tareas"):
    selected = st.multiselect(
        "Selecciona tareas",
        task_options,
        default=st.session_state.selected_tasks
    )
    submit = st.form_submit_button("Confirmar")

if submit:
    st.session_state.selected_tasks = selected

# -----------------------------
# GENERAR
# -----------------------------
if st.session_state.selected_tasks:

    st.write(f"📚 Curso: {selected_course_name}")
    st.write(f"📝 Tareas seleccionadas: {len(st.session_state.selected_tasks)}")

    if st.button("Generar análisis + Excel"):

        students = get_students(service, course_id)
        grades = {name: [] for name in students.values()}

        selected_tasks_objs = [tasks[int(t.split(" - ")[0]) - 1] for t in st.session_state.selected_tasks]
        selected_tasks_clean = [t.split(" - ", 1)[1] for t in st.session_state.selected_tasks]

        progress = st.progress(0)

        for i, task in enumerate(selected_tasks_objs):

            submissions = get_submissions(service, course_id, task["id"])
            results = {}

            for sub in submissions:
                student_id = sub["userId"]
                history = sub.get("submissionHistory", [])

                entrego = False
                for event in history:
                    if "stateHistory" in event and event["stateHistory"]["state"] == "TURNED_IN":
                        entrego = True
                        break

                assigned = sub.get("assignedGrade")
                if not entrego and assigned and assigned > 0:
                    entrego = True

                results[student_id] = 10 if entrego else 0

            for uid, name in students.items():
                grades[name].append(results.get(uid, 0))

            progress.progress((i+1)/len(selected_tasks_objs))

        # DataFrame
        df = build_dataframe(grades, selected_tasks_clean)

        # -----------------------------
        # INSIGHTS
        # -----------------------------
        st.subheader("📊 Análisis")

        group_avg = df["Promedio"].mean()
        st.metric("Promedio del grupo", round(group_avg, 2))

        at_risk = df[df["Promedio"] < 6]
        top = df[df["Promedio"] >= 9]

        if group_avg < 7:
            st.warning("⚠️ Bajo rendimiento general")

        if len(at_risk) > len(df)*0.3:
            st.error("🚨 Muchos alumnos en riesgo")

        st.write("⚠️ Alumnos en riesgo")
        st.dataframe(at_risk)

        st.write("🏆 Alumnos destacados")
        st.dataframe(top)

        # -----------------------------
        # RANKING
        # -----------------------------
        st.subheader("🏆 Ranking")

        df_sorted = df.sort_values(by="Promedio", ascending=False)
        df_sorted["Ranking"] = range(1, len(df_sorted)+1)
        st.dataframe(df_sorted)

        # -----------------------------
        # FILTRO
        # -----------------------------
        st.subheader("🔍 Filtro")

        min_avg = st.slider("Promedio mínimo", 0.0, 10.0, 0.0)
        filtered_df = df[df["Promedio"] >= min_avg]
        st.dataframe(filtered_df)

        # -----------------------------
        # GRÁFICA
        # -----------------------------
        st.subheader("📈 Visualización")
        st.bar_chart(df.set_index("Alumno")["Promedio"])

        # -----------------------------
        # EXCEL
        # -----------------------------
        file_name = f"calificaciones_{selected_course_name.replace(' ','_')}.xlsx"
        df.to_excel(file_name, index=False)

        wb = load_workbook(file_name)
        ws = wb.active

        for col in ws.columns:
            max_length = max(len(str(c.value)) if c.value else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 2

        wb.save(file_name)

        st.success("Excel generado correctamente")

        with open(file_name, "rb") as f:
            st.download_button(
                "Descargar Excel",
                f,
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
