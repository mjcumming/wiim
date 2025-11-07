# WiiM Play Codebase Review

**Date**: 2025-01-27
**Source**: [WiiM Play Repository](https://github.com/shumatech/wiimplay)
**Purpose**: Identify useful API endpoints, patterns, and insights from the wiimplay GTK3 control point

---

## 🔍 **Key Findings**

### **1. Fade Effects Endpoints** ⭐ **NEW DISCOVERY**

**Endpoints Found:**
- `GetFadeFeature` - Get fade effects status
- `SetFadeFeature:<value>` - Set fade effects (0=off, 1=on)

**Code Reference:**
```go
func (device *WiimDevice) GetFadeEffects() (bool, error) {
    result := &struct {
        FadeFeature int `json:"FadeFeature"`
    }{}
    err := device.command("GetFadeFeature", &result)
    if err != nil {
        return false, err
    }
    return result.FadeFeature != 0, nil
}

func (device *WiimDevice) SetFadeEffects(on bool) error {
    var result string
    value := 0
    if on {
        value = 1
    }
    err := device.command(fmt.Sprintf("SetFadeFeature:%d", value), &result)
    if err != nil {
        return err
    }
    if result != "OK" {
        return fmt.Errorf("setChannelBalance failed")
    }
    return nil
}
```

**Response Format:**
```json
{
  "FadeFeature": 1  // 0 = disabled, 1 = enabled
}
```

**Status:** ❌ Not documented in our API guide

---

### **2. Fixed Volume Control** ⭐ **NEW DISCOVERY**

**Endpoints Found:**
- `getStatusEx` - Used to read `volume_control` field
- `setVolumeControl:<value>` - Set fixed volume mode (0=variable, 1=fixed)

**Code Reference:**
```go
func (device *WiimDevice) GetFixedVolume() (bool, error) {
    result := &struct {
        FixedVolume string `json:"volume_control"`
    }{}
    err := device.command("getStatusEx", &result)
    if err != nil {
        return false, err
    }
    return result.FixedVolume != "0", nil
}

func (device *WiimDevice) SetFixedVolume(on bool) error {
    var result string
    value := 0
    if on {
        value = 1
    }
    err := device.command(fmt.Sprintf("setVolumeControl:%d", value), &result)
    if err != nil {
        return err
    }
    if result != "OK" {
        return fmt.Errorf("setVolumeControl failed")
    }
    return nil
}
```

**Observations:**
- Fixed volume mode prevents volume changes (useful for line-out connections)
- Status read from `getStatusEx` response field `volume_control`
- Set via dedicated `setVolumeControl` endpoint

**Status:** ❌ Not documented in our API guide

---

### **3. EQGetBand Confirmation** ✅ **ALREADY DOCUMENTED**

**Code Reference:**
```go
func (device *WiimDevice) GetEqualizer() (string, error) {
    result := &struct {
        Status    string `json:"status"`
        EQStat    string `json:"EQStat"`
        Name      string `json:"Name"`
    }{}
    err := device.command("EQGetBand", &result)
    if err != nil {
        return "", err
    }
    if result.Status != "OK" {
        return "", fmt.Errorf("EQGetBand returned %s", result.Status)
    }
    if result.EQStat == "Off" {
        return "Off", nil
    }
    return result.Name, nil
}
```

**Status:** ✅ We just documented this in our API guide

---

### **4. Audio Input Mode Mapping** 📝 **USEFUL REFERENCE**

**Code Reference:**
```go
func (device *WiimDevice) GetAudioInput() (int, error) {
    result := &struct {
        Mode string
    }{}
    err := device.command("getPlayerStatus", &result)
    if err != nil {
        return 0, err
    }
    return map[string]int{
        "10": 1,  // Network
        "41": 2,  // Bluetooth
        "40": 3,  // Line In
        "43": 4,  // Optical In
    }[result.Mode] - 1, nil
}

func (device *WiimDevice) SetAudioInput(input int) error {
    mode := []string{"wifi", "bluetooth", "line-in", "optical"}[input]
    var result string
    err := device.command(fmt.Sprintf("setPlayerCmd:switchmode:%s", mode), &result)
    if err != nil {
        return err
    }
    if result != "OK" {
        return fmt.Errorf("switchmode failed")
    }
    return nil
}
```

**Observations:**
- Mode values from `getPlayerStatus`: "10"=Network, "41"=Bluetooth, "40"=Line In, "43"=Optical
- Input switching uses `setPlayerCmd:switchmode:<mode>` with string values: "wifi", "bluetooth", "line-in", "optical"
- This confirms our source detection logic

**Status:** ✅ Already covered in our guide (source detection section)

---

### **5. Audio Output Mode Mapping** 📝 **CONFIRMS OUR DOCUMENTATION**

**Code Reference:**
```go
func (device *WiimDevice) GetAudioOutput() (int, error) {
    result := &struct {
        Hardware string
    }{}
    err := device.command("getNewAudioOutputHardwareMode", &result)
    if err != nil {
        return 0, err
    }
    hardware, err := strconv.Atoi(result.Hardware)
    if err != nil {
        return 0, err
    }
    return hardware - 1, nil  // Returns 0-based index
}

func (device *WiimDevice) GetAudioOutputList() ([]string, error) {
    return []string{"Optical Out", "Line Out", "Coax Out"}, nil
}

func (device *WiimDevice) SetAudioOutput(output int) error {
    var result string
    err := device.command(fmt.Sprintf("setAudioOutputHardwareMode:%d", output + 1), &result)
    // Note: They add 1 to convert from 0-based to 1-based API index
}
```

**Observations:**
- API uses 1-based indexing (1=Optical, 2=Line, 3=Coax)
- They convert to 0-based for UI (subtract 1 when reading, add 1 when setting)
- They don't include Bluetooth Out in the list (firmware-controlled)
- This matches our documentation

**Status:** ✅ Already documented in our guide

---

### **6. Channel Balance** ✅ **ALREADY DOCUMENTED**

**Code Reference:**
```go
func (device *WiimDevice) GetBalance() (float64, error) {
    result := 0.0
    err := device.command("getChannelBalance", &result)
    return result, err
}

func (device *WiimDevice) SetBalance(level float64) error {
    var result string
    err := device.command(fmt.Sprintf("setChannelBalance:%f", level), &result)
    if err != nil {
        return err
    }
    if result != "OK" {
        return fmt.Errorf("setChannelBalance failed")
    }
    return nil
}
```

**Status:** ✅ Already documented in our guide

---

### **7. Equalizer Preset Handling** ✅ **CONFIRMS OUR APPROACH**

**Code Reference:**
```go
func (device *WiimDevice) SetEqualizer(setting string) error {
    result := &struct {
        Status string
    }{}
    var command string
    if setting == "Off" {
        command = "EQOff"
    } else {
        command = "EQLoad:" + setting
    }
    err := device.command(command, &result)
    if err != nil {
        return err
    }
    if result.Status != "OK" {
        return fmt.Errorf("EQLoad returned %s", result.Status)
    }
    return nil
}

func (device *WiimDevice) GetEqualizerList() ([]string, error) {
    result := []string{}
    err := device.command("EQGetList", &result)
    if err != nil {
        return nil, err
    }
    result = append(result, "Off")
    return result, nil
}
```

**Observations:**
- They use `EQOff` for disabling EQ (not `EQGetStat`)
- They append "Off" to the preset list from `EQGetList`
- They use `EQLoad:<preset>` for setting presets
- This matches our implementation

**Status:** ✅ Already documented in our guide

---

### **8. UPnP Integration Pattern** 📚 **ARCHITECTURAL INSIGHT**

**Code Reference:**
```go
func NewWiimDevice(urlString string) (*WiimDevice, error) {
    device := &WiimDevice{}

    // UPnP clients for transport control
    atClients, err := upnp.NewAVTransport1ClientsByURL(url)
    device.transport = atClients[0]

    rcClients, err := upnp.NewRenderingControl1ClientsByURL(url)
    device.control = rcClients[0]

    pqClients, err := upnp.NewPlayQueue1ClientsByURL(url)
    device.playQueue = pqClients[0]

    // HTTP API for device-specific commands
    hostname := strings.Split(url.Host, ":")[0]
    device.url = "https://" + hostname + "/httpapi.asp?command="
    device.client = &http.Client{
        Timeout: 3 * time.Second,
        Transport: &http.Transport{
            TLSClientConfig: &tls.Config{
                InsecureSkipVerify: true,
            },
        },
    }
}
```

**Observations:**
- They use **UPnP for transport control** (play, pause, seek, volume, mute)
- They use **HTTP API for device-specific features** (EQ, audio output, balance, fade)
- This is a hybrid approach: UPnP for standard DLNA operations, HTTP API for WiiM-specific features
- They use HTTPS with self-signed cert acceptance (like we do)
- 3-second timeout (we use similar)

**Status:** 📝 Useful architectural pattern - we use HTTP API for everything, they use UPnP for transport

---

### **9. Loop Mode Values** 📝 **USEFUL REFERENCE**

**Code Reference:**
```go
type LoopMode uint
const (
    LoopModeNone LoopMode = 4
    LoopModeOne = 1
    LoopModeAll = 0
    LoopModeNoneShuffle = 3
    LoopModeOneShuffle = 5
    LoopModeAllShuffle = 2
)
```

**Observations:**
- Loop mode values: 0=All, 1=One, 2=All+Shuffle, 3=None+Shuffle, 4=None, 5=One+Shuffle
- This matches our play mode mapping

**Status:** ✅ Already documented in our guide

---

## 🎯 **Recommended Actions**

### **Priority 1: Document Fade Effects** 🔴 **HIGH PRIORITY**

**Endpoints to Add:**
- `GetFadeFeature` - Get fade effects status
- `SetFadeFeature:<value>` - Set fade effects (0=off, 1=on)

**Response Format:**
```json
{
  "FadeFeature": 1  // 0 = disabled, 1 = enabled
}
```

**Use Case:** Fade effects provide smooth transitions between tracks (fade out/in)

---

### **Priority 2: Document Fixed Volume Control** 🔴 **HIGH PRIORITY**

**Endpoints to Add:**
- `setVolumeControl:<value>` - Set fixed volume mode (0=variable, 1=fixed)

**Note:** Status read from `getStatusEx` field `volume_control` (already documented)

**Use Case:** Fixed volume mode prevents volume changes - useful when using line-out to external amplifier

---

### **Priority 3: Verify Audio Output List** 🟡 **MEDIUM PRIORITY**

**Observation:** They only list 3 outputs: "Optical Out", "Line Out", "Coax Out"
- They don't include "Bluetooth Out" in the list
- They note it's firmware-controlled (can't be set via API)

