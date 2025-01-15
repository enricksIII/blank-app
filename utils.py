import json
import os
import re
import io
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build, HttpError
from googleapiclient.http import MediaIoBaseUpload

# Constants
PLACEHOLDER_FILE = "placeholders.json"

# Initialize Google API clients
def initialize_google_clients(service_account_json, scopes):
    try:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(service_account_json),
            scopes=scopes
        )
        docs_service = build("docs", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)
        return docs_service, drive_service
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Google API clients: {e}")

# Fetch templates
def get_templates_from_folder(service, folder_id):
    try:
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.document'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return {file['name']: file['id'] for file in files}
    except HttpError as e:
        raise RuntimeError(f"Error fetching templates: {e}")

# Placeholder management
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
        raise RuntimeError(f"Error fetching placeholders: {e}")

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

# Legal Description Helper
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