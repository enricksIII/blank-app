import json
import re
import io
import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build, HttpError
from googleapiclient.http import MediaIoBaseUpload

# Placeholder Management
PLACEHOLDER_FILE = "placeholders.json"

# Initialize Google API clients
def initialize_google_clients(service_account_json, scopes):
    """Initialize Google API clients for Docs and Drive."""
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

# Fetch Templates
def get_templates_from_folder(service, folder_id):
    """Fetch Google Docs templates from a specific folder."""
    try:
        query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.document'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        return {file["name"]: file["id"] for file in files}
    except HttpError as e:
        raise RuntimeError(f"Error fetching templates: {e}")

# Placeholder Management
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

        # Exclude unnecessary placeholders and ensure `legal_description` is included
        placeholders = [ph for ph in placeholders if ph not in ["legal_description_1", "legal_description_2", "legal_description_3"]]
        if "legal_description" not in placeholders:
            placeholders.append("legal_description")

        return placeholders
    except HttpError as e:
        raise RuntimeError(f"Error fetching placeholders: {e}")

def save_placeholders(file_path, placeholders, doc_id):
    """Save placeholders to a JSON file."""
    if not placeholders:
        return

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

# Legal Description Splitting
def split_legal_description(legal_description):
    """Split legal description into three parts with character limits."""
    char_limits = [65, 91, 91]
    words = legal_description.split()
    parts = []
    current_part = ""
    current_limit_index = 0

    for word in words:
        if len(current_part) + len(word) + 1 <= char_limits[current_limit_index]:  # +1 for space
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

# Placeholder Replacement
def replace_placeholders(document_id, placeholders, data, docs_service):
    """Replace placeholders in a Google Doc."""
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
        docs_service.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    except HttpError as e:
        raise RuntimeError(f"Error replacing placeholders in document {document_id}: {e}")

# PDF Export and Cleanup
def export_to_pdf_and_delete(drive_service, document_id, folder_id, file_name):
    """Export Google Docs file to PDF and delete the original."""
    try:
        pdf_data = drive_service.files().export(fileId=document_id, mimeType='application/pdf').execute()
        pdf_metadata = {
            "name": f"{file_name}.pdf",
            "parents": [folder_id],
        }
        media = MediaIoBaseUpload(io.BytesIO(pdf_data), mimetype="application/pdf")
        drive_service.files().create(body=pdf_metadata, media_body=media, fields="id").execute()
        drive_service.files().delete(fileId=document_id).execute()
    except HttpError as e:
        raise RuntimeError(f"Error exporting or deleting document {document_id}: {e}")

# Contract Creation
def create_contract_on_google_docs(drive_service, docs_service, folder_id, template_id, placeholders, data):
    """Create a Google Doc, replace placeholders, export to PDF, and delete the original."""
    file_name = f"{data.get('property_address_line_1', '')}_{data.get('property_address_city', '')}"
    copied_file = drive_service.files().copy(fileId=template_id, body={"name": file_name, "parents": [folder_id]}).execute()
    replace_placeholders(copied_file["id"], placeholders, data, docs_service)
    export_to_pdf_and_delete(drive_service, copied_file["id"], folder_id, file_name)