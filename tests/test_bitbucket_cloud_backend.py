import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, UTC

# Import the backend class
from _backend_bitbucket_cloud import BitbucketCloudBackend

# Mock data generator for Bitbucket Cloud
def mock_bitbucket_cloud_repo(repo_id=12345):
    """Generate a mock Bitbucket Cloud repository"""
    return {
        "type": "bitbucket_cloud",
        "id": repo_id,
        "name": "test-repo",
        "group": "Test Workspace",
        "group_key": "test-workspace",
        "repo_key": "test-repo",
        "ssh_link": f"git@bitbucket.org:test-workspace/test-repo-{repo_id}.git",
        "http_link": f"https://bitbucket.org/test-workspace/test-repo-{repo_id}.git",
        "contact_name": None,
        "contact_mail": None,
        "latest_branch": None,
        "default_branch": "main",
        "folder": None,
        "scanned": None,
        "secrets_found": None,
        "report_path": None,
    }

# Test fixture for the Bitbucket Cloud client
@pytest.fixture
def mock_bitbucket_cloud_client():
    """Create a mock Bitbucket Cloud client"""
    mock_client = MagicMock()
    
    # Mock workspace response
    mock_workspace = {
        "values": [
            {
                "slug": "test-workspace",
                "name": "Test Workspace",
                "uuid": "{12345678-1234-1234-1234-123456789012}"
            }
        ]
    }
    
    # Mock repository response
    mock_repos = {
        "values": [
            {
                "name": "test-repo",
                "uuid": "{98765432-9876-9876-9876-987654321098}",
                "slug": "test-repo",
                "type": "repository",
                "mainbranch": {
                    "name": "main"
                },
                "links": {
                    "clone": [
                        {
                            "name": "https",
                            "href": "https://bitbucket.org/test-workspace/test-repo.git"
                        },
                        {
                            "name": "ssh",
                            "href": "git@bitbucket.org:test-workspace/test-repo.git"
                        }
                    ]
                }
            }
        ]
    }
    
    # Mock commits response
    mock_commits = {
        "values": [
            {
                "hash": "abc123",
                "date": datetime.now(UTC).isoformat(),
                "author": {
                    "user": {
                        "display_name": "Test User"
                    },
                    "raw": "Test User <test@org>"
                }
            }
        ]
    }
    
    # Mock branches response
    mock_branches = {
        "values": [
            {
                "name": "main",
                "target": {
                    "hash": "abc123"
                }
            },
            {
                "name": "feature-branch",
                "target": {
                    "hash": "def456"
                }
            }
        ]
    }
    
    # Set up return values for different API paths
    mock_client.get.side_effect = lambda path, **kwargs: {
        'workspaces': mock_workspace,
        'repositories/test-workspace': mock_repos,
        'repositories/test-workspace/test-repo/commits': mock_commits,
        'repositories/test-workspace/test-repo/refs/branches': mock_branches
    }.get(path, {})
    
    return mock_client

# Bitbucket Cloud Backend Tests - Properly patch the atlassian.Bitbucket import
@patch('_backend_bitbucket_cloud.Bitbucket', autospec=True)
def test_bitbucket_cloud_backend_setup(mock_bitbucket_api, mock_bitbucket_cloud_client):
    """Test Bitbucket Cloud backend setup"""
    # Configure the mock to return our test client
    mock_bitbucket_api.return_value = mock_bitbucket_cloud_client
    
    # Create backend and setup
    backend = BitbucketCloudBackend()
    connection_input = {
        "token": "username:bitbucket_test_token",
        "base_url": "https://api.bitbucket.org/2.0"
    }
    
    # Test setup
    with patch('_backend_bitbucket_cloud.Bitbucket', mock_bitbucket_api):
        backend.setup(connection_input)
    
    assert backend.client is not None
    assert backend.endpoint_identifier == "https://api.bitbucket.org/2.0"
    assert backend.username == "username"
    assert backend.token == "bitbucket_test_token"
    
    # Verify Bitbucket constructor was called correctly
    mock_bitbucket_api.assert_called_once_with(
        url="https://api.bitbucket.org/2.0",
        username="username",
        password="bitbucket_test_token",
        cloud=True
    )
    
    # Test get_git_username_password
    username, password = backend.get_git_username_password()
    assert username == "username"
    assert password == "bitbucket_test_token"

@patch('_backend_bitbucket_cloud.Bitbucket', autospec=True)
def test_bitbucket_cloud_fetch_repos(mock_bitbucket_api, mock_bitbucket_cloud_client):
    """Test Bitbucket Cloud fetchAllRepos method"""
    mock_bitbucket_api.return_value = mock_bitbucket_cloud_client
    
    # Create backend and setup
    backend = BitbucketCloudBackend()
    backend.client = mock_bitbucket_cloud_client  # Set client directly
    backend.endpoint_identifier = "foobar"
    backend.username = "username"
    backend.token = "bitbucket_test_token"
    
    # Test fetchAllRepos
    repos = backend.fetchAllRepos(verbose=True)
    assert len(repos) == 1
    repo = list(repos.values())[0]
    assert repo["type"] == "bitbucket_cloud"
    assert repo["name"] == "test-repo"
    assert repo["group"] == "Test Workspace"
    assert repo["group_key"] == "test-workspace"
    assert repo["repo_key"] == "test-repo"
    assert repo["ssh_link"] == "git@bitbucket.org:test-workspace/test-repo.git"
    assert repo["http_link"] == "https://bitbucket.org/test-workspace/test-repo.git"
    assert repo["default_branch"] == "main"
    
    # Verify API calls
    mock_bitbucket_cloud_client.get.assert_any_call('workspaces')
    mock_bitbucket_cloud_client.get.assert_any_call('repositories/test-workspace')

@patch('_backend_bitbucket_cloud.Bitbucket', autospec=True)
def test_bitbucket_cloud_enrich_repo(mock_bitbucket_api, mock_bitbucket_cloud_client):
    """Test Bitbucket Cloud enrichRepo method"""
    mock_bitbucket_api.return_value = mock_bitbucket_cloud_client
    
    # Create backend and setup
    backend = BitbucketCloudBackend()
    backend.client = mock_bitbucket_cloud_client  # Set client directly
    backend.endpoint_identifier = "https://api.bitbucket.org/2.0"
    backend.username = "username"
    backend.token = "bitbucket_test_token"
    
    # Create test repo to enrich
    repo = mock_bitbucket_cloud_repo()
    
    # Test enrichRepo
    enriched_repo = backend.enrichRepo(repo, verbose=True)
    
    # Verify enrichment
    assert enriched_repo["contact_name"] == "Test User"
    assert enriched_repo["contact_mail"] == "test@org"
    assert enriched_repo["latest_branch"] == "main"
    
    # Verify API calls
    mock_bitbucket_cloud_client.get.assert_any_call(f'repositories/{repo["group_key"]}/{repo["repo_key"]}/commits')
    mock_bitbucket_cloud_client.get.assert_any_call(f'repositories/{repo["group_key"]}/{repo["repo_key"]}/refs/branches')

