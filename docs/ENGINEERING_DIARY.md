# Engineering Diary

> A living document capturing development decisions, solutions, and architecture evolution.
> 
> **Project**: Audiobook Creator - PDF/EPUB to Audiobook converter using Apple Silicon MLX

---

## Project Vision

Convert PDF and EPUB books into high-quality audiobooks using local AI models on Apple Silicon, optimized for 16GB unified memory Macs.

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit UI                            │
│  (Upload → Configure → Generate → Export)                   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Pipeline Orchestrator                    │
│  (Sequential model loading, VRAM management)                │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
    │ Ingest  │         │   TTS   │         │  Audio  │
    │ Module  │         │  Engine │         │ Process │
    └─────────┘         └─────────┘         └─────────┘
    PDF/EPUB→Text      Text→Speech         Merge/Export
```

---

## 2026-01-28 - Phase 2: TTS Integration (Session 1)

### Tasks Completed

From `tasks/02_TTS_INTEGRATION.md`:

**2.1 Kokoro-82M TTS Engine**
- [x] Create `modules/tts/engine.py`
- [x] Implement `TTSEngine` class with load/synthesize/unload
- [x] Test basic synthesis with short text
- [x] Verify model download (bf16 variant, ~361MB)

**2.2 Text Chunking**
- [x] Create `modules/tts/chunker.py`
- [x] Implement `TextChunker` class with sentence boundary detection
- [x] Handle edge cases (quotes, dialogue)
- [x] Test with long chapter text (~950 chars → 3 chunks)

**2.4 VRAM Management**
- [x] Create `modules/tts/memory.py` utility
- [x] Implement `clear_vram()` function
- [x] Test memory freed after TTS unload (312MB → 0MB)
- [x] Ensure sequential model loading via VRAMManager singleton

**2.5 Voice Selection (partial)**
- [x] Create `config/voices.py` with presets and speed config

---

### Challenges & Solutions

#### Challenge 1: mlx-audio Model Authentication Error

**Problem**: Initial model path `lucasnewman/kokoro-mlx-4bit` returned 401 Unauthorized.

**Investigation**: Web search revealed the model was renamed/moved.

**Solution**: Updated to public repository `mlx-community/Kokoro-82M-bf16`.

**Code change** in `engine.py`:
```python
# Before
model_name: str = "lucasnewman/kokoro-mlx"

# After
model_name: str = "mlx-community/Kokoro-82M"
```

---

#### Challenge 2: generate_audio() Returns None

**Problem**: TTS test failed with "object of type 'NoneType' has no len()". The `generate_audio()` function from mlx-audio returns `None`.

**Investigation**: Checked function signature - it writes to files, doesn't return audio array.

```python
# API signature
def generate_audio(..., output_path: Optional[str] = None) -> None
```

**Solution**: Use temporary directory, let mlx-audio save file, then read it back:

```python
def synthesize(self, text, voice, speed):
    with tempfile.TemporaryDirectory() as temp_dir:
        generate_audio(
            text=text,
            model=self._model_path,
            voice=voice,
            output_path=temp_dir,
            file_prefix="tts_output",
            verbose=False
        )
        # Find and read the generated file
        wav_files = [f for f in os.listdir(temp_dir) if f.endswith('.wav')]
        audio_path = os.path.join(temp_dir, wav_files[0])
        audio, _ = sf.read(audio_path, dtype='float32')
        return audio
