# 參與 Asteria

謝謝你願意幫忙！Asteria 是個人興趣專案，處於 Alpha 階段：歡迎回報問題和送 PR，但回應時間不保證。

*English: issues and pull requests are welcome; this is a hobby project, so replies may take a while.
The rules below apply in either language.*

## 回報問題

請用 [Issues](https://github.com/rogerhao66666/Asteria/issues) 的範本，並附上：

- 作業系統、Python 版本、`pip show asteria` 的版本；
- 重現步驟（最好附上專案檔或最小的範例）；
- 預期結果和實際結果，有錯誤訊息或截圖更好。

## 開發環境

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[pygame,editor,mv,dev]"
python -m pytest -q
```

測試在無頭環境跑（SDL dummy driver、Qt offscreen），和 CI 一樣。

## 送 PR 前

1. **每個改動都要有測試**：修 bug 時先寫一個會失敗的測試，再修到它通過。
2. **全部測試通過**：`python -m pytest -q`。
3. **Lint 與格式**：每個 Python 檔每行 ≤ 99 字元。
   ```bash
   ruff check src scripts tests reference_projects
   ruff format --check src scripts tests reference_projects
   ```
4. **一個 PR 做一件事**，說明「為什麼」而不只是「改了什麼」。
5. **不要刪除既有功能**：要移除或改變行為，請先開 issue 討論。

## 設計原則

- **不限制作者**：有不只一種合理答案的規則，做成編輯器裡的選項，而不是寫死。
- **系統通用**：引擎裡不寫任何一款特定遊戲的規則；範例遊戲只是資料。
- **有證據才算完成**：功能有測試；畫面相關的改動，請附上實際畫面的截圖。

重要的設計決策記在 [`docs/audits/DECISION_LOG.md`](docs/audits/DECISION_LOG.md)。

## 素材

送進 repo 的素材必須能再散布：CC0 最好，CC-BY 需在
[`THIRD_PARTY_ASSETS.md`](THIRD_PARTY_ASSETS.md) 寫明作者與來源。**不要**提交 RPG Maker 內建素材、
從商業遊戲擷取的素材，或授權禁止再散布的素材；這類素材只能放在 git 忽略的 `local_reference/`。

## 授權

你送出的貢獻會以本專案的 [MIT License](LICENSE) 授權。
