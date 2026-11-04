import json
from pathlib import Path
import pandas as pd

DATA_FOLDER = Path("/home/kali/caldera-ai-project/data")
OUTPUT_FOLDER = Path("/home/kali/caldera-ai-project/reports")

records = []

for report in DATA_FOLDER.glob("*report*.json"):

    with open(report, "r", encoding="utf-8") as f:
        data = json.load(f)

    operation = data.get("name")

    steps = data.get("steps", {})

    for agent, values in steps.items():

        for step in values.get("steps", []):

            attack = step.get("attack", {})

            records.append({

                "Operation": operation,

                "Agent": agent,

                "Ability": step.get("name"),

                "Technique_ID": attack.get("technique_id"),

                "Technique_Name": attack.get("technique_name"),

                "Tactic": attack.get("tactic"),

                "Status": "Success" if step.get("status") == 0 else "Failed",

                "Command": step.get("command"),

                "Executor": step.get("executor"),

            })

df = pd.DataFrame(records)

OUTPUT_FOLDER.mkdir(exist_ok=True)

df.to_csv(OUTPUT_FOLDER / "caldera_dataset.csv", index=False)

print(df)

print("\nDataset saved to reports/caldera_dataset.csv")
