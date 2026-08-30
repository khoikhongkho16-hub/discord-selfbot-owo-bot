import time
import json
import asyncio
import sys
import os
import subprocess
import ctypes
from utils.helpers import UI
from utils.colors import color


class EventHandler:
    def __init__(self, bot):
        self.bot = bot
        self.ui = UI()
        self.captcha_keywords = [
            "captcha", "verify that you are human", "please complete",
            "(1/5)", "(2/5)", "(3/5)", "(4/5)", "(5/5)",
            "⚠", "banned", "macros or botting"
        ]
        self.is_ready = False
        self.captcha_detected = False
        self._solve_task = None
        self._is_solving = False
        self._user_confirmed_exit = False
        self._loop = None
        self._solving_lock = False
        self._last_event_time = 0
        self._event_cooldown = 1.0
        self._last_message_id = None
        self._current_user_id = None
        self._settings_displayed = False

    def connect(self):
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        @self.bot.discord_bot.gateway.command
        def on_ready(resp):
            # SỬA: ready_supplemental -> ready
            if resp.event.ready and not self.is_ready:
                self.is_ready = True
                self.bot._is_ready = True
                self._on_ready(resp)

        @self.bot.discord_bot.gateway.command
        def security(resp):
            self._security(resp)

    def display_settings(self):
        """Hiển thị thông tin cơ bản của tài khoản"""
        try:
            if self._settings_displayed:
                return
            
            # Lấy thông tin user từ session
            session_user = getattr(self.bot.discord_bot.gateway.session, "user", {})
            
            if not isinstance(session_user, dict) or not session_user:
                print(f"{color.warning}[WARNING]{color.reset} Cannot retrieve user information")
                return
            
            # Hiển thị thông tin cơ bản
            username = session_user.get('username', 'Unknown')
            discriminator = session_user.get('discriminator', '0000')
            user_id = session_user.get('id', 'Unknown')
            
            print(f"\n{color.okgreen}╔═══════════════════════════════════════════════════════════╗{color.reset}")
            print(f"{color.okgreen}║{color.reset}              {color.bold}ACCOUNT INFORMATION{color.reset}                  {color.okgreen}║{color.reset}")
            print(f"{color.okgreen}╠═══════════════════════════════════════════════════════════╣{color.reset}")
            print(f"{color.okgreen}║{color.reset}  {color.okcyan}Username:{color.reset} {username}#{discriminator}")
            print(f"{color.okgreen}║{color.reset}  {color.okcyan}User ID:{color.reset}   {user_id}")
            
            # Hiển thị channel info
            try:
                channel_info = self.bot.discord_bot.getChannel(self.bot.config.channel)
                if channel_info:
                    channel_json = channel_info.json()
                    if isinstance(channel_json, dict):
                        channel_name = channel_json.get('name', 'Unknown')
                        guild_id = channel_json.get('guild_id', 'Unknown')
                        print(f"{color.okgreen}║{color.reset}  {color.okcyan}Channel:{color.reset}  #{channel_name}")
                        print(f"{color.okgreen}║{color.reset}  {color.okcyan}Guild ID:{color.reset} {guild_id}")
            except:
                pass
            
            # Hiển thị bot version
            print(f"{color.okgreen}║{color.reset}  {color.okcyan}Bot Version:{color.reset} 3.7.0")
            
            # Hiển thị các module đã đăng ký
            modules = []
            if hasattr(self.bot, 'gems') and self.bot.gems:
                modules.append("Gems")
            if hasattr(self.bot, 'weapons') and self.bot.weapons:
                modules.append("Weapons")
            modules.extend(["Pray", "Exp", "Daily", "Sell"])
            
            if modules:
                print(f"{color.okgreen}║{color.reset}  {color.okcyan}Modules:{color.reset}    {', '.join(modules)}")
            
            print(f"{color.okgreen}╚═══════════════════════════════════════════════════════════╝{color.reset}\n")
            
            self._settings_displayed = True
            
        except Exception as e:
            print(f"{color.warning}[WARNING]{color.reset} Failed to display settings: {e}")

    def show_info(self):
        """Fallback: Hiển thị thông tin nếu display_settings không hoạt động"""
        try:
            session_user = getattr(self.bot.discord_bot.gateway.session, "user", {})
            if isinstance(session_user, dict) and session_user:
                username = session_user.get('username', 'Unknown')
                discriminator = session_user.get('discriminator', '0000')
                user_id = session_user.get('id', 'Unknown')
                
                print(f"\n{color.okgreen}=== ACCOUNT INFORMATION ==={color.reset}")
                print(f"{color.okcyan}Username:{color.reset} {username}#{discriminator}")
                print(f"{color.okcyan}User ID:{color.reset} {user_id}")
                print(f"{color.okcyan}Channel:{color.reset} {self.bot.config.channel}")
                print(f"{color.okcyan}Bot Version:{color.reset} 3.7.0")
                
                # Hiển thị modules
                modules = []
                if hasattr(self.bot, 'gems') and self.bot.gems:
                    modules.append("Gems")
                if hasattr(self.bot, 'weapons') and self.bot.weapons:
                    modules.append("Weapons")
                modules.extend(["Pray", "Exp", "Daily", "Sell"])
                if modules:
                    print(f"{color.okcyan}Modules:{color.reset} {', '.join(modules)}")
                print()
        except:
            pass

    def _on_ready(self, resp):
        """Xử lý khi bot ready"""
        try:
            # Lấy channel info
            try:
                channel_info = self.bot.discord_bot.getChannel(self.bot.config.channel)
                if channel_info:
                    channel_info = channel_info.json()
                    if isinstance(channel_info, dict):
                        self.bot.config.guildID = channel_info.get('guild_id')
                    else:
                        self.bot.config.guildID = None
            except:
                self.bot.config.guildID = None

            # Lấy DM info
            try:
                self.bot.config.dmsID = None
                dm_ids = getattr(self.bot.discord_bot.gateway.session, "DMIDs", [])
                dms = getattr(self.bot.discord_bot.gateway.session, "DMs", {})
                for dm_id in dm_ids:
                    dm_data = dms.get(dm_id, {})
                    recipients = dm_data.get('recipients', {})
                    if self.bot.config.OwOID in recipients:
                        self.bot.config.dmsID = dm_id
                        break
            except:
                pass
            
            # Hiển thị thông tin tài khoản sau khi ready
            self.display_settings()
            
            # Thông báo bot đã sẵn sàng
            print(f"{color.okgreen}[SUCCESS]{color.reset} Bot is ready and running!")
            print(f"{color.okcyan}[INFO]{color.reset} Started at: {time.strftime('%H:%M:%S')}")
            print(f"{color.okcyan}[INFO]{color.reset} Type Ctrl+C to stop the bot\n")

        except Exception as e:
            print(f"{color.warning}[WARNING]{color.reset} Error in _on_ready: {e}")

    def _security(self, resp):
        try:
            if not resp.event.message:
                return

            m = resp.parsed.auto()
            if not isinstance(m, dict):
                return

            # Deduplicate the same gateway message, never discard a different
            # security warning merely because it arrived within one second.
            message_id = m.get('id')
            if message_id and message_id == self._last_message_id:
                return
            self._last_message_id = message_id

            result = self._issue_checker(m)
            if result == "captcha" and not self.captcha_detected and not self._solving_lock:
                self.captcha_detected = True
                # Kill outgoing work before alerts, resolver checks or I/O.
                self.bot.emergency_pause()
                self._handle_captcha()
                return

            if self.bot.gems and self.bot.config.gm == "YES":
                content = m.get('content', '')
                author = m.get('author', {})
                author_id = author.get('id')

                if author_id == self.bot.config.OwOID and content:
                    if 'hunt is empowered by' in content.lower():
                        self.bot.gems.check_and_use_gems_from_hunt(content)

                    if 'already have an active' in content.lower() or 'you do not own this gem' in content.lower():
                        self.bot.gems.handle_use_response(content)

        except:
            pass

    def _handle_captcha(self):
        try:
            if self._solving_lock:
                return

            # Idempotent: the event handler normally paused it already, but
            # keep this safe when called directly.
            self.bot.emergency_pause(wait_for_scheduler=True)
            self._solving_lock = True
            self._trigger_alert()

            if not self.bot.has_captcha_resolver():
                self._pause_bot_no_resolver()
                return

            try:
                self.bot.discord_bot.gateway.close()
            except:
                pass

            self._run_resolver_in_place()

        except Exception as e:
            self._solving_lock = False
            self._pause_bot_no_resolver()

    def _trigger_alert(self):
        try:
            if os.name == "nt":
                try:
                    user32 = ctypes.windll.user32
                    kernel32 = ctypes.windll.kernel32

                    hwnd = kernel32.GetConsoleWindow()
                    if hwnd:
                        user32.FlashWindow(hwnd, True)

                        screen_width = user32.GetSystemMetrics(0)
                        screen_height = user32.GetSystemMetrics(1)

                        rect = ctypes.wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))

                        win_width = rect.right - rect.left
                        win_height = rect.bottom - rect.top

                        x = int((screen_width - win_width) / 2)
                        y = int((screen_height - win_height) / 2)

                        user32.MoveWindow(hwnd, x, y, win_width, win_height, True)
                        user32.SetForegroundWindow(hwnd)
                except:
                    pass

            print('\a')
            print('\a')

        except:
            pass

    def _run_resolver_in_place(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            resolver_script = os.path.join(base_dir, 'captcha_resolver', 'resolver_runner.py')

            if not os.path.exists(resolver_script):
                self._create_resolver_runner(resolver_script)

            user_id = self._current_user_id or "Unknown"
            os.environ['CAPTCHA_USER_ID'] = str(user_id)

            os.execv(sys.executable, [sys.executable, resolver_script])

        except Exception as e:
            self._pause_bot_no_resolver()

    def _create_resolver_runner(self, path):
        content = '''#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from captcha_resolver.resolver import run_resolver_standalone

if __name__ == "__main__":
    run_resolver_standalone()
'''
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except:
            pass

    def _pause_bot_no_resolver(self):
        try:
            self.bot.emergency_pause()

            print(f'{self.bot.at()}{color.warning} !! [CAPTCHA DETECTED] !! Bot Paused')
            print(f'{color.okcyan}[INFO]{color.reset} Captcha detected but no resolver configured.')
            print(f'{color.okcyan}[INFO]{color.reset} Bot is paused. Press Ctrl+C to exit.')

        except Exception as e:
            pass

    def _issue_checker(self, m):
        try:
            content = m.get('content', '')
            author = m.get('author', {})
            author_id = author.get('id')
            
            if self.captcha_detected or self.bot.config.stopped:
                return None
            
            if author_id != self.bot.config.OwOID:
                return None
            
            import re
            
            session_user = getattr(self.bot.discord_bot.gateway.session, "user", {})
            my_id = session_user.get('id') if isinstance(session_user, dict) else None
            
            if not my_id:
                return None
            
            self._current_user_id = my_id
            
            mention_pattern = r'<@!?(\d+)>'
            mentions = re.findall(mention_pattern, content)
            
            is_mentioned = str(my_id) in mentions
            
            if not is_mentioned:
                return None
            
            clean = content
            for zwc in ['\u200b', '\u200c', '\u200d', '\ufeff']:
                clean = clean.replace(zwc, '')
            clean = clean.lower()
            
            security_phrases = (
                "captcha",
                "are you a real human",
                "verify that you are human",
                "please complete",
                "macros or botting",
                "you have been banned",
            )
            if any(phrase in clean for phrase in security_phrases):
                channel_id = m.get('channel_id')
                if str(channel_id) == str(self.bot.config.channel):
                    return "captcha"
            
            return None
            
        except:
            return None

    def disconnect(self):
        try:
            self.bot.discord_bot.gateway.close()
        except:
            pass
