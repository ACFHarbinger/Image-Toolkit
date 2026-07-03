"""Asynchronous backlog sync: Gemini-driven Project Board updates.

Triggered by `.github/workflows/agent_sync.yml` on pushes to `main` that
modify `moon/ROADMAP.md` or `moon/CHANGELOG.md`. Reads the diff of the
triggering commit, asks Gemini 2.5 Pro to act as a Product Manager and
propose a strict JSON list of Project Board actions, then applies those
actions to the GitHub ProjectV2 board via the GraphQL API.

Environment variables:
    GH_PROJECT_TOKEN      GitHub PAT with `repo` + `project` scopes.
    GEMINI_API_KEY        API key for the google-genai SDK.
    GITHUB_REPOSITORY     "owner/repo", supplied automatically by Actions.
    GITHUB_SHA            Commit SHA that triggered the workflow.
    GITHUB_PROJECT_OWNER  Login of the ProjectV2 owner (org or user).
    PROJECT_NUMBER        Numeric ProjectV2 project number.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Literal

import requests
from google import genai

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
GEMINI_MODEL = "gemini-2.5-pro"

WATCHED_FILES = ("moon/ROADMAP.md", "moon/CHANGELOG.md")

COMPONENT_OPTIONS = (
    "Core: C++ Base",
    "Core: Python Backend",
    "UI: PySide6",
    "UI: Tauri Desktop",
    "UI: Mobile",
)

PRIORITY_OPTIONS = (
    "Tier 1: Core Engine",
    "Tier 2: QA Prototype",
    "Tier 3: Production App",
    "Tier 4: Backburner",
)

ActionType = Literal["create", "update", "close"]


@dataclass(frozen=True)
class BacklogAction:
    """A single Project Board mutation proposed by the model."""

    action: ActionType
    title: str
    component: str
    priority: str
    body: str = ""
    issue_number: int | None = None


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_diff_and_message(commit_sha: str) -> tuple[str, str]:
    """Return (diff, commit_message) for the watched files at `commit_sha`."""
    diff = subprocess.run(
        ["git", "diff", f"{commit_sha}~1", commit_sha, "--", *WATCHED_FILES],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    message = subprocess.run(
        ["git", "log", "-1", "--pretty=%B", commit_sha],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    return diff, message


def build_prompt(diff: str, commit_message: str) -> str:
    """Build the Gemini prompt instructing it to act as a Product Manager."""
    return f"""You are an experienced Product Manager for the Image-Toolkit project.

You will be given a git diff of `moon/ROADMAP.md` and/or `moon/CHANGELOG.md`
along with the commit message that introduced it. Read the diff and decide
which GitHub Project Board tickets should be created, updated, or closed as
a result.

Respond with ONLY a strict JSON array (no markdown fences, no prose) where
each element has this exact shape:

{{
  "action": "create" | "update" | "close",
  "title": "<issue title>",
  "component": "<one of: {', '.join(COMPONENT_OPTIONS)}>",
  "priority": "<one of: {', '.join(PRIORITY_OPTIONS)}>",
  "body": "<markdown body, empty string if action is close>",
  "issue_number": <int or null, required for update/close, null for create>
}}

Rules:
- "component" and "priority" MUST be copied verbatim from the option lists above.
- If nothing in the diff warrants a board change, return an empty array: []
- Do not invent issue numbers for "create" actions; leave issue_number null.
- Keep "title" under 80 characters.

Commit message:
{commit_message}

