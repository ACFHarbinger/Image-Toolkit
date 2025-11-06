package com.personal.image_toolkit.tools;

// Removed @BeforeEach
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.awt.Color;
import java.awt.Graphics2D;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for ImageFormatConverter utility class.
 */
class ImageFormatConverterTest {

    @TempDir
    Path tempDir;

    // Removed private String pngFile and jpgFile
    // Removed @BeforeEach setUp method

    @Test
    void convertImgFormat_fromPngToJpg_shouldFlattenTransparency() throws IOException {
        // Create only the input file needed for this test
        String pngFile = createDummyImage(tempDir.resolve("test.png").toString(), "png", 100, 50, true);
        
        Path outputPath = tempDir.resolve("test.jpg");
        assertThat(outputPath).doesNotExist(); // This will now pass

        ImageFormatConverter.convertImgFormat(pngFile, null, "jpg", false);

        assertThat(outputPath).exists();
        
        BufferedImage jpgImage = ImageIO.read(outputPath.toFile());
        assertThat(jpgImage).isNotNull();
        int rgb = jpgImage.getRGB(0, 0);
        Color pixelColor = new Color(rgb);

        // Check that the pixel is "very white"
        // JPG compression can cause slight artifacts, so we don't check for -1 exact
        assertThat(pixelColor.getRed()).isGreaterThan(240);
        assertThat(pixelColor.getGreen()).isGreaterThan(240);
        assertThat(pixelColor.getBlue()).isGreaterThan(240);
    }
    

    @Test
    void convertImgFormat_fromJpgToPng_shouldConvert() throws IOException {
        // Create only the input file needed for this test
        String jpgFile = createDummyImage(tempDir.resolve("test.jpg").toString(), "jpg", 100, 50, false);

        Path outputPath = tempDir.resolve("test.png");
        assertThat(outputPath).doesNotExist(); // This will now pass

        ImageFormatConverter.convertImgFormat(jpgFile, null, "png", false);

        assertThat(outputPath).exists();
        BufferedImage pngImage = ImageIO.read(outputPath.toFile());
        assertThat(pngImage).isNotNull();
        assertThat(pngImage.getWidth()).isEqualTo(100);
        assertThat(pngImage.getHeight()).isEqualTo(50);
    }

    @Test
    void convertImgFormat_withOutputName_shouldSaveToCorrectLocation() throws IOException {
        // Create only the input file needed for this test
        String jpgFile = createDummyImage(tempDir.resolve("test.jpg").toString(), "jpg", 100, 50, false);
        
        // Test with just a name, should save in same dir
        Path outputPath1 = tempDir.resolve("converted.png");
        ImageFormatConverter.convertImgFormat(jpgFile, "converted", "png", false);
        assertThat(outputPath1).exists();

        // Test with a relative path
        Path outputPath2 = tempDir.resolve("sub/converted.png");
        ImageFormatConverter.convertImgFormat(jpgFile, tempDir.resolve("sub/converted").toString(), "png", false);
        assertThat(outputPath2).exists();
    }

    @Test
    void convertImgFormat_withDelete_shouldRemoveOriginal() throws IOException {
        // Create only the input file needed for this test
        String jpgFile = createDummyImage(tempDir.resolve("test.jpg").toString(), "jpg", 100, 50, false);
        
        Path originalPath = Paths.get(jpgFile);
        Path outputPath = tempDir.resolve("test.png");
        
        assertThat(originalPath).exists();
        assertThat(outputPath).doesNotExist(); // This will now pass

        ImageFormatConverter.convertImgFormat(jpgFile, null, "png", true);

        assertThat(originalPath).doesNotExist();
        assertThat(outputPath).exists();
    }

    @Test
    void batchConvertImgFormat_shouldConvertMatchingFiles() throws IOException {
        // This test was already self-contained, so it remains the same.
        // It creates its own files.
        createDummyImage(tempDir.resolve("test.jpg").toString(), "jpg", 20, 20, false);
        createDummyImage(tempDir.resolve("another.jpg").toString(), "jpg", 20, 20, false);
        createDummyImage(tempDir.resolve("keep.png").toString(), "png", 20, 20, false);
        
        Path outputDir = tempDir.resolve("output");

        ImageFormatConverter.batchConvertImgFormat(
                tempDir.toString(),
                List.of("jpg"), // Convert JPGs
                outputDir.toString(),
                "png", // To PNG
                false
        );

        assertThat(outputDir.resolve("test.png")).exists();
        assertThat(outputDir.resolve("another.png")).exists();
        assertThat(outputDir.resolve("keep.png")).doesNotExist(); // Was not converted
        assertThat(tempDir.resolve("keep.png")).exists(); // Original still exists
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
            g.setBackground(new Color(0, 0, 0, 0));
            g.clearRect(0, 0, width, height);
            g.setColor(Color.RED);
            g.fillRect(10, 10, width - 20, height - 20);
        } else {
            g.setColor(Color.BLUE);
            g.fillRect(0, 0, width, height);
        }
        
        g.dispose();
        File file = new File(path);
        ImageIO.write(img, format, file);
        return file.getAbsolutePath();
    }
}