```

**Lesson**: Always verify external library APIs - documentation may be outdated or incomplete.

---

#### Challenge 3: Missing Dependencies

**Problem**: Cascading import errors when loading Kokoro model:
```
ModuleNotFoundError: No module named 'misaki'
ModuleNotFoundError: No module named 'num2words'
ModuleNotFoundError: No module named 'spacy'
```

**Solution**: Install with extras:
```bash
pip install "misaki[en]"  # Includes spacy, num2words, etc.
```

The model also downloads spaCy language model on first run:
```
python -m spacy download en_core_web_sm
```

**Lesson**: MLX-audio's Kokoro support has undocumented dependencies.

---

#### Challenge 4: Quantized Models Compatibility

**Problem**: 6-bit model failed with shape mismatch:
```
ValueError: Expected shape (512, 3, 512) but received shape (512, 512, 3)
```

**Investigation**: The quantized models on mlx-community may have been converted with a different mlx-audio version.

**Solution**: Use bf16 (full precision) model which works correctly. Size is ~361MB vs theoretical ~50MB for 4-bit, but reliability is more important.

**Lesson**: Stick with verified working model variants; smaller isn't always better.

---

### Architecture Changes

#### New Files Created

```
modules/tts/
├── __init__.py     # Updated with new exports
├── engine.py       # Modified: temp file synthesis
├── chunker.py      # NEW: TextChunker class
└── memory.py       # NEW: VRAMManager, clear_vram()

