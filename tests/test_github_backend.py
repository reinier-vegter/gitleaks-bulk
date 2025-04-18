import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

# Import the backend class
from _backend_github import GithubBackend

# Mock data generator for GitHub
def mock_github_repo(repo_id=12345):
    """Generate a mock GitHub repository"""
    return {
        "type": "github",
        "repo_key": repo_id,
        "id": repo_id,
        "group": "test-org",
        "name": "test-repo",
        "ssh_link": f"git@github.example.com:test-org/test-repo-{repo_id}.git",
        "http_link": f"https://github.example.com/test-org/test-repo-{repo_id}.git",
        "default_branch": "main",
        "contact_name": None,
        "contact_mail": None,
        "latest_branch": None,
        "folder": None,
        "scanned": None,
        "secrets_found": None,
        "report_path": None,
    }

# Test fixture for the GitHub client
@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client"""
    mock_client = MagicMock()
    
    # Mock organization
    mock_org = MagicMock()
    mock_org.login = "test-org"
    
    # Mock user
    mock_user = MagicMock()
    mock_user.login = "test-user"
    mock_user.get_orgs.return_value = [mock_org]
    
    # Mock repository
    mock_repository = MagicMock()
    mock_repository.id = 12345
    mock_repository.name = "test-repo"
    mock_repository.fork = False
    mock_repository.archived = False
    mock_repository.organization = mock_org
    mock_repository.ssh_url = "git@github.example.com:test-org/test-repo.git"
    mock_repository.clone_url = "https://github.example.com/test-org/test-repo.git"
    mock_repository.default_branch = "main"
    
    # Set up return values
    mock_client.get_user.return_value = mock_user
    mock_user.get_repos.return_value = [mock_repository]
    mock_org.get_repos.return_value = []
    
    return mock_client

# GitHub Backend Tests - properly patch both module imports
@patch('_backend_github.github')
@patch('_backend_github.Github')
def test_github_backend_setup(mock_github_class, mock_github_module, mock_github_client):
    """Test GitHub backend setup"""
    # Set up the mocks
    mock_github_class.return_value = mock_github_client
    
    # Need to mock the GithubException for error handling
    mock_exception = MagicMock()
    mock_github_module.GithubException = mock_exception
    
    # Create backend and setup
    backend = GithubBackend()
    connection_input = {
        "token": "github_test_token",
        "base_url": "https://api.github.example.com"
    }
    
    # Test setup
    backend.setup(connection_input)
    assert backend.client is not None
    assert backend.endpoint_identifier == "https://api.github.example.com"
    
    # Verify the Github constructor was called correctly
    if "base_url" in connection_input and connection_input["base_url"]:
        mock_github_class.assert_called_once_with(
            base_url=connection_input["base_url"],
            login_or_token=connection_input["token"]
        )
    else:
        mock_github_class.assert_called_once_with(connection_input["token"])
    
    # Test get_git_username_password
    username, password = backend.get_git_username_password()
    assert username == "x-access-token"
    assert password == "github_test_token"

@patch('_backend_github.github')
@patch('_backend_github.Github')
def test_github_fetch_repos(mock_github_class, mock_github_module, mock_github_client):
    """Test GitHub fetchAllRepos method"""
    # Set up the mocks
    mock_github_class.return_value = mock_github_client
    
    # Create backend and setup
    backend = GithubBackend()
    connection_input = {
        "token": "github_test_token",
        "base_url": "https://api.github.example.com"
    }
    backend.client = mock_github_client  # Set client directly to avoid setup()
    backend.connection_input = connection_input
    backend.endpoint_identifier = connection_input["base_url"]
    
    # Test fetchAllRepos
    repos = backend.fetchAllRepos(verbose=True)
    assert len(repos) == 1
    repo = list(repos.values())[0]
    assert repo["type"] == "github"
    assert repo["name"] == "test-repo"
    assert repo["group"] == "test-org"
    assert repo["ssh_link"] == "git@github.example.com:test-org/test-repo.git"
    assert repo["http_link"] == "https://github.example.com/test-org/test-repo.git"
    assert repo["default_branch"] == "main"

@patch('_backend_github.github')
@patch('_backend_github.Github')
def test_github_enrich_repo(mock_github_class, mock_github_module, mock_github_client):
    """Test GitHub enrichRepo method"""
    # Set up the mocks
    mock_github_class.return_value = mock_github_client
    
    # Mock GithubException
    mock_exception = MagicMock()
    mock_github_module.GithubException = mock_exception
    
    # Mock repository for enrichment
    mock_gh_repo = MagicMock()
    mock_branch = MagicMock()
    mock_branch.name = "feature-branch"
    mock_branch.commit.sha = "abc123"
    
    mock_commit = MagicMock()
    mock_commit.commit.author.date = datetime.now(UTC)
    mock_commit.commit.author.name = "Test User"
    mock_commit.commit.author.email = "test@example.com"
    
    # Set up return values
    mock_github_client.get_repo.return_value = mock_gh_repo
    mock_gh_repo.get_branches.return_value = [mock_branch]
    mock_gh_repo.get_commit.return_value = mock_commit
    
    # Create backend and setup
    backend = GithubBackend()
    connection_input = {
        "token": "github_test_token",
        "base_url": "https://api.github.example.com"
    }
    backend.client = mock_github_client  # Set client directly to avoid setup()
    backend.connection_input = connection_input
    backend.endpoint_identifier = connection_input["base_url"]
    
    # Create test repo to enrich
    repo = mock_github_repo()
    
    # Test enrichRepo
    enriched_repo = backend.enrichRepo(repo, verbose=True)
    
    # Verify enrichment
    assert enriched_repo["contact_name"] == "Test User"
    assert enriched_repo["contact_mail"] == "test@example.com"
    assert enriched_repo["latest_branch"] == "feature-branch"
