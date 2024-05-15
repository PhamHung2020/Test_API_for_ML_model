import os.path

from celery import Celery
import torch
from sqlmodel import create_engine, Session
import shutil
from datetime import datetime

from config import app_settings
from persistence import SubmissionFile, ReportFile, Report

from celery_task.classifiy_code_task import ClassifyCodeTask
from celery_task.model_tasks import ModelInfo, ModelManager
from celery.result import AsyncResult
from utils.constants import LANGUAGES

model_info_list = [
    ModelInfo("microsoft/codebert-base", "./codebert_classifier_model.pth", ["Python3"], "cuda")
]
model_manager = ModelManager(model_info_list)
is_model_loaded = False

db_engine = create_engine(str(app_settings.SQLALCHEMY_DATABASE_URI))

celery_app = Celery(
    "celery",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0",
    broker_connection_retry_on_startup=True
)


@celery_app.task()
def inference(data):
    global is_model_loaded
    if not is_model_loaded:
        model_manager.load()
        is_model_loaded = True

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


@celery_app.task(
    bind=True,
    base=ClassifyCodeTask
)
def celery_classify_code_task(self, data):
    # TODO: validate data

    if 'id' not in data or 'code' not in data:
        return -1

    code_id = data['id']
    code = data['code']

    with torch.no_grad():
        if not (code or len(code)):
            return -1

        tokenized_code = self.tokenizer(
            code,
            return_tensors="pt",
            padding='max_length',
            max_length=512,
            truncation=True
        ).to(self.device)

        result = self.classifier(tokenized_code)

    with Session(db_engine) as db_session:
        submission_file = db_session.get(SubmissionFile, code_id)
        if not submission_file:
            return result.item()

        update_data = {
            'machine_probability': result.item(),
            'evaluation_time': datetime.now()
        }

        submission_file.sqlmodel_update(update_data)
        db_session.add(submission_file)
        db_session.commit()

    return result.item()


@celery_app.task()
def celery_machine_code_detection_task(data):
    if not data["report_id"] or not data["path"] or not data["filename_list"]:
        print("validate failed")
        return

    filename_list: list[str] = data["filename_list"]
    path = data["path"]
    report_id = data["report_id"]
    report_files = []
    sent_task = []

    for filename in filename_list:
        extension = filename[filename.rindex("."):]
        if not extension:
            report_files.append(ReportFile(
                    report_id=report_id,
                    filename=filename,
                    programming_language="undefined",
                    machine_code_probability=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now()))
            continue

        language_info = None
        for language in LANGUAGES:
            if language["extension"] == extension:
                language_info = language
        if language_info is not None:
            data = {
                "path": path,
                "filename": filename,
                "programming_language": language_info["name"]
            }
            task = celery_app.send_task('celery_task.main.inference', args=[data], queue="inference")
            sent_task.append({
                "task": task,
                "filename": filename,
                "programming_language": language_info["name"]
            })
        else:
            report_files.append(ReportFile(
                    report_id=report_id,
                    filename=filename,
                    programming_language="undefined",
                    machine_code_probability=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now()))
            continue

    while len(sent_task) > 0:
        remaining_task = []
        for task in sent_task:
            task_result = AsyncResult(task["task"].id)
            if task_result.status == "SUCCESS":
                report_files.append(ReportFile(
                    report_id=report_id,
                    filename=task["filename"],
                    programming_language=task["programming_language"],
                    machine_code_probability=task_result.result,
                    created_at=datetime.now(),
                    updated_at=datetime.now()))
            elif task_result.status == "FAILURE":
                report_files.append(ReportFile(
                    report_id=report_id,
                    filename=task["filename"],
                    programming_language=task["programming_language"],
                    machine_code_probability=-1,
                    created_at=datetime.now(),
                    updated_at=datetime.now()))
            else:
                remaining_task.append(task)

        sent_task = remaining_task

    try:
        with Session(db_engine) as db_session:
            with db_session.begin():
                for report_file in report_files:
                    db_session.add(report_file)

                report = db_session.get(Report, report_id)
                if not report:
                    raise Exception("Report not found")

                report.machine_code_detect_status = 1
                db_session.add(report)

    except Exception as e:
        print(e)

    try:
        shutil.rmtree(path)
    except IOError:
        return
