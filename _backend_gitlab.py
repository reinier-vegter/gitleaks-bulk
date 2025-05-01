from datetime import datetime
from urllib.parse import urlparse

import gitlab
from typing import Dict, Tuple
from data_types import Repo, ConnectionInput, VcsBackend
from progress.bar import Bar


class GitlabBackend(VcsBackend):
    client: gitlab.Gitlab | None = None
    endpoint_identifier = ""
    connection_input = None

    @staticmethod
    def name() -> str:
        return "gitlab"

    @staticmethod
    def shortname() -> str:
        return "gl"

    def get_git_username_password(self) -> Tuple[str, str]:
        return "oauth2", self.connection_input['token']

    def setup(self, connection_input: ConnectionInput) -> None:
        self.endpoint_identifier = connection_input["base_url"]
        self.connection_input = connection_input
        print(f"({self.name()}) Connecting to {self.endpoint_identifier}")
        try:
            # Set up the GitLab connection
            self.client = gitlab.Gitlab(
                connection_input["base_url"],
                private_token=connection_input["token"])
            # Test the connection
            self.client.auth()
            print(
                f"Successfully connected to GitLab at {self.endpoint_identifier}")
        except gitlab.exceptions.GitlabAuthenticationError:
            raise Exception(
                f"Authentication failed at {connection_input['base_url']}. Please check your token.")
        except gitlab.exceptions.GitlabError as e:
            raise Exception(f"GitLab API error: {e}")
        return self

    def fetchAllRepos(self, progress: bool = False,
                      verbose: bool = False) -> Dict[int, Repo]:
        print(f"({self.name()}) Fetching repo data from {self.endpoint_identifier}")
        if self.client is None:
            raise Exception(
                "GitLab connection is not set up. Call setup() first.")

        repos: Dict[int, Repo] = {}
        projects = self.client.projects.list(iterator=True, per_page=100)
        if not projects.total:
            print("Did not get data from API, you probably have no valid session.")
            exit(1)

        bar = Bar(
            'Fetching repo data for projects',
            max=projects.total) if progress else None
        for project in projects:
            if project.archived is False and project.empty_repo is False and project.namespace[
                    'kind'] != 'user':
                repos[project.id] = Repo(
                    type=self.name(),
                    repo_key=project.id,
                    id=project.id,
                    group=project.namespace['full_path'],
                    name=project.name,
                    ssh_link=project.ssh_url_to_repo,
                    http_link=project.http_url_to_repo,
                    default_branch=(project.default_branch if hasattr(project, 'default_branch') else None))
            if bar:
                bar.next()
        if bar:
            bar.finish()

        return repos

    def enrichRepo(self, repo: Repo, verbose: bool = False) -> Repo:
        latest_commit_date = None
        contact_name = None
        contact_mail = None
        latest_branch = None

        branches = self.client.http_get(
            f'/projects/{repo["repo_key"]}/repository/branches')
        for branch in branches:
            try:
                # Get the last commit of the branch
                commit = branch['commit']
                commit_date = datetime.fromisoformat(commit['committed_date'])

                # Compare dates
                if latest_commit_date is None or commit_date > latest_commit_date:
                    latest_commit_date = commit_date
                    latest_branch = branch["name"]
                    contact_name = commit["author_name"]
                    contact_mail = commit["author_email"]

            except gitlab.exceptions.GitlabGetError:
                if verbose:
                    print(f"Error fetching commit for branch {branch["name"]}")

        repo["contact_mail"] = contact_mail
        repo["contact_name"] = contact_name
        repo["latest_branch"] = latest_branch
        return repo
