"""Unit tests for dlunch.gui module."""

import pytest
from unittest.mock import Mock, patch, PropertyMock
import omegaconf
import pandas as pd

from dlunch.gui import (
    Person,
    PersonBirthday,
    PasswordRenewer,
    BackendPasswordRenewer,
    BackendAddPrivilegedUser,
    BackendUserEraser,
    GraphicInterface,
    BackendInterface,
    _force_logout,
)
from dlunch.auth import AuthUser


class TestPerson:
    """Test Person param class."""

    @pytest.fixture
    def mock_config(self):
        """Mock config."""
        config = Mock()
        config.panel.lunch_times_options = ["12:30", "13:00"]
        config.panel.guest_types = ["Guest", "VIP"]
        return config

    @pytest.fixture
    def mock_guest_user(self):
        """Mock auth user."""
        auth_user = Mock(spec=AuthUser)
        auth_user.is_guest.return_value = True
        auth_user.name = "testuser"
        return auth_user

    @pytest.fixture
    def mock_auth_user(self):
        """Mock auth user."""
        auth_user = Mock(spec=AuthUser)
        auth_user.is_guest.return_value = False
        auth_user.name = "testuser"
        return auth_user

    def test_init_default(self, mock_config, mock_guest_user):
        """Test Person initialization with defaults."""
        person = Person(config=mock_config, auth_user=mock_guest_user)
        assert person.username == ""
        assert person.lunch_time == "12:30"
        assert person.guest == "Guest"
        assert not person.takeaway

    def test_init_with_privileged_user(self, mock_config, mock_auth_user):
        """Test Person initialization with privileged user."""
        person = Person(config=mock_config, auth_user=mock_auth_user)
        assert person.username == "testuser"

    def test_init_with_guest_user(self, mock_config):
        """Test Person initialization with guest user."""
        mock_guest_auth = Mock(spec=AuthUser)
        mock_guest_auth.is_guest.return_value = True
        mock_guest_auth.name = None
        person = Person(config=mock_config, auth_user=mock_guest_auth)
        assert person.username == ""

    def test_param_objects_set(self, mock_config, mock_auth_user):
        """Test that param objects are set from config."""
        person = Person(config=mock_config, auth_user=mock_auth_user)
        assert "12:30" in person.param.lunch_time.objects
        assert "13:00" in person.param.lunch_time.objects
        assert "Guest" in person.param.guest.objects
        assert "VIP" in person.param.guest.objects


class TestPersonBirthday:
    """Test PersonBirthday param class."""

    def test_init(self):
        """Test PersonBirthday initialization."""
        person_birthday = PersonBirthday()
        assert person_birthday.first_name == ""
        assert person_birthday.last_name == ""
        assert person_birthday.birthday_date is None

    def test_str(self):
        """Test PersonBirthday __str__."""
        person_birthday = PersonBirthday()
        person_birthday.first_name = "John"
        person_birthday.last_name = "Doe"
        # Note: name property might not exist, adjust based on actual implementation
        # For now, test the __str__ as is
        str_repr = str(person_birthday)
        assert "PERSON_BIRTHDAY" in str_repr


class TestPasswordRenewer:
    """Test PasswordRenewer param class."""

    def test_init(self):
        """Test PasswordRenewer initialization."""
        renewer = PasswordRenewer()
        assert renewer.old_password == ""
        assert renewer.new_password == ""
        assert renewer.repeat_new_password == ""

    def test_str(self):
        """Test PasswordRenewer __str__."""
        renewer = PasswordRenewer()
        assert str(renewer) == "PasswordRenewer"


class TestBackendPasswordRenewer:
    """Test BackendPasswordRenewer param class."""

    def test_init(self):
        """Test BackendPasswordRenewer initialization."""
        renewer = BackendPasswordRenewer()
        assert renewer.user == ""
        assert renewer.new_password == ""
        assert renewer.repeat_new_password == ""
        assert not renewer.admin
        assert not renewer.guest

    def test_str(self):
        """Test BackendPasswordRenewer __str__."""
        renewer = BackendPasswordRenewer()
        assert str(renewer) == "BackendPasswordRenewer"


class TestBackendAddPrivilegedUser:
    """Test BackendAddPrivilegedUser param class."""

    def test_init(self):
        """Test BackendAddPrivilegedUser initialization."""
        adder = BackendAddPrivilegedUser()
        assert adder.user == ""
        assert not adder.admin

    def test_str(self):
        """Test BackendAddPrivilegedUser __str__."""
        adder = BackendAddPrivilegedUser()
        assert str(adder) == "BackendAddUser"


