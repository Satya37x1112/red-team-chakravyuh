import os
import pandas as pd
from dotenv import load_dotenv
from groq import Groq


# Load environment

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# Load Caldera dataset

df = pd.read_csv(
    "/home/kali/caldera-ai-project/reports/caldera_dataset.csv"
)


print("[+] Loaded Caldera data")
print("[+] Total events:", len(df))


# Statistics

success = len(
    df[df["Status"]=="Success"]
)

failed = len(
    df[df["Status"]=="Failed"]
)


techniques = (
    df[
        [
        "Technique_ID",
        "Technique_Name",
        "Tactic"
        ]
    ]
    .drop_duplicates()
    .to_string(index=False)
)


events = (
    df[
        [
        "Ability",
        "Technique_ID",
        "Status"
        ]
    ]
    .head(50)
    .to_string(index=False)
)



prompt=f"""

You are a Senior SOC Analyst.

Analyze this MITRE Caldera adversary simulation.

This is a controlled cybersecurity lab.

Create a professional security assessment.

Simulation Statistics:

Total Actions:
{len(df)}

Successful Actions:
{success}

Failed Actions:
{failed}



MITRE ATT&CK Techniques:

{techniques}



Observed Activities:

{events}



Generate:

1. Executive Summary

2. Attack Simulation Overview

3. MITRE ATT&CK Mapping

4. Threat Actor Behavior Analysis

5. Detection Engineering Opportunities

6. Defensive Recommendations

7. Analyst Skills Demonstrated


Rules:

- Do not claim a real attack occurred.
- Do not exaggerate impact.
- Explain security relevance.
- Write professionally.
"""



response = client.chat.completions.create(

    model="llama-3.3-70b-versatile",

    messages=[
        {
        "role":"user",
        "content":prompt
        }
    ],

    temperature=0.2

)



report=response.choices[0].message.content



with open(
"output/groq_soc_report.md",
"w"
) as f:

    f.write(report)



print("[+] Report generated")
print("phase6/output/groq_soc_report.md")
