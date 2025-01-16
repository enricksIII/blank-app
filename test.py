import streamlit as st
import pandas as pd
import os
import json
import re
import io
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

# Constants and configurations
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')
TEMPLATE_FOLDER_ID = os.getenv('TEMPLATE_FOLDER_ID')
PLACEHOLDER_FILE = "placeholders.json"

# Initialize Google API clients
try:
    creds = service_account.Credentials.from_service_account_info(
        json.loads(SERVICE_ACCOUNT_JSON),
        scopes=SCOPES
    )
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
except Exception as e:
    st.error(f"Failed to initialize Google API clients: {e}")

# Utility Functions
def get_templates_from_folder(service, folder_id):
    try:
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.document'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return {file['name']: file['id'] for file in files}
    except HttpError as e:
        st.error(f"Error fetching templates: {e}")
        return {}

def fetch_placeholders(document_id, docs_service):
    try:
        document = docs_service.documents().get(documentId=document_id).execute()
        placeholders = []

        def extract_from_paragraph_elements(paragraph_elements):
            text_content = ""
            for element in paragraph_elements:
                text_content += element.get("textRun", {}).get("content", "")
            placeholders.extend(re.findall(r"\{([^{}]*)\}", text_content.lower()))

        for element in document.get('body', {}).get('content', []):
            if "paragraph" in element:
                extract_from_paragraph_elements(element["paragraph"]["elements"])
            if "table" in element:
                for row in element["table"]["tableRows"]:
                    for cell in row["tableCells"]:
                        for content in cell["content"]:
                            if "paragraph" in content:
                                extract_from_paragraph_elements(content["paragraph"]["elements"])

        placeholders = [ph for ph in placeholders if ph not in ["legal_description_1", "legal_description_2", "legal_description_3"]]
        if "legal_description" not in placeholders:
            placeholders.append("legal_description")

        return placeholders
    except HttpError as e:
        st.error(f"Error fetching placeholders for document {document_id}: {e}")
        return []

def save_placeholders(file_path, placeholders, doc_id):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
    else:
        data = {}

    data[doc_id] = placeholders

    with open(file_path, "w") as file:
        json.dump(data, file)

def load_placeholders(file_path, doc_id):
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
            return data.get(doc_id, [])
    return []

# Define separate pages
def page_import_csv():
    st.title("Import CSV for Contract Generation")
    templates = get_templates_from_folder(drive_service, TEMPLATE_FOLDER_ID)
    selected_template = st.selectbox("Select a template for contract generation", options=["Select a template"] + list(templates.keys()))

    if selected_template != "Select a template":
        doc_id = templates[selected_template]
        placeholders = load_placeholders(PLACEHOLDER_FILE, doc_id)
        if not placeholders:
            placeholders = fetch_placeholders(doc_id, docs_service)
            save_placeholders(PLACEHOLDER_FILE, placeholders, doc_id)

        uploaded_file = st.file_uploader("Upload a CSV file", type="csv")
        if uploaded_file:
            df = pd.read_csv(uploaded_file, dtype=str).fillna("")
            st.write("CSV data preview:", df.head())

            if st.button("Generate Contracts"):
                st.success("Contracts would be generated here.")  # Replace with generation logic

def page_manual_input():
    st.title("Manually Input Data for Contract Generation")
    templates = get_templates_from_folder(drive_service, TEMPLATE_FOLDER_ID)
    selected_template = st.selectbox("Select a template for manual input", options=["Select a template"] + list(templates.keys()))

    if selected_template != "Select a template":
        doc_id = templates[selected_template]
        placeholders = load_placeholders(PLACEHOLDER_FILE, doc_id)
        if not placeholders:
            placeholders = fetch_placeholders(doc_id, docs_service)
            save_placeholders(PLACEHOLDER_FILE, placeholders, doc_id)

        if "manual_data" not in st.session_state:
            st.session_state.manual_data = []

        with st.form("manual_form"):
            data = {ph: st.text_input(ph.replace("_", " ").title()) for ph in placeholders if ph != "legal_description"}
            data["legal_description"] = st.text_area("Legal Description")
            submitted = st.form_submit_button("Save Entry")
            if submitted:
                st.session_state.manual_data.append(data)
                st.success("Data added successfully!")

        st.write("Manual Entries:")
        st.write(st.session_state.manual_data)

        if st.button("Generate Contracts"):
            st.success("Contracts would be generated here.")  # Replace with generation logic

# Sidebar Navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Import CSV", "Manually Input Data"])

# Route to the correct page
if page == "Import CSV":
    page_import_csv()
elif page == "Manually Input Data":
    page_manual_input()