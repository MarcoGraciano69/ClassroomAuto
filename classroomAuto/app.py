import streamlit as st
import pandas as pd
from openpyxl import load_workbook
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# -----------------------------
# SCOPES necesarios de Classroom
# -----------------------------
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]

# -----------------------------
# Función para obtener credenciales
# -----------------------------
def get_credentials():

    if "creds" not in st.session_state:

        flow = InstalledAppFlow.from_client_config(
            json.loads(st.secrets["CREDENTIALS_JSON"]),
            SCOPES,
            redirect_uri="https://classroomauto-waii8w8kkpdnbm9226rdwu.streamlit.app/"
        )

        auth_url, _ = flow.authorization_url(
            prompt="consent"
        )

        st.title("🔑 Autorizar acceso a Google Classroom")

        st.write("1️⃣ Abre este enlace:")
        st.write(auth_url)

        st.write("2️⃣ Después de autorizar, copia el código de la URL")

        code = st.text_input("Pega aquí el código:")

        if code:

            flow.fetch_token(code=code)

            st.session_state.creds = flow.credentials
            st.rerun()

        st.stop()

    return st.session_state.creds


# -----------------------------
# Funciones de Google Classroom
# -----------------------------
def get_courses(service):
    results = service.courses().list().execute()
    return results.get("courses", [])


def get_coursework(service, course_id):
    results = service.courses().courseWork().list(courseId=course_id).execute()
    return results.get("courseWork", [])


def get_students(service, course_id):
    students_request = service.courses().students().list(courseId=course_id)
    students = {}

    while students_request is not None:
        response = students_request.execute()

        for s in response.get("students", []):
            name = f"{s['profile']['name'].get('familyName','')} {s['profile']['name'].get('givenName','')}"
            students[s["userId"]] = name

        students_request = service.courses().students().list_next(
            students_request,
            response
        )

    return dict(sorted(students.items(), key=lambda x: x[1].lower()))


def get_submissions(service, course_id, task_id):
    submissions = []

    request = service.courses().courseWork().studentSubmissions().list(
        courseId=course_id,
        courseWorkId=task_id,
        pageSize=100
    )

    while request is not None:
        response = request.execute()

        submissions.extend(response.get("studentSubmissions", []))

        request = service.courses().courseWork().studentSubmissions().list_next(
            request,
            response
        )

    return submissions


# -----------------------------
# Inicializar session_state
# -----------------------------
if "selected_course" not in st.session_state:
    st.session_state.selected_course = None

if "selected_tasks" not in st.session_state:
    st.session_state.selected_tasks = []


# -----------------------------
# Streamlit App
# -----------------------------
st.title("📊 Generador de calificaciones de Google Classroom")

creds = get_credentials()

service = build(
    "classroom",
    "v1",
    credentials=creds
)

# -----------------------------
# Selección de curso
# -----------------------------
courses = get_courses(service)

if not courses:
    st.warning("No se encontraron cursos.")
    st.stop()

course_names = [course["name"] for course in courses]

selected_course_name = st.selectbox(
    "Selecciona curso",
    course_names
)

st.session_state.selected_course = next(
    course for course in courses if course["name"] == selected_course_name
)

selected_course_id = st.session_state.selected_course["id"]


# -----------------------------
# Selección de tareas
# -----------------------------
tasks = get_coursework(service, selected_course_id)

if not tasks:
    st.warning("No hay tareas en este curso.")
    st.stop()

task_options = [
    f"{i+1} - {task['title']}"
    for i, task in enumerate(tasks)
]

selected_task_titles = st.multiselect(
    "Selecciona tareas en el orden que desees",
    options=task_options,
    default=st.session_state.selected_tasks
)

if st.button("Confirmar selección de tareas"):
    st.session_state.selected_tasks = selected_task_titles
    st.success(f"Tareas seleccionadas: {selected_task_titles}")


# -----------------------------
# Generar Excel
# -----------------------------
if st.session_state.selected_tasks:

    if st.button("Generar Excel"):

        students = get_students(service, selected_course_id)

        grades = {name: [] for name in students.values()}

        selected_tasks_objs = [
            tasks[int(t.split(" - ")[0]) - 1]
            for t in st.session_state.selected_tasks
        ]

        for task in selected_tasks_objs:

            submissions = get_submissions(
                service,
                selected_course_id,
                task["id"]
            )

            results_by_student = {}

            for sub in submissions:

                student_id = sub["userId"]

                history = sub.get("submissionHistory", [])

                entrego = False

                for event in history:
                    if "stateHistory" in event and event["stateHistory"]["state"] == "TURNED_IN":
                        entrego = True
                        break

                assigned = sub.get("assignedGrade")

                if not entrego and assigned is not None and assigned > 0:
                    entrego = True

                score = 10 if entrego else 0

                results_by_student[student_id] = score

            for student_id, name in students.items():
                grades[name].append(results_by_student.get(student_id, 0))


        data = []

        for student, scores in grades.items():

            promedio = round(sum(scores) / len(scores), 2) if scores else 0

            data.append([student] + scores + [promedio])


        columns = ["Alumno"] + st.session_state.selected_tasks + ["Promedio"]

        df = pd.DataFrame(data, columns=columns)


        file_name = f"calificaciones_{selected_course_name.replace(' ','_')}.xlsx"

        df.to_excel(file_name, index=False)


        wb = load_workbook(file_name)

        ws = wb.active

        for column in ws.columns:

            max_length = 0

            column_letter = column[0].column_letter

            for cell in column:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))

            ws.column_dimensions[column_letter].width = max_length + 2

        wb.save(file_name)


        st.success(f"Archivo generado: {file_name}")

        st.download_button(
            label="Descargar Excel",
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            data=open(file_name, "rb").read()
        )
