from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware

from config import app_settings
from dto import DatasetProcessInfo
from celery_task.dataset_processing import celery_machine_code_detection_task, celery_codeql_task

app = FastAPI(
    title='API for Machine Code Detection System',
)

# Set all CORS enabled origins
if app_settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            str(origin).strip("/") for origin in app_settings.BACKEND_CORS_ORIGINS
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.post("/dataset/process")
async def process_dataset(dataset_info: DatasetProcessInfo):
    print("File path: ", dataset_info.folder_path)
    print("Dataset ID: ", dataset_info.dataset_id)
    print("File list: ", dataset_info.file_list)

    celery_machine_code_detection_data = {
        "report_id": dataset_info.report_id,
        "path": dataset_info.folder_path,
        "filename_list": dataset_info.file_list
    }
    machine_code_detection_task = celery_machine_code_detection_task.delay(celery_machine_code_detection_data)

    celery_codeql_data = {
        "path": dataset_info.folder_path,
        "report_id": dataset_info.report_id
    }
    codeql_task = celery_codeql_task.delay(celery_codeql_data)

    return {
        "message": "ok",
        "machine_code_detect_task": machine_code_detection_task.id,
        "codeql_task": codeql_task.id
    }


@app.post("/codeql")
async def codeql(path: str):
    if not path:
        raise HTTPException(status_code=422, detail="Path to source is not specified")

    data = {
        "path": path,
        "report_id": "6048689173898497488"
    }

    task = celery_codeql_task.delay(data)
    return {
        "message": "ok",
        "task": task.id
    }


import requests


@app.post("/collect")
async def collect(path: str, report_id: str):
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
            "result_dir": path
        },
        headers={
            'Authorization': f'Bearer {token}'
        }
    )

    if collect_codeql_response.status_code != 200:
        print("Cannot push codeql result files to Rails. Response: ", collect_codeql_response.status_code,
              collect_codeql_response.text)
        return

    print("Success")

    return {
        "message": "ok"
    }
