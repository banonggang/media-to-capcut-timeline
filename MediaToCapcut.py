import argparse
import builtins
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
UUID_PATTERN = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
TEXT_NAMES = {"draft_settings", "draft.extra", "template.tmp", "template-2.tmp"}


def new_id():
    return str(uuid.uuid4()).upper()


def natural_key(value):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.opencode-{os.getpid()}")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def parse_number(value):
    text = str(value).strip()
    if not text:
        raise ValueError("empty value")
    if ":" in text:
        parts = text.split(":")
        if len(parts) != 3:
            raise ValueError("use seconds or M:SS")
        hours, minutes, seconds = parts
        number = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    else:
        number = float(text)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("duration must be greater than zero")
    return number


def format_time(microseconds):
    seconds = max(0, microseconds) / 1_000_000
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes}:{remainder:06.3f}"


def clean_path(value):
    text = str(value).strip()
    if text.casefold().startswith("file://"):
        parsed = urlparse(text)
        if os.name == "nt":
            netloc = unquote(parsed.netloc)
            if re.fullmatch(r"[A-Za-z]:", netloc):
                text = netloc + parsed.path
            elif netloc and netloc.casefold() != "localhost":
                text = f"//{netloc}{parsed.path}"
            else:
                text = parsed.path
            text = unquote(text).replace("/", "\\")
            if re.match(r"^\\[A-Za-z]:", text):
                text = text[1:]
        else:
            text = unquote(parsed.path)
    text = text.strip("'\"")
    text = text.replace("\\ ", " ")
    if os.name == "nt":
        text = os.path.expandvars(text)
    return Path(os.path.expanduser(text)).resolve(strict=False)


def comparable_path(value):
    text = str(value).strip()
    if not text:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(text))))


def same_path(left, right):
    return comparable_path(left) == comparable_path(right)


def ask(prompt, default, parser=None):
    while True:
        try:
            answer = input(f"{prompt} [{default}]: ").strip()
        except EOFError:
            return parser(default) if parser is not None else default
        if not answer:
            return parser(default) if parser is not None else default
        if parser is None:
            return answer
        try:
            return parser(answer)
        except Exception as error:
            print(f"Invalid value: {error}")


def ask_yes(prompt, default=True, assume=False):
    if assume:
        return default
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            answer = input(f"{prompt} {suffix} ").strip().casefold()
        except EOFError:
            return default
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False


def pause(interactive, disabled):
    if interactive and not disabled:
        try:
            input("Press Enter to close...")
        except EOFError:
            pass


def finish_pause():
    disabled = "--no-pause" in sys.argv or "--self-test" in sys.argv
    if os.name == "nt" and "--keep-open" not in sys.argv:
        return
    if os.name != "nt" and "--keep-open" in sys.argv:
        disabled = True
    if sys.stdin.isatty() and os.environ.get("TERM_PROGRAM") != "Apple_Terminal":
        pause(True, disabled)


def find_draft_root(explicit=None):
    candidates = []
    if explicit:
        candidates.append(clean_path(explicit))
    if os.environ.get("CAPCUT_DRAFT_ROOT"):
        candidates.append(clean_path(os.environ["CAPCUT_DRAFT_ROOT"]))
    home = Path.home()
    if os.name == "nt":
        bases = []
        for variable in ("LOCALAPPDATA", "APPDATA"):
            value = os.environ.get(variable)
            if value:
                base = clean_path(value)
                if base not in bases:
                    bases.append(base)
        for base in (home / "AppData/Local", home / "AppData/Roaming"):
            if base not in bases:
                bases.append(base)
        for base in bases:
            for directory in ("CapCut", "CapCut Desktop"):
                candidates.append(base / directory / "User Data/Projects/com.lveditor.draft")
    else:
        candidates.extend([
            home / "Movies/CapCut/User Data/Projects/com.lveditor.draft",
            home / "Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut/User Data/Projects/com.lveditor.draft",
            home / "Library/Application Support/CapCut/User Data/Projects/com.lveditor.draft",
        ])
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "root_meta_info.json").is_file():
            return candidate.resolve()
    raise RuntimeError("CapCut draft folder was not found. Check CapCut > Settings > Draft location.")


