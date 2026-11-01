// Command scanner simulates the baggage scanners at an airport hub.
//
// It calls bag-api over HTTP. Every SCAN_INTERVAL it does one action:
// it checks in a new bag, or it moves a bag to its next checkpoint.
//
//	scanner          run the simulation (same as "scanner run")
//	scanner run      run the simulation until SIGTERM or Ctrl+C
//	scanner report   print the number of bags at each checkpoint, then exit
package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const usage = `Usage:
  scanner          run the simulation (same as "scanner run")
  scanner run      run the simulation until SIGTERM or Ctrl+C
  scanner report   print the number of bags at each checkpoint, then exit

Environment variables:
  API_URL        bag-api address           (default http://bag-api:8000)
  SCAN_INTERVAL  time between two actions  (default 3s)
  SCANNER_ID     name used in logs and scan records (default: the hostname)
  APP_VERSION    version shown in the start line    (default dev)
  HEALTH_ADDR    address for GET /healthz           (default :8081)
`

// Config holds the settings that come from environment variables.
type Config struct {
	APIURL     string
	Interval   time.Duration
	ScannerID  string
	Version    string
	HealthAddr string
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

// run executes one command and returns the exit code.
func run(args []string, stdout, stderr io.Writer) int {
	command := "run"
	if len(args) > 0 {
		command = args[0]
	}
	cfg, err := loadConfig()
	switch command {
	case "run":
		if err != nil {
			fmt.Fprintln(stderr, "scanner:", err)
			return 2
		}
		return runScanner(cfg)
	case "report":
		return runReport(cfg, stdout, stderr)
	case "help", "-h", "--help":
		fmt.Fprint(stdout, usage)
		return 0
	default:
		fmt.Fprintf(stderr, "scanner: unknown command %q\n\n%s", command, usage)
		return 2
	}
}

// loadConfig reads the environment. The error only concerns SCAN_INTERVAL,
// so "scanner report" works even when SCAN_INTERVAL is wrong.
func loadConfig() (Config, error) {
	cfg := Config{
		APIURL:     getenv("API_URL", "http://bag-api:8000"),
		ScannerID:  os.Getenv("SCANNER_ID"),
		Version:    getenv("APP_VERSION", "dev"),
		HealthAddr: getenv("HEALTH_ADDR", ":8081"),
	}
	if cfg.ScannerID == "" {
		cfg.ScannerID, _ = os.Hostname() // the container ID in Docker, the pod name in Kubernetes
	}
	text := getenv("SCAN_INTERVAL", "3s")
	interval, err := time.ParseDuration(text)
	if err != nil || interval <= 0 {
		return cfg, fmt.Errorf("SCAN_INTERVAL must be a positive duration such as 3s or 500ms, not %q", text)
	}
	cfg.Interval = interval
	return cfg, nil
}

func getenv(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

// runScanner runs the simulation until the process gets SIGTERM or SIGINT.
func runScanner(cfg Config) int {
	log.Printf("scanner %s: starting version %s, API %s, interval %s, health on %s",
		cfg.ScannerID, cfg.Version, cfg.APIURL, cfg.Interval, cfg.HealthAddr)

	listener, err := net.Listen("tcp", cfg.HealthAddr)
	if err != nil {
		log.Printf("scanner %s: cannot serve /healthz: %v", cfg.ScannerID, err)
		return 1
	}
	health := &http.Server{Handler: healthHandler(), ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if err := health.Serve(listener); !errors.Is(err, http.ErrServerClosed) {
			log.Printf("scanner %s: health server stopped: %v", cfg.ScannerID, err)
		}
	}()

	// docker stop and Kubernetes send SIGTERM. Ctrl+C sends SIGINT.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		sig := <-signals
		log.Printf("scanner %s: received %s, stopping", cfg.ScannerID, signalName(sig))
		cancel()
	}()

	NewScanner(cfg.ScannerID, NewClient(cfg.APIURL)).Loop(ctx, cfg.Interval)

	shutdownCtx, done := context.WithTimeout(context.Background(), 2*time.Second)
	defer done()
	_ = health.Shutdown(shutdownCtx)
	log.Printf("scanner %s: stopped", cfg.ScannerID)
	return 0
}

func signalName(sig os.Signal) string {
	switch sig {
	case syscall.SIGTERM:
		return "SIGTERM"
	case syscall.SIGINT:
		return "SIGINT"
	}
	return sig.String()
}

// healthHandler answers GET /healthz with "ok". It does not call bag-api:
// if bag-api is down, restarting the scanner would not fix anything.
func healthHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		fmt.Fprintln(w, "ok")
	})
	return mux
}

// runReport prints the bag counts per checkpoint. It returns 1 if bag-api cannot be reached.
func runReport(cfg Config, stdout, stderr io.Writer) int {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	stats, err := NewClient(cfg.APIURL).Stats(ctx)
	if err != nil {
		fmt.Fprintf(stderr, "scanner report: cannot read stats from bag-api at %s: %v\n", cfg.APIURL, err)
		return 1
	}
	fmt.Fprint(stdout, FormatReport(stats))
	return 0
}
