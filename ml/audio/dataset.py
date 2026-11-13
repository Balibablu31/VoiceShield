import argparse
import csv
from pathlib import Path


def parse_protocol(protocol: Path, audio_dir: Path, output: Path):
    """Convert ASVspoof LA protocol rows to file,label CSV (0 bona fide, 1 spoof)."""
    rows = []
    for line_number, line in enumerate(protocol.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        if len(parts) < 5:
            raise ValueError(f"Malformed protocol row {line_number}")
        file_id, source_label = parts[1], parts[-1].lower()
        if source_label not in {"bonafide", "spoof"}:
            raise ValueError(f"Unknown protocol label at row {line_number}: {source_label}")
        audio = audio_dir / f"{file_id}.flac"
        if not audio.is_file():
            raise FileNotFoundError(audio)
        rows.append((str(audio), int(source_label == "spoof")))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream); writer.writerow(["file", "label"]); writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("protocol", type=Path); parser.add_argument("audio_dir", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args(); parse_protocol(args.protocol, args.audio_dir, args.output)
