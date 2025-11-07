package com.personal.image_toolkit;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.awt.Color;
import java.awt.Graphics2D;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * A tool for merging and transforming images, supporting horizontal,
 * vertical, and grid layouts. Uses FSETool for path management.
 *
 * Re-implementation of ImageMerger.py
 */
public final class ImageMerger {

    private ImageMerger() {}

    /**
     * Defines the layout direction for merging.
     */
    public enum MergeDirection {
        HORIZONTAL,
        VERTICAL,
        GRID
    }

    // --- Core Merging Logic (Private Static Methods) ---

    private static void mergeImagesHorizontal(List<BufferedImage> images, String outputPath, int spacing) throws IOException {
        int totalWidth = 0;
        int maxHeight = 0;
        
        for (BufferedImage img : images) {
            totalWidth += img.getWidth();
            if (img.getHeight() > maxHeight) {
                maxHeight = img.getHeight();
            }
        }
        totalWidth += (spacing * (images.size() - 1));

        BufferedImage mergedImage = new BufferedImage(totalWidth, maxHeight, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = mergedImage.createGraphics();
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, totalWidth, maxHeight);

        int xOffset = 0;
        for (BufferedImage img : images) {
            g.drawImage(img, xOffset, 0, null); // Align to top
            xOffset += img.getWidth() + spacing;
        }
        g.dispose();

        ImageIO.write(mergedImage, "png", new File(outputPath));
    }

    private static void mergeImagesVertical(List<BufferedImage> images, String outputPath, int spacing) throws IOException {
        int maxWidth = 0;
        int totalHeight = 0;

        for (BufferedImage img : images) {
            totalHeight += img.getHeight();
            if (img.getWidth() > maxWidth) {
                maxWidth = img.getWidth();
            }
        }
        totalHeight += (spacing * (images.size() - 1));

        BufferedImage mergedImage = new BufferedImage(maxWidth, totalHeight, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = mergedImage.createGraphics();
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, maxWidth, totalHeight);

        int yOffset = 0;
        for (BufferedImage img : images) {
            int xOffset = (maxWidth - img.getWidth()) / 2; // Center horizontally
            g.drawImage(img, xOffset, yOffset, null);
            yOffset += img.getHeight() + spacing;
        }
        g.dispose();

        ImageIO.write(mergedImage, "png", new File(outputPath));
    }

    private static void mergeImagesGrid(List<BufferedImage> images, String outputPath, int rows, int cols, int spacing) throws IOException {
        if (rows <= 0 || cols <= 0) {
            throw new IllegalArgumentException("Rows and columns must be greater than 0.");
        }
        if (images.size() > rows * cols) {
            System.err.println("Warning: More images provided than grid slots. Truncating list.");
            images = images.subList(0, rows * cols);
        }

        int maxWidth = 0;
        int maxHeight = 0;
        for (BufferedImage img : images) {
            if (img.getWidth() > maxWidth) maxWidth = img.getWidth();
            if (img.getHeight() > maxHeight) maxHeight = img.getHeight();
        }
        
        if (maxWidth == 0 || maxHeight == 0) {
            System.err.println("No images to merge for grid layout.");
            return;
        }

        int totalWidth = (cols * maxWidth) + (spacing * (cols - 1));
        int totalHeight = (rows * maxHeight) + (spacing * (rows - 1));
        
        BufferedImage mergedImage = new BufferedImage(totalWidth, totalHeight, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = mergedImage.createGraphics();
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, totalWidth, totalHeight);

        for (int i = 0; i < images.size(); i++) {
            BufferedImage img = images.get(i);
            int row = i / cols;
            int col = i % cols;
            
            // Center image within its grid cell
            int xOffset = col * (maxWidth + spacing) + (maxWidth - img.getWidth()) / 2;
            int yOffset = row * (maxHeight + spacing) + (maxHeight - img.getHeight()) / 2;
            
            g.drawImage(img, xOffset, yOffset, null);
        }
        g.dispose();
        
        ImageIO.write(mergedImage, "png", new File(outputPath));
    }

    // --- Public Methods ---

    /**
     * Merges a list of image files based on the specified direction.
     */
    public static void mergeImages(List<String> imagePaths, String outputPath, MergeDirection direction, 
                                   int rows, int cols, int spacing) throws IOException {
        
        // Replaced decorator: Explicitly create output directory
        FSETool.createDirectoryForFile(outputPath);
        
        List<BufferedImage> images = new ArrayList<>();
        for (String path : imagePaths) {
            try {
                BufferedImage img = ImageIO.read(new File(path));
                if (img != null) {
                    images.add(img);
                }
            } catch (IOException e) {
                System.err.println("Could not read image: " + path);
            }
        }

        if (images.isEmpty()) {
            System.out.println("No valid images to merge.");
            return;
        }

        switch (direction) {
            case HORIZONTAL:
                mergeImagesHorizontal(images, outputPath, spacing);
                break;
            case VERTICAL:
                mergeImagesVertical(images, outputPath, spacing);
                break;
            case GRID:
                mergeImagesGrid(images, outputPath, rows, cols, spacing);
                break;
            default:
                throw new IllegalArgumentException("Invalid merge direction: " + direction);
        }
        
        System.out.println("Merged " + images.size() + " images into '" + outputPath + "'.");
    }

    /**
     * Merges all images of specified formats found in a directory.
     */
    public static void mergeDirectoryImages(String directory, List<String> inputFormats, String outputPath, 
                                            MergeDirection direction, int rows, int cols, int spacing) throws IOException {
        
        // Replaced decorator: Explicitly create output directory
        FSETool.createDirectoryForFile(outputPath);

        List<String> imagePaths = new ArrayList<>();
        for (String fmt : inputFormats) {
            imagePaths.addAll(FSETool.getFilesByExtension(directory, fmt, false)); // Non-recursive
        }

        if (imagePaths.isEmpty()) {
            System.out.println("WARNING: No images found in directory '" + directory + "' with formats " + inputFormats);
            return;
        }

        mergeImages(imagePaths, outputPath, direction, rows, cols, spacing);
    }
}