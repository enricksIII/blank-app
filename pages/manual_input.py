import streamlit as st
import os
from utils import get_templates_from_folder, initialize_google_clients

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')
TEMPLATE_FOLDER_ID = os.getenv('TEMPLATE_FOLDER_ID')

# Initialize Google clients
docs_service, drive_service = initialize_google_clients(SERVICE_ACCOUNT_JSON, SCOPES)

# Title
st.title("Manually Input Data for Contract Generation")

# Fetch templates for the dropdown
templates = get_templates_from_folder(drive_service, TEMPLATE_FOLDER_ID)
selected_template = st.selectbox("Select a template", options=["Select a template"] + list(templates.keys()))

if selected_template != "Select a template":
    # Initialize session states
    if "manual_data" not in st.session_state:
        st.session_state.manual_data = []

    if "form_values" not in st.session_state:
        st.session_state.form_values = {"Field 1": "", "Field 2": "", "Field 3": ""}

    # Reset form logic
    if "reset_form" not in st.session_state:
        st.session_state.reset_form = False

    if st.session_state.reset_form:
        st.session_state.form_values = {"Field 1": "", "Field 2": "", "Field 3": ""}
        st.session_state.reset_form = False

    # Display the form
    form_values = st.session_state.form_values
    with st.form("manual_form"):
        field_1 = st.text_input("Field 1", value=form_values["Field 1"])
        field_2 = st.text_input("Field 2", value=form_values["Field 2"])
        field_3 = st.text_input("Field 3", value=form_values["Field 3"])
        submitted = st.form_submit_button("Save Entry")

        if submitted:
            # Save the form data
            st.session_state.manual_data.append({
                "Field 1": field_1,
                "Field 2": field_2,
                "Field 3": field_3,
            })
            st.success("Data added successfully!")

            # Clear form values for the next entry
            st.session_state.form_values = {"Field 1": "", "Field 2": "", "Field 3": ""}
            st.rerun()

    # Reset button outside the form
    if st.button("Reset Form"):
        st.session_state.reset_form = True
        st.rerun()

    # Display manual entries
    st.write("Manual Entries:")
    for idx, entry in enumerate(st.session_state.manual_data, start=1):
        st.write(f"Entry {idx}: {entry}")

    # Generate contracts button
    if st.button("Generate Contracts"):
        st.success("Contracts would be generated here.")