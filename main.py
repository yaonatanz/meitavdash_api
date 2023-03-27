import requests
import re
import math
import random
import time
import uvicorn
import os
from fastapi import FastAPI, APIRouter
from fastapi_utils.cbv import cbv
from fastapi_utils.inferring_router import InferringRouter
from config import config_master_password, config_username


app = FastAPI()
router = InferringRouter()

AUTH_FILE = "auth.key"

def tokenify(number):
    tokenbuf = []
    charmap = "1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ*$"
    remainder = number
    while (remainder > 0):
        tokenbuf.append(charmap[remainder & 0x3F]);
        remainder = math.floor(remainder / 64);
    return "".join(tokenbuf);

def get_password():
    if not os.path.exists(AUTH_FILE):
        return None
    with open(AUTH_FILE, "rb") as f:
        password = f.read()
    if password == b"":
        #initialize config
        return None
    return password


@cbv(router)
class Widget:
    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route("/set_login_password/{new_pass}", self.set_login_password, methods=["GET"])
        self.router.add_api_route("/stats", self.get_stats, methods=["GET"])
        self.router.add_api_route("/refresh_stats", self.refresh_stats, methods=["GET"])
        self.total_gain = 0
        self.days_value = 0
        self.total = 0


    def set_login_password(self, new_pass: str, master_password: str):
        master_password = bytes(master_password, "utf-8")
        new_pass = bytes(new_pass, "utf-8")

        status = "fail"

        if master_password != config_master_password:
            status = "Bad Authentication"
            return {"result": status}

        with open("auth.key", "wb") as f:
            f.write(new_pass)
            status = "success"

        return {"result": status}

    def get_stats(self):
        return {"total_gain": self.total_gain, "day_change": self.days_value, "total": self.total}

    def refresh_stats(self):
        password = get_password()
        if password is None:
            return {"result": "Password haven't been initialized"}

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = {
            'username': config_username,
            'password': password,
            'processLogin': 'Login',
            '_sourcePage': 'RJC5vOmZn254uKhif8j81A6HoOEZpvjZogYyWiP6v2SHULd0txXzkbj8xQDPCqsq',
            '__fp': '0RIFh7-fu8U=',
        }
        response = requests.post('https://meitav.viewtrade.com/login.action', headers=headers, data=data,
                                 allow_redirects=False)
        set_cookie = response.headers["Set-Cookie"]
        jsessionid = re.findall("JSESSIONID=(.*); Path", set_cookie)[0]

        cookies = {
            'JSESSIONID': jsessionid,
        }
        headers = {
            'Connection': 'keep-alive',
            'Content-Type': 'text/plain',
        }

        data = f'callCount=1\nc0-scriptName=__System\nc0-methodName=generateId\nc0-id=0\nbatchId=0\ninstanceId=0\npage=%2Fsecure%3Bjsessionid%3D{jsessionid}%2F\nscriptSessionId=\n'

        response = requests.post(
            f'https://meitav.viewtrade.com/secure/dwr//call/plaincall/__System.generateId.d wr;jsessionid={jsessionid}/',
            cookies=cookies,
            headers=headers,
            data=data,
        )

        dwrcookie = re.findall('handleCallback\(\"0\",\"0\",\"(.*)\"\);', response.text)[0]
        pageId = tokenify(int(time.time())) + "-" + tokenify(int(random.random() * 1E16));
        full_cookie = dwrcookie + "/" + pageId

        cookies = {
            'JSESSIONID': jsessionid,
            'DWRSESSIONID': dwrcookie,
        }

        data = f'callCount=1\nnextReverseAjaxIndex=0\nc0-scriptName=RemoteInterface\nc0-methodName=getPortfolioTotals\nc0-id=0\nbatchId=5\ninstanceId=0\npage=%2Fsecure%2F\nscriptSessionId={full_cookie}\n'

        response = requests.post(
            'https://meitav.viewtrade.com/secure/dwr//call/plaincall/RemoteInterface.getPortfolioTotals.dwr',
            cookies=cookies,
            headers=headers,
            data=data,
        )

        result = re.findall("({TotalGain.*)\);", response.text)[0]
        self.total_gain = re.findall("TotalGain:(.*?),", response.text)[0]
        self.days_value = re.findall("DaysValue:(.*?),", response.text)[0]
        self.total = re.findall("Total:(.*?),", response.text)[0]
        return {"result": "success"}



widget = Widget()
app.include_router(widget.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)