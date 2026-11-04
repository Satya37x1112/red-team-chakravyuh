import os
import pandas as pd
from dotenv import load_dotenv
from groq import Groq


# Load environment variables

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")


if not API_KEY:
    print("Groq API key missing")
    exit()


# Connect to Groq

client = Groq(
    api_key=API_KEY
)


# Load Caldera dataset

dataset = pd.read_csv(
    "/home/kali/caldera-ai-project/reports/caldera_dataset.csv"
)


# Convert data into text

security_data = dataset.to_string()


prompt = f"""

You are a senior SOC analyst reviewing a MITRE Caldera adversary simulation.

Important:
This is a controlled cybersecurity laboratory exercise.
Do not describe simulated actions as a confirmed real-world breach.

Analyze the Caldera execution results and create a professional security assessment.

Structure the report as:

1. Executive Summary

Explain:
- Purpose of the simulation
- Environment tested
- Overall security observations


2. Simulation Overview

Include:
- MITRE Caldera
- Adversary profile
- Host information
- Execution results


3. MITRE ATT&CK Technique Analysis

For every observed technique include:

- Technique ID
- Technique name
- Tactical category
- What the simulation tested
- Security impact


4. Detection Engineering Opportunities

Provide:

- Windows Event Logs to monitor
- PowerShell monitoring recommendations
- Endpoint detection ideas
- Possible SIEM alerts


5. Risk Assessment

Classify findings:

Critical
High
Medium
Low

Explain reasoning.


6. Defensive Recommendations

Include:

- Prevention controls
- Detection controls
- Monitoring improvements
- Hardening recommendations


7. Skills Demonstrated

Mention:

- MITRE ATT&CK knowledge
- Adversary emulation
- Security automation
- Python scripting
- AI assisted security analysis


Caldera Simulation Data:

{security_data}

"""


# Send request to LLM

response = client.chat.completions.create(

    model="llama-3.1-8b-instant",

    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ],

    temperature=0.3
)


report = response.choices[0].message.content


# Save report

with open(
    "/home/kali/caldera-ai-project/reports/AI_security_report.txt",
    "w",
    encoding="utf-8"
) as file:

    file.write(report)


print("AI Security Report Generated Successfully")
print("Location: reports/AI_security_report.txt")
