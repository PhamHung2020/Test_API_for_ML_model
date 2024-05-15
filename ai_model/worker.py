import redis
import time
import json
import torch
from sqlmodel import SQLModel, Field, Session, create_engine
from typing import Optional
from datetime import datetime
from load_model import get_model_tokenizer


class SubmissionFile(SQLModel, table=True):
    __tablename__ = "submission_file"
    id: int = Field(primary_key=True, default=None, nullable=False)
    filename: str = Field(title='filename')
    path: str = Field(title='path')
    machine_probability: Optional[float] = Field(title='machine_probability')
    evaluation_time: Optional[datetime] = Field(title='evaluation_time')
    file_size: int = Field(title='file_size')
    submission_id: int = Field(title='submission_id')


if __name__ == "__main__":

    device = "cuda"  # or 'cpu' if gpu is not available
    tokenizer, classifier = get_model_tokenizer(device)
    labels = ['HUMAN', 'MACHINE']

    r = redis.Redis(host='localhost', port=6379)

    engine = create_engine("mysql+pymysql://root:mypass@172.17.0.2:3306/code_detect_db")

    while True:
        item = r.rpop('data_queue')
        if item is None or not item:
            time.sleep(1)
            continue

        decoded_item = item.decode('utf-8')
        json_item = json.loads(decoded_item)
        print(json_item)

        # TODO: validate item

        if 'code' not in json_item:
            continue

        with ((torch.no_grad())):
            code = json_item['code']
            if not (code or len(code)):
                print({"status": "fail", "message": "Code is empty"})
                continue

            tokenized_code = tokenizer(
                code,
                return_tensors="pt",
                padding='max_length',
                max_length=512,
                truncation=True
            ).to(device)

            result = classifier(tokenized_code)

        with Session(engine) as db_session:
            submission_file = db_session.get(SubmissionFile, json_item['id'])
            if not submission_file:
                continue

            update_data = {
                'machine_probability': result.item(),
                'evaluation_time': datetime.now()
            }

            submission_file.sqlmodel_update(update_data)
            db_session.add(submission_file)
            db_session.commit()

