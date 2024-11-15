"""App"""

import pickle

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel


class Transaction(BaseModel):
    terminal_id: int
    hour_tx_datetime: float
    tx_amount: float
    percent_fraud_on_terminal: float


app = FastAPI()
with open("./src/model-1.pkl", "rb") as f:
    model = pickle.load(f)

@app.get("/")
def healthcheck():
    return {"status": "OK"}


@app.post("/predict")
def predict(transaction: Transaction):
    try:
        vector = np.array([
            int(transaction.terminal_id),
            float(transaction.hour_tx_datetime),
            float(transaction.tx_amount),
            float(transaction.percent_fraud_on_terminal)
        ]).reshape(1, -1)
        pred = model.predict(vector)
        ans = int(pred)
        return {"pred": ans}
    except Exception as e:
        return {"error": str(e)}