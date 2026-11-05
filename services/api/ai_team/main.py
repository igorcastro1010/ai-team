import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, update

from .agents import AGENTS, RESEARCHER
from .auth import COOKIE_NAME, authenticate, digest, require_owner
from .config import Settings
from .db import Database
from .github_actions import GitHubStore
from .github_routes import router as github_router
from .hermes_job_routes import router as hermes_jobs_router
from .hermes_routes import observation_snapshot as hermes_snapshot
from .hermes_routes import router as hermes_router
from .integrations import integration_statuses
from .issue_routes import router as issues_router
from .knowledge_routes import router as knowledge_router
from .memory_routes import router as memory_router
from .models import AuthSession, Event, Project, Task
from .office import office_snapshot
from .optimizer_routes import router as optimizer_router
from .report_routes import router as report_router
from .repository_routes import router as repository_router
from .run_routes import RunView
from .run_routes import router as runs_router
from .schedule_routes import ScheduleView
from .schedule_routes import router as schedule_router
from .schedules import ScheduleStore
from .schemas import (
    EventView,
    LoginInput,
    ProjectInput,
    ProjectView,
    TaskInput,
    TaskUpdate,
    TaskView,
)
from .vercel_routes import observation_snapshot
from .vercel_routes import router as vercel_router
from .workflow import WorkflowStore

