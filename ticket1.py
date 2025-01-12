import os
import getpass
import pandas as pd
import streamlit as st
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema.output_parser import StrOutputParser
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
import io

# Function to classify tickets using LangChain and LLM
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

        Carefully read the description below and classify it into one of the above categories.

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

# Process each ticket
ste=input("Enter input:")
print(classify_ticket_with_langchain(ste))
# File upload component

