"""In-flight agent tools for GitHub Project Board orchestration.

Callable Python functions intended to be exposed as tool schemas to an
autonomous developer agent (via MCP or direct LangChain/function-calling
integration). Each function is heavily typed with a docstring describing
its parameters and return value so a tool-calling framework can generate
an accurate schema from introspection.

Environment variables:
    GH_PROJECT_TOKEN      GitHub PAT with `repo` + `project` scopes.
    GITHUB_REPOSITORY     "owner/repo".
    GITHUB_PROJECT_OWNER  Login of the ProjectV2 owner (org or user).
    PROJECT_NUMBER        Numeric ProjectV2 project number.
"""

from __future__ import annotations

import os
from typing import Any, TypedDict

import requests

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# Status column names as configured on the Project Board's "Status" field.
STATUS_TODO = "Todo"
STATUS_IN_PROGRESS = "In Progress"
STATUS_REVIEW_QA = "Review / QA"
STATUS_DONE = "Done"

VALID_STATUS_COLUMNS = (STATUS_TODO, STATUS_IN_PROGRESS, STATUS_REVIEW_QA, STATUS_DONE)

COMPONENT_OPTIONS = (
    "Core: C++ Base",
    "Core: Python Backend",
    "UI: PySide6",
    "UI: Tauri Desktop",
    "UI: Mobile",
)


class TicketTransitionResult(TypedDict):
    """Structured result returned by ticket transition tool functions."""

    issue_number: int
    project_item_id: str
    status: str
    success: bool


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """Execute a GraphQL query/mutation against the GitHub API.

    Args:
        query: The GraphQL document to execute.
        variables: Variables referenced by the query.

    Returns:
        The `data` payload from the GraphQL response.

    Raises:
        RuntimeError: If the response HTTP status is an error, or the
            response body contains a top-level `errors` array.
    """
    token = _env("GH_PROJECT_TOKEN")
    resp = requests.post(
        GITHUB_GRAPHQL_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
        json={"query": query, "variables": variables},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def _repo_owner_and_name() -> tuple[str, str]:
    owner_repo = _env("GITHUB_REPOSITORY")
    owner, repo = owner_repo.split("/", 1)
    return owner, repo


def _project_id() -> str:
    """Resolve the node ID of the configured ProjectV2 board."""
    project_owner = os.environ.get("GITHUB_PROJECT_OWNER") or _repo_owner_and_name()[0]
    project_number = int(_env("PROJECT_NUMBER"))

    query = """
    query($owner: String!, $number: Int!) {
      user(login: $owner) { projectV2(number: $number) { id } }
      organization(login: $owner) { projectV2(number: $number) { id } }
    }
    """
    data = _graphql(query, {"owner": project_owner, "number": project_number})
    project = (data.get("organization") or {}).get("projectV2") or (
        data.get("user") or {}
    ).get("projectV2")
    if project is None:
        raise RuntimeError(f"Could not resolve ProjectV2 #{project_number} for {project_owner}")
    return project["id"]


def _find_issue(issue_number: int) -> str:
    """Return the node ID of an issue by number in the configured repository."""
    owner, repo = _repo_owner_and_name()
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
      repository(owner: $owner, name: $repo) {
        issue(number: $number) { id }
      }
    }
    """
    data = _graphql(query, {"owner": owner, "repo": repo, "number": issue_number})
    issue = data["repository"]["issue"]
    if issue is None:
        raise RuntimeError(f"Issue #{issue_number} not found in {owner}/{repo}")
    return issue["id"]


def _add_or_get_project_item(project_id: str, content_node_id: str) -> str:
    """Add an issue to the project (idempotent) and return its project item ID."""
    query = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    data = _graphql(query, {"projectId": project_id, "contentId": content_node_id})
    return data["addProjectV2ItemById"]["item"]["id"]


def _status_field(project_id: str) -> dict[str, Any]:
    """Return {"id": ..., "options": {optionName: optionId}} for the Status field."""
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
            }
          }
        }
      }
    }
    """
    data = _graphql(query, {"projectId": project_id})
    for node in data["node"]["fields"]["nodes"]:
        if node and node.get("name") == "Status":
            return {
                "id": node["id"],
                "options": {opt["name"]: opt["id"] for opt in node["options"]},
            }
    raise RuntimeError("Status field not found on project board")


