from asteria.assets import *


def test_import_cache_pipeline(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    record = AssetRecord.create(
        kind="texture", source_path="assets/x.png", importer="texture"
    )
    cache = ImportCache()
    pipe = ImportPipeline(cache)
    fp = fingerprint_file(f)
    artifact = pipe.commit(
        asset_record=record, fingerprint=fp, artifact_extension=".tex"
    )
    assert cache.get(record.id).key == artifact.key
