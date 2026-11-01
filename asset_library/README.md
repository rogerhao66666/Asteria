# Asset library

Free art that ships with the engine, sorted by what it holds. Every pack keeps its own folder
name and its licence file; where each came from is in `THIRD_PARTY_ASSETS.md`.

| Folder | What is in it |
| --- | --- |
| `characters/` | Heroes and monsters alike (anything that can walk a map or fight) |
| `tilesets/` | Map tiles |
| `objects/` | Things placed on a map: chests, traps |
| `items/` | Equipment and pickups |
| `icons/` | Item and skill icons |
| `effects/` | Spell and hit effects |
| `ui/` | Panels, HUD pieces, numbers |
| `models_3d/` | 3D models and animations (KayKit) |
| `fonts/` | Fonts used by exports |

A project takes pictures from here with **File ▸ Import from Asset Library…** (they are copied
into the project). Scripts find a pack by name, whatever folder holds it:
`asteria.assets.library.find_pack("Foozle_2DC0009_Lucifer_Warrior_Pixel_Art")`.

## Your own pictures

A project sorts its own pictures the same way, by folder. Put a picture in a folder of the
project named after its kind - `playable_assets/characters/my_hero.png` - and the editor offers
it wherever that kind is chosen (double-click an actor's picture in Database ▸ Actors). A map
character is a 3×4 walking sheet: three steps across, facing down, left, right and up from top
to bottom. **Browse…** in the same dialog takes a file from anywhere and copies it into
`playable_assets/characters/`.

---

# 素材庫

隨引擎附的免費素材，依種類分資料夾。每個素材包保留原本的資料夾名稱和授權檔；來源寫在
`THIRD_PARTY_ASSETS.md`。

| 資料夾 | 內容 |
| --- | --- |
| `characters/` | 角色與怪物（會在地圖上走、會戰鬥的都算） |
| `tilesets/` | 地圖圖塊 |
| `objects/` | 放在地圖上的物件：寶箱、陷阱 |
| `items/` | 裝備與道具 |
| `icons/` | 道具與技能圖示 |
| `effects/` | 法術與打擊特效 |
| `ui/` | 面板、HUD、數字 |
| `models_3d/` | 3D 模型與動作（KayKit） |
| `fonts/` | 匯出用字型 |

專案用 **檔案 ▸ 從素材庫匯入…** 從這裡挑圖（會複製進專案）。

## 自己的圖

專案自己的圖也用資料夾分類：把圖放進專案裡以種類命名的資料夾，例如
`playable_assets/characters/my_hero.png`，編輯器在挑那種圖的地方就會列出來（Database ▸
Actors 雙擊角色圖框）。地圖角色是 3×4 行走圖：橫向三個步伐，由上到下面向下、左、右、上。
同一個視窗的 **瀏覽…** 可以從電腦任何地方選圖，會自動複製到 `playable_assets/characters/`。