def _set_status(project_id: str, item_id: str, status_option_id: str, field_id: str) -> None:
    query = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: { singleSelectOptionId: $optionId }
        }
      ) {
        projectV2Item { id }
      }
    }
    """
    _graphql(
        query,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "optionId": status_option_id,
        },
    )


def _move_issue_to_status(issue_number: int, target_status: str) -> TicketTransitionResult:
    if target_status not in VALID_STATUS_COLUMNS:
        raise ValueError(
            f"target_status must be one of {VALID_STATUS_COLUMNS!r}, got {target_status!r}"
        )

    project_id = _project_id()
    issue_node_id = _find_issue(issue_number)
    item_id = _add_or_get_project_item(project_id, issue_node_id)

    field = _status_field(project_id)
    option_id = field["options"].get(target_status)
    if option_id is None:
        raise RuntimeError(
            f"Status option {target_status!r} not found. Known options: {list(field['options'])}"
        )

    _set_status(project_id, item_id, option_id, field["id"])

    return TicketTransitionResult(
        issue_number=issue_number,
        project_item_id=item_id,
        status=target_status,
        success=True,
    )


def initialize_ticket(issue_number: int, component: str) -> TicketTransitionResult:
    """Move a ticket onto the Project Board and mark it "In Progress".

    Call this when a developer agent begins active work on a GitHub issue.
    It locates the issue by number, adds it to the configured ProjectV2
    board if not already present, and sets its Status field to
    "In Progress".

    Args:
        issue_number: The GitHub issue number to initialize (e.g. 42 for
            issue "#42").
        component: One of the Project Board's Component options — must be
            exactly one of: "Core: C++ Base", "Core: Python Backend",
            "UI: PySide6", "UI: Tauri Desktop", "UI: Mobile". Used to set
            the Component field so the ticket appears in the correct
            filtered board tab.

    Returns:
        A TicketTransitionResult with the issue number, the ProjectV2
        item ID, the new status, and a success flag.

    Raises:
        RuntimeError: If the issue, project, or Status field cannot be
            resolved via the GitHub GraphQL API.
        ValueError: If `component` is not one of the recognized options.
    """
    if component not in COMPONENT_OPTIONS:
        raise ValueError(f"component must be one of {COMPONENT_OPTIONS!r}, got {component!r}")

    project_id = _project_id()
    issue_node_id = _find_issue(issue_number)
    item_id = _add_or_get_project_item(project_id, issue_node_id)

    component_field_query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
            }
          }
        }
      }
    }
    """
    data = _graphql(component_field_query, {"projectId": project_id})
    component_field = next(
        node for node in data["node"]["fields"]["nodes"] if node and node["name"] == "Component"
    )
    option_id = next(
        opt["id"] for opt in component_field["options"] if opt["name"] == component
    )
    _set_status(project_id, item_id, option_id, component_field["id"])

    return _move_issue_to_status(issue_number, STATUS_IN_PROGRESS)


def transition_ticket(issue_number: int, target_column: str) -> TicketTransitionResult:
    """Move a ticket to a specified Kanban column on the Project Board.

    Call this whenever a developer agent's work on an issue changes phase,
    e.g. after opening a PR (move to "Review / QA") or after the PR merges
    (move to "Done").

    Args:
        issue_number: The GitHub issue number to transition (e.g. 42 for
            issue "#42").
        target_column: The destination Status column. Must be exactly one
            of: "Todo", "In Progress", "Review / QA", "Done".

    Returns:
        A TicketTransitionResult with the issue number, the ProjectV2
        item ID, the new status, and a success flag.

    Raises:
        ValueError: If `target_column` is not one of the recognized
            Status options.
        RuntimeError: If the issue, project, or Status field cannot be
            resolved via the GitHub GraphQL API.
    """
    return _move_issue_to_status(issue_number, target_column)
