# Binary Mask Editor User Manual

## Overview

The Binary Mask Editor is a Python and Tkinter-based image editing tool designed for creating and editing binary mask images. It supports multi-layer management, image importing and processing, automatic mask generation, playback animation, and more, making it ideal for image segmentation and mask editing tasks. The program is compatible with Pyodide, allowing it to run in a browser environment.

## Features

- **Multi-Layer Management**: Create, delete, hide, sort, and rename layers.
- **Image Processing**: Import images (PNG, JPG, BMP, etc.) with options for grayscale, binarization, or color modes, supporting cropping or padding.
- **Editing Tools**: Includes brush (freehand drawing), rectangular paint/erase, and region selection/copy/paste/delete functions.
- **Automatic Masking**: Generate masks based on grayscale or LAB thresholds, or use white pixel intersections, applied to the second-to-last layer.
- **Playback Animation**: Display the second-to-last layer and swap layers at specified intervals for animation preview.
- **Undo/Redo**: Supports up to 50 history records for operations.
- **Resolution Settings**: Default VGA (640x480), with support for custom resolutions.
- **Interactive Interface**: Features mouse wheel zooming, middle-click panning, grid mode, axis display, and draggable layer panel.

## Installation and Running

1. **Requirements**:
   - Python 3.7+ (or Pyodide environment)
   - Dependencies: `tkinter`, `PIL` (Pillow), `numpy`, `opencv-python`, `datetime`, `platform`, `asyncio`

2. **Running the Program**:
   - Download the `mask_editor.py` file.
   - Run in a local Python environment:
     ```bash
     python mask_editor.py
     ```
   - Alternatively, load in a Pyodide-supported browser environment (no local installation required).

3. **Interface Layout**:
   - **Main Canvas**: Left side displays the image for editing and preview.
   - **Layer Panel**: Right side shows the layer list, supporting selection, hiding, deletion, and renaming.
   - **Menu Bar**: Top contains "File," "Edit," "Tools," "Layer," "Settings," and "Help" menus.
   - **Status Bar**: Bottom displays current operation status and prompts.

## Operation Guide

### 1. File Operations

#### Generate White Canvas
- **Function**: Creates a new blank layer (white, binary mask).
- **Operation**: Menu Bar → File → Generate White
- **Details**:
  - Default resolution is 640x480 (VGA).
  - If a custom resolution is set (see "Set Resolution"), it takes precedence.
  - The new canvas replaces all existing layers and becomes the current layer.
- **Example**: Click "Generate White" to create a 640x480 white layer named "Layer 1."

#### Import Image
- **Function**: Imports image files (PNG, JPG, BMP, etc.).
- **Operation**: Menu Bar → File → Import Image
- **Details**:
  - Import mode (selected via "File → Import Processing"):
    - **Grayscale**: Converts the image to grayscale (L mode).
    - **Binarization**: Converts the image to a binary mask based on set thresholds (grayscale or LAB).
    - **Color**: Retains the image in RGB mode.
  - After import, a crop preview window opens:
    - If the image is larger than the target resolution, drag the mouse to select a crop region (release to confirm).
    - If smaller, choose "Center and Pad" or "Scale to Target."
  - New layer is named "Layer N" (N is the layer number) and added to the layer list.
- **Example**: Select "Color" mode, import a JPG image, crop to 640x480, and add as "Layer 2."

#### Auto Mask
- **Function**: Generates a mask based on grayscale or LAB thresholds, or white pixel intersections, applied to the second-to-last layer.
- **Operation**: Menu Bar → File → Auto Mask
- **Details**:
  - Requires at least two layers (bottom layer and at least one foreground layer).
  - **Grayscale Threshold** (if set): Processes grayscale layers (L mode), taking the intersection of pixels within the threshold range.
  - **LAB Threshold** (if set): Processes color layers (RGB mode), taking the intersection of pixels within the LAB space threshold range.
  - **White Pixel Intersection** (if both thresholds are unset): Processes binary layers (L mode), taking the intersection of white pixels (255).
  - The result is applied to the second-to-last layer (typically the bottom layer), setting intersection areas to black (0).
