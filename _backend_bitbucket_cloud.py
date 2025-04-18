from datetime import datetime, UTC
from typing import Dict, Any, Tuple
from atlassian import Bitbucket
from data_types import Repo, ConnectionInput, VcsBackend
from progress.bar import Bar


class BitbucketCloudBackend(VcsBackend):
    client: Any = None
    endpoint_identifier = ""
    connection_input = None
    username = None
    token = None

    @staticmethod
    def name() -> str:
        return "bitbucket_cloud"

    @staticmethod
    def shortname() -> str:
        return "bc"

    def get_git_username_password(self) -> Tuple[str, str]:
        return self.username, self.token

    def setup(self, connection_input: ConnectionInput) -> None:
        self.connection_input = connection_input
        self.endpoint_identifier = "https://api.bitbucket.org/2.0"
        print(f"({self.name()}) Connecting to {self.endpoint_identifier}")

        if ':' in connection_input["token"]:
            tmp = connection_input["token"].split(':', 1)
            self.username = tmp[0]
            self.token = tmp[1]
        else:
            raise Exception("Username missing from token. Format token like '[username]:[token]'")

        try:
            self.client = Bitbucket(
                url=self.endpoint_identifier,
                username=self.username,
                password=self.token,
                cloud=True
            )

            # Verify connection by trying to fetch workspaces
            workspaces_response = self.client.get('workspaces')
            if not workspaces_response or 'values' not in workspaces_response or not workspaces_response['values']:
                raise Exception("No workspaces found. Check your token and permissions.")
        except Exception as e:
            raise Exception(
                f"Failed to setup Bitbucket Cloud connection. Check your credentials and URL: {str(e)}") from e
        return self

    def fetchAllRepos(self, progress: bool = False, verbose: bool = False) -> Dict[int, Repo]:
        print(f"({self.name()}) Fetching repo data from {self.endpoint_identifier}")
        if self.client is None:
            raise Exception("Bitbucket Cloud client is not set up. Call setup() first.")

        try:
            # Get all workspaces (equivalent to projects in Bitbucket Server)
            workspaces_response = self.client.get('workspaces')
            workspaces = workspaces_response.get('values', [])
        except Exception as e:
            raise Exception(f"Failed to fetch workspaces from Bitbucket Cloud: {str(e)}") from e

        repos: Dict[int, Repo] = {}
        bar = Bar('Fetching repo data for workspaces', max=len(workspaces)) if progress else None

        for workspace in workspaces:
            workspace_slug = workspace.get("slug")
            if verbose: print(f"Fetching repo data for workspace [{workspace_slug}]")

            try:
                # Get all repositories in the workspace
                repos_response = self.client.get(f'repositories/{workspace_slug}')
                workspace_repos = repos_response.get('values', [])
            except Exception as e:
                raise Exception(f"Failed to fetch repositories for workspace {workspace_slug}: {str(e)}") from e

            for repo_item in workspace_repos:
                # Skip archived repositories (TODO)
                if repo_item.get("type") == "repository":

                    # Extract clone links
                    clone_link = None
                    http_link = None
                    for link in repo_item.get("links", {}).get("clone", []):
                        if link.get("name") == "ssh":
                            clone_link = link.get("href")
                        elif link.get("name") == "https":
                            http_link = link.get("href")

                    # Generate a unique repo_id based on the repo UUID
                    # Using hash to convert the UUID string to an integer for compatibility with existing code
                    uuid = repo_item.get("uuid", "")
                    repo_id = hash(uuid) & 0x7FFFFFFF  # Ensure positive integer

                    repo_obj: Repo = {
                        "type": self.name(),
                        "id": repo_id,
                        "name": repo_item.get("name"),
                        "group": workspace.get("name"),
                        "group_key": workspace_slug,
                        "repo_key": repo_item.get("slug"),
                        "ssh_link": clone_link,
                        "http_link": http_link,
                        "contact_name": None,
                        "contact_mail": None,
                        "latest_branch": None,
                        "default_branch": repo_item.get("mainbranch", {}).get("name") if repo_item.get(
                            "mainbranch") else None,
                        "folder": None,
                        "scanned": None,
                        "secrets_found": None,
                        "report_path": None,
                    }

                    repos[repo_id] = repo_obj

            if progress:
                bar.next()

        if progress:
            bar.finish()

        if not repos:
            raise Exception("No repositories found. Check your token and permissions.")

        return repos

    def enrichRepo(self, repo: Repo, verbose: bool = False) -> Repo:
        if self.client is None:
            raise Exception("Bitbucket Cloud client is not set up. Call setup() first.")

        try:
            workspace_slug = repo["group_key"]
            repo_slug = repo["repo_key"]

            # Get commits to find the latest one
            commits_response = self.client.get(f'repositories/{workspace_slug}/{repo_slug}/commits')
            commits = commits_response.get('values', [])

            if commits:
                latest_commit = commits[0]  # First commit is the latest one

                # Extract commit date
                if 'date' in latest_commit:
                    commit_date_str = latest_commit['date']
                    try:
                        # Format is ISO 8601, e.g. "2023-01-15T12:34:56.789Z"
                        commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
                    except ValueError:
                        commit_date = None

                # Extract author information
                author = latest_commit.get('author', {})
                repo["contact_name"] = author.get('user', {}).get('display_name')
                repo["contact_mail"] = author.get('raw', '').split('<')[-1].split('>')[0] if '<' in author.get('raw',
                                                                                                               '') else None

                # Get branch information
                branches_response = self.client.get(f'repositories/{workspace_slug}/{repo_slug}/refs/branches')
                branches = branches_response.get('values', [])

                # Find the branch this commit belongs to
                for branch in branches:
                    if branch.get('target', {}).get('hash') == latest_commit.get('hash'):
                        repo["latest_branch"] = branch.get('name')
                        break

        except Exception as e:
            if verbose:
                print(f"Error enriching repo [{repo['group_key']}/{repo['repo_key']}]: {str(e)}")

        return repo
