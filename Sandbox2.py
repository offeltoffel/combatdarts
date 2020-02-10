from matplotlib import pyplot as plt
import numpy as np
import scipy.interpolate as scy_inp
import pandas as pd
from math import log
from datetime import timedelta, datetime
import time

wins = [[1,1,0], [3, 3, 0], [0, 4, 0]]
leg_wins = [i[1] for i in wins]
high = np.argmax(leg_wins)

print(high)