from dataclasses import dataclass


@dataclass(slots=True)
class JobCreateRequest:
    mode: str
    job_name: str
    filters: dict
    items: list[dict]
