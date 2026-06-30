import pytest

from unittest.mock import MagicMock, patch
from src.database.image_database import PgvectorImageDatabase


class TestPgvectorImageDatabase:
    @pytest.fixture
    def mock_db(self):
        with patch("src.database.image_database.psycopg2.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Init triggers connection and table creation
            db = PgvectorImageDatabase(
                db_name="test_db",
                db_user="user",
                db_password="pw",
                db_host="host",
                db_port="5432",
            )

            # Reset mocks purely to clear the init calls
            mock_connect.reset_mock()
            mock_cursor.reset_mock()

            yield db, mock_conn, mock_cursor

    def test_init_connection_success(self):
        with patch("src.core.image_database.psycopg2.connect") as mock_connect:
            db = PgvectorImageDatabase(db_name="test")
            mock_connect.assert_called_once()
            assert db.conn is not None

    def test_add_group(self, mock_db):
        db, _, mock_cursor = mock_db
        db.add_group("My Group")
        mock_cursor.execute.assert_called()
        assert "INSERT INTO groups" in mock_cursor.execute.call_args[0][0]
        assert ("My Group",) == mock_cursor.execute.call_args[0][1]

    def test_add_subgroup(self, mock_db):
        db, _, mock_cursor = mock_db

        # _get_or_create_entity will be called first to get group_id
        # We mock fetchone to return a dummy ID like (1,)
        mock_cursor.fetchone.return_value = (100,)

        db.add_subgroup("My Subgroup", "My Group")

        # Verify calls. Should first get group ID, then insert subgroup
        assert mock_cursor.execute.call_count >= 2

    def test_add_image_basic(self, mock_db):
        db, _, mock_cursor = mock_db
        mock_cursor.fetchone.return_value = (500,)  # Return new image ID

        img_id = db.add_image("/path/to/img.jpg", width=800, height=600)

        assert img_id == 500
        assert "INSERT INTO images" in mock_cursor.execute.call_args[0][0]
        args = mock_cursor.execute.call_args[0][1]
        assert args[1] == "img.jpg"  # filename
        assert args[3] == 800  # width

    def test_add_image_with_tags(self, mock_db):
        db, _, mock_cursor = mock_db

        # Sequence of fetchone returns:
        # 1. Image Insert -> (10,)
        # 2. Tag Insert 'tag1' -> (1,)
        # 3. Tag Insert 'tag2' -> (2,)
        mock_cursor.fetchone.side_effect = [(10,), (1,), (2,)]

        db.add_image("/path/to/img.jpg", tags=["tag1", "tag2"])

        # Check that we tried to insert tags and image_tags
        # We can't easily count exact calls due to potentially multiple cursor contexts,
        # but we can scan calls for keys.
        calls = mock_cursor.execute.call_args_list
        insert_image_tags_calls = [
            c for c in calls if "INSERT INTO image_tags" in c[0][0]
        ]
        assert len(insert_image_tags_calls) == 2

    def test_search_images_query_construction(self, mock_db):
        db, _, mock_cursor = mock_db
        mock_cursor.fetchall.return_value = []

        db.search_images(
            group_name="GroupA",
            subgroup_name="SubB",
            tags=["tag1"],
            filename_pattern="cat",
            input_formats=["jpg", "png"],
        )

        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "i.group_name ILIKE %s" in query
        assert "i.subgroup_name ILIKE %s" in query
        assert "t.name IN (%s)" in query
        assert "i.filename ILIKE %s" in query
        assert "%.jpg" in params
        assert "%GroupA%" in params

    def test_update_image(self, mock_db):
        db, _, mock_cursor = mock_db

        db.update_image(image_id=1, group_name="New Group", subgroup_name="New Sub")

        # Logic:
        # 1. Update images table
        # 2. Since subgroup given, ensure subgroup linkage (calls add_subgroup)
        calls = mock_cursor.execute.call_args_list
        update_call = [c for c in calls if "UPDATE images SET" in c[0][0]]
        assert len(update_call) == 1
        assert "group_name = %s" in update_call[0][0][0]

    def test_reset_database(self, mock_db):
        db, _, mock_cursor = mock_db

        db.reset_database()

        # Should drop tables
        drops = [
            c for c in mock_cursor.execute.call_args_list if "DROP TABLE" in c[0][0]
        ]
        assert len(drops) >= 5

        # Should recreate tables (CREATE TABLE)
        creates = [
            c for c in mock_cursor.execute.call_args_list if "CREATE TABLE" in c[0][0]
        ]
        assert len(creates) >= 5
