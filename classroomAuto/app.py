import streamlit as st
import pandas as pd
from openpyxl import load_workbook
import json
import requests
from concurrent.futures import ThreadPoolExecutor

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# 💖 ESTILO CURSI 💖
st.markdown(
    """
    <style>
    body {
        background: linear-gradient(135deg, #e3f2fd, #fce4ec);
    }

    .main-title {
        text-align: center;
        font-size: 40px;
        color: #ff4b6e;
        font-weight: bold;
    }

    .subtitle {
        text-align: center;
        font-size: 18px;
        color: #6a1b9a;
    }

    .love-box {
        text-align: center;
        padding: 15px;
        border-radius: 15px;
        background-color: #ffffffcc;
        margin-bottom: 15px;
        font-size: 18px;
    }

    .heart {
        position: fixed;
        bottom: -10px;
        font-size: 20px;
        animation: float 6s infinite;
        opacity: 0.7;
    }

    @keyframes float {
        0% {transform: translateY(0);}
        100% {transform: translateY(-100vh);}
    }
    </style>

    <div class="heart" style="left:10%;">💖</div>
    <div class="heart" style="left:20%; animation-duration:5s;">💗</div>
    <div class="heart" style="left:30%; animation-duration:7s;">💓</div>
    <div class="heart" style="left:40%; animation-duration:4s;">💞</div>
    <div class="heart" style="left:50%; animation-duration:6s;">💕</div>
    <div class="heart" style="left:60%; animation-duration:5s;">💘</div>
    <div class="heart" style="left:70%; animation-duration:8s;">💝</div>
    <div class="heart" style="left:80%; animation-duration:6s;">💖</div>
    <div class="heart" style="left:90%; animation-duration:7s;">💗</div>
    """,
    unsafe_allow_html=True
)

# SCOPES
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]

# -----------------------------
# LOGIN
# -----------------------------
def load_saved_credentials():
    if "creds_json" in st.session_state:
        return Credentials.from_authorized_user_info(
            json.loads(st.session_state.creds_json),
            SCOPES
        )
    return None

