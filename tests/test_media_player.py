"""Tests for Samsung Soundbar media player setup."""
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.samsung_soundbar.media_player import MultiRoomApi

from homeassistant.const import CONF_HOST, CONF_NAME, STATE_OFF

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
  entity.api.get_source = AsyncMock(return_value={'mode': 'hdmi1', 'submode': False})
  entity.api.get_volume = AsyncMock(return_value="10")
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


def _make_api_multi(xml_responses):
  """Return a MultiRoomApi whose session yields xml_responses in sequence."""
  mock_response = MagicMock()
  mock_response.text = AsyncMock(side_effect=xml_responses)
  session = MagicMock()
  session.get = AsyncMock(return_value=mock_response)
  return MultiRoomApi("192.168.1.100", "56001", session, None)


# --- _exec_get_xml ---

VOLUME_XML = '<UIC><method>VolumeLevel</method><response result="ok"><volume>10</volume></response></UIC>'
POWER_XML  = '<UIC><method>PowerStatus</method><response result="ok"><powerStatus>1</powerStatus></response></UIC>'
PUSH_XML   = '<UIC><method>PowerStatus</method><response result="ok"><powerStatus>1</powerStatus></response></UIC>'


async def test_exec_get_xml_happy_path():
  """Returns the response dict when the method matches on the first attempt."""
  api = _make_api(VOLUME_XML)
  result = await api._exec_get_xml('UIC', 'GetVolume', 'VolumeLevel')
  assert result == {'@result': 'ok', 'volume': '10'}


async def test_exec_get_xml_no_data():
  """Returns None immediately when _exec_cmd returns no data (e.g. timeout)."""
  api = _make_api_multi([None])
  with patch.object(api, '_exec_cmd', AsyncMock(return_value=None)):
    result = await api._exec_get_xml('UIC', 'GetVolume', 'VolumeLevel')
  assert result is None


async def test_exec_get_xml_parse_exception():
  """Returns None when the response is not valid XML."""
  api = _make_api("not xml at all")
  result = await api._exec_get_xml('UIC', 'GetVolume', 'VolumeLevel')
  assert result is None


async def test_exec_get_xml_wrong_result():
  """Returns None when the response result is not 'ok'."""
  api = _make_api('<UIC><method>VolumeLevel</method><response result="ng"><volume>10</volume></response></UIC>')
  result = await api._exec_get_xml('UIC', 'GetVolume', 'VolumeLevel')
  assert result is None


async def test_exec_get_xml_retry_on_wrong_method():
  """Retries when the first response has the wrong method, succeeds on the second."""
  api = _make_api_multi([PUSH_XML, VOLUME_XML])
  with patch.object(api, '_exec_cmd', AsyncMock(side_effect=[PUSH_XML, VOLUME_XML])):
    result = await api._exec_get_xml('UIC', 'GetVolume', 'VolumeLevel')
  assert result == {'@result': 'ok', 'volume': '10'}


async def test_exec_get_xml_exhausts_retries():
  """Returns None after all retries are consumed by wrong-method responses."""
  push_responses = [PUSH_XML] * 3
  with patch('custom_components.samsung_soundbar.media_player.MultiRoomApi._exec_cmd',
             AsyncMock(side_effect=push_responses)):
    api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
    result = await api._exec_get_xml('UIC', 'GetVolume', 'VolumeLevel', retries=3)
  assert result is None


async def test_exec_get_xml_timeout_passed_through():
  """The timeout argument is forwarded to _exec_cmd."""
  api = _make_api(VOLUME_XML)
  with patch.object(api, '_exec_cmd', AsyncMock(return_value=VOLUME_XML)) as mock_cmd:
    await api._exec_get_xml('UIC', 'GetVolume', 'VolumeLevel', timeout=0.5)
  mock_cmd.assert_called_once_with('UIC', '<name>GetVolume</name>', timeout=0.5)


# --- get_* tests ---

async def test_get_speaker_name_plain():
  """get_speaker_name returns the name as a plain string."""
  api = _make_api('<UIC><method>SpkName</method><response result="ok"><spkname>Office Soundbar</spkname></response></UIC>')
  result = await api.get_speaker_name()
  assert result == "Office Soundbar"

async def test_get_speaker_name_cdata():
  """get_speaker_name strips CDATA transparently via xmltodict."""
  api = _make_api('<UIC><method>SpkName</method><response result="ok"><spkname><![CDATA[Office Soundbar]]></spkname></response></UIC>')
  result = await api.get_speaker_name()
  assert result == "Office Soundbar"

