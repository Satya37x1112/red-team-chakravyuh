from flask import Flask, render_template
import pandas as pd


app = Flask(__name__)


DATA="../reports/caldera_dataset.csv"


@app.route("/")
def home():

    df=pd.read_csv(DATA)


    total=len(df)

    success=len(
        df[df["Status"]=="Success"]
    )

    failed=len(
        df[df["Status"]=="Failed"]
    )


    techniques=(
        df["Technique_Name"]
        .value_counts()
        .to_dict()
    )


    tactics=(
        df["Tactic"]
        .value_counts()
        .to_dict()
    )


    return render_template(
        "index.html",
        total=total,
        success=success,
        failed=failed,
        techniques=techniques,
        tactics=tactics
    )


app.run(
    host="0.0.0.0",
    port=5000
)
