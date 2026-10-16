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
    var moduleApp = null;
    var expectedTemplate = null;
    var hookedGraph = null;
    // ComfyUI can expose app only through its ES module.
    if (!window.app) {
        import("/scripts/app.js").then(function(module) { moduleApp = module.app; }).catch(function() {});
    }
    var pendingHighlight = null;
    var pendingParamSync = [];

    function log(msg) {
        console.log("[comfy_bridge] " + msg);
        if (bridge && typeof bridge.log === "function") {
            try { bridge.log(String(msg)); } catch (e) {}
        }
    }

    function getGraph() {
        var app = window.app || moduleApp;
        return (app && app.graph) ? app.graph : (window.graph || null);
    }

    function getCanvas() {
        var app = window.app || moduleApp;
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

    function matchesTemplate(graph) {
        if (!graph || !expectedTemplate || !Array.isArray(graph._nodes)) return false;
        var ids = Object.keys(expectedTemplate);
        if (ids.length !== graph._nodes.length) return false;
        return ids.every(function(id) {
            var spec = expectedTemplate[id];
            var node = findNode(graph, id);
            if (!node || (node.comfyClass || node.type) !== spec.class_type) return false;
            return Object.keys(spec.inputs || {}).every(function(name) {
                var value = spec.inputs[name];
                var input = (node.inputs || []).find(function(item) { return item.name === name; });
                if (!Array.isArray(value)) return !input || input.link == null;
                if (!input || input.link == null || !graph.links) return false;
                var link = typeof graph.links.get === "function" ? graph.links.get(input.link) : graph.links[input.link];
                return link && String(link.origin_id) === String(value[0]) && link.origin_slot === value[1];
            });
        });
    }

    function bindTemplate(raw) {
        try { expectedTemplate = JSON.parse(raw); } catch (e) { expectedTemplate = null; }
        var graph = getGraph();
        if (!matchesTemplate(graph) || !bridge) return;
        graph._nodes.forEach(function(node) {
            (node.widgets || []).forEach(function(widget) {
                if (widget && widget.name) bridge.notifyParamChanged(String(node.id), widget.name, JSON.stringify(widget.value));
            });
        });
    }

    async function loadTemplate(raw) {
        try {
            var workflow = (typeof raw === "string") ? JSON.parse(raw) : raw;
            if (!workflow || typeof workflow !== "object") {
                log("loadTemplate: invalid workflow payload");
                if (bridge && typeof bridge.notifyTemplateLoaded === "function") {
                    bridge.notifyTemplateLoaded(false);
                }
                return false;
            }

            expectedTemplate = workflow;
            var app = window.app || moduleApp;
            // Use ComfyUI's loader so node registration and links stay consistent.
            if (app && typeof app.loadApiJson === "function") {
                await app.loadApiJson(workflow);
            } else if (app && typeof app.loadGraphData === "function" && workflow.nodes) {
                await app.loadGraphData(workflow);
            } else {
                throw new Error("ComfyUI workflow loader is unavailable");
            }
            if (!matchesTemplate(getGraph())) {
                throw new Error("Loaded graph does not match the requested template");
            }

            var g = getGraph();
            var c = getCanvas();
            if (g) {
                initGraphHooks();
                if (typeof g.setDirtyCanvas === "function") {
                    g.setDirtyCanvas(true, true);
                }
            }
            if (c) {
                if (typeof c.setDirty === "function") {
                    c.setDirty(true, true);
                }
                if (typeof c.draw === "function") {
                    c.draw(true, true);
                }
            }

            bindTemplate(typeof raw === "string" ? raw : JSON.stringify(workflow));
            log("Loaded template into canvas (" + Object.keys(workflow).length + " nodes)");
            if (bridge && typeof bridge.notifyTemplateLoaded === "function") {
                bridge.notifyTemplateLoaded(true);
            }
            return true;
        } catch (err) {
            log("Error loading template: " + err);
            if (bridge && typeof bridge.notifyTemplateLoaded === "function") {
                bridge.notifyTemplateLoaded(false);
            }
            return false;
        }
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
                canvas.ds.offset[0] = (w / 2) / s - (node.pos[0] + nw / 2);
                canvas.ds.offset[1] = (h / 2) / s - (node.pos[1] + nh / 2);
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

            if (!matchesTemplate(graph)) return false;
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
        if (!node || !Array.isArray(node.widgets)) return;

        node.widgets.forEach(function(widget) {
            if (!widget || widget._bridgeHooked) return;
            widget._bridgeHooked = true;
            var origCallback = widget.callback;
            widget.callback = function(value) {
                try {
                    if (typeof origCallback === "function") {
                        origCallback.apply(this, arguments);
                    }
                } catch (e) {
                    console.error("[comfy_bridge] original widget callback error:", e);
                }
                if (!window._bridgeUpdating && matchesTemplate(getGraph()) && bridge && typeof bridge.notifyParamChanged === "function") {
                    try {
                        var vStr = JSON.stringify(value);
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
        if (hookedGraph === graph) return true;
        hookedGraph = graph;
        if (expectedTemplate) bindTemplate(JSON.stringify(expectedTemplate));

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
                if (bridge.bind_template_requested) {
                    bridge.bind_template_requested.connect(bindTemplate);
                }
                if (bridge.load_template_requested) {
                    bridge.load_template_requested.connect(loadTemplate);
                }
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

            setInterval(initGraphHooks, 250);
        });
    }

    window.comfyBridgeHelper = {
        highlightNode: highlightNode,
        setNodeWidgetValue: setNodeWidgetValue,
        findNode: findNode,
        initGraphHooks: initGraphHooks,
        getGraph: getGraph,
        getCanvas: getCanvas,
        bindTemplate: bindTemplate,
        matchesTemplate: matchesTemplate,
        loadTemplate: loadTemplate
    };

    if (document.readyState === "complete" || document.readyState === "interactive") {
        connectChannel();
    } else {
        window.addEventListener("DOMContentLoaded", connectChannel);
    }
})();
