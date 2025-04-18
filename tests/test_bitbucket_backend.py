import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

# Import the backend class
from _backend_bitbucket import BitbucketBackend

# Mock data generator for Bitbucket Server
def mock_bitbucket_repo(repo_id=12345):
    """Generate a mock Bitbucket Server repository"""
    return {
        "type": "bitbucket",
        "id": repo_id,
        "name": "test-repo",
        "group": "Test Project",
        "group_key": "TEST",
        "repo_key": "test-repo",
        "ssh_link": f"ssh://git@bitbucket.example.org:7999/test/test-repo-{repo_id}.git",
        "http_link": f"https://bitbucket.example.org/scm/test/test-repo-{repo_id}.git",
        "contact_name": None,
        "contact_mail": None,
        "latest_branch": None,
        "default_branch": "main",
        "folder": None,
        "scanned": None,
        "secrets_found": None,
        "report_path": None,
    }

# Test fixture for the Bitbucket Server client
@pytest.fixture
def mock_bitbucket_client():
    """Create a mock Bitbucket Server client"""
    mock_client = MagicMock()
    
    # Mock project
    mock_project = {
        "key": "TEST",
        "name": "Test Project",
        "type": "NORMAL"
    }
    
    # Mock repository
    mock_repo = {
        "id": 12345,
        "name": "test-repo",
        "slug": "test-repo",
        "state": "AVAILABLE",
        "archived": False,
        "defaultBranch": {
            "displayId": "main"
        },
        "links": {
            "clone": [
                {
                    "name": "http",
                    "href": "https://bitbucket.example.org/scm/test/test-repo.git"
                },
                {
                    "name": "ssh",
                    "href": "ssh://git@bitbucket.example.org:7999/test/test-repo.git"
                }
            ]
        }
    }
    
    # Mock branches data
    mock_branches = [
        {
            "displayId": "main",
            "isDefault": True,
            "latestCommit": "abc123",
            "metadata": {
                "com.atlassian.bitbucket.server.bitbucket-branch:latest-commit-metadata": {
                    "authorTimestamp": int(datetime.now(UTC).timestamp() * 1000),
                    "author": {
                        "displayName": "Test User",
                        "emailAddress": "test@example.com"
                    }
                }
            }
        },
        {
            "displayId": "feature-branch",
            "isDefault": False,
            "latestCommit": "def456",
            "metadata": {
                "com.atlassian.bitbucket.server.bitbucket-branch:latest-commit-metadata": {
                    "authorTimestamp": int((datetime.now(UTC)).timestamp() * 1000),
                    "author": {
                        "displayName": "Other User",
                        "emailAddress": "other@example.com"
                    }
                }
            }
        }
    ]
    
    # Set up return values
    # Create iterator-like objects instead of simple lists
    project_iterator = MagicMock()
    project_iterator.__iter__.return_value = [mock_project]

    repo_iterator = MagicMock()
    repo_iterator.__iter__.return_value = [mock_repo]

    # Set up return values to return iterators
    mock_client.project_list.return_value = project_iterator
    mock_client.repo_list.return_value = repo_iterator
    
    return mock_client

# Bitbucket Server Backend Tests - Properly patch the atlassian.Bitbucket import
@patch('_backend_bitbucket.Bitbucket', autospec=True)
def test_bitbucket_backend_setup(mock_bitbucket_api, mock_bitbucket_client):
    """Test Bitbucket Server backend setup"""
    # Configure the mock to return our test client
    mock_bitbucket_api.return_value = mock_bitbucket_client
    
    # Create backend and setup
    backend = BitbucketBackend()
    connection_input = {
        "token": "bitbucket_test_token",
        "base_url": "https://bitbucket.example.org"
    }
    
    # Test setup
    with patch('_backend_bitbucket.Bitbucket', mock_bitbucket_api):
        backend.setup(connection_input)
        
    assert backend.client is not None
    assert backend.endpoint_identifier == "https://bitbucket.example.org"
    
    # Verify Bitbucket constructor was called correctly
    mock_bitbucket_api.assert_called_once_with(
        url=connection_input["base_url"],
        token=connection_input["token"],
        cloud=False
    )
    
    # Test get_git_username_password
    username, password = backend.get_git_username_password()
    assert username == "x-token-auth"
    assert password == "bitbucket_test_token"

@patch('_backend_bitbucket.Bitbucket', autospec=True)
def test_bitbucket_fetch_repos(mock_bitbucket_api, mock_bitbucket_client):
    """Test Bitbucket Server fetchAllRepos method"""
    mock_bitbucket_api.return_value = mock_bitbucket_client
    
    # Create backend and setup
    backend = BitbucketBackend()
    backend.client = mock_bitbucket_client  # Set up the client directly
    backend.endpoint_identifier = "https://bitbucket.example.org"
    backend.connection_input = {
        "token": "bitbucket_test_token",
        "base_url": "https://bitbucket.example.org"
    }
    
    # Test fetchAllRepos
    repos = backend.fetchAllRepos(verbose=True)
    assert len(repos) == 1
    repo = list(repos.values())[0]
    assert repo["type"] == "bitbucket_dc"
    assert repo["name"] == "test-repo"
    assert repo["group"] == "Test Project"
    assert repo["group_key"] == "TEST"
    assert repo["repo_key"] == "test-repo"
    assert repo["ssh_link"] == "ssh://git@bitbucket.example.org:7999/test/test-repo.git"
    assert repo["default_branch"] == "main"
    
    # Verify API calls
    mock_bitbucket_client.project_list.assert_called_once()
    mock_bitbucket_client.repo_list.assert_called_once_with("TEST", limit=100)

@patch('_backend_bitbucket.Bitbucket', autospec=True)
def test_bitbucket_enrich_repo(mock_bitbucket_api, mock_bitbucket_client):
    """Test Bitbucket Server enrichRepo method"""
    mock_bitbucket_api.return_value = mock_bitbucket_client
    
    # Create backend and setup
    backend = BitbucketBackend()
    backend.client = mock_bitbucket_client  # Set up the client directly
    backend.endpoint_identifier = "https://bitbucket.example.org"
    backend.connection_input = {
        "token": "bitbucket_test_token",
        "base_url": "https://bitbucket.example.org"
    }
    
    # Create test repo to enrich
    repo = mock_bitbucket_repo()
    
    # Test enrichRepo
    enriched_repo = backend.enrichRepo(repo, verbose=True)
    
    # Verify enrichment TODO
    # assert enriched_repo["contact_name"] == "Test User"
    # assert enriched_repo["contact_mail"] == "test@example.com"
    # assert enriched_repo["latest_branch"] == "main"
    # assert enriched_repo["default_branch"] == "main"
    
    # Verify API call
    mock_bitbucket_client.get_branches.assert_called_once_with(
        project_key=repo["group_key"], 
        repository_slug=repo["repo_key"], 
        limit=100
    )
