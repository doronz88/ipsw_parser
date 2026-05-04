import logging
import os.path
from functools import cached_property
from typing import Optional

from ipsw_parser.exceptions import IpswException


class TSSResponse(dict):
    """Dictionary wrapper for TSS response payloads."""

    @property
    def ap_img4_ticket(self):
        """Return the AP IMG4 ticket from the TSS response."""
        ticket = self.get("ApImg4Ticket")

        if ticket is None:
            raise IpswException("TSS response doesn't contain a ApImg4Ticket")

        return ticket

    @property
    def bb_ticket(self):
        """Return the baseband ticket from the TSS response, if present."""
        return self.get("BBTicket")

    def get_path_by_entry(self, component: str):
        """Return the path for a component entry in the TSS response."""
        node = self.get(component)
        if node is not None:
            return node.get("Path")

        return None


class Component:
    """Resolved view of a build identity component."""

    def __init__(
        self,
        build_identity,
        name: str,
        tss: TSSResponse = None,
        data: Optional[bytes] = None,
        path: Optional[str] = None,
    ):
        """Create a component view for a build identity entry."""
        self.logger = logging.getLogger(__name__)
        self._tss = tss
        self.build_identity = build_identity
        self.name = name
        self._data = data
        self._path = path

    @cached_property
    def path(self) -> str:
        """Resolve the component path from TSS data or the build manifest."""
        if self._path:
            return self._path

        path = None
        if self._tss:
            path = self._tss.get_path_by_entry(self.name)

            if path is None:
                self.logger.debug(f"NOTE: No path for component {self.name} in TSS, will fetch from build_identity")

        if path is None:
            path = self.build_identity.get_component_path(self.name)

        if path is None:
            raise IpswException(f"Failed to find component path for: {self.name}")

        return path

    @cached_property
    def data(self) -> bytes:
        """Return the component payload bytes."""
        if self._data is None:
            self.logger.debug(f"Extracting {os.path.basename(self.path)} ({self.path})")
            return self.build_identity.build_manifest.ipsw.read(self.path)
        return self._data
