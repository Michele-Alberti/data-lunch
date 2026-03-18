"""Unit tests for dlunch.cli module."""

import omegaconf
import pytest
from click.testing import CliRunner
from unittest.mock import patch, Mock

from dlunch.cli import cli
from dlunch.auth import AuthContext
from dlunch.core import Waiter
from dlunch.models import (
    Password,
    Encrypted,
    Menu,
    Orders,
    Users,
    Stats,
    Birthdays,
    Flags,
    PrivilegedUsers,
    Credentials,
    DatabaseConnector,
    Data,
)


@pytest.fixture(scope="function")
def db_connector(test_config):
    db_connector = DatabaseConnector(config=test_config)
    db_connector.create_database()
    # Create a PrivilegedUsers record first (FK constraint)
    session = db_connector.create_session()
    with session:
        normal_user = PrivilegedUsers(user="normal_user", admin=False)
        admin_user = PrivilegedUsers(user="admin_user", admin=True)
        session.add_all([normal_user, admin_user])
        session.commit()
    yield db_connector
    Data.metadata.drop_all(db_connector.create_engine())
    # Shared data folder is removed in conftest.py fixture, so no need to clean up here


class TestCli:
    """Test CLI commands."""

    @pytest.fixture
    def runner(self):
        """CLI runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test CLI help output."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert (
            "Command line interface for managing Data-Lunch" in result.output
        )

    def test_users_list_privileged_only(
        self, runner, test_config, db_connector
    ):
        """Test users list command with privileged only."""
        with (
            patch("dlunch.cli.compose") as mock_compose,
            patch("dlunch.cli.initialize"),
        ):
            mock_compose.return_value = test_config
            result = runner.invoke(cli, ["users", "list", "--privileged-only"])
            assert result.exit_code == 0
            assert "normal_user" in result.output
            assert "admin_user" in result.output

    def test_users_add(self, runner, test_config, db_connector):
        """Test users add command."""
        with (
            patch("dlunch.cli.compose") as mock_compose,
            patch("dlunch.cli.initialize"),
        ):
            mock_compose.return_value = test_config

            result = runner.invoke(
                cli, ["users", "add", "testuser_admin", "--admin"]
            )
            assert result.exit_code == 0
            assert "User 'testuser_admin' added (admin: True)" in result.output

            result = runner.invoke(cli, ["users", "add", "testuser_normal"])
            assert result.exit_code == 0
            assert (
                "User 'testuser_normal' added (admin: False)" in result.output
            )

    def test_db_init(self, runner, test_config):
        """Test db init command."""
        with (
            patch("dlunch.cli.compose") as mock_compose,
            patch("dlunch.cli.initialize"),
        ):
            mock_compose.return_value = test_config

            result = runner.invoke(cli, ["db", "init"])
            assert result.exit_code == 0
            assert (
                "Database initialized (basic auth users: False)"
                in result.output
            )

            # Using omegaconf.open_dict to allow modifications to the test_config fixture
            with (
                omegaconf.open_dict(test_config),
                patch.dict(test_config, {"basic_auth": {"guest_user": True}}),
            ):
                result = runner.invoke(
                    cli, ["db", "init", "--add-basic-auth-users"]
                )
                assert result.exit_code == 0
                assert (
                    "Database initialized (basic auth users: True)"
                    in result.output
                )

            # Clean
            db_connector = DatabaseConnector(config=test_config)
            Data.metadata.drop_all(db_connector.create_engine())

    def test_db_clean(self, runner, test_config, db_connector):
        """Test db clean command."""
        with (
            patch("dlunch.cli.compose") as mock_compose,
            patch("dlunch.cli.initialize"),
        ):
            mock_compose.return_value = test_config

            result = runner.invoke(cli, ["db", "clean"], input="y\n")
            assert result.exit_code == 0
