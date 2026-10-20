"""Common shape for a job offer, whatever source it comes from."""

from dataclasses import dataclass


@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    published_at: str
    salary: str | None
    description: str
