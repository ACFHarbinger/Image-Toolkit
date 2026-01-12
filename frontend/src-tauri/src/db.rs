use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::postgres::{PgPool, PgPoolOptions};
use sqlx::{FromRow, Row};
use std::sync::Arc;

/// Database connection state managed by Tauri
pub struct Db {
    pool: Arc<PgPool>,
}

impl Db {
    /// Initialize database connection from environment variables
    pub async fn new(database_url: &str) -> Result<Self> {
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .connect(database_url)
            .await
            .context("Failed to connect to PostgreSQL database")?;

        // Run migrations if available
        sqlx::migrate!("./migrations")
            .run(&pool)
            .await
            .context("Failed to run database migrations")?;

        Ok(Self {
            pool: Arc::new(pool),
        })
    }

    /// Initialize database and ensure pgvector extension exists
    pub async fn init_schema(&self) -> Result<()> {
        sqlx::query("CREATE EXTENSION IF NOT EXISTS vector")
            .execute(&*self.pool)
            .await
            .context("Failed to create pgvector extension")?;

        Ok(())
    }

    pub fn pool(&self) -> &PgPool {
        &self.pool
    }
}

// ===== Database Models =====

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct ImageRecord {
    pub id: i32,
    pub file_path: String,
    pub filename: String,
    pub file_size: Option<i64>,
    pub width: Option<i32>,
    pub height: Option<i32>,
    pub group_name: Option<String>,
    pub subgroup_name: Option<String>,
    pub date_added: DateTime<Utc>,
    pub date_modified: Option<DateTime<Utc>>,
    #[sqlx(skip)]
    pub tags: Vec<String>,
    #[sqlx(skip)]
    pub distance: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchQuery {
    pub group_name: Option<String>,
    pub subgroup_name: Option<String>,
    pub tags: Option<Vec<String>>,
    pub filename_pattern: Option<String>,
    pub input_formats: Option<Vec<String>>,
    pub limit: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Tag {
    pub id: i32,
    pub name: String,
    #[sqlx(rename = "type")]
    pub tag_type: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, FromRow)]
pub struct Group {
    pub id: i32,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatabaseStats {
    pub total_images: i64,
    pub total_tags: i64,
    pub total_groups: i64,
    pub total_subgroups: i64,
}

// ===== Database Operations =====

impl Db {
    /// Search for images based on various filters
    pub async fn search_images(&self, query: SearchQuery) -> Result<Vec<ImageRecord>> {
        let limit = query.limit.unwrap_or(100).min(1000); // Cap at 1000

        let mut sql = String::from("SELECT DISTINCT i.* FROM images i");
        let mut conditions = Vec::new();
        let mut param_count = 0;

        // Join with tags if needed
        if query.tags.is_some() {
            sql.push_str(" JOIN image_tags it ON i.id = it.image_id JOIN tags t ON it.tag_id = t.id");
        }

        // Build WHERE clauses
        if let Some(group) = &query.group_name {
            param_count += 1;
            conditions.push(format!("i.group_name ILIKE ${}", param_count));
        }

        if let Some(subgroup) = &query.subgroup_name {
            param_count += 1;
            conditions.push(format!("i.subgroup_name ILIKE ${}", param_count));
        }

        if let Some(pattern) = &query.filename_pattern {
            param_count += 1;
            conditions.push(format!("i.filename ILIKE ${}", param_count));
        }

        if let Some(tags) = &query.tags {
            if !tags.is_empty() {
                let placeholders: Vec<String> = (0..tags.len())
                    .map(|i| {
                        param_count += 1;
                        format!("${}", param_count)
                    })
                    .collect();
                conditions.push(format!("t.name IN ({})", placeholders.join(", ")));
            }
        }

        if let Some(formats) = &query.input_formats {
            if !formats.is_empty() {
                let ext_conditions: Vec<String> = formats
                    .iter()
                    .map(|_| {
                        param_count += 1;
                        format!("i.filename ILIKE ${}", param_count)
                    })
                    .collect();
                conditions.push(format!("({})", ext_conditions.join(" OR ")));
            }
        }

        if !conditions.is_empty() {
            sql.push_str(" WHERE ");
            sql.push_str(&conditions.join(" AND "));
        }

        sql.push_str(" ORDER BY i.date_added DESC");
        sql.push_str(&format!(" LIMIT {}", limit));

        // Build query with parameters
        let mut query_builder = sqlx::query_as::<_, ImageRecord>(&sql);

        if let Some(group) = &query.group_name {
            query_builder = query_builder.bind(format!("%{}%", group));
        }
        if let Some(subgroup) = &query.subgroup_name {
            query_builder = query_builder.bind(format!("%{}%", subgroup));
        }
        if let Some(pattern) = &query.filename_pattern {
            query_builder = query_builder.bind(format!("%{}%", pattern));
        }
        if let Some(tags) = &query.tags {
            for tag in tags {
                query_builder = query_builder.bind(tag);
            }
        }
        if let Some(formats) = &query.input_formats {
            for format in formats {
                let clean_ext = format.trim_start_matches('.');
                query_builder = query_builder.bind(format!("%.{}", clean_ext));
            }
        }

        let mut images = query_builder.fetch_all(&*self.pool).await?;

        // Fetch tags for each image
        for image in &mut images {
            image.tags = self.get_image_tags(image.id).await?;
        }

        Ok(images)
    }

    /// Get all tags for a specific image
    pub async fn get_image_tags(&self, image_id: i32) -> Result<Vec<String>> {
        let tags = sqlx::query_scalar::<_, String>(
            r#"
            SELECT t.name FROM tags t
            JOIN image_tags it ON t.id = it.tag_id
            WHERE it.image_id = $1
            ORDER BY t.name
            "#,
        )
        .bind(image_id)
        .fetch_all(&*self.pool)
        .await?;

        Ok(tags)
    }

    /// Get all unique tags from the database
    pub async fn get_all_tags(&self) -> Result<Vec<String>> {
        let tags = sqlx::query_scalar::<_, String>("SELECT name FROM tags ORDER BY name")
            .fetch_all(&*self.pool)
            .await?;

        Ok(tags)
    }

    /// Get all groups
    pub async fn get_all_groups(&self) -> Result<Vec<String>> {
        let groups = sqlx::query_scalar::<_, String>("SELECT name FROM groups ORDER BY name")
            .fetch_all(&*self.pool)
            .await?;

        Ok(groups)
    }

    /// Get all subgroups for a specific group
    pub async fn get_subgroups_for_group(&self, group_name: &str) -> Result<Vec<String>> {
        let subgroups = sqlx::query_scalar::<_, String>(
            r#"
            SELECT s.name FROM subgroups s
            JOIN groups g ON s.group_id = g.id
            WHERE g.name = $1
            ORDER BY s.name
            "#,
        )
        .bind(group_name)
        .fetch_all(&*self.pool)
        .await?;

        Ok(subgroups)
    }

    /// Add a new image to the database
    pub async fn add_image(
        &self,
        file_path: &str,
        filename: &str,
        width: Option<i32>,
        height: Option<i32>,
        group_name: Option<&str>,
        subgroup_name: Option<&str>,
        tags: Option<Vec<String>>,
    ) -> Result<i32> {
        // Ensure group exists if provided
        if let Some(group) = group_name {
            self.ensure_group_exists(group).await?;
        }

        // Ensure subgroup exists if provided
        if let (Some(group), Some(subgroup)) = (group_name, subgroup_name) {
            self.ensure_subgroup_exists(subgroup, group).await?;
        }

        let now = Utc::now();

        let image_id = sqlx::query_scalar::<_, i32>(
            r#"
            INSERT INTO images
            (file_path, filename, file_size, width, height, group_name, subgroup_name, date_added, date_modified)
            VALUES ($1, $2, 0, $3, $4, $5, $6, $7, $7)
            ON CONFLICT (file_path) DO UPDATE SET
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                group_name = EXCLUDED.group_name,
                subgroup_name = EXCLUDED.subgroup_name,
                date_modified = $7
            RETURNING id
            "#,
        )
        .bind(file_path)
        .bind(filename)
        .bind(width)
        .bind(height)
        .bind(group_name)
        .bind(subgroup_name)
        .bind(now)
        .fetch_one(&*self.pool)
        .await?;

        // Add tags if provided
        if let Some(tag_list) = tags {
            self.set_image_tags(image_id, tag_list).await?;
        }

        Ok(image_id)
    }

    /// Set tags for an image (replaces existing tags)
    pub async fn set_image_tags(&self, image_id: i32, tags: Vec<String>) -> Result<()> {
        // Delete existing tags
        sqlx::query("DELETE FROM image_tags WHERE image_id = $1")
            .bind(image_id)
            .execute(&*self.pool)
            .await?;

        // Add new tags
        for tag_name in tags {
            let tag_id = self.get_or_create_tag(&tag_name).await?;
            sqlx::query(
                "INSERT INTO image_tags (image_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            )
            .bind(image_id)
            .bind(tag_id)
            .execute(&*self.pool)
            .await?;
        }

        Ok(())
    }

    /// Get or create a tag
    async fn get_or_create_tag(&self, name: &str) -> Result<i32> {
        let tag_id = sqlx::query_scalar::<_, i32>(
            r#"
            INSERT INTO tags (name) VALUES ($1)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            "#,
        )
        .bind(name)
        .fetch_one(&*self.pool)
        .await?;

        Ok(tag_id)
    }

    /// Ensure a group exists
    async fn ensure_group_exists(&self, name: &str) -> Result<()> {
        sqlx::query("INSERT INTO groups (name) VALUES ($1) ON CONFLICT (name) DO NOTHING")
            .bind(name)
            .execute(&*self.pool)
            .await?;

        Ok(())
    }

    /// Ensure a subgroup exists for a given group
    async fn ensure_subgroup_exists(&self, subgroup_name: &str, group_name: &str) -> Result<()> {
        // Get group ID
        let group_id = sqlx::query_scalar::<_, i32>("SELECT id FROM groups WHERE name = $1")
            .bind(group_name)
            .fetch_one(&*self.pool)
            .await?;

        sqlx::query(
            "INSERT INTO subgroups (name, group_id) VALUES ($1, $2) ON CONFLICT (name, group_id) DO NOTHING",
        )
        .bind(subgroup_name)
        .bind(group_id)
        .execute(&*self.pool)
        .await?;

        Ok(())
    }

    /// Delete an image by ID
    pub async fn delete_image(&self, image_id: i32) -> Result<()> {
        sqlx::query("DELETE FROM images WHERE id = $1")
            .bind(image_id)
            .execute(&*self.pool)
            .await?;

        Ok(())
    }

    /// Get database statistics
    pub async fn get_statistics(&self) -> Result<DatabaseStats> {
        let total_images = sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM images")
            .fetch_one(&*self.pool)
            .await?;

        let total_tags = sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM tags")
            .fetch_one(&*self.pool)
            .await?;

        let total_groups = sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM groups")
            .fetch_one(&*self.pool)
            .await?;

        let total_subgroups = sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM subgroups")
            .fetch_one(&*self.pool)
            .await?;

        Ok(DatabaseStats {
            total_images,
            total_tags,
            total_groups,
            total_subgroups,
        })
    }

    /// Test database connection
    pub async fn test_connection(&self) -> Result<bool> {
        sqlx::query("SELECT 1")
            .execute(&*self.pool)
            .await
            .context("Database connection test failed")?;

        Ok(true)
    }
}
