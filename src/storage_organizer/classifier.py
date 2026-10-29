from pathlib import Path

EXTENSIONS: dict[str, set[str]] = {
    "Photos": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".raw", ".dng", ".cr2", ".nef", ".arw", ".orf", ".rw2"},
    "Videos": {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".mpeg", ".mpg", ".3gp", ".mts", ".m2ts"},
    "Documents": {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".csv", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".json", ".xml", ".html", ".htm"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".aiff"},
    "Archives": {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz", ".tgz"},
}


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    for category, extensions in EXTENSIONS.items():
        if suffix in extensions:
            return category
    return "Other"
