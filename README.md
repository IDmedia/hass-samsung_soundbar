Samsung Soundbar
============
Control volume, and source of your multiroom device like Samsung Soundbar K650, HW-MS650 or Q90R. This is a fork of macbury's [ha_samsung_multi_room](https://github.com/macbury/ha_samsung_multi_room) working on the latest version of Home Assistant.

## Installation using HACS (Recommended)
1. Navigate to HACS and add a custom repository  
    **URL:** https://github.com/IDmedia/hass-samsung_soundbar  
    **Category:** Integration
2. Install module as usual
3. Restart Home Assistant

## Configuration
| Key | Default | Required | Description
| --- | --- | --- | ---
| name | | yes | Name of the media player.
| host | 127.0.0.1 | no | The ip of your soundbar.
| port | 56001 | no | The port which the soundbar uses. My Q90R uses 56001, but the port might differ, try 55001.
| max_volume | 40 | no | Limit the max volume.
| power_options | true | no | Enable or disable the power options

## Example
Add the following to your `configuration.yaml`:
```
media_player:
  - platform: samsung_soundbar
    name: "Soundbar"
    host: 192.168.1.227
    port: 56001
    max_volume: 20
    power_options: True
```

# Sources

* soundshare - this is tv
* bt - bluetooth
* aux
* optical
* hdmi

# Api support
Based on information gathered from: https://github.com/bacl/WAM_API_DOC/blob/master/API_Methods.md