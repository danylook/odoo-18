#!/usr/bin/env python3
"""
WF ROS Bridge — publishes Odoo panel piece poses to ROS2 topics.

Usage (inside a sourced ROS2 workspace):
    python3 wf_ros_bridge.py [--section L1_E8] [--db wally] [--host localhost]

Topics published:
    /wood_pieces/<data_id>/pose          geometry_msgs/PoseStamped   (one per piece)

Topics subscribed:
    /joint_states                        sensor_msgs/JointState
    /joint_trajectory_controller/controller_state

Utility method:
    node.send_joint_trajectory(positions)  → publishes to
    /joint_trajectory_controller/joint_trajectory  trajectory_msgs/JointTrajectory
"""

import argparse
import math
import sys

import psycopg2
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

# ── constants ────────────────────────────────────────────────────────────────
INCHES_TO_M = 0.0254          # SVG / DB units are imperial inches
PUBLISH_HZ  = 1.0             # pose re-publish rate

# 6-DOF arm joints (matches /joint_states name list from simulator)
ARM_JOINTS = [
    "joint_1",   # shoulder rotate
    "joint_2",   # shoulder pitch
    "joint_3",   # elbow
    "joint_4",   # wrist roll
    "joint_5",   # wrist pitch
    "joint_6",   # wrist rotate
]
GRIPPER_JOINTS = [
    "left_gripper_finger_joint",
    "right_gripper_finger_joint",
]
ALL_JOINTS = ARM_JOINTS + GRIPPER_JOINTS


# ── quaternion helpers ────────────────────────────────────────────────────────
def _quat_identity():
    """No rotation — flat / horizontal piece."""
    return dict(x=0.0, y=0.0, z=0.0, w=1.0)


def _quat_z90():
    """90° rotation around Z — vertical (stud) piece."""
    s = math.sqrt(2) / 2
    return dict(x=0.0, y=0.0, z=s, w=s)


