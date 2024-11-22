import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from ...container import container
from ...services.dto import Status
from ...services.jobservice import JobItem, JobRequest

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/job",
    tags=["job"],
)


@router.post("/setup")
def setup_job(job_request: JobRequest) -> JobItem:
    try:
        return asdict(container.jobservice.setup_job_request(jobrequest=job_request))
    except ConnectionRefusedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error setting up job: {exc}") from exc


@router.get("/trigger")
def trigger_job():
    """triggers a job that was setup before. this call needs to be sent to primary only and via GPIO the nodes will execute the job."""
    return container.jobservice.trigger_execute_job()


@router.get("/reset")
def reset_job():
    return container.jobservice.reset_job()


@router.get("/last")
def get_last_jobitem() -> JobItem:
    try:
        jobitem = container.jobservice._db_jobs.get_recent_item()
        return asdict(jobitem)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="there is no item stored yet") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/{job_id}/status")
def get_job_status(job_id: str) -> Status:
    try:
        print(job_id)
        print(container.jobservice._db_jobs._db)
        jobitem = container.jobservice._db_jobs.get_item_by_id(job_id)
        return jobitem.status
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Error: {exc}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/{job_id}")
def get_jobitem(job_id: str) -> JobItem:
    try:
        return asdict(container.jobservice._db_jobs.get_item_by_id(job_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Error: {exc}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"something went wrong, Exception: {exc}") from exc


@router.get("/")
def get_jobs():
    return container.jobservice._db_jobs.get_list_as_dict()
