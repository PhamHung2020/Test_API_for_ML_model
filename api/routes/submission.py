import os
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from typing import List, Annotated

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlmodel import select

from celery_task.dataset_processing import celery_machine_code_detection_task
from config import DbSessionDeps
from dto import (
    CodeSubmission,
    SubmissionRead,
    SubmissionFileRead,
    SubmissionDetailRead
)
from persistence import Submission, SubmissionFile

router = APIRouter()


@router.post("/test")
async def test(code_submission: CodeSubmission):
    if not code_submission.code:
        raise HTTPException(status_code=400, detail="Code must not be empty")

    return {
        "id": 12,
        "status": "queued",
        "url": "http://127.0.0.1:8000/test"
    }


@router.get("test_result/{task_id}")
async def get_test_result(task_id: str):
    result = AsyncResult(task_id)
    return {
        "status": result.status,
        "result": result.result
    }


@router.get("/list", response_model=List[SubmissionRead])
async def get_submission_list(db_session: DbSessionDeps):
    result = db_session.exec(select(Submission)).all()
    return result


@router.get("/get/{submission_id}", response_model=SubmissionDetailRead)
async def get_submission_detail(submission_id: int, db_session: DbSessionDeps):
    submission = db_session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=400, detail="Submission not found")

    return submission


@router.get("/result/{submission_file_id}", response_model=SubmissionFileRead)
async def get_submission_detail(submission_file_id: int, db_session: DbSessionDeps):
    submission = db_session.get(SubmissionFile, submission_file_id)
    if not submission:
        raise HTTPException(status_code=400, detail="Submission file not found")

    return submission


@router.get("/download/{submission_file_id}")
async def download_submission_file(submission_file_id: int, db_session: DbSessionDeps):
    submission_file = db_session.get(SubmissionFile, submission_file_id)
    if not submission_file:
        raise HTTPException(status_code=400, detail="Submission file not found")

    if not os.path.isfile(submission_file.path):
        raise HTTPException(status_code=400, detail="Submission file not found")

    return FileResponse(path=submission_file.path, media_type="application/octet-stream",
                        filename=submission_file.filename)


@router.post("/submit/code")
async def submit_code(
        submitted_code: CodeSubmission,
        db_session: DbSessionDeps
):
    code = submitted_code.code
    if not code or len(code) == 0 or len(code) > 10000:
        return {"status": "fail", "message": "Code is invalid"}

    submitted_time = datetime.now()
    filename = f"{str(uuid.uuid4())[:10]}_{submitted_time.strftime('%d_%m_%Y_%H_%M_%S')}"
    path = f"files/{filename}"
    with open(path, "w") as f:
        f.write(code)

    task = None
    try:
        submission = Submission(name=filename, submitted_time=submitted_time, status=1)
        db_session.add(submission)
        db_session.flush()
        print(submission.id)

        submission_file = SubmissionFile(
            filename=filename,
            path=f"files/{filename}",
            file_size=len(code),
            submission_id=submission.id
        )

        db_session.add(submission_file)
        db_session.flush()
        db_session.commit()

        data = {
            'id': submission_file.id,
            'path': path,
            'code': code
        }

        task = celery_machine_code_detection_task.delay(data)
        print(task.id)

    except Exception as e:
        print(e)
        db_session.rollback()

    return {
        "status": "success",
        "evaluation_status": "queued",
        "task_id": task.id
    }


@router.post("/submit/upload")
async def submit_upload(
        uploaded_files: Annotated[List[UploadFile], File()],
        db_session: DbSessionDeps,
        name: str = None,
):
    valid_files = []
    invalid_files = []
    for uploaded_file in uploaded_files:
        if uploaded_file.size <= 1024 * 1024 * 1024:
            valid_files.append(uploaded_file)
        else:
            invalid_files.append(uploaded_file)

    submission_files = []
    submission_datas = []
    tasks = []
    try:
        submitted_time = datetime.now()
        submission = Submission(name=uuid.uuid4() if name is None else name, submitted_time=submitted_time, status=1)
        db_session.add(submission)
        db_session.flush()
        print(submission.id)

        for uploaded_file in valid_files:
            file_extension = uploaded_file.filename[uploaded_file.filename.rindex('.'):]
            filename = f"{str(uuid.uuid4())[:10]}_{submitted_time.strftime('%d_%m_%Y_%H_%M_%S')}{file_extension}"
            path = f"files/{filename}"

            contents = await uploaded_file.read()
            code = contents.decode('utf-8')

            with open(path, 'wb') as file:
                file.write(contents)

            submission_file = SubmissionFile(
                filename=uploaded_file.filename,
                path=f"files/{filename}",
                file_size=len(code),
                submission_id=submission.id
            )

            db_session.add(submission_file)

            submission_files.append(submission_file)
            submission_datas.append({
                "path": path,
                "code": code
            })

        db_session.commit()

        for idx, submission_file in enumerate(submission_files):
            submission_datas[idx]['id'] = submission_file.id
            print(submission_file.id)
            task = celery_machine_code_detection_task.delay(submission_datas[idx])
            tasks.append(task.id)

    except Exception as e:
        print(e)
        db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "evaluation_status": "queued",
        "tasks": tasks
    }


@router.post("/submit/zip")
async def submit_upload(
        uploaded_file: Annotated[UploadFile, File()],
        db_session: DbSessionDeps,
        name: str = None,
):
    if uploaded_file.content_type != "application/zip":
        return {"message": "Must be a zip file"}

    print("Zip file uploaded")
    if uploaded_file.size > 1024*1024*1024:
        return {"message": "File too large"}

    contents = await uploaded_file.read()
    iob = BytesIO(contents)
    zip_data = zipfile.ZipFile(iob)
    zip_infos = zip_data.infolist()

    # iterate through each file
    filename_list = []
    for zip_info in zip_infos:
        if not zip_info.is_dir():
            filename_list.append(zip_info.filename)
            print(zip_info.filename)

    new_dir = str(uuid.uuid4())
    print(new_dir)
    zip_data.extractall(f"files/{new_dir}")

    submission_files = []
    submission_datas = []
    tasks = []

    try:
        submitted_time = datetime.now()
        submission = Submission(name=uuid.uuid4() if name is None else name, submitted_time=submitted_time, status=1)
        db_session.add(submission)
        db_session.flush()
        print(submission.id)

        for extracted_file in filename_list:
            filepath = os.path.join(new_dir, extracted_file)
            with open(f"files/{filepath}", "r") as f:
                extracted_content = f.read()

            submission_file = SubmissionFile(
                filename=extracted_file,
                path=f"files/{filepath}",
                file_size=len(extracted_content),
                submission_id=submission.id
            )

            db_session.add(submission_file)

            submission_files.append(submission_file)
            submission_datas.append({
                "path": filepath,
                "code": extracted_content
            })

        db_session.commit()

        for idx, submission_file in enumerate(submission_files):
            submission_datas[idx]['id'] = submission_file.id
            print(submission_file.id)
            task = celery_machine_code_detection_task.delay(submission_datas[idx])
            tasks.append(task.id)

    except Exception as e:
        print(e)
        db_session.rollback()

    return {
        "status": "success",
        "evaluation_status": "queued",
        "tasks": tasks
    }