- **Example**: Set grayscale threshold `100,200`, click "Auto Mask," and the second-to-last layer is updated with the grayscale intersection mask.

#### Mask Inversion
- **Function**: Inverts black and white pixels (0 ↔ 255) of the current layer.
- **Operation**: Menu Bar → File → Mask Inversion
- **Details**:
  - Applies only to the currently selected layer.
  - If the layer is in RGB mode, it is converted to grayscale (L mode) before inversion.
- **Example**: Select "Layer 1," click "Mask Inversion," and black areas become white, and vice versa.

#### Save Mask
- **Function**: Saves the composite mask of all visible layers (grayscale mode).
- **Operation**: Menu Bar → File → Save Mask
- **Details**:
  - Opens a save dialog to choose the path and filename (default extension: .png).
  - The composite mask is the superposition of all visible layers (white background, black foreground).
- **Example**: Click "Save Mask," select `/path/to/mask.png`, and save the composite mask.

#### Quick Save
- **Function**: Quickly saves the composite mask with a timestamped filename.
- **Operation**: Menu Bar → File → Quick Save
- **Details**:
  - Automatically generates a filename like `mask_YYYYMMDD_HHMMSS.png` (e.g., `mask_20250810_192300.png`).
  - Saves to the program's running directory.
- **Example**: Click "Quick Save," generating `mask_20250810_192300.png`.

### 2. Editing Operations

#### Undo/Redo
- **Function**: Undo or redo recent operations (up to 50 history records).
- **Operation**:
  - Undo: Menu Bar → Edit → Undo (Shortcut: `Ctrl+Z` or `Z`)
  - Redo: Menu Bar → Edit → Redo (Shortcut: `Ctrl+Y` or `Y`)
- **Details**: Supports undoing/redoing operations like drawing, layer management, and region movement.
- **Example**: Draw a rectangle, press `Ctrl+Z` to undo the drawing.

#### Select Region
- **Function**: Selects a specific region on the current layer for copying, pasting, or deletion.
- **Operation**: Menu Bar → Edit → Select Region
- **Details**:
  - After selecting the "Select" tool, click the image to auto-select non-white regions, or drag the mouse to define a custom region.
  - A blue rectangle outlines the selected region.
- **Example**: Select "Layer 1," click "Select Region," and drag to select (100,100,200,200).

#### Copy/Paste/Delete Region
- **Function**: Copy, paste, or delete the selected region.
- **Operation**:
  - Copy: Menu Bar → Edit → Copy
  - Paste: Menu Bar → Edit → Paste
  - Delete: Menu Bar → Edit → Delete Selected Region
- **Details**:
  - **Copy**: Copies the selected region of the current layer to the clipboard.
  - **Paste**: Pastes the clipboard content to the top-left corner (0,0) of the current layer.
  - **Delete**: Fills the selected region with white (255 or RGB (255,255,255)).
- **Example**: Select region (100,100,200,200), click "Copy," switch to "Layer 2," click "Paste," and the region is pasted at (0,0).

### 3. Tools

#### Paint (Rectangle)
- **Function**: Draws a black rectangle on the current layer.
- **Operation**: Menu Bar → Tools → Paint (Rectangle)
- **Details**:
  - Drag the mouse to draw a rectangle, release to confirm.
  - In grid mode, rectangle boundaries align with the merge factor (default 1).
  - RGB layers draw black (0,0,0), grayscale layers draw black (0).
- **Example**: Select "Paint (Rectangle)," drag on "Layer 1" to draw a black rectangle (50,50,150,150).

#### Erase (Rectangle)
- **Function**: Erases (fills with white) a rectangular area on the current layer.
- **Operation**: Menu Bar → Tools → Erase (Rectangle)
- **Details**:
  - Drag the mouse to erase a rectangular area, release to confirm.
  - RGB layers fill with white (255,255,255), grayscale layers fill with white (255).
