import pytest
from unittest.mock import Mock, patch, MagicMock

# Import the backend classes
from _backend_github import GithubBackend
from _backend_gitlab import GitlabBackend
from _backend_bitbucket import BitbucketBackend
from _backend_bitbucket_cloud import BitbucketCloudBackend

def test_git_username_password():
    """Test git username/password generation for different backends"""
    # GitHub
    github_backend = GithubBackend()
    github_backend.connection_input = {"token": "github_token"}
    gh_username, gh_password = github_backend.get_git_username_password()
    assert gh_username == "x-access-token"
    assert gh_password == "github_token"
    
    # GitLab
    gitlab_backend = GitlabBackend()
    gitlab_backend.connection_input = {"token": "gitlab_token"}
    gl_username, gl_password = gitlab_backend.get_git_username_password()
    assert gl_username == "oauth2"
    assert gl_password == "gitlab_token"
    
    # Bitbucket Server
    bitbucket_backend = BitbucketBackend()
    bitbucket_backend.connection_input = {"token": "bitbucket_token"}
    bb_username, bb_password = bitbucket_backend.get_git_username_password()
    assert bb_username == "x-token-auth"
    assert bb_password == "bitbucket_token"
    
    # Bitbucket Cloud
    bitbucket_cloud_backend = BitbucketCloudBackend()
    bitbucket_cloud_backend.username = "bb_username"
    bitbucket_cloud_backend.token = "bb_cloud_token"
    bc_username, bc_password = bitbucket_cloud_backend.get_git_username_password()
    assert bc_username == "bb_username"
    assert bc_password == "bb_cloud_token"
