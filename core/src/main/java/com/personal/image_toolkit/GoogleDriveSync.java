package com.example.drivesync;

import com.google.api.client.googleapis.json.GoogleJsonResponseException;
import com.google.api.client.http.FileContent;
import com.google.api.services.drive.Drive;
import com.google.api.services.drive.model.File;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.auth.oauth2.ServiceAccountCredentials;
import com.google.api.client.json.gson.GsonFactory;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.util.DateTime;

import java.io.FileInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.*;
import java.util.stream.Stream;

/**
 * Performs one-way synchronization (remote mirrors local) for top-level files
 * using the Google Drive API.
 */
public class GoogleDriveSync {

    // ==============================================================================
    // 1. CONFIGURATION
    // ==============================================================================

    // IMPORTANT: Path to your Google Service Account JSON key file.
    private static final String SERVICE_ACCOUNT_FILE = "service_account_key.json";

    // Local folder path you want to synchronize (e.g., a folder on your server)
    private static final String LOCAL_SOURCE_PATH = "/path/to/local/source/folder";

    // Destination folder *name* inside your Google Drive.
    private static final String DRIVE_DESTINATION_FOLDER_NAME = "Scheduled_Backups/Current_Month";

    // Optional: If you want to perform a dry run (show actions without executing them)
    private static final boolean DRY_RUN = false;

    // Google Drive scopes for read/write access
    private static final List<String> SCOPES = Collections.singletonList("https://www.googleapis.com/auth/drive");

    // ==============================================================================
    // 2. HELPER FUNCTIONS: DRIVE & AUTH
    // ==============================================================================

    private static Drive getDriveService(String keyFile) {
        System.out.println("🔑 Authenticating with Google Drive...");
        try (FileInputStream fis = new FileInputStream(keyFile)) {
            GoogleCredentials credentials = ServiceAccountCredentials.fromStream(fis)
                    .createScoped(SCOPES);

            Drive service = new Drive.Builder(
                    new NetHttpTransport(),
                    GsonFactory.getDefaultInstance(),
                    new com.google.api.client.http.javanet.NetHttpRequestInitializer(credentials)
            )
            .setApplicationName("PurePythonToRcloneJavaSync")
            .build();

            System.out.println("✅ Authentication successful.");
            return service;
        } catch (IOException e) {
            System.err.println("❌ Authentication Error: Failed to load service account key file.");
            throw new DriveSyncException("Service Account Key Error", e);
        }
    }

    private static String findOrCreateDestinationFolder(Drive service, String folderPathStr) throws IOException {
        String[] pathComponents = folderPathStr.split("/");
        String currentParentId = "root"; // Start search from the root

        System.out.printf("🔍 Locating/Creating destination path: /%s%n", folderPathStr);

        for (String folderName : pathComponents) {
            if (folderName.isEmpty()) continue;

            // 1. Search for the folder in the current parent
            String query = String.format(
                "name='%s' and mimeType='application/vnd.google-apps.folder' and '%s' in parents and trashed=false",
                folderName, currentParentId
            );

            Drive.Files.List request = service.files().list()
                    .setQ(query)
                    .setSpaces("drive")
                    .setFields("files(id, name)");

            List<File> files = request.execute().getFiles();

            if (!files.isEmpty()) {
                // Folder found
                currentParentId = files.get(0).getId();
            } else {
                // Folder not found, create it
                System.out.printf("   Creating folder: %s%n", folderName);
                File fileMetadata = new File()
                    .setName(folderName)
                    .setMimeType("application/vnd.google-apps.folder")
                    .setParents(Collections.singletonList(currentParentId));

                if (DRY_RUN) {
                    System.out.printf("   [DRY RUN] Would have created folder '%s'%n", folderName);
                    // Cannot continue traversing in dry run if path does not exist
                    return null; 
                }

                try {
                    File folder = service.files().create(fileMetadata).setFields("id").execute();
                    currentParentId = folder.getId();
                    System.out.printf("   Created folder: %s (ID: %s)%n", folderName, currentParentId);
                } catch (GoogleJsonResponseException e) {
                    System.err.printf("❌ Error creating folder '%s': %s%n", folderName, e.getDetails().getMessage());
                    return null;
                }
            }
        }

        System.out.printf("✅ Destination Folder ID: %s%n", currentParentId);
        return currentParentId;
    }

    // ==============================================================================
    // 3. CORE SYNCHRONIZATION LOGIC
    // ==============================================================================