- **Example**: Select "Erase (Rectangle)," drag on "Layer 1" to erase (50,50,150,150).

#### Brush (Freehand)
- **Function**: Freehand drawing (black) or erasing (white) on the current layer.
- **Operation**: Menu Bar → Tools → Brush (Freehand)
- **Details**:
  - Hold the left mouse button and drag to draw a circular brush path.
  - Brush size is adjustable via "Settings → Set Brush Size" (default 5 pixels).
  - Draws black or erases white, using (0,0,0) or (255,255,255) for RGB layers.
- **Example**: Select "Brush (Freehand)," set brush size to 10, draw a freehand path on "Layer 1."

### 4. Layer Management

#### Create New Layer
- **Function**: Creates a new blank layer (white).
- **Operation**: Menu Bar → Layer → New Layer
- **Details**:
  - Named "Layer N" (N is the layer number), with the current target resolution.
  - Becomes the current layer and appears in the layer list.
- **Example**: Click "New Layer" to create "Layer 2" with resolution 640x480.

#### Sort Layers
- **Function**: Adjusts the display order of layers.
- **Operation**: Menu Bar → Layer → Sort Layers
- **Details**:
  - Opens a sorting window, with sorted layers on the left and unsorted layers on the right.
  - Double-click a layer on the right to add it to the sorted list, click a layer on the left to remove it.
  - Click "Apply Sorting" to save the new order.
- **Example**: Move "Layer 2" to the top of the sorted list, click "Apply Sorting" to update the layer order.

#### Select Layer
- **Function**: Selects the current layer for editing.
- **Operation**: Click a layer name in the layer list.
- **Details**: The selected layer is highlighted, and the status bar updates to "Selected layer: {name}."
- **Example**: Click "Layer 1," status bar shows "Selected layer: Layer 1."

#### Hide/Show Layer
- **Function**: Toggles layer visibility (opacity 0.3 for hidden, 1.0 for visible).
- **Operation**: Select a layer in the layer list, click the "Hide" button.
- **Details**:
  - Hiding a foreground grayscale layer reveals the background color layer (RGB) in its original colors.
  - Hidden status is shown as "(Hidden)" in the layer list.
- **Example**: Select "Layer 1" (grayscale), click "Hide," and "Layer 2" (RGB) displays in color.

#### Delete Layer
- **Function**: Deletes the selected layer.
- **Operation**: Select a layer in the layer list, click the "Delete" button.
- **Details**:
  - Cannot delete the last layer.
  - Automatically selects the last remaining layer after deletion.
- **Example**: Select "Layer 2," click "Delete," and the layer list updates.

#### Rename Layer
- **Function**: Renames a layer.
- **Operation**: Right-click a layer in the layer list, select "Rename."
- **Details**:
  - Opens a window to input a new name, which must be non-empty and unique.
  - Updates the name in the sorting list (if sorted).
- **Example**: Right-click "Layer 1," select "Rename," input "Background," and confirm.

### 5. Settings

#### Set Resolution
- **Function**: Sets the target resolution for new canvases and imported images.
- **Operation**: Menu Bar → Settings → Set Resolution
- **Details**:
  - Input format: `width×height` (e.g., `800×600`).
  - Resolution must be positive integers.
  - Existing layers are resized to the new resolution (using LANCZOS interpolation).
  - Custom resolution overrides the default 640x480.
- **Example**: Input `800×600`, click "Apply," and all layers resize to 800x600.

#### Set Brush Size
- **Function**: Adjusts the diameter of the freehand brush.
- **Operation**: Menu Bar → Settings → Set Brush Size
- **Details**:
  - Input a positive integer (unit: pixels, default 5).
  - Affects the "Brush (Freehand)" tool.
- **Example**: Input `10`, click "Apply," and set brush size to 10 pixels.

#### Set Pixel Merge Factor
- **Function**: Sets the pixel alignment factor in grid mode.
- **Operation**: Menu Bar → Settings → Set Pixel Merge Factor
- **Details**:
  - Input a positive integer (default 1, no merging).
  - Affects rectangle drawing and brush alignment precision.
