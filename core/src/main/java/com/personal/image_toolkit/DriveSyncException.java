package com.example.image_toolkit;

/**
 * Custom exception for critical errors during the Drive synchronization process.
 */
public class DriveSyncException extends RuntimeException {
    public DriveSyncException(String message) {
        super(message);
    }
    public DriveSyncException(String message, Throwable cause) {
        super(message, cause);
    }
}