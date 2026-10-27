#!/usr/bin/env python3
"""Fetch one upstream validation case from the official MSD archive (~1.6 GB download)."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

URL = "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task09_Spleen.tar"
ARCHIVE_SHA256 = "dfeba347daae4fb08c38f4d243ab606b28b91b206ffc445ec55c35489fa65e60"
FILES = {
    "image.nii.gz": ("imagesTr", "78338b0015e5f4da8914e89147344cb9e0f6580237a654c70b3b24e85d87c9e2"),
    "label.nii.gz": ("labelsTr", "5df8d757e4ca841dbe0dbf37264cf4a4cc9a3fcc3f1a8889da266ea0c03ee156"),
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--archive", type=Path, help="Reuse a previously downloaded official archive")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.archive or args.output / "Task09_Spleen.tar"
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError("MSD archive checksum differs; download the complete official archive")
    with tarfile.open(archive) as source:
        for destination, (group, checksum) in FILES.items():
            member = source.getmember(f"Task09_Spleen/{group}/spleen_56.nii.gz")
            if not member.isfile():
                raise ValueError("Expected a regular NIfTI volume")
            data = source.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError("MSD example file checksum differs")
            (args.output / destination).write_bytes(data)
    (args.output / "DATA-LICENSE.json").write_text(json.dumps({
        "dataset": "Medical Segmentation Decathlon Task09_Spleen", "case": "spleen_56",
        "source": URL, "license": "CC-BY-SA-4.0", "attribution": "Medical Segmentation Decathlon; Memorial Sloan Kettering Cancer Center",
        "paper": "https://doi.org/10.1038/s41467-022-30695-9",
        "scope": "Published MONAI validation-subset example; not independent clinical accuracy validation",
    }, indent=2) + "\n")
    print("Verified example image.nii.gz, label.nii.gz and DATA-LICENSE.json")


if __name__ == "__main__":
    main()
