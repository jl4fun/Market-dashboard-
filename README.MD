# 📈 全球市場戰前 vs 最新 · 自動更新儀表板

> 以色列·伊朗戰爭（2026-02-28）前後全球市場對比，GitHub Actions 每日自動更新。

-----

## 🚀 部署步驟（10 分鐘完成）

### 第一步：Fork 或 Clone 本倉庫

```bash
git clone https://github.com/YOUR_USERNAME/market-dashboard.git
cd market-dashboard
```

### 第二步：啟用 GitHub Pages

1. 進入你的 GitHub 倉庫頁面
1. 點擊 **Settings** → **Pages**
1. Source 選擇 **Deploy from a branch**
1. Branch 選 **main**，資料夾選 **/ (root)**
1. 點擊 **Save**

幾分鐘後你的儀表板將在以下地址可訪問：

```
https://YOUR_USERNAME.github.io/market-dashboard/
```

### 第三步：啟用 GitHub Actions 權限

1. 進入倉庫 **Settings** → **Actions** → **General**
1. 在 “Workflow permissions” 下選擇 **Read and write permissions**
1. 點擊 **Save**

### 第四步：手動觸發一次更新（驗證）

1. 進入倉庫 **Actions** 標籤
1. 點擊左側 **📈 Update Market Data Daily**
1. 點擊右側 **Run workflow** → **Run workflow**
1. 等待約 1–2 分鐘完成
1. 刷新你的 GitHub Pages 網址，數據應已更新！

-----

## ⏰ 自動更新時間表

|時間（SGT）   |UTC      |說明     |
|----------|---------|-------|
|09:00 週一至五|01:00 UTC|亞洲市場開盤後|
|17:00 週一至五|09:00 UTC|美股開盤前  |

-----

## 📁 文件結構

```
market-dashboard/
├── index.html                          ← 自動生成的儀表板（主頁）
├── data/
│   └── market_data.json               ← 最新市場數據（JSON）
├── scripts/
│   └── update_data.py                 ← 數據抓取 + HTML 生成腳本
├── requirements.txt                   ← Python 依賴
├── .github/
│   └── workflows/
│       └── update-market-data.yml     ← GitHub Actions 配置
└── README.md
```

-----

## 📊 數據來源

|資產類別         |數據源                        |更新方式|
|-------------|---------------------------|----|
|股票指數、個股、期貨   |Yahoo Finance (yfinance)   |自動  |
|Bitcoin BTC  |CoinGecko 免費 API           |自動  |
|戰前基準數據（02-27）|CNBC/Yahoo/TradingView 人工驗證|靜態固定|

-----

## 🛠 本地測試

```bash
# 安裝依賴
pip install -r requirements.txt

# 執行更新腳本（在 market-dashboard 根目錄）
python scripts/update_data.py

# 打開 index.html 查看結果
open index.html   # macOS
start index.html  # Windows
```

-----

## ⚠️ 注意事項

- **Yahoo Finance** 是非官方 API，偶爾可能出現限流。腳本已有錯誤處理，單個數據抓取失敗不影響整體。
- **CoinGecko** 免費層每月 10,000 次請求，每天 2 次更新完全足夠（每月僅約 60 次）。
- 週末不執行（`1-5` 僅工作日）。
- `index.html` 頁面含 `<meta http-equiv="refresh" content="1800">` ，瀏覽器每 30 分鐘自動刷新一次。

-----

## 📌 本報告不構成任何投資建議

投資涉及風險，過去表現不代表未來結果。請諮詢持牌專業財務顧問。