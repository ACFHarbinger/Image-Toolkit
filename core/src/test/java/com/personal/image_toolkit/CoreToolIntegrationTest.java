package com.personal.image_toolkit;

import com.personal.image_toolkit.tools.FSETool;
import com.personal.image_toolkit.tools.ImageFormatConverter;
import com.personal.image_toolkit.tools.ImageMerger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.awt.Color;
import java.awt.Graphics2D;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.Files;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration tests for the core tool workflows.
 * These tests verify that the utility classes (FSETool, ImageFormatConverter,
 * ImageMerger) work correctly together to accomplish user-facing tasks.
 */
class CoreToolIntegrationTest {

    @TempDir
    Path tempDir;

    /**
     * Tests the "Batch Convert" workflow, corresponding to the ConvertTab.
     * This test integrates FSETool.getFilesByExtension and ImageFormatConverter.batchConvertImgFormat.
     */
    @Test
    void testBatchConversionWorkflow() throws IOException {
        // --- 1. Setup ---
        // Create input and output directories
        Path inputDir = tempDir.resolve("batch_convert_input");
        Path outputDir = tempDir.resolve("batch_convert_output");
        Files.createDirectories(inputDir);
        // Note: We don't create outputDir, we let the tool do it.

        // Create dummy files
        createDummyImage(inputDir.resolve("image1.jpg").toString(), "jpg", 100, 50, false);
        createDummyImage(inputDir.resolve("image2.jpg").toString(), "jpg", 50, 50, false);
        createDummyImage(inputDir.resolve("image3.png").toString(), "png", 80, 80, false); // Should be ignored
        Files.createFile(inputDir.resolve("readme.txt")); // Should be ignored

        // --- 2. Act ---
        // Run the batch conversion
        ImageFormatConverter.batchConvertImgFormat(
                inputDir.toString(),
                List.of("jpg"), // Convert all JPGs
                outputDir.toString(),
                "png", // To PNG
                false // Don't delete originals
        );

        // --- 3. Assert ---
        // Check that the output directory was created
        assertThat(outputDir).exists().isDirectory();

        // Check that the correct files were created
        assertThat(outputDir.resolve("image1.png")).exists().isRegularFile();
        assertThat(outputDir.resolve("image2.png")).exists().isRegularFile();

        // Check that ignored files were *not* created
        assertThat(outputDir.resolve("image3.png")).doesNotExist();
        assertThat(outputDir.resolve("readme.png")).doesNotExist();

        // Check that original files still exist
        assertThat(inputDir.resolve("image1.jpg")).exists();
        assertThat(inputDir.resolve("image3.png")).exists();
    }

    /**
     * Tests the "Batch Merge" workflow, corresponding to the MergeTab.
     * This test integrates FSETool.getFilesByExtension and ImageMerger.mergeDirectoryImages.
     */
    @Test
    void testBatchMergeWorkflow() throws IOException {
        // --- 1. Setup ---
        Path inputDir = tempDir.resolve("batch_merge_input");
        Files.createDirectories(inputDir);
        String outputPath = tempDir.resolve("final_merged_image.png").toString();

        // Create dummy files
        createDummyImage(inputDir.resolve("a.png").toString(), "png", 100, 50, false);
        createDummyImage(inputDir.resolve("b.png").toString(), "png", 50, 100, false);
        createDummyImage(inputDir.resolve("c.jpg").toString(), "jpg", 80, 80, false); // Should be ignored

        // --- 2. Act ---
        ImageMerger.mergeDirectoryImages(
                inputDir.toString(),
                List.of("png"), // Only merge PNGs
                outputPath,
                ImageMerger.MergeDirection.HORIZONTAL,
                0, 0, // rows/cols (not used for horizontal)
                10 // spacing
        );

        // --- 3. Assert ---
        // Check that the output file exists
        File mergedFile = new File(outputPath);
        assertThat(mergedFile).exists().isFile();

        // Check the dimensions of the merged image
        BufferedImage mergedImg = ImageIO.read(mergedFile);
        assertThat(mergedImg).isNotNull();
        // totalWidth = 100 + 50 + 10 (spacing) = 160
        assertThat(mergedImg.getWidth()).isEqualTo(160);
        // maxHeight = max(50, 100) = 100
        assertThat(mergedImg.getHeight()).isEqualTo(100);
    }

