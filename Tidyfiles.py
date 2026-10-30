#!/usr/bin/env python3
"""
tidyfiles - Range automatiquement un dossier de téléchargements.

Fonctionnalités :
  * trie les fichiers par type (images, PDF, archives, vidéos, ...)
  * archive dans un ZIP mensuel les fichiers plus vieux que N jours
  * mode simulation (--dry-run) pour voir ce qui se passerait
  * aucune dépendance externe

Exemples :
  python tidyfiles.py --dry-run
  python tidyfiles.py --source ~/Téléchargements --days 30
  python tidyfiles.py --days 0          # tri seul, sans archivage
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

__version__ = "1.0.0"

log = logging.getLogger("tidyfiles")

# Catégorie -> extensions associées (en minuscules, avec le point)
CATEGORIES: dict[str, frozenset[str]] = {
    "Images": frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
                         ".svg", ".heic", ".tif", ".tiff", ".avif"}),
    "PDF": frozenset({".pdf"}),
    "Archives": frozenset({".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
                          ".xz", ".tgz"}),
    "Vidéos": frozenset({".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
                         ".webm", ".m4v"}),
    "Audio": frozenset({".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}),
    "Documents": frozenset({".doc", ".docx", ".odt", ".rtf", ".txt", ".md",
                            ".xls", ".xlsx", ".ods", ".csv",
                            ".ppt", ".pptx", ".odp"}),
    "Installeurs": frozenset({".exe", ".msi", ".dmg", ".pkg", ".deb",
                              ".rpm", ".appimage"}),
}
OTHER = "Autres"
ARCHIVE_DIR = "_Archives"

# Fichiers ignorés : téléchargements en cours et fichiers système
PARTIAL_SUFFIXES = frozenset({".crdownload", ".part", ".tmp", ".download"})
IGNORED_NAMES = frozenset({"desktop.ini", "Thumbs.db", ".DS_Store"})

EXT_TO_CATEGORY: dict[str, str] = {
    ext: cat for cat, exts in CATEGORIES.items() for ext in exts
}


@dataclass
class Stats:
    sorted: int = 0
    archived: int = 0
    errors: int = 0


def default_downloads() -> Path:
    """Retourne le dossier de téléchargements (FR ou EN) de l'utilisateur."""
    home = Path.home()
    for name in ("Téléchargements", "Downloads"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home / "Downloads"


def categorize(path: Path) -> str:
    return EXT_TO_CATEGORY.get(path.suffix.lower(), OTHER)


def is_candidate(path: Path) -> bool:
    """Vrai si le fichier doit être traité (ni caché, ni partiel, ni lien)."""
    return (
        path.is_file()
        and not path.is_symlink()
        and not path.name.startswith(".")
        and path.name not in IGNORED_NAMES
        and path.suffix.lower() not in PARTIAL_SUFFIXES
    )


def unique_path(dest: Path) -> Path:
    """Évite d'écraser un fichier existant : 'doc.pdf' -> 'doc (1).pdf'."""
    if not dest.exists():
        return dest
    counter = 1
    while True:
        candidate = dest.with_name(f"{dest.stem} ({counter}){dest.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def collect_files(root: Path) -> list[Path]:
    """Fichiers à la racine + fichiers déjà rangés dans les dossiers de catégorie."""
    managed = set(CATEGORIES) | {OTHER}
    files: list[Path] = []
    for entry in root.iterdir():
        if is_candidate(entry):
            files.append(entry)
        elif entry.is_dir() and entry.name in managed:
            files.extend(p for p in entry.iterdir() if is_candidate(p))
    return files


def archive_group(root: Path, key: str, paths: list[Path],
                  dry_run: bool, stats: Stats) -> None:
    """Ajoute des fichiers anciens au ZIP du mois `key` (YYYY-MM), puis les supprime."""
    archive_dir = root / ARCHIVE_DIR
    archive_path = archive_dir / f"{key}.zip"
    log.info("ARCH  %d fichier(s) -> %s/%s.zip", len(paths), ARCHIVE_DIR, key)

    if dry_run:
        stats.archived += len(paths)
        return

    archive_dir.mkdir(exist_ok=True)
    written: list[Path] = []
    try:
        with zipfile.ZipFile(archive_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
            existing = set(zf.namelist())
            for path in paths:
                category = path.parent.name if path.parent != root else categorize(path)
                arcname = f"{category}/{path.name}"
                if arcname in existing:
                    arcname = f"{category}/{path.stem}_{len(existing)}{path.suffix}"
                zf.write(path, arcname)
                existing.add(arcname)
                written.append(path)
    except (OSError, zipfile.BadZipFile) as exc:
        log.error("Échec de l'archivage %s : %s", archive_path.name, exc)
        stats.errors += 1

    # Suppression seulement après écriture réussie dans le ZIP
    for path in written:
        try:
            path.unlink()
            stats.archived += 1
        except OSError as exc:
            log.error("Impossible de supprimer %s : %s", path.name, exc)
            stats.errors += 1


def process(root: Path, days: int, dry_run: bool) -> Stats:
    stats = Stats()
    cutoff = time.time() - days * 86400 if days > 0 else None
    old_files: dict[str, list[Path]] = defaultdict(list)

    for path in collect_files(root):
        try:
            mtime = path.stat().st_mtime
        except OSError as exc:
            log.error("Lecture impossible de %s : %s", path.name, exc)
            stats.errors += 1
            continue

        # 1) Fichier ancien -> à archiver (regroupé par mois de modification)
        if cutoff is not None and mtime < cutoff:
            old_files[datetime.fromtimestamp(mtime).strftime("%Y-%m")].append(path)
            continue

        # 2) Fichier récent à la racine -> à trier dans sa catégorie
        if path.parent == root:
            dest = unique_path(root / categorize(path) / path.name)
            log.info("TRI   %s -> %s", path.name, dest.relative_to(root))
            if not dry_run:
                try:
                    dest.parent.mkdir(exist_ok=True)
                    shutil.move(str(path), dest)
                except OSError as exc:
                    log.error("Déplacement impossible de %s : %s", path.name, exc)
                    stats.errors += 1
                    continue
            stats.sorted += 1
        # 3) Fichier récent déjà rangé -> on ne touche à rien

    for key, paths in sorted(old_files.items()):
        archive_group(root, key, paths, dry_run, stats)

    return stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="tidyfiles",
        description="Trie un dossier de téléchargements par type et archive les vieux fichiers.",
    )
    parser.add_argument("-s", "--source", type=Path, default=default_downloads(),
                        help="dossier à ranger (défaut : Téléchargements/Downloads)")
    parser.add_argument("-d", "--days", type=int, default=30,
                        help="archiver les fichiers plus vieux que N jours (0 = désactivé)")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="simuler sans rien modifier")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="affichage détaillé")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if args.days < 0:
        log.error("--days doit être positif ou nul.")
        return 2

    root = args.source.expanduser().resolve()
    if not root.is_dir():
        log.error("Dossier introuvable : %s", root)
        return 1

    if args.dry_run:
        log.info("Mode simulation : aucun fichier ne sera modifié.")
    log.info("Dossier : %s", root)

    stats = process(root, args.days, args.dry_run)

    log.info("Terminé : %d trié(s), %d archivé(s), %d erreur(s).",
             stats.sorted, stats.archived, stats.errors)
    return 1 if stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())