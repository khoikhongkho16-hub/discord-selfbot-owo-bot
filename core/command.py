import time
import random
import threading
from threading import Lock
import gc
from utils.helpers import UI
from utils.colors import color
from utils.constants import BotConstants

class CommandExecutor:
    def __init__(self, bot):
        self.bot = bot
        self.ui = UI()
        self.cmd_lock = Lock()
        self.last_global_cmd_time = 0
        self.GLOBAL_DELAY = 3.0
        self.CMD_COOLDOWN = {
            'hunt': 3,
            'battle': 3,
            'pray': 300,
            'daily': 3600,
            'sell': 600,
        }
        self.last_cmd_time = {}
        self.pending_commands = set()
        self.command_timestamps = {}
        
        self._last_yield_time = 0
        self._yield_interval = 0.1
        
        self._response_cache = {}
        self._cache_ttl = 30
        self._last_cache_clean = time.time()

    def _clean_cache(self):
        now = time.time()
        if now - self._last_cache_clean > 60:
            expired = [k for k, v in self._response_cache.items() 
                      if now - v.get('time', 0) > self._cache_ttl]
            for k in expired:
                self._response_cache.pop(k, None)
            self._last_cache_clean = now
            
            if len(self._response_cache) > 50:
                self._response_cache.clear()
                gc.collect()

    def _yield_cpu(self):
        now = time.time()
        if now - self._last_yield_time >= self._yield_interval:
            self._last_yield_time = now
            time.sleep(0)

    def _stopped(self) -> bool:
        return self.bot.should_stop()

    def _interruptible_sleep(self, seconds: float, step: float = 0.1) -> bool:
        """Return False immediately when the emergency stop is raised."""
        deadline = time.monotonic() + seconds
        while not self._stopped():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            self.bot.stop_event.wait(min(step, remaining))
        return False

    def send_command(self, cmd: str, extra_delay: bool = True) -> bool:
        if self._stopped():
            return False

        with self.cmd_lock:
            now = time.time()
            cmd_key = f"{cmd}_{int(now // 30)}"

            self._clean_cache()

            if cmd_key in self._response_cache:
                return False

            if self._stopped():
                return False

            if cmd_key in self.pending_commands:
                return False

            if now - self.last_global_cmd_time < self.GLOBAL_DELAY:
                return False

            if cmd in self.last_cmd_time:
                elapsed = now - self.last_cmd_time[cmd]
                if elapsed < self.CMD_COOLDOWN.get(cmd, 10):
                    return False

            try:
                if extra_delay:
                    delay = random.uniform(5.0, 10.0)
                    self.bot.discord_bot.typingAction(self.bot.config.channel)
                    
                    if not self._interruptible_sleep(delay):
                        return False

                full_cmd = f"owo {cmd}"
                if self._stopped():
                    return False
                response = self.bot.discord_bot.sendMessage(
                    self.bot.config.channel,
                    full_cmd
                )

                if response and response.status_code == 429:
                    self.ui.slowPrinting(
                        f"{self.bot.at()}{color.warning} [WARN]{color.reset} "
                        f"Rate limit on '{full_cmd}', waiting 120s"
                    )
                    remaining = 120
                    while remaining > 0 and not self._stopped():
                        chunk = min(remaining, 5)
                        if not self._interruptible_sleep(chunk):
                            break
                        self._yield_cpu()
                        remaining -= chunk
                    return False

                self.last_cmd_time[cmd] = now
                self.last_global_cmd_time = now
                self.pending_commands.add(cmd_key)
                threading.Timer(15, lambda: self.pending_commands.discard(cmd_key)).start()

                if response and response.status_code == 200:
                    self._response_cache[cmd_key] = {'time': now, 'status': 'sent'}
                    if len(self._response_cache) > 50:
                        self._response_cache.clear()

                self.ui.slowPrinting(
                    f"{self.bot.at()}{color.okgreen} [SENT]{color.reset} {full_cmd}"
                )
                self.bot.total_commands += 1
                self._yield_cpu()
                
                return True

            except Exception as e:
                time.sleep(8)
                self._yield_cpu()
                return False

    def send_hunt_battle(self) -> bool:
        if self.bot.config.stopped:
            return False

        try:
            self.bot.discord_bot.typingAction(self.bot.config.channel)
            
            if self.bot.hunt_cycles == 0:
                time.sleep(random.randint(2, 5))
            else:
                time.sleep(random.randint(10, 20))

            if self.bot.config.stopped:
                return False

            if not self.bot.config.stopped:
                self.send_command("hunt")

            if self.bot.hunt_cycles == 0:
                time.sleep(random.randint(2, 4))
            else:
                time.sleep(random.randint(8, 15))

            if self.bot.config.stopped:
                return False

            self.send_command("battle")

            self.bot.hunt_cycles += 1
            return True

        except Exception as e:
            self.ui.slowPrinting(
                f"{self.bot.at()}{color.warning} [WARN]{color.reset} "
                f"Hunt/Battle error: {str(e)[:50]}"
            )
            time.sleep(8)
            return False

    def send_pray(self) -> bool:
        if self.bot.config.pm != "YES" or self.bot.config.stopped:
            return False

        try:
            self.bot.discord_bot.typingAction(self.bot.config.channel)
            if not self._interruptible_sleep(random.randint(8, 20)):
                return False

            if self._stopped():
                return False
            response = self.bot.discord_bot.sendMessage(
                self.bot.config.channel,
                "owo pray"
            )

            if response and response.status_code == 429:
                self.ui.slowPrinting(
                    f"{self.bot.at()}{color.fail}[ERROR]{color.reset} "
                    "Rate limit on pray, waiting 120s"
                )
                time.sleep(120)
                return False

            self.ui.slowPrinting(
                f"{self.bot.at()}{color.okgreen} [SENT]{color.reset} owo pray"
            )
            self.bot.total_commands += 1
            return True

        except Exception as e:
            self.ui.slowPrinting(
                f"{self.bot.at()}{color.warning} [WARN]{color.reset} "
                f"Pray error: {str(e)[:50]}"
            )
            time.sleep(15)
            return False

    def send_daily(self) -> bool:
        if self.bot.config.daily != "YES" or self.bot.config.stopped:
            return False

        try:
            self.bot.discord_bot.typingAction(self.bot.config.channel)
            if not self._interruptible_sleep(5):
                return False

            if self._stopped():
                return False
            self.bot.discord_bot.sendMessage(self.bot.config.channel, "owo daily")
            self.ui.slowPrinting(
                f"{self.bot.at()}{color.okgreen} [SENT]{color.reset} owo daily"
            )
            self.bot.total_commands += 1

            if not self._interruptible_sleep(5):
                return False
            msgs = self.bot.getMessages(num=5) or []

            daily_string = ""
            length = len(msgs)
            i = 0
            while i < length:
                if (msgs[i]['author']['id'] == self.bot.config.OwOID and
                    msgs[i]['content'] != "" and
                    ("Nu" in msgs[i]['content'] or "daily" in msgs[i]['content'])):
                    daily_string = msgs[i]['content']
                    i = length
                else:
                    i += 1

            if not daily_string:
                time.sleep(8)
                self.bot.total_commands -= 1
                return self.send_daily()
            else:
                from re import findall
                if "Nu" in daily_string:
                    daily_string = findall('[0-9]+', daily_string)
                    wait_time = str(int(daily_string[0]) * 3600 +
                                  int(daily_string[1]) * 60 +
                                  int(daily_string[2]))
                    from datetime import timedelta
                    self.ui.slowPrinting(
                        f"{self.bot.at()}{color.okblue} [INFO]{color.reset} "
                        f"Next Daily: {str(timedelta(seconds=int(wait_time)))}"
                    )
                if "Your next daily" in daily_string:
                    self.ui.slowPrinting(
                        f"{self.bot.at()}{color.okblue} [INFO]{color.reset} "
                        "Claimed Daily"
                    )
            return True

        except Exception as e:
            self.ui.slowPrinting(
                f"{self.bot.at()}{color.warning} [WARN]{color.reset} "
                f"Daily error: {str(e)[:50]}"
            )
            time.sleep(8)
            return False

    def send_sell(self) -> bool:
        if self.bot.config.sell.get('enable') != "YES" or self.bot.config.stopped:
            return False

        try:
            sell_type = self.bot.config.sell.get('types', 'all')
            self.bot.discord_bot.typingAction(self.bot.config.channel)
            if not self._interruptible_sleep(random.randint(30, 70)):
                return False

            if self._stopped():
                return False
            self.bot.discord_bot.sendMessage(
                self.bot.config.channel,
                f"owo sell {sell_type}"
            )

            self.ui.slowPrinting(
                f"{self.bot.at()}{color.okgreen} [SENT]{color.reset} "
                f"owo sell {sell_type}"
            )
            self.bot.total_commands += 1
            return True

        except Exception as e:
            self.ui.slowPrinting(
                f"{self.bot.at()}{color.warning} [WARN]{color.reset} "
                f"Sell error: {str(e)[:50]}"
            )
            time.sleep(10)
            return False

    def send_raw(self, message: str) -> bool:
        if self.bot.config.stopped:
            return False

        try:
            self.bot.discord_bot.typingAction(self.bot.config.channel)
            if not self._interruptible_sleep(random.randint(4, 8)):
                return False

            if self._stopped():
                return False
            response = self.bot.discord_bot.sendMessage(
                self.bot.config.channel,
                message
            )

            if response and response.status_code == 429:
                self.ui.slowPrinting(
                    f"{self.bot.at()}{color.fail}[ERROR]{color.reset} "
                    "Rate limit on text, waiting 120s"
                )
                time.sleep(120)
                return False

            self.ui.slowPrinting(
                f"{self.bot.at()}{color.okgreen} [SENT]{color.reset} {message}"
            )
            self.bot.total_texts += 1
            
            return True

        except Exception as e:
            self.ui.slowPrinting(
                f"{self.bot.at()}{color.warning} [WARN]{color.reset} "
                f"Send text error: {str(e)[:50]}"
            )
            time.sleep(15)
            return False
