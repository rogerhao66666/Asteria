from pathlib import Path
from PIL import Image
import json
import pytest
from asteria.assets.character_generator import *
from asteria.editor.character_generator_workspace import CharacterGeneratorWorkspace

def mkpart(tmp_path, pid, category, rgba):
    frames={}
    for d in DIRECTIONS:
        frames[d]=[]
        for i in range(3):
            p=tmp_path/f"{pid}_{d}_{i}.png"; Image.new("RGBA",(48,48),rgba).save(p); frames[d].append(str(p))
    return CharacterPart(pid,category,frames,pid)

def test_generator_composes_and_exports_normal_asset(tmp_path):
    body=mkpart(tmp_path,"body_a","body",(200,150,120,255)); hair=mkpart(tmp_path,"hair_a","hair_front",(20,20,20,128))
    cat=CharacterGeneratorCatalog([body,hair]); ws=CharacterGeneratorWorkspace.create(cat,"hero")
    ws.select("body","body_a"); ws.select("hair_front","hair_a")
    result=ws.generate(tmp_path/"out")
    im=Image.open(result.sheet_path)
    assert im.size==(144,192) and im.mode=="RGBA"
    meta=json.loads(Path(result.metadata_path).read_text())
    assert meta["runtime_special_type"] is False
    assert meta["layout"]["row_directions"]==list(DIRECTIONS)

def test_generator_rejects_wrong_frame_dimensions(tmp_path):
    p=mkpart(tmp_path,"body_a","body",(1,2,3,255)); Image.new("RGBA",(32,32)).save(p.frames["up"][1])
    with pytest.raises(ValueError): CharacterGenerator(CharacterGeneratorCatalog([p])).generate(CharacterRecipe("x",parts={"body":"body_a"}),tmp_path/"out")

def test_workspace_rejects_category_mismatch(tmp_path):
    p=mkpart(tmp_path,"hair","hair_front",(1,2,3,255)); ws=CharacterGeneratorWorkspace.create(CharacterGeneratorCatalog([p]))
    with pytest.raises(ValueError): ws.select("body","hair")

def test_workspace_preview_matches_selected_layers(tmp_path):
    body=mkpart(tmp_path,"body","body",(100,80,60,255)); eyes=mkpart(tmp_path,"eyes","eyes",(20,30,40,128))
    ws=CharacterGeneratorWorkspace.create(CharacterGeneratorCatalog([body,eyes]))
    ws.select("body","body"); ws.select("eyes","eyes")
    im=ws.preview_frame("left",2)
    assert im.size==(48,48) and im.mode=="RGBA"
    assert im.getbbox()==(0,0,48,48)

def test_workspace_preview_rejects_bad_direction_and_frame(tmp_path):
    ws=CharacterGeneratorWorkspace.create(CharacterGeneratorCatalog())
    with pytest.raises(ValueError): ws.preview_frame("diagonal",0)
    with pytest.raises(IndexError): ws.preview_frame("down",99)
