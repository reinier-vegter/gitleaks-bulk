from urllib.parse import urlparse
import github
from github import Github
from typing import Dict, Tuple
from data_types import Repo, ConnectionInput, VcsBackend
from progress.bar import Bar


class GithubBackend(VcsBackend):
    client: Github | None = None
    endpoint_identifier = ""
    connection_input = None

    @staticmethod
    def name() -> str:
        return "github"

    @staticmethod
    def shortname() -> str:
        return "gh"

    def get_git_username_password(self) -> tuple[str, str]:
        return "x-access-token", self.connection_input['token']

    def setup(self, connection_input: ConnectionInput) -> None:
        self.connection_input = connection_input
        self.endpoint_identifier = connection_input.get(
            "base_url", "https://api.github.com")
        print(f"({self.name()}) Connecting to {self.endpoint_identifier}")
        try:
            # Set up the GitHub connection
            if "base_url" in connection_input and connection_input["base_url"]:
                # GitHub Enterprise
                self.client = Github(
                    base_url=connection_input["base_url"],
                    login_or_token=connection_input["token"]
                )
            else:
                # GitHub.com
                self.client = Github(connection_input["token"])

            # Test the connection
            self.client.get_user().login
            print(
                f"Successfully connected to GitHub at {self.endpoint_identifier}")
        except github.GithubException as e:
            if e.status == 401:
                raise Exception(
                    f"Authentication failed at {self.endpoint_identifier}. Please check your token.")
            else:
                raise Exception(f"GitHub API error: {e}")
        except Exception as e:
            raise Exception(f"Connection error: {e}")
        return self

    def fetchAllRepos(self, progress: bool = False,
                      verbose: bool = False) -> dict[int, Repo]:
        print(f"({self.name()}) Fetching repo data from {self.endpoint_identifier}")
        if self.client is None:
            raise Exception(
                "GitHub connection is not set up. Call setup() first.")

        repos: dict[int, Repo] = {}

        # Get the authenticated user
        user = self.client.get_user()

        # Fetch all repositories the user has access to
        all_repos = []

        # Get user's own repositories
        user_repos = user.get_repos()
        all_repos.extend(user_repos)

        # Get organization repositories the user is a member of
        for org in user.get_orgs():
            org_repos = org.get_repos()
            all_repos.extend(org_repos)

        total_repos = len(all_repos)

        if total_repos == 0:
            print(
                "Did not get data from API, you probably have no valid session or no repositories.")
            exit(1)

        bar = Bar('Fetching repo data for repositories',
                  max=total_repos) if progress else None

        for repo in all_repos:
            # Check if the repo is owned by the user or their organization
            # Skip forks and archived repositories
            if not repo.fork and not repo.archived:
                repo_id = repo.id
                repos[repo_id] = Repo(
                    type=self.name(),
                    repo_key=repo_id,
                    id=repo_id,
                    group=repo.organization.login if repo.organization else user.login,
                    name=repo.name,
                    ssh_link=repo.ssh_url,
                    http_link=repo.clone_url,
                    default_branch=(repo.default_branch if hasattr(repo, 'default_branch') else None)
                )
            if bar:
                bar.next()
        if bar:
            bar.finish()

        return repos

    def enrichRepo(self, repo: Repo, verbose: bool = False) -> Repo:
        if self.client is None:
            raise Exception(
                "GitHub connection is not set up. Call setup() first.")

        latest_commit_date = None
        contact_name = None
        contact_mail = None
        latest_branch = None

        try:
            # Get the repository object
            github_repo = self.client.get_repo(repo["id"])

            # Get all branches
            branches = github_repo.get_branches()

            for branch in branches:
                try:
                    # Get the last commit of the branch
                    commit = github_repo.get_commit(branch.commit.sha)
                    commit_date = commit.commit.author.date

                    # Compare dates
                    if latest_commit_date is None or commit_date > latest_commit_date:
                        latest_commit_date = commit_date
                        latest_branch = branch.name

                        # Get author info - GitHub API doesn't always expose email in the same way
                        # as GitLab, so we need to be a bit more careful
                        author = commit.commit.author
                        contact_name = author.name
                        contact_mail = author.email if author.email else None

                except github.GithubException:
                    if verbose:
                        print(
                            f"Error fetching commit for branch {branch.name}")

        except github.GithubException as e:
            if verbose:
                print(f"Error enriching repository data: {e}")

        repo["contact_mail"] = contact_mail
        repo["contact_name"] = contact_name
        repo["latest_branch"] = latest_branch
        return repo
