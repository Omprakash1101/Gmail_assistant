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

def main():
    # Example DataFrame
    import pandas as pd
    data = {
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Age': [25, 30, 35],
        'City': ['New York', 'San Francisco', 'Chicago']
    }
    df = pd.DataFrame(data)

    # Create CSV data in memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()

    # Authenticate and create the service
    service = authenticate_gmail()

    # Email details
    sender = 'projectchatbot.v1@gmail.com'  # Replace with your Gmail address
    to = 'omprakashgopi2k05@gmail.com'  # Replace with the recipient's email
    subject = 'CSV Report'
    body = 'Please find the CSV report attached.'
    attachment_file_name = 'report.csv'

    # Send the email with CSV data as attachment
    send_email(service, sender, to, subject, body, attachment_file_name, csv_data)

if __name__ == '__main__':
    main()
