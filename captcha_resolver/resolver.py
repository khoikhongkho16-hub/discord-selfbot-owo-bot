import asyncio
import aiohttp
import time
import sys
import os
import json
import subprocess
from typing import Optional

from .web_solver import WebSolver
from .image_solver import ImageSolver


class CaptchaResolver:
    def __init__(self, bot):
        self.bot = bot
        self.web_solver = None
        self.image_solver = None
        self.max_retries = 5
        self.retry_count = 0
        self._is_running = False
        self._user_id = None
        self._user_token = None
        
        self._init_solvers()
        
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

    def _log(self, level: str, msg: str):
        return

    def _init_solvers(self):
        config = self.bot.config.get('captcha', {})

        if not config.get('enabled', False):
            return

        api_key = config.get('api_key')
        if api_key:
            try:
                service = config.get('service', '2captcha')
                self.web_solver = WebSolver(
                    api_key=api_key,
                    service=service,
                    bot=self.bot
                )
            except Exception as e:
                pass

        if config.get('enable_image', True):
            try:
                model_path = config.get('model_path', 'best.onnx')
                if not os.path.exists(model_path):
                    possible_paths = [
                        model_path,
                        os.path.join('captcha_resolver', 'models', 'best.onnx'),
                        os.path.join('captcha_resolver', 'best.onnx'),
                        os.path.join('models', 'best.onnx'),
                    ]
                    for p in possible_paths:
                        if os.path.exists(p):
                            model_path = p
                            break
                
                self.image_solver = ImageSolver(
                    model_path=model_path,
                    bot=self.bot
                )
            except Exception as e:
                pass

    async def _fetch_user_id(self) -> Optional[str]:
        raw_token = self.bot.config.token
        
        if not raw_token:
            return None
        
        token = raw_token.strip()
        self._user_token = token
        
        headers = {
            "Authorization": token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://discord.com/api/v9/users/@me",
                    headers=headers,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        user_id = data.get('id')
                        self._user_id = user_id
                        return user_id
                    else:
                        return None
            except Exception as e:
                return None

    async def _solve_web_captcha(self) -> bool:
        if not self.web_solver:
            return False
        
        try:
            balance = await self.web_solver.get_balance()
            
            if balance >= self.web_solver.min_balance:
                success = await self.web_solver.solve(self._user_token)
                return success
            else:
                return False
        except Exception as e:
            return False

    async def _solve_image_captcha(self, image_url: str) -> Optional[str]:
        if not self.image_solver or not self.image_solver.is_available():
            return None
        
        result = await self.image_solver.solve_from_url(image_url)
        return result

    async def _refresh_token_if_needed(self) -> bool:
        if not self._user_token:
            return False
        
        headers = {
            "Authorization": self._user_token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://discord.com/api/v9/users/@me",
                    headers=headers,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        return False
            except:
                return False

    async def solve(self) -> bool:
        if self._is_running:
            return False

        self._is_running = True
        self.retry_count = 0
        
        self._user_id = await self._fetch_user_id()
        if not self._user_id:
            self._is_running = False
            return False

        try:
            while self.retry_count < self.max_retries:
                if self.web_solver:
                    if await self._solve_web_captcha():
                        self._is_running = False
                        return True
                
                token_valid = await self._refresh_token_if_needed()
                if not token_valid:
                    self._is_running = False
                    return False
                
                self.retry_count += 1
                
                if self.retry_count < self.max_retries:
                    wait_time = 60 * self.retry_count
                    await asyncio.sleep(wait_time)

            self._is_running = False
            return False

        except Exception as e:
            self._is_running = False
            return False

    def is_available(self) -> bool:
        web_available = self.web_solver is not None
        image_available = self.image_solver is not None and self.image_solver.is_available()
        return web_available or image_available
    
    def is_running(self) -> bool:
        return self._is_running
    
    def get_user_id(self) -> Optional[str]:
        return self._user_id


def run_resolver_standalone():
    from utils.colors import color
    
    print()
    print("=" * 60)
    print(f"{color.warning}CAPTCHA RESOLVER{color.reset}")
    print("=" * 60)
    print()
    
    config_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'settings.json'),
        os.path.join(os.getcwd(), 'settings.json'),
        'settings.json'
    ]
    
    config_data = None
    used_path = None
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                used_path = path
                break
            except Exception as e:
                print(f"Failed to load {path}: {e}")
    
    if not config_data:
        print(f"{color.fail}ERROR: settings.json not found!{color.reset}")
        sys.exit(1)
    
    print(f"Config loaded from: {used_path}")
    
    class MockConfig:
        def __init__(self, data):
            self._data = data
            self.token = data.get('token', '').strip()
            self.channel = data.get('channel', '')
            self.OwOID = '408785106942164992'
            self.stopped = False
            
            if self.token:
                print("Discord token loaded (value hidden)")
                
                if self.token.startswith('ND') or self.token.startswith('MT'):
                    print(f"{color.okgreen}✅ Token format looks valid{color.reset}")
                else:
                    print(f"{color.warning}⚠️ Token might not be in correct format{color.reset}")
            else:
                print(f"{color.fail}⚠️  Token is empty!{color.reset}")
        
        def get_captcha_config(self):
            return self._data.get('captcha', {})
        
        def get(self, key, default=None):
            if key == 'captcha':
                return self._data.get('captcha', {})
            return self._data.get(key, default)
    
    class MockBot:
        def __init__(self, config):
            self.config = config
            self.start_time = time.time()
        
        def log(self, level, msg):
            from utils.colors import color
            level_colors = {
                'INFO': color.okcyan,
                'SUCCESS': color.okgreen,
                'WARN': color.warning,
                'ERROR': color.fail,
                'DETECTED': color.warning,
            }
            color_code = level_colors.get(level, color.reset)
            timestamp = time.strftime('%H:%M:%S')
            print(f"{timestamp} {color_code}[{level}]{color.reset} {msg}")
    
    mock_config = MockConfig(config_data)
    mock_bot = MockBot(mock_config)
    
    resolver = CaptchaResolver(mock_bot)
    
    if not resolver.is_available():
        print()
        print(f"{color.fail}ERROR: No solver available!{color.reset}")
        print(f"{color.okcyan}Please check:{color.reset}")
        print(f"  1. API key in settings.json (captcha.api_key)")
        print(f"  2. Service type (captcha.service: '2captcha' or 'yescaptcha')")
        print(f"  3. ONNX model file exists (captcha.model_path)")
        print()
        sys.exit(1)
    
    print(f"{color.okgreen}Solver ready!{color.reset}")
    print()
    print("=" * 60)
    print(f"{color.okcyan}Starting captcha solving...{color.reset}")
    print("=" * 60)
    print()
    
    try:
        result = asyncio.run(resolver.solve())
        
        print()
        print("=" * 60)
        
        if result:
            print(f"{color.okgreen}CAPTCHA SOLVED SUCCESSFULLY!{color.reset}")
            print(f"{color.okcyan}User ID: {resolver.get_user_id()}{color.reset}")
            print(f"{color.okcyan}Restarting bot...{color.reset}")
            print("=" * 60)
            print()
            
            main_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'main.py'
            )
            
            if os.path.exists(main_path):
                os.execv(sys.executable, [sys.executable, main_path])
            else:
                print(f"{color.fail}ERROR: main.py not found!{color.reset}")
                sys.exit(1)
        else:
            print(f"{color.fail}CAPTCHA SOLVE FAILED AFTER {resolver.max_retries} ATTEMPTS{color.reset}")
            print(f"{color.okcyan}User ID: {resolver.get_user_id()}{color.reset}")
            print(f"{color.okcyan}Bot remains stopped; resolver will exit without restarting it.{color.reset}")
            print("=" * 60)
            print()
            sys.exit(1)
        
    except KeyboardInterrupt:
        print()
        print(f"{color.warning}Resolver interrupted by user{color.reset}")
        print(f"{color.okcyan}User ID: {resolver.get_user_id()}{color.reset}")
        sys.exit(1)
    except Exception as e:
        print(f"{color.fail}Resolver error: {e}{color.reset}")
        import traceback
        traceback.print_exc()
        print()
        sys.exit(1)
