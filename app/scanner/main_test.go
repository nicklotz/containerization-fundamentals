package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand/v2"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"
)

// fakeAPI is a small stand-in for bag-api that keeps bags in a map.
type fakeAPI struct {
	mu        sync.Mutex
	bags      map[string]*Bag
	scans     []string // "TAG checkpoint scanner" for every scan received
	listLimit string   // the limit parameter of the last GET /api/bags
	conflict  bool     // when true, every scan answers HTTP 409
}

func newFakeAPI(t *testing.T, bags ...Bag) (*fakeAPI, *httptest.Server) {
	t.Helper()
	f := &fakeAPI{bags: map[string]*Bag{}}
	for i := range bags {
		f.bags[bags[i].Tag] = &bags[i]
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/bags", f.list)
	mux.HandleFunc("POST /api/bags", f.checkIn)
	mux.HandleFunc("POST /api/bags/{tag}/scans", f.scan)
	mux.HandleFunc("GET /api/stats", f.stats)
	server := httptest.NewServer(mux)
	t.Cleanup(server.Close)
	return f, server
}

func (f *fakeAPI) list(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.listLimit = r.URL.Query().Get("limit")
	bags := []Bag{}
	for _, bag := range f.bags {
		bags = append(bags, *bag)
	}
	writeJSON(w, http.StatusOK, bags)
}

func (f *fakeAPI) checkIn(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	var bag Bag
	_ = json.NewDecoder(r.Body).Decode(&bag)
	bag.Tag = fmt.Sprintf("BT9000%02d", len(f.bags)+1)
	bag.Status = "checked_in"
	f.bags[bag.Tag] = &bag
	writeJSON(w, http.StatusCreated, bag)
}

func (f *fakeAPI) scan(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	var body struct{ Checkpoint, Scanner string }
	_ = json.NewDecoder(r.Body).Decode(&body)
	tag := r.PathValue("tag")
	f.scans = append(f.scans, fmt.Sprintf("%s %s %s", tag, body.Checkpoint, body.Scanner))
	bag, found := f.bags[tag]
	switch {
	case !found:
		writeJSON(w, http.StatusNotFound, map[string]string{"detail": "Bag " + tag + " not found"})
	case f.conflict:
		writeJSON(w, http.StatusConflict, map[string]string{"detail": "Bag " + tag + " was moved by another scan"})
	default:
		bag.Status = body.Checkpoint
		writeJSON(w, http.StatusOK, bag)
	}
}

func (f *fakeAPI) stats(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	stats := Stats{ByStatus: map[string]int{}}
	for _, bag := range f.bags {
		stats.ByStatus[bag.Status]++
		stats.Total++
	}
	writeJSON(w, http.StatusOK, stats)
}

// snapshot returns copies of what the fake API received, read under its lock.
func (f *fakeAPI) snapshot() (scans []string, listLimit string, bags map[string]Bag) {
	f.mu.Lock()
	defer f.mu.Unlock()
	bags = map[string]Bag{}
	for tag, bag := range f.bags {
		bags[tag] = *bag
	}
	return append([]string(nil), f.scans...), f.listLimit, bags
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

// testScanner returns a scanner with a fixed random seed.
func testScanner(url string, minMoving, checkInOneIn int) *Scanner {
	s := NewScanner("sc-test", NewClient(url))
	s.Rand = rand.New(rand.NewPCG(1, 2))
	s.MinMoving = minMoving
	s.CheckInOneIn = checkInOneIn
	return s
}

func TestNextCheckpoint(t *testing.T) {
	cases := []struct {
		current, next string
		ok            bool
	}{
		{"checked_in", "security", true},
		{"security", "sorted", true},
		{"sorted", "loaded", true},
		{"loaded", "unloaded", true},
		{"unloaded", "claimed", true},
		{"claimed", "", false},
		{"lost", "", false},
	}
	for _, c := range cases {
		next, ok := NextCheckpoint(c.current)
		if next != c.next || ok != c.ok {
			t.Errorf("NextCheckpoint(%q) = %q, %v; want %q, %v", c.current, next, ok, c.next, c.ok)
		}
	}
}

func TestStepScansBagToNextCheckpoint(t *testing.T) {
	api, server := newFakeAPI(t, Bag{Tag: "BT100005", Flight: "FL202", Destination: "DEN", Status: "sorted"})
	s := testScanner(server.URL, 1, 0) // one moving bag is enough, no random check-ins

	message, err := s.Step(context.Background())
	if err != nil {
		t.Fatalf("Step: %v", err)
	}
	if message != "BT100005 sorted -> loaded" {
		t.Errorf("message = %q", message)
	}
	scans, limit, _ := api.snapshot()
	if len(scans) != 1 || scans[0] != "BT100005 loaded sc-test" {
		t.Errorf("scans sent to the API = %v", scans)
	}
	if limit != "200" {
		t.Errorf("GET /api/bags limit = %q, want 200", limit)
	}
}

func TestStepChecksInWhenFewBagsAreMoving(t *testing.T) {
	api, server := newFakeAPI(t, Bag{Tag: "BT100001", Status: "claimed"})
	s := testScanner(server.URL, 1, 0) // no bag is moving, so the step must check one in

	message, err := s.Step(context.Background())
	if err != nil {
		t.Fatalf("Step: %v", err)
	}
	if !strings.HasPrefix(message, "BT900002 checked in for FL") {
		t.Errorf("message = %q", message)
	}
	scans, _, bags := api.snapshot()
	added, found := bags["BT900002"]
	if !found || added.Passenger == "" {
		t.Fatalf("new bag not created correctly: %+v", added)
	}
	for _, f := range flights {
		if f.Number == added.Flight && f.Destination != added.Destination {
			t.Errorf("flight %s sent with destination %s, want %s", f.Number, added.Destination, f.Destination)
		}
	}
	if len(scans) != 0 {
		t.Errorf("unexpected scans: %v", scans)
	}
}

func TestStepReturnsAPIErrorDetail(t *testing.T) {
	api, server := newFakeAPI(t, Bag{Tag: "BT100003", Status: "loaded"})
	api.conflict = true
	s := testScanner(server.URL, 1, 0)

	_, err := s.Step(context.Background())
	if err == nil || !strings.Contains(err.Error(), "HTTP 409: Bag BT100003 was moved by another scan") {
		t.Errorf("err = %v", err)
	}
}

func TestStepWhenAPIIsDown(t *testing.T) {
	_, server := newFakeAPI(t)
	server.Close()
	s := testScanner(server.URL, 1, 0)

	if _, err := s.Step(context.Background()); err == nil {
		t.Error("Step returned no error although the API is down")
	}
}

func TestLoopLogsActionsAndStopsWhenCancelled(t *testing.T) {
	api, server := newFakeAPI(t, Bag{Tag: "BT100007", Status: "security"})
	s := testScanner(server.URL, 1, 0)

	var logs bytes.Buffer
	log.SetOutput(&logs)
	defer log.SetOutput(os.Stderr)

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		s.Loop(ctx, 10*time.Millisecond)
		close(done)
	}()
	time.Sleep(200 * time.Millisecond)
	cancel()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Loop did not stop after cancel")
	}

	// The bag moves security -> sorted -> loaded -> unloaded -> claimed, then the scanner checks bags in.
	if !strings.Contains(logs.String(), "scanner sc-test: BT100007 security -> sorted") {
		t.Errorf("log does not show the first scan:\n%s", logs.String())
	}
	if _, _, bags := api.snapshot(); bags["BT100007"].Status != "claimed" {
		t.Errorf("bag status after the loop = %q, want claimed", bags["BT100007"].Status)
	}
}

