from matplotlib import pyplot as plt
import numpy as np
import scipy.interpolate as scy_inp
from math import log
from datetime import timedelta, datetime
import time

nplayers = 3

mystr = ", ".join(str(i+1) for i in range(nplayers))
print(mystr)