import asyncio
import configparser
import sys
from configparser import ConfigParser
import time
import datetime
import os
import shutil
import crawler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import queue
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import concurrent.futures

usrData = './usr_data'
filename = 'schedule.ini'
task_queue = queue.Queue()

scheduler = BackgroundScheduler()

def delete_uerData():
    if os.path.exists(usrData) and os.path.isdir(usrData):
        try:
            shutil.rmtree(usrData)
        except OSError as e:
            print(f'{usrData} 出現錯誤: {e}')

def crawlerMain(timeoutAdaptive):
    def run():
        asyncio.run(crawler.main())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            future.result(timeout=timeoutAdaptive)
        except concurrent.futures.TimeoutError:
            print("整體任務超時 強制結束")

def default_job():
    default_config = configparser.ConfigParser()
    default_config.read(filename)
    start_min= default_config['SCHEDULE_SET']['frequency_start']
    minute2= default_config['SCHEDULE_SET']['frequency_every_min']
    timeoutAdaptive= ((int(start_min + minute2)) / 2) * 60
    scheduler.remove_all_jobs()
    scheduler.add_job(delete_uerData, CronTrigger(day_of_week='mon', hour=4, minute=45), id='delete_usrData', replace_existing=True ,max_instances=1)
    scheduler.add_job(crawlerMain, CronTrigger(minute=f'{start_min}/{minute2}'), id='crawler_scheduler', replace_existing=True,max_instances=1,args=(timeoutAdaptive,))
    print("default job set done..!")

def change_job(jobData):
    scheduler.remove_all_jobs()
    try:
        start_min= int(jobData['frequency_start'])
        minute2 = int(jobData['frequency_every_min'])
        timeoutAdaptive = int(jobData['timeoutAdaptive'])
        scheduler.add_job(crawlerMain, CronTrigger(minute=f'{start_min}/{minute2}'), id='crawler_scheduler', replace_existing=True,max_instances=1,args=(timeoutAdaptive,))
        scheduler.add_job(delete_uerData, CronTrigger(day_of_week='mon', hour=4, minute=45), id='delete_usrData', replace_existing=True,max_instances=1)
        print(f"已更新，每整點{start_min}起，每隔{minute2}分執行爬蟲")
    except ValueError:
        print("非數字 任務未建立")
    return

def job_allocator():
    default_job()
    scheduler.start()

    while True:
        try:
            task = task_queue.get_nowait()
            if task['new_job']:
                print("Get new job call")
                change_job(task)
        except queue.Empty:
            pass
        time.sleep(1)

class SetFileWatcher(FileSystemEventHandler):
    def __init__(self, filename):
        self.filename = filename
        self.config = ConfigParser()
        self.osName = sys.platform

    def job_done(self):
        self.config.read(self.filename, encoding='utf-8')
        print("schedule.ini had change")
        frequency_start=self.config['SCHEDULE_SET']['frequency_start']
        frequency_every_min = self.config['SCHEDULE_SET']['frequency_every_min']
        job = {
            'new_job': True,
            'frequency_every_min': frequency_every_min,
            'frequency_start' : frequency_start,
            'timeoutAdaptive' : ((int(frequency_start+frequency_every_min))/2)*60
        }
        task_queue.put(job)

    def on_modified(self, event):
        if self.osName == 'win32' and event.src_path.endswith(self.filename):
            self.job_done()

    def on_moved(self, event):
        if self.osName == 'linux' and not event.is_directory and os.path.basename(event.dest_path) == self.filename:
            self.job_done()

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

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("程式中止!")
        scheduler.shutdown()

if __name__ == "__main__":
    main()
