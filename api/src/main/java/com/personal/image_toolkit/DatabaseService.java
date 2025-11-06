package com.personal.image_toolkit;

import com.pgvector.PGvector;
import io.agroal.api.AgroalDataSource; // Quarkus's connection pool
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Service class to handle all database operations.
 * This is the full Java re-implementation of PgvectorImageDatabase.py.
 *
 * @ApplicationScoped tells Quarkus to create one instance of this class.
 */
@ApplicationScoped
public class DatabaseService {

    @Inject
    AgroalDataSource dataSource; // Inject the managed datasource

    /**
     * Constructor: This is called once when the application starts.
     * We use it to register the PGvector type with the connection pool.
     */
    public DatabaseService() {
        try (Connection conn = getConnection()) {
            PGvector.addVectorType(conn);
            System.out.println("PGvector type added to connection.");
            // Note: In a production app, you'd also run _createTables() here.
        } catch (Exception e) {
            System.err.println("Failed to initialize database service or pgvector type");
            e.printStackTrace();
        }
    }

    /**
     * Helper to get a new database connection from the pool.
     */
    private Connection getConnection() throws SQLException {
        return dataSource.getConnection();
    }

    // --- Private Helper Methods ---

    private int getOrCreateTag(Connection conn, String tagName) throws SQLException {
        if (tagName == null || tagName.isBlank()) {
            throw new SQLException("Tag name cannot be empty.");
        }
        String sql = "INSERT INTO tags (name) VALUES (?) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id";
        try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, tagName.trim());
            ResultSet rs = pstmt.executeQuery();
            if (rs.next()) {
                return rs.getInt(1);
            }
            throw new SQLException("Failed to get or create tag.");
        }
    }

    private Map<String, Object> fetchImageDetails(int imageId) throws Exception {
        String sql = "SELECT * FROM images WHERE id = ?";
        try (Connection conn = getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {
            
            pstmt.setInt(1, imageId);
            ResultSet rs = pstmt.executeQuery();
            if (rs.next()) {
                Map<String, Object> data = new HashMap<>();
                data.put("id", rs.getInt("id"));
                data.put("file_path", rs.getString("file_path"));
                data.put("filename", rs.getString("filename"));
                data.put("group_name", rs.getString("group_name"));
                data.put("date_added", rs.getTimestamp("date_added"));
                data.put("width", rs.getInt("width"));
                data.put("height", rs.getInt("height"));
                // (Omit embedding from the JSON response)
                
                // Now get tags
                data.put("tags", getImageTags(conn, imageId));
                return data;
            }
        }
        return null; // Or throw new Exception("Image not found")
    }

    private List<String> getImageTags(Connection conn, int imageId) throws SQLException {
        List<String> tags = new ArrayList<>();
        String sql = "SELECT t.name FROM tags t JOIN image_tags it ON t.id = it.tag_id WHERE it.image_id = ?";
        try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setInt(1, imageId);
            ResultSet rs = pstmt.executeQuery();
            while (rs.next()) {
                tags.add(rs.getString("name"));
            }
        }
        return tags;
    }


    // --- Public API Methods (from PgvectorImageDatabase.py) ---

    public void addGroup(String groupName) throws Exception {
        if (groupName == null || groupName.isBlank()) {
            throw new IllegalArgumentException("Group name cannot be empty");
        }
        String sql = "INSERT INTO groups (name) VALUES (?) ON CONFLICT (name) DO NOTHING";
        try (Connection conn = getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, groupName.trim());
            pstmt.executeUpdate();
        }
    }

    public void addTag(String name, String type) throws Exception {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("Tag name cannot be empty");
        }
        String typeValue = (type != null && !type.isBlank()) ? type.trim() : null;
        String sql = "INSERT INTO tags (name, type) VALUES (?, ?) ON CONFLICT (name) DO UPDATE SET type = EXCLUDED.type";
        try (Connection conn = getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, name.trim());
            pstmt.setString(2, typeValue);
            pstmt.executeUpdate();
        }
    }

    public void deleteGroup(String name) throws Exception {
        String sql = "DELETE FROM groups WHERE name = ?";
        try (Connection conn = getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, name);
            pstmt.executeUpdate();
        }
    }

    public void deleteTag(String name) throws Exception {
        String sql = "DELETE FROM tags WHERE name = ?";
        try (Connection conn = getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, name);
            pstmt.executeUpdate();
        }
    }

    public void renameGroup(String oldName, String newName) throws Exception {
        if (oldName == null || newName == null || oldName.isBlank() || newName.isBlank() || oldName.equals(newName)) {
            throw new IllegalArgumentException("Invalid group names for rename.");
        }
        String sqlUpdateImages = "UPDATE images SET group_name = ? WHERE group_name = ?";
        String sqlUpdateGroups = "UPDATE groups SET name = ? WHERE name = ?";
        
        try (Connection conn = getConnection()) {
            conn.setAutoCommit(false); // Start transaction
            try (PreparedStatement pstmtImages = conn.prepareStatement(sqlUpdateImages);
                 PreparedStatement pstmtGroups = conn.prepareStatement(sqlUpdateGroups)) {
                
                pstmtImages.setString(1, newName);
                pstmtImages.setString(2, oldName);
                pstmtImages.executeUpdate();

                pstmtGroups.setString(1, newName);
                pstmtGroups.setString(2, oldName);
                pstmtGroups.executeUpdate();
                
                conn.commit(); // Commit transaction
            } catch (Exception e) {
                conn.rollback(); // Rollback on error
                throw e;
            } finally {
                conn.setAutoCommit(true); // Restore default
            }
        }
    }

    public void renameTag(String oldName, String newName) throws Exception {
        if (oldName == null || newName == null || oldName.isBlank() || newName.isBlank() || oldName.equals(newName)) {
            throw new IllegalArgumentException("Invalid tag names for rename.");
        }
        String sql = "UPDATE tags SET name = ? WHERE name = ?";
        try (Connection conn = getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, newName);
            pstmt.setString(2, oldName);
            pstmt.executeUpdate();
        }
    }

    public void updateTagType(String name, String newType) throws Exception {
        String typeValue = (newType != null && !newType.isBlank()) ? newType.trim() : null;
        String sql = "UPDATE tags SET type = ? WHERE name = ?";
        try (Connection conn = getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, typeValue);
            pstmt.setString(2, name);
            pstmt.executeUpdate();
        }
    }

    public List<Map<String, String>> getAllTagsWithTypes() throws Exception {
        List<Map<String, String>> tags = new ArrayList<>();
        String sql = "SELECT name, type FROM tags ORDER BY name";
        try (Connection conn = getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            while (rs.next()) {
                Map<String, String> tag = new HashMap<>();
                tag.put("name", rs.getString("name"));
                tag.put("type", rs.getString("type") != null ? rs.getString("type") : "");
                tags.add(tag);
            }
        }
        return tags;
    }

    public int addImage(String filePath, List<Float> embedding, String groupName, 
                        List<String> tags, Integer width, Integer height) throws Exception {
        
        String sql = "INSERT INTO images (file_path, filename, file_size, width, height, group_name, date_added, date_modified, embedding) " +
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) " +
                     "ON CONFLICT (file_path) DO UPDATE SET " +
                     "file_size = EXCLUDED.file_size, width = EXCLUDED.width, height = EXCLUDED.height, " +
                     "group_name = EXCLUDED.group_name, date_modified = ?, embedding = EXCLUDED.embedding " +
                     "RETURNING id";
        
        java.io.File file = new java.io.File(filePath);
        Timestamp now = Timestamp.valueOf(LocalDateTime.now());
        String group = (groupName != null && !groupName.isBlank()) ? groupName.trim() : null;

        if (group != null) {
            addGroup(group);
        }

        try (Connection conn = getConnection();
             PreparedStatement pstmt = conn.prepareStatement(sql)) {
            
            pstmt.setString(1, file.getAbsolutePath());
            pstmt.setString(2, file.getName());
            pstmt.setLong(3, file.length()); // Python code had 0, let's use real size
            pstmt.setObject(4, width);
            pstmt.setObject(5, height);
            pstmt.setString(6, group);
            pstmt.setTimestamp(7, now);
            pstmt.setTimestamp(8, now);
            pstmt.setObject(9, embedding != null ? new PGvector(embedding) : null);
            pstmt.setTimestamp(10, now); // For the ON CONFLICT update

            ResultSet rs = pstmt.executeQuery();
            if (rs.next()) {
                int imageId = rs.getInt(1);
                
                // Update tags if provided
                if (tags != null) {
                    // 1. Delete old tags
                    try (PreparedStatement delPstmt = conn.prepareStatement("DELETE FROM image_tags WHERE image_id = ?")) {
                        delPstmt.setInt(1, imageId);
                        delPstmt.executeUpdate();
                    }
                    // 2. Add new tags
                    String tagSql = "INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?) ON CONFLICT DO NOTHING";
                    try (PreparedStatement tagPstmt = conn.prepareStatement(tagSql)) {
                        for (String tagName : tags) {
                            int tagId = getOrCreateTag(conn, tagName);
                            tagPstmt.setInt(1, imageId);
                            tagPstmt.setInt(2, tagId);
                            tagPstmt.addBatch();
                        }
                        tagPstmt.executeBatch();
                    }
                }
                return imageId;
            }
            throw new SQLException("Creating/updating image failed, no ID obtained.");
        }
    }

    public Map<String, Object> getImageByPath(String filePath) throws Exception {
        String sql = "SELECT id FROM images WHERE file_path = ?";
        try (Connection conn = getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, filePath);
            ResultSet rs = pstmt.executeQuery();
            if (rs.next()) {
                return fetchImageDetails(rs.getInt("id"));
            }
        }
        return null;
    }

    public void updateImage(int imageId, String groupName, List<String> tags) throws Exception {
        Timestamp now = Timestamp.valueOf(LocalDateTime.now());
        String group = (groupName != null && !groupName.isBlank()) ? groupName.trim() : null;
        
        if (group != null) {
            addGroup(group);
        }

        try (Connection conn = getConnection()) {
            conn.setAutoCommit(false);
            
            // Update group_name
            if (groupName != null) {
                String sqlUpdateImg = "UPDATE images SET group_name = ?, date_modified = ? WHERE id = ?";
                try (PreparedStatement pstmt = conn.prepareStatement(sqlUpdateImg)) {
                    pstmt.setString(1, group);
                    pstmt.setTimestamp(2, now);
                    pstmt.setInt(3, imageId);
                    pstmt.executeUpdate();
                }
            }
            
            // Update tags
            if (tags != null) {
                // 1. Delete old tags
                try (PreparedStatement delPstmt = conn.prepareStatement("DELETE FROM image_tags WHERE image_id = ?")) {
                    delPstmt.setInt(1, imageId);
                    delPstmt.executeUpdate();
                }
                // 2. Add new tags
                String tagSql = "INSERT INTO image_tags (image_id, tag_id) VALUES (?, ?) ON CONFLICT DO NOTHING";
                try (PreparedStatement tagPstmt = conn.prepareStatement(tagSql)) {
                    for (String tagName : tags) {
                        int tagId = getOrCreateTag(conn, tagName);
                        tagPstmt.setInt(1, imageId);
                        tagPstmt.setInt(2, tagId);
                        tagPstmt.addBatch();
                    }
                    tagPstmt.executeBatch();
                }
            }
            conn.commit();
        } catch (Exception e) {
            // Can't auto-rollback with try-with-resources, but connection will close.
            // In a real app, you'd handle this more gracefully.
            throw e;
        }
    }

    public List<Map<String, Object>> searchImages(String groupName, List<String> tags, String filenamePattern, List<Float> queryVector, int limit) throws Exception {
        List<Map<String, Object>> results = new ArrayList<>();
        
        // --- Dynamic Query Building (like in Python) ---
        StringBuilder query = new StringBuilder("SELECT DISTINCT i.id FROM images i");
        List<Object> params = new ArrayList<>();
        int paramIndex = 1;

        if (tags != null && !tags.isEmpty()) {
            query.append(" JOIN image_tags it ON i.id = it.image_id JOIN tags t ON it.tag_id = t.id");
        }

        List<String> conditions = new ArrayList<>();
        
        if (tags != null && !tags.isEmpty()) {
            // Create placeholders (?, ?, ?)
            String tagPlaceholders = tags.stream().map(t -> "?").reduce((a, b) -> a + "," + b).orElse("");
            conditions.add("t.name IN (" + tagPlaceholders + ")");
            params.addAll(tags);
        }

        if (groupName != null && !groupName.isBlank()) {
            conditions.add("i.group_name ILIKE ?");
            params.add("%" + groupName + "%");
        }

        if (filenamePattern != null && !filenamePattern.isBlank()) {
            conditions.add("i.filename ILIKE ?");
            params.add("%" + filenamePattern + "%");
        }
        
        if (!conditions.isEmpty()) {
            query.append(" WHERE ").append(String.join(" AND ", conditions));
        }

        if (queryVector != null && !queryVector.isEmpty()) {
            query.append(" ORDER BY i.embedding <-> ? ASC NULLS LAST");
            params.add(new PGvector(queryVector));
        } else {
            query.append(" ORDER BY i.date_added DESC");
        }

        query.append(" LIMIT ?");
        params.add(limit);
        // --- End of Query Building ---

        // This query just gets the IDs. We then fetch full details.
        // This avoids complex JOINs and makes it easier to get tags.
        List<Integer> imageIds = new ArrayList<>();
        try (Connection conn = getConnection();
             PreparedStatement pstmt = conn.prepareStatement(query.toString())) {
            
            for (int i = 0; i < params.size(); i++) {
                pstmt.setObject(i + 1, params.get(i));
            }
            
            ResultSet rs = pstmt.executeQuery();
            while (rs.next()) {
                imageIds.add(rs.getInt("id"));
            }
        }
        
        // Now fetch full details for each ID
        for (int id : imageIds) {
            Map<String, Object> details = fetchImageDetails(id);
            if (details != null) {
                results.add(details);
            }
        }
        return results;
    }

    public List<String> getAllTags() throws Exception {
        List<String> tags = new ArrayList<>();
        String sql = "SELECT name FROM tags ORDER BY name";
        try (Connection conn = getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            while (rs.next()) {
                tags.add(rs.getString("name"));
            }
        }
        return tags;
    }

    public List<String> getAllGroups() throws Exception {
        List<String> groups = new ArrayList<>();
        String sql = "SELECT name FROM groups ORDER BY name";
        try (Connection conn = getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            while (rs.next()) {
                groups.add(rs.getString("name"));
            }
        }
        return groups;
    }

    public void deleteImage(int imageId) throws Exception {
        String sql = "DELETE FROM images WHERE id = ?";
        try (Connection conn = getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setInt(1, imageId);
            pstmt.executeUpdate();
        }
    }

    public Map<String, Long> getStatistics() throws Exception {
        Map<String, Long> stats = new HashMap<>();
        try (Connection conn = getConnection(); Statement stmt = conn.createStatement()) {
            ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM images");
            if (rs.next()) stats.put("total_images", rs.getLong(1));
            
            rs = stmt.executeQuery("SELECT COUNT(*) FROM tags");
            if (rs.next()) stats.put("total_tags", rs.getLong(1));
            
            rs = stmt.executeQuery("SELECT COUNT(*) FROM groups");
            if (rs.next()) stats.put("total_groups", rs.getLong(1));
        }
        return stats;
    }
}