def find_capcut_app():
    if os.name == "nt":
        candidates = []
        for variable in ("LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            value = os.environ.get(variable)
            if not value:
                continue
            base = Path(value)
            candidates.extend([
                base / "CapCut/CapCut.exe",
                base / "Programs/CapCut/CapCut.exe",
                base / "CapCut Desktop/CapCut.exe",
            ])
        candidates.extend([
            Path.home() / "AppData/Local/CapCut/CapCut.exe",
            Path.home() / "AppData/Local/Programs/CapCut/CapCut.exe",
            Path.home() / "AppData/Roaming/CapCut/CapCut.exe",
        ])
        for command in ("CapCut.exe", "CapCut"):
            located = shutil.which(command)
            if located:
                candidates.append(Path(located))
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None
    candidates = [Path("/Applications/CapCut.app"), Path.home() / "Applications/CapCut.app"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def capcut_is_running():
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq CapCut.exe", "/FO", "CSV", "/NH"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False
            )
        except (FileNotFoundError, OSError):
            return False
        output = result.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="ignore")
        return bool(re.search(r"(?i)\bcapcut(?:\.exe)?\b", output))
    try:
        return subprocess.run(["pgrep", "-x", "CapCut"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except FileNotFoundError:
        return False


def launch_capcut(app):
    if os.name == "nt":
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(app))
            else:
                subprocess.Popen([str(app)], check=False)
        except OSError:
            pass
        return
    subprocess.run(["open", "-a", str(app)], check=False)


def media_files(folder):
    files = [path for path in folder.iterdir() if path.is_file() and path.suffix.casefold() in MEDIA_EXTENSIONS]
    files.sort(key=lambda path: natural_key(path.name))
    return files


def candidate_asset_folders(downloads):
    candidates = []
    if not downloads.is_dir():
        return candidates
    for base, directories, files in os.walk(downloads):
        path = Path(base)
        try:
            depth = len(path.relative_to(downloads).parts)
        except ValueError:
            depth = 0
        directories[:] = [name for name in directories if not name.startswith(".") and name not in {"icons", "node_modules", "vendor"} and depth < 3]
        direct = [name for name in files if Path(name).suffix.casefold() in MEDIA_EXTENSIONS]
        if direct:
            newest = max((path / name).stat().st_mtime for name in direct)
            name_key = path.name.casefold()
            candidates.append((("autoflow" in name_key), len(direct) == 7, newest, -depth, path))
    candidates.sort(key=lambda item: item[:4], reverse=True)
    return [item[4] for item in candidates]


def default_asset_folder():
    downloads = Path.home() / "Downloads"
    candidates = candidate_asset_folders(downloads)
    if candidates:
        return candidates[0]
    if downloads.is_dir():
        return downloads
    return Path.home() / "Desktop"


def parse_fraction(value):
    if not value:
        return 0.0
    return int(value[:3].ljust(3, "0")) / 1000


def parse_file_timestamp(path):
    stem = Path(path).stem.strip()
    stem = re.sub(r"\s*#\d+\s*$", "", stem)
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    stem = re.sub(r"\s+copy\s*$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"_[A-Za-z]$", "", stem)
    stem = re.sub(r"^\d+\s+", "", stem)
    if re.fullmatch(r"(?:19|20)\d{2}[-_.]\d{1,2}[-_.]\d{1,2}", stem):
        return None
    stem = re.sub(r"^\d{4,}[-_]", "", stem)
    patterns = [
        r"^(\d{1,3})[-_](\d{1,2})[-_](\d{1,2})(?:[.,](\d+))?$",
        r"^(\d{1,3})\.(\d{1,2})\.(\d{1,2})(?:[.,](\d+))?$",
        r"^(\d{1,2})[-_](\d{1,2})(?:[.,](\d+))?$",
        r"^(\d{1,2})\.(\d{1,2})(?:[.,](\d+))?$",
    ]
    for index, pattern in enumerate(patterns):
        match = re.fullmatch(pattern, stem)
        if not match:
            continue
        if index < 2:
            hours, minutes, seconds, fraction = match.groups()
            if int(minutes) > 59 or int(seconds) > 59:
                return None
            return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + parse_fraction(fraction)
        minutes, seconds, fraction = match.groups()
        if int(seconds) > 59 or (index == 2 and int(minutes) > 59):
            return None
        return int(minutes) * 60 + int(seconds) + parse_fraction(fraction)
    return None


def parse_timestamp_list(path):
    text = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    values = []
    hms = re.compile(r"(?<!\d)(\d+):(\d+):(\d+(?:[.,]\d+)?)")
    ms = re.compile(r"(?<![\d:])(\d+):(\d+(?:[.,]\d+)?)(?!\d)")
    bare = re.compile(r"(?<![\d:])-?\d+(?:[.,]\d+)?(?!\d)")
    for line in text.splitlines():
        if not line.strip():
            continue
        match = hms.search(line)
        if match:
            hours, minutes, seconds = match.groups()
            values.append(int(hours) * 3600 + int(minutes) * 60 + float(seconds.replace(",", ".")))
            continue
        match = ms.search(line)
        if match:
            minutes, seconds = match.groups()
            values.append(int(minutes) * 60 + float(seconds.replace(",", ".")))
            continue
        match = bare.search(line)
        if match:
            values.append(float(match.group(0).replace(",", ".")))
    if any(value < 0 for value in values):
        raise RuntimeError("Negative timestamps are not supported.")
    return sorted(values)


def default_timestamp_file():
    downloads = Path.home() / "Downloads"
    files = sorted([path for path in downloads.glob("*") if path.suffix.casefold() in {".srt", ".vtt", ".txt"}], key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def frame_boundaries(raw_microseconds, fps):
    frame = max(1, round(1_000_000 / fps))
    values = [raw_microseconds[0]] + [round(value / frame) * frame for value in raw_microseconds[1:-1]] + [raw_microseconds[-1]]
    for index in range(1, len(values)):
        if values[index] <= values[index - 1]:
            raise RuntimeError("Two media items are too close together for the selected frame rate.")
    return values


def build_timing(media, mode, fps, target_seconds, last_seconds, timestamp_file=None, audio_seconds=None):
    count = len(media)
    if mode == "even":
        total = audio_seconds if audio_seconds and audio_seconds > 0 else target_seconds
        if count == 1:
            raw = [0, round(total * 1_000_000)]
        else:
            raw = [round(total * 1_000_000 * index / count) for index in range(count + 1)]
        boundaries = frame_boundaries(raw, fps)
    else:
        if mode == "filename":
            parsed = [parse_file_timestamp(path) for path in media]
            if any(value is None for value in parsed):
                raise RuntimeError("Not every media filename contains a valid timestamp.")
            pairs = sorted(zip(parsed, media), key=lambda item: (item[0], natural_key(item[1].name)))
            starts = [item[0] for item in pairs]
            media = [item[1] for item in pairs]
        else:
            if timestamp_file is None:
                raise RuntimeError("A timestamp list is required for list mode.")
            starts = parse_timestamp_list(timestamp_file)
            if len(starts) != count:
                raise RuntimeError(f"The timestamp list has {len(starts)} entries, but {count} media files were found.")
        for first, second in zip(starts, starts[1:]):
            if second - first < 0.04:
                raise RuntimeError("Adjacent media timestamps must be at least 0.04 seconds apart.")
        end = starts[-1] + last_seconds
        if audio_seconds and audio_seconds > 0:
            end = max(end, audio_seconds)
        raw = [round(value * 1_000_000) for value in starts] + [round(end * 1_000_000)]
        boundaries = frame_boundaries(raw, fps)
    total = boundaries[-1]
    return {"media": media, "boundaries": boundaries, "total": total, "mode": mode}


def ffprobe_data(path):
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return {}
    try:
        output = subprocess.check_output([
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path)
        ], text=True, stderr=subprocess.DEVNULL)
        data = json.loads(output)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def image_dimensions(path):
    try:
        output = subprocess.check_output(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], text=True, stderr=subprocess.DEVNULL)
        width = re.search(r"pixelWidth:\s*(\d+)", output)
        height = re.search(r"pixelHeight:\s*(\d+)", output)
        if width and height:
            return int(width.group(1)), int(height.group(1))
    except Exception:
        pass
    try:
        output = subprocess.check_output(["mdls", "-raw", "-name", "kMDItemPixelWidth", "-name", "kMDItemPixelHeight", str(path)], text=True, stderr=subprocess.DEVNULL)
        values = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("(null)")]
        if len(values) >= 2:
            return int(values[-2]), int(values[-1])
    except Exception:
        pass
    data = ffprobe_data(path)
    stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "video"), {})
    try:
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
    except (TypeError, ValueError):
        width = 0
        height = 0
    if width > 0 and height > 0:
        return width, height
    return 1920, 1080


def video_metadata(path):
    duration = 0.0
    width = 0
    height = 0
    has_audio = False
    data = ffprobe_data(path)
    streams = data.get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    duration_value = data.get("format", {}).get("duration") or video_stream.get("duration")
    if duration_value not in {None, "N/A"}:
        try:
            duration = float(duration_value)
        except (TypeError, ValueError):
            duration = 0.0
    try:
        width = int(video_stream.get("width") or 0)
        height = int(video_stream.get("height") or 0)
    except (TypeError, ValueError):
        width = 0
        height = 0
    has_audio = any(item.get("codec_type") == "audio" for item in streams)
    if duration <= 0 or width <= 0 or height <= 0 or not has_audio:
        properties = [
            "kMDItemDurationSeconds",
            "kMDItemPixelWidth",
            "kMDItemPixelHeight",
            "kMDItemAudioBitRate",
            "kMDItemAudioChannelCount"
        ]
        values = {}
        for name in properties:
            try:
                output = subprocess.check_output(["mdls", "-raw", "-name", name, str(path)], text=True, stderr=subprocess.DEVNULL)
                value = output.replace("\x00", "").strip()
                if value and value != "(null)":
                    values[name] = value
            except Exception:
                pass
        duration_match = re.search(r"[0-9]+(?:\.[0-9]+)?", values.get("kMDItemDurationSeconds", ""))
        width_match = re.search(r"[0-9]+", values.get("kMDItemPixelWidth", ""))
        height_match = re.search(r"[0-9]+", values.get("kMDItemPixelHeight", ""))
        audio_rate_match = re.search(r"[0-9]+", values.get("kMDItemAudioBitRate", ""))
        audio_channels_match = re.search(r"[0-9]+", values.get("kMDItemAudioChannelCount", ""))
        if duration <= 0 and duration_match:
            duration = float(duration_match.group(0))
        if width <= 0 and width_match:
            width = int(width_match.group(0))
        if height <= 0 and height_match:
            height = int(height_match.group(0))
        if not has_audio and ((audio_rate_match and int(audio_rate_match.group(0)) > 0) or (audio_channels_match and int(audio_channels_match.group(0)) > 0)):
            has_audio = True
    if duration <= 0:
        raise RuntimeError(f"Could not read video duration: {path}")
    return width or 1920, height or 1080, duration, has_audio


def audio_duration(path):
    try:
        output = subprocess.check_output(["afinfo", str(path)], text=True, stderr=subprocess.DEVNULL)
        match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", output, re.IGNORECASE)
        if match and float(match.group(1)) > 0:
            return float(match.group(1))
    except Exception:
        pass
    try:
        output = subprocess.check_output(["mdls", "-raw", "-name", "kMDItemDurationSeconds", str(path)], text=True, stderr=subprocess.DEVNULL)
        value = float(output.strip())
        if value > 0:
            return value
    except Exception:
        pass
    data = ffprobe_data(path)
    values = [data.get("format", {}).get("duration")]
    values.extend(item.get("duration") for item in data.get("streams", []) if item.get("codec_type") == "audio")
    for value in values:
        if value in {None, "N/A"}:
            continue
        try:
            duration = float(value)
        except (TypeError, ValueError):
            continue
        if duration > 0:
            return duration
    raise RuntimeError(f"Could not read audio duration: {path}")


