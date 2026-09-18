# PDFconverter

網頁版 PDF 轉換器，支援 PDF 轉圖片、圖片與 PDF 排序合併、PDF 頁面保留與刪除。

## 本機啟動

```powershell
pip install -r requirements.txt
python app.py
```

開啟 `http://127.0.0.1:9013`。

## Docker Compose

```powershell
docker compose up -d --build
```

預設服務連接埠是 `9013`，資料會保存在 `./data/storage`。

## GHCR 部署建議

推上 GitHub 後，GitHub Actions 會建置並推送映像檔到 GHCR。
伺服器端可使用：

```bash
docker pull ghcr.io/<github-owner>/<repo-name>:latest
PDFCONVERTER_IMAGE=ghcr.io/<github-owner>/<repo-name>:latest docker compose -f docker-compose.prod.yml up -d
```

第一次使用 GHCR 私有映像檔時，需要先在伺服器執行 `docker login ghcr.io`。
