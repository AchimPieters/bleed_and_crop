# bleed_and_crop
Add to non bleed document a 3mm bleed and cropmarks

# bleed_and_crop

A simple but powerful Python tool to make print-ready PDFs.

## ✨ Features

This script automatically prepares PDFs for print:

- ✂️ Removes white margins (auto-cropping)
- 🪞 Generates bleed by mirroring edges and corners
- 📏 Adds crop marks outside the artwork
- 📄 Outputs a ready-to-print PDF

## 📦 Requirements

Install dependencies:

```bash
pip install pymupdf pillow numpy
```

## 🚀 Usage

Basic usage:

```bash
python bleed_and_crop.py input.pdf
```

This creates:

```
input_Print.pdf
```

## ⚙️ Options

```bash
python bleed_and_crop.py input.pdf \
    --bleed-mm 3 \
    --mark-margin-mm 8 \
    --mark-len-mm 5 \
    --output output.pdf
```

### Parameters

| Option | Description | Default |
|------|------------|--------|
| `--bleed-mm` | Bleed size in mm | 3 |
| `--mark-margin-mm` | Margin outside artwork for crop marks | 8 |
| `--mark-len-mm` | Length of crop marks | 5 |
| `--stroke-mm` | Thickness of crop marks | 0.2 |
| `--analysis-dpi` | DPI for edge detection | 72 |
| `--output-dpi` | DPI for final output | 300 |

## 🧠 How it works

1. Detects non-white content at low resolution
2. Crops the PDF to its true content bounds
3. Re-renders at high resolution
4. Removes remaining anti-aliasing edge artifacts
5. Builds bleed by mirroring edges and corners
6. Adds crop marks outside the trim area

## 📁 Output

- Multi-page PDFs supported
- Output file automatically named:

  ```
  <input_name>_Print.pdf
  ```

## 🎯 Use cases

- Print production / prepress
- Flyers, posters, brochures
- Automating bleed creation
- Fixing PDFs without bleed

## 🛠️ Notes

- Works best with PDFs that have white margins
- Handles anti-aliased edge artifacts (no white hairlines)
- Fully automated — no manual cropping needed

## 📄 License

MIT License

---

Made for practical print workflows 🖨️
