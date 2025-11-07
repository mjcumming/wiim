# Response for Issue #86

Hi @Sudo-Rob,

Thanks for reporting this! I've already added "Headphone Out" support for the WiiM Ultra, but I need your help to verify the correct mode value.

## Current Status

The integration already includes "Headphone Out" as an option for Ultra devices, but the mode value needs verification. Currently, it's mapped to mode `0`, but this is an educated guess that needs testing.

## What I Need From You

When you select headphones from the Ultra front panel and it shows "Bluetooth Out" in Home Assistant, I need to know what mode value the device is actually reporting. Here are two ways to test this:

### Option 1: Test via Home Assistant (Easiest)

1. Connect headphones to your WiiM Ultra front panel
2. Select headphones from the front panel
3. In Home Assistant, check the `select.<your_device>_audio_output_mode` entity
   - What does it currently show? (You mentioned it shows "Bluetooth Out")
4. Check the entity's state attributes in Developer Tools → States
   - Look for any mode-related attributes

### Option 2: Test via API (Most Accurate)

1. Connect headphones to your WiiM Ultra front panel
2. Select headphones from the front panel
3. Open this URL in your browser (replace `192.168.1.68` with your device IP):
   ```
   https://192.168.1.68/httpapi.asp?command=getNewAudioOutputHardwareMode
   ```
4. You should see JSON like: `{"hardware":"2","source":"0","audiocast":"0"}`
5. **Tell me what the `hardware` field value is** - this is the mode number we need!

### Option 3: Test Setting Different Modes

Once we know what mode value is returned, we can test setting it. You can test different mode values by opening these URLs in your browser:

- Mode 0: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:0`
- Mode 1: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:1`
- Mode 2: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:2`
- Mode 3: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:3`
- Mode 4: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:4`
- Mode 5: `https://192.168.1.68/httpapi.asp?command=setAudioOutputHardwareMode:5`

Try each one and see which mode actually switches to headphones. Then report back with:
- What mode value is returned when headphones are selected (from Option 2)
- What mode value actually switches to headphones (from Option 3)

## Expected Results

Based on the current mapping:
- Mode 1 = Optical Out
- Mode 2 = Line Out
- Mode 4 = Bluetooth Out

If headphones are showing as "Bluetooth Out", it's possible the device is reporting mode `4` when headphones are selected, or there's a different mode value we haven't mapped yet.

## Next Steps

Once you provide the mode value(s), I'll update the code to correctly map "Headphone Out" to the right mode value, and it should work properly in Home Assistant.

Thanks for helping test this!

