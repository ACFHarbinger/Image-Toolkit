package com.example.image_toolkit;

import java.time.Instant;

/**
 * A simple record-like class to hold metadata for a file,
 * used for comparison during synchronization.
 */
public class FileMetadata {
    private final String name;
    private final String id;            // Remote ID (if it exists)
    private final String path;          // Local absolute path
    private final Instant modificationTime;
    private final boolean isFolder;

    // Constructor for Local Files
    public FileMetadata(String name, String path, Instant modificationTime) {
        this(name, null, path, modificationTime, false);
    }

    // Constructor for Remote Files (or general use)
    public FileMetadata(String name, String id, String path, Instant modificationTime, boolean isFolder) {
        this.name = name;
        this.id = id;
        this.path = path;
        this.modificationTime = modificationTime;
        this.isFolder = isFolder;
    }

    public String getName() { return name; }
    public String getId() { return id; }
    public String getPath() { return path; }
    public Instant getModificationTime() { return modificationTime; }
    public boolean isFolder() { return isFolder; }
    
    @Override
    public String toString() {
        return "FileMetadata{" +
                "name='" + name + '\'' +
                ", id='" + id + '\'' +
                ", mTime=" + modificationTime +
                ", isFolder=" + isFolder +
                '}';
    }
}