package com.personal.image_toolkit.tools;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.awt.Color;
import java.awt.Graphics2D;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/**
 * A tool for converting image formats for single files and batches.
 * Relies on FSETool for path management and directory creation.
 *
 * Re-implementation of FormatConverter.py
 */
public final class ImageFormatConverter {

    // This was imported in the Python version. We'll define it here.
    private static final Set<String> SUPPORTED_IMG_FORMATS = 
            Set.of("png", "jpg", "jpeg", "bmp", "gif");

    private ImageFormatConverter() {}

    /**
     * Core logic for image format conversion.
     * @return The converted image, or null on failure.
     */
    private static BufferedImage convertImgCore(String imagePath, String outputPath, String format, boolean delete) {
        File inputFile = new File(imagePath);
        File outputFile = new File(outputPath);
        String outputFormat = format.toLowerCase();

        // Check input extension
        String inputExt = getFileExtension(imagePath);
        if (!SUPPORTED_IMG_FORMATS.contains(inputExt)) {
            System.err.println("Invalid input file extension: " + inputExt);
            return null;
        }

        // Check output format
        if (!SUPPORTED_IMG_FORMATS.contains(outputFormat)) {
            System.err.println("Unsupported output format: " + outputFormat);
            return null;
        }

        try {
            BufferedImage img = ImageIO.read(inputFile);
            if (img == null) {
                throw new IOException("Could not read image file.");
            }

            // Handle JPEG conversion: ensure no transparency
            if ("jpg".equals(outputFormat) || "jpeg".equals(outputFormat)) {
                // Create a new image with a white background
                BufferedImage newImg = new BufferedImage(
                        img.getWidth(), img.getHeight(), BufferedImage.TYPE_INT_RGB
                );
                Graphics2D g = newImg.createGraphics();
                g.setColor(Color.WHITE); // Set background to white
                g.fillRect(0, 0, newImg.getWidth(), newImg.getHeight());
                g.drawImage(img, 0, 0, null);
                g.dispose();
                img = newImg;
            }
            
            // Write the new image
            ImageIO.write(img, outputFormat, outputFile);
            
            if (delete) {
                inputFile.delete();
            }
            System.out.println("Converted '" + inputFile.getName() + "' to '" + outputFile.getName() + "'.");
            return img;

        } catch (Exception e) {
            System.err.println("Warning: failed to convert file " + imagePath + ". Reason: " + e.getMessage());
            return null;
        }
    }

    /**
     * Converts a single image file to a specified format.
     */
    public static BufferedImage convertImgFormat(String imagePath, String outputName, String format, boolean delete) throws IOException {
        Path resolvedImagePath = FSETool.resolvePath(imagePath);
        String inputDir = resolvedImagePath.getParent().toString();
        String filenameOnly = getFileNameWithoutExtension(resolvedImagePath.getFileName().toString());

        String resolvedOutputPath;
        if (outputName == null || outputName.isEmpty()) {
            // Save in the same directory as the input image
            resolvedOutputPath = new File(inputDir, filenameOnly + "." + format).getAbsolutePath();
        } else {
            // outputName might be a full path or just a name.
            // FSETool.resolvePath handles both.
            Path outPath = FSETool.resolvePath(outputName);
            // If outputName was just a name, it's resolved relative to CWD.
            // Let's check if it has a parent. If not, place it in input dir.
            if (outPath.getParent() == null || outPath.getParent().toString().equals(System.getProperty("user.dir"))) {
                 resolvedOutputPath = new File(inputDir, outputName + "." + format).getAbsolutePath();
            } else {
                 resolvedOutputPath = outPath.toString() + "." + format;
            }
        }
        
        // Replaced decorator: Explicitly create parent directory
        FSETool.createDirectoryForFile(resolvedOutputPath);

        if (Files.isRegularFile(Paths.get(resolvedOutputPath))) {
            return null; // File already exists
        }

        return convertImgCore(resolvedImagePath.toString(), resolvedOutputPath, format, delete);
    }

    /**
     * Converts all images in a directory matching input_formats to the output_format.
     */
    public static List<BufferedImage> batchConvertImgFormat(
            String inputDir, List<String> inputsFormats, String outputDir, 
            String outputFormat, boolean delete) throws IOException {
        
        String resolvedOutputDir = (outputDir == null || outputDir.isEmpty()) 
                ? FSETool.resolvePath(inputDir).toString() 
                : FSETool.resolvePath(outputDir).toString();
        
        // Replaced decorator: Explicitly create output directory
        FSETool.createDirectory(resolvedOutputDir);

        String outFormat = outputFormat.toLowerCase();
        
        List<BufferedImage> newImages = new ArrayList<>();
        for (String inputFormat : inputsFormats) {
            if (inputFormat.toLowerCase().equals(outFormat)) {
                continue; // Skip if in-format == out-format
            }
            
            List<String> filesToConvert = FSETool.getFilesByExtension(inputDir, inputFormat, false);
            
            for (String inputFile : filesToConvert) {
                String filename = getFileNameWithoutExtension(new File(inputFile).getName());
                String outputPath = new File(resolvedOutputDir, filename + "." + outFormat).getAbsolutePath();
                
                if (!Files.isRegularFile(Paths.get(outputPath))) {
                    BufferedImage img = convertImgCore(inputFile, outputPath, outFormat, delete);
                    if (img != null) {
                        newImages.add(img);
                    }
                }
            }
        }
        
        System.out.println("\nBatch conversion complete! Converted " + newImages.size() + " images.");
        return newImages;
    }

    // Helper method
    private static String getFileExtension(String filename) {
        int dotIndex = filename.lastIndexOf('.');
        return (dotIndex == -1) ? "" : filename.substring(dotIndex + 1).toLowerCase();
    }

    // Helper method
    private static String getFileNameWithoutExtension(String filename) {
        int dotIndex = filename.lastIndexOf('.');
        return (dotIndex == -1) ? filename : filename.substring(0, dotIndex);
    }
}