async def test_get_state_on():
  """get_state returns '1' when the soundbar is powered on."""
  api = _make_api('<UIC><method>PowerStatus</method><response result="ok"><powerStatus>1</powerStatus></response></UIC>')
  result = await api.get_state()
  assert result == "1"

async def test_get_volume():
  """get_volume returns the volume level as a string."""
  api = _make_api('<UIC><method>VolumeLevel</method><response result="ok"><volume>15</volume></response></UIC>')
  result = await api.get_volume()
  assert result == "15"

# --- get_muted ---
async def test_get_muted_when_muted():
  """get_muted returns True when the device reports muted."""
  api = _make_api('<UIC><method>MuteStatus</method><response result="ok"><mute>on</mute></response></UIC>')
  result = await api.get_muted()
  assert result is True

async def test_get_muted_when_unmuted():
  """get_muted returns False when the device reports unmuted."""
  api = _make_api('<UIC><method>MuteStatus</method><response result="ok"><mute>off</mute></response></UIC>')
  result = await api.get_muted()
  assert result is False


async def test_get_radio_info():
  """get_radio_info returns the title as a string."""
  api = _make_api('<CPM><method>RadioInfo</method><response result="ok"><title>My Song</title></response></CPM>')
  result = await api.get_radio_info()
  assert result == "My Song"

async def test_get_radio_info_cdata_stripped():
  """get_radio_info strips CDATA transparently via xmltodict."""
  api = _make_api('<CPM><method>RadioInfo</method><response result="ok"><title><![CDATA[My Song]]></title></response></CPM>')
  result = await api.get_radio_info()
  assert result == "My Song"

async def test_get_radio_image():
  """get_radio_image returns the thumbnail URL as a string."""
  api = _make_api('<CPM><method>RadioInfo</method><response result="ok"><thumbnail>http://example.com/img.jpg</thumbnail></response></CPM>')
  result = await api.get_radio_image()
  assert result == "http://example.com/img.jpg"

async def test_get_source_physical_input(hass):
  """get_source returns {'mode': function, 'submode': False} for physical inputs like hdmi1."""
  api = _make_api('<UIC><method>CurrentFunc</method><response result="ok"><function>hdmi1</function><submode></submode></response></UIC>')
  result = await api.get_source()
  assert result == {'mode': 'hdmi1', 'submode': False}

async def test_get_source_wifi_tunein(hass):
  """get_source returns {'mode': 'wifi', 'submode': 'TuneIn'} when submode is 'cp' (streaming)."""
  api = _make_api('<UIC><method>CurrentFunc</method><response result="ok"><function>wifi</function><submode>cp</submode></response></UIC>')
  result = await api.get_source()
  assert result == {'mode': 'wifi', 'submode': 'TuneIn'}

async def test_get_source_wifi_other_submode(hass):
  """get_source returns {'mode': 'wifi', 'submode': False} for wifi with a non-cp submode."""
  api = _make_api('<UIC><method>CurrentFunc</method><response result="ok"><function>wifi</function><submode>dlna</submode></response></UIC>')
  result = await api.get_source()
  assert result == {'mode': 'wifi', 'submode': False}

async def test_get_source_wifi_on_exhausted_retries():
  """get_source falls back to wifi after all retries return push events instead of CurrentFunc."""
  api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
  with patch.object(api, '_exec_cmd', AsyncMock(side_effect=[PUSH_XML, PUSH_XML, PUSH_XML])), \
       patch('custom_components.samsung_soundbar.media_player.is_airplay_active',
             new=AsyncMock(return_value=False)):
    result = await api.get_source()
  assert result == {'mode': 'wifi', 'submode': False}


async def test_get_source_retries_past_push_event():
  """get_source discards a push event and succeeds on the next attempt."""
  good = '<UIC><method>CurrentFunc</method><response result="ok"><function>hdmi1</function><submode></submode></response></UIC>'
  api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
  with patch.object(api, '_exec_cmd', AsyncMock(side_effect=[PUSH_XML, good])):
    result = await api.get_source()
  assert result == {'mode': 'hdmi1', 'submode': False}


async def test_get_source_wifi_on_push_then_timeout():
  """get_source falls back to wifi when a push event is followed by a timeout (None)."""
  api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
  with patch.object(api, '_exec_cmd', AsyncMock(side_effect=[PUSH_XML, None])), \
       patch('custom_components.samsung_soundbar.media_player.is_airplay_active',
             new=AsyncMock(return_value=False)):
    result = await api.get_source()
  assert result == {'mode': 'wifi', 'submode': False}


# --- get_source AirPlay probe ---

