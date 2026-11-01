package main

import (
	"context"
	"fmt"
	"log"
	"math/rand/v2"
	"strings"
	"time"
)

// Checkpoints lists the checkpoints in the order a bag passes them.
// It must match CHECKPOINTS in bag-api (bagtrack/checkpoints.py).
var Checkpoints = []string{"checked_in", "security", "sorted", "loaded", "unloaded", "claimed"}

// NextCheckpoint returns the checkpoint after current.
// ok is false when current is the last checkpoint or not a checkpoint at all.
func NextCheckpoint(current string) (next string, ok bool) {
	for i, name := range Checkpoints {
		if name == current && i+1 < len(Checkpoints) {
			return Checkpoints[i+1], true
		}
	}
	return "", false
}

// Flights that new bags are checked in for, each with its destination.
var flights = []struct{ Number, Destination string }{
	{"FL101", "SFO"}, {"FL202", "DEN"}, {"FL303", "BOS"},
	{"FL404", "MIA"}, {"FL505", "SEA"}, {"FL606", "AUS"},
}

var passengers = []string{
	"Garcia", "Okafor", "Nguyen", "Schmidt", "Rossi", "Kowalski", "Haddad", "Tanaka",
	"Silva", "Novak", "Dubois", "Larsen", "Murphy", "Patel", "Kim", "Moreau",
}

// Scanner simulates one scanner device.
type Scanner struct {
	ID   string
	API  *Client
	Rand *rand.Rand

	// When fewer than MinMoving bags are still moving (not claimed),
	// every step checks in a new bag.
	MinMoving int
	// Otherwise a step checks in a new bag one time in CheckInOneIn
	// and scans a bag the other times. 0 means "never".
	CheckInOneIn int
	// How many recent bags each step reads from bag-api.
	ListLimit int
}

// NewScanner returns a scanner with the default simulation settings.
func NewScanner(id string, api *Client) *Scanner {
	return &Scanner{
		ID:           id,
		API:          api,
		Rand:         rand.New(rand.NewPCG(rand.Uint64(), rand.Uint64())),
		MinMoving:    8,
		CheckInOneIn: 7,
		ListLimit:    200,
	}
}

// Step does one action and returns a log message that describes it.
func (s *Scanner) Step(ctx context.Context) (string, error) {
	bags, err := s.API.ListBags(ctx, s.ListLimit)
	if err != nil {
		return "", err
	}
	var moving []Bag
	for _, bag := range bags {
		if _, ok := NextCheckpoint(bag.Status); ok {
			moving = append(moving, bag)
		}
	}
	randomCheckIn := s.CheckInOneIn > 0 && s.Rand.IntN(s.CheckInOneIn) == 0
	if len(moving) == 0 || len(moving) < s.MinMoving || randomCheckIn {
		return s.checkIn(ctx)
	}

	bag := moving[s.Rand.IntN(len(moving))]
	next, _ := NextCheckpoint(bag.Status)
	if _, err := s.API.Scan(ctx, bag.Tag, next, s.ID); err != nil {
		return "", err
	}
	return fmt.Sprintf("%s %s -> %s", bag.Tag, bag.Status, next), nil
}

func (s *Scanner) checkIn(ctx context.Context) (string, error) {
	flight := flights[s.Rand.IntN(len(flights))]
	passenger := passengers[s.Rand.IntN(len(passengers))]
	bag, err := s.API.CheckIn(ctx, flight.Number, passenger, flight.Destination)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%s checked in for %s to %s", bag.Tag, bag.Flight, bag.Destination), nil
}

// Loop runs Step every interval until ctx is cancelled. Errors are logged, and the loop goes on.
func (s *Scanner) Loop(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			stepCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
			message, err := s.Step(stepCtx)
			cancel()
			switch {
			case ctx.Err() != nil:
				return // shutting down: the request was cancelled on purpose
			case err != nil:
				log.Printf("scanner %s: error: %v", s.ID, err)
			default:
				log.Printf("scanner %s: %s", s.ID, message)
			}
		}
	}
}

// FormatReport returns a table with one line per checkpoint and a total line.
func FormatReport(stats Stats) string {
	var b strings.Builder
	fmt.Fprintf(&b, "%-12s %6s\n", "CHECKPOINT", "BAGS")
	for _, name := range Checkpoints {
		fmt.Fprintf(&b, "%-12s %6d\n", name, stats.ByStatus[name])
	}
	fmt.Fprintf(&b, "%-12s %6d\n", "total", stats.Total)
	return b.String()
}
