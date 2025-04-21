from datetime import datetime, UTC
from typing import Dict, Any, Tuple
from atlassian import Bitbucket
from data_types import Repo, ConnectionInput, VcsBackend
from progress.bar import Bar


class BitbucketBackend(VcsBackend):
    client: Any = None
    endpoint_identifier = ""
    connection_input = None

    @staticmethod
    def name() -> str:
        return "bitbucket_dc"

    @staticmethod
    def shortname() -> str:
        return "bb"

    def get_git_username_password(self) -> Tuple[str, str]:
        return "x-token-auth", self.connection_input['token']

    def setup(self, connection_input: ConnectionInput) -> None:
        self.connection_input = connection_input
        self.endpoint_identifier = connection_input["base_url"]
        print(f"({self.name()}) Connecting to {self.endpoint_identifier}")

        try:
            self.client = Bitbucket(
                url=connection_input["base_url"],
                token=connection_input["token"],
                cloud=False)
            project_gen = self.client.project_list(limit=1)
            first_project = next(project_gen, None)
            if first_project is None:
                raise Exception(
                    "No projects found. Check your token and permissions.")
        except Exception as e:
            raise Exception(
                "Failed to setup Bitbucket connection. Check your token and URL.") from e
        return self

    def fetchAllRepos(self, progress: bool = False,
                      verbose: bool = False) -> Dict[int, Repo]:
        print(f"({self.name()}) Fetching repo data from {self.endpoint_identifier}")
        if self.client is None:
            raise Exception(
                "Bitbucket client is not set up. Call setup() first.")
        try:
            projects = []
            for proj in self.client.project_list(limit=100):
                projects.append(proj)
        except Exception as e:
            raise Exception("Failed to fetch projects from Bitbucket.") from e

        repos: Dict[int, Repo] = {}
        bar = Bar(
            'Fetching repo data for projects',
            max=len(projects)) if progress else None

        for project in projects:
            if project["type"] == "NORMAL":
                project_key = project.get("key")
                if verbose:
                    print(f"Fetching repo data for project [{project_key}]")
                try:
                    project_repos = []
                    for repo_item in self.client.repo_list(
                            project_key, limit=100):
                        project_repos.append(repo_item)
                except Exception as e:
                    raise Exception(
                        f"Failed to fetch repositories for project {project_key}.") from e
                for repo_item in project_repos:
                    if not repo_item["archived"] and repo_item["state"] == "AVAILABLE":

                        clone_link = None
                        for link in repo_item["links"]["clone"]:
                            if link["name"] == "ssh":
                                clone_link = link["href"]

                        repo_obj: Repo = {
                            "type": self.name(),
                            "id": repo_item.get("id"),
                            "name": repo_item.get("name"),
                            "group": project.get("name"),
                            "group_key": project_key,
                            "repo_key": repo_item.get("slug"),
                            "ssh_link": clone_link,
                            "contact_name": None,
                            "contact_mail": None,
                            "latest_branch": None,
                            "default_branch": repo_item.get("defaultBranch", {}).get("displayId") if repo_item.get("defaultBranch") else None,
                            "folder": None,
                            "scanned": None,
                            "secrets_found": None,
                            "report_path": None,
                        }
                        repo_id = repo_obj["id"]
                        repos[repo_id] = repo_obj
            if progress:
                bar.next()
        if progress:
            bar.finish()
        if not repos:
            raise Exception(
                "No repositories found. Check your token and permissions.")
        return repos

    def enrichRepo(self, repo: Repo, verbose: bool = False) -> Repo:
        client = self.client
        try:
            latest_commit_date = None
            contact_name = None
            contact_mail = None
            latest_branch = None
            default_branch = None
            for branch in client.get_branches(
                    project_key=repo["group_key"], repository_slug=repo["repo_key"], limit=100):
                if "latestCommit" in branch and branch['latestCommit']:
                    commit_date = datetime.fromtimestamp(
                        branch['metadata']['com.atlassian.bitbucket.server.bitbucket-branch:latest-commit-metadata']['authorTimestamp'] /
                        1000,
                        UTC)
                    if latest_commit_date is None or commit_date > latest_commit_date:
                        latest_commit_date = commit_date
                        latest_branch = branch['displayId']

                        # Author from last commit
                        if "displayName" in branch['metadata'][
                                'com.atlassian.bitbucket.server.bitbucket-branch:latest-commit-metadata']['author']:
                            contact_name = branch['metadata']['com.atlassian.bitbucket.server.bitbucket-branch:latest-commit-metadata']['author']['displayName']
                        if "emailAddress" in branch['metadata'][
                                'com.atlassian.bitbucket.server.bitbucket-branch:latest-commit-metadata']['author']:
                            contact_mail = branch['metadata']['com.atlassian.bitbucket.server.bitbucket-branch:latest-commit-metadata']['author']['emailAddress']

                if branch['isDefault']:
                    default_branch = branch['displayId']
        except Exception:
            if verbose:
                print(f"Error fetching branch info for repo [{repo["group_key"]}/{repo["repo_key"]}]")

        repo["contact_mail"] = contact_mail
        repo["contact_name"] = contact_name
        repo["default_branch"] = default_branch
        repo["latest_branch"] = latest_branch
        return repo
