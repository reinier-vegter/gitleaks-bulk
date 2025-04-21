from typing import Dict, Protocol, Tuple
from typing_extensions import TypedDict, runtime_checkable


class Repo(TypedDict):
    # base fields:
    type: str  # backend name
    id: int  # repository ID as used in the backend API
    name: str  # readable name of repository
    group: str  # readable group/project name of repo
    group_key: str  # key/ID of group, used in backend API
    repo_key: str  # key/ID of repo, used in backend API
    http_link: str  # http clone link without auth
    ssh_link: str  # git clone link using ssh
    # enrichment fields:
    contact_name: str
    contact_mail: str
    latest_branch: str  # last branch someting was committed to
    default_branch: str
    # other fields to be filled later:
    folder: str  # folder where repo clone is stored
    scanned: str  # scanned branch name
    secrets_found: int  # amount of secrets found
    report_path: str  # path of output report


class ConnectionInput(TypedDict):
    base_url: str
    token: str


@runtime_checkable
class VcsBackend(Protocol):
    @staticmethod
    def name() -> str:
        """Returns the name of the backend."""

    @staticmethod
    def shortname() -> str:
        """Returns the shortname of the backend."""

    def get_git_username_password(self) -> tuple[str, str]:
        """Return git username and password"""

    def setup(self, connection_input: ConnectionInput) -> None:
        """Sets up the backend connection."""

    def fetchAllRepos(self, progress: bool = False,
                      verbose: bool = False) -> dict[int, Repo]:
        """Fetches all repositories from the backend."""

    def enrichRepo(self, repo: Repo, verbose: bool = False) -> Repo:
        """Enriches repository data."""
