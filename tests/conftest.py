import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Import test fixtures from individual test files
from .test_github_backend import mock_github_client
from .test_gitlab_backend import mock_gitlab_client
from .test_bitbucket_backend import mock_bitbucket_client
from .test_bitbucket_cloud_backend import mock_bitbucket_cloud_client

# Import mock data generators
from .test_github_backend import mock_github_repo
from .test_gitlab_backend import mock_gitlab_repo
from .test_bitbucket_backend import mock_bitbucket_repo
from .test_bitbucket_cloud_backend import mock_bitbucket_cloud_repo

@pytest.fixture
def temp_git_dir():
    """Create a temporary directory for Git operations"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Clean up
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_repo_folder(temp_git_dir):
    """Create a sample repository folder structure"""
    # Create a directory structure for a mock Git repository
    repo_path = os.path.join(temp_git_dir, "sample-repo")
    os.makedirs(repo_path, exist_ok=True)
    os.makedirs(os.path.join(repo_path, ".git"), exist_ok=True)
    
    # Create a sample file
    with open(os.path.join(repo_path, "README.md"), "w") as f:
        f.write("# Sample Repository\n\nThis is a sample repository for testing.")
    
    return repo_path

@pytest.fixture
def github_connection_input():
    """Create a sample GitHub connection input"""
    return {
        "token": "github_test_token",
        "base_url": "https://api.github.com"
    }

@pytest.fixture
def gitlab_connection_input():
    """Create a sample GitLab connection input"""
    return {
        "token": "gitlab_test_token",
        "base_url": "https://gitlab.com"
    }

@pytest.fixture
def bitbucket_connection_input():
    """Create a sample Bitbucket Server connection input"""
    return {
        "token": "bitbucket_test_token",
        "base_url": "https://bitbucket.example.org"
    }

@pytest.fixture
def bitbucket_cloud_connection_input():
    """Create a sample Bitbucket Cloud connection input"""
    return {
        "token": "username:bitbucket_test_token",
        "base_url": "https://api.bitbucket.example.com/2.0"
    }

@pytest.fixture
def mock_askpass_script():
    """Mock the creation and usage of a Git askpass script"""
    with patch('tempfile.mkstemp') as mock_mkstemp, \
         patch('os.fdopen') as mock_fdopen, \
         patch('os.chmod') as mock_chmod, \
         patch('os.unlink') as mock_unlink:
        
        mock_mkstemp.return_value = (5, "/tmp/git-askpass-script")
        
        yield "/tmp/git-askpass-script"

@pytest.fixture
def create_repo_with_http_link():
    """
    Create a mock repository of the specified type with both SSH and HTTP links
    
    Returns:
        A function that creates repositories of different types
    """
    def _create_repo(backend_type: str, repo_id: int = 12345):
        if backend_type == "github":
            return mock_github_repo(repo_id)
        elif backend_type == "gitlab":
            return mock_gitlab_repo(repo_id)
        elif backend_type == "bitbucket":
            return mock_bitbucket_repo(repo_id)
        elif backend_type == "bitbucket_cloud":
            return mock_bitbucket_cloud_repo(repo_id)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")
    
    return _create_repo

# Mock external library imports for all tests
@pytest.fixture(autouse=True)
def mock_external_libs():
    """Mock all external library imports to prevent any real network connections"""
    with patch('github.Github', autospec=True), \
         patch('gitlab.Gitlab', autospec=True), \
         patch('atlassian.Bitbucket', autospec=True):
        yield
