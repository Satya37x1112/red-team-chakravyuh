import json
import os
from pathlib import Path

# ----------------------------
# Location of the JSON reports
# ----------------------------
DATA_FOLDER = Path("/home/kali/caldera-ai-project/data")


def parse_report(file_path):
    """Read one Caldera report and extract important information."""

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    print("=" * 80)
    print(f"Operation : {data.get('name')}")
    print(f"Planner   : {data.get('planner')}")
    print(f"Start     : {data.get('start')}")
    print(f"Finish    : {data.get('finish')}")
    print("=" * 80)

    steps = data.get("steps", {})

    for agent_id, agent_data in steps.items():

        print(f"\nAgent: {agent_id}")

        for step in agent_data.get("steps", []):

            print("-" * 60)
            print(f"Ability       : {step.get('name')}")
            print(f"Tactic        : {step['attack']['tactic']}")
            print(f"Technique ID  : {step['attack']['technique_id']}")
            print(f"Technique     : {step['attack']['technique_name']}")
            print(f"Executor      : {step.get('executor')}")
            print(f"Status        : {'Success' if step.get('status') == 0 else 'Failed'}")
            print(f"Command       : {step.get('command')}")

            if "output" in step:
                print("\nOutput:")
                print(step["output"])

            print()


def main():

    if not DATA_FOLDER.exists():
        print("Data folder not found.")
        return

    reports = list(DATA_FOLDER.glob("*report*.json"))

    if len(reports) == 0:
        print("No report JSON files found.")
        return

    for report in reports:
        print(f"\nReading {report.name}\n")
        parse_report(report)


if __name__ == "__main__":
    main()
