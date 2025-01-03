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

# Constants and configurations using environment variables
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')  # Store JSON string in Heroku env vars
TEMPLATE_FOLDER_ID = os.getenv('TEMPLATE_FOLDER_ID')  # Store folder ID in Heroku env vars
PLACEHOLDER_FILE = "placeholders.json"

# Initialize Google API clients
try:
    # Parse the service account JSON from the environment variable
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
    """Fetch the list of Google Docs templates from a specific Google Drive folder."""
    try:
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.document'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return {file['name']: file['id'] for file in files}
    except HttpError as e:
        st.error(f"Error fetching templates: {e}")
        return {}

def fetch_placeholders(document_id, docs_service):
    """Fetch placeholders from a Google Document."""
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
    """Save placeholders in a JSON file."""
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
    else:
        data = {}

    data[doc_id] = placeholders

    with open(file_path, "w") as file:
        json.dump(data, file)

def load_placeholders(file_path, doc_id):
    """Load placeholders from a JSON file."""
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
            return data.get(doc_id, [])
    return []

def split_legal_description(legal_description):
    char_limits = [65, 91, 91]
    words = legal_description.split()
    parts = []
    current_part = ""
    current_limit_index = 0

    for word in words:
        if len(current_part) + len(word) + 1 <= char_limits[current_limit_index]:
            current_part += (word + " ")
        else:
            parts.append(current_part.strip())
            current_part = word + " "
            current_limit_index += 1

            if current_limit_index >= len(char_limits):
                break

    if current_limit_index < len(char_limits):
        parts.append(current_part.strip())

    while len(parts) < len(char_limits):
        parts.append("")

    return parts[:3]

def replace_placeholders(document_id, placeholders, data, service):
    """Replace placeholders with values, handle legal_description."""
    requests = []
    for key in placeholders:
        if key == "legal_description":
            legal_description = data.get(key, "")
            part1, part2, part3 = split_legal_description(legal_description)
            requests.extend([
                {"replaceAllText": {"containsText": {"text": "{legal_description_1}"}, "replaceText": part1}},
                {"replaceAllText": {"containsText": {"text": "{legal_description_2}"}, "replaceText": part2}},
                {"replaceAllText": {"containsText": {"text": "{legal_description_3}"}, "replaceText": part3}},
            ])
        else:
            value = data.get(key, "")
            requests.append({
                "replaceAllText": {"containsText": {"text": f"{{{key}}}"}, "replaceText": value}
            })

    try:
        service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    except HttpError as e:
        st.error(f"Error replacing placeholders in document {document_id}: {e}")

def export_to_pdf_and_delete(drive_service, document_id, folder_id, file_name):
    """Export a Google Docs file to PDF and delete the original document."""
    try:
        pdf_data = drive_service.files().export(fileId=document_id, mimeType='application/pdf').execute()
        pdf_file_metadata = {
            'name': f"{file_name}.pdf",
            'parents': [folder_id],
        }
        media = MediaIoBaseUpload(io.BytesIO(pdf_data), mimetype='application/pdf')
        drive_service.files().create(body=pdf_file_metadata, media_body=media, fields='id').execute()
        drive_service.files().delete(fileId=document_id).execute()
    except HttpError as e:
        st.error(f"Error exporting document {document_id}: {e}")

def create_contract_on_google_docs(drive_service, docs_service, folder_id, template_id, placeholders, data):
    file_name = f"{data.get('property_address_line_1', '')}_{data.get('property_address_city', '')}"
    copied_file = drive_service.files().copy(fileId=template_id, body={"name": file_name, "parents": [folder_id]}).execute()
    replace_placeholders(copied_file["id"], placeholders, data, docs_service)
    export_to_pdf_and_delete(drive_service, copied_file["id"], folder_id, file_name)

# Fetch templates for dropdown
templates = get_templates_from_folder(drive_service, TEMPLATE_FOLDER_ID)

# Streamlit App Logic
st.title("Automated Contract Generator")
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
        if "row_index" not in st.session_state:
            st.session_state.row_index = 0
        if "clean_data" not in st.session_state:
            st.session_state.clean_data = []

        current_index = st.session_state.row_index
        if current_index < len(df):
            current_row = df.iloc[current_index].to_dict()
            st.subheader(f"Editing Row {current_index + 1} of {len(df)}")
            with st.form(key=f"form_row_{current_index}"):
                edited_row = {ph: st.text_input(ph.replace("_", " ").title(), value=current_row.get(ph, "")) for ph in placeholders if ph != "legal_description"}
                edited_row["legal_description"] = st.text_area("Legal Description", value=current_row.get("legal_description", ""))
                if st.form_submit_button("Save and Next"):
                    if all(value.strip() for value in edited_row.values()):
                        st.session_state.clean_data.append(edited_row)
                        st.session_state.row_index += 1
                        st.rerun()
                    else:
                        st.error("All fields are required.")
        else:
            st.success("All rows edited. Generating contracts...")
            if st.button("Generate Contracts"):
                folder_id = drive_service.files().create(
                    body={'name': f"[AUTOGENERATED]_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}", 
                          'mimeType': 'application/vnd.google-apps.folder', 
                          'parents': [TEMPLATE_FOLDER_ID]}).execute()['id']
                progress = st.progress(0)
                for idx, row in enumerate(st.session_state.clean_data):
                    create_contract_on_google_docs(drive_service, docs_service, folder_id, doc_id, placeholders, row)
                    progress.progress((idx + 1) / len(st.session_state.clean_data))
                st.success(f"Contracts saved in folder: [Open in Google Drive](https://drive.google.com/drive/folders/{folder_id})")