# ── DB helpers ────────────────────────────────────────────────────────────────
def load_pieces(section_name: str, db: str, host: str, port: int,
                user: str, password: str) -> list[dict]:
    """Return all wf_panel_component rows for *section_name* as dicts."""
    conn = psycopg2.connect(
        dbname=db, host=host, port=port, user=user, password=password
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    wc.data_id,
                    wc.x,
                    wc.y,
                    wc.data_length,
                    wc.data_width,
                    wc.data_depth,
                    wc.data_orientation
                FROM wf_panel_component wc
                JOIN wf_panel_section ws ON wc.section_id = ws.id
                WHERE ws.name = %s
                ORDER BY wc.sequence, wc.id
                """,
                (section_name,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ── ROS2 node ─────────────────────────────────────────────────────────────────
class WFRosBridge(Node):
    """Publishes WF panel piece poses and interfaces with the robot arm."""

    def __init__(self, section_name: str, pieces: list[dict]):
        super().__init__("wf_ros_bridge")
        self.section_name = section_name
        self.pieces = pieces
        self._last_joint_state: JointState | None = None

        # ── publishers ───────────────────────────────────────────────────────
        self._pose_pubs: dict[str, object] = {}
        for piece in pieces:
            topic = f"/wood_pieces/{piece['data_id']}/pose"
            self._pose_pubs[piece["data_id"]] = self.create_publisher(
                PoseStamped, topic, 10
            )

        self._traj_pub = self.create_publisher(
            JointTrajectory,
            "/joint_trajectory_controller/joint_trajectory",
            10,
        )

        # ── subscribers ──────────────────────────────────────────────────────
        self.create_subscription(
            JointState,
            "/joint_states",
            self._on_joint_states,
            10,
        )
        self.create_subscription(
            JointState,   # controller_state also uses JointState-like header
            "/joint_trajectory_controller/controller_state",
            self._on_controller_state,
            10,
        )

        # ── timer ────────────────────────────────────────────────────────────
        self.create_timer(1.0 / PUBLISH_HZ, self._publish_poses)
        self.get_logger().info(
            f"WFRosBridge ready — section '{section_name}', "
            f"{len(pieces)} pieces, publishing at {PUBLISH_HZ} Hz"
        )

    # ── callbacks ─────────────────────────────────────────────────────────────
    def _on_joint_states(self, msg: JointState):
        self._last_joint_state = msg

    def _on_controller_state(self, msg):
        pass  # available for subclassing / logging

    # ── pose publisher ────────────────────────────────────────────────────────
    def _publish_poses(self):
        now = self.get_clock().now().to_msg()
        for piece in self.pieces:
            msg = self._piece_to_pose_stamped(piece, now)
            self._pose_pubs[piece["data_id"]].publish(msg)

    def _piece_to_pose_stamped(self, piece: dict, stamp) -> PoseStamped:
        """
        Convert a DB piece row to a geometry_msgs/PoseStamped.

        Coordinate mapping
        ------------------
        DB x, y  : SVG inches from panel origin (base_link frame)
        DB depth : inches; negative → sheathing offset behind the panel face
        orientation: 'horizontal' → identity quat, 'vertical' → 90° around Z
        """
        msg = PoseStamped()
        msg.header.stamp = stamp
        msg.header.frame_id = "base_link"

        # position — convert inches → metres
        msg.pose.position.x = float(piece["x"] or 0) * INCHES_TO_M
        msg.pose.position.y = float(piece["y"] or 0) * INCHES_TO_M
        # depth < 0 means sheathing sits behind the panel face
        depth_m = float(piece["data_depth"] or 0) * INCHES_TO_M
        msg.pose.position.z = depth_m

        # orientation
        if piece.get("data_orientation") == "vertical":
            q = _quat_z90()
        else:
            q = _quat_identity()

        msg.pose.orientation.x = q["x"]
        msg.pose.orientation.y = q["y"]
        msg.pose.orientation.z = q["z"]
        msg.pose.orientation.w = q["w"]

        return msg

    # ── trajectory helper ─────────────────────────────────────────────────────
    def send_joint_trajectory(
        self,
        positions: list[float],
        velocities: list[float] | None = None,
        time_sec: int = 2,
        time_nanosec: int = 0,
    ):
        """
        Publish a JointTrajectory to move the arm to *positions* (radians).

        Parameters
        ----------
        positions   : 6 target joint angles [joint_1 … joint_6] in radians
        velocities  : optional 6 velocities; defaults to zeros
        time_sec    : seconds to reach the target pose
        time_nanosec: nanoseconds component of time_from_start
        """
        if len(positions) != len(ARM_JOINTS):
            raise ValueError(
                f"positions must have {len(ARM_JOINTS)} values, got {len(positions)}"
            )
        if velocities is None:
            velocities = [0.0] * len(ARM_JOINTS)

        msg = JointTrajectory()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = ""
        msg.joint_names = ARM_JOINTS

        pt = JointTrajectoryPoint()
        pt.positions = list(positions)
        pt.velocities = list(velocities)
        pt.time_from_start = Duration(sec=time_sec, nanosec=time_nanosec)
        msg.points = [pt]

        self._traj_pub.publish(msg)
        self.get_logger().info(
            f"Trajectory sent: {[round(p, 3) for p in positions]} "
            f"in {time_sec}s"
        )

    # ── introspection ─────────────────────────────────────────────────────────
    def log_piece_summary(self):
        self.get_logger().info(f"Section: {self.section_name}")
        for p in self.pieces:
            x_m = (p["x"] or 0) * INCHES_TO_M
            y_m = (p["y"] or 0) * INCHES_TO_M
            self.get_logger().info(
                f"  {p['data_id']:45s}  "
                f"pos=({x_m:.3f}, {y_m:.3f})m  "
                f"size={p['data_length']:.3f}\"×{p['data_width']:.3f}\"  "
                f"orient={p['data_orientation'] or '-'}"
            )


# ── entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WF ROS Bridge")
    parser.add_argument("--section",  default="L1_E8",      help="Panel section name")
    parser.add_argument("--db",       default="wally",      help="PostgreSQL database")
    parser.add_argument("--host",     default="localhost",   help="PostgreSQL host")
    parser.add_argument("--port",     type=int, default=5432)
    parser.add_argument("--user",     default="odoo")
    parser.add_argument("--password", default="odoo")
    args, ros_args = parser.parse_known_args()

    # Load from DB before ROS init (fail early if DB is unreachable)
    print(f"Loading pieces for section '{args.section}' from {args.host}/{args.db}…")
    pieces = load_pieces(
        args.section, args.db, args.host, args.port, args.user, args.password
    )
    if not pieces:
        sys.exit(f"No pieces found for section '{args.section}'. Check DB.")
    print(f"  {len(pieces)} pieces loaded.")

    rclpy.init(args=ros_args)
    node = WFRosBridge(section_name=args.section, pieces=pieces)
    node.log_piece_summary()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
