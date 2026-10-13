"""Component data migrations (ASTERIA_SPEC §33 versioning + migration).

When a component schema's ``version`` increases, register one step per
version so older project files still load:

    @component_migration("asteria.Example", from_version=1)
    def _example_v1_to_v2(fields):
        fields["new_name"] = fields.pop("old_name")
        return fields

``deserialize_component`` applies the steps in order before validating.
"""

from __future__ import annotations

_STEPS: dict[tuple[str, int], object] = {}


class MigrationError(ValueError):
    pass


def component_migration(type_name, *, from_version):
    def register(func):
        key = (str(type_name), int(from_version))
        if key in _STEPS:
            raise MigrationError(f"duplicate migration for {type_name} v{from_version}")
        _STEPS[key] = func
        return func

    return register


def migrate_component_fields(type_name, fields, from_version, to_version):
    """Return ``fields`` upgraded from ``from_version`` to ``to_version``."""
    if from_version > to_version:
        raise MigrationError(
            f"{type_name} v{from_version} is newer than this engine (v{to_version})"
        )
    fields = dict(fields)
    for version in range(int(from_version), int(to_version)):
        step = _STEPS.get((type_name, version))
        if step is None:
            raise MigrationError(f"no migration for {type_name} from v{version} to v{version + 1}")
        fields = step(dict(fields))
    return fields
