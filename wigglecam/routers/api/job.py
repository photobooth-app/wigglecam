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
        return container.jobconnectedservice.setup_job_request(jobrequest=job_request)
    except ConnectionRefusedError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Error setting up job: {exc}") from exc


@router.get("/trigger")
def trigger_job():
    """triggers a job that was setup before. this call needs to be sent to primary only and via GPIO the nodes will execute the job."""
    return container.jobconnectedservice.trigger_execute_job()


@router.get("/list")
def get_jobs():
    """triggers a job that was setup before. this call needs to be sent to primary only and via GPIO the nodes will execute the job."""
    return container.jobconnectedservice.db_get_list_as_dict()


@router.get("/results/{job_id}")
def get_results(job_id: str) -> JobItem:
    raise NotImplementedError
    # return container.job_service.get_job_results(job_id=job_id)
