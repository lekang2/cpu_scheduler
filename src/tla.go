// tla.go
// Tail-Latency-Aware monitor with tunable parameters.
// All scheduling logic remains FIFO → CFS → (optional boost) FIFO → CFS.

package main

import (
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"sync"
	"time"

	"github.com/shirou/gopsutil/v3/process"
)

/* ------------------------------------------------------------------ */
/*  Tunable parameters (set once from main.go via -tla_* flags)        */
/* ------------------------------------------------------------------ */

var (
	tlaAlpha           = 0.10  // α for SLO exponential smoothing
	tlaRollingWinSz    = 50    // rolling-window size
	tlaMonitorInterval = 25    // monitor wake-up interval (ms)
	tlaPercentile      = 95    // chosen percentile (80–99)
	tlaSliceMult       = 1.2   // promote slice × Ts
)

/* ------------------------------------------------------------------ */
/*  Core data structures                                              */
/* ------------------------------------------------------------------ */

type TLA struct {
	mu           sync.Mutex
	turnSamples  []int64           // all turnaround samples
	shortSamples []int64           // only jobs that finished in ≤ 2×Ts
	sloEstimate  int64             // current SLO (ms) based on shortSamples
	jobStates    map[int]*JobState // job-id → state
	timeSlice    int               // base Ts (ms)
	completionCh chan CompletionEvent
	stopCh       chan struct{}
}

type JobState struct {
	pid       int
	startTime time.Time
	finished  bool
	promoted  bool
}

/* CompletionEvent is sent from Execute() when a job finishes. */
type CompletionEvent struct {
	JobID        int
	TurnaroundMS int64
	RequestIndex int32
}

/* ------------------------------------------------------------------ */
/*  Constructor                                                       */
/* ------------------------------------------------------------------ */

func NewTLA(ts int) *TLA {
	return &TLA{
		turnSamples:  make([]int64, 0, tlaRollingWinSz),
		shortSamples: make([]int64, 0, tlaRollingWinSz),
		sloEstimate:  int64(2 * ts), // initial guess ~ 2×Ts
		jobStates:    make(map[int]*JobState),
		timeSlice:    ts,
		completionCh: make(chan CompletionEvent, 1024),
		stopCh:       make(chan struct{}),
	}
}

/* ------------------------------------------------------------------ */
/*  Lifecycle hooks                                                   */
/* ------------------------------------------------------------------ */

func (t *TLA) StartMonitoring() {
	go t.monitorLoop()
	go t.handleCompletions()
}
func (t *TLA) StopMonitoring() { close(t.stopCh) }

func (t *TLA) OnJobStart(jobID, pid int, start time.Time) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if _, ok := t.jobStates[jobID]; !ok {
		t.jobStates[jobID] = &JobState{pid: pid, startTime: start}
	}
}

/* ------------------------------------------------------------------ */
/*  Handle completions & update SLO                                   */
/* ------------------------------------------------------------------ */

func (t *TLA) handleCompletions() {
	for {
		select {
		case ev := <-t.completionCh:
			t.onJobFinish(ev)
		case <-t.stopCh:
			return
		}
	}
}

func (t *TLA) onJobFinish(ev CompletionEvent) {
	t.mu.Lock()
	defer t.mu.Unlock()

	if st, ok := t.jobStates[ev.JobID]; ok {
		st.finished = true
	}

	/* rolling windows */
	t.turnSamples = append(t.turnSamples, ev.TurnaroundMS)
	if ev.TurnaroundMS <= int64(2*t.timeSlice) { // treat as “short/middle”
		t.shortSamples = append(t.shortSamples, ev.TurnaroundMS)
	}

	trim := func(sl *[]int64) {
		if len(*sl) > tlaRollingWinSz {
			*sl = (*sl)[1:]
		}
	}
	trim(&t.turnSamples)
	trim(&t.shortSamples)

	/* percentile over shortSamples; fallback to all if empty */
	var baseSlice []int64
	if len(t.shortSamples) > 0 {
		baseSlice = t.shortSamples
	} else {
		baseSlice = t.turnSamples
	}
	pSel := calcPXX(baseSlice)
	old := t.sloEstimate
	newVal := int64(tlaAlpha*float64(pSel) + (1-tlaAlpha)*float64(old))
	if newVal != old {
		t.sloEstimate = newVal
		logSLOChange(newVal, old, pSel, ev.RequestIndex)
	}
}

func logSLOChange(new, old, pSel int64, idx int32) {
	if f, err := os.OpenFile("/result/tla.txt", os.O_APPEND|os.O_WRONLY, 0644); err == nil {
		fmt.Fprintf(f, "[TLA] SLO→%d ms (old %d, p%d=%d) after Req#%d\n",
			new, old, tlaPercentile, pSel, idx)
		f.Close()
	}
}

/* ------------------------------------------------------------------ */
/*  Monitor loop                                                      */
/* ------------------------------------------------------------------ */

func (t *TLA) monitorLoop() {
	ticker := time.NewTicker(time.Duration(tlaMonitorInterval) * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			t.checkTailJobs()
		case <-t.stopCh:
			return
		}
	}
}

func (t *TLA) checkTailJobs() {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now()
	threshold := int64(1.2 * float64(t.sloEstimate)) // 1.2×SLO(short)
	for _, st := range t.jobStates {
		if st.finished || st.promoted {
			continue
		}
		elapsed := now.Sub(st.startTime).Milliseconds()
		if elapsed >= threshold {
			st.promoted = true
			go t.promoteJob(st.pid)
		}
	}
}

/* ------------------------------------------------------------------ */
/*  Promotion logic                                                   */
/* ------------------------------------------------------------------ */

func (t *TLA) promoteJob(pid int) {
	mask := GetCFSCpuCores(8) // adjust if needed
	_ = exec.Command("schedtool", "-F", "-p", "20", "-a", mask, strconv.Itoa(pid)).Run()

	time.Sleep(time.Duration(tlaSliceMult*float64(t.timeSlice)) * time.Millisecond)

	if p, err := process.NewProcess(int32(pid)); err == nil {
		if st, _ := p.Status(); len(st) > 0 && st[0] != "zombie" {
			_ = exec.Command("schedtool", "-N", "-a", mask, strconv.Itoa(pid)).Run()
		}
	}
}

/* ------------------------------------------------------------------ */
/*  Percentile helper                                                 */
/* ------------------------------------------------------------------ */

func calcPXX(arr []int64) int64 {
	if len(arr) == 0 {
		return 0
	}
	tmp := make([]int64, len(arr))
	copy(tmp, arr)
	quickSort(tmp, 0, len(tmp)-1)

	idx := int(float64(len(tmp))*float64(tlaPercentile)/100.0) - 1
	if idx < 0 {
		idx = 0
	}
	return tmp[idx]
}

/* simple quicksort */
func quickSort(a []int64, lo, hi int) {
	if lo >= hi {
		return
	}
	p := partition(a, lo, hi)
	quickSort(a, lo, p-1)
	quickSort(a, p+1, hi)
}
func partition(a []int64, lo, hi int) int {
	pivot := a[hi]
	i := lo
	for j := lo; j < hi; j++ {
		if a[j] < pivot {
			a[i], a[j] = a[j], a[i]
			i++
		}
	}
	a[i], a[hi] = a[hi], a[i]
	return i
}
