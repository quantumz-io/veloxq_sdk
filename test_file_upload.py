# Copyright 2025-2026 QUANTUMZ.IO sp. z o.o.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

from tqdm import tqdm

from veloxq_sdk.config import load_config

from veloxq_sdk import File


load_config("config.py")


def test_file_upload(fpath: Path, name: str) -> None:
    pbar = tqdm(
        total=fpath.stat().st_size, unit="B", unit_scale=True, desc="Uploading file"
    )
    file = File.from_path(fpath, name=name, force=True, upload_callback=pbar.update)
    pbar.close()
    assert file.id is not None


if __name__ == "__main__":
    test_file_upload(
        Path("/mnt/c/Users/hendr/Downloads/random3BodyIsing_L=100000000_1.h5"),
        name="test_big_upload_2",
    )
