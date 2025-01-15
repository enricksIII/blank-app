import streamlit as st
import os
from utils import get_templates_from_folder, initialize_google_clients

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SERVICE_ACCOUNT_JSON = os.getenv('SERVICE_ACCOUNT_JSON')
TEMPLATE_FOLDER_ID = os.getenv('TEMPLATE_FOLDER_ID')

# Initialize Google clients
docs_service, drive_service = initialize_google_clients(SERVICE_ACCOUNT_JSON, SCOPES)

st.title("Manually Input Data for Contract Generation")
templates = get_templates_from_folder(drive_service, TEMPLATE_FOLDER_ID)
selected_template = st.selectbox("Select a template", options=["Select a template"] + list(templates.keys()))

if selected_template != "Select a template":
    # Initialize session state for manual data and temporary form data
    if "manual_data" not in st.session_state:
        st.session_state.manual_data = []

    if "temp_data" not in st.session_state:
        st.session_state.temp_data = {
            "Field 1": "",
            "Field 2": "",
            "Field 3": ""
        }

    # Display the form
    with st.form("manual_form"):
        st.session_state.temp_data["Field 1"] = st.text_input("Field 1", value=st.session_state.temp_data["Field 1"])
        st.session_state.temp_data["Field 2"] = st.text_input("Field 2", value=st.session_state.temp_data["Field 2"])
        st.session_state.temp_data["Field 3"] = st.text_input("Field 3", value=st.session_state.temp_data["Field 3"])
        submitted = st.form_submit_button("Save Entry")
        if submitted:
            # Save the current form data to the manual_data list
            st.session_state.manual_data.append(st.session_state.temp_data.copy())
            st.success("Data added successfully!")
            # Clear the form fields
            st.session_state.temp_data = {key: "" for key in st.session_state.temp_data.keys()}

    # Display the manual entries
    st.write("Manual Entries:")
    st.write(st.session_state.manual_data)

    # Generate contracts button
    if st.button("Generate Contracts"):
        st.success("Contracts would be generated here.")