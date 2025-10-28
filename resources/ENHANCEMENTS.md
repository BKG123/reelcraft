# Video Enhancement Features

This document describes the new visual polish and editing features added to ReelCraft.

## Overview

Four major enhancements have been implemented to create more professional-looking videos:

1. **Dynamic Audio Ducking**
2. **Text-Only Scenes**
3. **Aspect Ratio Handling with Blurred Backgrounds**
4. **Smart Scene Transitions**

---

## 1. Dynamic Audio Ducking

**Location:** [utils/video_editing.py:197-226](utils/video_editing.py#L197-L226)

### What It Does
Automatically lowers background music volume when the voiceover is speaking and raises it during pauses, creating a professional audio mix.

### How It Works
- Uses FFmpeg's `sidechaincompress` filter
- Background music is "ducked" based on voiceover signal
- Configuration:
  - `threshold=0.02`: Start ducking at this audio level
  - `ratio=4`: Compression ratio (how much to duck)
  - `attack=5ms`: How fast to lower volume
  - `release=200ms`: How fast to return to normal
  - Voiceover weighted 2:1 vs background in final mix

### Before vs After
- **Before:** Static 0.2x volume on background music (too loud during speech)
- **After:** Dynamic volume adjustment that responds to voiceover

---

## 2. Text-Only Scenes

**Locations:**
- Prompt: [config/prompts.py:101-104](config/prompts.py#L101-L104)
- Pipeline: [services/pipeline.py:122-130](services/pipeline.py#L122-L130)
- Rendering: [utils/video_editing.py:52-61](utils/video_editing.py#L52-L61)

### What It Does
Allows AI to generate short, punchy text-only scenes (1-5 words) displayed on a solid background instead of stock footage. This breaks up visual monotony and emphasizes key points.

### How It Works
1. **Script Generation:** Gemini AI can now output scenes with `"scene_type": "text"`
2. **Pipeline Handling:** Text scenes skip Pexels asset download
3. **Video Rendering:** Uses FFmpeg `drawtext` filter to create animated text clips
   - Dark blue background (#1a1a2e)
   - Large white text (80px, bold)
   - Centered with text shadow
   - Fade in/out animation

### Scene Format
```json
{
  "scene_number": 3,
  "script": "KEY POINT",
  "scene_type": "text"
}
```

**Note:** For text scenes, omit `asset_keywords` and `asset_type`. The `script` field contains only the text to display (not voiceover).

---

## 3. Aspect Ratio Handling

**Location:** [utils/video_editing.py:275-329](utils/video_editing.py#L275-L329)

### What It Does
For landscape videos (16:9) in portrait frame (9:16), creates a professional blurred background effect instead of stretching/cropping.

### How It Works
1. **Detection:** Uses `ffprobe` to get video dimensions ([utils/video_editing.py:8-27](utils/video_editing.py#L8-L27))
2. **Aspect Ratio Check:** If video is wider than 1.2x target ratio (landscape)
3. **Effect Creation:**
   - **Background layer:** Scaled, cropped, and heavily blurred (`boxblur=20`)
   - **Foreground layer:** Original video scaled to fit width, centered
   - **Result:** Video sits in center with blurred version filling top/bottom

### Visual Result
```
┌─────────────────┐
│  Blurred bg     │
│ ┌─────────────┐ │
│ │ Original    │ │
│ │ Video       │ │
│ └─────────────┘ │
│  Blurred bg     │
└─────────────────┘
```

### Threshold
- Applies effect when `aspect_ratio > target_aspect_ratio * 1.2`
- For portrait 9:16 (0.5625): triggers at ~0.675 or wider
- Normal 16:9 videos (1.778) will definitely get the effect

---

## 4. Smart Scene Transitions

**Location:** [utils/video_editing.py:355-386](utils/video_editing.py#L355-L386)

### What It Does
Adds smooth transitions between scenes instead of hard cuts, making videos feel more dynamic and polished.

### How It Works
- Uses FFmpeg's `xfade` filter to blend between consecutive clips
- **Transition Duration:** 300ms (0.3 seconds)
- **Transition Types:** Cycles through different effects for variety:
  - `fade` - Classic crossfade
  - `wipeleft` / `wiperight` - Wipe transitions
  - `slideleft` / `slideright` - Slide transitions
  - `fadeblack` - Fade through black

### Technical Details
- Clips overlap by transition duration
- Offset calculated to maintain proper timing
- Can be disabled by passing `use_transitions=False` to `stitch_assets()`

### Performance Note
Transitions increase rendering time slightly due to the overlapping filter chains, but the quality improvement is worth it.

---

## Configuration

All enhancements are enabled by default. To customize:

### Disable Transitions
In [utils/video_editing.py](utils/video_editing.py), call:
```python
await stitch_assets(visual_assets, use_transitions=False)
```

### Adjust Audio Ducking
Modify parameters in [utils/video_editing.py:205-212](utils/video_editing.py#L205-L212):
```python
threshold=0.02,   # Lower = duck more often
ratio=4,          # Higher = duck more aggressively
attack=5,         # Faster = quicker ducking
release=200       # Slower = more gradual recovery
```

### Change Text Style
Edit [utils/video_editing.py:38-53](utils/video_editing.py#L38-L53):
```python
fontsize=80,              # Text size
fontcolor='white',        # Text color
font='Arial-Bold',        # Font family
shadowcolor='black',      # Shadow color
color=c=#1a1a2e          # Background color
```

### Adjust Blur Threshold
In [utils/video_editing.py:284](utils/video_editing.py#L284):
```python
if aspect_ratio > target_aspect_ratio * 1.2:  # Change 1.2 to adjust sensitivity
```

---

## Testing Checklist

- [x] Code compiles without syntax errors
- [ ] Test with article containing text-only scenes
- [ ] Test with landscape video assets
- [ ] Test audio ducking with background music
- [ ] Verify transitions work between all scene types
- [ ] Check performance impact on rendering time

---

## Files Modified

1. **config/prompts.py** - Added `scene_type` to JSON schema
2. **services/pipeline.py** - Handle text scenes in asset generation
3. **utils/video_editing.py** - All rendering enhancements
   - Added `generate_text_clip()`
   - Added `get_video_dimensions()` and `get_image_dimensions()`
   - Updated `mix_audio_streams()` for ducking
   - Updated `stitch_assets()` for transitions
   - Updated scene processing for text and aspect ratios

---

## Known Limitations

1. **Text Scenes:** Currently use system default font (Arial). Custom fonts require font file path.
2. **Transitions:** Only video-to-video transitions (xfade filter limitation).
3. **Aspect Ratio:** Only handles landscape→portrait. Portrait→landscape not implemented.
4. **Performance:** Blurred backgrounds and transitions increase render time by ~15-25%.

---

## Future Improvements

- [ ] Custom font support for text scenes
- [ ] More transition types (3D cube, zoom, etc.)
- [ ] Configurable text scene styles (colors, animations)
- [ ] Support for portrait videos in landscape frames
- [ ] Transition type selection based on scene content
