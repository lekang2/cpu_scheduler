import os
import random
import pandas as pd
import numpy as np

INVOCATION_PATTERN = {1: 40.6, 2:9.8, 3: 6.8, 4: 22.7, 5: 15.7}
JOB_DURATIONS = {1: 25, 2: 75, 3: 150, 4: 300, 5: 2000}
def readPattern(traceFile = "trace/invocations_per_function_md.anon.d01.csv", t = 0):
    pass
#updated by runxin 1228
def generateJob(std):
    # Randomly choose Fibonacci input (e.g., n in fib(n))
    #class id
    id=1
    fib_input = random.randint(10, 40)  # n between 10 and 40
    burstTime = int(fib_input * np.random.normal(1, std))  # Approximate burst time based on 'n'
    if burstTime < 10:
        burstTime = 10
    functype = "fib"
    return functype, burstTime, id

def generateWorkload(N, iat, outPath, std):
    totalTime = N*iat
    timeList = sorted(random.sample(range(totalTime), N))
    f = open(outPath, 'w')
    i = 0
    for t in timeList:
        functype, burstTime, class_id = generateJob(std)
        invocationId = "{}_{}".format(functype, i)
        startTime = t
        i += 1
        f.write("{} {} {} {} {}\n".format(invocationId, startTime, burstTime, class_id, i))
    f.close()

if __name__ == '__main__':
    N = 100  # Number of function invocations
    iat = 100  # Inter-arrival time in ms
    outPath = 'fib_workload.txt'  # Output file
    std = 0.1  # Standard deviation for burst time variability
    
    generateWorkload(N, iat, outPath, std)
    print(f"Fibonacci workload generated in {outPath}")