def is_empty_project(folder):
    info_path = folder / "draft_info.json"
    if not info_path.is_file():
        return False
    try:
        info = load_json(info_path)
    except Exception:
        return False
    if info.get("duration", 0) != 0:
        return False
    if any(track.get("segments") for track in info.get("tracks", [])):
        return False
    for values in info.get("materials", {}).values():
        if isinstance(values, list) and values:
            return False
    return (folder / "Timelines/project.json").is_file()


def find_template(root, explicit=None):
    if explicit:
        folder = clean_path(explicit)
        if not is_empty_project(folder):
            raise RuntimeError(f"The selected template is not an empty CapCut project: {folder}")
        return folder
    candidates = [path for path in root.iterdir() if path.is_dir() and is_empty_project(path)]
    if not candidates:
        raise RuntimeError("No empty CapCut project was found. Open CapCut, create one new empty project, quit CapCut, and run this command again.")
    candidates.sort(key=lambda path: (path / "draft_info.json").stat().st_mtime, reverse=True)
    return candidates[0]


def replace_ids_and_timeline(staging):
    mapping = {}
    for path in staging.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.casefold() not in {".json", ".tmp", ".bak", ".extra"} and path.name not in TEXT_NAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        replaced = text
        for old in UUID_PATTERN.findall(text):
            if old not in mapping:
                mapping[old] = new_id()
            replaced = re.sub(re.escape(old), mapping[old], replaced, flags=re.IGNORECASE)
        if replaced != text:
            path.write_text(replaced, encoding="utf-8")
    timeline_root = staging / "Timelines"
    for folder in list(timeline_root.iterdir()):
        if folder.is_dir() and folder.name in mapping:
            folder.rename(timeline_root / mapping[folder.name])
    return mapping


