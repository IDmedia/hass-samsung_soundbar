"""Tests for Samsung Soundbar media player setup."""
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.samsung_soundbar.media_player import MultiRoomApi

from homeassistant.const import CONF_HOST, CONF_NAME

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsung_soundbar.const import (
  DOMAIN,
  DEFAULT_NAME,
  DEFAULT_PORT,
  DEFAULT_MAX_VOLUME,
  DEFAULT_POWER_OPTIONS,
  CONF_PORT,
  CONF_MAX_VOLUME,
  CONF_POWER_OPTIONS,
)

BASE_ENTRY_DATA = {
  CONF_HOST: "192.168.1.100",
  CONF_NAME: DEFAULT_NAME,
  CONF_PORT: DEFAULT_PORT,
  CONF_MAX_VOLUME: int(DEFAULT_MAX_VOLUME),
  CONF_POWER_OPTIONS: DEFAULT_POWER_OPTIONS,
}

BASE_YAML_CONFIG = {
  CONF_HOST: "192.168.1.100",
  CONF_NAME: DEFAULT_NAME,
  CONF_PORT: DEFAULT_PORT,
  CONF_MAX_VOLUME: DEFAULT_MAX_VOLUME,  # string, as YAML delivers it
  CONF_POWER_OPTIONS: DEFAULT_POWER_OPTIONS,
}


async def _setup_entry(hass, data):
  """Helper: set up a config entry and return the created entities."""
  entry = MockConfigEntry(domain=DOMAIN, unique_id=data[CONF_HOST], data=data)
  entities = []

  with patch("custom_components.samsung_soundbar.media_player.async_get_clientsession"):
    from custom_components.samsung_soundbar.media_player import async_setup_entry
    await async_setup_entry(hass, entry, lambda e, *_: entities.extend(e))

  return entities


async def _setup_platform(hass, config):
  """Helper: set up via YAML platform path and return the created entities."""
  entities = []

  with patch("custom_components.samsung_soundbar.media_player.async_get_clientsession"):
    from custom_components.samsung_soundbar.media_player import async_setup_platform
    await async_setup_platform(hass, config, lambda e, *_: entities.extend(e))

  return entities


# --- Config entry (UI) path ---

async def test_max_volume_applied_when_nonzero(hass):
  """When max_volume is between 1-99, the entity uses that value."""
  entities = await _setup_entry(hass, {**BASE_ENTRY_DATA, CONF_MAX_VOLUME: 25})
  assert entities[0]._max_volume == 25


async def test_max_volume_100_when_zero(hass):
  """When max_volume is 0 (no limit), the entity uses 100."""
  entities = await _setup_entry(hass, {**BASE_ENTRY_DATA, CONF_MAX_VOLUME: 0})
  assert entities[0]._max_volume == 100


async def test_max_volume_100_when_100(hass):
  """When max_volume is 100 (no limit), the entity uses 100."""
  entities = await _setup_entry(hass, {**BASE_ENTRY_DATA, CONF_MAX_VOLUME: 100})
  assert entities[0]._max_volume == 100


# --- YAML platform path ---

async def test_yaml_max_volume_applied(hass):
  """YAML setup uses the configured max_volume string value."""
  entities = await _setup_platform(hass, {**BASE_YAML_CONFIG, CONF_MAX_VOLUME: "25"})
  assert entities[0]._max_volume == 25


async def test_yaml_set_volume_scales_by_max_volume(hass):
  """set_volume_level sends volume * max_volume to the device."""
  entities = await _setup_platform(hass, {**BASE_YAML_CONFIG, CONF_MAX_VOLUME: "40"})
  entity = entities[0]
  entity.api.set_volume = AsyncMock()

  await entity.async_set_volume_level(0.5)

  entity.api.set_volume.assert_called_once_with(20.0)


async def test_yaml_update_scales_volume_from_device(hass):
  """async_update divides raw device volume by the default max_volume (40)."""
  entities = await _setup_platform(hass, BASE_YAML_CONFIG)
  entity = entities[0]
  entity.api.get_state = AsyncMock(return_value="1")
  entity.api.get_source = AsyncMock(return_value=["hdmi1", False])
  entity.api.get_volume = AsyncMock(return_value=["10"])
  entity.api.get_muted = AsyncMock(return_value=False)

  await entity.async_update()

  assert entity._volume == 0.25


# --- MultiRoomApi ---

def _make_api(xml_response):
  """Return a MultiRoomApi whose session returns the given XML string."""
  mock_response = MagicMock()
  mock_response.text = AsyncMock(return_value=xml_response)
  session = MagicMock()
  session.get = AsyncMock(return_value=mock_response)
  return MultiRoomApi("192.168.1.100", "56001", session, None)


async def test_get_speaker_name_plain(hass):
  """get_speaker_name returns the name when it is a plain string."""
  api = _make_api("<UIC><response result='ok'><spkname>Office Soundbar</spkname></response></UIC>")
  result = await api.get_speaker_name()
  assert result == ["Office Soundbar"]


async def test_get_speaker_name_cdata(hass):
  """get_speaker_name strips CDATA wrapper and returns the bare name."""
  api = _make_api("<UIC><response result='ok'><spkname><![CDATA[Office Soundbar]]></spkname></response></UIC>")
  result = await api.get_speaker_name()
  assert result == ["Office Soundbar"]

async def test_yaml_update_scales_volume_from_device_nondefault_max(hass):
  """async_update scaling works correctly with a non-default max_volume."""
  entities = await _setup_platform(hass, {**BASE_YAML_CONFIG, CONF_MAX_VOLUME: "60"})
  entity = entities[0]
  entity.api.get_state = AsyncMock(return_value="1")
  entity.api.get_source = AsyncMock(return_value=["hdmi1", False])
  entity.api.get_volume = AsyncMock(return_value=["15"])
  entity.api.get_muted = AsyncMock(return_value=False)

  await entity.async_update()

  assert entity._volume == 0.25
