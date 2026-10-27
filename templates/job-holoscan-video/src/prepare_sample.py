"""Download the pinned NVIDIA/CAMMA research sample; preserve its license.

The resource license is https://developer.nvidia.com/clara-holoscan-EULA.
Downloaded model/video bytes are separate from the Apache-2.0 recipe source.
"""

import argparse
import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

URL = "https://api.ngc.nvidia.com/v2/resources/nvidia/clara-holoscan/holoscan_endoscopy_sample_data/versions/20230222/zip"
FILES = {
    "tool_loc_convlstm.onnx": "d05733d49187f10975eafd762001f4535f5029fd071ca39779f953c7886a3c18",
    "surgical_video.264": "09433acf51490090a3d2ccaa21454404967e28e3741b566c5adf4fc1e352a307",
    "NVIDIA-Clara-Holoscan-SDK-EULA.pdf": "81fc6e37c96278db7dd60aab75a9be7f406e65a1c4c8fb417b4552a2654d72c2",
}


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="holoscan-sample-") as directory:
        archive = Path(directory) / "sample.zip"
        try:
            with (
                urllib.request.urlopen(URL, timeout=120) as source,
                archive.open("wb") as target,
            ):
                shutil.copyfileobj(source, target)
        except Exception:
            # Redirect exceptions may contain signed URLs.
            raise RuntimeError(
                "NGC sample download failed; retry or inspect NGC resource availability"
            ) from None
        with zipfile.ZipFile(archive) as handle:
            for name, expected in FILES.items():
                if handle.namelist().count(name) != 1:
                    raise ValueError("NGC archive member identity differs")
                data = handle.read(name)
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError(
                        "NGC asset bytes differ from the pinned 20230222 resource"
                    )
                path = output / name
                if (
                    path.exists()
                    and hashlib.sha256(path.read_bytes()).hexdigest() != expected
                ):
                    raise ValueError(
                        "Existing asset differs; select a new output directory"
                    )
                path.write_bytes(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args().output)
