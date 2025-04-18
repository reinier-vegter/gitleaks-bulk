import os
import requests
from github import Github

# --- Configuration ---
owner = os.environ.get("GITHUB_REPOSITORY_OWNER")
repo_name = os.environ.get("GITHUB_REPOSITORY").split('/')[-1] # Get the repository name
github_token = os.environ.get("GITHUB_TOKEN") # Get token from environment
workflow_name = os.environ.get("GITHUB_WORKFLOW_NAME") # Specify the workflow name to filter, or leave empty
# -- Or set it manually --
# owner = "your_github_username_or_org"  # Replace
# repo_name = "your_repo_name"         # Replace
# workflow_name = "my-workflow.yml"  # Replace, leave empty to process all workflows.

# You must use the GITHUB_TOKEN, or set the GITHUB_TOKEN from the environment
# g = Github(os.environ.get("GITHUB_TOKEN"))  # Get token from environment
g = Github(github_token)
repo = g.get_repo(f"{owner}/{repo_name}")

def delete_workflow_runs(repo, workflow_name=None):

    """Deletes workflow runs.

    Args:
        repo: The repository object.
        workflow_name: Optional, workflow file name to filter.
    """

    url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs"
    params = {"status": "completed", "per_page": 100}  # Adjust per_page as needed

    if workflow_name:
        params['workflow_id'] = workflow_name

    while True:
        try:
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
                "X-GitHub-Api-Version": "2022-11-28"
            }
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for bad status codes
            data = response.json()

            runs = data["workflow_runs"]
            print(f"Found {len(runs)} completed runs (page)")

            for run in runs:
                run_id = run["id"]
                print(f"Deleting run ID: {run_id}...")
                delete_url = f"https://api.github.com/repos/{owner}/{repo_name}/actions/runs/{run_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                if delete_response.status_code == 204:  # No Content - Success
                    print(f"Successfully deleted run ID: {run_id}")
                else:
                    print(f"Error deleting run ID {run_id}: {delete_response.status_code} - {delete_response.text}")
            # Check for pagination
            if "next" in response.links:
                url = response.links["next"]["url"]
                print(f"Fetching next page: {url}")
            else:
                print("No more pages of runs.")
                break
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            break  # Stop on any API error

    print("Finished deleting workflow runs.")


if __name__ == "__main__":
    if not owner or not repo_name or not github_token:
        print("Error: Please set GITHUB_REPOSITORY_OWNER, GITHUB_REPOSITORY and GITHUB_TOKEN as environment variables.")
        exit(1)

    delete_workflow_runs(repo, workflow_name)