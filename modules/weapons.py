from time import time, sleep
from re import findall
import random
from utils.colors import color


class WeaponModule:
    def __init__(self, bot, start_time):
        self.bot = bot
        self.start_time = start_time

    def setup(self, bot):
        # Không đăng ký task mua rương nào cả
        pass

    def initialize(self):
        pass

    def buy_one_crate(self):
        pass

    def reset_state(self):
        pass
