package main

import (
    "fmt"
    "log"
    "os/exec"
    "strconv"
    "sync"
    "sync/atomic"
    "time"
)

// Global counter for completed requests
var completedRequests int32 = 0

// Global TLA instance pointer; set only in TLA mode (policy "tla")
var tlaInstanceGlobal *TLA = nil

type PidI struct {
    Pid    int
    Job    string
    N      int
    Id     int
    St     time.Time
    Credit int
}

func Send(job Action, pids chan PidI) {
    o := time.Now()
    new_pid := PidI{-10, job.JobName, job.Para, job.Id, o, -3}
    pids <- new_pid
}

func Execute(job PidI, p string, pids chan PidI, core string, queue chan PidI) {
    var cmd *exec.Cmd
    start_time := job.St
    t1 := time.Now()

    if p == "N" {
        cmd = exec.Command("schedtool", "-N", "-a", core, "-e", "python", "fib.py", strconv.Itoa(job.N), strconv.Itoa(job.Id))
    } else {
        cmd = exec.Command("schedtool", "-F", "-p", "20", "-a", core, "-e", "python", "fib.py", strconv.Itoa(job.N), strconv.Itoa(job.Id))
    }

    err := cmd.Start()
    if err != nil {
        log.Fatal("logs exec 1", err)
    }
    tw := time.Now()
    fmt.Println("logs wait time", tw.Sub(t1))

    // Notify TLA (if in TLA mode) that the job has started
    if tlaInstanceGlobal != nil && cmd.Process != nil {
        tlaInstanceGlobal.OnJobStart(job.Id, cmd.Process.Pid, start_time)
    }

    pid := cmd.Process.Pid
    var new_pid PidI
    if cmd != nil {
        new_pid = PidI{pid, job.Job, job.N, job.Id, time.Now(), job.Credit}
    } else {
        new_pid = PidI{0, job.Job, job.N, job.Id, time.Now(), job.Credit}
    }

    queue <- new_pid
    err = cmd.Wait()
    if err != nil {
        log.Fatal("exec 2", err)
    }
    t2 := time.Now()
    new_pid.Credit = -2
    pids <- new_pid

    requestIndex := atomic.AddInt32(&completedRequests, 1)
    fmt.Println("logs TIME: ", job.Job, t1.Sub(start_time), t2.Sub(start_time), "Request#", requestIndex)

    // Notify TLA of job completion (if in TLA mode)
    if tlaInstanceGlobal != nil {
        turnaround := t2.Sub(start_time).Milliseconds()
        ev := CompletionEvent{
            JobID:        job.Id,
            TurnaroundMS: turnaround,
            RequestIndex: requestIndex,
        }
        tlaInstanceGlobal.completionCh <- ev
    }
}

func ExecuteNoChannel(wg *sync.WaitGroup, job Action, p string, pids chan PidI, start_time time.Time, cpuC string) {
    defer wg.Done()

    t1 := time.Now()
    var cmd *exec.Cmd
    if p == "N" {
        cmd = exec.Command("schedtool", "-N", "-a", cpuC, "-e", "python", job.Exec, strconv.Itoa(job.Para), strconv.Itoa(job.Id))
    } else {
        cmd = exec.Command("schedtool", "-R", "-p", "20", "-a", "0x1", "-e", "python", job.Exec, strconv.Itoa(job.Para), strconv.Itoa(job.Id))
    }

    err := cmd.Start()
    if err != nil {
        log.Fatal("exec 1", err)
    }
    tw := time.Now()
    fmt.Println("logs wait time", tw.Sub(t1))

    if tlaInstanceGlobal != nil && cmd.Process != nil {
        tlaInstanceGlobal.OnJobStart(job.Id, cmd.Process.Pid, t1)
    }

    err = cmd.Wait()
    if err != nil {
        log.Fatal("exec 2", err)
    }
    t2 := time.Now()

    requestIndex := atomic.AddInt32(&completedRequests, 1)
    fmt.Println("logs TIME: ", job.JobName, t1.Sub(start_time), t2.Sub(start_time), "Request#", requestIndex)

    if tlaInstanceGlobal != nil {
        turnaround := t2.Sub(t1).Milliseconds()
        ev := CompletionEvent{
            JobID:        job.Id,
            TurnaroundMS: turnaround,
            RequestIndex: requestIndex,
        }
        tlaInstanceGlobal.completionCh <- ev
    }
}
