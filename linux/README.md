# LibrePods Linux

A native Linux application to control your AirPods, with support for:

- Noise Control modes (Off, Transparency, Adaptive, Noise Cancellation)
- Conversational Awareness
- Battery monitoring
- Auto play/pause on ear detection
- Hearing Aid features
   - Supports adjusting hearing aid- amplification, balance, tone, ambient noise reduction, own voice amplification, and conversation boost
   - Supports setting the values for left and right hearing aids (this is not a hearing test! you need to have an audiogram to set the values)
- Seamless handoff between Android and Linux

## Prerequisites

1. Your phone's Bluetooth MAC address (can be found in Settings > About Device)
2. Qt6 packages

   ```bash
   # For Arch Linux / EndeavourOS
   sudo pacman -S qt6-base qt6-connectivity qt6-multimedia-ffmpeg qt6-multimedia

   # For Debian
   sudo apt-get install qt6-base-dev qt6-declarative-dev qt6-connectivity-dev qt6-multimedia-dev \
        qml6-module-qtquick-controls qml6-module-qtqml-workerscript qml6-module-qtquick-templates \
        qml6-module-qtquick-window qml6-module-qtquick-layouts

    # For Fedora
    sudo dnf install qt6-qtbase-devel qt6-qtconnectivity-devel \
        qt6-qtmultimedia-devel qt6-qtdeclarative-devel
   ```
3. OpenSSL development headers

    ```bash
    # On Arch Linux / EndevaourOS, these are included in the OpenSSL package, so you might already have them installed.
    sudo pacman -S openssl
    
    # For Debian / Ubuntu
    sudo apt-get install libssl-dev
    
    # For Fedora
    sudo dnf install openssl-devel
    ```
## Setup

1. Build the application:

   ```bash
   mkdir build
   cd build
   cmake ..
   make -j $(nproc)
   ```

2. Run the application:

   ```bash
   ./librepods
   ```

## Usage

- Left-click the tray icon to view battery status
- Right-click to access the control menu:
  - Toggle Conversational Awareness
  - Switch between noise control modes
  - View battery levels
  - Control playback

## Hearing Aid

To use hearing aid features, you need to have an audiogram. To enable/disable hearing aid, you can use the toggle in the main app. But, to adjust the settings and set the audiogram, you need to use a different script which is located in this folder as `hearing_aid.py`. You can run it with:

```bash
python3 hearing_aid.py
```

The script will load the current settings from the AirPods and allow you to adjust them. You can set the audiogram by providing the values for 8 frequencies (250Hz, 500Hz, 1kHz, 2kHz, 3kHz, 4kHz, 6kHz, 8kHz) for both left and right ears. There are also options to adjust amplification, balance, tone, ambient noise reduction, own voice amplification, and conversation boost.