config/
└── voices.py       # Updated: get_voice_choices(), speed presets
```

#### Dependencies Added

```bash
pip install mlx-audio soundfile "misaki[en]"
```

These install: mlx, mlx-lm, kokoro support, spacy, soundfile, and related packages.

#### Key Design Decisions

1. **Singleton VRAMManager**: Ensures only one model loaded at a time
2. **Temp file synthesis**: Works around mlx-audio's file-based output
3. **bf16 over quantized**: Reliability chosen over smaller model size
4. **Token-based chunking**: Estimate ~4 chars/token for chunk sizing

---

### Current State

**What Works**:
- TTS generates audio from text (tested: ~2.1s audio, 50,400 samples)
- Memory properly freed after model unload (verified: 312MB → 0MB)
- Text chunking splits long content at sentence boundaries
- Voice configuration ready for UI integration

**What's Next**:
- Add Streamlit sidebar for voice/speed selection
- Integrate chunker with TTS for chapter processing
- Optional: LLM text cleaner (2.3) for improved TTS quality

---

### Commits

| Hash | Message |
|------|---------|
| c1bdcd6 | fix tts synthesize to use temp file output |
| e3a4600 | add text chunker for vram management |
| bb62107 | add vram memory management utility |
| cdf4970 | add voice choices and speed presets for ui |
| 8d9de37 | export chunker and memory utilities |

---

## 2026-01-28 - Phase 3: Audio Processing Complete

### Tasks Completed

From `tasks/03_AUDIO_PROCESSING.md`:

**3.1 Audio Processor (PyDub)**
- [x] Create `modules/audio/processor.py`
- [x] Implement `AudioProcessor` class with concatenate, normalize, silence
- [x] Test with multiple WAV file concatenation

**3.2 MP3 Encoder (FFmpeg)**
- [x] Create `modules/audio/encoder.py`
- [x] Implement `AudioEncoder` class with wav_to_mp3, get_duration
- [x] Verify VideoToolbox hardware acceleration available

**3.3 M4B Packager**
- [x] Create `modules/audio/packager.py`
- [x] Implement `M4BPackager` with chapter markers
- [x] Test chapter navigation (verified: 3 chapters with correct timestamps)

**3.4 Metadata Handling**
- [x] Integrated with existing EPUB/PDF parsers
- [x] `AudiobookMetadata` dataclass for user editing
- [x] Metadata embedded via FFmpeg metadata file

---

### Architecture Changes

#### New Files Created

```
modules/audio/
├── __init__.py     # Updated: exports all audio classes
├── processor.py    # NEW: AudioProcessor (PyDub)
├── encoder.py      # NEW: AudioEncoder (FFmpeg)
└── packager.py     # NEW: M4BPackager, AudiobookMetadata, ChapterMarker
```

#### Dependencies Added

```bash
pip install pydub  # Audio processing
# ffmpeg required (brew install ffmpeg)
```

#### Key Design Decisions

1. **PyDub for processing**: High-level API for WAV manipulation
2. **FFmpeg for encoding**: Industry standard, hardware accelerated on Mac
3. **Pure FFmpeg for M4B**: No m4b-tool dependency, uses ffmetadata format
4. **Dataclasses for metadata**: Clean API for user editing before export

---

### Current State

**What Works**:
- WAV concatenation and volume normalization (-16 dBFS target)
- MP3 encoding at 128kbps with duration utilities
- M4B creation with chapter markers and metadata
- Chapter navigation verified working

**What's Next (Phase 3.5 Cover Art - Deferred)**:
- Extract cover from EPUB
- Allow custom cover upload
- Embed cover in M4B

---

### Commits

| Hash | Message |
|------|---------|
| 1947c20 | add audio processor with pydub |
| b425736 | fix type annotations for pydub |
| d2e94f7 | export audio processor |
| b50df8d | add ffmpeg audio encoder |
| a931972 | add m4b audiobook packager |
| beb695e | export encoder and packager |

---

*Next entry will be added when continuing development.*

---

## 2026-01-28 - Phase 4: UI Polish (Session 1)

### Tasks Completed

From `tasks/04_UI_POLISH.md`:

**4.2 Real-time Log Window**
- [x] Create collapsible log component (uses `st.expander`)
- [x] Format: `> action_description...`
- [x] Shows last 10 log messages

**4.4 Visual Effects**  
- [x] Implement scanline overlay (CSS `::after` pseudo-element)
- [x] Add phosphor glow to amber text (`text-shadow`)
- [x] Style all buttons as `[ ACTION ]` (bracket format)
- [x] Implement hover state (color invert)
- [x] Remove all rounded corners (`border-radius: 0`)
- [x] Hide header anchor/link icons
- [x] Style audio player to match theme
- [x] Fix slider min/max labels visibility

**Voice Preview Feature**
- [x] Implement real TTS preview with James Joyce text
- [x] Loads Kokoro model, synthesizes ~10s audio, plays inline
- [x] Properly unloads model after preview

---

### Challenges & Solutions

#### Challenge 1: Header Anchor Links

**Problem**: Streamlit adds clickable link icons next to headers on hover.

**Solution**: CSS to hide all variants:
```css
.stMarkdown a[href^="#"],
[data-testid="stHeaderActionElements"],
a.anchor-link {
    display: none !important;
}
```

---

#### Challenge 2: Native Audio Player Styling

**Problem**: Browser's default audio player (gray pill) didn't match theme.

**Solution**: CSS pseudo-selectors for WebKit controls:
```css
audio::-webkit-media-controls-panel {
    background-color: #0A0A0A !important;
    border-radius: 0 !important;
}
audio::-webkit-media-controls-current-time-display {
    color: #FFB000 !important;
}
```

---

#### Challenge 3: Slider Labels Hidden

**Problem**: Min/max values under speed slider showed amber boxes with invisible text.

**Solution**: Make label backgrounds transparent:
```css
[data-testid="stTickBarMin"],
[data-testid="stTickBarMax"] {
    background-color: transparent !important;
}
```

---

### Architecture Changes

#### Files Modified

```
main.py              # Voice preview with real TTS, collapsible log
assets/css/retro.css # Audio player, slider labels, link hiding
```

#### Key Design Decisions

1. **Inline TTS preview**: Load model → synthesize → play → unload
2. **Base64 audio embedding**: Avoids file serving complexity
3. **Log as expander**: Reduces clutter, expandable when needed

---

### Current State

**What Works**:
- Full "Amber & Obsidian" retro terminal theme
- Real-time log window (collapsible)
- Voice preview plays actual TTS audio
- File upload with START CONVERSION button
- Model status display in processing section

**What's Next (Pipeline Integration)**:
- [ ] Wire START button to actual conversion pipeline
- [ ] Connect: Ingest → Chunker → TTS → Audio Processor → M4B Packager
- [ ] Real-time progress updates during conversion
- [ ] Chapter-by-chapter processing with progress percentage
- [ ] ETA calculation based on audio generation speed
- [ ] Export download button for completed audiobook

---

### Commits

| Hash | Message |
|------|---------|
| 3000bd0 | fix UI: styled audio player, collapsible log, hide links, TTS preview |
| 3fbd13c | Revert "style audio player slider with amber theme" |
| d7145d6 | fix slider min/max labels visibility |

---

*Next: Integrate full conversion pipeline with UI*

---

## 2026-01-29 - Phase 4: UI Polish Complete (Session 2)

### Tasks Completed

From `tasks/04_UI_POLISH.md`:

**4.1 Progress Tracking**
- [x] Create per-chapter progress bars
- [x] Show current stage (parsing, cleaning, TTS, encoding)
- [x] Display estimated time remaining
- [x] Handle cancellation gracefully
- [x] Persist progress across page refreshes

**4.3 Waveform Visualizer**
- [x] Create `modules/ui/waveform.py`
- [x] Implement blocky oscilloscope style
- [x] Use amber color (`#FFB000`)
- [x] Animate during playback
- [x] Show static preview when paused

