import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open, call
import yaml
import sys
from datetime import datetime

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
    from main import (
        readFile, writeFile, updateRepoInfo, checkRepoInFilterSet, 
        persistState, enrichRepoData, discover_backends, create_askpass_script
    )
    import main


# Fixtures for common test data
@pytest.fixture
def sample_repo():
    """Create a sample repository object for testing"""
    return {
        "type": "github",
        "id": 12345,
        "name": "test-repo",
        "group": "test-org",
        "repo_key": "test-repo",
        "group_key": "test-org",
        "ssh_link": "git@github.example.com:test-org/test-repo.git",
        "http_link": "https://github.example.com/test-org/test-repo.git",
        "default_branch": "main",
        "contact_name": "Test User",
        "contact_mail": "test@example.com",
        "latest_branch": "feature-branch",
        "folder": "/tmp/repos/github/test-org/test-repo",
        "scanned": None,
        "secrets_found": None,
        "report_path": None
    }

@pytest.fixture
def sample_repos(sample_repo):
    """Create a dictionary of sample repositories"""
    repos = {}
    # Add first repo
    repos[12345] = sample_repo
    
    # Add a second repo
    repo2 = sample_repo.copy()
    repo2["id"] = 67890
    repo2["name"] = "another-repo"
    repos[67890] = repo2
    
    return repos

@pytest.fixture
def mock_config():
    """Create a mock for the main.config dictionary"""
    original_config = main.config.copy()
    main.config = {
        "data_version": 1,
        "backends": {},
        "backends_chosen": ["github", "gitlab"],
        "output_folder": "test_output",
        "updateinfo": False,
        "verbose": False,
        "groupfilter": None,
        "repofilter": None,
        "grouprepofilter": None,
        "scan_gitleaks": True,
        "no_clone": False,
        "rulesfilter": None
    }
    yield main.config
    # Restore original config
    main.config = original_config

# Tests for file operations
@patch("shutil.move")
@patch("yaml.dump")
def test_write_file(mock_yaml_dump, mock_shutil_move, mock_config):
    """Test the writeFile function"""
    data = {"key": "value"}
    writeFile(data, "test.yaml")

    # Check if yaml.dump was called with correct arguments
    mock_yaml_dump.assert_called_once()
    args, kwargs = mock_yaml_dump.call_args
    assert args[0] == {"data_version": 1, "data": data}

    mock_shutil_move.assert_called_once()
    args, kwargs = mock_shutil_move.call_args
    assert args[1] == "test.yaml"


@patch("builtins.open", new_callable=mock_open)
@patch("yaml.safe_load")
def test_read_file_valid_version(mock_yaml_load, mock_file_open, mock_config):
    """Test the readFile function with valid data version"""
    mock_yaml_load.return_value = {
        "data_version": 1,
        "data": {"key": "value"}
    }
    
    result = readFile("test.yaml")
    
    # Check if file was opened
    mock_file_open.assert_called_once_with("test.yaml", "r")
    
    # Check the returned data
    assert result == {"key": "value"}

@patch("builtins.open", new_callable=mock_open)
@patch("yaml.safe_load")
def test_read_file_invalid_version(mock_yaml_load, mock_file_open, mock_config):
    """Test the readFile function with invalid data version"""
    mock_yaml_load.return_value = {
        "data_version": 0,  # Different version
        "data": {"key": "value"}
    }
    
    result = readFile("test.yaml")
    
    # Check if file was opened
    mock_file_open.assert_called_once_with("test.yaml", "r")
    
    # For invalid version, should return None
    assert result is None

# Tests for repo operations
def test_update_repo_info_new_repos(sample_repos):
    """Test updateRepoInfo with new repos"""
    current = {12345: sample_repos[12345]}
    new = {67890: sample_repos[67890]}
    
    result = updateRepoInfo(current, new)
    
    # Should add the new repo
    assert 67890 in result
    assert result[67890] == sample_repos[67890]

