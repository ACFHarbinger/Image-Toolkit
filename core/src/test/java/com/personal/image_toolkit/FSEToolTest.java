package com.personal.image_toolkit.tools;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for FSETool utility class.
 */
class FSEToolTest {

    @TempDir
    Path tempDir;

    @Test
    void createDirectoryForFile_shouldCreateParentDirectory() throws IOException {
        Path newFile = tempDir.resolve("subfolder/new_file.txt");
        assertThat(newFile.getParent()).doesNotExist();

        FSETool.createDirectoryForFile(newFile.toString());

        assertThat(newFile.getParent()).exists().isDirectory();
    }

    @Test
    void createDirectory_shouldCreateDirectory() throws IOException {
        Path newDir = tempDir.resolve("new_dir");
        assertThat(newDir).doesNotExist();

        FSETool.createDirectory(newDir.toString());

        assertThat(newDir).exists().isDirectory();
    }

    @Test
    void resolvePath_shouldReturnAbsolutePath() {
        Path relative = Paths.get("src", "..", "pom.xml"); // relative path
        Path absolute = FSETool.resolvePath(relative.toString());

        assertThat(absolute).isAbsolute().endsWith(Paths.get("pom.xml"));
    }

    @Test
    void pathContains_shouldReturnCorrectBoolean() {
        Path child = tempDir.resolve("sub/file.txt");
        Path sibling = tempDir.resolve("other/file.txt");

        assertThat(FSETool.pathContains(tempDir.toString(), child.toString())).isTrue();
        assertThat(FSETool.pathContains(tempDir.toString(), tempDir.toString())).isTrue();
        assertThat(FSETool.pathContains(child.toString(), tempDir.toString())).isFalse();
        assertThat(FSETool.pathContains(sibling.getParent().toString(), child.toString())).isFalse();
    }

    @Test
    void deleteFilesByExtensions_shouldDeleteOnlyMatchingFiles() throws IOException {
        Path file1 = Files.createFile(tempDir.resolve("a.txt"));
        Path file2 = Files.createFile(tempDir.resolve("b.jpg"));
        Files.createDirectories(tempDir.resolve("sub"));
        Path file3 = Files.createFile(tempDir.resolve("sub/c.txt"));

        FSETool.deleteFilesByExtensions(tempDir.toString(), List.of(".txt"));

        assertThat(file1).doesNotExist();
        assertThat(file3).doesNotExist();
        assertThat(file2).exists();
    }

    @Test
    void deletePath_shouldDeleteFile() throws IOException {
        Path file = Files.createFile(tempDir.resolve("file_to_delete.txt"));
        assertThat(file).exists();

        FSETool.deletePath(file.toString());

        assertThat(file).doesNotExist();
    }

    @Test
    void deletePath_shouldDeleteDirectoryRecursively() throws IOException {
        Path dir = Files.createDirectories(tempDir.resolve("dir_to_delete"));
        Files.createFile(dir.resolve("file.txt"));
        Files.createDirectories(dir.resolve("sub"));
        Files.createFile(dir.resolve("sub/another.txt"));

        assertThat(dir).exists();
        
        FSETool.deletePath(dir.toString());

        assertThat(dir).doesNotExist();
    }

    @Test
    void getFilesByExtension_shouldFindFiles() throws IOException {
        Files.createFile(tempDir.resolve("a.jpg"));
        Files.createFile(tempDir.resolve("b.png"));
        Files.createDirectories(tempDir.resolve("sub"));
        Path fileC = Files.createFile(tempDir.resolve("sub/c.jpg"));
        Path fileD = Files.createFile(tempDir.resolve("sub/d.JPG")); // Test case insensitivity

        // Test non-recursive
        List<String> nonRecursive = FSETool.getFilesByExtension(tempDir.toString(), "jpg", false);
        assertThat(nonRecursive).hasSize(1).contains(tempDir.resolve("a.jpg").toAbsolutePath().toString());
        
        // Test recursive
        List<String> recursive = FSETool.getFilesByExtension(tempDir.toString(), "jpg", true);
        assertThat(recursive)
                .hasSize(3) // a.jpg, c.jpg, d.JPG
                .contains(
                        tempDir.resolve("a.jpg").toAbsolutePath().toString(),
                        fileC.toAbsolutePath().toString(),
                        fileD.toAbsolutePath().toString()
                );
        
        // Test dot prefix
        List<String> pngs = FSETool.getFilesByExtension(tempDir.toString(), ".png", true);
        assertThat(pngs).hasSize(1).contains(tempDir.resolve("b.png").toAbsolutePath().toString());
    }
}