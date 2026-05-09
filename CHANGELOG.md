# Changelog

## 1.4.0 (2026-05-09)

- Soundbar is now registered as a device in the Home Assistant device registry, with manufacturer ("Samsung") and model name populated from the device
- Added two diagnostic sensor entities: MAC Address and Firmware Version

## 1.3.0 (2026-04-25)

- Added AirPlay source detection for soundbars in Wifi mode; probes using mDNS

## 1.2.0 (2026-04-23)

- Switched to XML parsing for device API responses, improving reliability with
  devices that return malformed or unexpected results (notably the HW-Q900A in
  certain Wifi modes)
- Improved robustness of source/function state retrieval
- Internal refactoring of API call structure

## 1.1.0 (2026-03-30)

- Added UI-driven configuration flow; YAML configuration remains supported
- Added UPnP/SSDP-based autodiscovery for compatible Samsung soundbars

## Earlier editions

Prior to 1.1.0, configuration was handled entirely via YAML. Various bug fixes and
compatibility updates were made over time for Home Assistant API changes and device
quirks.
