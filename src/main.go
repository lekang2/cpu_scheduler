package main

import (
    "flag"
    "fmt"
    "os"
    "sync"
    "syscall"
    "time"
)
var (
	tlaAlphaFlag  = flag.Float64("tla_alpha", 0.10, "TLA α smoothing (0–1)")
	tlaWinFlag    = flag.Int   ("tla_win",   50,   "TLA rolling-window size")
	tlaIntFlag    = flag.Int   ("tla_int",   25,   "TLA monitor interval (ms)")
	tlaPctFlag    = flag.Int   ("tla_pct",   95,   "TLA percentile (80–99)")
	tlaSliceFlag  = flag.Float64("tla_slice",1.2,  "TLA promote slice ×Ts")
)

func main() {
    var rLimit syscall.Rlimit
    err := syscall.Getrlimit(syscall.RLIMIT_NOFILE, &rLimit)
    if err != nil {
        fmt.Println("Error Getting Rlimit ", err)
    }
    rLimit.Max = 1024000
    rLimit.Cur = 1024000
    err = syscall.Setrlimit(syscall.RLIMIT_NOFILE, &rLimit)
    if err != nil {
        fmt.Println("Error Setting Rlimit ", err)
    }
    err = syscall.Getrlimit(syscall.RLIMIT_NOFILE, &rLimit)
    if err != nil {
        fmt.Println("Error Getting Rlimit ", err)
    }
    fmt.Println("logs Rlimit Final", rLimit)

    var policy string
    flag.StringVar(&policy, "p", "m", "scheduling policies: m:SFS; c:CFS; s:SRTF; f:FIFO; tla:TLA-SFS")
    var source string
    flag.StringVar(&source, "t", "", "trace")
    var optimal string
    flag.StringVar(&optimal, "o", "optimal.txt", "STCF optimal values")
    cpu := flag.Int("n", 16, "# of cpu cores")
    fmt.Println("logs main cpu", *cpu)
    flag.Parse()

    // push CLI values into tla.go globals
    tlaAlpha           = *tlaAlphaFlag
    tlaRollingWinSz    = *tlaWinFlag
    tlaMonitorInterval = *tlaIntFlag
    tlaPercentile      = *tlaPctFlag
    tlaSliceMult       = *tlaSliceFlag


    fmt.Println("logs main cpu", *cpu)
    flag.Usage()

    if policy == "m" {
        testSFS(*cpu, source)
    } else if policy == "c" {
        testCFS(*cpu, source)
    } else if policy == "f" {
        testFIFO(*cpu, source)
    } else if policy == "tla" {
        testTLA(*cpu, source)
    }else if policy == "r" {
        testRR(*cpu, source)
    }else {
        testSTCF(*cpu, source, optimal)
    }
}

func testSTCF(cpu int, source string, optimal string) {
    trace, _ := GetTrace(source)
    Simulate_schedule(trace, optimal, cpu)
}

func testSFS(cpu int, source string) {
    wg := sync.WaitGroup{}
    trace, num := GetTrace(source)
    cache := make(chan PidI, num)
    wg.Add(1)
    go Scheduler(&wg, cache, cpu, num)

    for i := 0; i < len(trace); i++ {
        go Send(trace[i], cache)
        if i < len(trace)-1 {
            time.Sleep(time.Duration(trace[i+1].Start-trace[i].Start) * time.Millisecond)
        }
    }

    wg.Wait()
    fmt.Println("DEBUG: All SFS requests processed")
    close(cache)
    fmt.Println("DEBUG: Cache channel closed.")

    logFile := "/result/sfs.txt"
    f, err := os.OpenFile(logFile, os.O_APPEND|os.O_WRONLY, 0644)
    if err == nil {
        f.WriteString("\nAll SFS requests are served.\n")
        f.Close()
    }
    fmt.Println("All SFS requests are served.")
}

// testTLA sets up SFS with TLA monitoring for tail latency
func testTLA(cpu int, source string) {
    wg := sync.WaitGroup{}
    trace, num := GetTrace(source)
    cache := make(chan PidI, num)

    wg.Add(1)
    go Scheduler(&wg, cache, cpu, num)

    // Create TLA instance with Ts = 6 ms (or choose your value)
    tlaInstance := NewTLA(6)
    tlaInstance.StartMonitoring()
    defer tlaInstance.StopMonitoring()

    // Store the TLA instance in a global variable for use in execute.go
    tlaInstanceGlobal = tlaInstance

    for i := 0; i < len(trace); i++ {
        go Send(trace[i], cache)
        if i < len(trace)-1 {
            time.Sleep(time.Duration(trace[i+1].Start-trace[i].Start) * time.Millisecond)
        }
    }

    wg.Wait()
    fmt.Println("DEBUG: All TLA-SFS requests processed")
    close(cache)
    fmt.Println("DEBUG: Cache channel closed.")

    logFile := "/result/tla.txt"
    f, err := os.OpenFile(logFile, os.O_APPEND|os.O_WRONLY, 0644)
    if err == nil {
        f.WriteString("\nAll TLA-SFS requests are served.\n")
        f.Close()
    }
    fmt.Println("All TLA-SFS requests are served.")
}

func testFIFO(cpu int, source string) {
    start_time := time.Now()
    wg := sync.WaitGroup{}
    trace, _ := GetTrace(source)
    cache := make(chan PidI)
    for _, v := range trace {
        wg.Add(1)
        go ExecuteNoChannel(&wg, v, "F", cache, start_time, "0xff")
    }
    wg.Wait()
    logFile := "/result/fifo.txt"
    f, err := os.OpenFile(logFile, os.O_APPEND|os.O_WRONLY, 0644)
    if err == nil {
        f.WriteString("\nAll fifo requests are served.\n")
        f.Close()
    }
    fmt.Println("All fifo requests are served.")
}

func testCFS(cpu int, source string) {
    start_time := time.Now()
    wg := sync.WaitGroup{}
    trace, _ := GetTrace(source)
    cache := make(chan PidI)
    cpuC := GetCFSCpuCores(cpu)
    wg.Add(len(trace))
    for i := 0; i < len(trace); i++ {
        go ExecuteNoChannel(&wg, trace[i], "N", cache, start_time, cpuC)
        if i < len(trace)-1 {
            time.Sleep(time.Duration(trace[i+1].Start-trace[i].Start) * time.Millisecond)
        }
    }
    wg.Wait()
    logFile := "/result/cfs.txt"
    f, err := os.OpenFile(logFile, os.O_APPEND|os.O_WRONLY, 0644)
    if err == nil {
        f.WriteString("\nAll CFS requests are served.\n")
        f.Close()
    }
    fmt.Println("All CFS requests are served.")
}
func testRR(cpu int, source string) {
    startTime := time.Now()
    wg := sync.WaitGroup{}
    trace, _ := GetTrace(source)

    cache   := make(chan PidI)         // unused by ExecuteNoChannel, kept for symmetry
    cpuMask := GetCFSCpuCores(cpu)     // pin RR tasks to all logical CPUs

    for _, job := range trace {
        wg.Add(1)
        go ExecuteNoChannel(&wg, job, "R", cache, startTime, cpuMask)
    }
    wg.Wait()

    logFile := "/result/rr.txt"
    if f, err := os.OpenFile(logFile, os.O_APPEND|os.O_WRONLY|os.O_CREATE, 0644); err == nil {
        f.WriteString("\nAll RR requests are served.\n")
        f.Close()
    }
    fmt.Println("All RR requests are served.")
}
