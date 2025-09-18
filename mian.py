import schedule
import time
import os
import shutil
import crawler
usrData= './usr_data'


def delete_uerData():
    if not os.path.exists(usrData):
        pass
    elif os.path.isfile(usrData):
        try:
            shutil.rmtree(usrData)
        except OSError as e:
            print(f'{usrData} 出現錯誤: {e}')


def main_jobs():
    crawler.main()

schedule.every().monday.at("04:30").do(delete_uerData)
schedule.every().hour.at(":05").do(main_jobs)

while True:
    schedule.run_pending()
    time.sleep(3)