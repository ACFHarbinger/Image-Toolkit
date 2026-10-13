// comfy_bridge.js - QWebChannel IPC bridge for embedded ComfyUI (#755)
//
// Injected via QWebEngineScript (MainWorld, DocumentReady) into the embedded
// ComfyUI canvas. Enables:
//  1. Active-node highlighting & auto-panning (driven by Gate E guidance)
//  2. Bidirectional parameter sync between Guided mode controls and LiteGraph
//  3. Native LoadImage node selection & file handoff
//
// Defensive by design: ComfyUI's frontend moves independently, so all DOM and
// LiteGraph accesses are guarded and fail open without breaking the web page.

(function() {
    if (window._comfyBridgeInjected) return;
    window._comfyBridgeInjected = true;

    var bridge = null;
    var pendingHighlight = null;
    var pendingParamSync = [];

    function log(msg) {
        console.log("[comfy_bridge] " + msg);
        if (bridge && typeof bridge.log === "function") {
            try { bridge.log(String(msg)); } catch (e) {}
        }
    }

    function getGraph() {
        var app = window.app;
        return (app && app.graph) ? app.graph : (window.graph || null);
    }

    function getCanvas() {
        var app = window.app;
        if (app && app.canvas) return app.canvas;
        if (window.LGraphCanvas && window.LGraphCanvas.active_canvas) {
            return window.LGraphCanvas.active_canvas;
        }
        return null;
    }

    function findNode(graph, id) {
        if (!graph) return null;
        var numId = Number(id);
        var node = (!isNaN(numId) && typeof graph.getNodeById === "function")
            ? graph.getNodeById(numId)
            : null;
        if (!node && typeof graph.getNodeById === "function") {
            node = graph.getNodeById(id);
        }
        if (!node && Array.isArray(graph._nodes)) {
            node = graph._nodes.find(function(n) {
                return n && (String(n.id) === String(id) || String(n.title) === String(id));
            });
        }
        return node || null;
    }

    function highlightNode(nodeId) {
        try {
            var graph = getGraph();
            var canvas = getCanvas();

            if (!graph || !canvas) {
                log("Highlight deferred: graph/canvas not ready for node " + nodeId);
                pendingHighlight = nodeId;
                return false;
            }

            var node = findNode(graph, nodeId);
            if (!node) {
                log("Node not found: " + nodeId);
                if (bridge && typeof bridge.notifyNodeHighlightFailed === "function") {
                    bridge.notifyNodeHighlightFailed(String(nodeId), "Node not found in graph");
                }
                return false;
            }

            // 1. Center viewport on node
            if (typeof canvas.centerOnNode === "function") {
                canvas.centerOnNode(node);
            } else if (canvas.ds && node.pos) {
                var w = canvas.canvas ? canvas.canvas.width : window.innerWidth;
                var h = canvas.canvas ? canvas.canvas.height : window.innerHeight;
                var s = canvas.ds.scale || 1.0;
                var nw = (node.size && node.size[0]) ? node.size[0] : 120;
                var nh = (node.size && node.size[1]) ? node.size[1] : 80;
                canvas.ds.offset[0] = (w / 2) - (node.pos[0] + nw / 2) * s;
                canvas.ds.offset[1] = (h / 2) - (node.pos[1] + nh / 2) * s;
            }

            // 2. Select node
            if (typeof canvas.selectNode === "function") {
                canvas.selectNode(node);
            } else if (typeof canvas.selectNodes === "function") {
                canvas.selectNodes([node]);
            }

            // 3. Visual pulse / highlight styling (amber border)
            var originalBoxColor = node.boxcolor;
            node.boxcolor = "#ff9900";
            node._bridgeHighlighted = true;
            if (typeof canvas.setDirty === "function") {
                canvas.setDirty(true, true);
            } else if (typeof graph.setDirtyCanvas === "function") {
                graph.setDirtyCanvas(true, true);
            }

            setTimeout(function() {
                try {
                    if (node && node._bridgeHighlighted) {
                        node.boxcolor = originalBoxColor;
                        delete node._bridgeHighlighted;
                        if (canvas && typeof canvas.setDirty === "function") {
                            canvas.setDirty(true, true);
                        } else if (graph && typeof graph.setDirtyCanvas === "function") {
                            graph.setDirtyCanvas(true, true);
                        }
                    }
                } catch (e) {}
            }, 2500);

            log("Highlighted node " + nodeId);
            if (bridge && typeof bridge.notifyNodeHighlighted === "function") {
                bridge.notifyNodeHighlighted(String(node.id));
            }
            return true;
        } catch (err) {
            log("Error highlighting node " + nodeId + ": " + err);
            if (bridge && typeof bridge.notifyNodeHighlightFailed === "function") {
                bridge.notifyNodeHighlightFailed(String(nodeId), String(err));
            }
            return false;
        }
    }

    function setNodeWidgetValue(nodeId, widgetName, rawValue) {
        try {
            var graph = getGraph();
            var canvas = getCanvas();
            if (!graph) {
                pendingParamSync.push({ nodeId: nodeId, widgetName: widgetName, value: rawValue });
                return false;
            }

            var node = findNode(graph, nodeId);
            if (!node) {
                log("setNodeWidgetValue: node " + nodeId + " not found");
                return false;
            }

            var parsedValue = rawValue;
            if (typeof rawValue === "string") {
                try {
                    parsedValue = JSON.parse(rawValue);
                } catch (e) {
                    parsedValue = rawValue;
                }
            }

            var updated = false;
            var targetName = String(widgetName).toLowerCase();

            if (Array.isArray(node.widgets)) {
                for (var i = 0; i < node.widgets.length; i++) {
                    var w = node.widgets[i];
                    if (w && w.name && String(w.name).toLowerCase() === targetName) {
                        window._bridgeUpdating = true;
                        try {
                            w.value = parsedValue;
                            if (typeof w.callback === "function") {
                                w.callback(w.value, canvas, node, node.pos, {});
                            }
                        } finally {
                            window._bridgeUpdating = false;
                        }
                        updated = true;
                        break;
                    }
                }
            }

            if (updated && Array.isArray(node.widgets_values) && Array.isArray(node.widgets)) {
                for (var j = 0; j < node.widgets.length; j++) {
                    if (node.widgets[j] && String(node.widgets[j].name).toLowerCase() === targetName) {
                        node.widgets_values[j] = parsedValue;
                        break;
                    }
                }
            }

            if (updated) {
                if (typeof graph.setDirtyCanvas === "function") {
                    graph.setDirtyCanvas(true, true);
                } else if (canvas && typeof canvas.setDirty === "function") {
                    canvas.setDirty(true, true);
                }
                log("Synced widget " + widgetName + " on node " + nodeId + " to " + JSON.stringify(parsedValue));
            }
            return updated;
        } catch (err) {
            log("Error setting widget " + widgetName + " on node " + nodeId + ": " + err);
            return false;
        }
    }

    function hookNode(node) {
        if (!node || !Array.isArray(node.widgets) || node._bridgeHooked) return;
        node._bridgeHooked = true;

        node.widgets.forEach(function(widget) {
            if (!widget) return;
            var origCallback = widget.callback;
            widget.callback = function(value) {
                try {
                    if (typeof origCallback === "function") {
                        origCallback.apply(this, arguments);
                    }
                } catch (e) {
                    console.error("[comfy_bridge] original widget callback error:", e);
                }
                if (!window._bridgeUpdating && bridge && typeof bridge.notifyParamChanged === "function") {
                    try {
                        var vStr = (typeof value === "object" && value !== null)
                            ? JSON.stringify(value)
                            : String(value);
                        bridge.notifyParamChanged(String(node.id), String(widget.name), vStr);
                    } catch (e) {
                        console.error("[comfy_bridge] notifyParamChanged error:", e);
                    }
                }
            };
        });
    }

    function hookAllNodes(graph) {
        if (!graph) return;
        if (Array.isArray(graph._nodes)) {
            graph._nodes.forEach(hookNode);
        }
    }

    function initGraphHooks() {
        var graph = getGraph();
        if (!graph) return false;

        hookAllNodes(graph);

        var origOnNodeAdded = graph.onNodeAdded;
        graph.onNodeAdded = function(node) {
            if (typeof origOnNodeAdded === "function") {
                try { origOnNodeAdded.apply(this, arguments); } catch (e) {}
            }
            hookNode(node);
        };

        if (pendingHighlight !== null) {
            var target = pendingHighlight;
            pendingHighlight = null;
            highlightNode(target);
        }

        if (pendingParamSync.length > 0) {
            var queue = pendingParamSync.slice();
            pendingParamSync = [];
            queue.forEach(function(item) {
                setNodeWidgetValue(item.nodeId, item.widgetName, item.value);
            });
        }

        return true;
    }

    function connectChannel() {
        if (typeof QWebChannel === "undefined") {
            setTimeout(connectChannel, 100);
            return;
        }

        if (typeof qt === "undefined" || !qt.webChannelTransport) {
            setTimeout(connectChannel, 100);
            return;
        }

        new QWebChannel(qt.webChannelTransport, function(channel) {
            bridge = channel.objects.comfyBridge;
            window.comfyBridge = bridge;
            log("QWebChannel connected to comfyBridge");

            if (bridge) {
                if (bridge.highlight_node_requested) {
                    bridge.highlight_node_requested.connect(function(nodeId) {
                        highlightNode(nodeId);
                    });
                }
                if (bridge.sync_param_requested) {
                    bridge.sync_param_requested.connect(function(nodeId, widgetName, valueJson) {
                        setNodeWidgetValue(nodeId, widgetName, valueJson);
                    });
                }
                if (bridge.set_image_requested) {
                    bridge.set_image_requested.connect(function(nodeId, imageFilename) {
                        setNodeWidgetValue(nodeId, "image", imageFilename);
                    });
                }

                if (typeof bridge.notifyBridgeReady === "function") {
                    bridge.notifyBridgeReady();
                }
            }

            var pollCount = 0;
            var pollTimer = setInterval(function() {
                pollCount++;
                if (initGraphHooks() || pollCount > 80) {
                    clearInterval(pollTimer);
                }
            }, 250);
        });
    }

    window.comfyBridgeHelper = {
        highlightNode: highlightNode,
        setNodeWidgetValue: setNodeWidgetValue,
        findNode: findNode,
        initGraphHooks: initGraphHooks,
        getGraph: getGraph,
        getCanvas: getCanvas
    };

    if (document.readyState === "complete" || document.readyState === "interactive") {
        connectChannel();
    } else {
        window.addEventListener("DOMContentLoaded", connectChannel);
    }
})();
