import os
import base64
import pandas as pd
import streamlit as st
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
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema.output_parser import StrOutputParser
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
import time
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

def get_original_email(service, user_id='me'):
    try:
        results = service.users().messages().list(userId=user_id, q = "is:unread", maxResults=1).execute()
        messages = results.get('messages', [])
        if not messages:
            print("No messages found.")
            return None
        
        message = service.users().messages().get(userId=user_id, id=messages[0]['id'], format='metadata').execute()
        thread_id = message['threadId']
        subject = None
        body=message['snippet']
        # Extract subject and message ID from headers
        for header in message['payload']['headers']:
            if header['name'].lower()=='content-type':
                contype=header['value'].split(';')[0]
            if header['name'].lower()=='from':
                to = header['value']
            if header['name'].lower() == 'subject':
                subject = header['value']
        
        print(f"Original Message ID: {messages[0]['id']}")
        print(f"Thread ID: {thread_id}")
        print(f"Subject: {subject}")
        return {
            'id': messages[0]['id'],
            'threadId': thread_id,
            'subject': subject,
            'to':to,
            'body':body,
            'content-type':contype,
        }
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    
def mark_as_read(service, message_id):
    # Labels you want to remove (UNREAD)
    msg_labels = {
        'removeLabelIds': ['UNREAD']
    }
    
    # Modify the message by removing the UNREAD label
    service.users().messages().modify(userId='me', id=message_id, body=msg_labels).execute()

    print(f"Message with ID: {message_id} marked as read.")


def create_message_with_attachment(sender, to, subject, body):
    """Create the MIME message with an attachment."""
    message = MIMEMultipart()
    message['from'] = sender
    message['to'] = to
    message['subject'] = subject

    # Attach the body text
    message.attach(MIMEText(body, 'plain'))
    # Encode the message as base64 URL-safe
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    return raw_message

def send_email(service, sender, to, subject, body):
    """Send the email via Gmail API."""
    try:
        raw_message = create_message_with_attachment(sender, to, subject, body)
        message = service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        print(f'Email sent successfully: {message["id"]}')
    except HttpError as error:
        print(f'An error occurred: {error}')

def classify_ticket_with_langchain(ticket):
    # Refined prompt template with more specific examples and instructions
    prompt = PromptTemplate(
        input_variables=["ticket"],
        template=""" 
        You are an AI assistant for classifying tickets into appropriate teams based on their descriptions and reply like a human , our aim is help the client by providing.
        
        Categories:
        1. Infra: Issues related to servers, networks, data centers, and hardware (e.g., server downtime, network outages, hardware issues).
        2. Application Team: Issues related to application bugs, coding errors, and user experience problems (e.g., login failures, incorrect data display, or feature malfunctions).
        3. Access Management: Requests for granting access to systems, tools, or accounts (e.g., new employee account setup, access requests).
        
        Examples:
        - Infra: "Server Downtime in Data Center 1. Several servers are unreachable."
        - Application Team: "Bug in User Authentication Module causing login errors."
        - Access Management: "Access request for a new employee to systems like email or CRM."

        Carefully read the description below and classify it into one of the above categories or else reply general for the input.

        Ticket Description: {ticket}
        """
    )

    # Initialize Ollama model
    if not os.getenv("HUGGINGFACEHUB_API_TOKEN"):
        os.environ["HUGGINGFACEHUB_API_TOKEN"] = "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"

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
                return "Email to Infra team"
            elif "application team" in classification:
                return "Email to Application Team"
            elif "access management" in classification:
                return "Email to Access Management team"
            else:
                return "Unknown"

    # Create LLMChain to process the ticket using the Ollama LLM and prompt
    llm_chain = LLMChain(
        llm=chat_model,
        prompt=prompt,
        output_parser=TeamOutputParser()
    )
    # Run the classification chain
    if "Description" in ticket:
        raw_result=llm_chain.invoke({"ticket":ticket["Description"]})
    elif "description" in ticket:
        raw_result=llm_chain.invoke({"ticket":ticket["Description"]})
    else:
        raw_result = llm_chain.invoke({"ticket": ticket})
    if isinstance(raw_result, dict) and "text" in raw_result:
        result = raw_result["text"].strip()
    else:
        raise ValueError(f"Unexpected LLM output format: {raw_result}")

    # Extract the classification result
    if result.lower()=="unknown":
        result="Hi, How can I help you, If any mistake kindly contact the admin"
    return result
st.title("Welcome to server")
service = authenticate_gmail()
while True:
        original_email = get_original_email(service)
        if not original_email:
            print("No email found to reply to.")
        else:
            print(original_email)
            to=original_email['to']
            sender='projectchatbot.v1@gmail.com'
            sub='RE: '+original_email['subject']
            if (original_email['content-type'].lower()=='multipart/alternative'):
                body="Dear User,\n"+classify_ticket_with_langchain(original_email["body"])
                print(body)
            else:
                body="Dear User,\nKindly use our website(https://tickets-v1.streamlit.app/) to rise a ticket with file.\nThank you and Regards,\nTicket Assist Team"

            mark_as_read(service,original_email['id'])
            send_email(service, sender, to, sub, body)
            time.sleep(5)
st.write("hi")

