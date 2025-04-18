import pytest
from typing import Dict, Any

# Import mock data generators from individual test files
from .test_github_backend import mock_github_repo
from .test_gitlab_backend import mock_gitlab_repo
from .test_bitbucket_backend import mock_bitbucket_repo
from .test_bitbucket_cloud_backend import mock_bitbucket_cloud_repo

def test_mock_data_generators():
    """Test all mock data generators"""
    
    # Test GitHub mock data
    github_repo = mock_github_repo(repo_id=54321)
    assert github_repo["type"] == "github"
    assert github_repo["id"] == 54321
    assert github_repo["http_link"] == "https://github.example.com/test-org/test-repo-54321.git"
    
    # Test GitLab mock data
    gitlab_repo = mock_gitlab_repo(repo_id=54321)
    assert gitlab_repo["type"] == "gitlab"
    assert gitlab_repo["id"] == 54321
    assert gitlab_repo["http_link"] == "https://gitlab.example.com/test-group/test-project/test-repo-54321.git"
    
    # Test Bitbucket Server mock data
    bitbucket_repo = mock_bitbucket_repo(repo_id=54321)
    assert bitbucket_repo["type"] == "bitbucket"
    assert bitbucket_repo["id"] == 54321
    assert bitbucket_repo["http_link"] == "https://bitbucket.example.org/scm/test/test-repo-54321.git"
    
    # Test Bitbucket Cloud mock data
    bitbucket_cloud_repo = mock_bitbucket_cloud_repo(repo_id=54321)
    assert bitbucket_cloud_repo["type"] == "bitbucket_cloud"
    assert bitbucket_cloud_repo["id"] == 54321
    assert bitbucket_cloud_repo["http_link"] == "https://bitbucket.org/test-workspace/test-repo-54321.git"

def create_repo_with_http_link(backend_type: str, repo_id: int = 12345) -> Dict[str, Any]:
    """
    Create a mock repository of the specified type with both SSH and HTTP links
    
    Args:
        backend_type: One of 'github', 'gitlab', 'bitbucket', or 'bitbucket_cloud'
        repo_id: Optional repo ID to use
        
    Returns:
        A mock repository dictionary
    """
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

def test_create_repo_with_http_link():
    """Test the create_repo_with_http_link helper function"""
    
    # Test creating repos of different types
    github_repo = create_repo_with_http_link("github")
    assert github_repo["type"] == "github"
    assert "ssh_link" in github_repo
    assert "http_link" in github_repo
    
    gitlab_repo = create_repo_with_http_link("gitlab")
    assert gitlab_repo["type"] == "gitlab"
    assert "ssh_link" in gitlab_repo
    assert "http_link" in gitlab_repo
    
    bitbucket_repo = create_repo_with_http_link("bitbucket")
    assert bitbucket_repo["type"] == "bitbucket"
    assert "ssh_link" in bitbucket_repo
    assert "http_link" in bitbucket_repo
    
    bitbucket_cloud_repo = create_repo_with_http_link("bitbucket_cloud")
    assert bitbucket_cloud_repo["type"] == "bitbucket_cloud"
    assert "ssh_link" in bitbucket_cloud_repo
    assert "http_link" in bitbucket_cloud_repo
    
    # Test with invalid type
    with pytest.raises(ValueError):
        create_repo_with_http_link("invalid_type")
