package com.personal.image_toolkit;

import com.personal.image_toolkit.tools.FSETool;
import com.personal.image_toolkit.tools.ImageFormatConverter;
import com.personal.image_toolkit.tools.ImageMerger;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Main API Controller for all tool actions.
 * This is the completed version with all actions implemented.
 */
@Path("/api/tools")
@ApplicationScoped
public class ToolController {

    @Inject
    DatabaseService databaseService;

    /**
     * Handles all read-only actions.
     * React calls: GET /api/tools/read?action=get_all_tags
     */
    @GET
    @Path("/read")
    @Produces(MediaType.APPLICATION_JSON)
    public Response handleReadActions(@QueryParam("action") String action,
                                      @QueryParam("file_path") String file_path) {
        if (action == null || action.isBlank()) {
            return badRequest("action is required.");
        }
        try {
            return switch (action) {
                case "get_all_tags" -> Response.ok(databaseService.getAllTags()).build();
                case "get_all_tags_with_types" -> Response.ok(databaseService.getAllTagsWithTypes()).build();
                case "get_all_groups" -> Response.ok(databaseService.getAllGroups()).build();
                case "get_statistics" -> Response.ok(databaseService.getStatistics()).build();
                case "get_image_by_path" -> {
                    if (file_path == null) throw new IllegalArgumentException("file_path is required.");
                    Map<String, Object> image = databaseService.getImageByPath(file_path);
                    if (image == null) throw new WebApplicationException("Image not found", 404);
                    yield Response.ok(image).build();
                }
                default -> throw new IllegalArgumentException("Unknown read action: " + action);
            };
        } catch (Exception e) {
            return handleError(e);
        }
    }

    /**
     * Handles all write actions.
     * React calls: POST /api/tools/write
     * with a JSON body: { "action": "delete", "delete_path": "..." }
     */
    @POST
    @Path("/write")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    public Response handleWriteActions(Map<String, Object> payload) {
        String action = (String) payload.get("action");
        if (action == null) {
            return badRequest("action is required.");
        }

        try {
            return switch (action) {
                // --- File System Actions ---
                case "delete" -> handleDelete(payload);
                case "convert" -> handleConvert(payload);
                case "merge" -> handleMerge(payload);

                // --- Database Actions ---
                case "search_images" -> handleSearch(payload);
                case "add_group" -> handleAddGroup(payload);
                case "add_tag" -> handleAddTag(payload);
                case "add_image" -> handleAddImage(payload);
                case "batch_add_images" -> handleBatchAddImages(payload);
                case "update_image" -> handleUpdateImage(payload);
                case "rename_group" -> handleRenameGroup(payload);
                case "rename_tag" -> handleRenameTag(payload);
                case "update_tag_type" -> handleUpdateTagType(payload);
                case "delete_image" -> handleDeleteImage(payload);
                case "delete_group" -> handleDeleteGroup(payload);
                case "delete_tag" -> handleDeleteTag(payload);

                default -> throw new IllegalArgumentException("Unknown write action: " + action);
            };
        } catch (Exception e) {
            return handleError(e);
        }
    }

    // --- Private Helper Methods for Actions ---

    private Response handleDelete(Map<String, Object> p) throws IOException {
        String path = getString(p, "delete_path");
        FSETool.deletePath(path);
        return ok("Successfully deleted: " + path);
    }

    private Response handleConvert(Map<String, Object> p) throws IOException {
        String inputPath = getString(p, "input_path");
        String outputFormat = getString(p, "output_format", "png");
        String outputPath = getString(p, "output_path", null); // Can be null
        List<String> inputFormats = getList(p, "input_formats");
        boolean delete = getBool(p, "delete", false);

        if (inputFormats != null && !inputFormats.isEmpty()) {
            // Batch convert
            ImageFormatConverter.batchConvertImgFormat(inputPath, inputFormats, outputPath, outputFormat, delete);
            return ok("Batch conversion complete.");
        } else {
            // Single file convert
            ImageFormatConverter.convertImgFormat(inputPath, outputPath, outputFormat, delete);
            return ok("File conversion complete.");
        }
    }

    private Response handleMerge(Map<String, Object> p) throws IOException {
        String inputDir = getString(p, "input_path"); // Assuming input_path is a directory for batch merge
        String outputPath = getString(p, "output_path");
        List<String> inputFormats = getList(p, "input_formats");
        ImageMerger.MergeDirection direction = ImageMerger.MergeDirection.valueOf(getString(p, "direction", "HORIZONTAL").toUpperCase());
        int spacing = getInt(p, "spacing", 0);
        int rows = getInt(p, "rows", 2);
        int cols = getInt(p, "cols", 2);

        ImageMerger.mergeDirectoryImages(inputDir, inputFormats, outputPath, direction, rows, cols, spacing);
        return ok("Image merge complete.");
    }

    private Response handleSearch(Map<String, Object> p) throws Exception {
        List<Map<String, Object>> results = databaseService.searchImages(
            getString(p, "query", null),
            getList(p, "tags"),
            getString(p, "group_name", null),
            getList(p, "query_vector"),
            getInt(p, "limit", 50)
        );
        return Response.ok(results).build();
    }

    private Response handleAddGroup(Map<String, Object> p) throws Exception {
        String groupName = getString(p, "group_name");
        databaseService.addGroup(groupName);
        return created("Group added: " + groupName);
    }