**4.5 Library View**
- [x] Create library page/tab
- [x] List all converted audiobooks
- [x] Show title, author, date, duration
- [x] Allow replay/re-export
- [x] Allow deletion
- [x] Search/filter functionality

**4.6 Keyboard Shortcuts**
- [x] `Ctrl+O` — Open file dialog
- [x] `Space` — Play/Pause
- [x] `Ctrl+L` — Toggle library
- [x] `Ctrl+E` — Export current
- [x] `Esc` — Cancel processing
- [x] Display shortcut hints in UI

---

### Architecture Changes

#### New Files Created

```
modules/ui/
├── __init__.py     # Updated: exports all components
├── progress.py     # NEW: ChapterProgress, ConversionProgress, rendering
├── waveform.py     # NEW: ASCII oscilloscope visualizer
├── library.py      # NEW: Book listing, search, detail view
└── shortcuts.py    # NEW: JavaScript keyboard handlers
```

#### Key Design Decisions

1. **Dataclass-based progress**: `ChapterProgress` and `ConversionProgress` use Python dataclasses for clean state management

2. **ASCII waveform**: Uses Unicode block characters (`▁▂▃▄▅▆▇█`) for retro terminal aesthetic

3. **Session state persistence**: Progress can be serialized to JSON and restored on page refresh

4. **JavaScript keyboard handler**: Injected via `st.markdown` with hidden input for Streamlit to read actions

5. **Database integration for library**: Uses existing `Database` class from `modules/storage/database.py`

#### Module Exports

```python
# modules/ui/__init__.py exports:
- ProcessingStage (enum)
- ChapterProgress, ConversionProgress (dataclasses)
- init_progress_state, get_progress, reset_progress
- set_chapters, update_chapter_progress, set_current_stage
- request_cancellation, is_cancelled, clear_cancellation
- save_progress_to_session, restore_progress_from_session
- render_chapter_progress, render_stage_indicator
```

---

### Current State

**What Works**:
- Per-chapter progress bars with ASCII visualization
- Processing stage indicator with color-coded status
- ETA display (formatter ready, needs pipeline integration)
- Cancellation support with graceful state cleanup
- Progress persistence across page refreshes
- Waveform visualizer with playback animation
- Library view with search/filter and CRUD operations
- Keyboard shortcuts (Ctrl+O, Space, Ctrl+L, Ctrl+E, Esc)

**What's Next (Phase 5: Optimization & Testing)**:
- [ ] Unit tests for all modules
- [ ] Integration tests for full pipeline
- [ ] Performance optimization for large files
- [ ] Memory profiling and leak detection
- [ ] Error handling improvements
- [ ] Documentation updates

---

### Commits

