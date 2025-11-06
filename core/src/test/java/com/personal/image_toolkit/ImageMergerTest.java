package com.personal.image_toolkit.tools;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.awt.Color;
import java.awt.Graphics2D;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for ImageMerger utility class.
 */
class ImageMergerTest {

    @TempDir
    Path tempDir;

    private String img1Path; // 100w x 50h
    private String img2Path; // 50w x 100h

    @BeforeEach
    void setUp() throws IOException {
        img1Path = createDummyImage(tempDir.resolve("img1.png").toString(), "png", 100, 50);
        img2Path = createDummyImage(tempDir.resolve("img2.png").toString(), "png", 50, 100);
    }

    @Test
    void mergeImages_Horizontal_shouldHaveCorrectDimensions() throws IOException {
        String outputPath = tempDir.resolve("merged_h.png").toString();
        int spacing = 10;
        
        ImageMerger.mergeImages(
                List.of(img1Path, img2Path),
                outputPath,
                ImageMerger.MergeDirection.HORIZONTAL,
                0, 0, spacing
        );

        File mergedFile = new File(outputPath);
        assertThat(mergedFile).exists();

        BufferedImage mergedImg = ImageIO.read(mergedFile);
        assertThat(mergedImg).isNotNull();
        
        // totalWidth = 100 + 50 + spacing = 160
        assertThat(mergedImg.getWidth()).isEqualTo(100 + 50 + spacing);
        // maxHeight = max(50, 100) = 100
        assertThat(mergedImg.getHeight()).isEqualTo(100);
    }

    @Test
    void mergeImages_Vertical_shouldHaveCorrectDimensions() throws IOException {
        String outputPath = tempDir.resolve("merged_v.png").toString();
        int spacing = 20;

        ImageMerger.mergeImages(
                List.of(img1Path, img2Path),
                outputPath,
                ImageMerger.MergeDirection.VERTICAL,
                0, 0, spacing
        );

        File mergedFile = new File(outputPath);
        assertThat(mergedFile).exists();

        BufferedImage mergedImg = ImageIO.read(mergedFile);
        assertThat(mergedImg).isNotNull();

        // maxWidth = max(100, 50) = 100
        assertThat(mergedImg.getWidth()).isEqualTo(100);
        // totalHeight = 50 + 100 + spacing = 170
        assertThat(mergedImg.getHeight()).isEqualTo(50 + 100 + spacing);
        
        // Check pixel at (0,70) - should be WHITE due to horizontal centering of 2nd img
        assertThat(mergedImg.getRGB(0, 70)).isEqualTo(Color.WHITE.getRGB());
    }
    
    @Test
    void mergeImages_Grid_shouldHaveCorrectDimensions() throws IOException {
        String img3Path = createDummyImage(tempDir.resolve("img3.png").toString(), "png", 60, 60);
        String outputPath = tempDir.resolve("merged_grid.png").toString();
        int spacing = 5;
        int rows = 2;
        int cols = 2;

        ImageMerger.mergeImages(
                List.of(img1Path, img2Path, img3Path),
                outputPath,
                ImageMerger.MergeDirection.GRID,
                rows, cols, spacing
        );

        File mergedFile = new File(outputPath);
        assertThat(mergedFile).exists();

        BufferedImage mergedImg = ImageIO.read(mergedFile);
        assertThat(mergedImg).isNotNull();

        // maxWidth = max(100, 50, 60) = 100
        // maxHeight = max(50, 100, 60) = 100
        int expectedWidth = (cols * 100) + (spacing * (cols - 1)); // 200 + 5 = 205
        int expectedHeight = (rows * 100) + (spacing * (rows - 1)); // 200 + 5 = 205
        
        assertThat(mergedImg.getWidth()).isEqualTo(expectedWidth);
        assertThat(mergedImg.getHeight()).isEqualTo(expectedHeight);
    }
    
    @Test
    void mergeDirectoryImages_shouldMergeCorrectFiles() throws IOException {
        String outputPath = tempDir.resolve("merged_dir.png").toString();
        // Create an extra file that should be ignored
        createDummyImage(tempDir.resolve("ignored.jpg").toString(), "jpg", 10, 10);
        
        ImageMerger.mergeDirectoryImages(
                tempDir.toString(),
                List.of("png"), // Only merge .png files
                outputPath,
                ImageMerger.MergeDirection.HORIZONTAL,
                0, 0, 0
        );

        File mergedFile = new File(outputPath);
        assertThat(mergedFile).exists();

        BufferedImage mergedImg = ImageIO.read(mergedFile);
        // Should have merged img1.png (100w) and img2.png (50w)
        assertThat(mergedImg.getWidth()).isEqualTo(100 + 50);
        assertThat(mergedImg.getHeight()).isEqualTo(100);
    }

    /**
     * Helper to create a dummy image file for testing.
     */
    private String createDummyImage(String path, String format, int width, int height) throws IOException {
        BufferedImage img = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        
        // Fill with a color to distinguish from white background
        g.setColor(Color.BLUE);
        g.fillRect(0, 0, width, height);
        
        g.dispose();
        File file = new File(path);
        ImageIO.write(img, format, file);
        return file.getAbsolutePath();
    }
}