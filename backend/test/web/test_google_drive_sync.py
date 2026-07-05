from unittest.mock import MagicMock, patch

from backend.src.web.cloud.google_drive_sync import GoogleDriveSync


class TestGoogleDriveSync:
    def test_init_with_token(self):
        """Test initialization when access token is provided directly."""
        sync = GoogleDriveSync(
            local_source_path="/tmp/local",
            drive_destination_folder_name="Backup",
            google_access_token="test_token",
            dry_run=True,
            action_local_orphans="upload",
            action_remote_orphans="download",
            extra_unused_argument="hello",  # Testing kwargs safety
        )

        assert sync.config["access_token"] == "test_token"
        assert sync.config["local_path"] == "/tmp/local"
        assert sync.config["remote_path"] == "Backup"
        assert sync.config["dry_run"] is True
        assert sync.config["action_local"] == "upload"
        assert sync.config["action_remote"] == "download"

    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    @patch("google.auth.transport.requests.Request")
    def test_init_with_service_account(self, mock_request, mock_from_info):
        """Test service account auth flow."""
        mock_creds = MagicMock()
        mock_creds.token = "sa_token"
        mock_from_info.return_value = mock_creds

        sa_data = {"project_id": "test-project"}
        sync = GoogleDriveSync(
            local_source_path="/tmp/local",
            drive_destination_folder_name="Backup",
            service_account_data=sa_data,
        )

        mock_from_info.assert_called_once_with(
            sa_data, scopes=["https://www.googleapis.com/auth/drive"]
        )
        mock_creds.refresh.assert_called_once()
        assert sync.config["access_token"] == "sa_token"

    @patch("google.oauth2.credentials.Credentials.from_authorized_user_file")
    def test_init_with_personal_account_valid_token_file(self, mock_from_file):
        """Test personal account auth when valid token file exists."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.token = "token_from_file"
        mock_from_file.return_value = mock_creds

        with patch("os.path.exists", return_value=True):
            sync = GoogleDriveSync(
                local_source_path="/tmp/local",
                drive_destination_folder_name="Backup",
                client_secrets_data={"client_id": "123"},
                token_file="/tmp/token.json",
            )

        mock_from_file.assert_called_once_with(
            "/tmp/token.json", ["https://www.googleapis.com/auth/drive"]
        )
        assert sync.config["access_token"] == "token_from_file"

    @patch("google.oauth2.credentials.Credentials.from_authorized_user_file")
    @patch("subprocess.Popen")
    def test_init_with_personal_account_flow_runs(self, mock_popen, mock_from_file):
        """Test personal account auth flow runs when no valid token exists."""
        # Setup: token file does not exist initially, then exists after auth helper runs
        mock_creds = MagicMock()
        mock_creds.token = "flow_token"
        mock_from_file.return_value = mock_creds

        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Exited immediately/successfully in mock
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("SUCCESS", "")
        mock_popen.return_value = mock_process

        client_secrets = {"client_id": "123", "client_secret": "abc"}

        called_exists = []
        def side_effect_exists(path):
            if path == "/tmp/token.json":
                if not called_exists:
                    called_exists.append(True)
                    return False
                return True
            return False

        with patch("os.path.exists", side_effect=side_effect_exists), \
             patch("os.path.dirname", return_value="/tmp"):

            sync = GoogleDriveSync(
                local_source_path="/tmp/local",
                drive_destination_folder_name="Backup",
                client_secrets_data=client_secrets,
                token_file="/tmp/token.json",
            )

            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            assert "gdrive_auth_helper.py" in args[0][1]

        assert sync.config["access_token"] == "flow_token"

