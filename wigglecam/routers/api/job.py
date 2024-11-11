import logging

from fastapi import APIRouter, HTTPException, status

from ...container import container
from ...services.jobservice import JobItem, JobRequest

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/job",
    tags=["job"],
)


@router.post("/setup")
def setup_job(job_request: JobRequest) -> JobItem:
    try:
        return container.jobservice.setup_job_request(jobrequest=job_request).asdict()
    except ConnectionRefusedError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Error setting up job: {exc}") from exc


@router.get("/trigger")
def trigger_job():
    """triggers a job that was setup before. this call needs to be sent to primary only and via GPIO the nodes will execute the job."""
    return container.jobservice.trigger_execute_job()


@router.get("/reset")
def reset_job():
    return container.jobservice.reset_job()


@router.get("/list")
def get_jobs():
    """triggers a job that was setup before. this call needs to be sent to primary only and via GPIO the nodes will execute the job."""
    return container.jobservice._db.get_list_as_dict()


@router.get("/results/{job_id}")
def get_results(job_id: str) -> JobItem:
    return container.jobservice._db.get_item_by_id(job_id).asdict()
