"""Node.js harness tests for comfy_bridge.js behavior (#755)."""
import json
import shutil
import subprocess

import pytest

from gui.src.tabs.models.gen.comfy_bridge import get_comfy_bridge_js


def test_javascript_sync_requires_matching_graph_and_preserves_strings():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for the bridge behavior harness")
    source = get_comfy_bridge_js()
    harness = """
const assert = require('node:assert/strict');
global.window = {app: null};
global.document = {readyState: "complete"};
global.setTimeout = function() {};
global.setInterval = function() {};
let calls = 0;
const widget = {name: "text", value: "existing", callback() { calls++; }};
const item = {id: 1, type: "Text", inputs: [], widgets: [widget], widgets_values: ["existing"]};
const graph = {_nodes: [item], getNodeById(id) {return this._nodes.find(n => String(n.id)===String(id));}, setDirtyCanvas() {}};
window.app = {graph, canvas: {}};
eval(SOURCE);
const helper = window.comfyBridgeHelper;
assert.equal(helper.setNodeWidgetValue("1", "text", '"no"'), false);
helper.bindTemplate(JSON.stringify({"1": {class_type: "Text", inputs: {text: "default"}}}));
assert.equal(widget.value, "existing"); // Binding must not push defaults.
assert.equal(helper.setNodeWidgetValue("1", "text", '"123"'), true);
assert.equal(widget.value, "123");
item.type = "Unrelated";
assert.equal(helper.setNodeWidgetValue("1", "text", '"bad"'), false);
assert.equal(widget.value, "123");
item.type = "Text";
helper.initGraphHooks();
helper.initGraphHooks();
const before = calls;
widget.callback("value");
assert.equal(calls, before + 1);
"""
    result = subprocess.run([node, "-"], input=harness.replace("SOURCE", json.dumps(source)),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_javascript_load_template_enables_sync():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js required for the bridge behavior harness")
    source = get_comfy_bridge_js()
    harness = """
const assert = require('node:assert/strict');
global.window = {app: null};
global.document = {readyState: "complete"};
global.setTimeout = function() {};
global.setInterval = function() {};

// Graph begins empty:
const graph = {_nodes: [], getNodeById(id) {return this._nodes.find(n => String(n.id)===String(id));}, setDirtyCanvas() {}};
window.app = {graph, canvas: {}};
eval(SOURCE);
const helper = window.comfyBridgeHelper;

assert.equal(helper.matchesTemplate(graph), false);
assert.equal(helper.setNodeWidgetValue("1", "ckpt_name", '"new_ckpt.safetensors"'), false);

// 1. Fallback graph construction when app.loadApiJson is not present:
const template = {
  "1": { class_type: "CheckpointLoaderSimple", inputs: { ckpt_name: "sd_xl.safetensors" } },
  "2": { class_type: "CLIPTextEncode", inputs: { text: "anime girl", clip: ["1", 1] } }
};
const res1 = helper.loadTemplate(JSON.stringify(template));
assert.equal(res1, true);
assert.equal(helper.matchesTemplate(graph), true);
assert.equal(helper.setNodeWidgetValue("1", "ckpt_name", '"v1-5.safetensors"'), true);
const n1 = graph.getNodeById("1");
assert.equal(n1.widgets.find(w => w.name === "ckpt_name").value, "v1-5.safetensors");

// 2. ComfyApp.loadApiJson path when present:
let apiJsonCalledWith = null;
window.app.loadApiJson = function(wf) {
  apiJsonCalledWith = wf;
  graph._nodes = [
    {id: 1, comfyClass: "CheckpointLoaderSimple", inputs: [], widgets: [{name: "ckpt_name", value: "init"}]},
    {id: 2, comfyClass: "CLIPTextEncode", inputs: [{name: "clip", link: 1}], widgets: [{name: "text", value: "init"}]}
  ];
  graph.links = { 1: { origin_id: "1", origin_slot: 1 } };
};
const res2 = helper.loadTemplate(JSON.stringify(template));
assert.equal(res2, true);
assert.notEqual(apiJsonCalledWith, null);
assert.equal(apiJsonCalledWith["1"].class_type, "CheckpointLoaderSimple");
assert.equal(helper.matchesTemplate(graph), true);
assert.equal(helper.setNodeWidgetValue("2", "text", '"masterpiece"'), true);
const n2 = graph.getNodeById("2");
assert.equal(n2.widgets.find(w => w.name === "text").value, "masterpiece");
"""
    result = subprocess.run([node, "-"], input=harness.replace("SOURCE", json.dumps(source)),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