async def test_get_source_wifi_fallback_airplay_active():
  """When GetFunc times out and is_airplay_active returns True, submode is 'AirPlay'."""
  api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
  with patch.object(api, '_exec_cmd', AsyncMock(return_value=None)), \
       patch('custom_components.samsung_soundbar.media_player.is_airplay_active',
             new=AsyncMock(return_value=True)) as mock_probe:
    result = await api.get_source()
  assert result == {'mode': 'wifi', 'submode': 'AirPlay'}
  mock_probe.assert_called_once_with("192.168.1.100")


async def test_get_source_wifi_fallback_airplay_inactive():
  """When GetFunc times out and is_airplay_active returns False, submode is False."""
  api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
  with patch.object(api, '_exec_cmd', AsyncMock(return_value=None)), \
       patch('custom_components.samsung_soundbar.media_player.is_airplay_active',
             new=AsyncMock(return_value=False)) as mock_probe:
    result = await api.get_source()
  assert result == {'mode': 'wifi', 'submode': False}
  mock_probe.assert_called_once_with("192.168.1.100")


async def test_get_source_physical_input_no_airplay_probe():
  """Physical input → is_airplay_active is never called."""
  api = _make_api('<UIC><method>CurrentFunc</method><response result="ok"><function>hdmi1</function><submode></submode></response></UIC>')
  with patch('custom_components.samsung_soundbar.media_player.is_airplay_active',
             new=AsyncMock(return_value=True)) as mock_probe:
    result = await api.get_source()
  assert result == {'mode': 'hdmi1', 'submode': False}
  mock_probe.assert_not_called()


async def test_get_source_bt_no_airplay_probe():
  """Bluetooth → is_airplay_active is never called."""
  api = _make_api('<UIC><method>CurrentFunc</method><response result="ok"><function>bt</function></response></UIC>')
  with patch('custom_components.samsung_soundbar.media_player.is_airplay_active',
             new=AsyncMock(return_value=True)) as mock_probe:
    result = await api.get_source()
  assert result == {'mode': 'bt', 'submode': False}
  mock_probe.assert_not_called()


async def test_get_source_tunein_no_airplay_probe():
  """TuneIn (GetFunc returns CurrentFunc) → is_airplay_active is never called."""
  api = _make_api('<UIC><method>CurrentFunc</method><response result="ok"><function>wifi</function><submode>cp</submode></response></UIC>')
  with patch('custom_components.samsung_soundbar.media_player.is_airplay_active',
             new=AsyncMock(return_value=True)) as mock_probe:
    result = await api.get_source()
  assert result == {'mode': 'wifi', 'submode': 'TuneIn'}
  mock_probe.assert_not_called()


async def test_yaml_update_scales_volume_from_device_nondefault_max(hass):
  """async_update scaling works correctly with a non-default max_volume."""
  entities = await _setup_platform(hass, {**BASE_YAML_CONFIG, CONF_MAX_VOLUME: "60"})
  entity = entities[0]
  entity.api.get_state = AsyncMock(return_value="1")
  entity.api.get_source = AsyncMock(return_value={'mode': 'hdmi1', 'submode': False})
  entity.api.get_volume = AsyncMock(return_value="15")
  entity.api.get_muted = AsyncMock(return_value=False)

  await entity.async_update()

  assert entity._volume == 0.25


# --- _update_with_power_options ---

async def test_update_power_options_airplay_sets_title(hass):
  """AirPlay mode → _media_title='AirPlay', _image_url=None."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  entity.api.get_state = AsyncMock(return_value="1")
  entity.api.get_source = AsyncMock(return_value={'mode': 'wifi', 'submode': 'AirPlay'})
  entity.api.get_volume = AsyncMock(return_value="10")
  entity.api.get_muted = AsyncMock(return_value=False)

  await entity._update_with_power_options()

  assert entity._media_title == 'AirPlay'
  assert entity._image_url is None


async def test_update_power_options_tunein_calls_refresh_media(hass):
  """TuneIn mode → _refresh_media_info is called; title and image are populated."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  entity.api.get_state = AsyncMock(return_value="1")
  entity.api.get_source = AsyncMock(return_value={'mode': 'wifi', 'submode': 'TuneIn'})
  entity.api.get_volume = AsyncMock(return_value="10")
  entity.api.get_muted = AsyncMock(return_value=False)
  entity.api.get_radio_info = AsyncMock(return_value="Radio Song")
  entity.api.get_radio_image = AsyncMock(return_value="http://example.com/img.jpg")

  await entity._update_with_power_options()

  assert entity._media_title == 'Radio Song'
  assert entity._image_url == "http://example.com/img.jpg"


