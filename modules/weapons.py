from time import time, sleep
from re import findall
import random
from utils.colors import color


class WeaponModule:
    def __init__(self, bot, start_time):
        self.bot = bot
        self.start_time = start_time
        self.ui = bot.ui

    def setup(self, bot):
        self.bot = bot
        # Đăng ký task chạy hàm buy_custom_item định kỳ từ 10 đến 10 giây
        if getattr(bot.config, 'wm', 'YES') == "YES":
            bot.scheduler.register_task(
                name="buy_id_1", 
                func=self.buy_custom_item, 
                min_interval=10,  
                max_interval=10,  
                priority=2
            )

    def at(self):
        elapsed = int(time() - self.start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f'\033[0;43m{h:02}:{m:02}:{s:02}\033[0;21m'

    def buy_custom_item(self):
        if self.bot.config.stopped:
            return
        
        try:
            # Mô phỏng gõ phím và gửi lệnh "owo buy 1" (hoặc "obuy 1")
            self.bot.discord_bot.typingAction(str(self.bot.config.channel))
            sleep(random.uniform(0.5, 1.0))
            
            # Bạn có thể đổi thành "obuy 1" nếu game hỗ trợ viết tắt
            command_text = "owo buy 1" 
            
            self.bot.discord_bot.sendMessage(str(self.bot.config.channel), command_text)
            self.ui.slowPrinting(f"{self.at()}{color.okgreen} [SENT]{color.reset} {command_text}")
            self.bot.total_commands += 1
            
        except Exception as e:
            self.ui.slowPrinting(f"{self.at()}{color.fail} [WEAPONS]{color.reset} Failed to send command: {e}")

    def initialize(self):
        pass

    def buy_one_crate(self):
        pass

    def reset_state(self):
        pass