    private static Map<String, FileMetadata> getLocalFilesMap(String localPath) throws IOException {
        Map<String, FileMetadata> localFiles = new HashMap<>();
        Path rootPath = Paths.get(localPath);

        // Files.walk is used to traverse the local directory recursively
        try (Stream<Path> stream = Files.walk(rootPath)) {
            stream.filter(Files::isRegularFile)
                  .forEach(filePath -> {
                      String fileName = filePath.getFileName().toString();
                      try {
                          // Get modification time and convert to Instant
                          Instant mtime = Files.getLastModifiedTime(filePath).toInstant();
                          FileMetadata metadata = new FileMetadata(fileName, filePath.toString(), mtime);
                          // We only map top-level files for this simplified sync
                          if (rootPath.equals(filePath.getParent())) {
                              localFiles.put(fileName, metadata);
                          }
                      } catch (IOException e) {
                          System.err.printf("Error reading local file metadata for %s: %s%n", filePath, e.getMessage());
                      }
                  });
        }
        return localFiles;
    }
    
    private static Map<String, FileMetadata> getRemoteFilesMap(Drive service, String folderId) throws IOException {
        Map<String, FileMetadata> remoteFiles = new HashMap<>();
        
        // Query files directly under the destination folder
        String query = String.format("'%s' in parents and trashed=false", folderId);

        String pageToken = null;
        do {
            Drive.Files.List request = service.files().list()
                    .setQ(query)
                    .setSpaces("drive")
                    .setFields("nextPageToken, files(id, name, modifiedTime, mimeType)")
                    .setPageToken(pageToken);
            
            com.google.api.services.drive.model.FileList response = request.execute();
            
            for (File file : response.getFiles()) {
                String name = file.getName();
                String mimeType = file.getMimeType();
                boolean isFolder = "application/vnd.google-apps.folder".equals(mimeType);

                // Drive API's DateTime includes milliseconds and timezone (RFC 3339)
                DateTime modifiedTimeApi = file.getModifiedTime();
                Instant mtime = modifiedTimeApi != null ? Instant.ofEpochMilli(modifiedTimeApi.getValue()) : Instant.ofEpochMilli(0);

                FileMetadata metadata = new FileMetadata(name, file.getId(), null, mtime, isFolder);
                remoteFiles.put(name, metadata);
            }
            pageToken = response.getNextPageToken();
        } while (pageToken != null);

        return remoteFiles;
    }

    private static boolean uploadFile(Drive service, Path localFilePath, String fileName, String folderId, String remoteFileId) throws IOException {
        // Prepare file metadata for upload/update
        File fileMetadata = new File()
            .setName(fileName)
            .setModifiedTime(new DateTime(Files.getLastModifiedTime(localFilePath).toMillis()));
        
        if (remoteFileId == null) {
            // New file upload
            fileMetadata.setParents(Collections.singletonList(folderId));
        }
        
        FileContent mediaContent = new FileContent(Files.probeContentType(localFilePath), localFilePath.toFile());

        if (DRY_RUN) {
            String action = (remoteFileId != null) ? "UPDATE" : "UPLOAD";
            System.out.printf("   [DRY RUN] %s: %s%n", action, fileName);
            return true;
        }

        try {
            if (remoteFileId != null) {
                // Update existing file
                service.files().update(remoteFileId, fileMetadata, mediaContent).execute();
            } else {
                // Upload new file
                service.files().create(fileMetadata, mediaContent).setFields("id").execute();
            }
            return true;
        } catch (GoogleJsonResponseException e) {
            System.err.printf("❌ Google API Error during file operation for '%s': %s%n", fileName, e.getDetails().getMessage());
            return false;
        }
    }
    
    private static boolean deleteFile(Drive service, String fileId, String fileName) throws IOException {
        System.out.printf("   DELETING: %s%n", fileName);

        if (DRY_RUN) {
            System.out.printf("   [DRY RUN] Would have deleted file/folder: %s%n", fileName);
            return true;
        }

        try {
            service.files().delete(fileId).execute();
            return true;
        } catch (GoogleJsonResponseException e) {
            System.err.printf("❌ Google API Error deleting '%s': %s%n", fileName, e.getDetails().getMessage());
            return false;
        }
    }
    