    /**
     * Tests a combined workflow: Batch convert files, then merge the *converted* files.
     * This integrates all three utility classes.
     */
    @Test
    void testFullWorkflow_ConvertThenMerge() throws IOException {
        // --- 1. Setup ---
        Path step1InputDir = tempDir.resolve("convert_in");
        Path step2MergeDir = tempDir.resolve("convert_out_merge_in"); // Output of convert, input of merge
        String step3FinalOutput = tempDir.resolve("final_image.png").toString();
        
        Files.createDirectories(step1InputDir);

        createDummyImage(step1InputDir.resolve("img1.jpg").toString(), "jpg", 100, 50, false);
        createDummyImage(step1InputDir.resolve("img2.bmp").toString(), "bmp", 50, 100, false);
        createDummyImage(step1InputDir.resolve("img3.jpg").toString(), "jpg", 60, 60, false);

        // --- 2. Act (Step 1: Convert) ---
        ImageFormatConverter.batchConvertImgFormat(
                step1InputDir.toString(),
                List.of("jpg", "bmp"), // Convert all JPGs and BMPs
                step2MergeDir.toString(),
                "png", // To PNG
                true // Delete originals
        );

        // --- 3. Assert (Step 1: Verify Conversion) ---
        assertThat(step2MergeDir).exists();
        assertThat(step2MergeDir.resolve("img1.png")).exists();
        assertThat(step2MergeDir.resolve("img2.png")).exists();
        assertThat(step2MergeDir.resolve("img3.png")).exists();
        // Check that originals were deleted
        assertThat(step1InputDir.resolve("img1.jpg")).doesNotExist();
        assertThat(step1InputDir.resolve("img2.bmp")).doesNotExist();
        
        // --- 4. Act (Step 2: Merge) ---
        ImageMerger.mergeDirectoryImages(
                step2MergeDir.toString(),
                List.of("png"), // Merge the new PNGs
                step3FinalOutput,
                ImageMerger.MergeDirection.GRID,
                2, 2, // 2x2 grid
                5 // 5px spacing
        );

        // --- 5. Assert (Step 2: Verify Merge) ---
        File finalFile = new File(step3FinalOutput);
        assertThat(finalFile).exists();

        BufferedImage finalImg = ImageIO.read(finalFile);
        // maxWidth = max(100, 50, 60) = 100
        // maxHeight = max(50, 100, 60) = 100
        // totalWidth = (2 * 100) + (1 * 5) = 205
        // totalHeight = (2 * 100) + (1 * 5) = 205
        assertThat(finalImg.getWidth()).isEqualTo(205);
        assertThat(finalImg.getHeight()).isEqualTo(205);
    }


    /**
     * Helper to create a dummy image file for testing.
     */
    private String createDummyImage(String path, String format, int width, int height, boolean withAlpha) throws IOException {
        // Ensure parent directory exists (needed for sub-directory tests)
        Path parentDir = Paths.get(path).getParent();
        if (parentDir != null && !Files.exists(parentDir)) {
            Files.createDirectories(parentDir);
        }

        int imageType = withAlpha ? BufferedImage.TYPE_INT_ARGB : BufferedImage.TYPE_INT_RGB;
        BufferedImage img = new BufferedImage(width, height, imageType);
        Graphics2D g = img.createGraphics();

        if (withAlpha) {
            // Fill with transparent
            g.setBackground(new Color(0, 0, 0, 0));
            g.clearRect(0, 0, width, height);
            // Draw a red box
            g.setColor(Color.RED);
            g.fillRect(10, 10, width - 20, height - 20);
        } else {
            // Fill with a solid color
            g.setColor(new Color(width % 255, height % 255, (width + height) % 255));
            g.fillRect(0, 0, width, height);
        }

        g.dispose();
        File file = new File(path);
        ImageIO.write(img, format, file);
        return file.getAbsolutePath();
    }
}