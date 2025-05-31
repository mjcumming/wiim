#!/usr/bin/env python3
"""
Script to find references to WiiM entities with _2 suffixes in Home Assistant configuration.
Run this in your Home Assistant config directory.
"""

import json
from pathlib import Path
import re


def find_stale_references(ha_config_path="."):
    """Find all references to WiiM entities with _2 suffixes."""

    # Entities to search for
    stale_entities = ["media_player.master_bedroom_2", "media_player.main_floor_speakers_2", "media_player.outdoor_2"]

    found_references = []

    # Search patterns
    patterns = [re.compile(re.escape(entity)) for entity in stale_entities]

    # Files to search
    search_files = ["configuration.yaml", "automations.yaml", "scripts.yaml", "scenes.yaml", "groups.yaml"]

    # Search in main config files
    for filename in search_files:
        filepath = Path(ha_config_path) / filename
        if filepath.exists():
            try:
                with open(filepath, "r") as f:
                    content = f.read()
                    for i, line in enumerate(content.split("\n"), 1):
                        for pattern in patterns:
                            if pattern.search(line):
                                found_references.append(
                                    {"file": filename, "line": i, "content": line.strip(), "entity": pattern.pattern}
                                )
            except Exception as e:
                print(f"Error reading {filepath}: {e}")

    # Search in .storage directory for UI configurations
    storage_path = Path(ha_config_path) / ".storage"
    if storage_path.exists():
        for storage_file in storage_path.glob("*.json"):
            try:
                with open(storage_file, "r") as f:
                    content = f.read()
                    for pattern in patterns:
                        if pattern.search(content):
                            # Try to parse as JSON for better formatting
                            try:
                                json.loads(content)
                                found_references.append(
                                    {
                                        "file": f".storage/{storage_file.name}",
                                        "line": "JSON",
                                        "content": f"Found in JSON: {pattern.pattern}",
                                        "entity": pattern.pattern,
                                    }
                                )
                            except json.JSONDecodeError:
                                found_references.append(
                                    {
                                        "file": f".storage/{storage_file.name}",
                                        "line": "?",
                                        "content": "Found in storage file",
                                        "entity": pattern.pattern,
                                    }
                                )
            except Exception as e:
                print(f"Error reading {storage_file}: {e}")

    return found_references


def main():
    print("🔍 Searching for stale WiiM entity references...")
    print("=" * 60)

    references = find_stale_references()

    if not references:
        print("✅ No stale entity references found!")
        return

    print(f"❌ Found {len(references)} stale references:")
    print()

    for ref in references:
        print(f"📁 File: {ref['file']}")
        print(f"📍 Line: {ref['line']}")
        print(f"🎯 Entity: {ref['entity']}")
        print(f"📝 Content: {ref['content']}")
        print("-" * 40)

    print()
    print("🛠️  To fix these:")
    print("1. Edit the files above")
    print("2. Replace '_2' entities with correct entity IDs")
    print("3. Or remove the references entirely")
    print("4. Restart Home Assistant")


if __name__ == "__main__":
    main()