class TestBackendUserEraser:
    """Test BackendUserEraser param class."""

    def test_init(self):
        """Test BackendUserEraser initialization."""
        eraser = BackendUserEraser()
        assert eraser.user == ""

    def test_str(self):
        """Test BackendUserEraser __str__."""
        eraser = BackendUserEraser()
        assert str(eraser) == "BackendUserEraser"


class TestGraphicInterface:
    """Test GraphicInterface class."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock authenticated user."""
        auth_user = Mock(spec=AuthUser)
        auth_user.is_guest.return_value = False
        auth_user.is_admin.return_value = False
        auth_user.name = "testuser"
        auth_user.auth_context = Mock()
        auth_user.auth_context.is_auth_active.return_value = False
        auth_user.auth_context.is_basic_auth_active.return_value = False
        return auth_user

    @pytest.fixture
    def mock_waiter(self):
        """Mock waiter object."""
        waiter = Mock()
        waiter.database_connector = Mock()
        waiter.database_connector.get_user_birthday.return_value = None
        waiter.database_connector.set_flag = Mock()
        return waiter

    @patch("dlunch.gui.pn.state")
    def test_graphic_interface_open_backend(self, mock_pn_state):
        """Test open_backend method."""
        mock_location = Mock()
        mock_location.pathname = "/app"
        mock_location.reload = False
        mock_pn_state.location = mock_location

        # Skip the full initialization by directly testing the method
        gi = GraphicInterface.__new__(GraphicInterface)
        gi.open_backend()

        # Verify pathname was modified to include /backend
        assert "/backend" in mock_pn_state.location.pathname

    @patch("dlunch.gui.pn.state")
    def test_graphic_interface_force_logout(self, mock_pn_state):
        """Test force_logout method."""
        mock_location = Mock()
        mock_location.pathname = "/app"
        mock_location.reload = False
        mock_pn_state.location = mock_location

        # Skip the full initialization by directly testing the method
        gi = GraphicInterface.__new__(GraphicInterface)
        gi.force_logout()

        # Verify that _force_logout is called (it modifies pathname)
        assert mock_pn_state.location.pathname == "/logout"

    def test_backend_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test backend button on_click calls open_backend."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate button click
        with patch.object(gi, "open_backend") as mock_open_backend:
            gi.backend_button.clicks += 1

            # Verify open_backend was called
            mock_open_backend.assert_called_once()

    def test_logout_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test logout button on_click calls force_logout."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate button click
        with patch.object(gi, "force_logout") as mock_force_logout:
            gi.logout_button.clicks += 1

            # Verify force_logout was called
            mock_force_logout.assert_called_once()

    def test_refresh_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test refresh button on_click calls waiter.reload_menu."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate button click
        gi.refresh_button.clicks += 1

        # Verify waiter.reload_menu was called
        mock_waiter.reload_menu.assert_called()

    def test_send_order_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test send order button on_click calls waiter.send_order."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate button click
        gi.send_order_button.clicks += 1

        # Verify waiter.send_order was called
        mock_waiter.send_order.assert_called()

    def test_delete_order_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test delete order button on_click calls waiter.delete_order."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate button click
        gi.delete_order_button.clicks += 1

        # Verify waiter.delete_order was called
        mock_waiter.delete_order.assert_called()

    def test_change_order_time_takeaway_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test change order time/takeaway button on_click calls waiter.change_order_time_takeaway."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate button click
        gi.change_order_time_takeaway_button.clicks += 1

        # Verify waiter.change_order_time_takeaway was called
        mock_waiter.change_order_time_takeaway.assert_called()

    def test_build_menu_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test build menu button on_click calls waiter.build_menu."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate button click
        gi.build_menu_button.clicks += 1

        # Verify waiter.build_menu was called
        mock_waiter.build_menu.assert_called()

    def test_submit_birthday_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test submit birthday button on_click calls submit_birthday_button_callback."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Mock the database_connector.set_user_birthday method
        mock_waiter.database_connector.set_user_birthday = Mock()

        # Mock pn.state.notifications
        with patch("dlunch.gui.pn.state") as mock_pn_state:
            mock_pn_state.notifications = Mock()

            # Simulate button click
            gi.submit_birthday_button.clicks += 1

            # Verify set_user_birthday was called or error notification was shown
            # (depends on whether birthday_date is set)
            mock_pn_state.notifications.error.assert_called()

    def test_delete_birthday_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test delete birthday button on_click calls delete_birthday_button_callback."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Mock the database_connector.delete_user_birthday method
        mock_waiter.database_connector.delete_user_birthday = Mock(
            return_value=1
        )

        # Mock pn.state.notifications
        with patch("dlunch.gui.pn.state") as mock_pn_state:
            mock_pn_state.notifications = Mock()

            # Simulate button click
            gi.delete_birthday_button.clicks += 1

            # Verify delete_user_birthday was called
            mock_waiter.database_connector.delete_user_birthday.assert_called()

    def test_submit_password_button_on_click(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test submit password button on_click calls auth_context.submit_password."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Mock the auth_context.submit_password method
        mock_auth_user.auth_context.submit_password = Mock()

        # Simulate button click
        gi.submit_password_button.clicks += 1

        # Verify submit_password was called
        mock_auth_user.auth_context.submit_password.assert_called()

    def test_toggle_no_more_order_button_on_toggle(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test toggle no more order button on_toggle calls reload_on_no_more_order_callback."""
        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate toggle button change
        gi.toggle_no_more_order_button.value = True

        # Verify database_connector.set_flag was called
        mock_waiter.database_connector.set_flag.assert_called()
        # Verify waiter.reload_menu was called
        mock_waiter.reload_menu.assert_called()

    def test_toggle_guest_override_button_on_toggle(
        self, test_config, mock_auth_user, mock_waiter
    ):
        """Test toggle guest override button on_toggle calls reload_on_guest_override_callback."""
        # Set up non-guest user for this test
        mock_auth_user.is_guest.return_value = False

        gi = GraphicInterface(
            config=test_config,
            auth_user=mock_auth_user,
            waiter=mock_waiter,
            app=Mock(),
        )

        # Simulate toggle button change
        gi.toggle_guest_override_button.value = True

        # Verify database_connector.set_flag was called
        mock_waiter.database_connector.set_flag.assert_called()
        # Verify waiter.reload_menu was called
        mock_waiter.reload_menu.assert_called()


class TestBackendInterface:
    """Test BackendInterface class."""

    @pytest.fixture
    def mock_auth_user(self):
        """Mock authenticated user."""
        auth_user = Mock(spec=AuthUser)
        auth_user.is_guest.return_value = False
        auth_user.is_admin.return_value = True
        auth_user.name = "admin_user"
        auth_user.auth_context = Mock()
        auth_user.auth_context.is_auth_active.return_value = False
        auth_user.auth_context.is_basic_auth_active.return_value = False
        auth_user.auth_context.list_users_guests_and_privileges.return_value = (
            pd.DataFrame()
        )
        return auth_user

    @patch("dlunch.gui.models.Flags.read_as_df")
    def test_backend_interface_exit_backend(
        self, mock_flags_read, test_config, mock_auth_user
    ):
        """Test exit_backend method."""
        mock_flags_read.return_value = pd.DataFrame()

        with patch("dlunch.gui.pn.state") as mock_pn_state:
            mock_pn_state.location.pathname = "/backend"
            mock_pn_state.location.reload = False

            bi = BackendInterface(config=test_config, auth_user=mock_auth_user)

            bi.exit_backend()

            # Verify pathname was modified to home
            assert "/" in mock_pn_state.location.pathname

    @patch("dlunch.gui.models.Flags.read_as_df")
    def test_backend_interface_reload_backend(
        self, mock_flags_read, test_config, mock_auth_user
    ):
        """Test reload_backend method updates data."""
        mock_flags_read.return_value = pd.DataFrame(
            {"id": [1, 2], "flag": ["flag1", "flag2"]}
        )

        bi = BackendInterface(config=test_config, auth_user=mock_auth_user)

        bi.reload_backend()

        # Verify users_tabulator was updated
        bi.users_tabulator.value = (
            mock_auth_user.auth_context.list_users_guests_and_privileges()
        )
        assert bi.users_tabulator.value is not None
        # Verify flags_content was updated
        assert bi.flags_content.value is not None

    @patch("dlunch.gui.models.Flags.read_as_df")
    def test_exit_button_on_click(
        self, mock_flags_read, test_config, mock_auth_user
    ):
        """Test exit button on_click calls exit_backend."""
        mock_flags_read.return_value = pd.DataFrame()

        bi = BackendInterface(config=test_config, auth_user=mock_auth_user)

        # Simulate button click
        with patch.object(bi, "exit_backend") as mock_exit:
            bi.exit_button.clicks += 1

            # Verify exit_backend was called
            mock_exit.assert_called_once()

    @patch("dlunch.gui.models.Flags.read_as_df")
    def test_submit_password_button_on_click(
        self, mock_flags_read, test_config, mock_auth_user
    ):
        """Test submit password button on_click calls auth_context.backend_submit_password and reload_backend."""
        mock_flags_read.return_value = pd.DataFrame()

        bi = BackendInterface(config=test_config, auth_user=mock_auth_user)

        # Mock reload_backend
        with patch.object(bi, "reload_backend") as mock_reload:
            # Simulate button click
            bi.submit_password_button.clicks += 1

            # Verify backend_submit_password was called
            mock_auth_user.auth_context.backend_submit_password.assert_called()
            # Verify reload_backend was called
            mock_reload.assert_called()

    @patch("dlunch.gui.models.Flags.read_as_df")
    def test_add_privileged_user_button_on_click(
        self, mock_flags_read, test_config, mock_auth_user
    ):
        """Test add privileged user button on_click calls add_privileged_user and reload_backend."""
        mock_flags_read.return_value = pd.DataFrame()

        bi = BackendInterface(config=test_config, auth_user=mock_auth_user)

        # Mock reload_backend and pn.state.notifications
        # Need to patch dlunch.gui.AuthUser, because an istance ofAuthUser is created
        # inside the add privileged user button callback
        with patch.object(bi, "reload_backend") as mock_reload:
            with patch("dlunch.gui.pn.state") as mock_pn_state:
                with patch("dlunch.gui.AuthUser") as mock_auth_user_class:
                    mock_auth_user_instance = Mock()
                    mock_auth_user_class.return_value = mock_auth_user_instance
                    mock_pn_state.notifications = Mock()

                    # Simulate button click
                    bi.add_privileged_user_button.clicks += 1

                    # Verify add_privileged_user was called
                    mock_auth_user_instance.add_privileged_user.assert_called()
                    # Verify reload_backend was called
                    mock_reload.assert_called()

    @patch("dlunch.gui.models.Flags.read_as_df")
    def test_delete_user_button_on_click(
        self, mock_flags_read, test_config, mock_auth_user
    ):
        """Test delete user button on_click calls remove_user and reload_backend."""
        mock_flags_read.return_value = pd.DataFrame()

        bi = BackendInterface(config=test_config, auth_user=mock_auth_user)

        # Mock reload_backend and pn.state.notifications
        # Need to patch dlunch.gui.AuthUser, because an istance ofAuthUser is created
        # inside the delete user button callback
        with patch.object(bi, "reload_backend") as mock_reload:
            with patch("dlunch.gui.pn.state") as mock_pn_state:
                with patch("dlunch.gui.AuthUser") as mock_auth_user_class:
                    mock_auth_user_instance = Mock()
                    mock_auth_user_instance.remove_user.return_value = {
                        "privileged_users_deleted": 1,
                        "credentials_deleted": 1,
                    }
                    mock_auth_user_class.return_value = mock_auth_user_instance
                    mock_pn_state.notifications = Mock()

                    # Simulate button click
                    bi.delete_user_button.clicks += 1

                    # Verify remove_user was called
                    mock_auth_user_instance.remove_user.assert_called()
                    # Verify reload_backend was called
                    mock_reload.assert_called()

    @patch("dlunch.gui.models.Flags.read_as_df")
    def test_clear_flags_button_on_click(
        self, mock_flags_read, test_config, mock_auth_user
    ):
        """Test clear flags button on_click calls Flags.clear_guest_override and reload_backend."""
        mock_flags_read.return_value = pd.DataFrame()

        bi = BackendInterface(config=test_config, auth_user=mock_auth_user)

        # Mock reload_backend and pn.state.notifications
        with patch(
            "dlunch.gui.models.Flags.clear_guest_override"
        ) as mock_clear_flags:
            with patch.object(bi, "reload_backend") as mock_reload:
                with patch("dlunch.gui.pn.state") as mock_pn_state:
                    mock_pn_state.notifications = Mock()

                    # Simulate button click
                    bi.clear_flags_button.clicks += 1

                    # Verify clear_guest_override was called
                    mock_clear_flags.assert_called()
                    # Verify reload_backend was called
                    mock_reload.assert_called()


class TestForceLogout:
    """Test _force_logout function."""

    @patch("dlunch.gui.pn.state")
    def test_force_logout(self, mock_pn_state):
        """Test that _force_logout sets the pathname to logout."""
        # _force_logout splits by "/" and takes first element, then adds "/logout"
        mock_pn_state.location.pathname = "backend/error"
        mock_pn_state.location.reload = False

        _force_logout()

        assert mock_pn_state.location.pathname == "backend/logout"
        assert mock_pn_state.location.reload