def get_credentials():
    saved_creds = load_saved_credentials()
    if saved_creds:
        return saved_creds

    if "creds" in st.session_state:
        return st.session_state.creds

    client_config = json.loads(st.secrets["CREDENTIALS_JSON"])
    web_config = client_config["web"]

    REDIRECT_URI = "https://classroomauto-waii8w8kkpdnbm9226rdwu.streamlit.app/"

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
            creds = Credentials(
                token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=web_config["token_uri"],
                client_id=web_config["client_id"],
                client_secret=web_config["client_secret"],
                scopes=SCOPES,
            )

            st.session_state.creds = creds
            st.session_state.creds_json = creds.to_json()
            st.query_params.clear()
            st.rerun()
        else:
            st.error("Error al autenticar con Google")
            st.write(token_data)
            st.stop()

    params = {
        "client_id": web_config["client_id"],
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"{web_config['auth_uri']}?{'&'.join([f'{k}={v}' for k,v in params.items()])}"

    st.markdown("<div class='main-title'>💖 Inicia sesión mi amor 💖</div>", unsafe_allow_html=True)
    st.link_button("💌 Login con Google", auth_url)
    st.stop()

# -----------------------------
# CACHE
# -----------------------------
@st.cache_data(ttl=300)
def get_courses(_):
    return _.courses().list().execute().get("courses", [])

@st.cache_data(ttl=300)
def get_coursework(_, course_id):
    return _.courses().courseWork().list(courseId=course_id).execute().get("courseWork", [])

@st.cache_data(ttl=300)
def get_students(_, course_id):
    students_request = _.courses().students().list(courseId=course_id)
    students = {}

    while students_request is not None:
        response = students_request.execute()
        for s in response.get("students", []):
            name = f"{s['profile']['name'].get('familyName','')} {s['profile']['name'].get('givenName','')}"
            students[s["userId"]] = name
        students_request = _.courses().students().list_next(students_request, response)

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
        request = service.courses().courseWork().studentSubmissions().list_next(request, response)

    return submissions

# -----------------------------
# UI
# -----------------------------
st.markdown(
    """
    <div class="main-title">
    💖 Para mi Itzelita preciosa 💖
    </div>
    <div class="subtitle">
    Hecho con todo mi amor para ti mi vida 🫶✨
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="love-box">
    💕 Te amo cielo 💕<br>
    💖 Eres la mejor mi vida 💖<br>
    💗 Mi corazón es tuyo siempre 💗<br>
    💞 Te quiero muchísimo amor de mi vida 💞<br>
    💘 Eres lo más hermoso que me ha pasado 💘<br>
    🌸 Mi Itzelita preciosa 🌸
    </div>
    """,
    unsafe_allow_html=True
)

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()
    st.success("Caché limpiado 💕")

creds = get_credentials()
service = build("classroom", "v1", credentials=creds)

courses = get_courses(service)
course_names = [c["name"] for c in courses]
selected_course_name = st.selectbox("Selecciona curso", course_names)

selected_course = next(c for c in courses if c["name"] == selected_course_name)
selected_course_id = selected_course["id"]

tasks = get_coursework(service, selected_course_id)
task_options = [f"{i+1} - {t['title']}" for i,t in enumerate(tasks)]

with st.form("tareas_form"):
    selected_task_titles = st.multiselect(
        "Selecciona tareas 💕",
        options=task_options
    )
    submitted = st.form_submit_button("Confirmar selección 💖")

# -----------------------------
# GENERAR
# -----------------------------
if selected_task_titles:

    if st.button("Generar Excel 💕"):

        with st.spinner("⏳ Procesando con amor..."):

            try:
                students = get_students(service, selected_course_id)
                grades = {name: [] for name in students.values()}

                selected_tasks_objs = [
                    tasks[int(t.split(" - ")[0]) - 1]
                    for t in selected_task_titles
                ]

                def process_task(task):
                    local_service = build("classroom", "v1", credentials=creds)
                    submissions = get_submissions(local_service, selected_course_id, task["id"])
                    results_by_student = {}

                    for sub in submissions:
                        student_id = sub["userId"]
                        history = sub.get("submissionHistory", [])

                        entrego = any(
                            "stateHistory" in e and e["stateHistory"]["state"] == "TURNED_IN"
                            for e in history
                        )

                        assigned = sub.get("assignedGrade")

                        if not entrego and assigned and assigned > 0:
                            entrego = True

                        results_by_student[student_id] = 10 if entrego else 0

                    return results_by_student

                with ThreadPoolExecutor(max_workers=3) as executor:
                    results = list(executor.map(process_task, selected_tasks_objs))

                for results_by_student in results:
                    for student_id, name in students.items():
                        grades[name].append(results_by_student.get(student_id, 0))

                data = []
                for student, scores in grades.items():
                    promedio = round(sum(scores)/len(scores), 2)
                    data.append([student] + scores + [promedio])

                columns = ["Alumno"] + selected_task_titles + ["Promedio"]
                df = pd.DataFrame(data, columns=columns)

                # 🔥 VISTA PREVIA CON COLORES
                st.subheader("📝 Vista previa")
                st.dataframe(
                    df.style
                    .applymap(lambda x: "background-color: #ffcdd2" if isinstance(x,(int,float)) and x==0 else "")
                    .applymap(lambda x: "background-color: #c8e6c9" if isinstance(x,(int,float)) and x==10 else ""),
                    use_container_width=True
                )

                # 🔥 NOMBRE CON CURSO
                file_name = f"calificaciones_{selected_course_name.replace(' ','_')}.xlsx"
                df.to_excel(file_name, index=False)

                wb = load_workbook(file_name)
                ws = wb.active

                for col in ws.columns:
                    max_len = max(len(str(c.value)) if c.value else 0 for c in col)
                    ws.column_dimensions[col[0].column_letter].width = max_len + 2

                wb.save(file_name)

                st.success("Archivo generado 💕✨")
                st.balloons()

                st.download_button(
                    "📥 Descargar Excel",
                    data=open(file_name,"rb").read(),
                    file_name=file_name
                )

                st.markdown(
                    """
                    <div class="love-box">
                    💌 Hecho con amor para ti 💌<br>
                    💖 Te amo muchísimo mi cielo 💖<br>
                    💕 Siempre contigo mi amor 💕<br>
                    💗 Eres la mejor mi vida 💗
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            except Exception as e:
                st.error("Error 😢")
                st.write(e)
