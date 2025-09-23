import random
import time
import asyncio  # 引入 asyncio 以執行非同步主程式
from datetime import datetime, timedelta
from configparser import ConfigParser
# 將 sync_api 改為 async_api 以支援 await
from playwright.async_api import async_playwright, expect
import json
from google.cloud import secretmanager
from google.oauth2 import service_account
import psutil
from pytest_playwright.pytest_playwright import browser


async def randomTime():
    timer =  round(random.uniform(2.0, 4.0), 2)

    await  asyncio.sleep(timer)

async def cleanChromium():
    ok = False
    for proc in psutil.process_iter():
        try:
            name = proc.name().lower()
            if "chrome" in name or "chromium" in name:
                print(f"Kill old process: PID={proc.pid}")
                proc.kill()
            ok = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            ok = False
            return
    return ok


async def is_filled(value):
    return value is not None and value.strip() != ""


async def get_secret(YOUR_PROJECT_ID, secret_id):
    try:

        client = secretmanager.SecretManagerServiceClient()
    except:
        credentials = service_account.Credentials.from_service_account_file("service-account.json")
        client = secretmanager.SecretManagerServiceClient(credentials=credentials)

    name = f"projects/{YOUR_PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


async def scroll(page, wait_time: int = 1000, max_scroll: int = 30):
    all_hrefs = []
    await page.wait_for_load_state()
    for a in range(max_scroll):
        # 滾動到
        keep = True

        while keep:
            articles = page.locator("article")
            current_article_count = await articles.count()
            for i in range(current_article_count):

                anchors = articles.nth(i).locator("a")
                article_element = articles.nth(i)
                count = await anchors.count()
                for j in range(count):
                    anchor = anchors.nth(j)
                    aria_label = await anchor.get_attribute("aria-label")
                    if aria_label and "查看貼文分析" in aria_label:
                        href = await anchor.get_attribute("href")
                        if href:
                            splitHref = href.split("/")
                            auther = splitHref[1]
                            postID = splitHref[3]
                            has_image = await article_element.locator("[data-testid='tweetPhoto']").count() > 0
                            has_videoLink = await article_element.locator("[aria-label='播放']").count() > 0
                            has_gif = await article_element.locator("[data-testid='videoComponent']").count() > 0
                            has_imgOrVideo = has_image or has_videoLink or has_gif
                            data = {
                                "auther": auther,
                                "postID": postID,
                                "has_image": has_imgOrVideo
                            }
                            all_hrefs.append(data)

                await page.wait_for_timeout(1000)
                await page.evaluate("window.scrollBy(0, 400)")  # 極端情況下每400px會畫面更新
                await page.wait_for_timeout(wait_time)  #

                is_bottom = await page.evaluate("""
                           () => {

                               const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
                               return Math.abs(scrollTop + clientHeight - scrollHeight) < 1; 
                           }
                       """)
                keep = not is_bottom

        if not keep:
            break

    seen = set()
    unique_data = []
    for d in all_hrefs:
        t = tuple(d.items())
        if t not in seen:
            seen.add(t)
            unique_data.append(d)

    return unique_data


async def retweet_pre(userReject, data, page):
    unique_list = []
    retweet_pre_data = []
    seen = set()

    # 先把讀取過來的資料先去除重複的ID -> 過濾掉拒絕的 -> 過濾沒照片

    # 重複的ID
    with open("posted.json", "r") as r:
        a = json.load(r)
        merge = a + data

        for i in merge:
            hashed_dict = tuple(sorted(i.items()))

            if hashed_dict not in seen:
                unique_list.append(i)
                seen.add(hashed_dict)

    # 拒絕的
    if userReject != "None":  # <-有人拒絕的意思
        delUsr = set(userReject)
        unique_list = [d for d in unique_list if d.get('auther') not in delUsr]

    # 過濾沒照片
    for item in unique_list:
        if not item['has_image']:
            targetID = item['postID']
            unique_list = [item for item in unique_list if item["postID"] != targetID]

    with open("posted.json", "r") as r:
        old_data = json.load(r)

    old_ids = {d["postID"] for d in old_data}

    # 只取新資料裡的
    new_data = [d for d in data if d["postID"] not in old_ids]

    # 過濾拒絕的
    if userReject != "None":
        delUsr = set(userReject)
        new_data = [d for d in new_data if d.get('auther') not in delUsr]

    # 過濾沒照片
    retweet_pre_data = [d for d in new_data if d.get("has_image", False)]

    return retweet_pre_data, unique_list


async def go_retweet(page, NewData, unique_list):
    for post in NewData:
        print(f"轉跳{post['auther']},{post['postID']}")
        await page.goto(f"https://x.com/{post['auther']}/status/{post['postID']}", timeout=60000)
        await page.wait_for_load_state()

        # 取得第一篇文章
        first_article = page.locator("article").first

        retweet_button = first_article.locator("button[data-testid*='retweet']").first

        await retweet_button.click()
        await randomTime()
        await page.click(
            "#layers > div.css-175oi2r.r-zchlnj.r-1d2f490.r-u8s1d.r-ipm5af.r-1p0dtai.r-105ug2t > div > div > div > div.css-175oi2r.r-1ny4l3l > div > div.css-175oi2r.r-j2cz3j.r-14lw9ot.r-1q9bdsx.r-1upvrn0.r-1udh08x.r-u8s1d > div > div > div > div")

    with open("posted.json", "w", encoding="utf-8") as w:
        json.dump(unique_list, w, indent=2, ensure_ascii=False)


