import streamlit as st
import os
from dotenv import load_dotenv
from utils import get_templates_from_folder, initialize_google_clients, load_placeholders, fetch_placeholders, save_placeholders

load_dotenv()

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')
TEMPLATE_FOLDER_ID = os.getenv('TEMPLATE_FOLDER_ID')
PLACEHOLDER_FILE = "placeholders.json"

# Initialize Google clients
docs_service, drive_service = initialize_google_clients(SERVICE_ACCOUNT_JSON, SCOPES)

# Title
st.title("Manually Input Data for Contract Generation")

# Fetch templates for the dropdown
templates = get_templates_from_folder(drive_service, TEMPLATE_FOLDER_ID)
selected_template = st.selectbox("Select a template", options=["Select a template"] + list(templates.keys()))

if selected_template != "Select a template":
    doc_id = templates[selected_template]

    # Load or fetch placeholders
    placeholders = load_placeholders(PLACEHOLDER_FILE, doc_id)
    if not placeholders:
        placeholders = fetch_placeholders(doc_id, docs_service)
        save_placeholders(PLACEHOLDER_FILE, placeholders, doc_id)

    # Initialize session state for manual data and form data
    if "manual_data" not in st.session_state:
        st.session_state.manual_data = []

    if "temp_form_data" not in st.session_state:
        st.session_state.temp_form_data = {ph: "" for ph in placeholders}

    # Display the form
    with st.form("manual_form", clear_on_submit=True):
        for ph in placeholders:
            if ph == "estimated_value":
                st.session_state.temp_form_data[ph] = st.text_input(
                    "Offer Price",
                    value=st.session_state.temp_form_data.get(ph, ""),
                    key=f"form_{ph}",
                )
            elif ph != "legal_description":
                st.session_state.temp_form_data[ph] = st.text_input(
                    ph.replace("_", " ").title(),
                    value=st.session_state.temp_form_data.get(ph, ""),
                    key=f"form_{ph}",
                )
        st.session_state.temp_form_data["legal_description"] = st.text_area(
            "Legal Description",
            value=st.session_state.temp_form_data.get("legal_description", ""),
            key="form_legal_description",
        )

        submitted = st.form_submit_button("Save Entry")

        if submitted:
            # Save the form data to manual_data
            st.session_state.manual_data.append(st.session_state.temp_form_data.copy())
            st.success("Data added successfully!")
            # Clear the form by resetting temp_form_data
            st.session_state.temp_form_data = {ph: "" for ph in placeholders}

    # # Display manual entries
    # st.write("Manual Entries:")
    # for idx, entry in enumerate(st.session_state.manual_data, start=1):
    #     st.write(f"Entry {idx}: {entry}")

    # Generate contracts button
    if st.button("Generate Contracts"):
        st.success("Contracts would be generated here.")