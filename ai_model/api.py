
from fastapi import FastAPI, Body
from pydantic import BaseModel
import torch

from load_model import get_model_tokenizer

tokenizer, classifier = get_model_tokenizer()
device = "cuda"
labels = ['HUMAN', 'MACHINE']

app = FastAPI()


class CodeSubmission(BaseModel):
    code: str


@app.post("/eval")
async def evaluate(submission: CodeSubmission = Body(description="Code that needs detecting")):
    with torch.no_grad():
        code = submission.code
        if not (code or len(code)):
            return {"status": "fail", "message": "Code is empty"}

        tokenized_code = tokenizer(code, return_tensors="pt", padding='max_length', max_length=512, truncation=True).to(device)
        result = classifier(tokenized_code)
        label_index = torch.argmax(result)

        return {
            "status": "success",
            "machine_generated_prob": result[label_index].item(),
            "message": f"Code is probably generated by {labels[label_index]}"
        }