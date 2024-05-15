import shutil
from datetime import datetime
import requests

from celery import Celery
from celery.result import AsyncResult
from sqlmodel import create_engine, Session

from config import app_settings
from persistence import ReportFile, Report
from utils.constants import LANGUAGES
import os
from .codeql_lib import create_database_folder, create_results_folder, create_database, analyze_database, merge_results

db_engine = create_engine(str(app_settings.SQLALCHEMY_DATABASE_URI))

celery_app = Celery(
    "celery",
    broker="redis://127.0.0.1:6379/0",
    backend="redis://127.0.0.1:6379/0",
    broker_connection_retry_on_startup=True
)


@celery_app.task()
def celery_machine_code_detection_task(data):
    if not data["report_id"] or not data["path"] or not data["filename_list"]:
        print("validate failed")
        return

    filename_list: list[str] = data["filename_list"]
    path = data["path"]
    report_id = int(data["report_id"])
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
            task = celery_app.send_task('celery_task.inference.inference', args=[data], queue="inference")
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

    # try:
    #     shutil.rmtree(path)
    # except IOError:
    #     return


@celery_app.task()
def celery_codeql_task(data):
    if not data or not isinstance(data, dict) or "path" not in data or "report_id" not in data:
        print("Sent data is invalid: ", data)
        return

    path_to_source = data["path"]
    report_id = data["report_id"]

    if not os.path.exists(path_to_source) or not os.path.isdir(path_to_source):
        print("Invalid folder path: " + path_to_source)
        return

    database_folder = create_database_folder(path_to_source)
    print("Database folder created at:", database_folder)

    database_path = create_database("database", database_folder, path_to_source)
    if database_path:
        print(f"Database created at: {database_path}")
    else:
        print(f"Failed to create database")

    # for file in os.listdir(path_to_source):
    #     if file.endswith(".py"):
    #         file_path = os.path.join(path_to_source, file)
    #         database_path = create_database(file_path, database_folder, path_to_source)
    #         if database_path:
    #             print(f"Database created at: {database_path}")
    #         else:
    #             print(f"Failed to create database for {file_path}")

    results_folder = create_results_folder(path_to_source)
    print("Results folder created at:", results_folder)

    for file in os.listdir(database_folder):
        if file.endswith(".ql"):
            print("Analyzing database:", file)
            analyze_database(database_folder, results_folder, file)
            print("Analysis completed.")

    merge_results(results_folder)
    print("Results merged into a single file: codeql.csv")

    login_response = requests.post(
        "http://127.0.0.1:3000/auth/login",
        {
            "email": "phammanhhung1@gmail.com",
            "password": "PhamHung"
        }
    )

    if login_response.status_code != 202:
        print("Cannot login to Rails")
        return

    login_response_json = login_response.json()
    token = login_response_json['token']

    collect_codeql_response = requests.post(
        f"http://127.0.0.1:3000/reports/{report_id}/codeql",
        {
            "status": True,
            "result_dir": results_folder
        },
        headers={
            'Authorization': f'Bearer {token}'
        }
    )

    if collect_codeql_response.status_code != 200:
        print("Cannot push codeql result files to Rails. Response: ", collect_codeql_response.status_code, collect_codeql_response.text)
        return

    print("Success")
