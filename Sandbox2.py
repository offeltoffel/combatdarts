from matplotlib import pyplot as plt
import numpy as np
import scipy.interpolate as scy_inp
import pandas as pd
from math import log
from datetime import timedelta, datetime
import time

a = [[[], []] for _ in range(4)]
myArr = np.array([1,2,3,4])
a[0][0] = myArr

print(a)