TRANSITIONS = {
    "backlog": {"in_progress"},
    "in_progress": {"backlog", "review"},
    "review": {"in_progress", "done"},
    "done": {"backlog"},
}


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    settings = settings or Settings()
    database = database or Database(settings)

    @asynccontextmanager
    async def lifespan(app):
        if settings.environment != "production":
            database.initialize()
        yield

    app = FastAPI(
        title="AI TEAM",
        version="0.7.0",
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
    )
    app.state.database, app.state.settings = database, settings
    app.include_router(runs_router)
    app.include_router(repository_router)
    app.include_router(github_router)
    app.include_router(vercel_router)
    app.include_router(schedule_router)
    app.include_router(report_router)
    app.include_router(hermes_router)
    app.include_router(hermes_jobs_router)
    app.include_router(issues_router)
    app.include_router(optimizer_router)
    app.include_router(memory_router)
    app.include_router(knowledge_router)

    @app.middleware("http")
    async def protect_origin(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            if request.headers.get("origin") != settings.public_origin:
                return JSONResponse({"detail": "Origem não autorizada"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    Owner = Annotated[str, Depends(require_owner)]

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.7.0"}

    @app.post("/auth/login")
    def login(data: LoginInput, response: Response):
        with database.session() as db:
            db.info["session_ttl"] = settings.session_ttl_seconds
            token = authenticate(db, data.username, data.password)
        response.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            samesite="strict",
            secure=settings.environment == "production",
            max_age=settings.session_ttl_seconds,
            path="/",
        )
        return {"username": data.username.strip()}

    @app.get("/auth/me")
    def me(owner: Owner):
        return {"username": owner}

    @app.post("/auth/logout", status_code=204)
    def logout(request: Request, response: Response, owner: Owner):
        with database.session() as db:
            session = db.get(AuthSession, digest(request.cookies[COOKIE_NAME]))
            db.delete(session)
            db.add(Event(kind="auth.logout", summary="Sessão encerrada", actor=owner))
            db.commit()
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            httponly=True,
            samesite="strict",
            secure=settings.environment == "production",
        )

    @app.get("/projects", response_model=list[ProjectView])
    def projects(owner: Owner):
        with database.session() as db:
            return list(db.scalars(select(Project).order_by(Project.created_at.desc())))

    @app.post("/projects", response_model=ProjectView, status_code=201)
    def add_project(data: ProjectInput, owner: Owner):
        with database.session() as db:
            project = Project(**data.model_dump())
            db.add(project)
            db.flush()
            db.add(
                Event(
                    kind="project.created",
                    resource_id=project.id,
                    summary=f"Projeto criado: {project.name}",
                    actor=owner,
                )
            )
            db.commit()
            return project

    @app.get("/tasks", response_model=list[TaskView])
    def tasks(owner: Owner):
        with database.session() as db:
            return list(db.scalars(select(Task).order_by(Task.created_at.desc())))

    @app.post("/tasks", response_model=TaskView, status_code=201)
    def add_task(data: TaskInput, owner: Owner):
        with database.session() as db:
            if not db.get(Project, data.project_id):
                raise HTTPException(404, "Projeto não encontrado")
            task = Task(**data.model_dump())
            db.add(task)
            db.flush()
            db.add(
                Event(
                    kind="task.created",
                    resource_id=task.id,
                    summary=f"Tarefa criada: {task.title}",
                    actor=owner,
                )
            )
            db.commit()
            return task

    @app.patch("/tasks/{task_id}", response_model=TaskView)
    def move_task(task_id: str, data: TaskUpdate, owner: Owner):
        with database.session() as db:
            task = db.get(Task, task_id)
            if not task:
                raise HTTPException(404, "Tarefa não encontrada")
            previous = task.status
            if data.status not in TRANSITIONS[previous]:
                raise HTTPException(409, "Transição inválida. Atualize o quadro e tente novamente.")
            changed = db.execute(
                update(Task)
                .where(Task.id == task_id, Task.status == previous)
                .values(status=data.status)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Tarefa alterada por outra sessão. Atualize o quadro.")
            db.add(
                Event(
                    kind="task.moved",
                    resource_id=task.id,
                    summary=f"Atualização manual: {previous} → {data.status}",
                    actor=owner,
                )
            )
            db.commit()
            db.refresh(task)
            return task

    @app.get("/events", response_model=list[EventView])
    def events(owner: Owner):
        with database.session() as db:
            return list(db.scalars(select(Event).order_by(Event.sequence.desc()).limit(200)))

    @app.get("/integrations")
    def integrations(owner: Owner):
        result = integration_statuses()
        connection = GitHubStore(database).snapshot()["connection"]
        if connection:
            github = next(item for item in result if item["id"] == "github")
            github.update(
                status="verified",
                verified_at=connection["verified_at"],
                description=(
                    "Instalação seletiva verificada para ai-team. Escritas exigem aprovação."
                ),
            )
        vercel = observation_snapshot(database)["connection"]
        if vercel:
            integration = next(item for item in result if item["id"] == "vercel")
            integration.update(
                status="verified",
                verified_at=vercel["verified_at"],
                description="Consulta própria registrada; publicação desativada.",
            )
        if database.engine.dialect.name == "postgresql":
            for item in result:
                if item["id"] == "supabase":
                    item["status"] = "configured"
                    item["description"] = (
                        "PostgreSQL configurado. Provedor Supabase não homologado."
                    )
        return result

    @app.get("/workspace")
    def workspace(owner: Owner):
        store = WorkflowStore(database)
        runs = store.all()
        usage = store.usage()
        return {
            "version": "0.7.0",
            "owner": owner,
            "projects": [ProjectView.model_validate(p) for p in projects(owner)],
            "tasks": [TaskView.model_validate(t) for t in tasks(owner)],
            "events": [EventView.model_validate(e) for e in events(owner)],
            "agents": [*AGENTS, RESEARCHER],
            "runs": [RunView.model_validate(run) for run in runs],
            "approvals": [RunView.model_validate(run) for run in WorkflowStore(database).pending()],
            "usage": usage,
            "office": office_snapshot(runs, worker_online=usage["worker_online"]),
            "office_observed_at": int(time.time()),
            "integrations": integrations(owner),
            "github": GitHubStore(database).snapshot(),
            "vercel": observation_snapshot(database),
            "hermes": hermes_snapshot(database),
            "schedules": [
                ScheduleView.model_validate(row) for row in ScheduleStore(database).all()
            ],
        }

    return app


app = create_app()
