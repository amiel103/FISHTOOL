import os
import sys
from pathlib import Path
import argparse
import re
from textwrap import shorten

# ------------------------------
# Project Template Definition
# ------------------------------

FISH_LOGO = """

-------------------------------------------------------------------
                THANK YOU FOR USING FISH TOOL
-------------------------------------------------------------------                  
                                  @@@@@@@@@@@@@@@@                    
 (                       @@@@@@@@@@@@@@@@@@@@@@@@@@@@   @             
 @@@                @@@@@@@@@@@@*             @@@@@   @@@@@@@         
  @@@@@        @@@@@@@@@@                   @@@@@@  @@@@@@@   @@@     
    @@@@@@ (@@@@@@@@                       @@@@@@  &@@@@@@  O  @@@@   
      /@@@@@@@@@                         @@@@@@@&  @@@@@@@@   @@@@@@
    @@@@@&  @@@@@@@@@                      @@@@@@  @@@@@@@@@@@@@@@@   
  @@@@@         @@@@@@@@@@                  @@@@@@  @@@@@@@@@@@@      
 @@@                &@@@@@@@@@@@@@            @@@@@   @@@@@@@         
@                         @@@@@@@@@@@@@@@@@@@@@@@@@@@  @             
                                  @@@@@@@@@@@@@@&*                    
"""

MAIN_TEMPLATE = '''
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import create_db_and_tables, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "HELLO HUMAN, IM A FISH"}

'''


ALEMBIC_ENV_TEMPLATE = '''
from logging.config import fileConfig
from sqlmodel import SQLModel


# import database engine
from app.database import engine


# import all your models here
from app.models import *

from alembic import context

config = context.config
fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

'''


DATABASE_TEMPLATE = '''

from sqlmodel import SQLModel, create_engine

sqlite_file_name = "app//database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
'''

def MODEL_TEMPLATE(model_name): 
    MODEL_TEMPLATE = f'''
    
from sqlmodel import Field, SQLModel


class {model_name}(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    '''

    return MODEL_TEMPLATE


def ROUTER_TEMPLATE(router_name): 

    ROUTER_TEMPLATE = f'''
from fastapi import APIRouter, HTTPException , status
from app.models.{router_name} import {router_name}
from sqlmodel import Session, select
router = APIRouter(prefix="/{router_name}", tags=["{router_name}"])
from ..database import engine

@router.get("/", summary="Get all {router_name}")
async def get_all():
    with Session(engine) as session:
        statement = select({router_name})
        results = session.exec(statement).all()
        return results



@router.post("/", summary="Create a new {router_name}", status_code=status.HTTP_201_CREATED)
async def create_item(_{router_name} : {router_name}):
    with Session(engine) as session:
        session.add(_{router_name})
        session.commit()
        session.refresh(_{router_name})
        return _{router_name}


@router.get("/{{item_id}}", summary="Get {router_name} by ID")
async def get_item(item_id: int):
    with Session(engine) as session:
        item = session.get({router_name}, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{router_name} not found")
        return item



@router.put("/{{item_id}}", summary="Update {router_name}")
async def update_item(_{router_name} : {router_name} , item_id: int):
    with Session(engine) as session:

        item = session.get({router_name}, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{router_name} not found")

        for key, value in _{router_name}.model_dump(exclude_unset=True).items():
            setattr(item, key, value)

        session.add(item)
        session.commit()
        session.refresh(item)
        return item


@router.delete("/{{item_id}}", summary="Delete {router_name}" ,status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int):

    with Session(engine) as session:
        item = session.get({router_name}, item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{router_name} not found")

        session.delete(item)
        session.commit()
        return None

'''

    return ROUTER_TEMPLATE




STRUCTURE = {
    "app": {
        "__init__.py": "",
        "main.py":MAIN_TEMPLATE,
        "dependencies.py": "# Dependency definitions\n",
        "database.py": DATABASE_TEMPLATE,
        "routers": {"__init__.py": ""},
        "models": {"__init__.py": ""},
        "internal": {
            "__init__.py": "",
            "admin.py": "# Internal admin routes\n",
        },
    }
}

# ------------------------------
# Utility Functions
# ------------------------------

def log(message: str, kind: str = "info"):
    """Pretty print messages with icons."""
    icons = {
        "info": "📄",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
    }
    print(f"{icons.get(kind, '')} {message}")


def valid_name(name: str) -> bool:
    """Check if a name is a valid Python identifier."""
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))


# ------------------------------
# Core Functions
# ------------------------------

def create_structure(base_path: Path, structure: dict) -> None:
    """Recursively create directories and files from a structure dictionary."""
    for name, content in structure.items():
        path = base_path / name
        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            create_structure(path, content)
        else:
            path.write_text(content.strip() + "\n", encoding="utf-8")
            log(f"Created file: {path.relative_to(base_path.parent)}", "success")


