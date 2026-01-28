"""
Documentation API Router
========================

REST API endpoints for automatic documentation generation.

Endpoints:
- POST /api/docs/generate - Generate documentation for a project
- GET /api/docs/{project_name} - List documentation files
- GET /api/docs/{project_name}/{filename} - Get documentation content
- POST /api/docs/preview - Preview README content
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from auto_documentation import DocumentationGenerator
from registry import get_project_path, list_registered_projects

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docs", tags=["documentation"])


# ============================================================================
# Request/Response Models
# ============================================================================


class GenerateDocsRequest(BaseModel):
    """Request to generate documentation."""

    project_name: str = Field(..., description="Project name or path")
    output_dir: str = Field("docs", description="Output directory for docs")
    generate_readme: bool = Field(True, description="Generate README.md")
    generate_api: bool = Field(True, description="Generate API documentation")
    generate_setup: bool = Field(True, description="Generate setup guide")


class GenerateDocsResponse(BaseModel):
    """Response from documentation generation."""

    project_name: str
    generated_files: dict
    message: str


class DocFile(BaseModel):
    """A documentation file."""

    filename: str
    path: str
    size: int
    modified: str


class ListDocsResponse(BaseModel):
    """List of documentation files."""

    files: list[DocFile]
    count: int


class PreviewRequest(BaseModel):
    """Request to preview README."""

    project_name: str = Field(..., description="Project name or path")


class PreviewResponse(BaseModel):
    """Preview of README content."""

    content: str
    project_name: str
    description: str
    tech_stack: dict
    features_count: int
    endpoints_count: int
    components_count: int


# ============================================================================
# Helper Functions
# ============================================================================


def get_project_dir(project_name: str) -> Path:
    """Get project directory from name or path."""
    project_path = get_project_path(project_name)
    if project_path:
        # Validate that registered project path is within allowed boundaries
        resolved_path = Path(project_path).resolve()
        _validate_project_path(resolved_path)
        return resolved_path

    path = Path(project_name)
    if path.exists() and path.is_dir():
        # Resolve and validate the arbitrary path
        resolved_path = path.resolve()
        _validate_project_path(resolved_path)
        return resolved_path

    raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")


def _validate_project_path(path: Path) -> None:
    """Validate that a project path is within allowed boundaries.

    Args:
        path: The resolved project path to validate

    Raises:
        HTTPException: If the path is outside allowed boundaries
    """
    # Use current working directory as the allowed projects root
    # This prevents directory traversal attacks
    allowed_root = Path.cwd().resolve()

    try:
        # First check if the path is within the allowed root directory (cwd)
        if path.is_relative_to(allowed_root):
            return
    except ValueError:
        pass

    # Check if the path matches or is within any registered project path
    try:
        registered_projects = list_registered_projects()
        for proj_name, proj_info in registered_projects.items():
            registered_path = Path(proj_info["path"]).resolve()
            try:
                if path == registered_path or path.is_relative_to(registered_path):
                    return
            except ValueError:
                continue
    except Exception as e:
        logger.warning(f"Failed to check registry: {e}")

    # Path is not within allowed boundaries
    raise HTTPException(
        status_code=403,
        detail=f"Access denied: Project path '{path}' is outside allowed directory boundary"
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/generate", response_model=GenerateDocsResponse)
async def generate_docs(request: GenerateDocsRequest):
    """
    Generate documentation for a project.

    Creates:
    - README.md in project root
    - SETUP.md in docs directory
    - API.md in docs directory (if API endpoints found)
    """
    project_dir = get_project_dir(request.project_name)

    try:
        generator = DocumentationGenerator(project_dir, request.output_dir)
        docs = generator.generate()

        generated = {}

        if request.generate_readme:
            readme_path = generator.write_readme(docs)
            generated["readme"] = str(readme_path.relative_to(project_dir))

        if request.generate_setup:
            setup_path = generator.write_setup_guide(docs)
            generated["setup"] = str(setup_path.relative_to(project_dir))

        if request.generate_api:
            api_path = generator.write_api_docs(docs)
            if api_path:
                generated["api"] = str(api_path.relative_to(project_dir))

        return GenerateDocsResponse(
            project_name=docs.project_name,
            generated_files=generated,
            message=f"Generated {len(generated)} documentation files",
        )

    except ValueError as e:
        logger.error(f"Invalid output directory: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Documentation generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_name}", response_model=ListDocsResponse)
async def list_docs(project_name: str):
    """
    List all documentation files for a project.

    Searches for Markdown files in project root and docs/ directory.
    """
    project_dir = get_project_dir(project_name)

    files = []

    # Check root for README
    for md_file in ["README.md", "CHANGELOG.md", "CONTRIBUTING.md"]:
        file_path = project_dir / md_file
        if file_path.exists():
            stat = file_path.stat()
            files.append(
                DocFile(
                    filename=md_file,
                    path=md_file,
                    size=stat.st_size,
                    modified=stat.st_mtime.__str__(),
                )
            )

    # Check docs directory
    docs_dir = project_dir / "docs"
    if docs_dir.exists():
        for md_file in docs_dir.glob("*.md"):
            stat = md_file.stat()
            files.append(
                DocFile(
                    filename=md_file.name,
                    path=str(md_file.relative_to(project_dir)),
                    size=stat.st_size,
                    modified=stat.st_mtime.__str__(),
                )
            )

    return ListDocsResponse(files=files, count=len(files))


@router.get("/{project_name}/{filename:path}")
async def get_doc_content(project_name: str, filename: str):
    """
    Get content of a documentation file.

    Args:
        project_name: Project name
        filename: Documentation file path (e.g., "README.md" or "docs/API.md")
    """
    project_dir = get_project_dir(project_name)

    # Resolve both paths to handle symlinks and get absolute paths
    resolved_project_dir = project_dir.resolve()
    resolved_file_path = (project_dir / filename).resolve()

    # Validate that the resolved file path is within the resolved project directory
    try:
        if os.path.commonpath([resolved_project_dir]) != os.path.commonpath([resolved_project_dir, resolved_file_path]):
            raise HTTPException(status_code=400, detail="Invalid filename: path outside project directory")
    except (ValueError, TypeError):
        # Handle case where path comparison fails
        raise HTTPException(status_code=400, detail="Invalid filename: path outside project directory")

    if not resolved_file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    if not resolved_file_path.suffix.lower() == ".md":
        raise HTTPException(status_code=400, detail="Only Markdown files are supported")

    try:
        content = resolved_file_path.read_text()
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")


@router.post("/preview", response_model=PreviewResponse)
async def preview_readme(request: PreviewRequest):
    """
    Preview README content without writing to disk.

    Returns the generated README content and project statistics.
    """
    project_dir = get_project_dir(request.project_name)

    try:
        generator = DocumentationGenerator(project_dir)
        docs = generator.generate()

        # Generate README content in memory
        lines = []
        lines.append(f"# {docs.project_name}\n")

        if docs.description:
            lines.append(f"{docs.description}\n")

        if any(docs.tech_stack.values()):
            lines.append("## Tech Stack\n")
            for category, items in docs.tech_stack.items():
                if items:
                    lines.append(f"**{category.title()}:** {', '.join(items)}\n")

        if docs.features:
            lines.append("\n## Features\n")
            for f in docs.features[:10]:
                status = "[x]" if f.get("status") == "completed" else "[ ]"
                lines.append(f"- {status} {f.get('name', 'Unnamed Feature')}")
            if len(docs.features) > 10:
                lines.append(f"\n*...and {len(docs.features) - 10} more features*")

        content = "\n".join(lines)

        return PreviewResponse(
            content=content,
            project_name=docs.project_name,
            description=docs.description,
            tech_stack=docs.tech_stack,
            features_count=len(docs.features),
            endpoints_count=len(docs.api_endpoints),
            components_count=len(docs.components),
        )

    except Exception as e:
        logger.error(f"Preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_name}/{filename:path}")
async def delete_doc(project_name: str, filename: str):
    """
    Delete a documentation file.

    Args:
        project_name: Project name
        filename: Documentation file path
    """
    project_dir = get_project_dir(project_name)

    # Resolve both paths to handle symlinks and get absolute paths
    resolved_project_dir = project_dir.resolve()
    resolved_file_path = (project_dir / filename).resolve()

    # Validate that the resolved file path is within the resolved project directory
    try:
        if os.path.commonpath([resolved_project_dir]) != os.path.commonpath([resolved_project_dir, resolved_file_path]):
            raise HTTPException(status_code=400, detail="Invalid filename: path outside project directory")
    except (ValueError, TypeError):
        # Handle case where path comparison fails
        raise HTTPException(status_code=400, detail="Invalid filename: path outside project directory")

    if not resolved_file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    if not resolved_file_path.suffix.lower() == ".md":
        raise HTTPException(status_code=400, detail="Only Markdown files can be deleted")

    try:
        resolved_file_path.unlink()
        return {"deleted": True, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {e}")