async def main():
    clean = await cleanChromium()
    if clean:

        config = ConfigParser()
        config.read('set.ini', encoding='utf-8')
        days = int(config['SPIDER_SET']['days'])
        today = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')
        keywords = config['SPIDER_SET']['keywords'].split(',')
        userReject = config['SPIDER_SET']['userReject'].split(',')
        x_acc = str(config['SPIDER_SET']['X_acc'])
        x_pwd = str(config['SPIDER_SET']['X_pwd'])
        x_usrname = str(config['SPIDER_SET']['X_usrname'])
        gcp_SM_PID = str(config['SPIDER_SET']['PROJECT_ID'])
        gcp_SM_SID = str(config['SPIDER_SET']['secret_ID'])
        # 優先級 gcp > local acc
        has_manual_creds = await is_filled(x_acc) and await is_filled(x_pwd) and await is_filled(x_usrname)
        has_gcp_creds = await is_filled(gcp_SM_PID) and await is_filled(gcp_SM_SID)

        acc, pw, username = None, None, None
        if has_manual_creds and not has_gcp_creds:
            acc, pw, username = x_acc, x_pwd, x_usrname
        elif not has_manual_creds and has_gcp_creds:
            pwd = await get_secret(gcp_SM_PID, gcp_SM_SID)
            acc, pw, username = pwd.splitlines()
        elif has_manual_creds and has_gcp_creds:
            pwd = await get_secret(gcp_SM_PID, gcp_SM_SID)
            acc, pw, username = pwd.splitlines()
        else:
            print("set.ini 設定錯誤，請設定好再重新啟動")
            return


        async with async_playwright() as p:
            try:
                # await 瀏覽器啟動
                context = await p.chromium.launch_persistent_context(
                    slow_mo=100,
                    user_data_dir="./usr_data",
                    headless=True,
                    locale="zh-TW",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/116.0.0.0 Safari/537.36"
                    ),
                    extra_http_headers={
                        "Accept-Language": "zh-TW",
                        "Referer": "https://x.com/",
                        "Origin": "https://x.com"
                    },
                    args=[
                        "--lang=zh-TW",
                        "--disable-blink-features=AutomationControlled",  # 移除 Playwright 標記
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-extensions",
                        "--disable-infobars",
                        "--start-maximized"
                    ]
                )

                page = await context.new_page()

                # 至指定網址
                await page.goto("https://x.com")
                await page.wait_for_load_state()
            except Exception as a:
                print(f'網頁啟動程序錯誤 {a}')
            else:
                print(f'網頁啟動完成')
                try:
                    cookies = await context.cookies()
                    is_logged_in = any(cookie['name'] == 'auth_token' for cookie in cookies)
                    if is_logged_in:
                        print("已登入")
                    elif not is_logged_in:
                        print("未登入，進行登入")
                        await page.wait_for_load_state()  #

                        await page.locator("a[data-testid='loginButton']").click()

                        await page.wait_for_load_state()

                        await page.locator("input[autocomplete='username']").type(acc, delay=400)

                        await page.click(
                            "#layers > div:nth-child(2) > div > div > div > div > div > div.css-175oi2r.r-1ny4l3l.r-18u37iz.r-1pi2tsx.r-1777fci.r-1xcajam.r-ipm5af.r-g6jmlv.r-1awozwy > div.css-175oi2r.r-1wbh5a2.r-htvplk.r-1udh08x.r-1867qdf.r-kwpbio.r-rsyp9y.r-1pjcn9w.r-1279nm1 > div > div > div.css-175oi2r.r-1ny4l3l.r-6koalj.r-16y2uox.r-14lw9ot.r-1wbh5a2 > div.css-175oi2r.r-16y2uox.r-1wbh5a2.r-f8sm7e.r-13qz1uu.r-1ye8kvj > div > div > div > button:nth-child(6)")

                        await page.wait_for_load_state()

                        try:
                            await expect(page.locator("input[name='password']")).to_be_visible(timeout=2500)
                        except:
                            await page.locator("input[name='text']").type(username, delay=300)

                            await page.locator("button[data-testid='ocfEnterTextNextButton']").click()

                            await page.locator("input[name='password']").type(pw, delay=250)
                            await page.locator("button[data-testid='LoginForm_Login_Button']").click()

                        else:
                            await page.locator("input[name='password']").type(pw, delay=350)

                            await page.click("button[data-testid='LoginForm_Login_Button']")
                            await page.wait_for_load_state()
                except Exception as e:
                    print("登入流程失敗:", e)
                    return
                else:

                    await page.goto("https://x.com/explore")
                    await page.wait_for_load_state()

                    # 收尋
                    for keyword in keywords:
                        print(f"---{keyword} 轉推開始---")
                        try:
                            await randomTime()
                            searchBox = page.locator("input[data-testid='SearchBox_Search_Input']")
                            await searchBox.fill("")
                            await searchBox.type(f"#{keyword} since:{today}", delay=330)

                            await page.keyboard.press("Enter")
                            await page.wait_for_load_state()
                            await page.get_by_role("tab", name="最新").click()
                            await page.wait_for_load_state()
                            await randomTime()
                            count = await page.locator("div[data-testid='empty_state_header_text']").count()

                            if count == 0:
                                await page.mouse.wheel(0, 250)
                                await page.wait_for_timeout(500)
                                await page.mouse.wheel(0, -250)


                                data = await scroll(page)

                                retweet_pre_data, unique_list = await retweet_pre(userReject, data, page)
                                print("已過濾拒絕名單")
                                await go_retweet(page, retweet_pre_data, unique_list)
                                print(f"---{keyword} 轉推結束---")
                                await randomTime()
                            elif count != 0:
                                print(f"---{keyword} 無資料跳過---")
                                await randomTime()
                        except Exception as e:
                            print(f' 關鍵字迴圈出現錯誤 ,{e}')
                            print(f"---出現錯誤{keyword} 轉推強制跳過---")
                            await randomTime()
                    print("此輪結束")
            await context.close()
    elif not clean:
        pass