def create_router(router_name: str, force: bool = False) -> None:
    """Generate a FastAPI router file."""
    if not valid_name(router_name):
        log(f"Invalid router name: '{router_name}'.", "error")
        sys.exit(1)

    router_dir = Path("app/routers")
    router_dir.mkdir(parents=True, exist_ok=True)

    router_path = router_dir / f"{router_name}.py"
    if router_path.exists() and not force:
        log(f"Router '{router_name}' already exists. Use --force to overwrite.", "warning")
        return

    template = ROUTER_TEMPLATE(router_name)

    router_path.write_text(template.strip() + "\n", encoding="utf-8")
    log(f"Created router: {router_path}", "success")

    register_router_in_main(router_name)


def replace_env_file():
    """Replace Alembic's env.py with the SQLModel-compatible template."""
    env_path = Path("migrations/env.py")
    if not env_path.exists():
        log("⚠️ Alembic env.py not found. Did you run 'alembic init migrations'?", "warning")
        return

    env_path.write_text(ALEMBIC_ENV_TEMPLATE.strip() + "\n", encoding="utf-8")
    log("✅ Replaced Alembic env.py with SQLModel-compatible template.", "success")

def register_sqlmodel_in_mako():
    """Ensure 'import sqlmodel' is present in Alembic's script.py.mako template."""
    mako_path = Path("migrations/script.py.mako")
    if not mako_path.exists():
        log("⚠️ script.py.mako not found in migrations directory.", "warning")
        return

    content = mako_path.read_text(encoding="utf-8")

    # Check if import already exists
    if "import sqlmodel" in content:
        log("✅ 'import sqlmodel' already registered in script.py.mako.", "info")
        return

    # Find position after 'from typing import Sequence, Union'
    lines = content.splitlines()
    new_lines = []
    inserted = False

    for line in lines:
        new_lines.append(line)
        if not inserted and line.strip().startswith("from typing import Sequence, Union"):
            new_lines.append("import sqlmodel")
            inserted = True

    updated_content = "\n".join(new_lines)
    mako_path.write_text(updated_content, encoding="utf-8")
    log("🔗 Added 'import sqlmodel' to script.py.mako.", "success")

def register_model_init( models_dir ,  model_name):
    init_path = models_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text("", encoding="utf-8")

    content = init_path.read_text(encoding="utf-8").strip().splitlines()
    import_line = f"from .{model_name} import {model_name}"

    # Add import line if not present
    if import_line not in content:
        content.append(import_line)

    # Rebuild __all__ list
    model_names = []
    for line in content:
        match = re.match(r"from \.\w+ import (\w+)", line)
        if match:
            model_names.append(match.group(1))


    models_names_str = ", ".join(f'"{n}"' for n in model_names)
    all_line = f"__all__ = [{models_names_str}]"

    # Remove any old __all__ lines
    content = [line for line in content if not line.strip().startswith("__all__")]
    content.append("")  # spacer line
    content.append(all_line)

    init_path.write_text("\n".join(content).strip() + "\n", encoding="utf-8")
    log(f"Updated models/__init__.py with '{model_name}' import.", "success")


def make_model(model_name: str, force: bool = False) -> None:
    """Create a SQLModel file and a corresponding router."""
    model_name = model_name.capitalize()
    if not valid_name(model_name):
        log(f"Invalid model name: '{model_name}'.", "error")
        sys.exit(1)

    models_dir = Path("app/models")
    models_dir.mkdir(parents=True, exist_ok=True)

    model_path = models_dir / f"{model_name}.py"
    if model_path.exists() and not force:
        log(f"Model '{model_name}' already exists. Use --force to overwrite.", "warning")
        return

    template = MODEL_TEMPLATE(model_name)

    model_path.write_text(template.strip() + "\n", encoding="utf-8")
    log(f"Created model: {model_path}", "success")

    # Automatically generate router
    create_router(model_name, force=force)
    register_model_init( models_dir ,  model_name)


def make_migrations(message) -> None:

    exit_code = os.system(f"alembic revision --autogenerate -m {message}")

    if exit_code == 0:
        log("created migrations.", "success")
    else:
        log("exited with errors.", "error")

def migrate() -> None:

    exit_code = os.system(f"alembic upgrade head")

    if exit_code == 0:
        log("migrations done", "success")
    else:
        log("exited with errors.", "error")
    


# ------------------------------
# Router Registration
# ------------------------------

