"""P1.1 local identity and device-trust implementation."""

from app.control_plane.router import router
from app.control_plane.service import ControlPlaneService

__all__ = ["ControlPlaneService", "router"]
