from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN, DEFAULT_PORT, CONF_PORT
from .media_player import MultiRoomApi


async def async_setup_entry(hass, config_entry, async_add_entities):
    data = config_entry.data
    ip = data[CONF_HOST]
    port = data.get(CONF_PORT, DEFAULT_PORT)
    session = async_get_clientsession(hass)
    api = MultiRoomApi(ip, port, session, hass)
    unique_id = config_entry.entry_id

    async_add_entities([
        SamsungSoundbarMacAddressSensor(api, unique_id),
        SamsungSoundbarFirmwareSensor(api, unique_id),
    ])


class _SamsungSoundbarSensorBase(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, api, unique_id):
        self.api = api
        self._unique_id = unique_id
        self._fetched = False
        self._attr_native_value = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
        )

    async def async_update(self):
        if self._fetched:
            return
        await self._do_fetch()

    async def _do_fetch(self):
        raise NotImplementedError


class SamsungSoundbarMacAddressSensor(_SamsungSoundbarSensorBase):
    _attr_translation_key = "mac_address"

    def __init__(self, api, unique_id):
        super().__init__(api, unique_id)
        self._attr_unique_id = f"{unique_id}_mac_address"

    async def _do_fetch(self):
        info = await self.api.get_main_info()
        if info:
            mac = info.get('spkmacaddr')
            if mac:
                self._attr_native_value = mac
                self._attr_device_info = DeviceInfo(
                    identifiers={(DOMAIN, self._unique_id)},
                    connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))},
                )
                self._fetched = True


class SamsungSoundbarFirmwareSensor(_SamsungSoundbarSensorBase):
    _attr_translation_key = "firmware"

    def __init__(self, api, unique_id):
        super().__init__(api, unique_id)
        self._attr_unique_id = f"{unique_id}_firmware"

    async def _do_fetch(self):
        info = await self.api.get_software_version()
        if info:
            displayversion = info.get('displayversion')
            if displayversion:
                self._attr_native_value = displayversion
                self._attr_device_info = DeviceInfo(
                    identifiers={(DOMAIN, self._unique_id)},
                    sw_version=displayversion,
                )
                self._fetched = True
