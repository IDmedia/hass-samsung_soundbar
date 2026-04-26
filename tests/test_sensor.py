"""Tests for Samsung Soundbar diagnostic sensors."""
from unittest.mock import AsyncMock, MagicMock, patch

import homeassistant.helpers.device_registry as dr
from homeassistant.const import CONF_HOST

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsung_soundbar.const import DOMAIN, DEFAULT_PORT, CONF_PORT

BASE_ENTRY_DATA = {
  CONF_HOST: "192.168.1.100",
  CONF_PORT: DEFAULT_PORT,
}

BASE_MAIN_INFO = {'spkmacaddr': '70:b1:3d:ce:19:64', 'spkmodelname': 'HW-Q900A'}
BASE_SW_VERSION = {'version': 'HW-Q900AWWB-1011.1', 'displayversion': 'HW-Q900AWWB-1011.1'}


async def _setup_sensors(hass, data=None):
  if data is None:
    data = BASE_ENTRY_DATA
  entry = MockConfigEntry(domain=DOMAIN, unique_id=data[CONF_HOST], data=data)
  entities = []
  with patch("custom_components.samsung_soundbar.sensor.async_get_clientsession"):
    from custom_components.samsung_soundbar.sensor import async_setup_entry
    await async_setup_entry(hass, entry, lambda e, *_: entities.extend(e))
  return entities, entry


# --- setup ---

async def test_setup_creates_two_entities(hass):
  """async_setup_entry creates exactly 2 sensor entities."""
  entities, _ = await _setup_sensors(hass)
  assert len(entities) == 2


async def test_entity_unique_id_suffixes(hass):
  """Each sensor has the correct unique_id suffix."""
  entities, entry = await _setup_sensors(hass)
  suffixes = {e._attr_unique_id for e in entities}
  assert f"{entry.entry_id}_mac_address" in suffixes
  assert f"{entry.entry_id}_firmware" in suffixes


async def test_all_entities_share_device_identifier(hass):
  """All 3 sensors share the same device identifier (DOMAIN, entry_id)."""
  entities, entry = await _setup_sensors(hass)
  for entity in entities:
    assert (DOMAIN, entry.entry_id) in entity._attr_device_info['identifiers']


# --- MAC address sensor ---

async def test_mac_sensor_update_populates_value(hass):
  """MAC sensor async_update sets _attr_native_value from get_main_info."""
  entities, _ = await _setup_sensors(hass)
  mac_sensor = next(e for e in entities if e._attr_unique_id.endswith('_mac_address'))
  mac_sensor.api.get_main_info = AsyncMock(return_value=BASE_MAIN_INFO)

  await mac_sensor.async_update()

  assert mac_sensor._attr_native_value == '70:b1:3d:ce:19:64'


async def test_mac_sensor_device_info_connection(hass):
  """MAC sensor device_info includes the normalized MAC connection after update."""
  entities, _ = await _setup_sensors(hass)
  mac_sensor = next(e for e in entities if e._attr_unique_id.endswith('_mac_address'))
  mac_sensor.api.get_main_info = AsyncMock(return_value=BASE_MAIN_INFO)

  await mac_sensor.async_update()

  expected = (dr.CONNECTION_NETWORK_MAC, dr.format_mac('70:b1:3d:ce:19:64'))
  assert expected in mac_sensor._attr_device_info['connections']


async def test_mac_sensor_no_second_call(hass):
  """MAC sensor makes no additional API calls after first successful update."""
  entities, _ = await _setup_sensors(hass)
  mac_sensor = next(e for e in entities if e._attr_unique_id.endswith('_mac_address'))
  mac_sensor.api.get_main_info = AsyncMock(return_value=BASE_MAIN_INFO)

  await mac_sensor.async_update()
  await mac_sensor.async_update()

  mac_sensor.api.get_main_info.assert_called_once()


async def test_mac_sensor_offline_no_crash(hass):
  """MAC sensor does not raise and leaves native_value None when device is offline."""
  entities, _ = await _setup_sensors(hass)
  mac_sensor = next(e for e in entities if e._attr_unique_id.endswith('_mac_address'))
  mac_sensor.api.get_main_info = AsyncMock(return_value=None)

  await mac_sensor.async_update()

  assert mac_sensor._attr_native_value is None
  assert mac_sensor._fetched is False


# --- Firmware sensor ---

async def test_firmware_sensor_update_populates_value(hass):
  """Firmware sensor async_update sets _attr_native_value from get_software_version."""
  entities, _ = await _setup_sensors(hass)
  fw_sensor = next(e for e in entities if e._attr_unique_id.endswith('_firmware'))
  fw_sensor.api.get_software_version = AsyncMock(return_value=BASE_SW_VERSION)

  await fw_sensor.async_update()

  assert fw_sensor._attr_native_value == 'HW-Q900AWWB-1011.1'


async def test_firmware_sensor_device_info_sw_version(hass):
  """Firmware sensor device_info includes sw_version after update."""
  entities, _ = await _setup_sensors(hass)
  fw_sensor = next(e for e in entities if e._attr_unique_id.endswith('_firmware'))
  fw_sensor.api.get_software_version = AsyncMock(return_value=BASE_SW_VERSION)

  await fw_sensor.async_update()

  assert fw_sensor._attr_device_info['sw_version'] == 'HW-Q900AWWB-1011.1'


async def test_firmware_sensor_no_second_call(hass):
  """Firmware sensor makes no additional API calls after first successful update."""
  entities, _ = await _setup_sensors(hass)
  fw_sensor = next(e for e in entities if e._attr_unique_id.endswith('_firmware'))
  fw_sensor.api.get_software_version = AsyncMock(return_value=BASE_SW_VERSION)

  await fw_sensor.async_update()
  await fw_sensor.async_update()

  fw_sensor.api.get_software_version.assert_called_once()


async def test_firmware_sensor_offline_no_crash(hass):
  """Firmware sensor does not raise and leaves native_value None when offline."""
  entities, _ = await _setup_sensors(hass)
  fw_sensor = next(e for e in entities if e._attr_unique_id.endswith('_firmware'))
  fw_sensor.api.get_software_version = AsyncMock(return_value=None)

  await fw_sensor.async_update()

  assert fw_sensor._attr_native_value is None
  assert fw_sensor._fetched is False
