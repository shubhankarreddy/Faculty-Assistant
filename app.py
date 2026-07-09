import time
import requests
import streamlit as st
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title="Agentic RAG Productivity Assistant", layout="wide")

st.title("Agentic RAG Productivity Assistant")
st.write("Streamlit frontend connected to CrewAI backend")

API_URL = st.secrets["CREWAI_API_URL"].rstrip("/")
TOKEN = st.secrets["CREWAI_BEARER_TOKEN"]

if not TOKEN.lower().startswith("bearer "):
    TOKEN = "Bearer " + TOKEN

headers = {
    "Authorization": TOKEN,
    "Content-Type": "application/json"
}


def extract_text_from_file(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".txt") or file_name.endswith(".csv"):
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")

    if file_name.endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        text = ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        return text

    if file_name.endswith(".docx"):
        doc = Document(uploaded_file)
        text = ""

        for para in doc.paragraphs:
            text += para.text + "\n"

        return text

    return ""


output_type = st.selectbox(
    "Output Type",
    ["summary", "document_qa", "quiz", "assignment", "email_draft"]
)

topic = st.text_input("Topic", placeholder="Example: MySQL basics")

audience_profile = st.text_input(
    "Audience Profile",
    placeholder="Example: B.Tech students, beginner level"
)

user_requirements = st.text_area(
    "User Requirements",
    placeholder="Example: Create a beginner-friendly summary with examples.",
    height=120
)

uploaded_files = st.file_uploader(
    "Upload files for context",
    type=["pdf", "docx", "txt", "csv"],
    accept_multiple_files=True
)

pasted_context = st.text_area(
    "Optional Context",
    placeholder="Paste document content here if you want the assistant to use it.",
    height=180
)

run_btn = st.button("Run Assistant", type="primary")

if run_btn:
    if topic.strip() == "":
        st.error("Please enter a topic.")
        st.stop()

    if user_requirements.strip() == "":
        st.error("Please enter user requirements.")
        st.stop()

    extracted_file_context = ""

    if uploaded_files:
        for file in uploaded_files:
            file_text = extract_text_from_file(file)

            if file_text.strip():
                extracted_file_context += f"\n\n--- Content from uploaded file: {file.name} ---\n"
                extracted_file_context += file_text

    final_context = ""

    if extracted_file_context.strip():
        final_context += extracted_file_context

    if pasted_context.strip():
        final_context += "\n\n--- User pasted context ---\n"
        final_context += pasted_context

    final_context = final_context[:25000]

    inputs = {
        "topic": topic,
        "output_type": output_type,
        "audience_profile": audience_profile,
        "user_requirements": user_requirements,
        "teaching_requirements": user_requirements,
        "pasted_context": final_context
    }

    try:
        status_box = st.empty()
        progress_bar = st.progress(0)

        with st.spinner("Starting CrewAI run..."):
            kickoff_url = API_URL + "/kickoff"

            response = requests.post(
                kickoff_url,
                headers=headers,
                json={"inputs": inputs},
                timeout=60
            )

            response.raise_for_status()
            kickoff_data = response.json()

        kickoff_id = kickoff_data.get("kickoff_id") or kickoff_data.get("id")

        if not kickoff_id:
            st.error("No kickoff_id found.")
            st.write("CrewAI response:")
            st.json(kickoff_data)
            st.stop()

        with st.spinner("Waiting for CrewAI result..."):
            final_data = None

            for i in range(120):
                status_url_1 = API_URL + f"/status/{kickoff_id}"
                status_url_2 = API_URL + f"/{kickoff_id}/status"

                status_response = requests.get(
                    status_url_1,
                    headers=headers,
                    timeout=30
                )

                if status_response.status_code == 404:
                    status_response = requests.get(
                        status_url_2,
                        headers=headers,
                        timeout=30
                    )

                status_response.raise_for_status()
                status_data = status_response.json()

                status = str(
                    status_data.get("status") or status_data.get("state") or ""
                ).lower()

                status_box.info(f"Current status: {status}")
                progress_bar.progress(min((i + 1) / 120, 1.0))

                if status in ["success", "succeeded", "completed", "complete", "done", "finished"]:
                    final_data = status_data
                    status_box.success("CrewAI run completed")
                    progress_bar.progress(1.0)
                    break

                if status in ["failed", "failure", "error", "cancelled"]:
                    status_box.error("CrewAI run failed.")
                    st.json(status_data)
                    st.stop()

                time.sleep(2)

        if final_data is None:
            st.error("CrewAI took too long. Try again with shorter input.")
            st.stop()

        result = (
            final_data.get("result")
            or final_data.get("output")
            or final_data.get("response")
            or final_data
        )

        if isinstance(result, dict):
            final_output = (
                result.get("raw")
                or result.get("response")
                or result.get("final_output")
                or str(result)
            )
        else:
            final_output = str(result)

        st.success("Done")
        st.subheader("Final Output")
        st.markdown(final_output)

        st.download_button(
            "Download Output",
            final_output,
            file_name="crewai_output.md",
            mime="text/markdown"
        )

    except Exception as e:
        st.error("Something went wrong.")
        st.exception(e)