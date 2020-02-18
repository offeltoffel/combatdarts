from matplotlib import pyplot as plt
import numpy as np
import scipy.interpolate as scy_inp
from math import log
from datetime import timedelta, datetime
import time

blub = list()

for i in range(3):
    bla = int(input("Number >> "))
    if bla > 5:
        i -= 1
        continue
    else:
        blub.append(bla)

print(blub)