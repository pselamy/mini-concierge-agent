import os
from unittest.mock import patch, MagicMock
import pytest
from google.api_core.exceptions import GoogleAPIError
from app.secrets import load_gemini_api_key_from_secret_manager

@pytest.fixture(autouse=True)
def clean_env():
    # Store original values
    orig_key = os.environ.get("GEMINI_API_KEY")
    orig_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    
    # Remove from env for test
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    if "GOOGLE_CLOUD_PROJECT" in os.environ:
        del os.environ["GOOGLE_CLOUD_PROJECT"]
        
    yield
    
    # Restore original values
    if orig_key is not None:
        os.environ["GEMINI_API_KEY"] = orig_key
    elif "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
        
    if orig_project is not None:
        os.environ["GOOGLE_CLOUD_PROJECT"] = orig_project
    elif "GOOGLE_CLOUD_PROJECT" in os.environ:
        del os.environ["GOOGLE_CLOUD_PROJECT"]

def test_secrets_already_set():
    os.environ["GEMINI_API_KEY"] = "preset-key"
    load_gemini_api_key_from_secret_manager()
    assert os.environ["GEMINI_API_KEY"] == "preset-key"

def test_secrets_no_project():
    load_gemini_api_key_from_secret_manager()
    assert "GEMINI_API_KEY" not in os.environ

@patch("google.cloud.secretmanager.SecretManagerServiceClient")
def test_secrets_success(mock_client_class):
    os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
    
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.payload.data = b"secret-payload-key"
    mock_client.access_secret_version.return_value = mock_response
    
    load_gemini_api_key_from_secret_manager()
    
    assert os.environ["GEMINI_API_KEY"] == "secret-payload-key"
    mock_client.access_secret_version.assert_called_once_with(
        request={"name": "projects/test-project/secrets/gemini-api-key/versions/latest"}
    )

@patch("google.cloud.secretmanager.SecretManagerServiceClient")
def test_secrets_api_error(mock_client_class):
    os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
    
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Simulate API error
    mock_client.access_secret_version.side_effect = GoogleAPIError("Permission denied")
    
    # Should not raise an exception, just print a warning
    load_gemini_api_key_from_secret_manager()
    
    assert "GEMINI_API_KEY" not in os.environ

@patch("google.cloud.secretmanager.SecretManagerServiceClient")
def test_secrets_generic_exception(mock_client_class):
    os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
    
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    # Simulate generic exception (e.g. ValueError)
    mock_client.access_secret_version.side_effect = ValueError("Some other error")
    
    # Should not raise an exception, just print a warning
    load_gemini_api_key_from_secret_manager()
    
    assert "GEMINI_API_KEY" not in os.environ

