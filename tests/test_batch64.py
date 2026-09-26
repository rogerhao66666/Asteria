from pathlib import Path
import pytest
from asteria.assets import *
def make(tmp,items):
 s=tmp/"pkg";s.mkdir()
 for n,v in items.items():p=s/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v)
 return s
def test_install_tree(tmp_path):
 s=make(tmp_path,{"hero.asset.json":"{}","textures/hero.png":"png"});a=tmp_path/"project/Assets"
 q=AssetPackageInstaller(a).install_tree(s);assert q.ok and (a/"hero.asset.json").read_text()=="{}" and (a/"textures/hero.png").read_text()=="png"
def test_destination(tmp_path):
 s=make(tmp_path,{"x.asset.json":"{}"});a=tmp_path/"Assets";q=AssetPackageInstaller(a).install_tree(s,destination="Characters/Hero");assert q.ok and (a/"Characters/Hero/x.asset.json").exists()
@pytest.mark.parametrize("bad",["../escape","a/../../escape","/absolute"])
def test_reject_traversal(tmp_path,bad):
 s=make(tmp_path,{"x":"x"});q=AssetPackageInstaller(tmp_path/"Assets").install(s,[bad]);assert not q.ok and q.issues[0].code=="install.unsafe_path"
def test_missing_all_or_nothing(tmp_path):
 s=make(tmp_path,{"a":"a"});a=tmp_path/"Assets";q=AssetPackageInstaller(a).install(s,["a","missing"]);assert not q.ok and not (a/"a").exists()
def test_collision_error_preserves_existing(tmp_path):
 s=make(tmp_path,{"a":"new","b":"b"});a=tmp_path/"Assets";a.mkdir();(a/"a").write_text("old");q=AssetPackageInstaller(a).install_tree(s);assert not q.ok and (a/"a").read_text()=="old" and not (a/"b").exists()
def test_replace(tmp_path):
 s=make(tmp_path,{"a":"new","b":"b"});a=tmp_path/"Assets";a.mkdir();(a/"a").write_text("old");q=AssetPackageInstaller(a).install_tree(s,collision="replace");assert q.ok and (a/"a").read_text()=="new" and (a/"b").read_text()=="b" and q.replaced==("a",)
def test_manifest_preserved_exact(tmp_path):
 body='{"asset_id":"hero","kind":"monster","custom":{"x":9}}';s=make(tmp_path,{"hero.asset.json":body});a=tmp_path/"Assets";q=AssetPackageInstaller(a).install_tree(s);assert q.ok and (a/"hero.asset.json").read_text()==body
def test_nested_dirs(tmp_path):
 s=make(tmp_path,{"a/b/c/d.png":"x","a/b/c/d.asset.json":"{}"});a=tmp_path/"Assets";assert AssetPackageInstaller(a).install_tree(s).ok and (a/"a/b/c/d.png").exists()
def test_duplicate_paths(tmp_path):
 s=make(tmp_path,{"a":"a"});q=AssetPackageInstaller(tmp_path/"Assets").install(s,["a","a"]);assert not q.ok and q.issues[0].code=="install.duplicate_path"
def test_bad_policy(tmp_path):
 s=make(tmp_path,{"a":"a"});assert not AssetPackageInstaller(tmp_path/"Assets").install_tree(s,collision="merge").ok
def test_10000_files(tmp_path):
 s=tmp_path/"pkg";s.mkdir()
 for i in range(10000):(s/f"{i}.asset.json").write_text("{}")
 a=tmp_path/"Assets";q=AssetPackageInstaller(a).install_tree(s);assert q.ok and len(q.installed)==10000 and len(list(a.glob("*.asset.json")))==10000