- **Example**: Input `4`, click "Apply," and drawing aligns to a 4x4 pixel grid.

#### Set Threshold
- **Function**: Sets thresholds for image binarization during import.
- **Operation**: Menu Bar → Settings → Set Threshold
- **Details**:
  - **Grayscale Threshold**: Format `min,max` (e.g., `100,200`), range [0,255], min ≤ max.
  - **LAB Threshold**: Format `Lmin,Lmax,Amin,Amax,Bmin,Bmax` (e.g., `0,200,100,150,100,150`), L ∈ [0,255], A/B ∈ [-128,127], min ≤ max.
  - Affects image import in "Binarization" mode.
- **Example**: Input LAB threshold `0,200,100,150,100,150`, click "Apply," and use for binarized image import.

#### Set Auto Mask Threshold
- **Function**: Sets thresholds for automatic mask generation.
- **Operation**: Menu Bar → Settings → Set Auto Mask Threshold
- **Details**:
  - **Grayscale Threshold**: Format `min,max` (e.g., `100,200`), leave empty to skip grayscale processing.
  - **LAB Threshold**: Format `Lmin,Lmax,Amin,Amax,Bmin,Bmax` (e.g., `0,200,100,150,100,150`), leave empty to skip color processing.
  - If both are empty, only processes white pixel intersections in binary layers.
  - Threshold validation is the same as "Set Threshold."
- **Example**: Input grayscale threshold `100,200`, leave LAB empty, click "Apply," and auto-mask processes only grayscale layers.

#### Set Playback Interval
- **Function**: Sets the interval for playback animation.
- **Operation**: Menu Bar → Settings → Set Playback Interval
- **Details**:
  - Input a positive number (unit: seconds, default 3).
  - Affects the layer switching interval in playback.
- **Example**: Input `2`, click "Apply," and set playback interval to 2 seconds.

#### Set Preview Display
- **Function**: Enables/disables image preview.
- **Operation**: Menu Bar → Settings → Set Preview Display (check/uncheck)
- **Details**: When disabled, the canvas shows a placeholder text.
- **Example**: Uncheck "Set Preview Display," and the canvas shows "No image, please import or generate a white canvas."

### 6. View Options

#### Show Pixel Grid
- **Function**: Displays a pixel grid on the canvas.
- **Operation**: Menu Bar → View → Show Pixel Grid (check/uncheck)
- **Details**:
  - Grid aligns with the merge factor (default 1), visible when zoom is sufficient.
  - Affects rectangle drawing and brush alignment.
- **Example**: Check "Show Pixel Grid," set merge factor to 4, and the canvas shows a 4x4 pixel grid.

#### Show Layer Panel
- **Function**: Shows/hides the right-side layer panel.
- **Operation**: Menu Bar → View → Show Layer Panel (check/uncheck)
- **Details**: Hiding the panel can be reversed by dragging it back.
- **Example**: Uncheck "Show Layer Panel," and the layer panel hides.

#### Show Coordinate Axis
- **Function**: Displays coordinate axes on the canvas.
- **Operation**: Menu Bar → View → Show Coordinate Axis (check/uncheck)
- **Details**:
  - Axes mark every 10 pixels, with major ticks every 50 pixels.
  - Facilitates precise editing.
- **Example**: Check "Show Coordinate Axis," and the canvas shows X/Y axis ticks.

### 7. Playback Animation

- **Function**: Plays a layer animation at specified intervals.
- **Operation**: Click the "Play" button in the layer list (changes to "Stop" during playback).
- **Details**:
  - Requires at least three layers.
  - Animation process:
    1. Displays the second-to-last layer (others hidden).
    2. After the interval, swaps layers starting from the third-to-last, displaying each in the second-to-last position.
    3. Finally swaps the first layer with the second-to-last.
    4. Restores original layer order after completion.
  - Interval is adjustable via "Settings → Set Playback Interval" (default 3 seconds).
