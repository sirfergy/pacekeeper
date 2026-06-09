# Homebrain PaceKeeper for WalkingPads in Home Assistant

PaceKeeper connects to your WalkingPad over Bluetooth and exposes it in Home Assistant. There are two ways to run it:

* **Home Assistant integration (recommended if you have a Bluetooth proxy).** A native integration that talks to the treadmill over Home Assistant's own Bluetooth stack. The connection is automatically routed through whatever adapter can reach the treadmill — including an **ESP32 Bluetooth proxy** running ESPHome in *active* mode. No dedicated board to flash, no MQTT. See [Option A](#option-a--home-assistant-integration-bluetooth-proxy--no-extra-hardware).
* **ESP32 firmware bridge.** Flash a dedicated ESP32 with this firmware; it connects directly to the treadmill and bridges it to Home Assistant over MQTT. See [Option B](#option-b--esp32-firmware-bridge-mqtt).

![Home Assistant PaceKeeper Device](doc/ha_device.png)

See the video on Youtube:

[![Usage video](https://img.youtube.com/vi/Pwt5jl2jNe4/0.jpg)](https://www.youtube.com/watch?v=Pwt5jl2jNe4)

## Supported Hardware

* PitPat-T01 Treadmill – Superun BA06-B1 [[AliExpress](https://s.click.aliexpress.com/e/_c3V1ssrv)]

## Option A — Home Assistant integration (Bluetooth proxy / no extra hardware)

This is a native Home Assistant integration (in [`custom_components/pacekeeper`](custom_components/pacekeeper)). It talks to the treadmill over Home Assistant's own Bluetooth stack, so the connection is transparently routed through whichever adapter can reach it — a USB/onboard Bluetooth adapter **or an ESP32 Bluetooth proxy**. You don't flash anything treadmill-specific and you don't need MQTT.

### Requirements

* Home Assistant **2024.12** or newer with the [Bluetooth integration](https://www.home-assistant.io/integrations/bluetooth/) set up.
* A way for Home Assistant to *connect* to the treadmill:
  * a local Bluetooth adapter within range, **or**
  * an **ESP32 Bluetooth proxy** running [ESPHome's `bluetooth_proxy`](https://esphome.io/components/bluetooth_proxy.html) in **active** mode.

> [!IMPORTANT]
> The proxy needs **active connections** enabled so Home Assistant can *connect* to the treadmill, not just *discover* it. Current ESPHome enables this by default (`bluetooth_proxy: active: true`); older scanner-only proxies do not. If the treadmill is never found, edit the proxy in the ESPHome dashboard and make sure it has:
>
> ```yaml
> esp32_ble_tracker:
>   scan_parameters:
>     active: true
> bluetooth_proxy:
>   active: true
> ```
>
> then **Install** (OTA) to re-flash it.

### Installation

**Via HACS (custom repository):**

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/peteh/pacekeeper`, category **Integration**.
2. Install **PaceKeeper Treadmill**, then restart Home Assistant.

**Manually:**

1. Copy the [`custom_components/pacekeeper`](custom_components/pacekeeper) folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

### Setup

* Power the treadmill on (see [Cloud Free Usage](#cloud-free-usage--start-without-wifi-app-and-cloud-account) if it's still locked). If it is in range of an active adapter/proxy, Home Assistant auto-discovers it and a **PaceKeeper Treadmill** card appears under *Settings → Devices & Services*.
* Otherwise add it manually: *Settings → Devices & Services → Add Integration → PaceKeeper Treadmill*, then pick the treadmill from the list.

### Entities

| Entity | Type | Notes |
| --- | --- | --- |
| Speed | `number` (slider, 0–6 km/h) | Sets target speed; starts the belt. Setting it to 0 stops the belt. |
| Speed | `sensor` | Current belt speed. |
| State | `sensor` | `countdown` / `running` / `paused` / `stopped` / `disconnected`. |
| Distance, Duration, Calories | `sensor` | Workout totals. |
| Start / Pause-Resume / Stop | `button` | Belt controls. |
| Max speed, Firmware | `sensor` (diagnostic) | Reported by the treadmill. |

Reconnection is handled automatically: when the treadmill is switched off it goes *unavailable*, and the integration reconnects through the proxy as soon as it advertises again.

## Option B — ESP32 firmware bridge (MQTT)

This is the original approach: a dedicated ESP32 flashed with this firmware connects directly to the treadmill and bridges it to Home Assistant over MQTT. Choose this if you don't have a Bluetooth proxy (or local adapter) reachable from Home Assistant.

### Required Tools

* ESP32 – I'm using a Wemos S3 Mini, but any ESP32 with Bluetooth should do [[AliExpress](https://de.aliexpress.com/item/1005006646247867.html)] [[Amazon](https://amzn.to/44VolhQ)]
* VS Code with PlatformIO

### Setup

#### Find the Bluetooth Address of the Device

Get an app like **nRF Connect** – this app allows you to view Bluetooth connections on your phone.

* Turn the device on with the power switch
* Either use the app to initialize the device or follow the steps in the section **"Cloud Free Usage"**
* Open nRF Connect on your phone
* The device should show up as `PitPat-T01`
* Write down the Bluetooth address (it should look like `AA:BB:CC:11:22`)

#### Preparation of Home Assistant for MQTT

* Add the MQTT integration and follow the setup steps:  
  <https://www.home-assistant.io/integrations/mqtt>

#### Project Compilation

* Set up VS Code with PlatformIO  
  (<https://docs.platformio.org/en/latest/integration/ide/vscode.html#installation>)
* Clone this repo and open it in VS Code
* Rename `config.h.sample` to `config.h`
* Open the file and set the configuration values for MQTT and the Bluetooth address from the previous step
* Connect the ESP32 with a USB cable (you might have to hold **RST** and **BOOT** while plugging it in)
* Compile and flash the project via **PlatformIO → Upload and Monitor**
* If everything goes well, you should see a bunch of log messages, and a new device called `PaceKeeper` should show up in your Home Assistant

## Cloud Free Usage – Start Without WiFi, App, and Cloud Account

You’ll get a remote with it; it has **+**, **−**, and **play/pause** buttons. However, when you turn it on, it initially reacts with a long, annoying sound to any button press. When you turn it on with the power button, it will also take a while before showing display information, first lighting up all display segments.

That’s where you strike.

Turn it on and quickly press **(+)**; you will be greeted with a short sound. Then press **−, −, −, +, +**, wait **20 seconds**, turn it off and on again. It should now display something else, and you can start using it.

### Sequence

* Turn on using the `power` switch on the device
* Press `-` on the remote **3×**
* Press `+` on the remote **1×**
* Press `+` on the remote for **3 seconds**

Each correct input will be confirmed by a short, happy sound. Each incorrect input will be confirmed by a long, annoying sound.

Source:  
<https://www.reddit.com/r/treadmills/comments/1jtuwix/heres_how_you_unlock_superun_treadmills_without/>

## Acknowledgements

I built this with the help of many other people who put effort into reverse-engineering the Bluetooth protocol.

### Web Bluetooth App (Python)

Python web interface to control the treadmill via Bluetooth but for another model.

GitHub project:  
<https://github.com/azmke/pitpat-treadmill-control>

### Web Bluetooth App (JavaScript)

A Web Bluetooth app written in JavaScript. Fully supports the B1 as well.

GitHub project:  
<https://github.com/KeiranY/PitPat-WebBT/>

### Zwift Integration by qdomyos

There is some work in a B1 sub-branch.

Source file:  
<https://github.com/cagnulein/qdomyos-zwift/blob/master/src/devices/deeruntreadmill/deerruntreadmill.cpp>

## Further Notes

Deerrun and Superun seem to use the same OEM hardware, so it's likely that those devices might work as well.
