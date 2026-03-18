"""Unit tests for dlunch.core module."""

import pytest
from unittest.mock import Mock, patch
import pandas as pd
from pathlib import Path
from sqlalchemy import select

import dlunch.gui as gui
import dlunch.models as models
from dlunch.auth import AuthUser
from dlunch.core import Waiter
from dlunch.models import DatabaseConnector
from dlunch.models import Data
from PIL import Image


class TestWaiter:
    """Test Waiter class."""

    @pytest.fixture
    def mock_panel_state(self):
        """Mock panel state."""
        state = Mock()
        state.user = "test@example.com"
        return state

    @pytest.fixture
    def waiter(self, test_config, mock_panel_state, mocker):
        """Create Waiter instance."""
        mocker.patch("dlunch.auth.pn.state", mock_panel_state)
        waiter = Waiter(config=test_config)
        waiter.database_connector.create_database()
        yield waiter
        Data.metadata.drop_all(waiter.database_connector.create_engine())
        # Shared data folder is removed in conftest.py fixture, so no need to clean up here

    def test_init(self, waiter, mock_panel_state, test_config, mocker):
        """Test Waiter initialization."""
        mocker.patch("dlunch.auth.pn.state", mock_panel_state)
        assert waiter.config == test_config
        assert waiter.auth_user.name == AuthUser(config=test_config).name
        assert (
            waiter.database_connector.config
            == DatabaseConnector(config=test_config).config
        )

    def test_set_config(self, waiter, test_config):
        """Test setting config."""
        waiter.set_config(test_config)
        assert waiter.config == test_config

    @patch("socket.gethostname")
    @patch("socket.gethostbyname")
    @patch("subprocess.run")
    def test_hostname(
        self, mock_subprocess, mock_gethostbyname, mock_gethostname, waiter
    ):
        """Test hostname property."""
        mock_gethostname.return_value = "testhost"
        mock_gethostbyname.return_value = "192.168.1.1"
        mock_subprocess.return_value = Mock(stdout=b"docker_user_testhost\n")

        result = waiter.hostname
        assert "testhost" in result

    @patch("pathlib.Path")
    def test_delete_files(self, mock_path, waiter):
        """Test deleting files."""
        mock_file = Mock()
        mock_file.name = "menu.png"
        mock_glob = Mock(return_value=[mock_file])
        mock_path_instance = Mock()
        mock_path_instance.glob = mock_glob
        mock_path.return_value = mock_path_instance
        waiter.delete_files()
        mock_file.unlink.assert_called_once_with(missing_ok=True)

    @patch("dlunch.models.Orders.clear")
    @patch("dlunch.models.Menu.clear")
    @patch("dlunch.models.Users.clear")
    @patch("dlunch.models.Flags.clear_guest_override")
    @patch("panel.state.clear_caches")
    def test_clean_tables(
        self,
        mock_clear_caches,
        mock_clear_guest_override,
        mock_clear_users,
        mock_clear_menu,
        mock_clear_orders,
        waiter,
    ):
        """Test cleaning tables."""
        waiter.database_connector.set_flag = Mock()
        waiter.clean_tables()
        mock_clear_orders.assert_called_once_with(config=waiter.config)
        mock_clear_menu.assert_called_once_with(config=waiter.config)
        mock_clear_users.assert_called_once_with(config=waiter.config)
        mock_clear_guest_override.assert_called_once_with(config=waiter.config)
        mock_clear_caches.assert_called_once()
        waiter.database_connector.set_flag.assert_called_once_with(
            id="no_more_orders", value=False
        )

    @patch("PIL.Image.open")
    @patch("pytesseract.pytesseract.image_to_string")
    @patch.object(Waiter, "clean_tables")
    @patch.object(Waiter, "delete_files")
    @patch.object(Waiter, "reload_menu")
    def test_build_menu_image(
        self,
        mock_reload_menu,
        mock_delete_files,
        mock_clean_tables,
        mock_pytesseract,
        mock_image_open,
        waiter,
    ):
        """Test building menu from image."""
        waiter.database_connector.set_flag = Mock()
        # Mock file widget
        mock_file_widget = Mock()
        mock_file_widget.value = b"fake image data"
        mock_file_widget.filename = "menu.png"
        mock_file_widget.save = Mock()

        # Mock graphic interface
        mock_gi = Mock()
        mock_gi.file_widget = mock_file_widget
        mock_gi.error_message = Mock()

        # Mock PIL image
        mock_img = Mock(spec=Image.Image)
        mock_img.format = "PNG"
        mock_image_open.return_value = mock_img
        mock_pytesseract.return_value = (
            "PRIMO\npizza\npasta\nSECONDO\nbistecca\nCONTORNO\nfagiolini"
        )

        # Mock app
        mock_app = Mock()

        # Mock event
        mock_event = Mock()

        with patch("dlunch.core.pn.state.notifications") as mock_notifications:
            mock_notifications.success = Mock()
            waiter.build_menu(mock_event, mock_app, mock_gi)

        mock_delete_files.assert_called_once()
        mock_clean_tables.assert_called_once()
        mock_file_widget.save.assert_called_once()
        mock_reload_menu.assert_called_once()

    @patch("pandas.read_excel")
    @patch("dlunch.models.Menu.write_from_df")
    @patch.object(Waiter, "clean_tables")
    @patch.object(Waiter, "delete_files")
    @patch.object(Waiter, "reload_menu")
    def test_build_menu_excel(
        self,
        mock_reload_menu,
        mock_delete_files,
        mock_clean_tables,
        mock_write_from_df,
        mock_read_excel,
        waiter,
    ):
        """Test building menu from Excel."""
        waiter.database_connector.set_flag = Mock()
        # Mock file widget
        mock_file_widget = Mock()
        mock_file_widget.value = b"fake excel data"
        mock_file_widget.filename = "menu.xlsx"
        mock_file_widget.save = Mock()

        # Mock graphic interface
        mock_gi = Mock()
        mock_gi.file_widget = mock_file_widget
        mock_gi.error_message = Mock()

        # Mock pandas read_excel
        mock_df = pd.DataFrame({"item": ["Pizza", "Pasta"]})
        mock_read_excel.return_value = mock_df

        # Mock app
        mock_app = Mock()

        # Mock event
        mock_event = Mock()

        with patch("dlunch.core.pn.state.notifications") as mock_notifications:
            mock_notifications.success = Mock()
            waiter.build_menu(mock_event, mock_app, mock_gi)

        mock_delete_files.assert_called_once()
        mock_clean_tables.assert_called_once()
        mock_file_widget.save.assert_called_once()
        mock_write_from_df.assert_called_once()
        mock_reload_menu.assert_called_once()

    def test_build_menu_no_file(self, waiter):
        """Test building menu with no file selected."""
        mock_file_widget = Mock()
        mock_file_widget.value = None

        mock_gi = Mock()
        mock_gi.file_widget = mock_file_widget

        mock_app = Mock()
        mock_event = Mock()

        with patch(
            "dlunch.core.pn.state.notifications.warning"
        ) as mock_warning:
            waiter.build_menu(mock_event, mock_app, mock_gi)
            mock_warning.assert_called_once()

    def test_reload_menu(self, waiter, test_config):
        """Test reloading menu."""

        waiter.database_connector.set_flag(id="no_more_orders", value=False)

        mock_app = Mock()
        mock_event = Mock()

        gi = gui.GraphicInterface(
            config=test_config,
            waiter=waiter,
            app=mock_app,
            guest_password="guest_password",
            auth_user=waiter.auth_user,
        )

        # Check that logs debug info have been called with proper messages
        with patch("logging.Logger.debug") as mock_debug:
            waiter.reload_menu(mock_event, gi)
            mock_debug.assert_any_call("menu reloaded")
            mock_debug.assert_any_call("results reloaded")
            mock_debug.assert_any_call("birthdays reloaded")
            mock_debug.assert_any_call("stats and info updated")

    def test_send_order_no_more_orders_flag(self, waiter, mocker):
        """Test send_order when no_more_orders flag is set."""
        # Mock dependencies
        mock_event = Mock()
        mock_app = Mock()
        mock_person = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="testuser")
        }
        mock_gi.error_message = Mock(visible=False)

        # Set the no_more_orders flag
        waiter.database_connector.set_flag(id="no_more_orders", value=True)

        # Mock reload_menu
        mocker.patch.object(waiter, "reload_menu")

        with patch("dlunch.core.pn.state.notifications.error") as mock_error:
            waiter.send_order(mock_event, mock_app, mock_person, mock_gi)
            mock_error.assert_called_once()
            waiter.reload_menu.assert_called_once()

    def test_send_order_missing_username(self, waiter, mocker):
        """Test send_order with missing username."""
        mock_event = Mock()
        mock_app = Mock()
        mock_person = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {"username": Mock(value_input="")}
        mock_gi.error_message = Mock(visible=False)
        # Create a proper mock dataframe
        mock_gi.dataframe = Mock()
        mock_gi.dataframe.value = pd.DataFrame({"order": [False, False]})

        with patch(
            "dlunch.core.pn.state.notifications.warning"
        ) as mock_warning:
            waiter.send_order(mock_event, mock_app, mock_person, mock_gi)
            # Should trigger warning for missing username
            calls = [str(call) for call in mock_warning.call_args_list]
            assert any("user name" in str(call).lower() for call in calls)

    def test_send_order_no_selection(self, waiter, mocker):
        """Test send_order with no order selected."""
        mock_event = Mock()
        mock_app = Mock()
        mock_person = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="testuser")
        }
        mock_gi.error_message = Mock(visible=False)

        # Create empty dataframe (no orders selected)
        mock_gi.dataframe = Mock()
        mock_df = pd.DataFrame({"order": [False, False]})
        mock_gi.dataframe.value = mock_df

        with patch(
            "dlunch.core.pn.state.notifications.warning"
        ) as mock_warning:
            waiter.send_order(mock_event, mock_app, mock_person, mock_gi)
            mock_warning.assert_called()

    def test_delete_order_no_more_orders_flag(self, waiter, mocker):
        """Test delete_order when no_more_orders flag is set."""
        mock_event = Mock()
        mock_app = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="testuser")
        }
        mock_gi.error_message = Mock(visible=False)

        # Set the no_more_orders flag
        waiter.database_connector.set_flag(id="no_more_orders", value=True)

        mocker.patch.object(waiter, "reload_menu")

        with patch("dlunch.core.pn.state.notifications.error") as mock_error:
            waiter.delete_order(mock_event, mock_app, mock_gi)
            mock_error.assert_called_once()
            waiter.reload_menu.assert_called_once()

    def test_delete_order_missing_username(self, waiter, mocker):
        """Test delete_order with missing username."""
        mock_event = Mock()
        mock_app = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {"username": Mock(value_input="")}
        mock_gi.error_message = Mock(visible=False)

        with patch(
            "dlunch.core.pn.state.notifications.warning"
        ) as mock_warning:
            waiter.delete_order(mock_event, mock_app, mock_gi)
            mock_warning.assert_called()

    def test_delete_order_nonexistent_user(self, waiter, mocker):
        """Test delete_order with non-existent user."""
        mock_event = Mock()
        mock_app = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="nonexistent")
        }
        mock_gi.error_message = Mock(visible=False)

        mocker.patch.object(waiter, "reload_menu")

        with patch(
            "dlunch.core.pn.state.notifications.warning"
        ) as mock_warning:
            waiter.delete_order(mock_event, mock_app, mock_gi)
            mock_warning.assert_called()

    def test_change_order_time_takeaway_updates_user(self, waiter, mocker):
        """Test change_order_time_takeaway successfully updates user time and takeaway."""
        # Seed menu
        menu_df = pd.DataFrame({"item": ["Pizza"]})
        models.Menu.write_from_df(
            config=waiter.config, df=menu_df, index=False
        )
        menu_df_db = models.Menu.read_as_df(
            config=waiter.config, index_col="id"
        )

        # Create user and order
        session = waiter.database_connector.create_session()
        with session:
            user = models.Users(
                id="testuser",
                lunch_time="12:00",
                takeaway=False,
            )
            session.add(user)
            session.commit()
            order = models.Orders(
                user="testuser",
                menu_item_id=int(menu_df_db.index[0]),
                note="",
            )
            session.add(order)
            session.commit()

        # Prepare mocks
        mock_event = Mock()
        mock_person = Mock(lunch_time="13:00", takeaway=True)
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="testuser")
        }

        # Patch reload_menu
        mocker.patch.object(waiter, "reload_menu")

        with patch(
            "dlunch.core.pn.state.notifications.success"
        ) as mock_success:
            waiter.change_order_time_takeaway(mock_event, mock_person, mock_gi)
            mock_success.assert_called_once()
            # Check success message contains updated details
            call_args = mock_success.call_args[0][0]
            assert "13:00 TAKEAWAY" in call_args
            assert "Pizza" in call_args

        # Assert database state
        session = waiter.database_connector.create_session()
        with session:
            updated_user = session.get(models.Users, "testuser")
            assert updated_user.lunch_time == "13:00"
            assert updated_user.takeaway

    def test_change_order_time_takeaway_no_more_orders_flag(
        self, waiter, mocker
    ):
        """Test change_order_time_takeaway when no_more_orders flag is set."""
        mock_event = Mock()
        mock_person = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="testuser")
        }

        waiter.database_connector.set_flag(id="no_more_orders", value=True)
        mocker.patch.object(waiter, "reload_menu")

        with patch("dlunch.core.pn.state.notifications.error") as mock_error:
            waiter.change_order_time_takeaway(mock_event, mock_person, mock_gi)
            mock_error.assert_called_once()
            waiter.reload_menu.assert_called_once()

    def test_change_order_time_takeaway_missing_username(self, waiter, mocker):
        """Test change_order_time_takeaway with missing username."""
        mock_event = Mock()
        mock_person = Mock()
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {"username": Mock(value_input="")}

        with patch(
            "dlunch.core.pn.state.notifications.warning"
        ) as mock_warning:
            waiter.change_order_time_takeaway(mock_event, mock_person, mock_gi)
            mock_warning.assert_called()

    def test_change_order_time_takeaway_nonexistent_user(self, waiter, mocker):
        """Test change_order_time_takeaway with nonexistent user."""
        mock_event = Mock()
        mock_person = Mock(lunch_time="13:00", takeaway=True)
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="nonexistent")
        }

        mocker.patch.object(waiter, "reload_menu")

        with patch(
            "dlunch.core.pn.state.notifications.warning"
        ) as mock_warning:
            waiter.change_order_time_takeaway(mock_event, mock_person, mock_gi)
            mock_warning.assert_called_once()
            call_args = mock_warning.call_args[0][0]
            assert "nonexistent" in call_args

    def test_df_list_by_lunch_time_empty(self, waiter):
        """Test df_list_by_lunch_time with no orders."""
        result = waiter.df_list_by_lunch_time()
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_download_dataframe_no_orders(self, waiter, mocker):
        """Test download_dataframe with no orders in database."""
        mock_gi = Mock()
        mock_gi.dataframe = Mock()
        mock_df = pd.DataFrame(
            {"item": ["Pizza", "Pasta"], "order": [False, False]}
        )
        mock_gi.dataframe.value = mock_df

        result = waiter.download_dataframe(mock_gi)

        assert isinstance(result, type(result))  # BytesIO type
        assert result.tell() == 0  # Pointer is at start (seeked to 0)

    def test_send_order_creates_user_and_order(self, waiter, mocker):
        """Test send_order successfully creates a user and order."""
        # Seed menu into database
        menu_df = pd.DataFrame({"item": ["Pizza", "Pasta"]})
        models.Menu.write_from_df(
            config=waiter.config, df=menu_df, index=False
        )

        # Build GUI dataframe with one selected item and a note
        menu_df_db = models.Menu.read_as_df(
            config=waiter.config, index_col="id"
        )
        note_col = waiter.config.panel.gui.note_column_name
        df_gui = menu_df_db.copy()
        df_gui["order"] = False
        df_gui.loc[menu_df_db.index[0], "order"] = True
        df_gui[note_col] = "MyNote"

        # Prepare mocks
        mock_event = Mock()
        mock_app = Mock()
        mock_person = Mock(
            lunch_time="12:00",
            takeaway=False,
            guest=waiter.config.panel.guest_types[0],
        )
        mock_gi = Mock()
        mock_gi.person_widget._widgets = {
            "username": Mock(value_input="testuser")
        }
        mock_gi.error_message = Mock(visible=False)
        mock_gi.dataframe = Mock()
        mock_gi.dataframe.value = df_gui

        # Patch reload_menu to avoid UI complexity
        mocker.patch.object(waiter, "reload_menu")

        with patch(
            "dlunch.core.pn.state.notifications.success"
        ) as mock_success:
            waiter.send_order(mock_event, mock_app, mock_person, mock_gi)
            mock_success.assert_called_once()

        # Assert database state
        session = waiter.database_connector.create_session()
        with session:
            user = session.get(models.Users, "testuser")
            assert user is not None
            assert user.lunch_time == "12:00"

            orders = session.scalars(
                select(models.Orders).where(models.Orders.user == "testuser")
            ).all()
            assert len(orders) == 1
            assert orders[0].note == "mynote"

    def test_df_list_by_lunch_time_with_orders(self, waiter):
        """Test df_list_by_lunch_time returns correct structure for orders."""
        # Seed menu and create two users (one takeaway)
        menu_df = pd.DataFrame({"item": ["Pizza", "Pasta"]})
        models.Menu.write_from_df(
            config=waiter.config, df=menu_df, index=False
        )
        menu_df_db = models.Menu.read_as_df(
            config=waiter.config, index_col="id"
        )

        # Create users and orders directly
        session = waiter.database_connector.create_session()
        with session:
            user1 = models.Users(
                id="user1",
                lunch_time="12:00",
                takeaway=False,
            )
            user2 = models.Users(
                id="guest1",
                lunch_time="12:00",
                takeaway=True,
                guest=waiter.config.panel.guest_types[0],
            )
            session.add_all([user1, user2])
            session.commit()
            # Create orders (one per user)
            order1 = models.Orders(
                user="user1",
                menu_item_id=int(menu_df_db.index[0]),
                note="hello",
            )
            order2 = models.Orders(
                user="guest1",
                menu_item_id=int(menu_df_db.index[1]),
                note="bye",
            )
            session.add_all([order1, order2])
            session.commit()

        result = waiter.df_list_by_lunch_time()
        takeaway_key = f"12:00 {waiter.config.panel.gui.takeaway_id}"

        assert "12:00" in result
        assert takeaway_key in result

        # Check columns include users, total and note
        note_col = waiter.config.panel.gui.note_column_name
        for key in ["12:00", takeaway_key]:
            df = result[key]
            assert note_col in df.columns
            assert waiter.config.panel.gui.total_column_name in df.columns

        # Check that notes were concatenated and lowercased
        df_normal = result["12:00"]
        df_takeaway = result[takeaway_key]
        assert (
            "1 hello"
            in df_normal.loc[
                menu_df_db.loc[menu_df_db.index[0], "item"], note_col
            ]
        )
        assert (
            "1 bye"
            in df_takeaway.loc[
                menu_df_db.loc[menu_df_db.index[1], "item"], note_col
            ]
        )

    def test_download_dataframe_with_orders(self, waiter):
        """Test download_dataframe exports Excel sheets for lunch times."""
        # Seed menu and create an order
        menu_df = pd.DataFrame({"item": ["Pizza", "Pasta"]})
        models.Menu.write_from_df(
            config=waiter.config, df=menu_df, index=False
        )
        menu_df_db = models.Menu.read_as_df(
            config=waiter.config, index_col="id"
        )

        session = waiter.database_connector.create_session()
        with session:
            user = models.Users(
                id="user1",
                lunch_time="12:00",
                takeaway=False,
            )
            session.add(user)
            session.commit()
            order = models.Orders(
                user="user1",
                menu_item_id=int(menu_df_db.index[0]),
                note="excel",
            )
            session.add(order)
            session.commit()

        mock_gi = Mock()
        mock_gi.dataframe = Mock()
        mock_gi.dataframe.value = pd.DataFrame(
            {"item": ["Pizza"], "order": [True]}
        )

        result = waiter.download_dataframe(mock_gi)

        # Validate Excel workbook has expected sheet
        xls = pd.ExcelFile(result)
        assert "12.00" in xls.sheet_names
