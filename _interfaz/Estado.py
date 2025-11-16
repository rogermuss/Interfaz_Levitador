from enum import Enum

class Estado(Enum):

     RISING = 1
     FALLING = 2
     OFF = 3
     NO_BALL = 4
     STABLE = 5
     OUT_OF_RANGE = 6
     UNSTABLE = 7