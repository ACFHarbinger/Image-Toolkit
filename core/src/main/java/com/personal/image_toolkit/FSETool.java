package com.personal.image_toolkit.tools;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.Collection;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * A comprehensive tool for managing file system entries, including path
 * resolution, directory creation, file searching, and deletion.
 *
 * Re-implementation of FSETool.py
 */
public final class FSETool {

    /**
     * Private constructor to prevent instantiation of this utility class.
     */
    private FSETool() {}

    // --- Utility Methods (replacing Python decorators) ---

    /**
     * Creates the parent directory for a given file path if it doesn't exist.
     * @param filePath The path to the file whose parent directory should be created.
     * @throws IOException If an I/O error occurs.
     */
    public static void createDirectoryForFile(String filePath) throws IOException {
        if (filePath == null || filePath.isEmpty()) {
            return;
        }
        Path parentDir = Paths.get(filePath).getParent();
        if (parentDir != null && !Files.exists(parentDir)) {
            Files.createDirectories(parentDir);
            System.out.println("Created directory: '" + parentDir.toAbsolutePath() + "'.");
        }
    }

    /**
     * Creates a directory if it doesn't exist.
     * @param dirPath The path of the directory to create.
     * @throws IOException If an I/O error occurs.
     */
    public static void createDirectory(String dirPath) throws IOException {
        if (dirPath == null || dirPath.isEmpty()) {
            return;
        }
        Path path = Paths.get(dirPath);
        if (!Files.exists(path)) {
            Files.createDirectories(path);
            System.out.println("Created directory: '" + path.toAbsolutePath() + "'.");
        }
    }

    /**
     * Resolves a string path to an absolute, normalized Path object.
     * @param path The path string (can be relative or absolute).
     * @return A resolved, absolute Path.
     */
    public static Path resolvePath(String path) {
        return Paths.get(path).toAbsolutePath().normalize();
    }

    /**
     * Check if parentPath contains childPath.
     * @param parentPath The potential parent path.
     * @param childPath The potential child path.
     * @return True if childPath is within parentPath or equal to it.
     */
    public static boolean pathContains(String parentPath, String childPath) {
        try {
            Path parent = resolvePath(parentPath);
            Path child = resolvePath(childPath);
            return child.startsWith(parent);
        } catch (Exception e) {
            return false;
        }
    }

    // --- Core File System Methods ---

    /**
     * Recursively delete files with specified extensions in a directory.
     * @param directory The absolute path to the starting directory.
     * @param extensions A collection of extensions (e.g., ".txt", ".jpg").
     * @throws IOException If an I/O error occurs.
     */
    public static void deleteFilesByExtensions(String directory, Collection<String> extensions) throws IOException {
        Path startPath = resolvePath(directory);
        if (!Files.isDirectory(startPath)) {
            System.out.println("Not a directory. Skipping: " + directory);
            return;
        }

        // Ensure extensions start with a dot
        Set<String> dotExtensions = extensions.stream()
                .map(ext -> ext.startsWith(".") ? ext : "." + ext)
                .collect(Collectors.toSet());

        try (Stream<Path> stream = Files.walk(startPath)) {
            stream.filter(Files::isRegularFile)
                  .filter(file -> {
                      String fileName = file.getFileName().toString();
                      int lastDot = fileName.lastIndexOf('.');
                      return lastDot != -1 && dotExtensions.contains(fileName.substring(lastDot));
                  })
                  .forEach(file -> {
                      try {
                          Files.delete(file);
                          System.out.println("Deleted: " + file);
                      } catch (IOException e) {
                          System.err.println("ERROR: Could not delete file " + file + ". Reason: " + e.getMessage());
                      }
                  });
        }
    }

    /**
     * Deletes a file or recursively deletes a directory.
     * @param pathToDelete The absolute path to the file or directory.
     * @throws IOException If an I/O error occurs.
     */
    public static void deletePath(String pathToDelete) throws IOException {
        Path path = resolvePath(pathToDelete);

        if (!Files.exists(path)) {
            System.out.println("WARNING: specified path does not exist - did not delete '" + path + "'.");
            return;
        }

        if (Files.isDirectory(path)) {
            Files.walkFileTree(path, new SimpleFileVisitor<Path>() {
                @Override
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                    Files.delete(file);
                    return FileVisitResult.CONTINUE;
                }

                @Override
                public FileVisitResult postVisitDirectory(Path dir, IOException exc) throws IOException {
                    Files.delete(dir);
                    System.out.println("Deleted directory: '" + dir + "'.");
                    return FileVisitResult.CONTINUE;
                }
            });
        } else {
            Files.delete(path);
            System.out.println("Deleted file: '" + path + "'.");
        }
    }

    /**
     * Get all files with a specific extension in a directory.
     * @param directory The path to the directory.
     * @param extension The file extension (e.g., "txt", ".jpeg").
     * @param recursive Whether to search subdirectories.
     * @return A list of absolute file paths (strings).
     * @throws IOException If an I/O error occurs.
     */
    public static List<String> getFilesByExtension(String directory, String extension, boolean recursive) throws IOException {
        Path startPath = resolvePath(directory);
        if (!Files.isDirectory(startPath)) {
            return List.of();
        }

        String dotExtension = extension.startsWith(".") ? extension : "." + extension;
        int maxDepth = recursive ? Integer.MAX_VALUE : 1;

        try (Stream<Path> stream = Files.walk(startPath, maxDepth)) {
            return stream
                    .filter(Files::isRegularFile)
                    .filter(file -> file.getFileName().toString().toLowerCase().endsWith(dotExtension))
                    .map(path -> path.toAbsolutePath().toString())
                    .collect(Collectors.toList());
        }
    }
}