import os
import logging
from google.cloud import secretmanager
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger("secrets")


def load_gemini_api_key_from_secret_manager():
    if "GEMINI_API_KEY" in os.environ:
        logger.info("GEMINI_API_KEY is already set in environment.")
        return

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        logger.warning(
            "GOOGLE_CLOUD_PROJECT is not set. Cannot fetch secret from Secret Manager."
        )
        return

    secret_id = "gemini-api-key"
    secret_version = "latest"
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{secret_version}"

    logger.info(f"Attempting to fetch secret {name} from Secret Manager...")
    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": name})
        secret_payload = response.payload.data.decode("UTF-8")
        os.environ["GEMINI_API_KEY"] = secret_payload
        logger.info("Successfully loaded GEMINI_API_KEY from Secret Manager.")
    except GoogleAPIError as e:
        logger.warning(
            f"Failed to access Secret Manager: {e}. "
            "If running locally, ensure you have set GEMINI_API_KEY or "
            "authenticated application default credentials."
        )
    except Exception as e:
        logger.warning(f"Unexpected error loading secret from Secret Manager: {e}")
