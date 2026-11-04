# AI-Assisted Adversary Simulation & Threat Analysis Platform

## Overview

The **AI-Assisted Adversary Simulation & Threat Analysis Platform** is a cybersecurity assessment framework that combines adversary simulation, MITRE ATT&CK technique mapping, automated data processing, Large Language Model (LLM)-based threat analysis, and security visualization.

The objective of this project is to simulate real-world attacker behavior inside a controlled laboratory environment, collect adversary activity data, analyze executed techniques, and transform raw security telemetry into SOC-style threat intelligence.

The platform integrates:

* MITRE Caldera for adversary emulation
* MITRE ATT&CK framework for technique identification
* Python-based data processing pipelines
* Groq LLM integration for automated threat analysis
* Dashboard for security visualization

---

# Architecture

```
MITRE Caldera
      |
      |
Windows Sandcat Agent
      |
      |
Adversary Operations
      |
      |
JSON Reports + Event Logs
      |
      |
Python Data Processing
      |
      |
MITRE ATT&CK Mapping
      |
      |
Groq LLM Threat Analysis
      |
      |
Security Dashboard
```

---

# Key Features

## Adversary Simulation

* Executes controlled attack simulations using MITRE Caldera.
* Uses Sandcat agents for endpoint interaction.
* Generates operation reports and execution telemetry.

## Data Processing Pipeline

* Parses Caldera JSON operation reports.
* Extracts security-relevant events.
* Converts raw simulation output into structured datasets.

## MITRE ATT&CK Mapping

* Maps adversary behavior to ATT&CK techniques.
* Identifies tactics and techniques observed during simulations.
* Provides structured threat context.

## AI-Based Threat Analysis

* Uses Groq LLM inference for automated analysis.
* Generates SOC-style summaries.
* Converts technical telemetry into analyst-friendly reports.

## Security Dashboard

Provides visualization of:

* Attack timeline
* Technique distribution
* Threat summaries
* Simulation results

---

# Project Structure

```
caldera-ai-project/

├── scripts/
│   ├── parser.py
│   ├── dataset_builder.py
│   └── ai_anal.py
│
├── dashboard/
|   ├── phase6/
|       └── output/
|           ├── screenshots
|           ├── groq_soc_report.md
|       ├── groq_analyzer.py
│   ├── prompt_templates/
│       ├── index.html
│   ├── app.py
│
├── data/
|   ├── smoke_test2_discovery_report.json
|   ├── smoke_test3_superspy_report.json
|   ├── smoke_test_defenseeva_report.json
|
├── reports/
│   ├── operation reports
│   └── processed datasets
│
└── README.md
```

---

# Technologies Used

## Cybersecurity Frameworks

* MITRE Caldera
* MITRE ATT&CK Framework
* Sandcat Agent

## Programming

* Python
* JSON processing
* Data transformation pipelines

## Artificial Intelligence

* Groq LLM API
* Prompt engineering
* Automated threat reporting

## Visualization

* Data visualization components

---

# Installation

## 1. Clone Repository

```bash
git clone https://github.com/imvk15/caldera-ai-project.git

cd caldera-ai-project
```

---

## 2. Create Python Environment

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Create a `.env` file:

```
GROQ_API_KEY=your_api_key_here
```

The API key should never be committed to the repository.

---

# Usage

## Data Processing

Convert Caldera reports into structured datasets:

```bash
python scripts/json_parser.py
```

Build processed security datasets:

```bash
python scripts/dataset_builder.py
```

---

## AI Threat Analysis

Run the LLM-based threat analysis module:

```bash
python phase6/groq_analyzer.py
```

Generated reports include:

* Threat summary
* Observed techniques
* Analyst recommendations
* Security insights

---

## Launch Dashboard

Start the dashboard:

```bash
python dashboard/app.py
```

The dashboard provides a visual representation of:

* Attack execution timeline
* ATT&CK technique mapping
* Threat analysis results

---

# Sample Workflow

1. Deploy MITRE Caldera in a controlled lab environment.
2. Execute adversary operations using configured abilities.
3. Collect operation reports and event logs.
4. Process collected data using Python scripts.
5. Map behaviors to MITRE ATT&CK techniques.
6. Analyze results using Groq LLM.
7. Display findings through the security dashboard.

---

# Security Considerations

This project is designed for:

* Cybersecurity education
* Defensive security research
* Controlled adversary simulation
* SOC analyst training

All simulations should be performed only in authorized environments.

Do not deploy adversary simulation capabilities against systems without explicit permission.

---

# Future Improvements

Potential enhancements:

* Real-time log ingestion
* Integration with SIEM platforms
* Automated incident response recommendations
* Additional ATT&CK technique coverage
* Multi-agent attack simulations
* Enhanced threat intelligence correlation

---

# Author

**imvk15**

Cybersecurity | Threat Analysis | Adversary Simulation | AI Security Research

---

# License

This project is intended for educational and research purposes.
