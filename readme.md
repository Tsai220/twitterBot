自動推特轉推機器人
===
##### 基於Playwright套件的爬蟲。  


---
## 事前準備  
Google Cloud (必須):   
- 建立專案並取得編號和ID  
- 設定Identity and Access Management (IAM) 並把推特帳密和用戶名輸入進去  
 
  
個人推特帳號 (非選):  
- 帳號  
- 密碼  
- 用戶名  
  
  
> #### 執行指令
> ##### pip install -r requirements.txt
>
> ##### playwright install chromium  

***
## 設定
> #### set.ini
> 
> ##### userReject=None    `若有人不想被轉推可以設定`
> ##### keywords=ことぴく,はのぴく,ことメモ,見どころはのぴ  `hashtag關鍵字`
> ##### days=2   `幾天前到現在的新推文`
> ##### PROJECT_ID=810413721043  `GCP 專案編號`
> ##### secret_ID=twitter_hakobot_acc  `GCP 專案ID`
> ##### X_acc=None  `twitter 帳號`
> ##### X_pwd=None  `twitter 密碼`
> ##### X_usrname=None `twitter 用戶名 `
> 

***
## 紀錄

##### 在posted.json會記錄轉推過的推文

```程式類型=json
[
  {
    "auther": "XXX_user", 
    "postID": "0000000000000",
    "has_image": true
  }
]
```
auther `被轉推的用戶名`  
postID `該推文的ID`  
has_image `是否含有影像`  
***
## 其他配置(重要)
把一開始在GCP Identity and Access Management (IAM) 設定好的密鑰下載下來取名為`service-account.json`

