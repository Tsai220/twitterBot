from configparser import ConfigParser
import schedule
import time
import os
import shutil
import crawler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import queue
import threading
usrData= './usr_data'
filename='schedule.ini'

task_queue = queue.Queue()

def delete_uerData():
    if not os.path.exists(usrData):
        pass
    elif os.path.isfile(usrData):
        try:
            shutil.rmtree(usrData)
        except OSError as e:
            print(f'{usrData} 出現錯誤: {e}')


def crawlerMain():
    crawler.main()

def default_job():
    schedule.clear()
    schedule.every().monday.at("04:45").do(delete_uerData)
    schedule.every().hour.at(":05").do(crawlerMain)
    print("default job set done..! ")
    for job in schedule.jobs:
        print(job)

def change_job(jobData):
    schedule.clear()
    if jobData['frequency_every_min'].isdigit():
        min=int(jobData['frequency_every_min'])
        schedule.every(min).minutes.do(crawlerMain)
    else:
        print("偵測非數字 任務未建立")
    return


def job_allocator():
    default_job()

    while True:

        try:
            task = task_queue.get_nowait()
            if task['new_job']:
                print("Get new job call")
                jobData=task
                ch= change_job(jobData)
                schedule.every().monday.at("04:45").do(delete_uerData)
                for job in schedule.jobs:
                    print(job)

                # 清除任務、重建任務
        except queue.Empty:
            pass

        schedule.run_pending()
        time.sleep(1)

class SetFileWatcher(FileSystemEventHandler):
    def __init__(self,filename):
        self.filename = filename
        self.config = ConfigParser()


    def on_modified(self,event):
        if event.src_path.endswith(self.filename):
            job = {'new_job':False}
            self.config.read(self.filename, encoding='utf-8')
            #--------
            frequency_every_min=self.config['SCHEDULE_SET']['frequency_every_min']
            job= {
                'new_job':True,
                'frequency_every_min':frequency_every_min
            }
            # 這邊可以檢視ini檔是否改變後再發出信號
            task_queue.put(job)





def start_watchdog(filename):
    event = SetFileWatcher(filename)
    observer = Observer()
    observer.schedule(event, '.', recursive=True)
    observer.start()

    print(f"開始監控 {filename} ... (按Ctrl+C停止)")
    def watchdog_loop():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    threading.Thread(target=watchdog_loop, daemon=True).start()


def main():
    start_watchdog(filename)
    time.sleep(1)
    threading.Thread(target=job_allocator, daemon=True).start()

    #主線程
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("程式中止!")

if __name__ == "__main__":
    main()




