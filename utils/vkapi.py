import requests
import os
import random
from urllib import parse

API_BASE = 'https://api.vk.com/method/'
HEADERS = {
    'cache-control': 'no-cache',
    'x-get-processing-time': '1',
    'x-vk-android-client': 'new',
}

USER_AGENT = 'VKAndroidApp/6.3-5277 (Android 6.0; SDK 23; armeabi-v7a; ZTE Blade X3; en; 1920x1080)'


class VkAPIError(Exception):
    pass


class VkAuthError(Exception):
    pass


class VkAPI:
    def __init__(self, login="", password="", v='5.123', token=""):
        self.token = token
        self.user_id = None
        self.version = v
        self.headers = HEADERS
        self.user_agent = USER_AGENT
        self.headers["user-agent"] = self.user_agent
        self.authenticated = False
        if not os.path.exists(".device_id"):
            self.device_id = "".join(random.choices("0123456789abcdef", k=16))
            with open(".device_id", "w") as f:
                f.write(self.device_id)
        else:
            self.device_id = open(".device_id").read().splitlines()[0]
        if self.token:
            self.user_id = self.request("execute.getUserInfo")['profile']['id']
        else:
            self.try_auth(login, password)

    def try_auth(self, login, password, code=""):
        auth_url = "https://oauth.vk.com/token?client_id=2274003&client_secret=hHbZxrka2uZ6jB1inYsH" \
                   "&libverify_support=1&scope=all&v=%s&lang=en&device_id=%s&grant_type=password" \
                   "&username=%s&password=%s&2fa_supported=1"
        auth_params = (self.version, self.device_id, parse.quote_plus(login), parse.quote_plus(password))
        if code:
            auth_url += "&code=" + code
        resp = requests.post(auth_url % auth_params, headers=self.headers).json()
        if "access_token" in resp:
            self.token = resp["access_token"]
            self.user_id = resp["user_id"]
            self.authenticated = True
            print('[VK] Authentication succeed')
        else:
            if resp["error_description"] == "use app code":
                # print("[VK] 2FA with login app detected")
                app_code = input("[VK] 2FA app code: ")
                self.try_auth(login, password, app_code)
            else:
                raise VkAuthError(resp["error"])

    def request(self, method, parameters=None) -> dict:
        if parameters is None:
            parameters = dict()
        parameters['access_token'] = self.token
        parameters['v'] = self.version
        parameters['device_id'] = self.device_id
        parameters['lang'] = 'en'
        resp = requests.post(API_BASE + method, data=parameters, headers=self.headers).json()
        if 'error' in resp:
            error = resp['error']
            error_code = error['error_code']
            error_msg = error['error_msg']
            if error_code == 14:
                c_sid = error['captcha_sid']
                c_img = error['captcha_img']
                with open('captcha.jpg', 'wb') as f:
                    f.write(requests.get(c_img, headers=self.headers).content)
                c_key = input('Enter text from captcha.jpg')
                parameters['captcha_sid'] = c_sid
                parameters['captcha_key'] = c_key
                return self.request(method, parameters)
            raise VkAPIError("Error code %d: %s" % (error_code, error_msg))
        else:
            return resp['response']

    def upload(self, url, file):
        chars = "0123456789abcdef"
        boundary = "VK-FILE-UPLOAD-BOUNDARY-%s-%s-%s-%s-%s" % (
            "".join(random.choices(chars, k=8)), "".join(random.choices(chars, k=4)),
            "".join(random.choices(chars, k=4)), "".join(random.choices(chars, k=4)),
            "".join(random.choices(chars, k=12)))
        headers = {"user-agent": self.user_agent, "content-type": "multipart/form-data; boundary=" + boundary}
        filename = "".join(random.choices(chars, k=10)) + ".jpg"
        data_header = '\r\n--%s\r\nContent-Disposition: form-data; name="photo"; filename="%s"' \
                      '\r\nContent-Type: image/jpeg\r\n\r\n' % (boundary, filename)
        data_end = "\r\n--%s--\r\n" % boundary
        data = data_header.encode("ascii") + file + data_end.encode("ascii")
        resp = requests.post(url, headers=headers, data=data).json()
        server, photo, vk_hash = resp.get("server"), resp.get("photo"), resp.get("hash")
        if server and photo and vk_hash:
            return server, photo, vk_hash
        else:
            raise VkAPIError("Failed to upload")