func TestFormatReport(t *testing.T) {
	stats := Stats{Total: 5, ByStatus: map[string]int{"checked_in": 2, "sorted": 1, "claimed": 2}}
	want := "" +
		"CHECKPOINT     BAGS\n" +
		"checked_in        2\n" +
		"security          0\n" +
		"sorted            1\n" +
		"loaded            0\n" +
		"unloaded          0\n" +
		"claimed           2\n" +
		"total             5\n"
	if got := FormatReport(stats); got != want {
		t.Errorf("FormatReport:\n%s\nwant:\n%s", got, want)
	}
}

func TestReportCommand(t *testing.T) {
	_, server := newFakeAPI(t, Bag{Tag: "BT100001", Status: "claimed"}, Bag{Tag: "BT100002", Status: "loaded"})
	t.Setenv("API_URL", server.URL)

	var out, errOut bytes.Buffer
	if code := run([]string{"report"}, &out, &errOut); code != 0 {
		t.Fatalf("exit code %d, stderr: %s", code, errOut.String())
	}
	if !strings.Contains(out.String(), "loaded            1\n") || !strings.Contains(out.String(), "total             2\n") {
		t.Errorf("report output:\n%s", out.String())
	}

	server.Close()
	out.Reset()
	if code := run([]string{"report"}, &out, &errOut); code != 1 {
		t.Errorf("exit code with the API down = %d, want 1", code)
	}
	if !strings.Contains(errOut.String(), "cannot read stats from bag-api at "+server.URL) {
		t.Errorf("stderr = %q", errOut.String())
	}
}

func TestHealthz(t *testing.T) {
	recorder := httptest.NewRecorder()
	healthHandler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if recorder.Code != http.StatusOK || recorder.Body.String() != "ok\n" {
		t.Errorf("GET /healthz = %d %q", recorder.Code, recorder.Body.String())
	}
}

func TestConfigDefaultsAndErrors(t *testing.T) {
	for _, name := range []string{"API_URL", "SCAN_INTERVAL", "SCANNER_ID", "APP_VERSION", "HEALTH_ADDR"} {
		t.Setenv(name, "")
	}
	cfg, err := loadConfig()
	if err != nil {
		t.Fatalf("loadConfig: %v", err)
	}
	hostname, _ := os.Hostname()
	want := Config{APIURL: "http://bag-api:8000", Interval: 3 * time.Second, ScannerID: hostname, Version: "dev", HealthAddr: ":8081"}
	if cfg != want {
		t.Errorf("defaults = %+v, want %+v", cfg, want)
	}

	t.Setenv("SCAN_INTERVAL", "3") // no unit
	var out, errOut bytes.Buffer
	if code := run([]string{"run"}, &out, &errOut); code != 2 || !strings.Contains(errOut.String(), "SCAN_INTERVAL") {
		t.Errorf("run with a bad SCAN_INTERVAL: exit %d, stderr %q", code, errOut.String())
	}
	if code := run([]string{"fly"}, &out, &errOut); code != 2 {
		t.Errorf("unknown command: exit %d, want 2", code)
	}
}
