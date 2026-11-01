package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Client calls the bag-api HTTP API.
type Client struct {
	baseURL string
	http    *http.Client
}

// NewClient returns a client for the bag-api at baseURL, for example http://bag-api:8000.
func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		http:    &http.Client{Timeout: 5 * time.Second},
	}
}

// Bag holds the bag fields that the scanner uses.
type Bag struct {
	Tag         string `json:"tag"`
	Flight      string `json:"flight"`
	Passenger   string `json:"passenger"`
	Destination string `json:"destination"`
	Status      string `json:"status"`
}

// Stats is the answer of GET /api/stats.
type Stats struct {
	Total    int            `json:"total"`
	ByStatus map[string]int `json:"by_status"`
}

// ListBags returns the most recently updated bags, newest first.
func (c *Client) ListBags(ctx context.Context, limit int) ([]Bag, error) {
	var bags []Bag
	err := c.call(ctx, http.MethodGet, fmt.Sprintf("/api/bags?limit=%d", limit), nil, &bags)
	return bags, err
}

// CheckIn creates a new bag. bag-api chooses the tag.
func (c *Client) CheckIn(ctx context.Context, flight, passenger, destination string) (Bag, error) {
	var bag Bag
	body := map[string]string{"flight": flight, "passenger": passenger, "destination": destination}
	err := c.call(ctx, http.MethodPost, "/api/bags", body, &bag)
	return bag, err
}

// Scan records that the bag passed checkpoint. scannerID says who scanned it.
func (c *Client) Scan(ctx context.Context, tag, checkpoint, scannerID string) (Bag, error) {
	var bag Bag
	body := map[string]string{"checkpoint": checkpoint, "scanner": scannerID}
	err := c.call(ctx, http.MethodPost, "/api/bags/"+url.PathEscape(tag)+"/scans", body, &bag)
	return bag, err
}

// Stats returns the number of bags at each checkpoint.
func (c *Client) Stats(ctx context.Context) (Stats, error) {
	var stats Stats
	err := c.call(ctx, http.MethodGet, "/api/stats", nil, &stats)
	return stats, err
}

// call sends one request. It sends body as JSON (if not nil) and decodes the JSON answer into out.
func (c *Client) call(ctx context.Context, method, path string, body, out any) error {
	var payload io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return err
		}
		payload = bytes.NewReader(data)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, payload)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return err // for example: dial tcp: lookup bag-api: no such host
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return fmt.Errorf("%s %s: HTTP %d: %s", method, path, resp.StatusCode, errorDetail(resp.Body))
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

// errorDetail returns the "detail" message of a bag-api error answer, or the raw answer.
func errorDetail(body io.Reader) string {
	data, _ := io.ReadAll(io.LimitReader(body, 4096))
	var answer struct {
		Detail any `json:"detail"`
	}
	if json.Unmarshal(data, &answer) == nil {
		if text, ok := answer.Detail.(string); ok {
			return text
		}
	}
	return strings.TrimSpace(string(data))
}
