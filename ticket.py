import os
import re
import pandas as pd
import streamlit as st
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema.output_parser import StrOutputParser
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
import io
import os
import base64
import io
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

# Scopes required to send email
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def authenticate_gmail():
    """Authenticate and create Gmail API service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    service = build('gmail', 'v1', credentials=creds)
    return service

def create_message_with_attachment(sender, to, subject, body, attachment_file_name, attachment_data):
    """Create the MIME message with an attachment."""
    message = MIMEMultipart()
    message['from'] = sender
    message['to'] = to
    message['subject'] = subject

    # Attach the body text
    message.attach(MIMEText(body, 'plain'))

    # Attach the file
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment_data)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename={attachment_file_name}')
    message.attach(part)

    # Encode the message as base64 URL-safe
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    return raw_message

def send_email(service, sender, to, subject, body, attachment_file_name, attachment_data):
    """Send the email via Gmail API."""
    try:
        raw_message = create_message_with_attachment(sender, to, subject, body, attachment_file_name, attachment_data)
        message = service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        print(f'Email sent successfully: {message["id"]}')
    except HttpError as error:
        print(f'An error occurred: {error}')

# Function to classify tickets using LangChain and LLM
def classify_ticket_with_langchain(ticket):
    # Refined prompt template with more specific examples and instructions
    prompt = PromptTemplate(
        input_variables=["ticket_description"],
        template=""" 
        You are an AI assistant for classifying tickets into appropriate teams based on their descriptions.
        
        Categories:
        1. Infra: Issues related to servers, networks, data centers, and hardware (e.g., server downtime, network outages, hardware issues).
        2. Application Team: Issues related to application bugs, coding errors, and user experience problems (e.g., login failures, incorrect data display, or feature malfunctions).
        3. Access Management: Requests for granting access to systems, tools, or accounts (e.g., new employee account setup, access requests).

        Examples:
        - Infra: "Server Downtime in Data Center 1. Several servers are unreachable."
        - Application Team: "Bug in User Authentication Module causing login errors."
        - Access Management: "Access request for a new employee to systems like email or CRM."

        Carefully read the description below and classify it into one of the above categories.

        Ticket Description: {ticket_description}
        """
    )

    # Initialize Ollama model
    if not os.getenv("HUGGINGFACEHUB_API_TOKEN"):
        os.environ["HUGGINGFACEHUB_API_TOKEN"] = "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@gmail.com"

    llm = HuggingFaceEndpoint(
        repo_id="HuggingFaceH4/zephyr-7b-beta",
        # task="text-generation",
        # max_new_tokens=512,
        # do_sample=False,
        # repetition_penalty=1.03,
    )

    chat_model = ChatHuggingFace(llm=llm)

    # OutputParser to process the result and normalize the output
    class TeamOutputParser(StrOutputParser):
        def parse(self, output: str) -> str:
            classification = output.strip().lower()
            if "infra" in classification:
                return "Infra"
            elif "application team" in classification:
                return "Application Team"
            elif "access management" in classification:
                return "Access Management"
            else:
                return "Unknown"

    # Create LLMChain to process the ticket using the Ollama LLM and prompt
    llm_chain = LLMChain(
        llm=chat_model,
        prompt=prompt,
        output_parser=TeamOutputParser()
    )

    # Run the classification chain
    raw_result = llm_chain.invoke({"ticket_description": ticket["Description"]})

    # Extract the classification result
    if isinstance(raw_result, dict) and "text" in raw_result:
        result = raw_result["text"].strip()
    else:
        raise ValueError(f"Unexpected LLM output format: {raw_result}")

    return result

def is_valid_email(email):
    # Define a regex pattern for validating an email 
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$' 
    # Use re.match to check whether the email matches the pattern 
    if re.match(pattern, email) and "@gmail.com" in email: 
        return True 
    else: 
        return False

# Function to process text files
def process_txt_file(file):
    lines = file.read().decode("utf-8").splitlines()
    ticket_data = []
    current_ticket = {}
    for line in lines:
        if line.strip() == "--------------------":
            if current_ticket:
                ticket_data.append(current_ticket)
                current_ticket = {}
        elif ":" in line:
            key, value = line.split(":", 1)
            current_ticket[key.strip()] = value.strip()
        elif "Description" in current_ticket:
            current_ticket["Description"] += " " + line.strip()
    if current_ticket:
        ticket_data.append(current_ticket)
    return pd.DataFrame(ticket_data)

# Streamlit UI for file upload and ticket classification
st.title("Ticket Assignment System")

# Initialize session state variables
if "disabled" not in st.session_state:
    st.session_state.disabled = False  # Initially, the email input and button are enabled
    st.session_state.email_validated = False  # Email not validated initially

# Handle button click event to disable inputs immediately
def handle_email_input():
    st.session_state.disabled = True  # Disable the email input and button
    if is_valid_email(Email):
        st.session_state.email_validated = True
    else:
        st.warning("Invalid email ID. Please refresh to retry.")

# Email input and button
Email = st.text_input("Enter your Email ID", disabled=st.session_state.disabled)
ebutton = st.button("Enter", disabled=st.session_state.disabled, on_click=handle_email_input)

# Show the file uploader only if the email is validated
if st.session_state.get("email_validated", False):
    uploaded_file = st.file_uploader("Upload Ticket Details (CSV/Excel/TXT)", type=["csv", "xlsx", "txt"])
    if uploaded_file is not None:
        # Read file into DataFrame
        if uploaded_file.name.endswith(".csv"):
            tickets_data = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(".xlsx"):
            tickets_data = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith(".txt"):
            tickets_data = process_txt_file(uploaded_file)

        st.write("Uploaded Ticket Data:")
        st.write(tickets_data)

        # Ticket assignments list
        ticket_assignments = []

        # Define email mappings
        email_mapping = {
            "Infra": os.getenv('INFRA_EMAIL', "infra@example.com"),
            "Application Team": os.getenv('APP_TEAM_EMAIL', "app_team@example.com"),
            "Access Management": os.getenv('ACCESS_MGMT_EMAIL', "access_mgmt@example.com")
        }

        # Process each ticket
        for _, ticket in tickets_data.iterrows():
            # Classify the ticket dynamically based on its description
            result = classify_ticket_with_langchain(ticket)

            # Assign recipient email based on result
            recipient = email_mapping.get(result, "unknown@example.com")

            ticket_assignments.append({
                "Ticket Title": ticket.get("Ticket Title", "Unknown"),
                "Assigned To": result,
                "Recipient Email": recipient
            })

        # Convert to DataFrame and display the assignments
        df = pd.DataFrame(ticket_assignments)
        st.write("Ticket Assignments:")
        st.table(df)

        # Create a CSV file in memory for download
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        # Add a download button for the CSV
        st.download_button(
            label="Download Assignments as CSV",
            data=csv_data.encode("utf-8"),
            file_name="ticket_assignments.csv",
            mime="text/csv"
        )
        # Authenticate and create the service
        service = authenticate_gmail()

        # Email details
        sender = 'projectchatbot.v1@gmail.com'
        subject = 'Tickets CSV Report'
        body = 'Dear User,\nPlease find the CSV report attached.'
        attachment_file_name = 'report.csv'

        # Send the email with CSV data as attachment
        send_email(service, sender, Email, subject, body, attachment_file_name, csv_data)
        st.info("Email sent successfully")
                
else:
    if st.session_state.get("disabled", False):
        st.info("Email not validated. Please refresh to retry.")
