"""WebSocket update module."""

# List of device types and the events that they support is listed at
# https://answers.alarm.com/Customer/Website_and_App/User_Management/Web_App_Users/Do_the_app_and_website_update_in_real_time#To_refresh_the_Customer_Website.
from _pyalarmdotcomajax.websocket.client import ConnectionEvent, WebSocketState

__all__: tuple[str, ...] = ("ConnectionEvent", "WebSocketState")
