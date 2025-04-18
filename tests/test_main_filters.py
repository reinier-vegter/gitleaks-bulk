import pytest
import re
from unittest.mock import patch, MagicMock, mock_open
import sys

# Import main functions for testing
# Use patch to avoid importing dependencies before mocking
with patch.dict(sys.modules, {
    'git': MagicMock(),
    'InquirerPy': MagicMock(),
    'progress.bar': MagicMock(),
    'dotenv': MagicMock(),
    'atlassian': MagicMock(),
    'github': MagicMock(),
    'gitlab': MagicMock()
}):
    from main import checkRepoInFilterSet
    import main

# Fixtures for testing filter operations
@pytest.fixture
def sample_repo():
    """Create a sample repository for testing filters"""
    return {
        "type": "github",
        "id": 12345,
        "name": "test-repo",
        "group": "test-org",
        "repo_key": "test-repo-key",
        "group_key": "test-org",
        "http_link": "https://github.example.com/test-org/test-repo.git",
        "ssh_link": "git@github.example.com:test-org/test-repo.git",
        "default_branch": "main",
        "latest_branch": "feature-branch",
        "folder": "/tmp/repos/github/test-org/test-repo"
    }

@pytest.fixture
def mock_config():
    """Setup mock config for filters"""
    original_config = main.config.copy()
    
    main.config = {
        "groupfilter": None,
        "repofilter": None,
        "grouprepofilter": None
    }
    
    yield main.config
    
    # Restore original config
    main.config = original_config

# Tests for repository filtering
def test_check_repo_no_filters(sample_repo, mock_config):
    """Test checking repository with no filters applied"""
    # No filters set
    result = checkRepoInFilterSet(sample_repo)
    
    # Should include all repos when no filters are applied
    assert result == True

def test_check_repo_group_filter_match(sample_repo, mock_config):
    """Test checking repository with matching group filter"""
    # Set group filter to match test-org
    main.config["groupfilter"] = "test-org"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match the group filter
    assert result == True

def test_check_repo_group_filter_no_match(sample_repo, mock_config):
    """Test checking repository with non-matching group filter"""
    # Set group filter that doesn't match
    main.config["groupfilter"] = "other-org"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should not match the group filter
    assert result == False

def test_check_repo_regex_group_filter(sample_repo, mock_config):
    """Test checking repository with regex group filter"""
    # Set regex group filter
    main.config["groupfilter"] = "test-.*"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match the regex pattern
    assert result == True

def test_check_repo_repo_filter_match(sample_repo, mock_config):
    """Test checking repository with matching repo filter"""
    # Set repo filter to match test-repo
    main.config["repofilter"] = "test-repo"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match the repo filter
    assert result == True

def test_check_repo_repo_filter_no_match(sample_repo, mock_config):
    """Test checking repository with non-matching repo filter"""
    # Set repo filter that doesn't match
    main.config["repofilter"] = "other-repo"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should not match the repo filter
    assert result == False

def test_check_repo_regex_repo_filter(sample_repo, mock_config):
    """Test checking repository with regex repo filter"""
    # Set regex repo filter
    main.config["repofilter"] = "test-.*"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match the regex pattern
    assert result == True

def test_check_repo_both_filters_match(sample_repo, mock_config):
    """Test checking repository with both group and repo filters matching"""
    # Set both filters to match
    main.config["groupfilter"] = "test-org"
    main.config["repofilter"] = "test-repo"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match both filters
    assert result == True

def test_check_repo_both_filters_one_mismatch(sample_repo, mock_config):
    """Test checking repository with one filter matching and one not"""
    # Set group filter to match but repo filter to not match
    main.config["groupfilter"] = "test-org"
    main.config["repofilter"] = "other-repo"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should not match due to repo filter
    assert result == False
    
    # Reset and try the opposite
    main.config["groupfilter"] = "other-org"
    main.config["repofilter"] = "test-repo"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should not match due to group filter
    assert result == False

def test_check_repo_group_repo_filter_match_group(sample_repo, mock_config):
    """Test checking repository with group/repo filter matching the group"""
    # Set group/repo filter to match the group name
    main.config["grouprepofilter"] = "test-org"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match the group/repo filter
    assert result == True

def test_check_repo_group_repo_filter_match_repo(sample_repo, mock_config):
    """Test checking repository with group/repo filter matching the repo name"""
    # Set group/repo filter to match the repo name
    main.config["grouprepofilter"] = "test-repo"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match the group/repo filter
    assert result == True

def test_check_repo_group_repo_filter_no_match(sample_repo, mock_config):
    """Test checking repository with non-matching group/repo filter"""
    # Set group/repo filter that doesn't match
    main.config["grouprepofilter"] = "other"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should not match the group/repo filter
    assert result == False

def test_check_repo_group_repo_filter_regex(sample_repo, mock_config):
    """Test checking repository with regex group/repo filter"""
    # Set regex group/repo filter
    main.config["grouprepofilter"] = ".*-.*"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match the regex pattern
    assert result == True

def test_check_repo_case_insensitive(sample_repo, mock_config):
    """Test checking repository with case-insensitive filters"""
    # Set filters with different case
    main.config["groupfilter"] = "TEST-org"
    main.config["repofilter"] = "TEST-repo"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match case-insensitive
    assert result == True
    
    # Try group/repo filter too
    main.config["groupfilter"] = None
    main.config["repofilter"] = None
    main.config["grouprepofilter"] = "TEST-org"
    
    result = checkRepoInFilterSet(sample_repo)
    
    # Should match case-insensitive
    assert result == True

def test_check_repo_invalid_regex(sample_repo, mock_config):
    """Test checking repository with invalid regex pattern"""
    # Set an invalid regex pattern
    main.config["groupfilter"] = "test-org["  # Missing closing bracket
    
    # Should raise an exception due to invalid regex
    with pytest.raises(re.error):
        checkRepoInFilterSet(sample_repo)