| Hash | Message |
|------|---------|
| 83eca66 | add progress tracking module |
| 081d7e6 | export progress tracking components |
| b10c3ab | integrate progress tracking component |
| 60c17b5 | add cancellation and persistence support |
| 3673a78 | export cancellation and persistence functions |
| 286e0ad | add waveform visualizer component |
| 5fe0e76 | integrate waveform visualizer component |
| 944531a | add library view component |
| a496c71 | add keyboard shortcuts module |

---

*Phase 4 complete. Ready for Phase 5: Optimization & Testing.*



## 2026-01-29 - Phase 4.5: Pipeline Integration

### Tasks Completed

From `tasks/04.5_PIPELINE_INTEGRATION.md`:

**4.5.1 Pipeline Orchestrator**
- [x] Create `modules/pipeline/orchestrator.py`
- [x] Implement `ConversionPipeline` orchestrator logic
- [x] Add `PipelineStage` enum with CLEANING stage
- [x] Implement error handling and cancellation checks

**4.5.2 Text Cleaner Integration**
- [x] Integrate `TextCleaner` into pipeline (Stage 2.5)
- [x] Add progress reporting for cleaning stage

**4.5.3 Real-time Progress**
- [x] Update `orchestrator.py` to notify progress callback
- [x] Implement live UI updates via Streamlit placeholders in `conversion.py`
- [x] Pass placeholders from `main.py` to `run_conversion`

**4.5.4 ETA Calculation**
- [x] Implement `estimate_eta()` in orchestrator
- [x] Pass `eta_seconds` to progress callback
- [x] Display formatted ETA in UI

**4.5.5 Audio Processing Fixes**
- [x] Fix `AudioProcessor` usage in orchestrator (load/save vs load_audio/save_audio)
- [x] Remove duplicate initialization logic

**4.5.7 Export & Library**
- [x] Integrate `Database` saving on successful conversion
- [x] Add chapter buttons in UI (download individual MP3s)
- [x] Allow full M4B download

---

### Challenges & Solutions

#### Challenge 1: Live UI Updates in Streamlit

**Problem**: Progress bars weren't updating in real-time inside the `run_conversion` function because Streamlit often requires a full rerun to update state.

**Solution**: Passed Streamlit `empty()` placeholders (`progress_container`, `status_container`) from `main.py` down to `run_conversion`. The callback then writes directly to these containers using context managers (`with container:`), enabling live updates without full page reruns.

#### Challenge 2: AudioProcessor Usage Confusion

**Problem**: `orchestrator.py` was trying to call `processor.load_audio()` and `processor.save_audio()`, but the actual methods in `modules/audio/processor.py` are named `load()` and `save()`.

**Solution**: Updated `orchestrator.py` to use correct method names. Also fixed a copy-paste error where `AudioProcessor` was initialized twice in the same block.

---

### Architecture Changes

#### Files Modified

```
modules/pipeline/
└── orchestrator.py   # NEW: Core logic, ETA, cleaning stage, progress callbacks

modules/ui/
└── conversion.py     # Modified: Accepts UI placeholders, handles live updates

main.py               # Modified: Creates placeholders, integrates DB saving & downloads
```

#### Key Design Decisions

1. **Callback-driven UI**: Pipeline is UI-agnostic; it pushes status via a callback. The UI layer (`conversion.py`) translates these to Streamlit widget updates.
2. **Context Manager Cleaning**: Used `with TextCleaner() as cleaner:` to ensuring VRAM is freed immediately after the cleaning stage, before TTS starts.
3. **Database-backed Library**: Conversions are automatically saved to SQLite, making the "Library" tab functional.

---

### Current State

**What Works**:
- Full end-to-end pipeline: Ingest → Chunk → Clean → TTS → Process → Package
- Live progress bars for Chapters and overall Book
- Real-time ETA estimation
- Database storage of results
- Individual chapter and full book downloads

**What's Next**:
- Phase 5: Optimization & Testing (Performance profiling, large file tests)