def register_router_in_main(router_name: str) -> None:
    """Append import and include_router lines to app/main.py if not already present."""
    main_path = Path("app/main.py")

    if not main_path.exists():
        log("⚠️ app/main.py not found. Skipping router registration.", "warning")
        return

    content = main_path.read_text(encoding="utf-8")

    import_line = f"from app.routers import {router_name}"
    include_line = f"app.include_router({router_name}.router)"

    if import_line in content and include_line in content:
        log(f"Router '{router_name}' already registered in main.py.", "info")
        return

    lines = content.splitlines()
    new_lines = []
    inserted_import = False
    inserted_include = False

    for line in lines:
        new_lines.append(line)
        if not inserted_import and line.strip().startswith("from app.routers import"):
            new_lines.append(import_line)
            inserted_import = True

    if not inserted_import:
        for i, line in enumerate(new_lines):
            if "FastAPI" in line:
                new_lines.insert(i + 1, import_line)
                inserted_import = True
                break

    for i, line in enumerate(new_lines):
        if not inserted_include and line.strip().startswith("app ="):
            new_lines.insert(i + 1, include_line)
            inserted_include = True
            break

    if not inserted_include:
        new_lines.append(include_line)

    updated_content = "\n".join(new_lines) + "\n"
    main_path.write_text(updated_content, encoding="utf-8")

    log(f"🔗 Registered '{router_name}' router in app/main.py", "success")


# ------------------------------
# List Endpoints Command
# ------------------------------

def list_endpoints() -> None:
    """Scan all routers in app/routers/ and list the defined endpoints."""
    router_dir = Path("app/routers")
    if not router_dir.exists():
        log("⚠️ No routers directory found. Nothing to list.", "warning")
        return

    route_pattern = re.compile(
        r"@router\.(get|post|put|delete|patch)\((.*?)\)",
        re.IGNORECASE | re.DOTALL,
    )

    endpoints = []

    for router_file in router_dir.glob("*.py"):
        if router_file.name == "__init__.py":
            continue

        text = router_file.read_text(encoding="utf-8")
        for match in route_pattern.finditer(text):
            method = match.group(1).upper()
            args = match.group(2)
            path_match = re.search(r"['\"](.*?)['\"]", args)
            route_path = path_match.group(1) if path_match else "(unknown)"

            endpoints.append({
                "router": router_file.stem,
                "method": method,
                "path": route_path,
            })

    if not endpoints:
        log("No endpoints found in routers.", "warning")
        return

    endpoints.sort(key=lambda e: (e["router"], e["path"]))

    print("\n📋 Registered Endpoints:")
    print("-" * 60)
    print(f"{'Router':15} {'Method':10} {'Path'}")
    print("-" * 60)
    for ep in endpoints:
        print(f"{ep['router']:15} {ep['method']:10} {shorten(ep['path'], width=40)}")
    print("-" * 60)
    print(f"Total: {len(endpoints)} endpoints\n")



def initialize_project() -> None:
    """Install dependencies from requirements.txt."""
    requirements_path = Path("requirements.txt")
    if not requirements_path.exists():
        log("requirements.txt not found in the current directory.", "error")
        sys.exit(1)

    log("Installing dependencies from requirements.txt...", "info")
    exit_code = os.system(f"{sys.executable} -m pip install -r {requirements_path}")
    if exit_code == 0:
        log("Dependencies installed successfully ✅", "success")
        migrate = os.system("alembic init migrations")
        if migrate == 0 :
            register_sqlmodel_in_mako()
            replace_env_file()
    else:
        log("Failed to install some dependencies. Check the error above.", "error")

def serve_app() -> None:
    """Run the FastAPI app with Uvicorn in reload mode."""
    log("Starting FastAPI development server... 🚀", "info")

    # Ensure you're in the app directory
    app_path = Path("app/main.py")
    if not app_path.exists():
        log("app/main.py not found. Make sure you're in the project root.", "error")
        sys.exit(1)

    # Run the server
    exit_code = os.system("py -m uvicorn app.main:app --reload")

    if exit_code == 0:
        log("Server stopped gracefully.", "success")
    else:
        log("Server exited with errors.", "error")


# ------------------------------
# CLI Entry Point
# ------------------------------

def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="FastAPI Project Scaffolding Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("list", help="List all registered endpoints")
    subparsers.add_parser("init", help="Install dependencies from requirements.txt")
    subparsers.add_parser("serve", help="Run the FastAPI app using Uvicorn with reload")
    subparsers.add_parser("migrate", help="Run migrations")

    new_parser = subparsers.add_parser("new", help="Create a new project structure")
    new_parser.add_argument("path", nargs="?", default=".", help="Base directory for project")

    model_parser = subparsers.add_parser("makemodel", help="Create a new model (and router)")
    model_parser.add_argument("name", help="Model name")
    model_parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    migrations_parser = subparsers.add_parser("makemigrations", help="Create a new migrations")
    migrations_parser.add_argument("message", help="migration message")


    

    args = parser.parse_args()

    if args.command == "new":
        target_dir = Path(args.path)
        create_structure(target_dir, STRUCTURE)
        log(f"Project structure created at: {target_dir.resolve()}", "success")
        print(FISH_LOGO)

    elif args.command == "makemodel":
        make_model(args.name, force=args.force)

    elif args.command == "list":
        list_endpoints()

    elif args.command == "init":
        initialize_project()
    elif args.command == "serve":
        serve_app()
    elif args.command == "makemigrations":
        make_migrations()
    elif args.command == "migrate":
        migrate()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
