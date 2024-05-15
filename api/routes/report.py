from fastapi import APIRouter, HTTPException, Form, UploadFile
from config.deps import DbSessionDeps
from persistence import Report
from sqlmodel import select
from typing import List, Annotated

from dto import DatasetCreate

router = APIRouter()


@router.get("/list", response_model=List[Report])
async def list_report(db_session: DbSessionDeps):
    return db_session.exec(select(Report)).all()


@router.get("/{report_id}", response_model=Report)
async def get(report_id: int, db_session: DbSessionDeps):
    report = db_session.get(Report, {"id": report_id})
    if not report:
        raise HTTPException(status_code=400, detail={"msg": "Report not found"})

    return report


@router.post("/")
async def create(
        dataset_name: Annotated[str, Form(alias='dataset[name]')],
        dataset_programming_language: Annotated[str, Form(alias='dataset[programming_language]')],
        dataset_zipfile: Annotated[UploadFile, Form(alias='dataset[zipfile]')]
):
    print(dataset_name)
    print(dataset_programming_language)
    with open("test.zip", "wb") as f:
        f.write((await dataset_zipfile.read()))

    return {"status": "ok"}
