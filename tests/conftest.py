import os
import pytest
import shutil
from hydra import initialize, compose
from unittest import mock


@pytest.fixture(scope="session", autouse=True)
def setup_environment_variables():
    with mock.patch.dict(os.environ, clear=True):
        env_vars = {
            "PANEL_APP": "data-lunch-test-app",
            "PANEL_ENV": "production",
            "DATA_LUNCH_COOKIE_SECRET": "m7FG6dauWWKIbXecwCx0ZvT8R3gdIsS2svpiQviAw65B",
            "DATA_LUNCH_OAUTH_ENC_KEY": "n7M__09XF8DhRW9dxs7hFVZoPScXxlj6La7r9U240xc=",
            "DOCKER_USERNAME": "docker_user",
        }
        mp = pytest.MonkeyPatch()
        for k, v in env_vars.items():
            mp.setenv(k, v)
        # Yield ensures that environment variables are removed after the test
        yield


@pytest.fixture(scope="session")
def test_config(setup_environment_variables):
    """Set up Hydra config for tests."""

    # Set path for test shared data
    shared_data_path = "shared_data/test"
    # Define any overrides needed for testing
    hydra_overrides = [
        "panel=no_sched_clean",
        "db=sqlite",
        "server=no_auth",
        f"db.shared_data_folder={shared_data_path}",
        "db.ext_storage_upload.enabled=false",
    ]

    # Create config for
    initialize(
        config_path="../dlunch/conf",
        job_name="data_lunch_test",
        version_base="1.3",
    )
    config = compose(config_name="config", overrides=hydra_overrides)

    # Create shared data folder if it doesn't exist
    os.makedirs(config.db.shared_data_folder, exist_ok=True)

    yield config

    # Remove the test database file
    shutil.rmtree(shared_data_path)