async def test_update_power_options_idle_wifi_clears_title(hass):
  """Idle WiFi mode → _media_title='', _image_url=None."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  entity.api.get_state = AsyncMock(return_value="1")
  entity.api.get_source = AsyncMock(return_value={'mode': 'wifi', 'submode': False})
  entity.api.get_volume = AsyncMock(return_value="10")
  entity.api.get_muted = AsyncMock(return_value=False)

  await entity._update_with_power_options()

  assert entity._media_title == ''
  assert entity._image_url is None


async def test_update_power_options_device_off_clears_title(hass):
  """Device off → state=STATE_OFF, _media_title='', _image_url=None."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  entity.api.get_state = AsyncMock(return_value="0")

  await entity._update_with_power_options()

  assert entity._state == STATE_OFF
  assert entity._media_title == ''
  assert entity._image_url is None


# --- get_main_info ---

MAIN_INFO_XML = (
  '<UIC><method>MainInfo</method><response result="ok">'
  '<spkmacaddr>70:b1:3d:ce:19:64</spkmacaddr>'
  '<spkmodelname>HW-Q900A</spkmodelname>'
  '</response></UIC>'
)


async def test_get_main_info_happy_path():
  """get_main_info returns a dict with spkmacaddr and spkmodelname."""
  api = _make_api(MAIN_INFO_XML)
  result = await api.get_main_info()
  assert result['spkmacaddr'] == '70:b1:3d:ce:19:64'
  assert result['spkmodelname'] == 'HW-Q900A'


async def test_get_main_info_offline():
  """get_main_info returns None when the device is unreachable."""
  api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
  with patch.object(api, '_exec_cmd', AsyncMock(return_value=None)):
    result = await api.get_main_info()
  assert result is None


async def test_get_main_info_ng_result():
  """get_main_info returns None when the response result is not 'ok'."""
  api = _make_api(
    '<UIC><method>MainInfo</method><response result="ng">'
    '<spkmacaddr>70:b1:3d:ce:19:64</spkmacaddr>'
    '</response></UIC>'
  )
  result = await api.get_main_info()
  assert result is None


# --- get_software_version ---

SW_VERSION_XML = (
  '<UIC><method>SoftwareVersion</method><response result="ok">'
  '<version>HW-Q900AWWB-1011.1</version>'
  '<displayversion>HW-Q900AWWB-1011.1</displayversion>'
  '</response></UIC>'
)


async def test_get_software_version_happy_path():
  """get_software_version returns a dict with version and displayversion."""
  api = _make_api(SW_VERSION_XML)
  result = await api.get_software_version()
  assert result['version'] == 'HW-Q900AWWB-1011.1'
  assert result['displayversion'] == 'HW-Q900AWWB-1011.1'


async def test_get_software_version_offline():
  """get_software_version returns None when the device is unreachable."""
  api = MultiRoomApi("192.168.1.100", "56001", MagicMock(), None)
  with patch.object(api, '_exec_cmd', AsyncMock(return_value=None)):
    result = await api.get_software_version()
  assert result is None


# --- MultiRoomDevice device_info ---

async def test_device_info_identifiers(hass):
  """device_info identifiers use (DOMAIN, unique_id)."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  assert (DOMAIN, entity._attr_unique_id) in entity._attr_device_info['identifiers']


async def test_device_info_manufacturer(hass):
  """device_info manufacturer is 'Samsung'."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  assert entity._attr_device_info['manufacturer'] == 'Samsung'


async def test_fetch_model_if_needed_populates_model(hass):
  """_fetch_model_if_needed sets device_info['model'] on first successful call."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  entity.api.get_main_info = AsyncMock(return_value={'spkmodelname': 'HW-Q900A'})

  await entity._fetch_model_if_needed()

  assert entity._attr_device_info['model'] == 'HW-Q900A'
  assert entity._model_fetched is True


async def test_fetch_model_if_needed_no_second_call(hass):
  """_fetch_model_if_needed makes no API call after _model_fetched is True."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  entity.api.get_main_info = AsyncMock(return_value={'spkmodelname': 'HW-Q900A'})

  await entity._fetch_model_if_needed()
  await entity._fetch_model_if_needed()

  entity.api.get_main_info.assert_called_once()


async def test_fetch_model_if_needed_offline_no_crash(hass):
  """_fetch_model_if_needed does not raise when get_main_info returns None."""
  entities = await _setup_entry(hass, BASE_ENTRY_DATA)
  entity = entities[0]
  entity.api.get_main_info = AsyncMock(return_value=None)

  await entity._fetch_model_if_needed()

  assert entity._model_fetched is False
  assert 'model' not in entity._attr_device_info
