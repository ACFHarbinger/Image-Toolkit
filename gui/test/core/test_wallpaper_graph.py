import pytest
from PySide6.QtCore import Qt, QPointF
from gui.src.tabs.core.elements.graph.wallpaper_graph_scene import WallpaperGraphScene
from gui.src.tabs.core.elements.graph.data import GraphData

pytestmark = pytest.mark.gui


def test_wallpaper_graph_scene_connection_mode(q_app):
    scene = WallpaperGraphScene()
    graph = GraphData()
    scene.load_graph(graph)

    # Add a couple of nodes
    n1_id = scene.add_node("dummy1.png", QPointF(0, 0))
    n2_id = scene.add_node("dummy2.png", QPointF(200, 200))

    # Verify nodes are in scene
    assert n1_id in scene._node_items
    assert n2_id in scene._node_items

    # Start connection mode from node 1
    scene.start_connection_mode(n1_id)
    # Process events to allow the deferred connection mode start to run
    q_app.processEvents()
    
    assert scene._connecting_source_node_id == n1_id
    assert scene._temp_connection_pos is not None

    # Hover over empty space (no node)
    scene.handle_connection_move(QPointF(-50, -50))
    assert scene._hovered_target_node is None
    assert scene._temp_connection_pos == QPointF(-50, -50)

    # Hover over node 2
    # Node 2 is at (200, 200) with width 140, height 115
    scene.handle_connection_move(QPointF(250, 250))
    assert scene._hovered_target_node == scene._node_items[n2_id]
    assert scene._node_items[n2_id]._hovered_orange is True
    assert scene._temp_connection_pos == QPointF(250, 250)

    # Press left mouse button on node 2 to connect them
    scene.handle_connection_press(QPointF(250, 250), Qt.MouseButton.LeftButton)

    # Process events to allow QTimer.singleShot(0, ...) to run
    q_app.processEvents()

    # Verify edge is added between n1 and n2
    edges = scene._graph.edges
    assert len(edges) == 1
    assert edges[0].source_id == n1_id
    assert edges[0].target_id == n2_id

    # Verify connection mode is ended
    assert scene._connecting_source_node_id is None
    assert scene._temp_connection_pos is None
    assert scene._node_items[n2_id]._hovered_orange is False


def test_wallpaper_graph_scene_cancel_connection_right_click(q_app):
    scene = WallpaperGraphScene()
    graph = GraphData()
    scene.load_graph(graph)

    # Add a node
    n1_id = scene.add_node("dummy1.png", QPointF(0, 0))

    # Start connection mode
    scene.start_connection_mode(n1_id)
    q_app.processEvents()
    
    assert scene._connecting_source_node_id == n1_id
    assert scene._temp_connection_pos is not None

    # Right click to cancel
    scene.handle_connection_press(QPointF(150, 150), Qt.MouseButton.RightButton)
    q_app.processEvents()

    # Verify connection mode ended without creating any edge
    assert scene._connecting_source_node_id is None
    assert scene._temp_connection_pos is None
    assert len(scene._graph.edges) == 0
