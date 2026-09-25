with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_FINAL.py", "r", encoding="utf-8") as f:
    text = f.read()

arch_comment = """
# ======================================================================
# REAL N2N V14
#
# Gemini:
# T0-T3
# persistent Chrome
# persistent Gemini tabs
# first-free release order
#
# WMR:
# W0-W3
# 2 tabs/profile
# global first-free
# owner-thread Selenium
#
# Downloads:
# CDP GUID
# independent lifecycle
#
# Backend:
# R2
# DB
# credits
# BullMQ
#
# Authentication:
# Google + Gemini active validation
# ======================================================================
"""

with open(r"C:\Users\PC\Desktop\FULL_QUEUE_WORKER_V14_N2N_FINAL.py", "w", encoding="utf-8") as f:
    f.write(arch_comment + "\n" + text)
