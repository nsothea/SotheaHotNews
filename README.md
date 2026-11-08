# Sothea Hot News & Alert System
## (ប្រព័ន្ធតាមដាន និងជូនដំណឹងព័ត៌មានទាន់ហេតុការណ៍អន្តរជាតិ)

ប្រព័ន្ធនេះផ្តល់នូវការតាមដាន និងជូនដំណឹងរាល់ព័ត៌មានក្តៅគគុក (Hot/Breaking War News) ទាក់ទងនឹងសង្គ្រាមធំៗលើពិភពលោក (អ៊ុយក្រែន-រុស្ស៊ី, មជ្ឈិមបូព៌ា, ស៊ូដង់, មីយ៉ាន់ម៉ា...) ដោយស្វ័យប្រវត្តិតាមរយៈ **In-Chat AI Scheduler**, **Telegram Bot**, **Discord Webhook** និង **Windows Sound Alert**។

---

## ⚡ វិធីសាស្រ្តទទួលដំណឹង (Alert Channels)

### 🔔 លក្ខណៈពិសេសនៃ Windows Desktop Notification
- **ភាសាខ្មែរ ១០០% (Khmer Translation):** បកប្រែចំណងជើង និងព័ត៌មានក្តៅគគុកទៅជាភាសាខ្មែរដោយស្វ័យប្រវត្តិ។
- **ប៊ូតុងចុចចូលមើលប្រភពដើម (Clickable Source Link):** រាល់ពេលលោត Toast Notification លើអេក្រង់ អ្នកអាចចុចលើផ្ទាំងដំណឹងផ្ទាល់ ឬចុចប៊ូតុង **`🔗 អានលម្អិត (More Detail)`** ដើម្បីបើកទៅកាន់គេហទំព័រព័ត៌មានដើម (Reuters, BBC, Al Jazeera...) ក្នុង Browser របស់អ្នកភ្លាមៗ!
- **សំឡេងកណ្តឹងរោទិ៍ (Audio Beep):** បន្លឺសំឡេងប្រាប់ភ្លាមៗនៅពេលមានដំណឹងបន្ទាន់។

### ១. ដំណឹងក្នុង Chat នេះផ្ទាល់ (In-Chat AI Scheduler)
- ប្រព័ន្ធត្រូវបានកំណត់ឱ្យពិនិត្យមើលរៀងរាល់ **១៥ នាទីម្តង** ដោយស្វ័យប្រវត្តិតាមរយៈ Scheduler Daemon (`schedule`)។
- នៅពេលមានព័ត៌មានសង្គ្រាមផ្ទុះឡើងថ្មី ប្រព័ន្ធនឹងសង្ខេបបកប្រែជាភាសាខ្មែរ រួមទាំងភ្ជាប់ប្រភព Link មកក្នុង chat នេះភ្លាមៗ។

---

### ២. ដំណឹងទៅកាន់ Telegram ឬ Discord (Phone / Desktop Notification)

ដើម្បីឱ្យប្រព័ន្ធផ្ញើសារទាន់ហេតុការណ៍ចូលទូរស័ព្ទរបស់អ្នកតាមរយៈ Telegram ឬ Discord៖

1. បង្កើតឯកសារ `.env` (ចម្លងចេញពី [`.env.example`](file:///d:/AI_Project/News/.env.example))៖
   ```bash
   cp .env.example .env
   ```
2. បើកកែប្រែឯកសារ `.env` រួចបំពេញព័ត៌មាន៖
   - **Telegram:**
     - ឆាតទៅកាន់ `@BotFather` ដើម្បីបង្កើត Bot និងយក `TELEGRAM_BOT_TOKEN`
     - ឆាតទៅកាន់ `@userinfobot` ដើម្បីយកលេខ `TELEGRAM_CHAT_ID`
   - **Discord (បើចង់បាន):**
     - បង្កើត Webhook ក្នុង Discord Server (`Channel Settings` -> `Integrations` -> `Webhooks`) រួចចម្លងដាក់ក្នុង `DISCORD_WEBHOOK_URL`

3. ដំណើរការកម្មវិធីតាមដាន៖
   ```powershell
   .\.venv\Scripts\python alert_watcher.py
   ```
   *(ដំណើរការពិនិត្យរៀងរាល់ ១៥ នាទីម្តងជាលំនាំដើម)*

---

### ៣. តាមដានព័ត៌មានសង្ខេបភ្លាមៗ (On-Demand Fetch)
ដើម្បីទាញយកព័ត៌មានសង្គ្រាមថ្មីៗទាំងអស់ភ្លាមៗ និងរក្សាទុកជារបាយការណ៍៖
```powershell
.\.venv\Scripts\python war_news_tracker.py
```

---

## 📂 រចនាសម្ព័ន្ធឯកសារ (Project Structure)
- [`alert_watcher.py`](file:///d:/AI_Project/News/alert_watcher.py) : ប្រព័ន្ធតាមដាន និងបាញ់ដំណឹង (Alert Daemon: Telegram, Discord, Windows Beep)
- [`war_news_tracker.py`](file:///d:/AI_Project/News/war_news_tracker.py) : កម្មវិធីទាញយក និងបកប្រែព័ត៌មានលម្អិត
- [`.env.example`](file:///d:/AI_Project/News/.env.example) : គំរូកំណត់រចនាសម្ព័ន្ធ Telegram/Discord/Gemini Token
- [`seen_articles.json`](file:///d:/AI_Project/News/seen_articles.json) : កន្លែងកត់ត្រាព័ត៌មានដែលបានជូនដំណឹងរួច (ដើម្បីកុំឱ្យផ្ញើជាន់គ្នា)
- [`alerts/`](file:///d:/AI_Project/News/alerts/) : ថតកត់ត្រាប្រវត្តិនៃរាល់ដំណឹងទាន់ហេតុការណ៍
- [`reports/`](file:///d:/AI_Project/News/reports/) : ថតរក្សាទុករបាយការណ៍សង្ខេបប្រចាំថ្ងៃ
