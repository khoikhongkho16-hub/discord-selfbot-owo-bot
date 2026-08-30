import time
import random
import threading
from threading import Thread, Event
import gc
from utils.helpers import UI
from utils.colors import color
from utils.constants import BotConstants

class Scheduler:
    def __init__(self, bot):
        self.bot = bot
        self.ui = UI()
        self.running = False
        self.thread = None
        self._stop_event = Event()
        self.queue = []
        self.queue_lock = threading.Lock()
        
        self.is_sleeping = False
        self.sleep_until = 0
        self.active_until = 0
        self.session_start_time = time.time()
        self.total_active_time = 0
        self.total_sleep_time = 0
        self.sleep_count = 0
        
        self.hunt_cycles = 0
        self.weapon_counter = 0
        self.daily_done = False
        
        self.last_command_time = 0
        self.last_hunt_time = 0
        self.min_hunt_interval = 3
        
        self.pray_next_time = time.time() + random.randint(300, 420)
        self.sell_next_time = time.time() + random.randint(1800, 3600)
        self.gems_next_time = time.time() + 10
        self.exp_counter = 0
        self.exp_next_time = time.time() + random.randint(15, 30)
        
        self.weapon_cycle_counter = 0
        self.weapon_cycle_threshold = 2
        
        self.exp_cycle_counter = 0
        self.exp_cycle_threshold = 3
        
        self.command_timestamps = {}
        self.min_command_interval = 1.5
        
        self._loop_interval = 0.5
        self._gc_counter = 0
        self._gc_interval = 10
        
        self._queued_commands = set()

    def _format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _get_uptime(self):
        return time.time() - self.session_start_time

    def _schedule_sleep(self):
        if self.bot.config.sm != "YES":
            self.is_sleeping = False
            return
        
        active_duration = random.randint(420, 1140)
        break_duration = random.randint(222, 999)
        
        self.active_until = time.time() + active_duration
        self.sleep_until = self.active_until + break_duration
        
        active_end_time = time.strftime('%H:%M:%S', time.localtime(self.active_until))
        sleep_end_time = time.strftime('%H:%M:%S', time.localtime(self.sleep_until))
        
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Scheduler will run until {active_end_time} (active: {self._format_time(active_duration)})")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Next sleep from {active_end_time} to {sleep_end_time} (sleep: {self._format_time(break_duration)})")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Current uptime: {self._format_time(self._get_uptime())}")

    def register_task(self, name, func, min_interval, max_interval,
                      priority=0, depends_on=None):
        pass

    def _add_to_queue(self, func, priority=0):
        if self.bot.should_stop() or self._stop_event.is_set():
            return
        with self.queue_lock:
            func_name = func.__name__
            now = time.time()
            
            if func_name in self.command_timestamps:
                if now - self.command_timestamps[func_name] < self.min_command_interval:
                    return
            
            if func_name in self._queued_commands:
                return
            
            self.queue.append((priority, func))
            self.queue.sort(key=lambda x: x[0])
            self.command_timestamps[func_name] = now
            self._queued_commands.add(func_name)

    def _is_in_queue(self, func):
        with self.queue_lock:
            return func.__name__ in self._queued_commands

    def _should_sleep(self):
        if self.bot.config.sm != "YES" or self.bot.config.stopped:
            return False
        
        now = time.time()
        if self.is_sleeping:
            if now < self.sleep_until:
                return True
            else:
                self.is_sleeping = False
                self.sleep_count += 1
                self._schedule_sleep()
                return False
        
        if now >= self.active_until:
            self.is_sleeping = True
            self.total_active_time += self.active_until - (now - self._get_uptime())
            
            sleep_duration = int(self.sleep_until - now)
            sleep_end_time = time.strftime('%H:%M:%S', time.localtime(self.sleep_until))
            
            print(f"{self.bot.at()} {color.warning}[SLEEP]{color.reset} Entering sleep mode...")
            print(f"{self.bot.at()} {color.warning}[SLEEP]{color.reset} Sleep duration: {self._format_time(sleep_duration)}")
            print(f"{self.bot.at()} {color.warning}[SLEEP]{color.reset} Will resume at: {sleep_end_time}")
            print(f"{self.bot.at()} {color.warning}[SLEEP]{color.reset} Total sleep count: {self.sleep_count}")
            return True
        
        return False

    def _do_sleep(self):
        if self.bot.config.stopped:
            return
        
        remaining = int(self.sleep_until - time.time())
        if remaining > 0:
            while time.time() < self.sleep_until and not self.bot.config.stopped and not self._stop_event.is_set():
                time.sleep(1)
            
            if not self.bot.config.stopped and not self._stop_event.is_set():
                self.is_sleeping = False
                self.total_sleep_time += int(self.sleep_until - (time.time() - remaining))
                print(f"{self.bot.at()} {color.okgreen}[INFO]{color.reset} Waking up from sleep!")
                print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Total uptime: {self._format_time(self._get_uptime())}")
                print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Total sleep time: {self._format_time(self.total_sleep_time)}")
                print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Sleep cycles: {self.sleep_count}")
                self._schedule_sleep()

    def _queue_commands(self):
        if self.bot.config.stopped or self._stop_event.is_set():
            return
        
        now = time.time()
        
        if not self.daily_done and self.hunt_cycles >= 1 and self.bot.config.daily == "YES":
            if not self._is_in_queue(self._do_daily):
                self._add_to_queue(self._do_daily, priority=0)
                self.daily_done = True
        
        if self.hunt_cycles == 0 or (now - self.last_hunt_time >= self.min_hunt_interval):
            if not self._is_in_queue(self._do_hunt_battle):
                self._add_to_queue(self._do_hunt_battle, priority=10)
        
        if (self.bot.config.wm == "YES" and self.bot.weapons and 
            self.weapon_cycle_counter >= self.weapon_cycle_threshold and
            self.hunt_cycles > 0):
            if not self._is_in_queue(self._do_weapons):
                self._add_to_queue(self._do_weapons, priority=2)
                self.weapon_cycle_counter = 0
        
        if (self.bot.config.em.get('text') == "YES" and 
            self.exp_cycle_counter >= self.exp_cycle_threshold and
            self.hunt_cycles > 0):
            if not self._is_in_queue(self._do_exp):
                self._add_to_queue(self._do_exp, priority=3)
                self.exp_cycle_counter = 0
        
        if (self.bot.config.gm == "YES" and self.bot.gems and 
            self.hunt_cycles >= 1 and now >= self.gems_next_time):
            if not self._is_in_queue(self._do_gems):
                self._add_to_queue(self._do_gems, priority=7)
                self.gems_next_time = now + random.randint(120, 180)
        
        if self.bot.config.pm == "YES" and now >= self.pray_next_time:
            if not self._is_in_queue(self._do_pray):
                self._add_to_queue(self._do_pray, priority=4)
                self.pray_next_time = now + random.randint(300, 420)
        
        if (self.bot.config.sell.get('enable') == "YES" and 
            now >= self.sell_next_time):
            if not self._is_in_queue(self._do_sell):
                self._add_to_queue(self._do_sell, priority=5)
                self.sell_next_time = now + random.randint(1800, 3600)

    def _do_hunt_battle(self):
        if self.bot.should_stop() or self._stop_event.is_set():
            return
        
        now = time.time()
        if now - self.last_hunt_time < self.min_hunt_interval:
            return
        
        if not self.bot.executor.send_command("hunt"):
            return
        if self._stop_event.wait(random.randint(3, 7)) or self.bot.should_stop():
            return
        
        self.bot.executor.send_command("battle")
        
        self.hunt_cycles += 1
        self.last_hunt_time = now
        self.weapon_cycle_counter += 1
        self.exp_cycle_counter += 1
        
        with self.queue_lock:
            self._queued_commands.discard('_do_hunt_battle')

    def _do_daily(self):
        if self.bot.config.stopped or self._stop_event.is_set():
            return
        self.bot.executor.send_daily()
        with self.queue_lock:
            self._queued_commands.discard('_do_daily')

    def _do_weapons(self):
        if self.bot.config.stopped or not self.bot.weapons or self._stop_event.is_set():
            return
        self.bot.weapons.buy_one_crate()
        with self.queue_lock:
            self._queued_commands.discard('_do_weapons')

    def _do_exp(self):
        if self.bot.config.stopped or self._stop_event.is_set():
            return
        try:
            from requests import get
            if not hasattr(self.bot.config, 'quote_count'):
                self.bot.config.quote_count = 0
            if not hasattr(self.bot.config, 'quote_threshold'):
                self.bot.config.quote_threshold = random.randint(2, 4)
            
            response = get("https://dummyjson.com/quotes/random", timeout=10)
            if response.status_code == 200:
                json_data = response.json()
                quote = f"{json_data['quote']}"
                self.bot.executor.send_raw(quote)
                self.bot.config.quote_count += 1
                
                if (self.bot.config.em.get('owo') == "YES" and
                    self.bot.config.quote_count >= self.bot.config.quote_threshold):
                    time.sleep(random.randint(10, 20))
                    owo = random.choice(['owo', 'uwu'])
                    self.bot.executor.send_raw(owo)
                    self.bot.config.quote_count = 0
                    self.bot.config.quote_threshold = random.randint(2, 4)
        except Exception as e:
            pass
        
        with self.queue_lock:
            self._queued_commands.discard('_do_exp')

    def _do_pray(self):
        if self.bot.config.stopped or self._stop_event.is_set():
            return
        self.bot.executor.send_pray()
        with self.queue_lock:
            self._queued_commands.discard('_do_pray')

    def _do_sell(self):
        if self.bot.config.stopped or self._stop_event.is_set():
            return
        self.bot.executor.send_sell()
        with self.queue_lock:
            self._queued_commands.discard('_do_sell')

    def _do_gems(self):
        if self.bot.config.stopped or not self.bot.gems or self._stop_event.is_set():
            return
        try:
            self.bot.gems.gem_cycle()
        except Exception as e:
            pass
        with self.queue_lock:
            self._queued_commands.discard('_do_gems')

    def start(self):
        self.running = True
        self._stop_event.clear()
        self.session_start_time = time.time()
        self._schedule_sleep()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        while self.running and not self._stop_event.is_set() and not self.bot.config.stopped:
            try:
                time.sleep(self._loop_interval)
                
                if self._should_sleep():
                    self._do_sleep()
                    continue
                
                self._queue_commands()
                
                if self.queue and not self._stop_event.is_set() and not self.bot.config.stopped:
                    with self.queue_lock:
                        priority, command = self.queue.pop(0)
                    
                    if self.last_command_time > 0:
                        if command.__name__ == '_do_hunt_battle':
                            delay = random.randint(2, 4)
                        else:
                            delay = random.randint(1, 3)
                        
                        elapsed = time.time() - self.last_command_time
                        if elapsed < delay:
                            remaining = delay - elapsed
                            while remaining > 0 and not self._stop_event.is_set():
                                chunk = min(remaining, self._loop_interval)
                                if self._stop_event.wait(chunk):
                                    break
                                remaining -= chunk
                    
                    if not self.bot.config.stopped and not self._stop_event.is_set():
                        try:
                            command()
                            self.last_command_time = time.time()
                        except Exception as e:
                            pass
                        finally:
                            # A task may return early because of cooldown or an
                            # emergency stop. It must never remain queued forever.
                            with self.queue_lock:
                                self._queued_commands.discard(command.__name__)
                
                self._gc_counter += 1
                if self._gc_counter % self._gc_interval == 0:
                    gc.collect()
                
            except Exception as e:
                if not self._stop_event.is_set():
                    time.sleep(self._loop_interval)

    def stop(self):
        if self._stop_event.is_set() and not self.running:
            return
        self.running = False
        self._stop_event.set()
        with self.queue_lock:
            self.queue.clear()
            self._queued_commands.clear()
        
        total_runtime = self._get_uptime()
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} ========== SESSION SUMMARY ==========")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Total runtime: {self._format_time(total_runtime)}")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Active time: {self._format_time(self.total_active_time)}")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Sleep time: {self._format_time(self.total_sleep_time)}")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Sleep cycles: {self.sleep_count}")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} Hunt cycles: {self.hunt_cycles}")
        print(f"{self.bot.at()} {color.okcyan}[INFO]{color.reset} ======================================")

    def wait_stopped(self, timeout=5.0):
        """Wait briefly for the worker to exit before replacing the process."""
        if self.thread and self.thread.is_alive() and self.thread is not threading.current_thread():
            self.thread.join(timeout=timeout)
        return not self.thread or not self.thread.is_alive()