**Action:** Verify if Bluetooth Out should be in our selectable outputs list or if it's truly firmware-only

---

## 📊 **Summary**

| Feature | Status | Action Needed |
|---------|--------|---------------|
| Fade Effects | ❌ Missing | Add `GetFadeFeature` and `SetFadeFeature` docs |
| Fixed Volume | ❌ Missing | Add `setVolumeControl` endpoint docs |
| EQGetBand | ✅ Done | Already documented |
| Channel Balance | ✅ Done | Already documented |
| Audio Output | ✅ Done | Already documented |
| Audio Input | ✅ Done | Already documented |
| Loop Modes | ✅ Done | Already documented |
| UPnP Pattern | 📝 Reference | Useful architectural insight |

---

## 💡 **Key Insights**

1. **Hybrid Approach**: WiiM Play uses UPnP for standard DLNA operations and HTTP API for device-specific features. Our integration uses HTTP API for everything, which is simpler but may miss some UPnP event benefits.

2. **Fade Effects**: This is a feature we haven't documented - provides smooth track transitions.

3. **Fixed Volume**: Useful for line-out connections where you want to prevent volume changes.

4. **EQGetBand Confirmation**: They use the same endpoint we just discovered and documented - confirms our finding.

5. **Audio Output Indexing**: They use 0-based for UI, 1-based for API (add/subtract 1) - confirms our documentation.

---

## 🔗 **References**

- [WiiM Play Repository](https://github.com/shumatech/wiimplay)
- [WiiM Play Main Device Code](https://github.com/shumatech/wiimplay/blob/main/wiimdev/wiim.go)
- [WiiM Play Types](https://github.com/shumatech/wiimplay/blob/main/wiimdev/types.go)

