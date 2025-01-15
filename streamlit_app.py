import streamlit as st

st.set_page_config(
    page_title="Contract Generator",
    page_icon="📄",
    layout="wide",
)

st.title("Welcome to the Contract Generator")
st.write(
    """
    This application allows you to:
    - Import data from a CSV file to generate contracts.
    - Manually input data to generate contracts.

    Use the navigation menu on the left to get started.
    """
)