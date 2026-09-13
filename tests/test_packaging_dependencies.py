import tomllib
from pathlib import Path


def test_dev_extra_declares_pillow_for_image_asset_tests():
    project = Path(__file__).parents[1] / "pyproject.toml"
    data = tomllib.loads(project.read_text(encoding="utf-8"))
    dependencies = data["project"]["optional-dependencies"]["dev"]
    assert any(requirement.lower().startswith("pillow") for requirement in dependencies)
