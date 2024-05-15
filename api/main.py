from fastapi import APIRouter

from api.routes import submission, report

api_router = APIRouter()
api_router.include_router(submission.router, prefix='/submission', tags=['submissions'])
api_router.include_router(report.router, prefix="/reports", tags=['report'])