Diff:
{diff}
"""


def call_gemini(prompt: str) -> list[BacklogAction]:
    """Send the prompt to Gemini 2.5 Pro and parse the JSON response."""
    client = genai.Client(api_key=_env("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )

    raw = response.text or "[]"
    payload: list[dict[str, Any]] = json.loads(raw)

    actions: list[BacklogAction] = []
    for item in payload:
        component = item["component"]
        priority = item["priority"]
        if component not in COMPONENT_OPTIONS:
            raise ValueError(f"Model returned unknown component: {component!r}")
        if priority not in PRIORITY_OPTIONS:
            raise ValueError(f"Model returned unknown priority: {priority!r}")

        actions.append(
            BacklogAction(
                action=item["action"],
                title=item["title"],
                component=component,
                priority=priority,
                body=item.get("body", ""),
                issue_number=item.get("issue_number"),
            )
        )
    return actions


class GitHubProjectClient:
    """Thin GraphQL client for GitHub ProjectV2 + Issues mutations."""

    def __init__(self, token: str, owner: str, repo: str, project_number: int) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
            }
        )
        self.owner = owner
        self.repo = repo
        self.project_number = project_number
        self._project_id: str | None = None
        self._field_cache: dict[str, dict[str, Any]] = {}

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        resp = self._session.post(
            GITHUB_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise RuntimeError(f"GraphQL error: {payload['errors']}")
        return payload["data"]

    def get_project_id(self) -> str:
        if self._project_id is not None:
            return self._project_id

        query = """
        query($owner: String!, $number: Int!) {
          organizationOrUser: repositoryOwner(login: $owner) {
            ... on ProjectV2Owner {
              projectV2(number: $number) { id }
            }
          }
        }
        """
        # Fall back between user/org roots since ProjectV2Owner is polymorphic.
        query = """
        query($owner: String!, $number: Int!) {
          user(login: $owner) { projectV2(number: $number) { id } }
          organization(login: $owner) { projectV2(number: $number) { id } }
        }
        """
        data = self._post(query, {"owner": self.owner, "number": self.project_number})
        project = (data.get("organization") or {}).get("projectV2") or (
            data.get("user") or {}
        ).get("projectV2")
        if project is None:
            raise RuntimeError(
                f"Could not resolve ProjectV2 #{self.project_number} for owner {self.owner}"
            )
        self._project_id = project["id"]
        return self._project_id

    def get_field(self, field_name: str) -> dict[str, Any]:
        """Return {"id": ..., "options": {optionName: optionId}} for a project field."""
        if field_name in self._field_cache:
            return self._field_cache[field_name]

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
        data = self._post(query, {"projectId": self.get_project_id()})
        for node in data["node"]["fields"]["nodes"]:
            if not node or node.get("name") != field_name:
                continue
            info = {
                "id": node["id"],
                "options": {opt["name"]: opt["id"] for opt in node["options"]},
            }
            self._field_cache[field_name] = info
            return info

        raise RuntimeError(f"Project field {field_name!r} not found")

    def find_issue_node_id(self, issue_number: int) -> str:
        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) { id }
          }
        }
        """
        data = self._post(
            query,
            {"owner": self.owner, "repo": self.repo, "number": issue_number},
        )
        issue = data["repository"]["issue"]
        if issue is None:
            raise RuntimeError(f"Issue #{issue_number} not found in {self.owner}/{self.repo}")
        return issue["id"]

    def create_issue(self, title: str, body: str) -> tuple[str, int]:
        query = """
        mutation($repoId: ID!, $title: String!, $body: String!) {
          createIssue(input: {repositoryId: $repoId, title: $title, body: $body}) {
            issue { id number }
          }
        }
        """
        repo_id = self._get_repo_id()
        data = self._post(query, {"repoId": repo_id, "title": title, "body": body})
        issue = data["createIssue"]["issue"]
        return issue["id"], issue["number"]

    def close_issue(self, issue_node_id: str) -> None:
        query = """
        mutation($issueId: ID!) {
          closeIssue(input: {issueId: $issueId}) { issue { id } }
        }
        """
        self._post(query, {"issueId": issue_node_id})

    def _get_repo_id(self) -> str:
        query = """
        query($owner: String!, $repo: String!) {
          repository(owner: $owner, name: $repo) { id }
        }
        """
        data = self._post(query, {"owner": self.owner, "repo": self.repo})
        return data["repository"]["id"]

    def add_item_to_project(self, content_node_id: str) -> str:
        query = """
        mutation($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item { id }
          }
        }
        """
        data = self._post(
            query,
            {"projectId": self.get_project_id(), "contentId": content_node_id},
        )
        return data["addProjectV2ItemById"]["item"]["id"]

    def set_single_select_field(self, item_id: str, field_name: str, option_name: str) -> None:
        field = self.get_field(field_name)
        option_id = field["options"].get(option_name)
        if option_id is None:
            raise RuntimeError(
                f"Option {option_name!r} not found for field {field_name!r}. "
                f"Known options: {list(field['options'])}"
            )

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
        self._post(
            query,
            {
                "projectId": self.get_project_id(),
                "itemId": item_id,
                "fieldId": field["id"],
                "optionId": option_id,
            },
        )


def apply_action(client: GitHubProjectClient, action: BacklogAction) -> None:
    """Apply a single BacklogAction to the Project Board via GraphQL."""
    if action.action == "create":
        issue_node_id, issue_number = client.create_issue(action.title, action.body)
        item_id = client.add_item_to_project(issue_node_id)
        client.set_single_select_field(item_id, "Component", action.component)
        client.set_single_select_field(item_id, "Priority", action.priority)
        print(f"Created issue #{issue_number}: {action.title}")

    elif action.action == "update":
        if action.issue_number is None:
            raise ValueError("update action requires issue_number")
        issue_node_id = client.find_issue_node_id(action.issue_number)
        item_id = client.add_item_to_project(issue_node_id)
        client.set_single_select_field(item_id, "Component", action.component)
        client.set_single_select_field(item_id, "Priority", action.priority)
        print(f"Updated issue #{action.issue_number}: {action.title}")

    elif action.action == "close":
        if action.issue_number is None:
            raise ValueError("close action requires issue_number")
        issue_node_id = client.find_issue_node_id(action.issue_number)
        client.close_issue(issue_node_id)
        print(f"Closed issue #{action.issue_number}")

    else:
        raise ValueError(f"Unknown action type: {action.action!r}")


def main() -> int:
    owner_repo = _env("GITHUB_REPOSITORY")
    owner, repo = owner_repo.split("/", 1)
    commit_sha = _env("GITHUB_SHA")
    project_owner = os.environ.get("GITHUB_PROJECT_OWNER", owner)
    project_number = int(_env("PROJECT_NUMBER"))

    diff, commit_message = get_diff_and_message(commit_sha)
    if not diff.strip():
        print("No changes detected in watched files; nothing to sync.")
        return 0

    prompt = build_prompt(diff, commit_message)
    actions = call_gemini(prompt)
    if not actions:
        print("Model proposed no backlog actions.")
        return 0

    client = GitHubProjectClient(
        token=_env("GH_PROJECT_TOKEN"),
        owner=project_owner,
        repo=repo,
        project_number=project_number,
    )

    for action in actions:
        apply_action(client, action)

    return 0


if __name__ == "__main__":
    sys.exit(main())
