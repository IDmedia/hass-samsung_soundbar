import voluptuous as vol
from urllib.parse import urlparse
from homeassistant import config_entries
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
  NumberSelector,
  NumberSelectorConfig,
  NumberSelectorMode,
)

from .const import (
  DOMAIN,
  DEFAULT_NAME,
  DEFAULT_PORT,
  DEFAULT_MAX_VOLUME,
  DEFAULT_POWER_OPTIONS,
  CONF_PORT,
  CONF_MAX_VOLUME,
  CONF_POWER_OPTIONS,
)
from .media_player import MultiRoomApi


class SamsungSoundbarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
  """Handle a config flow for Samsung Soundbar."""

  VERSION = 1

  async def async_step_user(self, user_input=None):
    """Handle the initial step."""
    errors = {}

    if user_input is not None:
      host = user_input[CONF_HOST]
      port = user_input.get(CONF_PORT, DEFAULT_PORT)
      session = async_get_clientsession(self.hass)
      api = MultiRoomApi(host, port, session, self.hass)

      # Basic connectivity test
      speaker_name = await api.get_speaker_name()

      if speaker_name:
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
          title=user_input.get(CONF_NAME, DEFAULT_NAME),
          data=user_input,
        )
      errors["base"] = "cannot_connect"

    return self.async_show_form(
      step_id="user",
      data_schema=vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
        vol.Required(CONF_MAX_VOLUME, default=int(DEFAULT_MAX_VOLUME)): NumberSelector(
          NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.SLIDER)
        ),
        vol.Required(CONF_POWER_OPTIONS, default=DEFAULT_POWER_OPTIONS): cv.boolean,
      }),
      errors=errors,
    )

  async def async_step_ssdp(self, discovery_info: SsdpServiceInfo):
    """Handle SSDP discovery."""
    host = urlparse(discovery_info.ssdp_location).hostname
    port = DEFAULT_PORT
    session = async_get_clientsession(self.hass)
    api = MultiRoomApi(host, port, session, self.hass)

    speaker_name = await api.get_speaker_name()
    if not speaker_name:
      return self.async_abort(reason="not_samsung_soundbar")

    await self.async_set_unique_id(f"{host}:{port}")
    self._abort_if_unique_id_configured()

    self._discovered_host = host
    self._discovered_name = speaker_name[0] if isinstance(speaker_name, list) else speaker_name
    self.context["title_placeholders"] = {"name": self._discovered_name}
    return await self.async_step_confirm()

  async def async_step_confirm(self, user_input=None):
    """Confirm adding a discovered device."""
    if user_input is not None:
      return self.async_create_entry(
        title=self._discovered_name,
        data={
          CONF_HOST: self._discovered_host,
          CONF_NAME: self._discovered_name,
          CONF_PORT: DEFAULT_PORT,
          CONF_MAX_VOLUME: int(DEFAULT_MAX_VOLUME),
          CONF_POWER_OPTIONS: DEFAULT_POWER_OPTIONS,
        },
      )

    return self.async_show_form(
      step_id="confirm",
      description_placeholders={
        "name": self._discovered_name,
        "host": self._discovered_host,
      },
    )
