import os
import sys
from pathlib import Path
import argparse
import re
from textwrap import shorten

# ------------------------------
# Project Template Definition
# ------------------------------

STRUCTURE = {
    "app": {
        "__init__.py": "",
        "main.py":
'''from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import create_db_and_tables, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "HELLO HUMAN"}

''',

        "dependencies.py": "# Dependency definitions\n",

        "database.py":
'''from sqlmodel import SQLModel, create_engine

sqlite_file_name = "app//database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
''',

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

    template = f'''from fastapi import APIRouter, HTTPException
from app.models import {router_name}

router = APIRouter(prefix="/{router_name}", tags=["{router_name}"])


@router.get("/", summary="Get all {router_name}")
async def get_all():
    return {{"message": "Get all {router_name}"}}


@router.post("/", summary="Create a new {router_name}")
async def create_item():
    return {{"message": "Create {router_name}"}}


@router.get("/{{item_id}}", summary="Get {router_name} by ID")
async def get_item(item_id: int):
    return {{"message": f"Get {router_name} {{item_id}}"}}


@router.put("/{{item_id}}", summary="Update {router_name}")
async def update_item(item_id: int):
    return {{"message": f"Update {router_name} {{item_id}}"}}


@router.delete("/{{item_id}}", summary="Delete {router_name}")
async def delete_item(item_id: int):
    return {{"message": f"Delete {router_name} {{item_id}}"}}
'''

    router_path.write_text(template.strip() + "\n", encoding="utf-8")
    log(f"Created router: {router_path}", "success")

    register_router_in_main(router_name)


def make_model(model_name: str, force: bool = False) -> None:
    """Create a SQLModel file and a corresponding router."""
    if not valid_name(model_name):
        log(f"Invalid model name: '{model_name}'.", "error")
        sys.exit(1)

    models_dir = Path("app/models")
    models_dir.mkdir(parents=True, exist_ok=True)

    model_path = models_dir / f"{model_name}.py"
    if model_path.exists() and not force:
        log(f"Model '{model_name}' already exists. Use --force to overwrite.", "warning")
        return

    template = f'''from sqlmodel import Field, SQLModel


class {model_name.capitalize()}(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
'''

    model_path.write_text(template.strip() + "\n", encoding="utf-8")
    log(f"Created model: {model_path}", "success")

    # Automatically generate router
    create_router(model_name, force=force)


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


# ------------------------------
# CLI Entry Point
# ------------------------------

def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="FastAPI Project Scaffolding Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("list", help="List all registered endpoints")

    new_parser = subparsers.add_parser("new", help="Create a new project structure")
    new_parser.add_argument("path", nargs="?", default=".", help="Base directory for project")

    model_parser = subparsers.add_parser("makemodel", help="Create a new model (and router)")
    model_parser.add_argument("name", help="Model name")
    model_parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    args = parser.parse_args()

    if args.command == "new":
        target_dir = Path(args.path)
        create_structure(target_dir, STRUCTURE)
        log(f"Project structure created at: {target_dir.resolve()}", "success")

    elif args.command == "makemodel":
        make_model(args.name, force=args.force)

    elif args.command == "list":
        list_endpoints()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
