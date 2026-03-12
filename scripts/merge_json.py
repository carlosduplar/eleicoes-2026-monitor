import json
import sys
from pathlib import Path


def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def merge_json(ours_path, theirs_path, output_path):
    ours = load_json(ours_path)
    theirs = load_json(theirs_path)

    if ours is None and theirs is None:
        return False
    if ours is None:
        json.dump(theirs, output_path.open("w"), indent=2, ensure_ascii=False)
        return True
    if theirs is None:
        json.dump(ours, output_path.open("w"), indent=2, ensure_ascii=False)
        return True

    if isinstance(ours, list) and isinstance(theirs, list):
        merged = list(ours)
        ids = {
            item.get("id") or item.get("url")
            for item in merged
            if isinstance(item, dict)
        }
        for item in theirs:
            if isinstance(item, dict):
                key = item.get("id") or item.get("url")
                if key and key not in ids:
                    merged.append(item)
                    ids.add(key)
    elif isinstance(ours, dict) and isinstance(theirs, dict):
        merged = {**ours, **theirs}
    else:
        merged = theirs

    json.dump(merged, output_path.open("w"), indent=2, ensure_ascii=False)
    return True


if __name__ == "__main__":
    ours = sys.argv[1]
    theirs = sys.argv[2]
    output = sys.argv[3]
    merge_json(Path(ours), Path(theirs), Path(output))
