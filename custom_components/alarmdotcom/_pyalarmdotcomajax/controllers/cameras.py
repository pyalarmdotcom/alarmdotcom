"""Alarm.com controller for cameras."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
from _pyalarmdotcomajax.const import API_URL_BASE, ResponseTypes
from _pyalarmdotcomajax.controllers.base import BaseController
from _pyalarmdotcomajax.exceptions import (
    AuthenticationFailed,
    UnexpectedResponse,
)
from _pyalarmdotcomajax.models.base import ResourceType
from _pyalarmdotcomajax.models.camera import Camera
from _pyalarmdotcomajax.models.jsonapi import Resource

from .base import device_controller

log = logging.getLogger(__name__)


@device_controller(ResourceType.CAMERA, Camera)
class CameraController(BaseController[Camera]):
    """Controller for cameras."""

    _resource_url_override = "video/devices/cameras"
    _is_device_controller = True

    def _device_filter(
        self, data: list[Resource] | Resource
    ) -> list[Resource] | Resource:
        """Return all supported cameras reported by the Alarm.com endpoint."""
        return data

    async def _refresh(
        self,
        pre_fetched: list[Resource] | None = None,
        resource_id: str | None = None,
        fetch_started: float | None = None,
    ) -> None:
        """Refresh controller directly from the camera endpoint."""
        url = f"{API_URL_BASE}{self._resource_url_override}"
        text_rsp = ""
        payload: dict[str, Any] | None = None

        for attempt in range(2):
            try:
                async with self._bridge.create_request(
                    "get",
                    url,
                    accept_types=ResponseTypes.JSON,
                    use_ajax_key=False,
                ) as rsp:
                    text_rsp = await rsp.text()

                    if rsp.status == 403:
                        log.debug(
                            "Alarm.com camera list endpoint returned 403 (NotAllowed). "
                            "Skipping camera list refresh and leaving camera controller empty."
                        )
                        self._resources.clear()
                        return

                    if rsp.status == 401 and attempt == 0:
                        await self._bridge.login()
                        continue

                    rsp.raise_for_status()
                    payload = json.loads(text_rsp)
                    break

            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403) and attempt == 0:
                    await self._bridge.login()
                    continue

                log.warning(
                    "Alarm.com camera list endpoint failed with HTTP %s, leaving camera controller empty.",
                    err.status,
                )
                self._resources.clear()
                return

            except json.JSONDecodeError:
                log.warning(
                    "Alarm.com camera list response was not valid JSON, leaving camera controller empty. "
                    "Response: %s",
                    text_rsp[:500],
                )
                self._resources.clear()
                return

            except AuthenticationFailed:
                if attempt == 0:
                    await self._bridge.login()
                    continue

                log.warning(
                    "Authentication failed while fetching camera list, leaving camera controller empty."
                )
                self._resources.clear()
                return

            except Exception as err:
                log.warning(
                    "Unexpected error while fetching camera list: %s. Leaving camera controller empty.",
                    err,
                )
                self._resources.clear()
                return
        else:
            log.warning(
                "Alarm.com camera list endpoint could not be fetched, leaving camera controller empty."
            )
            self._resources.clear()
            return

        if payload is None:
            self._resources.clear()
            return

        data = payload.get("data") if isinstance(payload, dict) else None
        included = payload.get("included") if isinstance(payload, dict) else None

        if data is None:
            self._resources.clear()
            return

        filtered = self._device_filter(data)

        self._resources.clear()

        if isinstance(filtered, list):
            for item in filtered:
                try:
                    await self._register_or_update_resource(item, included)
                except Exception as err:
                    log.error("Failed to register camera resource %s: %s", item, err)
        else:
            try:
                await self._register_or_update_resource(filtered, included)
            except Exception as err:
                log.error("Failed to register camera resource %s: %s", filtered, err)

        log.debug(
            "Camera controller items after refresh: %s",
            [f"{getattr(x, 'id', None)}:{getattr(x, 'name', None)}" for x in self.items],
        )

    async def get_live_stream_info(self, id: str) -> dict[str, Any] | None:
        """Fetch live WebRTC stream information for a camera."""
        url = f"{API_URL_BASE}video/videoSources/liveVideoHighestResSources/{id}"
        text_rsp = ""

        for attempt in range(2):
            try:
                async with self._bridge.create_request(
                    "get",
                    url,
                    accept_types=ResponseTypes.JSON,
                    use_ajax_key=False,
                ) as rsp:
                    text_rsp = await rsp.text()

                    if rsp.status == 401 and attempt == 0:
                        await self._bridge.login()
                        continue

                    rsp.raise_for_status()
                    payload = json.loads(text_rsp)

            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403) and attempt == 0:
                    await self._bridge.login()
                    continue
                raise UnexpectedResponse(
                    f"Failed to fetch camera stream info for {id}. HTTP {err.status}."
                ) from err

            except json.JSONDecodeError as err:
                raise UnexpectedResponse(
                    f"Camera stream info response was not valid JSON: {text_rsp[:500]}"
                ) from err

            except AuthenticationFailed:
                if attempt == 0:
                    await self._bridge.login()
                    continue
                raise

            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            included = payload.get("included", []) if isinstance(payload, dict) else []

            top_attrs = data.get("attributes", {})

            ice_servers_raw = top_attrs.get("iceServers")
            ice_servers: list[dict[str, Any]] = []
            if isinstance(ice_servers_raw, str) and ice_servers_raw:
                try:
                    ice_servers = json.loads(ice_servers_raw)
                except json.JSONDecodeError:
                    log.debug("Could not decode iceServers JSON for camera %s", id)

            proxy_config: dict[str, Any] | None = None
            end_to_end_config: dict[str, Any] | None = None

            for inc in included:
                inc_type = inc.get("type")
                attrs = inc.get("attributes", {})

                if inc_type == "video/videoSources/endToEndWebrtcConnectionInfo":
                    end_to_end_config = dict(attrs)
                    end_to_end_config["iceServers"] = ice_servers

                elif inc_type == "video/videoSources/proxyWebrtcConnectionInfo":
                    proxy_config = dict(attrs)
                    proxy_config["iceServers"] = ice_servers
                    proxy_config["proxyUrl"] = top_attrs.get("proxyUrl")
                    proxy_config["janusGatewayUrl"] = top_attrs.get("janusGatewayUrl")
                    proxy_config["janusToken"] = top_attrs.get("janusToken")
                    proxy_config["isMjpeg"] = top_attrs.get("isMjpeg", False)
                    proxy_config["urlEncoded"] = top_attrs.get("urlEncoded", False)
                    proxy_config["proxyStreamTimeoutTime"] = top_attrs.get("proxyStreamTimeoutTime")
                    proxy_config["streamType"] = "janus"

                    camera_suffix = str(id).split("-")[-1]
                    if camera_suffix.isdigit():
                        proxy_config["streamId"] = int(camera_suffix)

            if end_to_end_config is not None:
                end_to_end_config["streamType"] = "endToEnd"
                return end_to_end_config

            if proxy_config is not None:
                return proxy_config

            log.warning("No usable WebRTC connection info found for camera %s", id)
            return None

        return None