def linked_path(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "linked"
    except OSError:
        shutil.copy2(source, destination)
        return "copied"


def create_cover(source, cover):
    if cover.exists():
        cover.unlink()
    is_image = source.suffix.casefold() in IMAGE_EXTENSIONS
    if is_image:
        try:
            subprocess.run(["sips", "-s", "format", "jpeg", str(source), "--out", str(cover)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception:
            pass
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg and (not is_image or os.name == "nt") and (not cover.is_file() or cover.stat().st_size == 0):
        command = [ffmpeg, "-y"]
        if not is_image:
            command.extend(["-ss", "0"])
        command.extend([
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-q:v",
            "2",
            str(cover)
        ])
        try:
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception:
            if cover.exists():
                cover.unlink()
    if cover.is_file() and cover.stat().st_size > 0:
        return
    qlmanage = shutil.which("qlmanage")
    if qlmanage:
        thumbnail = cover.parent / f"{source.stem}.png"
        if thumbnail.exists():
            thumbnail.unlink()
        try:
            subprocess.run([qlmanage, "-t", "-s", "1080", "-o", str(cover.parent), str(source)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if thumbnail.is_file():
                subprocess.run(["sips", "-s", "format", "jpeg", str(thumbnail), "--out", str(cover)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                thumbnail.unlink()
        except Exception:
            if thumbnail.exists():
                thumbnail.unlink()
    if not cover.is_file() or cover.stat().st_size == 0:
        raise RuntimeError(f"Could not create a project cover from: {source}")


def make_photo_material(material_id, path, width, height):
    return {
        "id": material_id,
        "unique_id": uuid.uuid4().hex,
        "type": "photo",
        "duration": 10_800_000_000,
        "path": str(path),
        "media_path": "",
        "local_id": "",
        "has_audio": False,
        "reverse_path": "",
        "intensifies_path": "",
        "reverse_intensifies_path": "",
        "intensifies_audio_path": "",
        "cartoon_path": "",
        "width": width,
        "height": height,
        "category_id": "",
        "category_name": "local",
        "material_id": "",
        "material_name": Path(path).name,
        "material_url": "",
        "crop": {
            "upper_left_x": 0.0,
            "upper_left_y": 0.0,
            "upper_right_x": 1.0,
            "upper_right_y": 0.0,
            "lower_left_x": 0.0,
            "lower_left_y": 1.0,
            "lower_right_x": 1.0,
            "lower_right_y": 1.0
        },
        "crop_ratio": "free",
        "audio_fade": None,
        "crop_scale": 1.0,
        "extra_type_option": 0,
        "stable": {"stable_level": 0, "matrix_path": "", "time_range": {"start": 0, "duration": 0}},
        "matting": {
            "flag": 0,
            "path": "",
            "interactiveTime": [],
            "has_use_quick_brush": False,
            "strokes": [],
            "has_use_quick_eraser": False,
            "expansion": 0,
            "feather": 0,
            "reverse": False,
            "custom_matting_id": "",
            "enable_matting_stroke": False,
            "is_clould": False,
            "mask_video_path": "",
            "cloud_product_fps": 0.0
        },
        "source": 0,
        "source_platform": 0,
        "formula_id": "",
        "check_flag": 62978047,
        "video_algorithm": {
            "algorithms": [],
            "time_range": None,
            "path": "",
            "gameplay_configs": [],
            "ai_in_painting_config": [],
            "complement_frame_config": None,
            "motion_blur_config": None,
            "deflicker": None,
            "noise_reduction": None,
            "quality_enhance": None,
            "super_resolution": None,
            "ai_background_configs": [],
            "smart_complement_frame": None,
            "aigc_generate": None,
            "aigc_generate_list": [],
            "mouth_shape_driver": None,
            "ai_expression_driven": None,
            "motion_blend": None,
            "image_interpretation": None,
            "story_video_modify_video_config": {
                "task_id": "",
                "is_overwrite_last_video": False,
                "tracker_task_id": "",
                "generate_id": "",
                "generate_card_id": ""
            },
            "skip_algorithm_index": []
        },
        "is_unified_beauty_mode": False,
        "is_set_beauty_mode": False,
        "object_locked": None,
        "smart_motion": None,
        "multi_camera_info": None,
        "freeze": None,
        "picture_from": "none",
        "picture_set_category_id": "",
        "picture_set_category_name": "",
        "team_id": "",
        "local_material_id": "",
        "origin_material_id": "",
        "request_id": "",
        "has_sound_separated": False,
        "is_text_edit_overdub": False,
        "is_ai_generate_content": False,
        "aigc_type": "none",
        "is_copyright": False,
        "aigc_history_id": "",
        "aigc_item_id": "",
        "local_material_from": "",
        "smart_match_info": None,
        "beauty_face_preset_infos": [],
        "beauty_body_preset_id": "",
        "beauty_face_auto_preset": {"preset_id": "", "name": "", "rate_map": "", "scene": ""},
        "beauty_face_auto_preset_infos": [],
        "beauty_body_auto_preset": None,
        "live_photo_timestamp": -1,
        "live_photo_cover_path": "",
        "content_feature_info": None,
        "corner_pin": None,
        "surface_trackings": [],
        "video_mask_stroke": {
            "resource_id": "",
            "path": "",
            "type": "",
            "color": "",
            "size": 0.0,
            "alpha": 0.0,
            "distance": 0.0,
            "texture": 0.0,
            "horizontal_shift": 0.0,
            "vertical_shift": 0.0
        },
        "video_mask_shadow": {
            "resource_id": "",
            "path": "",
            "color": "",
            "alpha": 0.0,
            "blur": 0.0,
            "distance": 0.0,
            "angle": 0.0
        },
        "pre_applied_vip_materials": [],
        "workflow_node_id": ""
    }


def make_video_material(material_id, path, width, height, duration, has_audio):
    material = make_photo_material(material_id, path, width, height)
    material["unique_id"] = ""
    material["type"] = "video"
    material["duration"] = max(1, round(duration * 1_000_000))
    material["has_audio"] = has_audio
    material["category_name"] = ""
    material["video_algorithm"] = copy.deepcopy(material["video_algorithm"])
    material["video_algorithm"].pop("motion_blend", None)
    material["video_algorithm"]["ai_motion_driven"] = None
    return material


def make_audio_material(material_id, path, duration, registration_id):
    return {
        "id": material_id,
        "unique_id": uuid.uuid4().hex,
        "type": "extract_music",
        "name": Path(path).name,
        "duration": duration,
        "path": str(path),
        "category_name": "local",
        "wave_points": [],
        "music_id": "",
        "app_id": 0,
        "text_id": "",
        "tone_type": "",
        "source_platform": 0,
        "video_id": "",
        "effect_id": "",
        "resource_id": "",
        "third_resource_id": "",
        "category_id": "",
        "intensifies_path": "",
        "formula_id": "",
        "check_flag": 3,
        "team_id": "",
        "local_material_id": registration_id,
        "tone_speaker": "",
        "mock_tone_speaker": "",
        "tone_effect_id": "",
        "tone_effect_name": "",
        "tone_platform": "",
        "cloned_model_type": "",
        "tone_category_id": "",
        "tone_category_name": "",
        "tone_second_category_id": "",
        "tone_second_category_name": "",
        "tone_emotion_name_key": "",
        "tone_emotion_style": "",
        "tone_emotion_role": "",
        "tone_emotion_selection": "",
        "tone_emotion_scale": 0.0,
        "moyin_emotion": "",
        "request_id": "",
        "query": "",
        "search_id": "",
        "sound_separate_type": "",
        "is_text_edit_overdub": False,
        "is_ugc": False,
        "is_ai_clone_tone": False,
        "is_ai_clone_tone_post": False,
        "source_from": "",
        "copyright_limit_type": "none",
        "aigc_history_id": "",
        "aigc_item_id": "",
        "music_source": "",
        "pgc_id": "",
        "pgc_name": "",
        "similiar_music_info": {"original_song_id": "", "original_song_name": ""},
        "ai_music_type": 0,
        "ai_music_enter_from": "",
        "lyric_type": 0,
        "tts_task_id": "",
        "tts_generate_scene": "",
        "ai_music_generate_scene": 0,
        "tts_benefit_info": {
            "benefit_type": "none",
            "benefit_log_id": "",
            "benefit_log_extra": "",
            "benefit_amount": -1
        }
    }


def media_extras(materials, video=False):
    ids = {
        "speed": new_id(),
        "placeholder": new_id(),
        "canvas": new_id(),
        "animation": new_id(),
        "sound": new_id(),
        "color": new_id(),
        "vocal": new_id()
    }
    if not video:
        ids["loudness"] = new_id()
    materials["speeds"].append({"id": ids["speed"], "type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None})
    materials["placeholder_infos"].append({"id": ids["placeholder"], "type": "placeholder_info", "meta_type": "none", "res_path": "", "res_text": "", "error_path": "", "error_text": ""})
    materials["canvases"].append({"id": ids["canvas"], "type": "canvas_color", "color": "", "blur": 0.0, "image": "", "album_image": "", "image_id": "", "image_name": "", "source_platform": 0, "team_id": ""})
    materials["material_animations"].append({"id": ids["animation"], "type": "sticker_animation", "animations": [], "multi_language_current": "none"})
    materials["sound_channel_mappings"].append({"id": ids["sound"], "type": "" if video else "none", "audio_channel_mapping": 0, "is_config_open": False})
    materials["material_colors"].append({"id": ids["color"], "is_color_clip": False, "is_gradient": False, "solid_color": "", "gradient_colors": [], "gradient_percents": [], "gradient_angle": 90.0, "width": 0.0, "height": 0.0})
    if not video:
        materials["loudnesses"].append({"id": ids["loudness"], "enable": False, "time_range": None, "file_id": "", "target_loudness": 0.0, "loudness_param": None})
    materials["vocal_separations"].append({"id": ids["vocal"], "type": "vocal_separation", "choice": 0, "removed_sounds": [], "time_range": None, "production_path": "", "final_algorithm": "", "enter_from": ""})
    return list(ids.values())


def make_photo_segment(segment_id, material_id, start, duration, width, height, canvas_width, canvas_height, placement, extra_ids):
    if placement == "fill":
        scale = max(canvas_width / width, canvas_height / height)
    elif placement == "fit":
        scale = min(canvas_width / width, canvas_height / height)
    else:
        scale = 1.0
    return {
        "id": segment_id,
        "source_timerange": {"start": 0, "duration": duration},
        "target_timerange": {"start": start, "duration": duration},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "",
        "state": 0,
        "speed": 1.0,
        "is_loop": False,
        "is_tone_modify": False,
        "reverse": False,
        "intensifies_audio": False,
        "cartoon": False,
        "volume": 1.0,
        "last_nonzero_volume": 1.0,
        "clip": {
            "scale": {"x": scale, "y": scale},
            "rotation": 0.0,
            "transform": {"x": 0.0, "y": 0.0},
            "flip": {"vertical": False, "horizontal": False},
            "alpha": 1.0
        },
        "uniform_scale": {"on": True, "value": 1.0},
        "material_id": material_id,
        "extra_material_refs": extra_ids,
        "render_index": 0,
        "keyframe_refs": [],
        "enable_lut": False,
        "enable_adjust": False,
        "enable_hsl": False,
        "visible": True,
        "group_id": "",
        "enable_color_curves": True,
        "enable_hsl_curves": True,
        "track_render_index": 0,
        "hdr_settings": None,
        "enable_color_wheels": True,
        "track_attribute": 0,
        "is_placeholder": False,
        "template_id": "",
        "enable_smart_color_adjust": False,
        "template_scene": "default",
        "common_keyframes": [],
        "caption_info": None,
        "responsive_layout": {"enable": False, "target_follow": "", "size_layout": 0, "horizontal_pos_layout": 0, "vertical_pos_layout": 0},
        "enable_color_match_adjust": False,
        "enable_color_correct_adjust": False,
        "enable_adjust_mask": False,
        "raw_segment_id": "",
        "lyric_keyframes": None,
        "enable_video_mask": True,
        "digital_human_template_group_id": "",
        "color_correct_alg_result": "",
        "source": "segmentsourcenormal",
        "enable_mask_stroke": False,
        "enable_mask_shadow": False,
        "enable_color_adjust_pro": False,
        "segment_color_tag": ""
    }


def make_video_segment(segment_id, material_id, start, duration, width, height, canvas_width, canvas_height, placement, extra_ids):
    segment = make_photo_segment(segment_id, material_id, start, duration, width, height, canvas_width, canvas_height, placement, extra_ids)
    segment["enable_lut"] = True
    segment["enable_adjust"] = True
    segment["hdr_settings"] = {"mode": 1, "intensity": 1.0, "nits": 1000}
    segment["hdr_vivid_settings"] = None
    return segment


def zoom_keyframe(offset, value):
    return {
        "id": new_id(),
        "curveType": "Line",
        "time_offset": round(offset),
        "left_control": {"x": 0.0, "y": 0.0},
        "right_control": {"x": 0.0, "y": 0.0},
        "values": [round(value, 6)],
        "string_value": "",
        "graphID": ""
    }


def zoom_keyframe_group(property_type, duration, start_scale, end_scale):
    return {
        "id": new_id(),
        "material_id": "",
        "property_type": property_type,
        "keyframe_list": [zoom_keyframe(0, start_scale), zoom_keyframe(duration, end_scale)]
    }


def apply_zoom(segments, mode, amount):
    # Ken Burns zoom: the scale keyframes CapCut draws as diamonds in the keyframe
    # panel. time_offset is RELATIVE to the clip (0 = clip start, duration = clip
    # end) because absolute offsets only animate the clip that sits at t=0.
    # clip.scale keeps the fit/fill/native placement scale and the keyframes
    # multiply it, so a zoomed clip stays framed the way the placement asked.
    if mode == "none" or not segments:
        return 0
    for index, segment in enumerate(segments):
        clip = segment.get("clip") or {}
        scale = (clip.get("scale") or {}).get("x")
        base = float(scale) if isinstance(scale, (int, float)) and scale > 0 else 1.0
        if mode == "in":
            start_scale, end_scale = base, base * (1.0 + amount)
        elif mode == "out":
            start_scale, end_scale = base * (1.0 + amount), base
        else:
            start_scale, end_scale = (base, base * (1.0 + amount)) if index % 2 == 0 else (base * (1.0 + amount), base)
        duration = (segment.get("target_timerange") or {}).get("duration") or 0
        segment["common_keyframes"] = [
            zoom_keyframe_group("KFTypeScaleX", duration, start_scale, end_scale),
            zoom_keyframe_group("KFTypeScaleY", duration, start_scale, end_scale)
        ]
    return len(segments)


def make_audio_track(material_id, duration, track_index, materials):
    ids = {
        "speed": new_id(),
        "placeholder": new_id(),
        "sound": new_id(),
        "beat": new_id(),
        "vocal": new_id()
    }
    materials["speeds"].append({"id": ids["speed"], "type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None})
    materials["placeholder_infos"].append({"id": ids["placeholder"], "type": "placeholder_info", "meta_type": "none", "res_path": "", "res_text": "", "error_path": "", "error_text": ""})
    materials["sound_channel_mappings"].append({"id": ids["sound"], "type": "none", "audio_channel_mapping": 0, "is_config_open": False})
    materials["beats"].append({
        "id": ids["beat"],
        "type": "beats",
        "enable_ai_beats": False,
        "gear": 404,
        "gear_count": 0,
        "mode": 404,
        "user_beats": [],
        "user_delete_ai_beats": None,
        "ai_beats": {
            "melody_url": "",
            "melody_path": "",
            "beats_url": "",
            "beats_path": "",
            "melody_percents": [0.0],
            "beat_speed_infos": []
        }
    })
    materials["vocal_separations"].append({"id": ids["vocal"], "type": "vocal_separation", "choice": 0, "removed_sounds": [], "time_range": None, "production_path": "", "final_algorithm": "", "enter_from": ""})
    segment = {
        "id": new_id(),
        "source_timerange": {"start": 0, "duration": duration},
        "target_timerange": {"start": 0, "duration": duration},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "",
        "state": 0,
        "speed": 1.0,
        "is_loop": False,
        "is_tone_modify": False,
        "reverse": False,
        "intensifies_audio": False,
        "cartoon": False,
        "volume": 1.0,
        "last_nonzero_volume": 1.0,
        "clip": None,
        "uniform_scale": None,
        "material_id": material_id,
        "extra_material_refs": list(ids.values()),
        "render_index": 0,
        "keyframe_refs": [],
        "enable_lut": False,
        "enable_adjust": False,
        "enable_hsl": False,
        "visible": True,
        "group_id": "",
        "enable_color_curves": True,
        "enable_hsl_curves": True,
        "track_render_index": track_index,
        "hdr_settings": None,
        "enable_color_wheels": True,
        "track_attribute": 0,
        "is_placeholder": False,
        "template_id": "",
        "enable_smart_color_adjust": False,
        "template_scene": "default",
        "common_keyframes": [],
        "caption_info": None,
        "responsive_layout": {"enable": False, "target_follow": "", "size_layout": 0, "horizontal_pos_layout": 0, "vertical_pos_layout": 0},
        "enable_color_match_adjust": False,
        "enable_color_correct_adjust": False,
        "enable_adjust_mask": False,
        "raw_segment_id": "",
        "lyric_keyframes": None,
        "enable_video_mask": True,
        "digital_human_template_group_id": "",
        "color_correct_alg_result": "",
        "source": "segmentsourcenormal",
        "enable_mask_stroke": False,
        "enable_mask_shadow": False,
        "enable_color_adjust_pro": False,
        "segment_color_tag": ""
    }
    return {"id": new_id(), "type": "audio", "segments": [segment], "flag": 0, "attribute": 0, "name": "", "is_default_name": True}


def registration(path, width, height, duration, metetype, now_seconds, now_microseconds):
    return {
        "ai_group_type": "",
        "create_time": now_seconds,
        "duration": duration,
        "enter_from": 0,
        "extra_info": Path(path).name,
        "file_Path": str(path),
        "height": height,
        "id": str(uuid.uuid4()),
        "import_time": now_seconds,
        "import_time_ms": now_microseconds,
        "item_source": 1,
        "material_color_tag": "",
        "md5": "",
        "metetype": metetype,
        "roughcut_time_range": {"duration": duration if metetype in {"music", "video"} else -1, "start": 0 if metetype in {"music", "video"} else -1},
        "sub_time_range": {"duration": -1, "start": -1},
        "type": 0,
        "width": width
    }


def validate_generated(target, root_meta, media_count, audio_expected, total):
    info = load_json(target / "draft_info.json")
    meta = load_json(target / "draft_meta_info.json")
    project = load_json(target / "Timelines/project.json")
    timeline_id = info["id"]
    timeline = target / "Timelines" / timeline_id
    if not timeline.is_dir() or load_json(timeline / "draft_info.json") != info:
        raise RuntimeError("The generated timeline copy is invalid.")
    if project.get("main_timeline_id") != timeline_id:
        raise RuntimeError("The CapCut project index does not match the timeline.")
    video_tracks = [track for track in info.get("tracks", []) if track.get("type") == "video"]
    if len(video_tracks) != 1 or len(video_tracks[0].get("segments", [])) != media_count:
        raise RuntimeError("The generated media track is invalid.")
    previous_end = None
    for segment in video_tracks[0]["segments"]:
        start = segment["target_timerange"]["start"]
        duration = segment["target_timerange"]["duration"]
        if previous_end is not None and start != previous_end:
            raise RuntimeError("The media segments contain a gap or overlap.")
        previous_end = start + duration
        material = next((item for item in info["materials"]["videos"] if item["id"] == segment["material_id"]), None)
        if material is None or material.get("type") not in {"photo", "video"} or not Path(material["path"]).is_file():
            raise RuntimeError("A generated media link is missing.")
        if material["type"] == "video" and segment["source_timerange"]["duration"] > material["duration"]:
            raise RuntimeError("A generated video segment is longer than its source file.")
    if previous_end != total or info.get("duration") != total or meta.get("tm_duration") != total:
        raise RuntimeError("The generated project duration is invalid.")
    audio_tracks = [track for track in info.get("tracks", []) if track.get("type") == "audio"]
    if audio_expected != bool(audio_tracks):
        raise RuntimeError("The generated audio track is invalid.")
    entries = [entry for entry in root_meta.get("all_draft_store", []) if same_path(entry.get("draft_fold_path", ""), target)]
    if len(entries) != 1 or entries[0].get("draft_name") != info.get("name"):
        raise RuntimeError("The CapCut project list entry is invalid.")


def install_project(root, template, name, timing, ratio, fps, placement, audio, audio_seconds, assume_yes, zoom="none", zoom_amount=0.1):
    root_meta_path = root / "root_meta_info.json"
    root_meta = load_json(root_meta_path)
    target = root / name
    matching = [entry for entry in root_meta.get("all_draft_store", []) if entry.get("draft_name", "").casefold() == name.casefold() or same_path(entry.get("draft_fold_path", ""), target)]
    existing_paths = []
    if target.exists():
        existing_paths.append(target)
    for entry in matching:
        path = Path(entry.get("draft_fold_path", ""))
        if path.is_dir() and path not in existing_paths:
            existing_paths.append(path)
    if existing_paths and not assume_yes and not ask_yes(f"Back up existing project '{name}' and continue?"):
        raise RuntimeError("Cancelled. Nothing was changed.")
    staging = root / f".building-{new_id()}"
    backup_paths = []
    root_backup = None
    installed = False
    try:
        shutil.copytree(template, staging)
        id_map = replace_ids_and_timeline(staging)
        info = load_json(staging / "draft_info.json")
        timeline_id = id_map.get(info.get("id", "").upper(), new_id())
        if timeline_id not in [item.name for item in (staging / "Timelines").iterdir() if item.is_dir()]:
            old_timeline = staging / "Timelines" / info["id"]
            if old_timeline.is_dir():
                old_timeline.rename(staging / "Timelines" / timeline_id)
        info["id"] = timeline_id
        info["name"] = name
        info["duration"] = timing["total"]
        info["fps"] = float(fps)
        info["canvas_config"] = {"ratio": "original" if ratio == "16:9" else ratio, "width": ratio_width(ratio), "height": ratio_height(ratio), "background": None}
        info["tracks"] = []
        info["group_container"] = None
        info["cover"] = None
        info["retouch_cover"] = None
        info["extra_info"] = None
        for values in info.get("materials", {}).values():
            if isinstance(values, list):
                values.clear()
        media_dir = staging / "banong-media"
        media_dir.mkdir(parents=True, exist_ok=True)
        segments = []
        materials = info["materials"]
        for key in ("videos", "audios", "speeds", "placeholder_infos", "canvases", "material_animations", "sound_channel_mappings", "material_colors", "loudnesses", "beats", "vocal_separations"):
            materials.setdefault(key, [])
        registrations = []
        now_microseconds = time.time_ns() // 1000
        now_seconds = now_microseconds // 1_000_000
        for index, source in enumerate(timing["media"], 1):
            relative_media = Path("banong-media") / f"{index:04d}-{source.name}"
            linked_path(source, staging / relative_media)
            destination = target / relative_media
            start = timing["boundaries"][index - 1]
            duration = timing["boundaries"][index] - start
            material_id = new_id()
            if source.suffix.casefold() in VIDEO_EXTENSIONS:
                width, height, source_duration, has_audio = video_metadata(source)
                source_duration_microseconds = max(1, round(source_duration * 1_000_000))
                if duration / 1_000_000 > source_duration + 0.000001:
                    raise RuntimeError(f"Video '{source.name}' is only {format_time(source_duration_microseconds)} long, but its timestamp slot is {format_time(duration)}.")
                material = make_video_material(material_id, destination, width, height, source_duration, has_audio)
                extra_ids = media_extras(materials, video=True)
                segment = make_video_segment(new_id(), material_id, start, duration, width, height, ratio_width(ratio), ratio_height(ratio), placement, extra_ids)
                registrations.append(registration(destination, width, height, source_duration_microseconds, "video", now_seconds, now_microseconds + index))
            else:
                width, height = image_dimensions(source)
                material = make_photo_material(material_id, destination, width, height)
                extra_ids = media_extras(materials)
                segment = make_photo_segment(new_id(), material_id, start, duration, width, height, ratio_width(ratio), ratio_height(ratio), placement, extra_ids)
                registrations.append(registration(destination, width, height, 5_000_000, "photo", now_seconds, now_microseconds + index))
            materials["videos"].append(material)
            segments.append(segment)
        apply_zoom(segments, zoom, zoom_amount)
        info["tracks"].append({"id": new_id(), "type": "video", "segments": segments, "flag": 0, "attribute": 0, "name": "", "is_default_name": True})
        if audio is not None:
            relative_audio = Path("banong-media") / f"audio-{audio.name}"
            linked_path(audio, staging / relative_audio)
            destination = target / relative_audio
            audio_microseconds = max(1, round(audio_seconds * 1_000_000))
            audio_registration = registration(destination, 0, 0, audio_microseconds, "music", now_seconds, now_microseconds + len(timing["media"]) + 1)
            registrations.append(audio_registration)
            audio_material_id = new_id()
            materials["audios"].append(make_audio_material(audio_material_id, destination, audio_microseconds, audio_registration["id"]))
            info["tracks"].append(make_audio_track(audio_material_id, audio_microseconds, len(info["tracks"]), materials))
        first_media = media_dir / f"0001-{timing['media'][0].name}"
        create_cover(first_media, staging / "draft_cover.jpg")
        draft_id = new_id()
        now_microseconds = time.time_ns() // 1000
        payload = json.dumps(info, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        for relative in [
            Path("draft_info.json"),
            Path("draft_info.json.bak"),
            Path("template-2.tmp"),
            Path("Timelines") / timeline_id / "draft_info.json",
            Path("Timelines") / timeline_id / "draft_info.json.bak",
            Path("Timelines") / timeline_id / "template-2.tmp"
        ]:
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        project_path = staging / "Timelines/project.json"
        project = load_json(project_path)
        project["create_time"] = now_microseconds
        project["update_time"] = now_microseconds
        project["main_timeline_id"] = timeline_id
        project.setdefault("timelines", [{}])[0].update({"create_time": now_microseconds, "id": timeline_id, "update_time": now_microseconds, "is_marked_delete": False, "name": "Timeline 01"})
        write_json_atomic(project_path, project)
        project_backup = project_path.with_name("project.json.bak")
        if project_backup.exists():
            write_json_atomic(project_backup, project)
        layout_path = staging / "timeline_layout.json"
        if layout_path.is_file():
            layout = load_json(layout_path)
            for item in layout.get("dockItems", []):
                item["timelineIds"] = [timeline_id]
                item["timelineNames"] = ["Timeline 01"]
            write_json_atomic(layout_path, layout)
        meta_path = staging / "draft_meta_info.json"
        meta = load_json(meta_path)
        meta["draft_cover"] = "draft_cover.jpg"
        meta["draft_fold_path"] = str(target)
        meta["draft_id"] = draft_id
        meta["draft_name"] = name
        meta["draft_new_version"] = info.get("new_version", "")
        meta["draft_root_path"] = str(root)
        groups = meta.setdefault("draft_materials", [])
        type_zero = next((group for group in groups if group.get("type") == 0), None)
        if type_zero is None:
            type_zero = {"type": 0, "value": []}
            groups.insert(0, type_zero)
        type_zero["value"] = registrations
        material_size = sum(path.stat().st_size for path in media_dir.iterdir() if path.is_file())
        meta["draft_timeline_materials_size_"] = material_size
        meta["tm_draft_create"] = now_microseconds
        meta["tm_draft_modified"] = now_microseconds
        meta["tm_duration"] = timing["total"]
        write_json_atomic(meta_path, meta)
        write_json_atomic(staging / "draft_virtual_store.json", {
            "draft_materials": [],
            "draft_virtual_store": [
                {"type": 0, "value": [{"creation_time": 0, "display_name": "", "filter_type": 0, "id": "", "import_time": 0, "import_time_us": 0, "material_color_tag": "", "sort_sub_type": 0, "sort_type": 0, "subdraft_filter_type": 0}]},
                {"type": 1, "value": [{"child_id": item["id"], "parent_id": ""} for item in registrations]},
                {"type": 2, "value": []}
            ]
        })
        base_entry = next((entry for entry in root_meta.get("all_draft_store", []) if same_path(entry.get("draft_fold_path", ""), template)), {})
        entry = copy.deepcopy(base_entry)
        entry.update({
            "draft_cover": str(target / "draft_cover.jpg"),
            "draft_fold_path": str(target),
            "draft_id": draft_id,
            "draft_json_file": str(target / "draft_info.json"),
            "draft_name": name,
            "draft_new_version": info.get("new_version", ""),
            "draft_root_path": str(root),
            "draft_timeline_materials_size": material_size,
            "streaming_edit_draft_ready": True,
            "tm_draft_create": now_microseconds,
            "tm_draft_modified": now_microseconds,
            "tm_draft_removed": 0,
            "tm_duration": timing["total"]
        })
        root_meta["all_draft_store"] = [entry] + [item for item in root_meta.get("all_draft_store", []) if not same_path(item.get("draft_fold_path", ""), target) and item.get("draft_name", "").casefold() != name.casefold()]
        root_meta["draft_ids"] = len(root_meta["all_draft_store"])
        root_meta["root_path"] = str(root)
        root_backup = root_meta_path.with_name("root_meta_info.json.banong-backup")
        shutil.copy2(root_meta_path, root_backup)
        backup_root = root / ".banong-backup"
        backup_root.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        for existing in existing_paths:
            destination = backup_root / f"{stamp}-{existing.name}"
            counter = 1
            while destination.exists():
                destination = backup_root / f"{stamp}-{existing.name}-{counter}"
                counter += 1
            existing.rename(destination)
            backup_paths.append((existing, destination))
        staging.rename(target)
        installed = True
        write_json_atomic(root_meta_path, root_meta)
        validate_generated(target, root_meta, len(timing["media"]), audio is not None, timing["total"])
        return target, backup_paths
    except Exception:
        if root_backup is not None and root_backup.is_file():
            shutil.copy2(root_backup, root_meta_path)
        if installed and target.exists():
            target.rename(staging)
        if staging.exists():
            shutil.rmtree(staging)
        for original, backup in reversed(backup_paths):
            if backup.exists() and not original.exists():
                backup.rename(original)
        raise


def ratio_width(ratio):
    return {"16:9": 1920, "9:16": 1080, "1:1": 1080}[ratio]


def ratio_height(ratio):
    return {"16:9": 1080, "9:16": 1920, "1:1": 1080}[ratio]


def parse_ratio(value):
    normalized = value.replace("x", ":").replace("/", ":")
    if normalized not in {"16:9", "9:16", "1:1"}:
        raise ValueError("choose 16:9, 9:16, or 1:1")
    return normalized


def parse_fps(value):
    number = int(value)
    if number not in {24, 25, 30, 50, 60}:
        raise ValueError("choose 24, 25, 30, 50, or 60")
    return number


def parse_zoom(value):
    normalized = str(value).strip().casefold().replace(" ", "").replace("_", "").replace("-", "")
    aliases = {
        "none": "none", "off": "none", "no": "none",
        "in": "in", "zoomin": "in",
        "out": "out", "zoomout": "out",
        "alternate": "alternate", "alt": "alternate", "alternating": "alternate"
    }
    if normalized not in aliases:
        raise ValueError("choose none, in, out, or alternate")
    return aliases[normalized]


def parse_zoom_amount(value):
    text = str(value).strip().rstrip("%")
    if not text:
        raise ValueError("empty value")
    try:
        percent = float(text)
    except ValueError:
        raise ValueError("use a percent such as 10 or 10%") from None
    if not math.isfinite(percent) or percent <= 0 or percent > 100:
        raise ValueError("choose an amount between 1 and 100 percent")
    return percent / 100.0


def self_test():
    cases = {
        "00-05.png": 5.0,
        "0-00.jpeg": 0.0,
        "0-06.jpeg": 6.0,
        "0-11.jpeg": 11.0,
        "01-02-03.png": 3723.0,
        "00-00-07.966.png": 7.966,
        "83.5.png": 4985.0,
        "0-6.png": 6.0,
        "0.06.png": 6.0,
        "1-2-3.png": 3723.0,
        "0-00 copy.png": 0.0,
        "0-00 COPY.png": 0.0,
        "0-00-6.png": 6.0
    }
    for name, expected in cases.items():
        actual = parse_file_timestamp(name)
        if actual is None or abs(actual - expected) > 0.0001:
            raise RuntimeError(f"Self-test failed for {name}: {actual}")
    for name in ["2026-09-26.png", "1999-12-31.jpg", "photo.png", "0-60.png", "0-0-0-0.png"]:
        if parse_file_timestamp(name) is not None:
            raise RuntimeError(f"Self-test expected no timestamp for {name}.")
    media = [Path(f"00-00-{index:02d}.000.png") for index in range(7)]
    timing = build_timing(media, "even", 30, 62.0, 5.0)
    if len(timing["boundaries"]) != 8 or timing["total"] != 62_000_000:
        raise RuntimeError("Timeline self-test failed.")
    timestamp_media = [Path("0-00.png"), Path("0-05.jpg"), Path("0-10.mp4"), Path("0-15.mov")]
    timestamp_timing = build_timing(timestamp_media, "filename", 30, 0.0, 5.0)
    if timestamp_timing["total"] != 20_000_000 or [path.name for path in timestamp_timing["media"]] != ["0-00.png", "0-05.jpg", "0-10.mp4", "0-15.mov"]:
        raise RuntimeError("Timestamp media self-test failed.")
    native_segment = make_photo_segment(new_id(), new_id(), 0, 1_000_000, 1376, 768, 1920, 1080, "native", [])
    fill_segment = make_photo_segment(new_id(), new_id(), 0, 1_000_000, 1376, 768, 1920, 1080, "fill", [])
    fit_segment = make_photo_segment(new_id(), new_id(), 0, 1_000_000, 1376, 768, 1920, 1080, "fit", [])
    if native_segment["clip"]["scale"] != {"x": 1.0, "y": 1.0} or abs(fill_segment["clip"]["scale"]["x"] - 1.40625) > 0.00001 or abs(fit_segment["clip"]["scale"]["x"] - 1.3953488372) > 0.00001:
        raise RuntimeError("Scale self-test failed.")
    zoom_cases = {
        "none": [(1.0, 1.0), (1.0, 1.0)],
        "in": [(1.0, 1.1), (1.0, 1.1)],
        "out": [(1.1, 1.0), (1.1, 1.0)],
        "alternate": [(1.0, 1.1), (1.1, 1.0)]
    }
    for mode, expected in zoom_cases.items():
        segments = [make_photo_segment(new_id(), new_id(), 0, 1_000_000, 1920, 1080, 1920, 1080, "native", []) for _ in range(2)]
        apply_zoom(segments, mode, 0.1)
        for segment, (want_start, want_end) in zip(segments, expected):
            groups = segment["common_keyframes"]
            if mode == "none":
                if groups:
                    raise RuntimeError(f"Zoom self-test failed for {mode}: keyframes were written.")
                continue
            if [group["property_type"] for group in groups] != ["KFTypeScaleX", "KFTypeScaleY"]:
                raise RuntimeError(f"Zoom self-test failed for {mode}: wrong property types.")
            for group in groups:
                frames = group["keyframe_list"]
                if len(frames) != 2 or frames[0]["time_offset"] != 0 or frames[1]["time_offset"] != 1_000_000:
                    raise RuntimeError(f"Zoom self-test failed for {mode}: wrong keyframe offsets.")
                if abs(frames[0]["values"][0] - want_start) > 0.00001 or abs(frames[1]["values"][0] - want_end) > 0.00001:
                    raise RuntimeError(f"Zoom self-test failed for {mode}: wrong values {frames[0]['values'][0]} -> {frames[1]['values'][0]}.")
                if frames[0]["curveType"] != "Line" or group["material_id"] != "":
                    raise RuntimeError(f"Zoom self-test failed for {mode}: wrong keyframe shape.")
    fill_zoom = [make_photo_segment(new_id(), new_id(), 0, 2_000_000, 1376, 768, 1920, 1080, "fill", [])]
    apply_zoom(fill_zoom, "in", 0.1)
    fill_values = [frame["values"][0] for frame in fill_zoom[0]["common_keyframes"][0]["keyframe_list"]]
    if abs(fill_values[0] - 1.40625) > 0.00001 or abs(fill_values[1] - 1.40625 * 1.1) > 0.00001:
        raise RuntimeError("Zoom self-test failed: fill placement scale was not preserved.")
    original_input = builtins.input
    try:
        builtins.input = lambda prompt: ""
        if ask("Last clip length in seconds", "5", parse_number) != 5.0:
            raise RuntimeError("Prompt default self-test failed.")
    finally:
        builtins.input = original_input
    sample = {"id": new_id(), "duration": timing["total"]}
    if json.loads(json.dumps(sample)) != sample:
        raise RuntimeError("JSON self-test failed.")
    print("Self-test passed.")


def build_parser():
    parser = argparse.ArgumentParser(description="Create a CapCut media timeline from a folder.")
    parser.add_argument("--assets")
    parser.add_argument("--name")
    parser.add_argument("--duration", type=parse_number)
    parser.add_argument("--last-duration", type=parse_number)
    parser.add_argument("--timestamps")
    parser.add_argument("--timing", choices=("auto", "filename", "list", "even"), default="auto")
    parser.add_argument("--audio")
    parser.add_argument("--ratio", type=parse_ratio)
    parser.add_argument("--fps", type=parse_fps)
    placement = parser.add_mutually_exclusive_group()
    placement.add_argument("--fit", action="store_true")
    placement.add_argument("--fill", action="store_true")
    parser.add_argument("--zoom", type=parse_zoom, default="none", help="Ken Burns zoom on every clip: none, in, out, or alternate")
    parser.add_argument("--zoom-amount", type=parse_zoom_amount, default=0.1, metavar="PERCENT", help="Ken Burns zoom amount in percent, 1-100 (default 10)")
    parser.add_argument("--draft-root")
    parser.add_argument("--template")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--no-pause", action="store_true")
    parser.add_argument("--keep-open", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    if args.self_test:
        self_test()
        return
    interactive = sys.stdin.isatty()
    print("Media to Capcut Timeline by Banong Gang")
    print("==========================")
    root = find_draft_root(args.draft_root)
    print(f"CapCut drafts: {root}")
    if not args.dry_run and capcut_is_running():
        raise RuntimeError("CapCut is running. Quit CapCut completely, then run this command again.")
    default_assets = default_asset_folder()
    if args.assets:
        assets = clean_path(args.assets)
    else:
        print(f"Detected asset folder: {default_assets}")
        entered = ask("Assets folder", str(default_assets), clean_path)
        assets = entered
    if not assets.is_dir():
        raise RuntimeError(f"Asset folder does not exist: {assets}")
    media = media_files(assets)
    if not media:
        raise RuntimeError(f"No supported images or videos were found in: {assets}")
    if len(media) > 3000:
        raise RuntimeError("The HTML tool accepts at most 3000 media files.")
    if any(path.suffix.casefold() == ".webp" for path in media):
        print("WARNING: Some CapCut versions may not render .webp images.")
    mode = args.timing
    unparsed = []
    if mode == "auto":
        parsed_timestamps = [parse_file_timestamp(path) for path in media]
        if all(value is not None for value in parsed_timestamps):
            mode = "filename"
        else:
            mode = "even"
            unparsed = [path.name for path, value in zip(media, parsed_timestamps) if value is None]
            if unparsed:
                shown = ", ".join(unparsed[:8]) + (f", and {len(unparsed) - 8} more" if len(unparsed) > 8 else "")
                print()
                print(f"WARNING: {len(unparsed)} of {len(media)} filenames have no timestamp this tool can read,")
                print("so every clip is spaced evenly instead of following the filenames.")
                print(f"Files that stopped timestamp mode: {shown}")
                print("Rename them like 0-06.jpg, or pass --timing list with a timestamp file for exact control.")
    target_seconds = args.duration
    if target_seconds is None:
        if mode == "even":
            target_seconds = ask("Target length in seconds or M:SS", "62", parse_number) if interactive else 62.0
        else:
            target_seconds = 0.0
    last_seconds = args.last_duration
    if last_seconds is None:
        if mode in {"filename", "list"}:
            last_seconds = ask("Last clip length in seconds", "5", parse_number) if interactive else 5.0
        else:
            last_seconds = 0.0
    if mode in {"filename", "list"} and last_seconds < 0.2:
        raise RuntimeError("Last clip length must be at least 0.2 seconds.")
    timestamp_file = clean_path(args.timestamps) if args.timestamps else None
    if mode == "list" and timestamp_file is None:
        suggested = default_timestamp_file()
        if interactive:
            answer = ask("Timestamp file", str(suggested) if suggested else "")
            timestamp_file = clean_path(answer) if answer else None
        elif suggested is not None:
            timestamp_file = suggested
    if timestamp_file is not None and not timestamp_file.is_file():
        raise RuntimeError(f"Timestamp file does not exist: {timestamp_file}")
    audio = clean_path(args.audio) if args.audio else None
    if not args.audio and interactive:
        audio_answer = ask("Optional audio file (blank for none)", "")
        audio = clean_path(audio_answer) if audio_answer else None
    audio_seconds = 0.0
    if audio is not None:
        if not audio.is_file():
            raise RuntimeError(f"Audio file does not exist: {audio}")
        if audio.suffix.casefold() not in AUDIO_EXTENSIONS:
            print(f"WARNING: Unusual audio extension: {audio.suffix}")
        audio_seconds = audio_duration(audio)
    timing = build_timing(media, mode, args.fps or 30, target_seconds, last_seconds, timestamp_file, audio_seconds)
    media = timing["media"]
    image_count = sum(path.suffix.casefold() in IMAGE_EXTENSIONS for path in media)
    video_count = sum(path.suffix.casefold() in VIDEO_EXTENSIONS for path in media)
    default_name = datetime.now().strftime("%m%d")
    if args.name:
        name = args.name.strip()
    else:
        name = ask("CapCut project name", default_name).strip() if interactive else default_name
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\0" in name:
        raise RuntimeError("Project name is invalid.")
    ratio = args.ratio or (ask("Ratio", "16:9", parse_ratio) if interactive else "16:9")
    fps = args.fps or (ask("Frame rate", "30", parse_fps) if interactive else 30)
    zoom = args.zoom if "--zoom" in sys.argv or not interactive else ask("Ken Burns zoom (none/in/out/alternate)", "none", parse_zoom)
    zoom_amount = args.zoom_amount
    if zoom != "none" and "--zoom-amount" not in sys.argv and interactive:
        zoom_amount = ask("Ken Burns zoom amount in percent", "10", parse_zoom_amount)
    placement = "fill" if args.fill else ("fit" if args.fit else "native")
    template = find_template(root, args.template)
    matching = [entry for entry in load_json(root / "root_meta_info.json").get("all_draft_store", []) if entry.get("draft_name", "").casefold() == name.casefold()]
    print()
    print(f"Project: {name}")
    print(f"Media: {len(media)} ({image_count} images, {video_count} videos)")
    print(f"Timing: {mode}" + (f" ({len(unparsed)} of {len(media)} filenames had no readable timestamp)" if unparsed else ""))
    print(f"Length: {format_time(timing['total'])}")
    print(f"Average clip: {format_time(timing['total'] // len(media))}")
    print(f"Ratio: {ratio} at {fps} fps")
    print(f"Placement: {placement}")
    print(f"Zoom: {zoom}" + (f" {zoom_amount * 100:g}%" if zoom != "none" else ""))
    print(f"Audio: {audio if audio else 'none'}")
    print(f"Template: {template}")
    if matching:
        print("A project with this name already exists and will be backed up.")
    print()
    if not args.yes and not args.dry_run and not ask_yes("Create the CapCut project?"):
        raise RuntimeError("Cancelled. Nothing was changed.")
    if args.dry_run:
        print("Dry run complete. No files were changed.")
        return
    target, backups = install_project(root, template, name, timing, ratio, fps, placement, audio, audio_seconds, args.yes, zoom, zoom_amount)
    print()
    print(f"Created: {target}")
    print(f"Length: {format_time(timing['total'])}")
    print(f"Root index backup: {root / 'root_meta_info.json.banong-backup'}")
    for original, backup in backups:
        print(f"Project backup: {backup}")
    app = find_capcut_app()
    if not args.no_launch and app is not None:
        if args.yes or ask_yes("Open CapCut now?", True, args.yes):
            launch_capcut(app)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. Nothing was changed.")
        sys.exit(130)
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
    else:
        finish_pause()
