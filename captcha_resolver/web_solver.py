import asyncio
import aiohttp
import json
import time
from typing import Optional, Dict, Any

OWO_SITE_KEY = "a6a1d5ce-612d-472d-8e37-7601408fbc09"
OWO_CLIENT_ID = "408785106942164992"
OWO_AUTH_URL = (
    "https://discord.com/api/v9/oauth2/authorize"
    f"?client_id={OWO_CLIENT_ID}&response_type=code"
    "&redirect_uri=https://owobot.com/api/auth/discord/redirect"
    "&scope=identify guilds"
)

SERVICES = {
    'yescaptcha': {
        'base': 'https://api.yescaptcha.com',
        'balance_endpoint': '/getBalance',
        'create_endpoint': '/createTask',
        'result_endpoint': '/getTaskResult',
        'min_balance': 30,
        'task_type': 'HCaptchaTaskProxyless'
    },
    '2captcha': {
        'base': 'https://api.2captcha.com',
        'balance_endpoint': '/getBalance',
        'create_endpoint': '/createTask',
        'result_endpoint': '/getTaskResult',
        'min_balance': 0.01,
        'task_type': 'HCaptchaTaskProxyless'
    }
}


class WebSolver:
    def __init__(self, api_key: str, service: str = 'yescaptcha', bot=None):
        self.api_key = api_key
        self.service_name = service.lower()
        self.bot = bot
        self.balance = 0.0
        self.last_error = None

        self.service = SERVICES.get(self.service_name, SERVICES['yescaptcha'])
        self.base_url = self.service['base']
        self.min_balance = self.service.get('min_balance', 30)
        self.task_type = self.service.get('task_type', 'HCaptchaTaskProxyless')

        self.oauth_body = {
            "authorize": True,
            "permissions": "0",
            "integration_type": 0,
            "location_context": {
                "guild_id": "10000",
                "channel_id": "10000",
                "channel_type": 10000,
            },
        }

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _log(self, level: str, msg: str):
        if self.bot:
            self.bot.log(level, f"[WebSolver] {msg}")

    async def get_balance(self) -> float:
        self.last_error = None
        try:
            if self.service_name == '2captcha':
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}{self.service['balance_endpoint']}",
                        json={'clientKey': self.api_key},
                        timeout=10
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            if data.get('errorId') == 0:
                                self.balance = float(data.get('balance', 0))
                            else:
                                self.balance = 0.0
                                self.last_error = data.get('errorCode', 'UNKNOWN_API_ERROR')
                        else:
                            self.last_error = f'HTTP_{resp.status}'
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}{self.service['balance_endpoint']}",
                        json={"clientKey": self.api_key},
                        timeout=10
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('errorId') == 0:
                                self.balance = float(data.get('balance', 0))
                            else:
                                self.balance = 0.0
                                self.last_error = data.get('errorCode', 'UNKNOWN_API_ERROR')
                        else:
                            self.last_error = f'HTTP_{resp.status}'
            return self.balance
        except Exception as e:
            self.last_error = f'{type(e).__name__}: {e}'
            self._log("ERROR", f"Get balance failed: {e}")
            return 0.0

    async def _request_token(self, retries: int = 3) -> Optional[str]:
        try:
            if self.service_name == '2captcha':
                payload = {
                    'clientKey': self.api_key,
                    'task': {
                        'type': self.task_type,
                        'websiteKey': OWO_SITE_KEY,
                        'websiteURL': 'https://owobot.com/captcha',
                        'userAgent': self.headers['User-Agent'],
                    },
                }
                create_url = f"{self.base_url}{self.service['create_endpoint']}"
                async with aiohttp.ClientSession() as session:
                    async with session.post(create_url, json=payload, timeout=30) as resp:
                        if resp.status != 200:
                            self.last_error = f'HTTP_{resp.status}'
                            return None
                        data = await resp.json(content_type=None)
                        if data.get('errorId') != 0:
                            self.last_error = data.get('errorCode', 'CREATE_TASK_FAILED')
                            return None
                        task_id = data.get('taskId')
            else:
                payload = {
                    "clientKey": self.api_key,
                    "task": {
                        "type": self.task_type,
                        "websiteKey": OWO_SITE_KEY,
                        "websiteURL": "https://owobot.com",
                    },
                    "softID": 94493
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}{self.service['create_endpoint']}",
                        json=payload,
                        timeout=30
                    ) as resp:
                        if resp.status != 200:
                            return None
                        data = await resp.json()
                        if data.get('errorId') != 0:
                            return None
                        task_id = data.get('taskId')

            if not task_id:
                return None

            for attempt in range(24):
                await asyncio.sleep(5)

                if self.service_name == '2captcha':
                    payload = {'clientKey': self.api_key, 'taskId': task_id}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{self.base_url}{self.service['result_endpoint']}",
                            json=payload,
                            timeout=10
                        ) as resp:
                            if resp.status != 200:
                                continue
                            data = await resp.json(content_type=None)
                            if data.get('errorId') != 0:
                                self.last_error = data.get('errorCode', 'GET_TASK_FAILED')
                                return None
                            if data.get('status') == 'processing':
                                continue
                            if data.get('status') == 'ready':
                                solution = data.get('solution', {})
                                return (
                                    solution.get('gRecaptchaResponse')
                                    or solution.get('token')
                                )
                            self.last_error = 'UNEXPECTED_TASK_STATUS'
                            return None
                else:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{self.base_url}{self.service['result_endpoint']}",
                            json={"clientKey": self.api_key, "taskId": task_id},
                            timeout=10
                        ) as resp:
                            if resp.status != 200:
                                continue
                            data = await resp.json()
                            if data.get('errorId') != 0:
                                self.last_error = data.get('errorCode', 'GET_TASK_FAILED')
                                return None
                            if data.get('status') == 'ready':
                                return data.get('solution', {}).get('gRecaptchaResponse')

            return None

        except Exception as e:
            self.last_error = f'{type(e).__name__}: {e}'
            self._log("ERROR", f"Request token failed: {e}")
            return None

    async def solve(self, discord_token: str, retries: int = 3) -> bool:
        try:
            balance = await self.get_balance()
            if balance < self.min_balance:
                self._log("ERROR", f"Balance too low: {balance} < {self.min_balance}")
                return False

            self._log("INFO", f"Balance: {balance}, starting solve...")

            # Discord user tokens are sent raw. Retrying as Bearer would create
            # another paid captcha task even though that auth form is invalid.
            auth_methods = [
                {"name": "Raw Token", "value": discord_token},
            ]
            
            for auth_method in auth_methods:
                self._log("INFO", f"Trying auth: {auth_method['name']}...")
                
                headers = {
                    "Authorization": auth_method["value"],
                    "Content-Type": "application/json",
                    "User-Agent": self.headers["User-Agent"]
                }

                async with aiohttp.ClientSession(headers=headers) as session:
                    self._log("INFO", "OAuth flow...")
                    async with session.post(OWO_AUTH_URL, json=self.oauth_body) as resp:
                        if resp.status != 200:
                            self._log("WARN", f"OAuth failed with {auth_method['name']}: {resp.status}")
                            continue
                        
                        auth_data = await resp.json()
                        redirect_url = auth_data.get("location")

                        if redirect_url:
                            async with session.get(redirect_url) as r:
                                if r.status != 200:
                                    self._log("WARN", f"Redirect failed with {auth_method['name']}: {r.status}")
                                    continue

                        self._log("INFO", "Getting captcha page...")
                        async with session.get("https://owobot.com/captcha") as resp:
                            if resp.status != 200:
                                self._log("WARN", f"Captcha page failed with {auth_method['name']}: {resp.status}")
                                continue

                        self._log("INFO", "Checking auth...")
                        async with session.get("https://owobot.com/api/auth") as resp:
                            if resp.status != 200:
                                self._log("WARN", f"Auth check failed with {auth_method['name']}: {resp.status}")
                                continue
                            auth_data = await resp.json()
                            if not auth_data:
                                self._log("WARN", f"Empty auth data with {auth_method['name']}")
                                continue

                        self._log("INFO", "Requesting captcha token...")
                        token = await self._request_token(retries)
                        if not token:
                            self._log("WARN", f"No token received with {auth_method['name']}")
                            continue

                        self._log("INFO", "Token received, verifying...")

                        verify_headers = {
                            "Referer": "https://owobot.com/captcha",
                            "Origin": "https://owobot.com",
                            "Accept": "application/json, text/plain, */*",
                            "Content-Type": "application/json",
                        }
                        async with session.post(
                            "https://owobot.com/api/captcha/verify",
                            json={"token": token},
                            headers=verify_headers
                        ) as resp:
                            if resp.status == 200:
                                self._log("SUCCESS", f"Captcha verified with {auth_method['name']}!")
                                return True
                            else:
                                error_text = await resp.text()
                                self._log("WARN", f"Verify failed with {auth_method['name']}: {resp.status}")
                
            self._log("ERROR", "All authentication methods failed")
            return False

        except Exception as e:
            self._log("ERROR", f"Solve failed: {e}")
            return False
