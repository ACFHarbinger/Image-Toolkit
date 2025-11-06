import os
import psycopg2
import psycopg2.extras # Import extras for DictCursor
import numpy as np

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv


class PgvectorImageDatabase:
    def __init__(self,
                 embed_dim: int = 128,
                 db_name: str = None,
                 db_user: str = None,
                 db_password: str = None,
                 db_host: str = None,
                 db_port: str = None,
                 env_path: str = 'env/vars.env'):
        """Initialize the PostgreSQL database connection and set up the schema."""
        self.conn = None
        self.embedding_dim = embed_dim
        load_dotenv(dotenv_path=env_path)
        self.conn_params = {
            'dbname': os.getenv("DB_NAME") if db_name is None else db_name,
            'user': os.getenv("DB_USER") if db_user is None else db_user,
            'password': os.getenv("DB_PASSWORD") if db_password is None else db_password,
            'host': os.getenv("DB_HOST") if db_host is None else db_host,
            'port': os.getenv("DB_PORT") if db_port is None else db_port
        }
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establishes the database connection."""
        try:
            self.conn = psycopg2.connect(**self.conn_params)
            self.conn.autocommit = True
        except psycopg2.OperationalError as e:
            print(f"Error connecting to database: {e}")
            print("\n--- ERROR: DATABASE CONNECTION FAILED ---")
            print("Please ensure PostgreSQL is running and connection details are correct.")
            self.conn = None
            exit(1)


    def _create_tables(self):
        """Create the database tables and pgvector extension if they don't exist."""
        if not self.conn:
            return

        with self.conn.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS images (
                        id SERIAL PRIMARY KEY,
                        file_path TEXT UNIQUE NOT NULL,
                        filename TEXT NOT NULL,
                        file_size BIGINT,
                        width INTEGER,
                        height INTEGER,
                        group_name TEXT, 
                        date_added TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                        date_modified TIMESTAMP WITHOUT TIME ZONE,
                        embedding vector({self.embedding_dim}) 
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS groups (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tags (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) UNIQUE NOT NULL,
                        type VARCHAR(255) 
                    )
                """)
                
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS image_tags (
                        image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
                        tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                        PRIMARY KEY (image_id, tag_id)
                    )
                """)

                cur.execute("CREATE INDEX IF NOT EXISTS idx_images_group ON images(group_name)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_images_path ON images(file_path)")
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_images_embedding ON images USING hnsw (embedding vector_l2_ops) WHERE embedding IS NOT NULL;
                """)
            
            except Exception as e:
                raise Exception(f"Error during table creation: {e}")
            finally:
                self.conn.commit()


    def _get_or_create_entity(self, table: str, name: str) -> int:
        """Generic function to get ID or create a new row using ON CONFLICT."""
        sql = f"""
            INSERT INTO {table} (name) VALUES (%s)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (name,))
            return cur.fetchone()[0]

    def _get_or_create_tag(self, name: str) -> int:
        return self._get_or_create_entity('tags', name)
    
    def add_group(self, name: str):
        """
        Adds a new group name to the 'groups' table.
        """
        if not name or not name.strip():
            raise ValueError("Group name cannot be empty")
            
        sql = """
            INSERT INTO groups (name) VALUES (%s)
            ON CONFLICT (name) DO NOTHING;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (name.strip(),))

    def add_tag(self, name: str, type: Optional[str] = None):
        """
        Adds a new tag or updates the type of an existing tag.
        """
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty")
            
        type_value = type if type and type.strip() else None
        
        sql = """
            INSERT INTO tags (name, type) VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET
                type = EXCLUDED.type;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (name.strip(), type_value))

    def delete_group(self, name: str):
        """Deletes a group from the 'groups' table."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM groups WHERE name = %s", (name,))

    def delete_tag(self, name: str):
        """Deletes a tag from the 'tags' table. This will cascade to image_tags."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM tags WHERE name = %s", (name,))

    # --- NEW METHOD: Rename Group ---
    def rename_group(self, old_name: str, new_name: str):
        """Renames a group. This is a transaction that updates both 'groups' and 'images' tables."""
        if not old_name or not new_name or not new_name.strip():
            raise ValueError("Group names cannot be empty")
        
        if old_name == new_name:
            return # Nothing to do

        # Must run as a transaction
        self.conn.autocommit = False
        try:
            with self.conn.cursor() as cur:
                # 1. Update all references in the 'images' table
                cur.execute(
                    "UPDATE images SET group_name = %s WHERE group_name = %s",
                    (new_name, old_name)
                )
                # 2. Update the 'groups' table
                cur.execute(
                    "UPDATE groups SET name = %s WHERE name = %s",
                    (new_name, old_name)
                )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e # Re-raise the exception (e.g., UniqueViolation)
        finally:
            self.conn.autocommit = True # Restore default behavior

    # --- NEW METHOD: Rename Tag ---
    def rename_tag(self, old_name: str, new_name: str):
        """Renames a tag in the 'tags' table."""
        if not old_name or not new_name or not new_name.strip():
            raise ValueError("Tag names cannot be empty")

        if old_name == new_name:
            return
            
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE tags SET name = %s WHERE name = %s",
                (new_name, old_name)
            )

    # --- NEW METHOD: Update Tag Type ---
    def update_tag_type(self, name: str, new_type: str):
        """Updates the 'type' of an existing tag."""
        type_value = new_type if new_type and new_type.strip() else None
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE tags SET type = %s WHERE name = %s",
                (type_value, name)
            )
            
    def get_all_tags_with_types(self) -> List[Dict[str, str]]:
        """
        Gets a list of all tags and their types.
        """
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT name, type FROM tags ORDER BY name")
            return [{'name': row['name'], 'type': row['type'] or ''} for row in cur.fetchall()]

    
    def add_image(self, 
                  file_path: str, 
                  embedding: Optional[List[float]] = None,
                  group_name: Optional[str] = None,
                  tags: Optional[List[str]] = None,
                  width: Optional[int] = None,
                  height: Optional[int] = None) -> int:
        """Add an image and its vector embedding (optional) to the database."""
        path = Path(file_path)
        
        file_size = 0
        filename = path.name
        date_added = datetime.now()
        embedding_value = embedding if embedding is not None else None
        
        if group_name and group_name.strip():
            self.add_group(group_name)

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO images 
                    (file_path, filename, file_size, width, height, group_name, date_added, date_modified, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (file_path) DO UPDATE SET
                        file_size = EXCLUDED.file_size, 
                        width = EXCLUDED.width,
                        height = EXCLUDED.height,
                        group_name = EXCLUDED.group_name,
                        date_modified = %s,
                        embedding = EXCLUDED.embedding
                    RETURNING id
                """, (
                    str(path.absolute()), filename, file_size, width, height, group_name,
                    date_added, date_added, embedding_value, date_added
                ))
                
                image_id = cur.fetchone()[0]
                
                if tags is not None:
                    cur.execute("DELETE FROM image_tags WHERE image_id = %s", (image_id,))
                    for tag_name in tags:
                        tag_id = self._get_or_create_tag(tag_name)
                        cur.execute(
                            "INSERT INTO image_tags (image_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", 
                            (image_id, tag_id)
                        )
                
                return image_id
        except Exception as e:
            raise Exception(f"Error adding image: {e}")
    
    
    def _fetch_one_image_details(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Helper to fetch a single image's details and tags."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM images WHERE id = %s", (image_id,))
            row = cur.fetchone()
            
            if not row:
                return None
            
            image_data = dict(row)
            image_data.pop('embedding', None)
            image_data['tags'] = self.get_image_tags(image_id)
            return image_data
    
    def get_image_tags(self, image_id: int) -> List[str]:
        """Get all tags for an image."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT t.name FROM tags t
                JOIN image_tags it ON t.id = it.tag_id
                WHERE it.image_id = %s
            """, (image_id,))
            return [row[0] for row in cur.fetchall()]
    
    def get_image_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get image data by file path."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM images WHERE file_path = %s", (file_path,))
            row = cur.fetchone()
            if row:
                return self._fetch_one_image_details(row[0])
            return None

    def update_image(self, image_id: int, group_name: Optional[str] = None,
                         tags: Optional[List[str]] = None):
        """Update image metadata."""
        date_modified = datetime.now()
        
        if group_name and group_name.strip():
            self.add_group(group_name)

        with self.conn.cursor() as cur:
            if group_name is not None:
                cur.execute(
                    "UPDATE images SET group_name = %s, date_modified = %s WHERE id = %s",
                    (group_name, date_modified, image_id)
                )
            
            if tags is not None:
                cur.execute("DELETE FROM image_tags WHERE image_id = %s", (image_id,))
                for tag_name in tags:
                    tag_id = self._get_or_create_tag(tag_name)
                    cur.execute(
                        "INSERT INTO image_tags (image_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", 
                        (image_id, tag_id)
                    )
    
    
    def search_images(self, 
                      group_name: Optional[str] = None,
                      tags: Optional[List[str]] = None,
                      filename_pattern: Optional[str] = None,
                      query_vector: Optional[List[float]] = None,
                      limit: int = 10) -> List[Dict[str, Any]]:
        
        base_query_select = "SELECT DISTINCT i.*"
        
        if query_vector:
            vector_str = str(query_vector).replace('[', '{').replace(']', '}')
            base_query_select += f", i.embedding <-> '{vector_str}' AS distance"

        query = base_query_select + " FROM images i"
        conditions = []
        params = []
            
        if tags:
            query += " JOIN image_tags it ON i.id = it.image_id JOIN tags t ON it.tag_id = t.id"
            tag_placeholders = ','.join(['%s'] * len(tags))
            conditions.append(f"t.name IN ({tag_placeholders})")
            params.extend(tags)
            
        if group_name:
            conditions.append("i.group_name ILIKE %s")
            params.append(f"%{group_name}%")
            
        if filename_pattern:
            conditions.append("i.filename ILIKE %s")
            params.append(f"%{filename_pattern}%")
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        if query_vector:
            query += " ORDER BY distance ASC NULLS LAST"
        else:
            query += " ORDER BY i.date_added DESC"

        query += f" LIMIT {limit}"
        
        results = []
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
                for row in rows:
                    image_id = row['id']
                    image_data = dict(row)
                    image_data.pop('embedding', None)
                    image_data['tags'] = self.get_image_tags(image_id)
                    results.append(image_data)
        except Exception as e:
            raise Exception(f"Error during search: {e}")
        
        return results
    
    
    def get_all_tags(self) -> List[str]:
        """Get list of all tags in database."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT name FROM tags ORDER BY name")
            return [row[0] for row in cur.fetchall()]
    
    def get_all_groups(self) -> List[str]:
        """
        Get list of all group names from the dedicated 'groups' table.
        """
        with self.conn.cursor() as cur:
            cur.execute("SELECT name FROM groups ORDER BY name")
            return [row[0] for row in cur.fetchall()]
    
    def delete_image(self, image_id: int):
        """Delete an image from the database."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM images WHERE id = %s", (image_id,))
    
    def get_statistics(self) -> Dict[str, int]:
        """Get database statistics."""
        stats = {}
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM images")
            stats['total_images'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM tags")
            stats['total_tags'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM groups")
            stats['total_groups'] = cur.fetchone()[0]
            
        return stats
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