- **Example**: With layers "Layer 1," "Layer 2," "Layer 3," click "Play" to show "Layer 2," switching every 3 seconds.

### 8. Interactive Operations

#### Zoom
- **Function**: Zooms the canvas display.
- **Operation**: Scroll mouse wheel up (zoom in) or down (zoom out).
- **Details**:
  - Zoom range: 0.1x to 10x.
  - Zooms centered on the mouse position.
- **Example**: Scroll up at the canvas center, increasing zoom to 2.0.

#### Pan
- **Function**: Moves the canvas display area.
- **Operation**: Hold the middle mouse button and drag.
- **Details**: Panning adjusts the display position without altering image content.
- **Example**: Middle-click and drag the canvas to move the image left by 100 pixels.

#### Drag Layer Panel
- **Function**: Repositions the layer panel.
- **Operation**: Click and drag the top of the layer panel.
- **Details**: Allows custom interface layout.
- **Example**: Drag the layer panel to the top-right corner of the window.

## Notes

- **Layer Restriction**: At least one layer must remain; the last layer cannot be deleted.
- **Resolution Changes**: Changing resolution resizes all layers, which may affect image quality.
- **Auto Mask**: Requires at least two layers with the bottom layer containing an image.
- **Playback Animation**: Needs three or more layers; other operations may be restricted during playback.
- **Save Path**: Quick save uses the program’s running directory; ensure sufficient disk space.
- **Pyodide Compatibility**: Avoid local file I/O and network calls to ensure browser compatibility.

## Example Workflow

1. **Create Canvas**:
   - Menu Bar → Settings → Set Resolution, input `800×600`.
   - Menu Bar → File → Generate White, create an 800x600 white canvas (Layer 1).

2. **Import Color Image**:
   - Menu Bar → File → Import Processing → Color.
   - Menu Bar → File → Import Image, select `image.jpg`, crop to 800x600, add as Layer 2.

3. **Set Auto Mask Thresholds**:
   - Menu Bar → Settings → Set Auto Mask Threshold, input grayscale threshold `100,200`, LAB threshold `0,200,100,150,100,150`.
   - Menu Bar → File → Auto Mask, apply mask to Layer 1.

4. **Edit Mask**:
   - Select Layer 1, click "Tools → Brush (Freehand)," set brush size to 10, draw black areas.
   - Select "Tools → Erase (Rectangle)," erase part of the area.

5. **Hide Canvas to Show Color**:
   - In the layer list, select Layer 1 (grayscale), click "Hide," and Layer 2 (RGB) displays in color.

6. **Rename Layer**:
   - Right-click Layer 1, select "Rename," input "Mask," and confirm.

7. **Play Animation**:
   - Add Layer 3 (new canvas), click "Play" to view layer switching animation.

8. **Save Result**:
   - Menu Bar → File → Quick Save, generate `mask_20250810_192300.png`.

## FAQs

- **Q: Image displays incorrectly after import?**
  - A: Check the import mode (Grayscale/Binarization/Color) and threshold settings; ensure the image format is supported (PNG/JPG/BMP).
- **Q: Auto mask has no effect?**
  - A: Ensure at least two layers with foreground in grayscale or color and valid threshold settings.
- **Q: Playback animation is laggy?**
  - A: Try shortening the playback interval or reducing layer count; check browser performance.
- **Q: How to restore default settings?**
  - A: Menu Bar → Edit → Reset, clears all layers and settings, restoring defaults.

## Changelog

- **August 10, 2025**:
  - Changed LAB threshold input order to `Lmin,Lmax,Amin,Amax,Bmin,Bmax`.
  - Optimized auto-mask logic: skips grayscale/LAB processing if thresholds are unset, using white pixel intersections if both are empty.
  - Supported hiding foreground grayscale layers to display background color images.
  - Added right-click layer renaming in the layer list.
  - Auto-mask threshold window uses vertical layout for grayscale and LAB inputs.
  - Default resolution set to VGA (640x480), with custom resolution support.

