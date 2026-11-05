from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
AgentName = Literal["CEO", "DEV", "DESIGNER", "QA", "PESQUISADOR"]
Mode = Literal["manual", "supervised", "automatic"]
Status = Literal["backlog", "in_progress", "review", "done"]


class LoginInput(BaseModel):
    username: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class ProjectInput(BaseModel):
    name: Name
    description: Description = ""
    mode: Mode = "supervised"


class ProjectView(ProjectInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: int


class TaskInput(BaseModel):
    project_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    title: Title
    description: Description = ""
    agent: AgentName = "DEV"


class TaskUpdate(BaseModel):
    status: Status


class TaskView(TaskInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: Status
    created_at: int


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    resource_id: str
    summary: str
    actor: str
    created_at: int