def test_update_repo_info_existing_repos(sample_repos):
    """Test updateRepoInfo with existing repos"""
    current = {12345: sample_repos[12345].copy()}
    current[12345]["contact_name"] = "Old User"
    current[12345]["scanned"] = "main"
    current[12345]["secrets_found"] = 5
    
    new = {12345: sample_repos[12345].copy()}
    new[12345]["contact_name"] = "New User"
    
    result = updateRepoInfo(current, new)
    
    # Should update contact_name but preserve scanned and secrets_found
    assert result[12345]["contact_name"] == "New User"
    assert result[12345]["scanned"] == "main"
    assert result[12345]["secrets_found"] == 5

def test_update_repo_info_none_values():
    """Test updateRepoInfo with None values"""
    # New data with None value
    with pytest.raises(Exception, match="New data of type None"):
        updateRepoInfo({}, None)
    
    # Empty new data
    result = updateRepoInfo(None, {})
    assert result == {}
    
    # Current None, new has data
    result = updateRepoInfo(None, {"id": "repo"})
    assert result == {"id": "repo"}

# Tests for filtering
def test_check_repo_in_filter_set_no_filters(sample_repo, mock_config):
    """Test checkRepoInFilterSet with no filters"""
    assert checkRepoInFilterSet(sample_repo) == True

def test_check_repo_in_filter_set_group_filter(sample_repo, mock_config):
    """Test checkRepoInFilterSet with group filter"""
    # Matching filter
    main.config["groupfilter"] = "test"
    assert checkRepoInFilterSet(sample_repo) == True
    
    # Non-matching filter
    main.config["groupfilter"] = "nonexistent"
    assert checkRepoInFilterSet(sample_repo) == False

def test_check_repo_in_filter_set_repo_filter(sample_repo, mock_config):
    """Test checkRepoInFilterSet with repo filter"""
    # Matching filter
    main.config["repofilter"] = "test"
    assert checkRepoInFilterSet(sample_repo) == True
    
    # Non-matching filter
    main.config["repofilter"] = "nonexistent"
    assert checkRepoInFilterSet(sample_repo) == False

def test_check_repo_in_filter_set_group_repo_filter(sample_repo, mock_config):
    """Test checkRepoInFilterSet with group/repo filter"""
    # Matching group
    main.config["grouprepofilter"] = "test-org"
    assert checkRepoInFilterSet(sample_repo) == True
    
    # Matching repo
    main.config["grouprepofilter"] = "test-repo"
    assert checkRepoInFilterSet(sample_repo) == True
    
    # Non-matching filter
    main.config["grouprepofilter"] = "nonexistent"
    assert checkRepoInFilterSet(sample_repo) == False

# Tests for askpass script
def test_create_askpass_script():
    """Test create_askpass_script function"""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Create askpass script
            script_path = create_askpass_script("test-username", "test-token")
            
            # Check if file exists
            assert os.path.exists(script_path)
            
            # Check file permissions
            assert os.access(script_path, os.X_OK)
            
            # Check file content
            with open(script_path, 'r') as f:
                content = f.read()
                assert "test-username" in content
                assert "test-token" in content
                assert "Username for" in content
        finally:
            os.chdir(original_cwd)
            # Clean up script if it wasn't cleaned up
            if os.path.exists(script_path):
                os.unlink(script_path)

# Test for enrich repo data
def test_enrich_repo_data(sample_repo, mock_config):
    """Test enrichRepoData function"""
    # Mock backend
    mock_backend = MagicMock()
    mock_backend.name.return_value = "github"
    
    # Set up the return value for enrichRepo
    enriched_repo = sample_repo.copy()
    enriched_repo["contact_name"] = "Enriched User"
    mock_backend.enrichRepo.return_value = enriched_repo
    
    # Mock config
    main.config["backends"] = {"github": mock_backend}
    main.config["verbose"] = True
    
    # Call enrichRepoData
    result = enrichRepoData(sample_repo)
    
    # Check if enrichRepo was called
    mock_backend.enrichRepo.assert_called_once_with(sample_repo)
    
    # Verify the result
    assert result["contact_name"] == "Enriched User"