    private static boolean executeSync(Drive service, String localPath, String remoteFolderId) throws IOException {
        
        Map<String, FileMetadata> localFiles = getLocalFilesMap(localPath);
        Map<String, FileMetadata> remoteFiles = getRemoteFilesMap(service, remoteFolderId);
        
        System.out.println("\n--- Sync Operation Analysis ---");
        
        int filesToSync = 0;
        int filesToDelete = 0;
        
        // 1. Determine files to upload/update
        for (Map.Entry<String, FileMetadata> localEntry : localFiles.entrySet()) {
            String localName = localEntry.getKey();
            FileMetadata localData = localEntry.getValue();
            Instant localMtime = localData.getModificationTime();
            Path localFilePath = Paths.get(localData.getPath());
            
            if (remoteFiles.containsKey(localName)) {
                FileMetadata remoteData = remoteFiles.get(localName);
                Instant remoteMtime = remoteData.getModificationTime();
                
                // Compare modification times (Local must be strictly newer)
                // Use isAfter for precise time comparison
                if (localMtime.isAfter(remoteMtime.plusSeconds(1))) { // Add 1s buffer for safety
                    System.out.printf("   UPDATING: %s (Local newer: %s > %s)%n", localName, localMtime, remoteMtime);
                    uploadFile(service, localFilePath, localName, remoteFolderId, remoteData.getId());
                    filesToSync++;
                }
                // Remote file is present, so remove it from the remote map to prevent deletion
                remoteFiles.remove(localName);
            } else {
                // File exists locally but not remotely -> UPLOAD
                System.out.printf("   UPLOADING: %s (New file)%n", localName);
                uploadFile(service, localFilePath, localName, remoteFolderId, null);
                filesToSync++;
            }
        }

        // 2. Determine files to delete (remaining files in remoteFiles map)
        for (FileMetadata remoteData : remoteFiles.values()) {
            // File exists remotely but not locally -> DELETE (rclone sync behavior)
            System.out.printf("   DELETING: %s (Not found locally)%n", remoteData.getName());
            deleteFile(service, remoteData.getId(), remoteData.getName());
            filesToDelete++;
        }
        
        int totalActions = filesToSync + filesToDelete;
        
        System.out.println("\n--- Sync Execution Summary ---");
        
        if (totalActions == 0) {
            System.out.println("No changes required. Source and Destination are synchronized.");
        } else {
            System.out.printf("Total actions performed: %d (Upload/Update: %d, Delete: %d)%n",
                              totalActions, filesToSync, filesToDelete);
        }
        
        return totalActions > 0;
    }

    // ==============================================================================
    // 4. MAIN EXECUTION FLOW
    // ==============================================================================

    public static void main(String[] args) {
        
        if (DRY_RUN) {
            System.out.println("\n=======================================================");
            System.out.println("          !!! D R Y   R U N   M O D E !!!");
            System.out.println("    No changes will be made to the Google Drive.");
            System.out.println("=======================================================\n");
        }

        try {
            // 4.1. Prerequisite Checks
            if (!Files.exists(Paths.get(SERVICE_ACCOUNT_FILE))) {
                System.err.printf("Error: Service Account key file '%s' not found.%n", SERVICE_ACCOUNT_FILE);
                System.exit(1);
            }
            if (!Files.isDirectory(Paths.get(LOCAL_SOURCE_PATH))) {
                 System.err.printf("Error: Local source path '%s' does not exist or is not a directory.%n", LOCAL_SOURCE_PATH);
                 System.exit(1);
            }

            // 4.2. Initialize Drive Service
            Drive driveService = getDriveService(SERVICE_ACCOUNT_FILE);

            // 4.3. Find Destination Folder
            String destFolderId = findOrCreateDestinationFolder(driveService, DRIVE_DESTINATION_FOLDER_NAME);
            
            if (destFolderId == null && !DRY_RUN) {
                 System.err.println("❌ Failed to secure destination folder ID. Exiting.");
                 System.exit(1);
            }

            // 4.4. Run the Synchronization
            boolean changesMade = false;
            if (destFolderId != null) {
                changesMade = executeSync(driveService, LOCAL_SOURCE_PATH, destFolderId);
            } else if (DRY_RUN) {
                System.out.println("⚠️  Cannot proceed with file sync comparison in DRY RUN as destination folder was not secured.");
            }
            
            // 4.5. Exit Code for Scheduling Environment
            if (!changesMade && !DRY_RUN) {
                System.out.println("\nScript finished successfully (No changes needed).");
                System.exit(0);
            } else if (DRY_RUN) {
                 System.out.println("\nScript finished successfully in DRY RUN mode.");
                 System.exit(0);
            } else {
                System.out.println("\nScript finished successfully (Changes were made).");
                System.exit(0);
            }

        } catch (GoogleJsonResponseException e) {
            System.err.printf("❌ Google Drive API Error: %s%n", e.getDetails().getMessage());
            System.exit(1);
        } catch (DriveSyncException e) {
            System.err.printf("❌ Critical Sync Error: %s%n", e.getMessage());
            System.exit(1);
        } catch (Exception e) {
            System.err.printf("❌ An unexpected script error occurred: %s%n", e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
}