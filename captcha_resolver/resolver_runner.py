#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from captcha_resolver.resolver import run_resolver_standalone

if __name__ == "__main__":
    run_resolver_standalone()