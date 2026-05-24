# pylint: disable=pointless-statement
{
    "name": "WF ROS2 Bridge",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "summary": "Integración ROS2 — API REST, estado de piezas y visor 3D de avance",
    "category": "Manufacturing",
    "depends": [
        "WF_panel_manufacturing",
        "model_viewer_widget",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/wf_ros2_piece_status_views.xml",
        "views/mrp_production_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "https://unpkg.com/three@0.160.0/build/three.min.js",
            "WF_ros2_bridge/static/src/css/wf_panel_3d_viewer.css",
            "WF_ros2_bridge/static/src/xml/wf_panel_3d_viewer.xml",
            "WF_ros2_bridge/static/src/js/wf_panel_3d_viewer.js",
        ],
    },
    "installable": True,
    "application": False,
}
