import time
import asyncio
import gc
import threading
import discum
from utils.helpers import UI
from utils.colors import color
from utils.constants import BotConstants

class OwOBot:
    def __init__(self, config, start_time=None):
        self.modules = []
        self.config = config
        self._message_cache = {}
        self._cache_timeout = 10
        self.start_time = start_time if start_time else time.time()
        self.executor = None
        self.scheduler = None
        self.events = None
        self._ready_event = asyncio.Event()
        # Shared kill switch checked by the gateway and every command path.
        self.stop_event = threading.Event()

        self.discord_bot = discum.Client(
            token=config.token,
            log=False,
            user_agent=[
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36/PAsMWa7l-11',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.135 YaBrowser/20.8.3.115 Yowser/2.5 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:60.7.2) Gecko/20100101 / Firefox/60.7.2'
            ]
        )

        self.ui = UI()
        self.running = False
        self.hunt_cycles = 0
        self.total_commands = config.totalcmd
        self.total_texts = config.totaltext

        self.gems = None
        self.weapons = None

        self.last_command_id = None
        self.last_command_time = 0
        self.command_history = []

        self.captcha_resolver = None
        self._init_captcha_resolver()
        
        self._last_yield_time = 0
        self._yield_interval = 0.1
        
        self._gc_counter = 0
        self._gc_interval = 30
        self._last_gc_time = time.time()
        
        self._message_cache_limit = 30
        
        self._user_info = None
        self._is_ready = False

    def log(self, level: str, msg: str):
        return

    def register_module(self, module):
        self.modules.append(module)
        if hasattr(module, 'setup'):
            try:
                module.setup(self)
            except Exception as e:
                pass

    def set_gems_module(self, gems_module):
        self.gems = gems_module

    def set_weapons_module(self, weapons_module):
        self.weapons = weapons_module

    def _init_captcha_resolver(self):
        try:
            captcha_config = self.config.get_captcha_config()
            if not captcha_config.get('enabled', False):
                return

            from captcha_resolver.resolver import CaptchaResolver
            resolver = CaptchaResolver(self)
            if resolver.is_available():
                self.captcha_resolver = resolver
        except Exception as exc:
            self.log("ERROR", f"Captcha resolver initialization failed: {exc}")

    def _yield_cpu(self):
        now = time.time()
        if now - self._last_yield_time >= self._yield_interval:
            self._last_yield_time = now
            time.sleep(0)

    def wait_for_ready(self, timeout=30):
        start = time.time()
        while not self._is_ready and time.time() - start < timeout:
            time.sleep(0.5)
        return self._is_ready

    def start(self):
        self.stop_event.clear()
        self.running = True
        
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            self.discord_bot.gateway.run(auto_reconnect=True)
        except Exception as e:
            pass

    def stop(self):
        self.stop_event.set()
        self.running = False
        self.config.stopped = True

        if self.scheduler:
            try:
                self.scheduler.stop()
            except:
                pass

        try:
            self.discord_bot.gateway.close()
        except:
            pass

        print(f"\n{self.at()} Bot stopped!")
        print(f"{self.at()} Total Commands: {self.total_commands}")
        print(f"{self.at()} Total Texts: {self.total_texts}")
        print(f"{self.at()} Status: IDLE")

    def resume(self):
        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            self.stop_event.clear()
            self.config.stopped = False
            self.running = True

            try:
                if not self.discord_bot.gateway._ws:
                    self.discord_bot.gateway.run(auto_reconnect=True)
            except Exception as e:
                pass

            if self.scheduler and not self.scheduler.running:
                self.scheduler.start()

        except Exception as e:
            pass

    def has_captcha_resolver(self) -> bool:
        return (
            self.captcha_resolver is not None
            and self.captcha_resolver.is_available()
        )

    def is_captcha_mode(self) -> bool:
        return (self.events and self.events._is_solving)

    def should_stop(self) -> bool:
        return self.stop_event.is_set() or self.config.stopped

    def emergency_pause(self, wait_for_scheduler=False):
        """Atomically prevent any new outgoing action before doing cleanup."""
        self.stop_event.set()
        self.config.stopped = True
        self.running = False

        if self.scheduler:
            self.scheduler.stop()
            if wait_for_scheduler:
                self.scheduler.wait_stopped(timeout=5.0)

    def at(self):
        elapsed = int(time.time() - self.start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f'\033[0;43m{h:02}:{m:02}:{s:02}\033[0;21m'

    def getMessages(self, num=1, channel=None):
        if channel is None:
            channel = self.config.channel

        messageObject = None
        retries = 0
        while not messageObject and retries <= 10:
            try:
                messageObject = self.discord_bot.getMessages(channel, num=num)
                messageObject = messageObject.json()
                if not isinstance(messageObject, list):
                    messageObject = None
                else:
                    break
                retries += 1
                time.sleep(2)
                self._yield_cpu()
            except Exception as e:
                retries += 1
                time.sleep(2)
                self._yield_cpu()
        if not messageObject:
            return []
        return messageObject
    
    def get_user_info(self):
        try:
            user = getattr(self.discord_bot.gateway.session, "user", {})
            if not isinstance(user, dict):
                user = {}
            return {
                'username': user.get('username', 'Unknown'),
                'discriminator': user.get('discriminator', '0000'),
                'id': user.get('id', 'Unknown')
            }
        except:
            return None
