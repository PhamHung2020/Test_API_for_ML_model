import os.path

import torch
from celery import Celery
from sqlmodel import create_engine

from celery_task.model_tasks import ModelInfo, ModelManager
from config import app_settings

model_info_list = [
    ModelInfo("microsoft/codebert-base", "./codebert_classifier_model.pth", ["Python3"], "cuda")
]
model_manager = ModelManager(model_info_list)
model_manager.load()

db_engine = create_engine(str(app_settings.SQLALCHEMY_DATABASE_URI))

celery_app = Celery(
    "celery",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0",
    broker_connection_retry_on_startup=True
)


@celery_app.task()
def inference(data):
    path = data["path"]
    filename = data["filename"]
    programming_language = data["programming_language"]

    model_info = model_manager.get_model_by_language(programming_language)
    if model_info is None:
        print("No model info found")
        return 0

    try:
        fullpath = os.path.join(path, filename)
        with open(fullpath, "r") as f:
            content = f.read()

        if not content:
            print("No content")
            return 0

        with torch.no_grad():
            tokenized_code = model_info.tokenizer(
                content,
                return_tensors="pt",
                padding='max_length',
                max_length=512,
                truncation=True
            ).to(model_info.device)

            result = model_info.model(tokenized_code)

        return result.item()

    except IOError:
        print(f"Can't open {path}/{filename}")
