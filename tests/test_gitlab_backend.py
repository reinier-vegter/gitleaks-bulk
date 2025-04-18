import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC, timedelta

# Import the backend class
from _backend_gitlab import GitlabBackend

# Mock data generator for GitLab
def mock_gitlab_repo(repo_id=12345):
    """Generate a mock GitLab repository"""
    return {
        "type": "gitlab",
        "repo_key": repo_id,
        "id": repo_id,
        "group": "test-group/test-project",
        "name": "test-repo",
        "ssh_link": f"git@gitlab.example.com:test-group/test-project/test-repo-{repo_id}.git",
        "http_link": f"https://gitlab.example.com/test-group/test-project/test-repo-{repo_id}.git",
        "default_branch": "main",
        "contact_name": None,
        "contact_mail": None,
        "latest_branch": None,
        "folder": None,
        "scanned": None,
        "secrets_found": None,
        "report_path": None,
    }

# Test fixture for the GitLab client
@pytest.fixture
def mock_gitlab_client():
    """Create a mock GitLab client"""
    mock_client = MagicMock()
    
    # Mock project
    mock_project = MagicMock()
    mock_project.id = 12345
    mock_project.name = "test-repo"
    mock_project.archived = False
    mock_project.empty_repo = False
    mock_project.namespace = {
        'kind': 'group',
        'full_path': 'test-group/test-project'
    }
    mock_project.ssh_url_to_repo = "git@gitlab.example.com:test-group/test-project/test-repo.git"
    mock_project.http_url_to_repo = "https://gitlab.example.com/test-group/test-project/test-repo.git"
    mock_project.default_branch = "main"
    
    # Mock project iterator
    mock_projects = MagicMock()
    mock_projects.total = 1
    mock_projects.__iter__.return_value = [mock_project]
    
    # Set up return values
    mock_client.projects.list.return_value = mock_projects
    
    # Mock branches
    mock_branches = [
        {
            "name": "main",
            "commit": {
                "author_name": "Test User",
                "author_email": "test@example.com",
                "committed_date": (datetime.now(UTC)).isoformat()
            }
        },
        {
            "name": "feature-branch",
            "commit": {
                "author_name": "Other User",
                "author_email": "other@example.com",
                "committed_date": (datetime.now(UTC) + timedelta(seconds=-3)).isoformat()
            }
        }
    ]
    
    # Mock HTTP get method
    mock_client.http_get.return_value = mock_branches
    
    # Add auth method to verify connection
    mock_client.auth = MagicMock()
    
    return mock_client

# GitLab Backend Tests - Properly patch the gitlab.Gitlab import
@patch('_backend_gitlab.gitlab.Gitlab')
def test_gitlab_backend_setup(mock_gitlab_api, mock_gitlab_client):
    """Test GitLab backend setup"""
    mock_gitlab_api.return_value = mock_gitlab_client
    
    # Create backend and setup
    backend = GitlabBackend()
    connection_input = {
        "token": "gitlab_test_token",
        "base_url": "https://gitlab.example.com"
    }
    
    # Test setup
    backend.setup(connection_input)
    assert backend.client is not None
    assert backend.endpoint_identifier == "https://gitlab.example.com"
    
    # Verify GitLab constructor was called correctly
    mock_gitlab_api.assert_called_once_with(
        connection_input["base_url"],
        private_token=connection_input["token"]
    )
    
    # Verify auth was called
    mock_gitlab_client.auth.assert_called_once()
    
    # Test get_git_username_password
    username, password = backend.get_git_username_password()
    assert username == "oauth2"
    assert password == "gitlab_test_token"

@patch('_backend_gitlab.gitlab.Gitlab')
def test_gitlab_fetch_repos(mock_gitlab_api, mock_gitlab_client):
    """Test GitLab fetchAllRepos method"""
    mock_gitlab_api.return_value = mock_gitlab_client
    
    # Create backend and setup
    backend = GitlabBackend()
    connection_input = {
        "token": "gitlab_test_token",
        "base_url": "https://gitlab.example.com"
    }
    backend.setup(connection_input)
    
    # Test fetchAllRepos
    repos = backend.fetchAllRepos(verbose=True)
    assert len(repos) == 1
    repo = list(repos.values())[0]
    assert repo["type"] == "gitlab"
    assert repo["name"] == "test-repo"
    assert repo["group"] == "test-group/test-project"
    assert repo["ssh_link"] == "git@gitlab.example.com:test-group/test-project/test-repo.git"
    assert repo["http_link"] == "https://gitlab.example.com/test-group/test-project/test-repo.git"
    assert repo["default_branch"] == "main"

@patch('_backend_gitlab.gitlab.Gitlab')
def test_gitlab_enrich_repo(mock_gitlab_api, mock_gitlab_client):
    """Test GitLab enrichRepo method"""
    mock_gitlab_api.return_value = mock_gitlab_client
    
    # Create backend and setup
    backend = GitlabBackend()
    connection_input = {
        "token": "gitlab_test_token",
        "base_url": "https://gitlab.example.com"
    }
    backend.setup(connection_input)
    
    # Create test repo to enrich
    repo = mock_gitlab_repo()
    
    # Test enrichRepo
    enriched_repo = backend.enrichRepo(repo, verbose=True)
    
    # Verify enrichment
    assert enriched_repo["contact_name"] == "Test User"
    assert enriched_repo["contact_mail"] == "test@example.com"
    assert enriched_repo["latest_branch"] == "main"
    
    # Verify API call
    mock_gitlab_client.http_get.assert_called_once_with(f'/projects/{repo["repo_key"]}/repository/branches')