    private Response handleAddTag(Map<String, Object> p) throws Exception {
        databaseService.addTag(getString(p, "name"), getString(p, "type", null));
        return created("Tag added/updated.");
    }

    private Response handleAddImage(Map<String, Object> p) throws Exception {
        int id = databaseService.addImage(
            getString(p, "image_path"),
            getList(p, "embedding"),
            getString(p, "group_name", null),
            getList(p, "tags"),
            getInt(p, "width", null),
            getInt(p, "height", null)
        );
        return created(Map.of("message", "Image added/updated.", "id", id));
    }

    private Response handleBatchAddImages(Map<String, Object> p) throws Exception {
        List<String> imagePaths = getList(p, "image_paths");
        String groupName = getString(p, "group_name", null);
        if (imagePaths == null) throw new IllegalArgumentException("image_paths is required.");
        
        int count = 0;
        List<Integer> ids = new ArrayList<>();
        for (String path : imagePaths) {
            try {
                int id = databaseService.addImage(path, null, groupName, null, null, null);
                ids.add(id);
                count++;
            } catch (Exception e) {
                System.err.println("Failed to batch add image: " + path + " | Error: " + e.getMessage());
            }
        }
        return created(Map.of(
            "message", "Batch add complete. Added " + count + " of " + imagePaths.size() + " images.",
            "new_ids", ids
        ));
    }

    private Response handleUpdateImage(Map<String, Object> p) throws Exception {
        databaseService.updateImage(
            getInt(p, "image_id"),
            getString(p, "group_name", null),
            getList(p, "tags")
        );
        return ok("Image updated.");
    }

    private Response handleRenameGroup(Map<String, Object> p) throws Exception {
        databaseService.renameGroup(getString(p, "old_name"), getString(p, "new_name"));
        return ok("Group renamed.");
    }

    private Response handleRenameTag(Map<String, Object> p) throws Exception {
        databaseService.renameTag(getString(p, "old_name"), getString(p, "new_name"));
        return ok("Tag renamed.");
    }

    private Response handleUpdateTagType(Map<String, Object> p) throws Exception {
        databaseService.updateTagType(getString(p, "name"), getString(p, "new_type"));
        return ok("Tag type updated.");
    }

    private Response handleDeleteImage(Map<String, Object> p) throws Exception {
        databaseService.deleteImage(getInt(p, "image_id"));
        return ok("Image deleted.");
    }

    private Response handleDeleteGroup(Map<String, Object> p) throws Exception {
        databaseService.deleteGroup(getString(p, "name"));
        return ok("Group deleted.");
    }

    private Response handleDeleteTag(Map<String, Object> p) throws Exception {
        databaseService.deleteTag(getString(p, "name"));
        return ok("Tag deleted.");
    }

    // --- Type-safe Payload Getters ---
    
    private String getString(Map<String, Object> p, String key) {
        if (!p.containsKey(key)) throw new IllegalArgumentException("Missing required parameter: " + key);
        return (String) p.get(key);
    }
    
    private String getString(Map<String, Object> p, String key, String defaultValue) {
        return (String) p.getOrDefault(key, defaultValue);
    }

    private Integer getInt(Map<String, Object> p, String key) {
        if (!p.containsKey(key)) throw new IllegalArgumentException("Missing required parameter: " + key);
        // JSON numbers are often parsed as Double, so we handle that.
        Object val = p.get(key);
        if (val instanceof Number) return ((Number) val).intValue();
        throw new IllegalArgumentException("Parameter " + key + " must be a number.");
    }
    
    private Integer getInt(Map<String, Object> p, String key, Integer defaultValue) {
        Object val = p.get(key);
        if (val == null) return defaultValue;
        if (val instanceof Number) return ((Number) val).intValue();
        return defaultValue;
    }
    
    private boolean getBool(Map<String, Object> p, String key, boolean defaultValue) {
        Object val = p.get(key);
        if (val instanceof Boolean) return (Boolean) val;
        return defaultValue;
    }

    private <T> List<T> getList(Map<String, Object> p, String key) {
        return (List<T>) p.get(key); // Can be null, methods must handle
    }

    // --- Standard Response Helpers ---

    private Response ok(String message) {
        return Response.ok(Map.of("message", message)).build();
    }
    
    private Response ok(Object entity) {
        return Response.ok(entity).build();
    }

    private Response created(String message) {
        return Response.status(Response.Status.CREATED).entity(Map.of("message", message)).build();
    }
    
    private Response created(Object entity) {
        return Response.status(Response.Status.CREATED).entity(entity).build();
    }

    private Response badRequest(String message) {
        return Response.status(Response.Status.BAD_REQUEST).entity(Map.of("message", message)).build();
    }
    
    private Response handleError(Exception e) {
        e.printStackTrace(); // Log the full error
        // Don't leak internal error details, just send a generic message
        if (e instanceof IllegalArgumentException || e instanceof WebApplicationException) {
            return Response.status(Response.Status.BAD_REQUEST).entity(Map.of("message", e.getMessage())).build();
        }
        return Response.status(Response.Status.INTERNAL_SERVER_ERROR).entity(Map.of("message", "An internal server error occurred.")).build();
    }
}