from __future__ import annotations

import json
import sys
import tempfile
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "utils"))

check = import_module("check_conda_env")


def write_distribution(site_packages: Path) -> None:
    dist_info = site_packages / "boolean_py-5.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: boolean.py\nVersion: 5.0\n"
    )
    (dist_info / "direct_url.json").write_text(
        json.dumps(
            {
                "url": "https://example.org/boolean.py.git",
                "vcs_info": {"vcs": "git", "commit_id": "abc123"},
            }
        )
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        prefix = root / "env"
        conda_meta = prefix / "conda-meta"
        conda_meta.mkdir(parents=True)
        (conda_meta / "python-3.11.9-h123_0.json").write_text(
            json.dumps(
                {
                    "name": "python",
                    "version": "3.11.9",
                    "build": "h123_0",
                }
            )
        )
        write_distribution(prefix / "lib" / "python3.11" / "site-packages")

        yaml = root / "environment.yml"
        yaml.write_text(
            """\
name: scbolt-test
dependencies:
  - python=3.11.9=h123_0
  - pip:
      - boolean-py==5.0
"""
        )

        name, expected = check.read_environment_yaml(yaml)
        installed = check.installed_environment(prefix)

        assert name == "scbolt-test"
        assert check.compare_specs(expected, installed.packages) == []
        assert check.direct_url_commit(installed.distributions, "boolean-py") == (
            "abc123"
        )

    print("conda environment check tests passed")


if __name__ == "__main__":
    main()
